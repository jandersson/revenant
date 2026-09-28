"""Train Outdoorsmanship by collecting, nothing left in piles:  ;forage

    ;forage              COLLECT rock PRACTICE until Outdoorsmanship mind-locks
    ;forage <item>       another item the map tags rooms with (dirt, moss, ...)
    ;forage <item> <n>   n collects, then end
    ;forage here         collect where you stand, even if the map lists no such item here
    ;forage herb red flower [pieces=25]
                         FORAGE a remedy's herb until that many pieces, then dry and combine them
    ;forage return       (typed while it runs) finish the collect in hand and end
    ;stop forage         quit at once

What it does
  - Walks to the nearest room the community map tags with the item, unless `here`
    (settings.json's `avoid_rooms` are walked around).
  - COLLECT <item> PRACTICE again and again: experience without items;
    Perception trains alongside.
  - herb: FORAGE <herb> PRECISE (Remedial Herb Gathering; plain FORAGE without it),
    finds into the loot container; then, at the Crossing Alchemy
    Society's dry press, each is pressed and all are combined into one dried stack.
  - Both hands full: STOWs what they hold, never a drop, and goes on.

When it stops
  - Outdoorsmanship mind-locks, or the <n> collects are done (herb: the pieces)
  - nothing to find: 3 empty answers in a row before a first success, 10 after
    (herb: 40 tries without a find)
  - a refusal, or no hand could be freed
  - death, or hostiles in the room (it flees)
  - ;forage return (herb: the finds so far are still pressed)

;train runs it as a task for Outdoorsmanship. The method is Elanthipedia's
(Outdoorsmanship skill, Collect command). Report any "forage: unrecognized ..." line.
"""

import re

from client.game import flight, probe
from client.game.loop import danger, wants_stop
from client.game.buffs import locked
from client.game.mapdb import MapDB
from client.game.walker import avoided_rooms, locate, walk
from client.settings import load_settings

# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Train Outdoorsmanship by collecting — COLLECT rock, wait, again:  ;forage

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

The herb mode (#370, captured 2026-09-28 on a circle-14 Paladin,
Outdoorsmanship 66, the Crossing): FORAGE RED FLOWER finds about one
try in four or five — "You manage to find some red flowers." (6
pieces, COUNT: "You count out 6 pieces of material there."); the
plural name answers "can't quite seem to remember what it was you
were looking for" and never finds, so the herb is the wiki's forage
name (Elanthipedia: Red flower). COLLECT RED FLOWER found nothing in
15 at that rank (a pile's size is skill against the herb's
difficulty). A raw herb will not COMBINE ("The flowers must first be
prepared before it can be combined with anything else."); the
Alchemy Society's Tool Shop has a public dry press (LOOK: "A large
iron press designed for fast drying of herbs and spices."): PUT MY
FLOWERS IN PRESS — "... You then crank the press open and remove some
dried red flowers." (5-7 s); a dried one answers "That herb already
appears prepared, and so you stop." Dried stacks join: "You combine
the stacks of herbs together." A remedy takes five pieces a use, so
the stack's size is ;remedies' to use (#370). With the Remedies
technique Remedial Herb Gathering, FORAGE RED FLOWER PRECISE found on
three tries in three, 10, 9 and 10 pieces, at 10 s of roundtime (plain:
about one in five, 6 pieces, 3-4 s) — about three times the pieces a
minute; COUNT waits the roundtime out ("...wait 1 seconds." otherwise).
"""

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
# Both hands full (captured 2026-09-26: a stopped ;remedies left the
# pestle and the mortar in them): "You really need to have at least one
# hand free to properly collect something." — 1263 times in nineteen
# minutes, no roundtime, until the fuse. The hands are freed with STOW.
_HANDS_FULL = ("at least one hand free",)

# The herb mode (#370, captured 2026-09-28; the wordings in _NOTES).
HERB_PIECES = 25  # a bought stack's size: five uses of a remedy
HERB_MISSES = 40  # tries without a find before the run gives up
PRESS_ROOMS = (8860,)  # the Crossing Alchemy Society's Tool Shop: a dry press
_HERB_FOUND = re.compile(r"you manage to find (?:some |an? )?(?P<what>[^.!]+)", re.I)
_PIECES = re.compile(r"count out (\d+) pieces?")
_PRESSED = ("remove some dried",)
_PREPARED = ("already appears prepared",)
_COMBINED = ("you combine",)
_STOWED_IN = re.compile(r"you put your .+? in your (?P<container>[^.]+)\.", re.I)
_GOT = ("you get", "you pick up", "you are already holding")


def parse_args(args):
    options = {"item": ITEM, "count": 0, "here": False}
    words = [arg.strip().lower() for arg in args if arg.strip()]
    if words and words[0] == "herb":
        # ;forage herb red flower [pieces=N] [here]
        options.update(herb=True, pieces=HERB_PIECES)
        name = []
        for low in words[1:]:
            if low == "here":
                options["here"] = True
            elif low.startswith("pieces=") and low[7:].isdigit():
                options["pieces"] = int(low[7:])
            else:
                name.append(low)
        options["item"] = " ".join(name)
        return options
    for low in words:
        if low == "here":
            options["here"] = True
        elif low.isdigit():
            options["count"] = int(low)
        else:
            options["item"] = low
    return options


def classify(answer):
    """ "hands full", "empty" (nothing here), "refused", "ok", "tried" (a failed try
    that says the item is here), or None for a wording outside the
    tables."""
    lowered = answer.lower()
    if any(word in lowered for word in _HANDS_FULL):
        return "hands full"
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


def free_a_hand(s):
    """STOW what the hands hold, left first — never a drop. True when a
    hand was emptied (the parser's hand state lags, so the answer is
    the judge: anything but "What were you referring to?" counts)."""
    for side in ("left_hand", "right_hand"):
        held = getattr(s.state, side, None)
        noun = held.get("noun") if isinstance(held, dict) else None
        if noun:
            answer = probe.ask(s, f"stow my {noun}", COLLECT_SECONDS, TAIL_SECONDS)
            s.echo(f"forage: both hands full — stowed the {noun}")
            return "what were you" not in answer.lower()
    return False


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
    collected = successes = empties = freed = 0
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
        if outcome == "hands full":
            freed += 1
            if freed > 2 or not free_a_hand(s):
                return f"no hand free: {first_line(answer)}", collected
            continue
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


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def pieces_of(s, noun):
    """COUNT MY <noun>: its pieces, 0 when the answer gives none."""
    match = _PIECES.search(ask(s, f"count my {noun}").lower())
    return int(match.group(1)) if match else 0


def gather_herb(s, options, bag):
    """FORAGE the herb until the pieces are in: each find counted and
    put in `bag`. (why it ended, pieces, the find's noun)."""
    item, target = options["item"], options["pieces"]
    pieces, misses, noun = 0, 0, ""
    precise = True  # Remedial Herb Gathering's PRECISE; plain FORAGE without it
    for _ in range(MAX_COLLECTS):
        if reason := danger(s):
            return reason, pieces, noun
        if wants_stop(s):
            return "returning on request", pieces, noun
        if pieces >= target:
            return f"{pieces} piece(s) of {item} found", pieces, noun
        answer = ask(s, f"forage {item} precise" if precise else f"forage {item}")
        s.waitrt()  # the forage's roundtime before COUNT and PUT
        found = _HERB_FOUND.search(answer)
        if found:
            misses = 0
            noun = found.group("what").split()[-1].lower()
            pieces += pieces_of(s, noun)
            ask(s, f"put my {noun} in my {bag}")
            continue
        outcome = classify(answer)
        if precise and outcome is None:
            # Not a find, not a known miss: taken for a character without
            # the technique (its refusal is uncaptured) — plain from here.
            precise = False
            s.echo(
                f"forage: FORAGE PRECISE answered {first_line(answer)!r} — "
                "plain FORAGE from here"
            )
            continue
        if outcome == "hands full":
            if not free_a_hand(s):
                return f"no hand free: {first_line(answer)}", pieces, noun
            continue
        if outcome == "refused":
            return f"refused: {first_line(answer)}", pieces, noun
        misses += 1
        if misses >= HERB_MISSES:
            return f"no {item} found in {misses} tries", pieces, noun
    return "forage fuse spent", pieces, noun


def press_herb(s, noun, bag):
    """At the dry press: each raw find out of `bag` pressed and combined
    with the dried stack before it, the stack stowed. The dried stack's
    pieces, or None when nothing came out of the bag."""
    home = ""  # where STOW puts the dried stack, read off its answer
    stacks = 0
    for _ in range(MAX_COLLECTS):
        if s.dead or danger(s):
            break
        got = ask(s, f"get {noun} from my {bag}").lower()
        if not any(word in got for word in _GOT):
            break  # the bag holds no more
        pressed = ask(s, f"put my {noun} in press").lower()
        if not any(word in pressed for word in _PRESSED + _PREPARED):
            s.echo(f"forage: the press answered {first_line(pressed)!r} — stopping")
            ask(s, f"put my {noun} in my {bag}")
            break
        stacks += 1
        if home:
            again = ask(s, f"get dried {noun} from my {home}").lower()
            if any(word in again for word in _GOT):
                joined = ask(s, f"combine {noun} with {noun}").lower()
                if not any(word in joined for word in _COMBINED):
                    s.echo(f"forage: the {noun} would not combine — two stacks kept")
                    ask(s, "stow left")
        stored = _STOWED_IN.search(ask(s, f"stow my {noun}"))
        if stored:
            home = stored.group("container").strip()
        if any(word in pressed for word in _PREPARED) and home == bag:
            break  # the bag holds only the dried stack now: all pressed
    if not stacks:
        return None
    if home:
        ask(s, f"get dried {noun} from my {home}")
        total = pieces_of(s, noun)
        ask(s, f"stow my {noun}")
        return total
    return 0


def run_herb(s, options, db=None, avoid=(), bag="sack"):
    """The herb mode: gather, then press and combine. Why it ended."""
    item = options["item"]
    if not item:
        return "which herb? — ;forage herb red flower"
    if db is not None and not options["here"] and not find_item(s, db, item, avoid):
        return "no room to forage in"
    reason, pieces, noun = gather_herb(s, options, bag)
    if not pieces:
        return reason
    s.echo(f"forage: {reason} — to the dry press")
    if db is not None and not walk(s, db, set(PRESS_ROOMS), describe="the dry press"):
        return f"{reason}; could not reach the dry press — the {noun} wait in the {bag}"
    total = press_herb(s, noun, bag)
    if total is None:
        return f"{reason}; nothing to press"
    return f"{reason}; pressed and combined — {total} dried piece(s) stowed"


def main(s):
    options = parse_args(s.args or [])
    db = None if options["here"] else MapDB.load()
    avoid = avoided_rooms(db, load_settings().get("avoid_rooms")) if db else ()
    if options.get("herb"):
        from client.game.profile import load_profile

        profile = load_profile(getattr(s.state, "name", None) or "")
        bag = profile.get("loot_container") or "backpack"
        reason = run_herb(s, options, db=db, avoid=avoid, bag=bag)
        s.echo(f"forage: {reason}")
    else:
        reason, collected = run(s, options, db=db, avoid=avoid)
        s.echo(f"forage: {reason} — {collected} collect(s) of {options['item']}")
    if "hostiles" in reason:
        flight.react(s, "forage")
