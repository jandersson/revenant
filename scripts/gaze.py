"""Train Arcana on the sanowret crystal:  ;gaze

    ;gaze                 GAZE at the crystal whenever concentration is full, until Arcana mind-locks
    ;gaze exhale          EXHALE on it instead: half the lesson, no lecture to sit through
    ;gaze until=30        stop at that mindstate instead of 34
    ;gaze once            exit at mind-lock instead of holding for the drain
    ;gaze crystal=<name>  another crystal than "sanowret crystal"
    ;gaze return          (typed while it runs) finish the lecture in hand and end
    ;stop gaze            quit at once

What it does
  - GETs the crystal (a hand freed first), waits for concentration at 100%, GAZEs,
    reads the lecture to its end, and waits for the refill before the next.
  - At mind-lock it holds until the pool drains, then resumes (client/game/trainer.py);
    ;train runs it as a task and ends it at the plan's target.
  - STOWs the crystal at the end, a ;stop included. Never a DROP: the crystal damages.

What stops it: death, hostiles in the room, no crystal on you, three gazes in a row
the game refused, four without gain.

The wordings are client/game/gaze.py's (Elanthipedia: Sanowret crystal).
"""

from client.game import act, gaze, hands, probe, trainer
from client.game.act import ask, missing, said
from client.game.loop import mindstate, pause

_NOTES = """
Riphik carries a frost-red sanowret crystal (the Chris' Mass kind) in his
backpack; nothing used it before 2026-10-09 (#500). The wiki: GAZE is
about thirty seconds of lecture and ~51% concentration whatever the
rank; EXHALE half the lesson at once for the same cost; both wait only
on the refill. Learning scales with Arcana rank, so a high rank gets
more per gaze. The wordings here are the verb template's, not captured
— the first live run's answers go into the fixtures.
"""

REFILL_POLL = 5  # seconds between looks at the concentration bar
REFUSED_LIMIT = 3  # gazes in a row the game refused before giving up
STALE_LIMIT = 4  # gazes in a row without gain before giving up
TAIL_SECONDS = 0.5


def parse_args(args):
    options = {
        "exhale": False,
        "until": trainer.MIND_LOCK,
        "once": False,
        "crystal": gaze.CRYSTAL,
    }
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "until" and value.isdigit():
            options["until"] = int(value)
        elif sep and key == "crystal" and value:
            options["crystal"] = value
        elif key in ("exhale", "once"):
            options[key] = True
    return options


def take(s, crystal):
    """The crystal into a hand: True when it is there."""
    if hands.holding(s, crystal.split()[-1]):
        return True
    if hands.full(s):
        hands.free_one(s)
    answer = ask(s, f"get my {crystal}")
    if missing(answer) and not hands.holding(s, crystal.split()[-1]):
        s.echo(f"gaze: no {crystal} on you — {said(answer)}")
        return False
    return True


def put_away(s, crystal):
    if hands.holding(s, crystal.split()[-1]):
        ask(s, f"stow my {crystal}")


def run(s, options):
    """The setup — the crystal in hand — then the trainer loop with one
    step: wait for the concentration, one GAZE (or EXHALE), the lecture
    read to its end."""
    crystal = options["crystal"]
    if not take(s, crystal):
        return "no crystal"
    exhale = options["exhale"]
    verb = "EXHALE" if exhale else "GAZE"
    refused, stale, count = 0, 0, 0

    def step(s):
        nonlocal refused, stale, count
        while not gaze.ready(getattr(s.state, "vitals", None)):
            if not pause(s, REFILL_POLL):
                return None  # the loop says why
        before = mindstate(s, gaze.SKILL)
        answer = ask(s, gaze.command(exhale, crystal))
        if missing(answer):
            return f"the {crystal} is gone from your hands"
        if gaze.said(answer, gaze.EXHALED if exhale else gaze.GAZED):
            refused = 0
            if not exhale and not gaze.said(answer, gaze.LECTURE_END):
                probe.collect(s, gaze.LECTURE_SECONDS, until="quite enlightened")
        else:
            refused += 1
            if refused == 1:
                act.unknown(s, "gaze", verb, answer)  # once a streak
            if refused >= REFUSED_LIMIT:
                return f"{verb} refused {REFUSED_LIMIT} times in a row"
            return None
        count += 1
        after = mindstate(s, gaze.SKILL)
        if after is not None and before is not None and after > before:
            stale = 0
        else:
            stale += 1
        if stale >= STALE_LIMIT and (after or 0) < options["until"]:
            return f"{STALE_LIMIT} {verb.lower()}s without gain"
        if count % 5 == 0:
            s.echo(f"gaze: Arcana {after}/34 after {count} {verb.lower()}s")
        return None

    return trainer.train(
        s,
        "gaze",
        gaze.SKILL,
        step,
        until=options["until"],
        once=options["once"],
        again="gazing again",
        finish=lambda s, why: put_away(s, crystal),
    )


def main(s):
    run(s, parse_args(s.args or []))
