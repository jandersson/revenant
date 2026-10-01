"""The one way to walk: a ;go2 target resolved, avoid_rooms routed around.

    travel.go(s, "bank", "the bank teller")   # a tag, an id, a title, or ids; True on arrival
    travel.here(s)                            # the map id of the room, or None
    travel.mapdb()                            # the map, parsed once
    travel.avoided(db)                        # settings.json's avoid_rooms as ids

A test passes its fakes as db= and walk= (the walker's arguments, avoid
included); avoid=() walks through anything. go() says "nothing in the
map matches <describe>" and returns False when nothing does.
"""

from client.game import walker
from client.game.mapdb import MapDB
from client.settings import setting

_NOTES = """
Seven of the twenty-two walking scripts honoured avoid_rooms before
#407; the rest resolved and walked their own way, each with its own
"nothing in the map matches" line.
"""


def mapdb():
    """The community map, parsed once a process (MapDB.load)."""
    return MapDB.load()


def avoided(db=None):
    """The rooms settings.json's avoid_rooms names, as ids in `db`."""
    return walker.avoided_rooms(db or mapdb(), setting("avoid_rooms"))


def goals_of(db, target):
    """The room ids a target names: an id, a tag, a title substring (a
    ;go2 target, as text), or ids given outright; empty when nothing in
    the map matches."""
    if isinstance(target, bool):
        return set()
    if isinstance(target, int):
        return {target} if target in db.rooms else set()
    if isinstance(target, str):
        return set(db.resolve(target.strip())) if target.strip() else set()
    return {int(room) for room in target if int(room) in db.rooms}


def here(s, db=None):
    """The map id of the room the character stands in, or None."""
    return walker.locate(db or mapdb(), getattr(s, "state", None))


def go(s, target, describe=None, *, db=None, walk=None, avoid=None, max_steps=None):
    """Walk to the nearest room `target` names; True on arrival (or
    there already), False said when nothing in the map matches, or as
    the walker says why."""
    db = db or mapdb()
    describe = describe or repr(target)
    goals = goals_of(db, target)
    if not goals:
        s.echo(f"nothing in the map matches {describe}")
        return False
    if avoid is None:
        avoid = avoided(db)
    walk = walk or walker.walk
    extra = {} if max_steps is None else {"max_steps": max_steps}
    return bool(walk(s, db, goals, describe=describe, avoid=avoid, **extra))
