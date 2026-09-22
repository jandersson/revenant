"""The loop idioms every trainer script repeats: the typed "return", the
danger check, the sliced pause that notices both.

Eight scripts (attune, cast, forage, heal, perform, scholarship, seek,
soul) each carried the same three functions until 2026-09-22; they
import them from here now, so the graceful-end rule — `;stop <name>`
quits at once, a typed `;<name> return` finishes the step in hand and
ends (the operator, 2026-09-12) — has one home. Qt-free, reloadable.

wants_stop(s)      True once "return" was typed at the script.
danger(s)          why the loop must end now — "you are dead", "hostiles
                   in the room" — or None. The floors a fight needs
                   (health, wounds, stuns) stay with ;hunt and ;athletics.
pause(s, seconds)  sleep in one-second slices so a typed return or a
                   danger is noticed at once; False when either arrived.
"""


def wants_stop(s):
    """True once "return" was typed at the script: finish the step in
    hand and end. (;stop <name> is the abrupt end for every script; a
    typed word is the graceful one, the operator's rule 2026-09-12.)"""
    while (line := s.command(timeout=0)) is not None:
        if "return" in line.lower():
            return True
    return False


def danger(s):
    """Why a training loop must stop right now, or None: the character
    is dead, or something hostile shares the room."""
    if s.dead:
        return "you are dead"
    if getattr(s.state, "hostiles", None):
        return "hostiles in the room"
    return None


def pause(s, seconds):
    """Sleep `seconds` in one-second slices so a typed return or danger
    is noticed at once; False when either arrived, True when the whole
    pause passed."""
    left = seconds
    while left > 0:
        step = min(1, left)
        s.sleep(step)
        left -= step
        if wants_stop(s) or danger(s):
            return False
    return True
