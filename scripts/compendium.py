"""Train First Aid and Scholarship from a compendium of anatomy charts:  ;compendium

    ;compendium              study its charts until First Aid and Scholarship mind-lock, then hold
    ;compendium until=30     stop at that mindstate instead of 34
    ;compendium once         end at the lock, or when every chart is resting
    ;compendium minutes=20   end after that long
    ;compendium return       (typed while it runs) finish the chart in hand and end
    ;stop compendium         quit at once; the compendium is stowed

What it does
  - Gets the compendium (the profile's `compendium`) into a hand and LOOKs at it for its charts.
  - First Aid is paid per chart at clarity, Scholarship per study. So while First Aid
    has room, the charts at your level go first, hardest first: a few studies each.
  - A slow chart (past your level: "having a difficult time comprehending") fills the
    time while Scholarship has room, five minutes a turn; it keeps its progress.
  - A chart at clarity rests twenty minutes; with every chart resting it waits for the first.
  - Stows the compendium at every end.

When it stops
  - both skills at the mindstate (with `once`), or ;compendium return
  - death or hostiles (the shared escape)
  - no compendium on you or a hand to hold it, no chart in it, none Scholarship reads

;train runs it as a First Aid and Scholarship task. The model and the game's
wordings are client/game/compendium.py's; docs/firstaid.md.
"""

import time

from client.game import compendium, hands, trainer
from client.game.act import ask, missing, unknown
from client.game.loop import danger, pause, wants_stop
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
one mindstate, Scholarship alongside. A chart past the level (the
Boggle, the wiki's 90) took 39 studies of 18 s to clarity: one First
Aid award in 14 minutes against an at-level chart's in under one, but
Scholarship 15/34 -> 25/34 on the way (the operator: lock both from
the compendium). Hence at-level charts while First Aid has room, the
slow ones for Scholarship and the time between.
"""

SKILL = "First Aid"
SCHOLARSHIP = "Scholarship"
SKILLS = [SKILL, SCHOLARSHIP]  # the run holds or ends when both lock
STUDY_FUSE = 60  # studies of one chart before giving it up: the Boggle took 39
# A slow chart's turn: then the next choice. A chart keeps its progress
# across pages ("You continue to study the Cougar chart" after a Boggle
# study, 2026-10-04), so a slice loses nothing, and a typed return or
# ;train's budget never waits out a 14-minute chart.
SLOW_SLICE = 300
clock = time.monotonic  # tests replace it


def parse_args(args):
    options = {"until": trainer.MIND_LOCK, "once": False, "minutes": 0}
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "until" and value.isdigit():
            options["until"] = min(int(value), trainer.MIND_LOCK)
        elif sep and key == "minutes" and value.isdigit():
            options["minutes"] = int(value)
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


def study(s, noun, name, tally, give_way=lambda: False, slow=False, until=None):
    """TURN to the chart and STUDY it until clarity; what came of it:
    "clarity", "locked", "too hard", "missing", "unheld", "danger",
    "slow" (it answered "difficult time" and `give_way()` says an
    at-level chart is waiting), "slice" (a slow chart's SLOW_SLICE is
    up), "stop" (a slow chart, and a typed return or the run's `until`
    deadline came), or "unknown" (said). A chart that answered
    "difficult time" is marked slow, one that went to clarity without
    it at level."""
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
    struggled = False
    started = clock()
    for _ in range(STUDY_FUSE):
        if danger(s):
            return "danger"
        if slow or struggled:
            if wants_stop(s) or (until is not None and clock() >= until):
                return "stop"
            if clock() - started >= SLOW_SLICE:
                return "slice"
        answer = ask(s, f"study my {noun}")
        outcome = classify(answer, compendium.STUDY_OUTCOMES)
        if outcome == "studying":
            tally["studies"] += 1
            if any(word in answer.lower() for word in compendium.DIFFICULT):
                if not struggled:
                    struggled = True
                    compendium.mark(name, slow=True)
                if give_way():
                    return "slow"
            continue
        if outcome in ("clarity", "done"):
            tally["studies"] += 1
            if not struggled:
                compendium.mark(name, slow=False)
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

    budget = options.get("minutes") or 0
    deadline = clock() + budget * 60 if budget else None

    def finish(s, why):
        # A cleanup put: it goes out after a ;stop too, which an ask
        # does not (the book stayed in hand, 2026-10-04).
        if hands.holding(s, noun):
            hands.cleanup(s, f"stow my {noun}")

    def step(s):
        if deadline is not None and clock() >= deadline:
            return f"{budget} minutes up"
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
            easy = [name for name in order if not compendium.slow(name, scholarship)]
            hard = [name for name in order if compendium.slow(name, scholarship)]
            s.echo(
                f"compendium: {len(order)} chart(s) — at your level, hardest "
                f"first: {', '.join(easy) or 'none'}"
                + (f"; slow, for the time between: {', '.join(hard)}" if hard else "")
            )
        now = clock()
        usable = [name for name in order if name not in shut]
        if not usable:
            return f"no chart in the {noun} that can be studied"
        scholarship = rank_of(s, SCHOLARSHIP)
        until = options["until"]
        values = trainer.mindstates(s, SKILLS)

        def room(skill):
            value = values.get(skill)
            return value is None or value < until

        name = compendium.choose(
            usable, now, scholarship, room(SKILL), room(SCHOLARSHIP)
        )
        if name is None:
            # What could be chosen once it opens: the at-level charts for
            # First Aid, every chart while Scholarship has room.
            resting = [
                other
                for other in usable
                if compendium.locked(other, now)
                and (room(SCHOLARSHIP) or not compendium.slow(other, scholarship))
            ]
            if not resting:
                return "no chart left that teaches a skill with room"
            seconds, first = compendium.next_unlock(resting, now)
            minutes = max(1, round(seconds / 60))
            if options["once"]:
                return f"every chart is resting — the {first} opens in {minutes} min"
            s.echo(
                f"compendium: every chart is resting — waiting {minutes} min "
                f"for the {first}"
            )
            pause(s, seconds)
            return None

        def give_way():
            """An at-level chart opened while First Aid has room: a slow
            chart is set aside for it."""
            if not room(SKILL):
                return False
            current = trainer.mindstates(s, [SKILL]).get(SKILL)
            if current is not None and current >= until:
                return False
            return any(
                other != name
                and not compendium.slow(other, scholarship)
                and not compendium.locked(other, clock())
                for other in usable
            )

        outcome = study(
            s,
            noun,
            name,
            tally,
            give_way,
            slow=compendium.slow(name, scholarship),
            until=deadline,
        )
        if outcome in ("clarity", "locked"):
            compendium.lock(name, clock())
            if outcome == "clarity":
                tally["charts"] += 1
                shown = trainer.mindstates(s, SKILLS)
                s.echo(
                    f"compendium: {name} at clarity — "
                    + ", ".join(
                        f"{skill} {shown.get(skill, '?')}/34" for skill in SKILLS
                    )
                )
        elif outcome == "slow":
            s.echo(
                f"compendium: the {name} is slow at your Scholarship — "
                "back to it when the others rest"
            )
        elif outcome == "slice":
            s.echo(
                f"compendium: {SLOW_SLICE // 60} minutes on the {name} — "
                "its progress keeps for the next turn"
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
        SKILLS,
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
