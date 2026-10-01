"""Train Mechanical Lore by braiding foraged grass:  ;mechlore

    ;mechlore            forage grass and braid it until the skill locks, then hold
    ;mechlore return     (typed while it runs) finish the piece in hand and end

Stand outdoors somewhere grassy and run it: the script forages grass,
braids it through its roundtimes until a rope forms (or the material
is ruined), drops the result — grass and grass rope are the only
things any script may drop (client/game/discard.py) — and repeats,
holding at mind-lock until the pool drains (client/game/trainer.py,
the loop every trainer runs). Braiding grass is the free entry method
(Elanthipedia); vines come later (#71). Progress is echoed about
every five minutes. Ends on death or hostiles (the shared escape).
Stop with:  ;stop mechlore, or ;mechlore return.

The forage/braid message patterns are assumptions until captures pin
them — anything the script can't classify is echoed as
"mechlore: unrecognized ...": report those lines and they become
fixtures.
"""

import time

from client.game import trainer
from client.game.act import NOT_FOUND, ask, unknown
from client.game.discard import drop
from client.game.loop import pause
from client.game.probe import classify

PAUSE = 1  # breather between commands
HANDS_FULL_WAIT = 30  # seconds before the next try with the hands full
REPORT_EVERY_SECONDS = 300
MAX_BRAIDS_PER_PIECE = 30  # a rope forms well before this; a fuse, not a plan
FORAGE_FAILURES_BEFORE_GIVING_UP = 5

SKILL = "Mechanical Lore"

# Keyword classification of the game's answers (assumptions until
# captured — #71). Checked in order; first hit wins. Failures come
# before "ok" so "You find nothing" never hits the "you find" needle.
FORAGE_OUTCOMES = (
    # "can't quite seem to remember" captured live 2026-08-22: foraging
    # an item the room can't supply turns into a blind forage.
    (
        "nothing_here",
        (
            "find nothing",
            "nothing like that",
            "nothing here",
            "can't quite seem to remember",
        ),
    ),
    ("indoors", ("must be outside", "can't forage here", "while inside")),
    ("hands_full", ("hands are full", "free hand")),
    ("ok", ("you manage to find", "you find", "you gather")),
)
BRAID_OUTCOMES = (
    ("done", ("rope", "finish braiding", "you finish")),
    ("ruined", ("ruined", "too damaged", "falls apart", "unravel")),
    ("progress", ("braid", "twist", "weave")),
    ("no_material", (*NOT_FOUND, "you need", "nothing to braid")),
)


def braid_piece(s):
    """Braid what's in hand until it's a rope or ruined; drop either.
    Returns braid count for the report."""
    for braids in range(1, MAX_BRAIDS_PER_PIECE + 1):
        answer = ask(s, "braid my grass")
        outcome = classify(answer, BRAID_OUTCOMES)
        if outcome == "done":
            drop(s, "grass rope", ask)
            return braids
        if outcome == "ruined":
            drop(s, "grass", ask)
            return braids
        if outcome == "no_material":
            return braids
        if outcome is None:
            unknown(s, "mechlore", "braid", answer)
        s.sleep(PAUSE)
    # The fuse blew: stop feeding a piece that never resolves.
    drop(s, "grass", ask)
    return MAX_BRAIDS_PER_PIECE


def run(s):
    """The trainer loop with one step: FORAGE GRASS, and a find braided."""
    counts = {"pieces": 0, "braids": 0, "failures": 0}
    reported = {"at": time.monotonic()}

    def step(s):
        answer = ask(s, "forage grass")
        outcome = classify(answer, FORAGE_OUTCOMES)
        if outcome == "ok":
            counts["failures"] = 0
            counts["pieces"] += 1
            counts["braids"] += braid_piece(s)
        elif outcome == "hands_full":
            s.echo("mechlore: hands full — empty them and I'll continue")
            if not pause(s, HANDS_FULL_WAIT):
                return None  # the loop says why
        else:
            counts["failures"] += 1
            if outcome is None:
                unknown(s, "mechlore", "forage", answer)
            if counts["failures"] >= FORAGE_FAILURES_BEFORE_GIVING_UP:
                return (
                    "can't forage grass here — move somewhere grassy (outdoors) "
                    "and ;run mechlore again"
                )
            s.sleep(PAUSE)
        now = time.monotonic()
        if now - reported["at"] >= REPORT_EVERY_SECONDS:
            reported["at"] = now
            shown = trainer.mindstates(s, SKILL).get(SKILL)
            s.echo(
                f"mechlore: {counts['pieces']} pieces, {counts['braids']} braids — "
                f"{SKILL} mindstate {shown if shown is not None else '?'}"
            )
        s.sleep(PAUSE)
        return None

    s.echo("mechlore: braiding grass — stand outdoors somewhere grassy")
    return trainer.train(s, "mechlore", SKILL, step, again="braiding again")


def main(s):
    run(s)
