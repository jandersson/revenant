"""Shared room location and walking for scripts (;go2, ;athletics, ...).

locate() turns parsed game state into a community-map room id; walk()
drives the character along a BFS route from the map database, verifying
arrival room by room. Extracted from ;go2 (this is ;go2's engine) so
any script can travel.
"""

from client.client_logger import ClientLogger
from client.mapdb import normalize_title, translate_embedded

module_logger = ClientLogger()

DIRECTIONS = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "ne": "northeast",
    "nw": "northwest",
    "se": "southeast",
    "sw": "southwest",
    "up": "up",
    "down": "down",
    "out": "out",
}


def locate(db, state):
    """The map id of the current room.

    The game's <nav rm> uid is the exact fix and wins whenever the map
    knows it; titles collide (roads repeat the same title), so the
    title+exits guess is only the fallback. None when position is
    unknown."""
    if state is None:
        return None
    uid = getattr(state, "room_uid", None)
    if uid:
        by_uid = db.room_by_uid(uid)
        if by_uid is not None:
            return by_uid
    title = getattr(state, "room_title", None)
    if not title:
        return None
    candidates = db.rooms_titled(title)
    if not candidates:
        return None
    return _disambiguate(db, candidates, state.compass)


def _disambiguate(db, candidates, compass):
    """Same title, several rooms: prefer the one whose exits match ours."""
    if len(candidates) == 1 or not compass:
        return candidates[0]
    here_exits = {DIRECTIONS.get(direction, direction) for direction in compass}

    def exits_of(room_id):
        wayto = db.rooms[room_id].get("wayto") or {}
        return {
            command
            for command in wayto.values()
            if isinstance(command, str) and command in DIRECTIONS.values()
        }

    return max(candidates, key=lambda room_id: len(here_exits & exits_of(room_id)))


def walk(s, db, goals, describe="destination"):
    """Walk to the nearest goal room; True on arrival (or already there).

    Echoes progress and failure detail the way ;go2 always has: stalls
    and off-course rooms stop the walk rather than guessing onward."""
    if s.dead:
        s.echo("you are DEAD — corpses don't travel; deathwatch has it (#91)")
        return False
    here = locate(db, s.state)
    if here is None:
        title = getattr(s.state, "room_title", None) if s.state else None
        if title and not db.rooms_titled(title):
            s.echo(f"room {title!r} is not in the map database")
        else:
            s.echo("current room unknown yet — 'look' once and retry")
        return False
    route = db.path(here, set(goals))
    if route is None:
        s.echo(f"no walkable path to {describe} (a scripted-only edge may be needed)")
        return False
    if not route:
        return True

    s.echo(f"walking {len(route)} steps to {describe}")
    for number, (dest, command) in enumerate(route, 1):
        if s.dead:
            s.echo(f"died en route at step {number} — stopping; deathwatch takes it")
            return False
        # A scripted edge translates to several game commands; the last
        # one lands in the destination room and gets the arrival check.
        commands = translate_embedded(command) or [command]
        s.waitrt()
        for preliminary in commands[:-1]:
            s.put(preliminary)
            s.waitrt()
        # Discard any stale compass frames so the next one that arrives
        # pairs with this move — a spurious frame must never desync the
        # walk (the double-frame bug, structurally prevented).
        while s.get(timeout=0, streams=("compass",)) is not None:
            pass
        s.put(commands[-1])
        arrived = s.get(timeout=15, streams=("compass",)) is not None
        if not arrived:
            # Engaged: moves and climbs refuse until retreated out to
            # missile range (docs/combat.md) — burst retreat/retreat/
            # step through the type-ahead and give the step one retry.
            # Unconditionally: hostile state can be empty while engaged
            # (#88 — the #85 wipe left a walker stalled at melee with a
            # clean hostiles dict, and it walked away from the fight by
            # exiting), and a retreat while unengaged is harmless.
            s.put("retreat")
            s.put("retreat")
            s.put(commands[-1])
            arrived = s.get(timeout=15, streams=("compass",)) is not None
        if not arrived:
            s.echo(f"stalled at step {number} ({commands[-1]!r}) — stopping here")
            return False
        # Arrival check: the nav uid is exact when the map knows it;
        # title comparison is the fallback for unmapped-uid rooms.
        uid = getattr(s.state, "room_uid", None)
        mapped = db.room_by_uid(uid) if uid else None
        if mapped is not None:
            if mapped != dest:
                s.echo(
                    f"off course at step {number}: in room {mapped} "
                    f"({s.state.room_title!r}), expected {dest} — stopping here"
                )
                return False
            continue
        expected = db.rooms[dest].get("title") or []
        actual = s.state.room_title
        if expected and actual:
            wanted = {normalize_title(title) for title in expected}
            if normalize_title(actual) not in wanted:
                s.echo(
                    f"off course at step {number}: in {actual!r}, expected "
                    f"{expected[0]!r} — stopping here"
                )
                return False
    s.waitrt()
    return True
