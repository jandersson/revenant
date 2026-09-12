"""Shared room location and walking for scripts (;go2, ;athletics, ...).

locate() turns parsed game state into a community-map room id; walk()
drives the character along a BFS route from the map database, verifying
arrival room by room. Extracted from ;go2 (this is ;go2's engine) so
any script can travel. A climb the game turns back for footing (#157)
gets one retry standing with the hindering items stowed, then stops
with what would help; an engagement gets the retreat burst, unless
the room's only exit is "out" — a bank or shop, where nothing engages
and a retreat has nowhere to go (#171) (docs/movement.md).
"""

import re
from time import monotonic

from client.client_logger import ClientLogger
from client.game.mapdb import normalize_title, translate_embedded

module_logger = ClientLogger()

ARRIVAL_TIMEOUT = 15  # seconds for the compass frame after a move

# The felled tree, captured 2026-09-11 (#157): a climb beyond the
# character's Athletics — worse armed and armored — is turned back
# with these two lines and no room change. The first names what
# hinders; "Your oak-hafted handaxe and plate vambraces make the climb
# more difficult." The second is the refusal.
# Going up: "...your footing is questionable. Reluctantly, you climb
# back down." Going down (captured 2026-09-12 on the Arthe Dale oak):
# "You attempt to climb down the tree, but you can't seem to find
# purchase." and "You start down the tree, but you find it hard going.
# Rather than risking a fall, you make your way back up." — unknown,
# they read as a stall and drew the retreat burst in a tree house.
# A third descent wording came on the next walk: "Trying to judge the
# climb, you peer over the edge.  A wave of dizziness hits you, and you
# back away from the tree."
CLIMB_REFUSALS = (
    "footing is questionable",
    "climb back down",
    "find purchase",
    "make your way back up",
    "back away from the tree",
)
# A climb (or a stow) attempted sitting — what a turned-back climb
# leaves you — answers with these (captured on the retry, 2026-09-11);
# the same retry, which STANDs first, is the remedy.
POSTURE_REFUSALS = ("You must be standing", "You must stand first")
_HINDERS = re.compile(r"Your (.+?) makes? the climb more difficult")


def hindering_nouns(text):
    """The nouns of the items a "make the climb more difficult" line
    names — "oak-hafted handaxe and plate vambraces" → handaxe,
    vambraces — the words STOW takes."""
    match = _HINDERS.search(text)
    if not match:
        return []
    items = re.split(r",\s*|\s+and\s+", match.group(1))
    return [item.split()[-1] for item in items if item.strip()]


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


def avoided_rooms(db, entries):
    """The room ids an avoid list names — each entry resolved like a
    ;go2 target (tag, room id, or title substring). The standing list
    lives in settings ("avoid_rooms"); scripts resolve it once per db."""
    rooms = set()
    for entry in entries or []:
        rooms.update(db.resolve(str(entry)))
    return rooms


def await_arrival(s, timeout=ARRIVAL_TIMEOUT):
    """Wait for the compass frame that means the move landed, reading
    the story meanwhile for a climb turned back. ("arrived" | "refused"
    | "stalled", the hindering item nouns a refusal named)."""
    deadline = monotonic() + timeout
    hindering = []
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return "stalled", hindering
        item = s.get(timeout=remaining, streams=None)
        if item is None:
            return "stalled", hindering
        stream, text = item
        if stream == "compass":
            return "arrived", hindering
        if stream:
            continue  # a dock's stream: not the story
        hindering.extend(hindering_nouns(text))
        if any(needle in text for needle in CLIMB_REFUSALS + POSTURE_REFUSALS):
            return "refused", hindering


def retry_climb(s, command, hindering):
    """The one retry a turned-back climb gets: the refusal's roundtime
    waited out, STAND (a failed climb sits you down, and the posture
    indicator lands a beat after the refusal text — reading it at once
    said "standing" and both STOWs answered "You must stand first.",
    captured 2026-09-11; standing already, STAND is harmless), the
    hindering items stowed (a worn piece answers STOW with a refusal,
    harmless), the climb again. Returns await_arrival's answer."""
    s.waitrt()
    s.put("stand")
    s.waitrt()
    steps = ["stood up"]
    for noun in hindering:
        s.put(f"stow my {noun}")
        s.waitrt()
    if hindering:
        steps.append("stowed " + ", ".join(hindering))
    s.echo(f"the climb was turned back — {', '.join(steps)}, trying it once more")
    while s.get(timeout=0, streams=("compass",)) is not None:
        pass
    s.put(command)
    return await_arrival(s)


def walk(s, db, goals, describe="destination", avoid=()):
    """Walk to the nearest goal room; True on arrival (or already there).

    Rooms in `avoid` are routed around when a clean detour exists;
    a route forced through them is announced before the first step.
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
    avoid = frozenset(avoid)
    route = db.path(here, set(goals), avoid=avoid)
    if route is None:
        s.echo(f"no walkable path to {describe} (a scripted-only edge may be needed)")
        return False
    if not route:
        return True

    crossed = [dest for dest, _ in route if dest in avoid]
    if crossed:
        titles = db.rooms[crossed[0]].get("title") or ["?"]
        s.echo(
            f"warning: no clean detour — the route crosses "
            f"{len(crossed)} avoided room(s), first {titles[0]}"
        )
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
        outcome, hindering = await_arrival(s)
        if outcome == "refused":
            # A climb beyond the character's Athletics (#157): one
            # retry standing and unburdened, then the truth and a stop.
            outcome, again = retry_climb(s, commands[-1], hindering)
            if outcome == "refused":
                load = ", ".join(dict.fromkeys(hindering + again))
                s.echo(
                    f"the climb at step {number} ({commands[-1]!r}) is beyond "
                    "your Athletics"
                    + (f" with your {load}" if load else "")
                    + " — shed the load, train it (;athletics), or take the "
                    "long way — stopping here"
                )
                return False
            if outcome == "arrived" and hindering:
                s.echo(
                    f"made it with your {', '.join(hindering)} stowed — "
                    "get what you need back out"
                )
        if outcome == "stalled":
            # Engaged: moves and climbs refuse until retreated out to
            # missile range (docs/combat.md) — burst retreat/retreat/
            # step through the type-ahead and give the step one retry.
            # Unconditionally: hostile state can be empty while engaged
            # (#88 — the #85 wipe left a walker stalled at melee with a
            # clean hostiles dict, and it walked away from the fight by
            # exiting), and a retreat while unengaged is harmless —
            # except where the only exit is "out" (a bank's lobby, a
            # shop, #171): nothing engages there and a retreat answers
            # "You are already as far away as you can get!", so the
            # step gets its one retry alone.
            if list(getattr(s.state, "compass", None) or []) != ["out"]:
                s.put("retreat")
                s.put("retreat")
            s.put(commands[-1])
            outcome, _ = await_arrival(s)
        if outcome != "arrived":
            s.echo(f"stalled at step {number} ({commands[-1]!r}) — stopping here")
            return False
        # Arrival check: the nav uid is exact when the map knows it;
        # title comparison is the fallback for unmapped-uid rooms.
        uid = getattr(s.state, "room_uid", None)
        mapped = db.room_by_uid(uid) if uid else None
        if mapped is not None:
            # A twin of the planned room is the planned room: the map
            # lists some places twice, only one entry carrying the
            # game's uid (#137).
            if not db.same_place(mapped, dest):
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
