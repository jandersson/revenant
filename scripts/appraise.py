"""Train Appraisal by appraising your own things:  ;appraise

    ;appraise                      APPRAISE each item on you in turn, quick, until Appraisal mind-locks
    ;appraise items=pouch,shield   items of your own instead of the profile's `appraisal_items` or the inventory
    ;appraise careful              full appraisals instead of QUICK (a longer roundtime, the same learning)
    ;appraise until=30             stop at that mindstate instead of 34
    ;appraise once                 exit at mind-lock instead of holding for the drain
    ;appraise return               (typed while it runs) finish the appraisal in hand and end

What it does
  - The rotation: the profile's `appraisal_items`, else everything worn or held as the last
    INV LIST saw it, plus each gem pouch or bundle inside a worn container — GOT into a hand
    by its id, appraised, put back (the game will not appraise one where it lies).
  - Pouches and bundles first; each item APPRAISEd QUICK, the roundtime waited out.
  - An item teaches once, then not for a while: each waits ten minutes before its next
    appraisal, and with none due the script waits instead of repeating one.
  - Drops an item the game cannot find, will not appraise, or finds closed or empty.

When it stops
  - Appraisal at the mindstate with `once`; else it holds until below 28 and goes on
  - death or hostiles in the room; ;appraise return; nothing left to appraise

;train runs it as an Appraisal task. Model: client/game/appraisal.py; docs/training.md.
"""

import time

from client.game import probe
from client.game import flight
from client.game.appraisal import (
    CLOSED,
    EMPTY,
    IN_CONTAINER,
    ITEM_WAIT,
    NOT_FOUND,
    PUT_BACK,
    REFUSED,
    TAKEN,
    appraise_command,
    parse_args,
    targets,
)
from client.game.loop import danger, ensure_mindstate, mindstate, pause, wants_stop

# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Every APPRAISE of an item on you teaches Appraisal, at any rank; a
valuable or many-part item — a gem pouch, a bundle, a weapon, armor —
teaches most, else the whole inventory does (Elanthipedia: Appraisal
skill, Appraise command; after dr-scripts' appraisal.lic, which cycles
the same way). The INV LIST is the autostarted ;sheet's at login
(;sheet inv refreshes it); an item it listed with a game id is
appraised by it (#<exist>), so twins are two items. The mindstate is
the exp window's (EXP APPRAISAL when it does not list the skill).
Creatures are never appraised (they teach nothing below 76 ranks) and
other players never (uncouth).
#382 (2026-09-28, Crannach at 1205): one gem pouch taught 0 -> 2/34 and
eighteen repeats after it nothing, while the rest of the pouches were
refused in the pack ("You can't appraise the fuzzy gem pouch in
there."); taken into a hand, nine tied pouches (51 stones, a million
Kronars and more each) took it 2 -> 14, and the first pouch taught
again twelve minutes on. So a pouch or bundle inside a worn container
is GOT by its id, appraised and put back (PUT refused: STOWed, never
dropped; a ;stop between: put back on the way out), each item waits
ITEM_WAIT between appraisals, and a closed or empty pouch leaves the
rotation. The first answer of a run is echoed as "appraise: <item>
answered ..." so new wordings become fixtures.
"""

SKILL = "Appraisal"
MIND_LOCK = 34
RESUME_BELOW = 28  # resume once enough has drained to be worth a lap
LOCK_POLL = 30
COLLECT_SECONDS = 2
TAIL_SECONDS = 0.5
MAX_LAPS = 400  # the fuse under the loop
clock = time.monotonic  # tests replace it
# Why an item leaves the rotation, as said (#382).
DROPPED = {
    "not found": "the game finds no {label}",
    "refused": "the game will not appraise the {label}",
    "in container": "the {label} is inside a container — the game appraises it only in hand",
    "closed": "the {label} is closed — nothing to appraise in it",
    "empty": "the {label} is empty",
}


def ask(s, command):
    """The game's answer to one command, lower-cased."""
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS).lower()


def profile_items(s):
    """The profile's `appraisal_items`, or []."""
    name = getattr(s.state, "name", None)
    if not name:
        return []
    from client.game.profile import load_profile

    return list(load_profile(name).get("appraisal_items") or [])


def hold_at_lock(s, until):
    """Wait at mind-lock until the mindstate drains below RESUME_BELOW
    (or the target, when lower); False when the wait is interrupted."""
    s.echo(f"appraise: {SKILL} mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        value = mindstate(s, SKILL)
        if value is not None and value <= floor:
            s.echo(f"appraise: drained to {value}/34 — appraising again")
            return True


def hands_full(s):
    state = s.state
    return bool(
        getattr(state, "left_hand", None) and getattr(state, "right_hand", None)
    )


def classify(answer):
    """An APPRAISE answer: "ok", or why the item leaves the rotation."""
    for outcome, words in (
        ("not found", NOT_FOUND),
        ("in container", IN_CONTAINER),
        ("refused", REFUSED),
        ("closed", CLOSED),
        ("empty", EMPTY),
    ):
        if any(word in answer for word in words):
            return outcome
    return "ok"


def appraise(s, target, careful, held):
    """One APPRAISE, the roundtime waited out: (outcome, answer), the
    outcome "ok", "no hand" (both hands full for an item to fetch) or
    why the item leaves the rotation. An item inside a container is
    GOT into a hand first and put back after (#382); `held` keeps its
    PUT until it is back, for the way out on a ;stop."""
    if target["fetch"]:
        if hands_full(s):
            return "no hand", ""
        got = ask(s, target["fetch"])
        if not any(word in got for word in TAKEN):
            return "not found", got
        held["back"] = target["back"]
        s.waitrt()
    answer = ask(s, appraise_command(target["ref"], careful))
    s.waitrt()
    if target["back"]:
        back = ask(s, target["back"])
        if not any(word in back for word in PUT_BACK):
            # Never a DROP: a PUT refused (a full pack) stows it instead.
            first = (back.strip().splitlines() or ["(silence)"])[0]
            s.echo(
                f"appraise: the {target['label']} did not go back ({first!r}) — stowed"
            )
            ask(s, f"stow {target['ref']}")
        held["back"] = None
    return classify(answer), answer


def wait_for_due(s, items, last):
    """No item due: wait until the first one is, said once; False when
    a typed return or danger ended the wait."""
    now = clock()
    left = min(ITEM_WAIT - (now - last[target["key"]]) for target in items)
    s.echo(
        f"appraise: every item appraised in the last {ITEM_WAIT // 60} min "
        f"— an item teaches once, then not for a while; next in {int(left) + 1} s"
    )
    return pause(s, max(1, int(left) + 1))


def run(s, options):
    value = ensure_mindstate(s, SKILL, ask)
    if value is None:
        s.echo(f"appraise: EXP shows no {SKILL} — nothing to train")
        return
    items = targets(
        getattr(s.state, "possessions", None),
        options["items"] or profile_items(s),
    )
    if not items:
        s.echo(
            "appraise: nothing to appraise — items=<noun,noun>, the profile's "
            "appraisal_items, or ;sheet inv first so the inventory is known"
        )
        return
    counts = {}
    for target in items:
        counts[target["label"]] = counts.get(target["label"], 0) + 1
    listed = ", ".join(
        label if n == 1 else f"{label} x{n}" for label, n in counts.items()
    )
    s.echo(
        f"appraise: {len(items)} item(s) in rotation ({listed}) — {SKILL} {value}/34"
    )
    held = {"back": None}  # a fetched item's PUT, until it is back
    try:
        lap(s, options, items, held)
    finally:
        if held["back"] and not getattr(s, "dead", False):
            # A ;stop between the GET and the PUT: back it goes all the same.
            s.put(held["back"], cleanup=True)
            s.echo("appraise: the item in hand went back where it came from")


def lap(s, options, items, held):
    last = {}  # target key -> clock() of its last appraisal
    reported = False
    for _ in range(MAX_LAPS):
        due = [
            t
            for t in items
            if t["key"] not in last or clock() - last[t["key"]] >= ITEM_WAIT
        ]
        if not due:
            if not wait_for_due(s, items, last):
                reason = danger(s)
                s.echo(
                    f"appraise: {reason} — stopping"
                    if reason
                    else "appraise: stopping as asked"
                )
                if reason and "hostiles" in reason:
                    flight.react(s, "appraise")
                return
            continue
        for target in due:
            reason = danger(s)
            if reason:
                s.echo(f"appraise: {reason} — stopping")
                if "hostiles" in reason:
                    flight.react(s, "appraise")
                return
            if wants_stop(s):
                s.echo("appraise: stopping as asked")
                return
            value = mindstate(s, SKILL)
            if value is not None and value >= options["until"]:
                if options["once"]:
                    s.echo(f"appraise: {SKILL} at {value}/34 — done")
                    return
                if not hold_at_lock(s, options["until"]):
                    s.echo("appraise: stopping")
                    return
            outcome, answer = appraise(s, target, options["careful"], held)
            if outcome == "no hand":
                continue  # both hands full: the next lap
            last[target["key"]] = clock()
            if outcome != "ok":
                items.remove(target)
                reason = DROPPED[outcome].format(label=target["label"])
                s.echo(f"appraise: {reason} — out of the rotation ({len(items)} left)")
                if not items:
                    s.echo("appraise: nothing left to appraise — stopping")
                    return
                continue
            if not reported:
                reported = True
                first = (answer.strip().splitlines() or ["(silence)"])[0]
                s.echo(f"appraise: {target['label']} answered {first!r}")
    s.echo(f"appraise: {MAX_LAPS} laps — stopping")


def main(s):
    run(s, parse_args(s.args or []))
