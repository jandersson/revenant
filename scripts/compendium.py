"""Train First Aid from a compendium of anatomy charts:  ;compendium

    ;compendium              study its charts, hardest first, until First Aid mind-locks, then hold
    ;compendium until=30     stop at that mindstate instead of 34
    ;compendium once         end at mind-lock, or when every chart is resting
    ;compendium return       (typed while it runs) finish the chart in hand and end
    ;stop compendium         quit at once; the compendium is stowed

What it does
  - Gets the compendium (the profile's `compendium`) into a hand and LOOKs at it for its charts.
  - The hardest chart Scholarship reads goes first: TURN to its page, STUDY until clarity, then the next.
  - A chart at clarity rests twenty minutes; with every chart resting it waits for the first to open.
  - Scholarship learns on every study, First Aid on the first and at clarity.
  - Stows the compendium at every end.

When it stops
  - First Aid at the mindstate (with `once`), or ;compendium return
  - death or hostiles (the shared escape)
  - no compendium on you or a hand to hold it, no chart in it, none Scholarship reads

;train runs it as a First Aid task. The model and the game's wordings are
client/game/compendium.py's; docs/firstaid.md.
"""

import time

from client.game import compendium, hands, trainer
from client.game.act import ask, missing, unknown
from client.game.loop import danger, pause
from client.game.probe import classify
from client.game.profile import load_profile

_NOTES = """
dr-scripts' first-aid.lic is the method: LOOK the compendium for its
charts, sort them by the Scholarship each asks (data/base-anatomy-
charts.yaml, generated here as client/game/anatomy_data.py), TURN to
each and STUDY it until it makes sense. Cecil's trials on 2026-10-04
pinned the wordings and the pace: a chart well inside the reach (a
Silver Leucro at Scholarship 77) reached clarity at the first study and
taught next to nothing; one nearer the reach (Blood Nyad, Glutinous
Lipopod) took seven to nine studies of 14 s and moved First Aid about
one mindstate, Scholarship alongside. So the hardest goes first.
"""

SKILL = "First Aid"
SCHOLARSHIP = "Scholarship"
STUDY_FUSE = 60  # studies of one chart before giving it up: the Boggle took 39
clock = time.monotonic  # tests replace it


def parse_args(args):
    options = {"until": trainer.MIND_LOCK, "once": False}
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "until" and value.isdigit():
            options["until"] = min(int(value), trainer.MIND_LOCK)
        elif key == "once":
            options["once"] = True
    return options


def rank_of(s, skill):
    """The skill's rank in the exp window, or None before it shows."""
    experience = getattr(s.state, "experience", None) or {}
    return (experience.get(skill) or {}).get("rank")


def hold(s, noun):
    """The compendium in a hand: True when held or got; False said."""
    if hands.holding(s, noun):
        return True
    if hands.full(s):
        s.echo(f"compendium: both hands are full — the {noun} needs one")
        return False
    answer = ask(s, f"get my {noun}")
    if missing(answer) or not any(
        word in str(answer or "").lower() for word in compendium.GOT
    ):
        s.echo(f"compendium: no {noun} on you — the profile's `compendium` names it")
        return False
    return True


def study(s, noun, name, tally):
    """TURN to the chart and STUDY it until clarity; what came of it:
    "clarity", "locked", "too hard", "missing", "unheld", "danger", or
    "unknown" (said)."""
    for attempt in range(2):
        answer = ask(s, f"turn my {noun} to {compendium.index(name)}")
        outcome = classify(answer, compendium.TURN_OUTCOMES)
        if outcome == "unheld" and attempt == 0 and hold(s, noun):
            continue
        break
    if outcome != "turned":
        if outcome is None:
            unknown(s, "compendium", "turn", answer)
            return "unknown"
        return outcome
    for _ in range(STUDY_FUSE):
        if danger(s):
            return "danger"
        answer = ask(s, f"study my {noun}")
        outcome = classify(answer, compendium.STUDY_OUTCOMES)
        if outcome == "studying":
            tally["studies"] += 1
            continue
        if outcome in ("clarity", "done"):
            tally["studies"] += 1
            return "clarity"
        if outcome == "unheld":
            if not hold(s, noun):
                return "unheld"
            continue
        if outcome is None:
            unknown(s, "compendium", "study", answer)
            return "unknown"
        return outcome  # locked, too hard
    return "fuse"


def run(s, options, profile):
    noun = str(profile.get("compendium") or "compendium").strip().lower()
    tally = {"studies": 0, "charts": 0}
    order = []
    shut = set()  # charts this run cannot study: missing, too hard, failing

    def finish(s, why):
        if hands.holding(s, noun):
            hands.stow(s, noun, ask)

    def step(s):
        if not hold(s, noun):
            return "no compendium in hand"
        if not order:
            listed = compendium.charts(ask(s, f"look my {noun}"))
            if not listed:
                return f"no chart in the {noun}"
            scholarship = rank_of(s, SCHOLARSHIP)
            order.extend(compendium.plan(listed, scholarship))
            if not order:
                return f"no chart in the {noun} that Scholarship {scholarship} reads"
            s.echo(
                f"compendium: {len(order)} chart(s), hardest first — "
                + ", ".join(order)
            )
        now = clock()
        open_ = [
            name
            for name in order
            if name not in shut and not compendium.locked(name, now)
        ]
        if not open_:
            usable = [name for name in order if name not in shut]
            if not usable:
                return f"no chart in the {noun} that can be studied"
            wait = compendium.next_unlock(usable, now)
            seconds, first = wait if wait else (0, usable[0])
            minutes = max(1, round(seconds / 60))
            if options["once"]:
                return f"every chart is resting — the {first} opens in {minutes} min"
            s.echo(
                f"compendium: every chart is resting — waiting {minutes} min "
                f"for the {first}"
            )
            pause(s, seconds)
            return None
        name = open_[0]
        outcome = study(s, noun, name, tally)
        if outcome in ("clarity", "locked"):
            compendium.lock(name, clock())
            if outcome == "clarity":
                tally["charts"] += 1
                shown = trainer.mindstates(s, SKILL).get(SKILL)
                s.echo(
                    f"compendium: {name} at clarity — {SKILL} "
                    f"{shown if shown is not None else '?'}/34"
                )
        elif outcome == "too hard":
            shut.add(name)
            s.echo(f"compendium: the {name} is past your Scholarship — skipped")
        elif outcome in ("missing", "unknown", "fuse"):
            shut.add(name)
        elif outcome == "unheld":
            return f"the {noun} would not stay in hand"
        return None

    why = trainer.train(
        s,
        "compendium",
        SKILL,
        step,
        until=options["until"],
        once=options["once"],
        again="studying again",
        finish=finish,
    )
    s.echo(
        f"compendium: {tally['charts']} chart(s) to clarity in "
        f"{tally['studies']} studies"
    )
    return why


def main(s):
    options = parse_args(s.args or [])
    profile = load_profile(getattr(s.state, "name", None) or "")
    run(s, options, profile)
