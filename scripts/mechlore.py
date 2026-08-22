"""Train Mechanical Lore by braiding foraged grass:  ;mechlore

Stand outdoors somewhere grassy and run it: the script forages grass,
braids it through its roundtimes until a rope forms (or the material
is ruined), drops the result, and repeats — pausing at mind-lock and
resuming as the pool drains, like ;athletics. Braiding grass is the
free entry method (Elanthipedia); vines come later (#71). Progress is
echoed about every five minutes. Stop with:  ;stop mechlore

The forage/braid message patterns are assumptions until captures pin
them — anything the script can't classify is echoed as
"mechlore: unrecognized ...": report those lines and they become
fixtures.
"""

import time

MIND_LOCK = 34  # mindstate 34/34: nothing more fits
RESUME_BELOW = 28  # resume once enough has drained to be worth it
LOCK_POLL = 30  # seconds between mindstate checks while locked
PAUSE = 1  # breather between commands
COLLECT_SECONDS = 3  # forage/braid answer in one quick burst
REPORT_EVERY_SECONDS = 300
MAX_BRAIDS_PER_PIECE = 30  # a rope forms well before this; a fuse, not a plan
FORAGE_FAILURES_BEFORE_GIVING_UP = 5

SKILL = "Mechanical Lore"

# Keyword classification of the game's answers (assumptions until
# captured — #71). Checked in order; first hit wins.
FORAGE_OUTCOMES = (
    ("ok", ("you manage to find", "you find", "you gather")),
    ("nothing_here", ("find nothing", "nothing like that", "nothing here")),
    ("indoors", ("must be outside", "can't forage here", "while inside")),
    ("hands_full", ("hands are full", "free hand")),
)
BRAID_OUTCOMES = (
    ("done", ("rope", "finish braiding", "you finish")),
    ("ruined", ("ruined", "too damaged", "falls apart", "unravel")),
    ("progress", ("braid", "twist", "weave")),
    ("no_material", ("what were you referring", "you need", "nothing to braid")),
)


def classify(text, outcomes):
    lowered = text.lower()
    for outcome, needles in outcomes:
        if any(needle in lowered for needle in needles):
            return outcome
    return None


def collect(s, seconds):
    pieces = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = s.get(timeout=0.5)
        if line is not None:
            pieces.append(line)
    return "\n".join(pieces)


def mindstate(state):
    """Mechanical Lore mindstate 0-34, or None when it isn't in the
    exp window yet."""
    experience = getattr(state, "experience", None) or {}
    entry = experience.get(SKILL)
    return entry["mindstate"] if entry else None


def wait_for_drain(s):
    """Pause at mind-lock until the pool drains enough to be worth it."""
    s.echo(f"mechlore: {SKILL} mind-locked — pausing until it drains")
    while True:
        s.sleep(LOCK_POLL)
        current = mindstate(s.state)
        if current is None or current <= RESUME_BELOW:
            return


def ask(s, command):
    s.put(command)
    s.waitrt()
    return collect(s, COLLECT_SECONDS)


def braid_piece(s):
    """Braid what's in hand until it's a rope or ruined; drop either.
    Returns braid count for the report."""
    for braids in range(1, MAX_BRAIDS_PER_PIECE + 1):
        answer = ask(s, "braid my grass")
        outcome = classify(answer, BRAID_OUTCOMES)
        if outcome == "done":
            ask(s, "drop my rope")
            return braids
        if outcome == "ruined":
            ask(s, "drop my grass")
            return braids
        if outcome == "no_material":
            return braids
        if outcome is None:
            for line in answer.splitlines():
                if line.strip():
                    s.echo(f"mechlore: unrecognized (braid): {line.strip()}")
                    break
        s.sleep(PAUSE)
    # The fuse blew: stop feeding a piece that never resolves.
    ask(s, "drop my grass")
    return MAX_BRAIDS_PER_PIECE


def main(s):
    pieces, braids, failures = 0, 0, 0
    last_report = time.monotonic()
    s.echo("mechlore: braiding grass — stand outdoors somewhere grassy")
    while True:
        current = mindstate(s.state)
        if current is not None and current >= MIND_LOCK:
            wait_for_drain(s)
            continue
        answer = ask(s, "forage grass")
        outcome = classify(answer, FORAGE_OUTCOMES)
        if outcome == "ok":
            failures = 0
            pieces += 1
            braids += braid_piece(s)
        elif outcome == "hands_full":
            s.echo("mechlore: hands full — empty them and I'll continue")
            s.sleep(LOCK_POLL)
        else:
            failures += 1
            if outcome is None:
                for line in answer.splitlines():
                    if line.strip():
                        s.echo(f"mechlore: unrecognized (forage): {line.strip()}")
                        break
            if failures >= FORAGE_FAILURES_BEFORE_GIVING_UP:
                s.echo(
                    "mechlore: can't forage grass here — move somewhere "
                    "grassy (outdoors) and ;run mechlore again"
                )
                return
            s.sleep(PAUSE)
        now = time.monotonic()
        if now - last_report >= REPORT_EVERY_SECONDS:
            last_report = now
            shown = mindstate(s.state)
            s.echo(
                f"mechlore: {pieces} pieces, {braids} braids — "
                f"{SKILL} mindstate {shown if shown is not None else '?'}"
            )
        s.sleep(PAUSE)
