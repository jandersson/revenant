"""Ask the game a question and classify its answer by keyword — the
half of a script that ;mechlore and ;favors used to each carry a copy of.

ask() sends a command and gathers the lines that follow, including the
ones the game holds back until the roundtime ends; classify() maps the
gathered text to the first outcome in an ordered table whose needle it
contains. Scripts keep their own outcome tables and collection windows
(module constants, so tests can shorten them) and call in here.

collect() is the piece every answer-reading script shares: it glues the
segments the session hands a script back into whole game lines. A line
the game styles or links arrives as several pieces, only the last of
which carries the newline (core.Engine.read marks it) — INV LIST's
<d>-linked items came apart into one piece per link, and the inventory
parser filed every nested item at the top level (#123).
"""

import time


def classify(text, outcomes):
    """The first outcome whose needles appear in the text (case-
    insensitive), or None. outcomes is an ordered sequence of
    (outcome, needles): put failure wordings before success ones when
    a needle is a substring of another ("you find nothing" vs "you
    find")."""
    lowered = text.lower()
    for outcome, needles in outcomes:
        if any(needle in lowered for needle in needles):
            return outcome
    return None


def collect(s, seconds, until=None):
    """Every main-stream line that arrives within the window, joined
    with newlines ("" when nothing does). A line containing `until`
    ends the wait early — the recognizable last line of an answer.

    Pieces are glued until one ends in a newline, which is how the
    engine marks the last piece of each line: a styled or linked line
    reaches a script in several pieces, and joining those with newlines
    tore INV LIST's indented items apart (#123). A piece left open when
    the window closes is kept as a line of its own.
    """
    lines = []
    partial = ""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        piece = s.get(timeout=0.5)
        if piece is None:
            continue
        partial += piece
        if not partial.endswith("\n"):
            continue
        line, partial = partial.rstrip("\r\n"), ""
        lines.append(line)
        if until is not None and until in line:
            break
    if partial:
        lines.append(partial)
    return "\n".join(lines)


def ask(s, command, seconds, tail_seconds):
    """Send a command and return the game's answer: the lines within
    `seconds` of sending, then — after any roundtime the command opened
    has run out — the lines within `tail_seconds` more.

    Results can land at the END of the roundtime (captured 2026-08-22:
    a 6s blind forage answered only after the old single collect window
    had closed, so the classifier saw just the narration). The roundtime
    isn't announced until the command goes out, so waitrt comes after
    the opening collect, never before it."""
    s.put(command)
    opening = collect(s, seconds)
    s.waitrt()
    tail = collect(s, tail_seconds)
    return f"{opening}\n{tail}" if tail else opening
