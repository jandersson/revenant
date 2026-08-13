"""Pathfind and walk anywhere the community map knows:  ;go2 <target>

Targets: a room id (;go2 1234), a tag (;go2 bank), or a title substring
(;go2 herald street). ;go2 alone reports where the map thinks you are;
;go2 update refreshes the database. First use downloads it (~13MB) into
~/.revenant/mapdb/.
"""

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


def main(s):
    from client.mapdb import MapDB, download, mapdb_path, normalize_title

    if s.args and s.args[0] == "update":
        s.echo("downloading map database ...")
        s.echo(f"updated {download()}")
        return
    if not mapdb_path().is_file():
        s.echo("downloading map database (first use, ~13MB) ...")
        download()
    db = MapDB.load()

    here = locate(db, s.state)
    if here is None:
        title = getattr(s.state, "room_title", None) if s.state else None
        if title and not db.rooms_titled(title):
            s.echo(f"room {title!r} is not in the map database")
        else:
            s.echo("current room unknown yet — 'look' once and retry")
        return

    if not s.args:
        titles = db.rooms[here].get("title") or ["?"]
        s.echo(f"you are in room {here}: {titles[0]}")
        s.echo("usage: ;go2 <room id | tag | title substring>")
        return

    query = " ".join(s.args)
    goals = db.resolve(query)
    if not goals:
        s.echo(f"nothing in the map matches {query!r}")
        return
    route = db.path(here, goals)
    if route is None:
        s.echo(f"no walkable path to {query!r} (a scripted-only edge may be needed)")
        return
    if not route:
        s.echo("you are already there")
        return

    s.echo(f"walking {len(route)} steps to {query!r}")
    dest = here
    for number, (dest, command) in enumerate(route, 1):
        s.waitrt()
        # Discard any stale compass frames so the next one that arrives
        # pairs with this move — a spurious frame must never desync the
        # walk (the double-frame bug, structurally prevented).
        while s.get(timeout=0, streams=("compass",)) is not None:
            pass
        s.put(command)
        if s.get(timeout=15, streams=("compass",)) is None:
            s.echo(f"stalled at step {number} ({command!r}) — stopping here")
            return
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
                return
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
                return
    s.waitrt()
    s.echo(f"arrived: {s.state.room_title} (room {dest})")


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
