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
mindstate(s, skill)             the exp window's mindstate for a skill, or None.
ensure_mindstate(s, skill, ask) the same, asking EXP <skill> when the window
                   lacks the skill and seeding the parser's whole entry (#239).
"""

import re

from client.engine.xml_data import LEARNING_RATES


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


def _entry(s, skill):
    """The exp window's entry for `skill`, the name matched ignoring
    case (a plan or a script says "parry ability"); when a lowercase
    seed from before #295 sits beside the window's own spelling, the
    window's wins."""
    experience = getattr(s.state, "experience", None) or {}
    wanted = skill.strip().lower()
    found = [
        (name, entry)
        for name, entry in experience.items()
        if str(name).strip().lower() == wanted and entry
    ]
    if not found:
        return None
    for name, entry in found:
        if name != name.lower():
            return entry
    return found[0][1]


def mindstate(s, skill):
    """The exp window's mindstate (0-34) for `skill`, or None when the
    window does not list it — a clear pool is absent from it, and a
    guild without the skill never shows it."""
    entry = _entry(s, skill)
    return entry["mindstate"] if entry else None


def _exp_answer(skill):
    # Case-insensitive: a script's ask() may lower-case the answer.
    return re.compile(
        rf"(?P<name>{re.escape(skill)}):\s+(\d+)\s+[\d.]+%\s+.*?\((\d+)/34\)",
        re.IGNORECASE,
    )


def _window_name(skill, printed):
    """The key the exp window would use: the answer's own spelling when
    it kept its case, else the skill in title case — "parry ability"
    seeded as "Parry Ability", so the window's later pushes update the
    same entry rather than leaving the seed stuck beside it (#295: a
    class read 11/34 for half an hour while the window said 25)."""
    if printed != printed.lower():
        return printed.strip()
    return " ".join(word.capitalize() for word in skill.strip().split())


def ensure_mindstate(s, skill, ask):
    """The mindstate: the exp window's, or EXP <skill>'s own answer when
    the window does not list the skill — `ask(s, command)` returns the
    game's text. The answer seeds a whole entry in the parser's shape
    (rank, percent, mindstate, rate): the engine renders every entry of
    the state, and a seed without a rate took the session down (#239).
    None when the game shows no such skill."""
    value = mindstate(s, skill)
    if value is None:
        answer = ask(s, f"exp {skill.lower()}")
        value = mindstate(s, skill)
        if value is None:
            match = _exp_answer(skill).search(answer or "")
            if match:
                value = int(match.group(3))
                s.state.experience = dict(getattr(s.state, "experience", None) or {})
                s.state.experience[_window_name(skill, match.group("name"))] = {
                    "rank": int(match.group(2)),
                    "percent": 0,
                    "mindstate": value,
                    "rate": LEARNING_RATES[min(value, 34)],
                }
    return value
