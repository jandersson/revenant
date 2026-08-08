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

    here_title = s.state.room_title if s.state else None
    if not here_title:
        s.echo("current room unknown yet — 'look' once and retry")
        return
    candidates = db.rooms_titled(here_title)
    if not candidates:
        s.echo(f"room {here_title!r} is not in the map database")
        return
    here = _disambiguate(db, candidates, s.state.compass)

    if not s.args:
        s.echo(f"you are in room {here}: {here_title}")
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
        s.put(command)
        if s.get(timeout=15, streams=("compass",)) is None:
            s.echo(f"stalled at step {number} ({command!r}) — stopping here")
            return
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
