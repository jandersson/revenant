"""Pathfind and walk anywhere the community map knows:  ;go2 <target>

Targets: a room id (;go2 1234), a tag (;go2 bank), or a title substring
(;go2 herald street). Routes take the fastest way the map knows (its
timeto travel times) and detour around the rooms your avoid list names
(settings "avoid_rooms" — cougar grounds by default) whenever a clean
way around exists; ;go2 direct <target> skips the detour for one trip.
;go2 alone reports where the map thinks you are; ;go2 update refreshes
the database. First use downloads it (~13MB) into ~/.revenant/mapdb/.
The location and walking engine lives in client/walker.py, shared with
other traveling scripts.
"""

from client.walker import DIRECTIONS, avoided_rooms, locate, walk  # noqa: F401


def main(s):
    from client.mapdb import MapDB, download, mapdb_path
    from client.settings import setting

    if s.args and s.args[0] == "update":
        s.echo("downloading map database ...")
        s.echo(f"updated {download()}")
        return
    if not mapdb_path().is_file():
        s.echo("downloading map database (first use, ~13MB) ...")
        download()
    db = MapDB.load()

    avoid = avoided_rooms(db, setting("avoid_rooms"))
    if s.args and s.args[0] == "direct":
        avoid = set()
        s.args = s.args[1:]

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
    if walk(s, db, goals, describe=repr(query), avoid=avoid):
        final = locate(db, s.state)
        s.echo(f"arrived: {s.state.room_title} (room {final})")
