"""Walk the streets until a room lists a wandering NPC:  ;seek <noun>

    ;seek peddler            loop the nearby streets from here until a room lists "peddler"
    ;seek peddler rooms=12   a longer loop (default 8 rooms out and back)
    ;seek peddler laps=5     lap the loop this many times before giving up (default 3)
    ;seek peddler from=389   walk to that ;go2 target first and loop from there
    ;seek return             (typed while it runs) walk back to where the search began and end

A wandering NPC — Riverhaven's Tall Human Peddler, who sells the
copper zills — has no room on the map, so ;go2 cannot reach him. This
walks a loop of street rooms from where you stand (or from the `from=`
target): the chain ;attune power-walks, plain compass moves in both
directions, out and back, and reads every room's "You also see ..."
listing (the parser's room objs; LOOK on a session whose parser
predates it) and its players for the noun, whole word, any case. Found:
it stops in that room and says what it saw — "seek: a tall human
Human peddler here" (captured 2026-09-18 on River Road East: "You
also see a Riverhaven Warden, a tall Human peddler and some rickety
steps.") — and does nothing more; asking, ordering and buying are
yours (the peddler: ASK PEDDLER ABOUT INSTRUMENTS lists his six with
their numbers and prices, then "[To purchase something: ORDER # FROM
peddler]"; ORDER 3 FROM PEDDLER bought the copper zills for 500
Lirums, Lirums only; Elanthipedia: Tall Human Peddler). Not found
after the laps: it says
so and stops where the last lap ended, the start. Another player's
room is passed through, never lingered in. It stops on death and when
the map has no street to loop.
Stop with:  ;stop seek (at once), or ;seek return to walk back to the start first.
"""

from client.game import probe
from client.game.mapdb import MapDB
from client.game.seek import loop, parse_args, present
from client.game.walker import avoided_rooms, locate, walk
from client.settings import load_settings

COLLECT_SECONDS = 2  # LOOK's listing, for a parser without room_objs
TAIL_SECONDS = 0.5


def wants_stop(s):
    """True once "return" was typed at the script."""
    while (line := s.command(timeout=0)) is not None:
        if "return" in line.lower():
            return True
    return False


def listing(s):
    """The room's "You also see ..." text: the parser's, or LOOK's
    answer on a session whose parser has no room_objs yet."""
    text = getattr(s.state, "room_objs", None)
    if text is None:
        text = probe.ask(s, "look", COLLECT_SECONDS, TAIL_SECONDS)
    return text or ""


def found_here(s, noun):
    return present(noun, listing(s), getattr(s.state, "room_players", None) or ())


def run(s, options, mapdb, walk_fn=walk, avoid=()):
    noun = options["noun"]
    if options["from"]:
        goals = mapdb.resolve(options["from"])
        if not goals:
            s.echo(f"seek: nothing in the map matches start room {options['from']!r}")
            return
        if not walk_fn(
            s, mapdb, goals, describe=f"start room {options['from']!r}", avoid=avoid
        ):
            s.echo("seek: could not reach the start room — stopping")
            return
    start = locate(mapdb, s.state)
    if start is None:
        s.echo("seek: current room unknown — 'look' once and retry")
        return
    if entry := found_here(s, noun):
        s.echo(f"seek: {entry} here")
        return
    order = loop(mapdb, start, options["rooms"], avoid=avoid)
    if not order:
        s.echo("seek: no street to loop from here — try from= a street")
        return
    titles = [(mapdb.rooms[r].get("title") or ["?"])[0] for r in order]
    s.echo(
        f"seek: looking for {noun!r} along {len(set(order))} rooms, "
        f"{options['laps']} lap(s): {titles[0]} … {titles[len(order) // 2]}"
    )
    for lap in range(1, options["laps"] + 1):
        for room in order:
            if s.dead:
                s.echo("seek: you are dead — stopping; deathwatch has it")
                return
            if wants_stop(s):
                s.echo("seek: returning to the start as asked")
                walk_fn(s, mapdb, {start}, describe="the start", avoid=avoid)
                return
            if room != locate(mapdb, s.state) and not walk_fn(
                s, mapdb, {room}, describe="the next room", avoid=avoid
            ):
                s.echo("seek: the walk failed — stopping")
                return
            if entry := found_here(s, noun):
                s.echo(f"seek: {entry} here")
                return
        s.echo(f"seek: lap {lap} done, no {noun!r} yet")
    s.echo(f"seek: no {noun!r} in {options['laps']} lap(s) — stopping at the start")


def main(s):
    options = parse_args(s.args or [])
    if not options["noun"] or options["noun"].lower() == "return":
        s.echo("seek: what to look for? ;seek <noun> — ;help seek for the options")
        return
    mapdb = MapDB.load()
    avoid = avoided_rooms(mapdb, load_settings().get("avoid_rooms"))
    run(s, options, mapdb, avoid=avoid)
