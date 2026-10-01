"""Train Appraisal by appraising your own things:  ;appraise

    ;appraise                      APPRAISE each item on you in turn, quick, until Appraisal mind-locks
    ;appraise items=pouch,shield   items of your own instead of the profile's `appraisal_items` or the inventory
    ;appraise careful              full appraisals instead of QUICK (a longer roundtime, the same learning)
    ;appraise until=30             stop at that mindstate instead of 34
    ;appraise once                 exit at mind-lock instead of holding for the drain
    ;appraise focus=box            APPRAISE FOCUS on that item beside the rotation (200 ranks;
                                   focus=offense for a concept, focus=inner_fire for two words)
    ;appraise return               (typed while it runs) finish the appraisal in hand and end

What it does
  - The rotation: the profile's `appraisal_items`, else everything worn or held as the last
    INV LIST saw it, plus each gem pouch or bundle inside a worn container — GOT into a hand
    by its id, appraised, put back (the game will not appraise one where it lies).
  - Pouches and bundles first; each item APPRAISEd QUICK, the roundtime waited out.
  - An item teaches once, then not for a while: each waits ten minutes before its next
    appraisal, and with none due the script waits instead of repeating one.
  - Drops an item the game cannot find, will not appraise, or finds closed or empty.
  - focus=: APPRAISE FOCUS CHECK every few minutes; with no project and no boost running,
    GET the item, APPRAISE FOCUS it, STOW it. The breakthrough pays Appraisal and speeds
    the drain of the item's skill (a box: Locksmithing) for up to an hour. Never beside a
    magical research project: that answer turns the focus off for the run.

When it stops
  - Appraisal at the mindstate with `once`; else it holds until below 28 and goes on
  - death or hostiles in the room (the shared escape); ;appraise return; nothing left
    to appraise

;train runs it as an Appraisal task. The loop is every trainer's
(client/game/trainer.py). Model: client/game/appraisal.py; docs/training.md.
"""

import time

from client.game import hands, trainer
from client.game.act import ask
from client.game.appraisal import (
    CLOSED,
    EMPTY,
    FOCUS_CONCEPTS,
    FOCUS_RANKS,
    IN_CONTAINER,
    ITEM_WAIT,
    NOT_FOUND,
    PUT_BACK,
    REFUSED,
    TAKEN,
    appraise_command,
    focus_check,
    focus_command,
    focus_events,
    focus_outcome,
    parse_args,
    targets,
)
from client.game.loop import ensure_mindstate, exp_entry, pause

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
#383: APPRAISE FOCUS rides beside the rotation, since appraising
items does not interrupt the project (Elanthipedia: Appraisal skill,
Magical research). APPRAISE FOCUS CHECK decides when a new project is
due, so a breakthrough or "fully explored" line another read swallowed
costs a poll, not the focus; every answer is scanned for both lines
too. The item is GOT and STOWed around the focus as dr-scripts'
appraisal.lic does. An almanac interlude's STUDY may interrupt a
project (it does a research portion); the next check starts another.
The CHECK's idle answer and the start's are echoed once for fixtures.
"""

SKILL = "Appraisal"
MIND_LOCK = 34
MAX_LAPS = 400  # the fuse under the loop
FOCUS_POLL = 120  # seconds between APPRAISE FOCUS CHECKs while a project runs
BOOST_POLL = 300  # ... while its boost runs (20 to 60 minutes)
clock = time.monotonic  # tests replace it
# Why an item leaves the rotation, as said (#382).
DROPPED = {
    "not found": "the game finds no {label}",
    "refused": "the game will not appraise the {label}",
    "in container": "the {label} is inside a container — the game appraises it only in hand",
    "closed": "the {label} is closed — nothing to appraise in it",
    "empty": "the {label} is empty",
}


def profile_items(s):
    """The profile's `appraisal_items`, or []."""
    name = getattr(s.state, "name", None)
    if not name:
        return []
    from client.game.profile import load_profile

    return list(load_profile(name).get("appraisal_items") or [])


def first_line(answer):
    return ((answer or "").strip().splitlines() or ["(silence)"])[0]


def focus_setup(s, item):
    """The focus for the run — {"item", "next", "said"} — or None: no
    item named, or fewer than FOCUS_RANKS Appraisal ranks (said)."""
    if not item:
        return None
    rank = (exp_entry(s, SKILL) or {}).get("rank")
    if rank is not None and rank < FOCUS_RANKS:
        s.echo(
            f"appraise: APPRAISE FOCUS needs {FOCUS_RANKS} {SKILL} ranks, "
            f"{rank} here — the rotation only"
        )
        return None
    s.echo(f"appraise: APPRAISE FOCUS on {item} beside the rotation")
    return {"item": item, "next": 0.0, "said": set()}


def focus_note(s, focus, text):
    """The focus lines in an answer: a breakthrough said, and a boost
    that has run out makes the next check due at once."""
    if not focus:
        return
    for event in focus_events(text):
        if event == "breakthrough":
            s.echo(
                "appraise: focus breakthrough — Appraisal paid, the drain boost runs"
            )
            focus["next"] = clock() + BOOST_POLL
        elif event == "explored":
            s.echo("appraise: the focus boost has run out — a new focus next")
            focus["next"] = 0.0


def focus_off(s, focus, why):
    s.echo(f"appraise: {why} — focus off for the run")
    focus["next"] = float("inf")


def focus_tick(s, focus, held):
    """APPRAISE FOCUS CHECK when due; with no project and no boost
    running, start a new focus."""
    if not focus or clock() < focus["next"]:
        return
    answer = ask(s, "appraise focus check")
    s.waitrt()
    focus_note(s, focus, answer)
    status = focus_check(answer)
    if status == "running":
        focus["next"] = clock() + FOCUS_POLL
        return
    if status == "boost":
        focus["next"] = clock() + BOOST_POLL
        return
    if "check" not in focus["said"]:
        focus["said"].add("check")
        s.echo(f"appraise: APPRAISE FOCUS CHECK answered {first_line(answer)!r}")
    start_focus(s, focus, held)


def start_focus(s, focus, held):
    """GET the item (a concept needs none), APPRAISE FOCUS it, STOW it."""
    item = focus["item"]
    fetched = False
    if item not in FOCUS_CONCEPTS and not hands.holding(s, item):
        if hands.full(s):
            focus["next"] = clock() + FOCUS_POLL
            return
        got = ask(s, f"get my {item}")
        s.waitrt()
        lowered = got.lower()
        if any(word in lowered for word in NOT_FOUND):
            focus_off(s, focus, f"no {item} to focus on ({first_line(got)!r})")
            return
        fetched = any(word in lowered for word in TAKEN) and "already" not in lowered
        if fetched:
            held["back"] = f"stow my {item}"
    answer = ask(s, focus_command(item))
    s.waitrt()
    if fetched:
        ask(s, f"stow my {item}")
        held["back"] = None
    focus_note(s, focus, answer)
    outcome = focus_outcome(answer)
    if outcome == "started":
        s.echo(f"appraise: APPRAISE FOCUS on the {item} begun ({first_line(answer)!r})")
        focus["next"] = clock() + FOCUS_POLL
    elif outcome == "running":
        focus["next"] = clock() + FOCUS_POLL
    elif outcome == "boost":
        focus["next"] = clock() + BOOST_POLL
    elif outcome == "research":
        focus_off(
            s,
            focus,
            f"APPRAISE FOCUS answered {first_line(answer)!r}: a magical research "
            "project is in progress, and the two never run together",
        )
    else:
        focus_off(s, focus, f"APPRAISE FOCUS {item} answered {first_line(answer)!r}")


def classify(answer):
    """An APPRAISE answer: "ok", or why the item leaves the rotation."""
    lowered = answer.lower()
    for outcome, words in (
        ("not found", NOT_FOUND),
        ("in container", IN_CONTAINER),
        ("refused", REFUSED),
        ("closed", CLOSED),
        ("empty", EMPTY),
    ):
        if any(word in lowered for word in words):
            return outcome
    return "ok"


def appraise(s, target, careful, held):
    """One APPRAISE, the roundtime waited out: (outcome, answer), the
    outcome "ok", "no hand" (both hands full for an item to fetch) or
    why the item leaves the rotation. An item inside a container is
    GOT into a hand first and put back after (#382); `held` keeps its
    PUT until it is back, for the way out on a ;stop."""
    if target["fetch"]:
        if hands.full(s):
            return "no hand", ""
        got = ask(s, target["fetch"])
        if not any(word in got.lower() for word in TAKEN):
            return "not found", got
        held["back"] = target["back"]
        s.waitrt()
    answer = ask(s, appraise_command(target["ref"], careful))
    s.waitrt()
    if target["back"]:
        back = ask(s, target["back"])
        if not any(word in back.lower() for word in PUT_BACK):
            # Never a DROP: a PUT refused (a full pack) stows it instead.
            first = (back.strip().splitlines() or ["(silence)"])[0]
            s.echo(
                f"appraise: the {target['label']} did not go back ({first!r}) — stowed"
            )
            ask(s, f"stow {target['ref']}")
        held["back"] = None
    return classify(answer), answer


def wait_for_due(s, items, last, tick=None):
    """No item due: wait until the first one is, said once, running
    `tick` (the focus) every FOCUS_POLL; False when a typed return or
    danger ended the wait."""
    now = clock()
    left = min(ITEM_WAIT - (now - last[target["key"]]) for target in items)
    s.echo(
        f"appraise: every item appraised in the last {ITEM_WAIT // 60} min "
        f"— an item teaches once, then not for a while; next in {int(left) + 1} s"
    )
    left = max(1, int(left) + 1)
    while left > 0:
        chunk = min(left, FOCUS_POLL) if tick else left
        if not pause(s, chunk):
            return False
        left -= chunk
        if tick and left > 0:
            tick()
    return True


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
    focus = focus_setup(s, options.get("focus"))
    return lap(s, options, items, held, focus)


def lap(s, options, items, held, focus=None):
    """The trainer loop (client/game/trainer.py) with one step: the next
    item due of the lap appraised — a lap with none due waited out,
    the focus ticked between items and through the hold — and the
    item in hand put back at every end, a ;stop included."""
    last = {}  # target key -> clock() of its last appraisal
    due = []  # the items of this lap still to appraise
    counts = {"laps": 0, "reported": False}

    def focus_step():
        focus_tick(s, focus, held)

    tick = focus_step if focus else None

    def step(s):
        if not due:
            if counts["laps"] >= MAX_LAPS:
                return f"{MAX_LAPS} laps"
            counts["laps"] += 1
            due.extend(
                t
                for t in items
                if t["key"] not in last or clock() - last[t["key"]] >= ITEM_WAIT
            )
            if not due:
                wait_for_due(s, items, last, tick)  # False: the loop says why
                return None
        target = due.pop(0)
        if tick:
            tick()
        outcome, answer = appraise(s, target, options["careful"], held)
        focus_note(s, focus, answer)
        if outcome == "no hand":
            return None  # both hands full: the next lap
        last[target["key"]] = clock()
        if outcome != "ok":
            items.remove(target)
            reason = DROPPED[outcome].format(label=target["label"])
            s.echo(f"appraise: {reason} — out of the rotation ({len(items)} left)")
            if not items:
                return "nothing left to appraise"
            return None
        if not counts["reported"]:
            counts["reported"] = True
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"appraise: {target['label']} answered {first!r}")
        return None

    def finish(s, why):
        if held["back"] and not getattr(s, "dead", False):
            # A ;stop between the GET and the PUT: back it goes all the same.
            hands.cleanup(s, held["back"])
            s.echo("appraise: the item in hand went back where it came from")

    return trainer.train(
        s,
        "appraise",
        SKILL,
        step,
        until=options["until"],
        once=options["once"],
        again="appraising again",
        finish=finish,
        tick=tick,
        ask=ask,
    )


def main(s):
    run(s, parse_args(s.args or []))
