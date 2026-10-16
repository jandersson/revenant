"""A caravan or a guild pack animal walked room by room, waited for at
every step (trade.lic's take_caravan_to): ;trade brings its caravan in
when a lead stops short of the outpost, ;commodities walks the pack
animal the guild lends with a pit's goods (#557).

TELL <it> TO FOLLOW ("You grab hold of your lumbering auroch's harness
and make it follow." for an animal, the driver's order for a caravan),
then each move waits for "Your lumbering auroch ..., following you."
Alfren's Ferry and the Faldesu's are ridden with it aboard (a fare the
purse lacks fetched by ;bank, the caravan told to wait at the dock), the
Obsidian Pass gondola too; a scripted edge it cannot follow ends the
walk before it starts.
"""

import re

from client.game import travel, walker
from client.game.act import ask, said
from client.game.mapdb import pause_seconds, ride_args, ride_of, translate_embedded
from client.game.trade import FOLLOW_ORDERED, FOLLOWING

FOLLOW_SECONDS = 30  # a step's wait for the caravan to catch up
# A command sent in roundtime is dropped: "...wait 3 seconds." (an INV
# LIST typed mid-walk took a step's move, 2026-10-15).
# A regex, as waitfor matches: "...wait" unescaped took "city waits" in
# the Road to Shard's description for it (2026-10-15).
WAITED = r"^\.\.\.wait \d+ seconds?\."
FERRY = "ferry"  # a route step the walker rides: Alfren's Ferry, the Faldesu's,
GONDOLA = "gondola"  # the Hibarnhvidar-Ain Ghazal ferry, and the Obsidian Pass gondola
RIDDEN = {  # the map's names
    "ferry": FERRY,
    "faldesu": FERRY,
    "ferry1": FERRY,  # #555: a lead to Ain Ghazal ends at Hibarnhvidar's dock
    "gondola": GONDOLA,
}


def steps(route):
    """Each edge of a route as the game commands it sends — FERRY for
    Alfren's Ferry and the Faldesu's, GONDOLA for the gondola, which the
    walker rides (the bank or the cab's direction the argument) — or
    None when one is a scripted edge a caravan cannot follow."""
    out = []
    for _, command in route:
        ride = RIDDEN.get(ride_of(command)) if command.startswith(";e") else None
        if ride:
            out.append((ride, ride_args(command)))
            continue
        sent = translate_embedded(command) if command.startswith(";e") else [command]
        if not sent:
            return None
        out.append(sent)
    return out


def fare(s, db, name, coin):
    """A ferry fare the purse lacked (a run back from Ilithi carries only
    Dokoras: "You haven't got enough kronars to pay for your trip."),
    fetched by ;bank at the nearest teller with the caravan told to wait
    at the dock: True back at the dock with the caravan following."""
    dock = travel.here(s, db)
    ask(s, f"tell {name} to wait")
    if not walker.fetch_fare(s, coin[0] if coin else ""):
        return False
    if travel.here(s, db) != dock and not travel.go(s, {dock}, "the ferry dock", db=db):
        return False
    return said(ask(s, f"tell {name} to follow"), FOLLOW_ORDERED)


def bring(s, db, name, room, prefix):
    """Walk the caravan (or animal) `name` to `room` one room at a time,
    waiting for it to follow each; True there, told to wait. False,
    said under `prefix`, when there is no plain walk, it will not follow,
    a ride fails or it falls behind."""
    here = travel.here(s, db)
    if here == room:
        return True
    route = db.path(here, [room]) if here is not None else None
    edges = steps(route) if route else None
    if not edges:
        s.echo(f"{prefix}: no plain walk from here — bring your {name} yourself")
        return False
    if not said(ask(s, f"tell {name} to follow"), FOLLOW_ORDERED):
        s.echo(f"{prefix}: your {name} would not follow")
        return False
    for commands in edges:
        s.clear()
        if commands[0] == FERRY:
            # The caravan follows aboard and off again; GO DOCK is the
            # step it is waited for on.
            ride = walker.ride_ferry(s, commands[1])
            if ride.startswith("fare") and fare(s, db, name, ride.split()[1:]):
                ride = walker.ride_ferry(s, commands[1])
            if ride != "landed":
                s.echo(f"{prefix}: the ferry crossing failed — your {name} is with you")
                return False
            commands = ["go dock"]
        elif commands[0] == GONDOLA:
            # The caravan follows into the cab, and the cab's direction
            # waits for it (trade.lic's ride_gondola); OUT is the step
            # it is waited for on after.
            ride = walker.ride_gondola(
                s,
                commands[1],
                aboard=lambda: s.waitfor(FOLLOWING, timeout=FOLLOW_SECONDS),
            )
            if ride != "landed":
                s.echo(
                    f"{prefix}: the gondola ride failed ({ride}) — your {name} is with you"
                )
                return False
            commands = ["out"]
        for command in commands:
            pause = pause_seconds(command)
            if pause is not None:
                s.sleep(pause)
                continue
            s.waitrt()
            s.put(command)
        line = s.waitfor(FOLLOWING, WAITED, timeout=FOLLOW_SECONDS)
        if line is not None and re.search(WAITED, line):
            s.waitrt()
            s.put(commands[-1])
            line = s.waitfor(FOLLOWING, timeout=FOLLOW_SECONDS)
        if line is None:
            s.echo(f"{prefix}: your {name} fell behind after {commands[-1]!r}")
            return False
    ask(s, f"tell {name} to wait")
    return travel.here(s, db) == room
