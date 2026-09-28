"""The almanac — one STUDY fills a random skill's pool by half, then the
book rests ten minutes; the profile's `almanac` names its noun, and
any running script studies it at its next safe point once it is ready
(client/game/interlude.py), ;hunt mid-fight too, sharing this module's
timer.

Captured 2026-09-28 on the Squat Bungalow's diamond-hide almanac:
STUDY, open and ready — "You set about studying your diamond-hide
almanac intently.  You believe you've learned something significant
about Bow!" (10 s; Bow 0 to 17/34); on its timer — "You've gleaned all
the insight you can from the diamond-hide almanac, for now. /
[Please try again in 9 roisaen.]" (rounded down: 9:48 were left), and
under a minute "[Please try again in about a roisan.]"; closed — "...you would learn
something significant about a random skill if you were to OPEN the
diamond-hide almanac and STUDY its contents." (no study; the same once
the timer ran out, so the skill is not rolled ahead). Elanthipedia:
Almanac — ten minutes, shared by every almanac and whoever studied;
dr-scripts' almanac.lic studies on a 600 s timer of its own.
"""

import re
import time

SECONDS = 600
_LEARNED = re.compile(r"learned something significant about (?P<skill>[^!.]+)")
_WAIT = re.compile(r"try again in (?:about )?(?P<n>\d+|an?) roisa")
_CLOSED = "if you were to open"
_MISSING = ("what were you", "could not find")

# The next moment a study is worth trying, per noun; shared by every
# script in the session (a reload starts it over — the game's countdown
# corrects it at the next try).
_NEXT = {}
_OFF = set()
clock = time.monotonic  # tests replace it


def answer(text):
    """What a STUDY said: ("learned", skill, seconds to the next),
    ("waiting", None, seconds), ("closed", None, 0), or (None, None, 0)
    for an answer outside the table."""
    text = str(text or "")
    learned = _LEARNED.search(text)
    if learned:
        return "learned", learned.group("skill").strip(), SECONDS
    wait = _WAIT.search(text)
    if wait:
        # The countdown is rounded down: "9 roisaen" came with 9:48 left
        # and the next try, 13 s early, read "about a roisan" (2026-09-28).
        n = wait.group("n")
        return "waiting", None, (int(n) + 1) * 60 if n.isdigit() else 60
    if _CLOSED in text.lower():
        return "closed", None, 0
    return None, None, 0


def ready(noun):
    return bool(noun) and noun not in _OFF and clock() >= _NEXT.get(noun, 0.0)


def hand_free(state, noun):
    """True when the book is in hand or a hand is free for it."""
    hands = [getattr(state, side, None) for side in ("left_hand", "right_hand")]
    return any((hand or {}).get("noun") == noun for hand in hands) or not all(hands)


def study(s, noun, ask, prefix):
    """The almanac studied if ready and a hand is free: GOT (unless in
    hand), OPENed, STUDIEd, stowed again unless it was in hand. `ask` is
    the caller's (s, command) -> answer. The skill learned, or None."""
    if not ready(noun) or getattr(s, "dead", False):
        return None
    state = s.state
    hands = [getattr(state, side, None) for side in ("left_hand", "right_hand")]
    held = any((hand or {}).get("noun") == noun for hand in hands)
    if not held and all(hands):
        return None  # no hand free: the next chance
    s.waitrt()
    got = "" if held else ask(s, f"get my {noun}").lower()
    if any(word in got for word in _MISSING):
        s.echo(f"{prefix}: no {noun} on you — the almanac is off for this session")
        _OFF.add(noun)
        return None
    ask(s, f"open my {noun}")
    said = ask(s, f"study my {noun}")
    s.waitrt()
    if not held:
        ask(s, f"stow my {noun}")
    outcome, skill, wait = answer(said)
    if outcome == "learned":
        s.echo(f"{prefix}: almanac studied — {skill}")
    elif outcome is None:
        first = (said.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"{prefix}: the almanac answered {first!r} — trying again in 10 minutes")
        wait = SECONDS
    _NEXT[noun] = clock() + wait + 20
    return skill
