"""Ask the game and read what it said: the four calls every script uses.

    answer = act.ask(s, "get my bundling rope")   # the answer, the game's case kept
    act.missing(answer)                           # True for either not-found wording
    act.said(answer, NO_BUNDLE)                   # the line to quote: one holding a wording, else the first
    act.unknown(s, "skins", "SELL", answer)       # the one "please report it" echo

ask() is probe.ask with one pair of windows (ASK_SECONDS, TAIL_SECONDS,
read at call time) and never lower-cases. NOT_FOUND is the pair of
not-found wordings, for a classify table.
"""

import re
from client.game import probe

_NOTES = """
The windows are the largest any script used (4 s, 2 s): since #248 they
are ceilings, closed by the prompt and a quiet stream, so the larger
pair costs nothing live. The game has two not-found wordings, "What were
you referring to?" and "I could not find what you were referring to.";
a table that knew the first alone let a SEARCH through unrecognized
(2026-09-20) and read a STOW's refusal as a stow (;forage). said() picks
the game's line over a bystander's that landed first in the window
(#359, #389). Before #407 twenty-six scripts carried an ask, thirty a
not-found check, forty-eight quoted a first line inline and
thirty-eight wrote the report-it echo their own way.
"""

ASK_SECONDS = 4  # the opening window after a send
TAIL_SECONDS = 2  # the window after a roundtime the command opened

# The game's two wordings for a thing that is not there; "could not
# find" alone also covers "I could not find a ..." forms.
# The two not-found answers, and the parser's refusal of a name it
# cannot read at all: an item is ADJECTIVE NOUN, never three words
# (the operator, 2026-10-08) — `get my massive coal nugget` answered
# "Please rephrase that command." and ;remedies looped on it (#488).
NOT_FOUND = ("what were you referring", "could not find", "please rephrase")

SILENCE = "(silence)"


def ask(s, command, seconds=None, tail=None):
    """The game's answer to `command`, as the game wrote it, the
    roundtime tail included (probe.ask with the module's windows)."""
    return probe.ask(
        s,
        command,
        ASK_SECONDS if seconds is None else seconds,
        TAIL_SECONDS if tail is None else tail,
    )


def missing(answer, more=()):
    """True when the answer says the thing is not there: either of the
    game's wordings (NOT_FOUND), or one of a caller's own in `more`
    ("don't have", "not wearing" for a thing that must be on you)."""
    lowered = str(answer or "").lower()
    return any(needle in lowered for needle in (*NOT_FOUND, *more))


# Lines that answer no command and can close an answer window before
# the command's own lines land (#483): a creature's arrival, the rested
# line, a player's coming and going, the parser's balance line. A LOOT
# answered "You feel fully rested." and its box went uncounted; a BOB
# answered with an earlier swing's line (2026-10-07/08).
NOISE = (
    "heralding the arrival",
    "just arrived",
    "joins the adventure",
    "you feel fully rested",
    "you feel rested",
)
_COMINGS = re.compile(
    r"\b(arrives|arrived|leaves|left|goes|went|runs|walks|wanders)\b.*\.$", re.I
)


def noise_only(answer, swings=False):
    """True when every line of the window is noise (NOISE, a coming or
    going without a 'you', a [You're ...] balance line, and with `swings`
    a combat stream's `<` swing line) — or the window is empty. Then the
    command's own answer is still to come: rest_of_answer()."""
    found = [line.strip() for line in str(answer or "").splitlines() if line.strip()]
    for line in found:
        lowered = line.lower()
        if any(word in lowered for word in NOISE):
            continue
        if line.startswith("[You're") or line.startswith("[You are"):
            continue
        if swings and line.startswith(("<", "&lt;")):
            continue
        if _COMINGS.search(line) and not re.search(r"\byou\b|\byour\b", lowered):
            continue
        return False
    return True


def rest_of_answer(s, seconds=None):
    """The lines that follow a window a stray line closed early: one more
    collect of TAIL_SECONDS (a test patches this name on the script)."""
    return probe.collect(s, TAIL_SECONDS if seconds is None else seconds)


def lines(answer):
    """The answer's non-blank lines, each stripped, in order."""
    return [line.strip() for line in str(answer or "").splitlines() if line.strip()]


def said(answer, needles=()):
    """The line to quote: the first holding one of `needles` (the
    wording the caller knows, case-insensitive), else the first line,
    else SILENCE. A bystander's line that landed first in the window
    is never quoted for the game's own when a needle names the game's."""
    found = lines(answer)
    if not found:
        return SILENCE
    wanted = tuple(str(needle).lower() for needle in needles)
    for line in found:
        lowered = line.lower()
        if any(needle in lowered for needle in wanted):
            return line
    return found[0]


def unknown(s, prefix, what, answer, tally=None):
    """Echo `<prefix>: unrecognized <what> answer '<line>' — please report
    it` (no `what`: "unrecognized answer"), step `tally.unrecognized` when a
    tally is given, and return the line quoted."""
    line = said(answer)
    kind = f"unrecognized {what} answer" if what else "unrecognized answer"
    s.echo(f"{prefix}: {kind} {line!r} — please report it")
    if tally is not None:
        tally.unrecognized += 1
    return line
