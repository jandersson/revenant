"""Train Outdoorsmanship by collecting — COLLECT rock, wait, again:  ;forage

    ;forage              COLLECT rock PRACTICE until Outdoorsmanship mind-locks
    ;forage <item>       another item the map tags rooms with (dirt, moss, ...)
    ;forage <item> <n>   n collects, then end
    ;forage here         collect where you stand even if the map lists no such item here
    ;forage return       (typed while it runs) finish the collect in hand and end

Outdoorsmanship trains by foraging, and COLLECT for the easiest item
pays best — "the easier item you collect, the more you will get, which
grants more experience" (Elanthipedia: Outdoorsmanship skill, Collect
command); COLLECT <item> PRACTICE "gains experience without generating
items", so nothing is left in piles. Perception rides along: COLLECT
is its most efficient foraging (Elanthipedia: Perception skill). The
community map tags each room with what can be foraged there (`rock`
on the Crossing's streets), so a room without the item is left for
the nearest one that has it, through the shared walker, unless
`here`. Captured 2026-09-14 on the Crossing's streets at rank 1: the
practice answers "You wander around and poke your fingers into a few
places, wondering what you might find." and "You find something dead
and lifeless, is this what you were looking for?" (6 s roundtime —
not the wiki's 15 — and Outdoorsmanship 1 74% dabbling → learning on
the first), the near misses "You are certain you could find what you
were looking for, if you had a bit more luck." / "You are sure you
knew what you were looking for when you started to forage." / "You
begin to forage around, but can't quite seem to remember what it was
you were looking for.", and "You forage
around but are unable to find anything." (6 s), which a room without
the item answers every time and a room with it answers on a failed
try, so three of those in a row end the run only before the first
success (ten in a row after). The wordings grow with the ranks
(captured 2026-09-20 on the same rocks): the success is "You begin
exploring the area, searching for a rock.  In almost no time, you
manage to identify 2 of them but leave them where they are,
undisturbed." (15 s), often after "You move slightly to the right,
hoping to find a better foraging spot.", and a miss can say "You
forage around and believe you would probably have better luck trying
to find a dragon's egg than what you were looking for." (4 s). An
answer outside the table is echoed once per wording and the run goes on.
Stops at mind-lock, on death, on hostiles in the room, and on
`return`. ;train runs it as a task (skills:
["Outdoorsmanship"], return_word "return").
Stop with:  ;stop forage (at once), or ;forage return for a clean finish.
"""

from client.game import flight, probe
from client.game.loop import danger, wants_stop
from client.game.buffs import locked
from client.game.mapdb import MapDB
from client.game.walker import avoided_rooms, locate, walk
from client.settings import load_settings

ITEM = "rock"
SKILL = "Outdoorsmanship"
EMPTY_LIMIT = 3  # empty answers in a row before giving up, nothing found yet
EMPTY_STREAK = 10  # ... once something was: a failed try answers the same
MAX_COLLECTS = 2000  # the fuse
COLLECT_SECONDS = 3  # the answer lands before the roundtime
TAIL_SECONDS = 0.5

# Captured 2026-09-14 (#193): the same empty answer in a room with
# nothing to collect and on a failed try where there is; the practice
# line on a success. An answer outside every table still counts as a
# collect (the roundtime says one went out) and is reported once per
# wording.
_EMPTY = ("unable to find anything",)
# The practice success at higher ranks (captured 2026-09-20, Cecil on
# the Crossing's rocks, 15 s roundtime): "You begin exploring the area,
# searching for a rock.  In almost no time, you manage to identify 2 of
# them but leave them where they are, undisturbed." — often after "You
# move slightly to the right, hoping to find a better foraging spot."
_COLLECTED = (
    "poke your fingers",
    "dead and lifeless",
    "you collect",
    "pile",
    "leave them where they are",
    "manage to identify",
)
# A failed try that says the item is here, in three flavors (2026-09-14):
# "You are certain you could find what you were looking for, if you had
# a bit more luck.", "You are sure you knew what you were looking for
# when you started to forage.", "You begin to forage around, but can't
# quite seem to remember what it was you were looking for."
_TRIED = (
    "a bit more luck",
    "knew what you were looking for",
    "remember what it was you were looking for",
    # A miss at higher ranks (2026-09-20, 4 s roundtime, three times in
    # a room that gave 9 successes and 25 empty answers): "You forage
    # around and believe you would probably have better luck trying to
    # find a dragon's egg than what you were looking for."
    "dragon's egg",
)
_REFUSED = ("can't do that", "cannot do that", "not something you can", "what were you")


def parse_args(args):
    options = {"item": ITEM, "count": 0, "here": False}
    for arg in args:
        low = arg.strip().lower()
        if not low:
            continue
        if low == "here":
            options["here"] = True
        elif low.isdigit():
            options["count"] = int(low)
        else:
            options["item"] = low
    return options


def classify(answer):
    """ "empty" (nothing here), "refused", "ok", "tried" (a failed try
    that says the item is here), or None for a wording outside the
    tables."""
    lowered = answer.lower()
    if any(word in lowered for word in _EMPTY):
        return "empty"
    if any(word in lowered for word in _REFUSED):
        return "refused"
    if any(word in lowered for word in _COLLECTED):
        return "ok"
    if any(word in lowered for word in _TRIED):
        return "tried"
    return None


def first_line(answer):
    return (answer.strip().splitlines() or ["(silence)"])[0]


def find_item(s, db, item, avoid=()):
    """True standing in a room the map tags with the item: here already,
    or after a walk to the nearest one. False when the map tags no room
    with it or the walk failed."""
    tagged = set(db.rooms_tagged(item))
    if not tagged:
        s.echo(f"forage: the map tags no room with {item!r} — try ;forage {item} here")
        return False
    if locate(db, s.state) in tagged:
        return True
    s.echo(f"forage: no {item} here on the map — walking to the nearest room with some")
    return walk(s, db, tagged, describe=item, avoid=avoid)


def run(s, options, db=None, avoid=()):
    """The loop; returns why it ended and how many collects went out."""
    item, count = options["item"], options["count"]
    if db is not None and not options["here"] and not find_item(s, db, item, avoid):
        return "no room to collect in", 0
    collected = successes = empties = 0
    seen = set()
    for _ in range(MAX_COLLECTS):
        if reason := danger(s):
            return reason, collected
        if wants_stop(s):
            return "returning on request", collected
        if locked(s.state, [SKILL]):
            return f"{SKILL} mind-locked", collected
        if count and collected >= count:
            return f"{count} collect(s) done", collected
        answer = probe.ask(s, f"collect {item} practice", COLLECT_SECONDS, TAIL_SECONDS)
        outcome = classify(answer)
        if outcome == "empty":
            empties += 1
            limit = EMPTY_STREAK if successes else EMPTY_LIMIT
            if empties >= limit:
                return (
                    f"nothing to collect here ({limit} empty answers in a row)",
                    collected,
                )
            continue
        if outcome == "refused":
            return f"refused: {first_line(answer)}", collected
        empties = 0
        collected += 1
        if outcome == "ok":
            successes += 1
        elif outcome is None:
            first = first_line(answer)
            if first not in seen:
                seen.add(first)
                s.echo(
                    f"forage: unrecognized collect answer {first!r} — please report it"
                )
    return "collect fuse spent", collected


def main(s):
    options = parse_args(s.args or [])
    db = None if options["here"] else MapDB.load()
    avoid = avoided_rooms(db, load_settings().get("avoid_rooms")) if db else ()
    reason, collected = run(s, options, db=db, avoid=avoid)
    s.echo(f"forage: {reason} — {collected} collect(s) of {options['item']}")
    if "hostiles" in reason:
        flight.react(s, "forage")
