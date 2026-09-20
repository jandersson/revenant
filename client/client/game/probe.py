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
parser filed every nested item at the top level (#123). It reads the
story and the combat stream both (STORY_STREAMS): the game pushes
swings and kills through <pushStream id="combat"/>, which the main
window shows but a handle's default get() does not deliver, and the
second live ;hunt (2026-09-12) never saw one of its eight kills.
"""

import time

# An answer is complete once the game's prompt has followed it and the
# stream has stayed quiet this long (#248): ask() used to hold a script
# for its whole window and tail after the answer had arrived — 4.5 s a
# command in the hunt, a dozen seconds standing still per kill, "waiting
# a few seconds after the matching message" (the operator, 2026-09-20).
# The quiet stretch is what keeps a prompt that followed a bite or
# another player's arrival, right after the send, from closing the
# window before the answer itself arrives.
QUIET_SECONDS = 0.25

# What the main window shows: the story, and the combat stream the
# game pushes every swing and kill line through (<pushStream
# id="combat"/>). The engine routes that block as its own stream and a
# handle's get() reads the story alone by default, so every kill of
# the 2026-09-12 hunt was invisible to the answer collector — the loop
# swung at corpses and walked the ground until it declared it empty.
STORY_STREAMS = ("", "combat")


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


def _prompts(s):
    """The parser's count of prompts seen, or None for a handle whose
    state does not count them (a test's fake)."""
    state = getattr(s, "state", None)
    return getattr(state, "prompt_count", None) if state is not None else None


def roundtime_open(s):
    """True when the state says a roundtime or cast time is still to run,
    False when none is, None when the state cannot say (a fake)."""
    state = getattr(s, "state", None)
    seen = getattr(state, "server_time", None) if state is not None else None
    if seen is None:
        return None
    waits = (getattr(state, "roundtime", 0) or 0, getattr(state, "casttime", 0) or 0)
    return max(waits) > seen


def collect(s, seconds, until=None, prompts_from=None, quiet=QUIET_SECONDS):
    """Every main-stream line that arrives within the window, joined
    with newlines ("" when nothing does). A line containing `until`
    ends the wait early — the recognizable last line of an answer.
    With `prompts_from` (the prompt count before the command) the window
    also ends once a prompt past it has been seen and no piece has come
    for `quiet` seconds — the answer is complete (#248); nothing at all
    arriving still waits the window out.

    Pieces are glued until one ends in a newline, which is how the
    engine marks the last piece of each line: a styled or linked line
    reaches a script in several pieces, and joining those with newlines
    tore INV LIST's indented items apart (#123). A piece left open when
    the window closes is kept as a line of its own.
    """
    lines = []
    partial = ""
    deadline = time.monotonic() + seconds
    last_piece = None
    watching = prompts_from is not None
    while time.monotonic() < deadline:
        piece = s.get(timeout=0.1 if watching else 0.5, streams=STORY_STREAMS)
        if piece is None:
            if (
                watching
                and last_piece is not None
                and (_prompts(s) or 0) > prompts_from
                and time.monotonic() - last_piece >= quiet
            ):
                break
            continue
        last_piece = time.monotonic()
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
    the opening collect, never before it.

    Both windows are ceilings, not waits (#248): each ends once the
    game's prompt has closed the answer and the stream has gone quiet,
    and a command that opened no roundtime gets no tail at all — nothing
    lands later. A handle whose state counts no prompts (a test's fake)
    waits the windows out as before."""
    before = _prompts(s)
    s.put(command)
    opening = collect(s, seconds, prompts_from=before)
    if before is not None and roundtime_open(s) is False:
        return opening
    s.waitrt()
    tail = collect(s, tail_seconds, prompts_from=_prompts(s))
    return f"{opening}\n{tail}" if tail else opening
