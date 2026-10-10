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

import re
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
# A creature's attack aimed at the character opens with "* " (every one
# of 3,441 in a hunt night's combat stream; the character's own swings
# open with "<"). It comes with a prompt of its own and is never a
# command's answer, so it never ends the window: a wolf's claw and its
# prompt closed a CIRCLE's window 2026-09-30 before "You fake a blood
# wolf..." arrived, and ;hunt read the claw as the answer (#398).
ATTACKED = "* "
# Another player's doing, a line that opens with the name of someone in
# the room (the parser's room_players), is never the answer either: a
# crafter beside Cecil put her pestle away with a prompt of its own
# right after his BUNDLE, the window closed on it, and ;remedies
# reported "Khaelyn puts her pestle in her farmer's haversack." as
# BUNDLE's answer (2026-10-03, #441). A command whose own answer opens
# with a player's name waits its window out instead.


def _bystander(line, names):
    """True when the line opens with the name of a player in the room."""
    return any(line.startswith((f"{name} ", f"{name}'s ")) for name in names)


# The game's refusal of a command sent inside a roundtime; the command
# did not run and ask() sends it again after the seconds named (#251).
_WAIT = re.compile(r"^\.\.\.wait (\d+) seconds?\.", re.MULTILINE)
WAIT_RETRIES = 3
WAIT_PAD = 0.2
# A sprung mime trap's invisible box (captured 2026-10-09 on an ogre
# coffer, #497): every command for ten minutes or so answers "You
# attempt that, but end up getting caught in an invisible box." (10 s
# roundtime) and nothing runs; it ends with "You suddenly feel nauseous,
# as if you'd been doing performance art." ask() waits for that line,
# MIME_WAIT at most, said once, and sends the command again — every
# script, not ;boxes alone (;compendium reported it four times, #504).
MIMED = ("caught in an invisible box",)
MIME_OVER = ("doing performance art",)
MIME_WAIT = 900
MIME_POLL = 5


def wait_seconds(answer):
    """The seconds a "...wait N seconds." refusal names, or None when
    the game ran the command."""
    held = _WAIT.search(answer or "")
    return int(held.group(1)) if held else None


def mimed(answer):
    """True when the answer is the mime trap's invisible box."""
    lowered = str(answer or "").lower()
    return any(needle in lowered for needle in MIMED)


def wait_mime(s):
    """Read the story for the line that ends the mime trap's box,
    MIME_WAIT seconds at most, said once: True when it ended."""
    s.echo(
        f"caught in a mime trap's invisible box — waiting it out (up to {MIME_WAIT // 60} minutes)"
    )
    deadline = clock() + MIME_WAIT
    while clock() < deadline and not getattr(s, "dead", False):
        piece = s.get(timeout=MIME_POLL, streams=STORY_STREAMS)
        if piece and any(needle in piece.lower() for needle in MIME_OVER):
            s.echo("out of the invisible box")
            return True
    return False


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
    """True when the state says a roundtime is still to run, False when
    none is, None when the state cannot say (a fake). A cast time is not
    one: a forming pattern holds no command but the CAST (#249), so a
    PREPARE's answer gets no tail."""
    state = getattr(s, "state", None)
    seen = getattr(state, "server_time", None) if state is not None else None
    if seen is None:
        return None
    return (getattr(state, "roundtime", 0) or 0) > seen


clock = time.monotonic  # tests replace it (#501)


def collect(s, seconds, until=None, prompts_from=None, quiet=None):
    """Every main-stream line that arrives within the window, joined
    with newlines ("" when nothing does). A line containing `until`
    ends the wait early — the recognizable last line of an answer.
    With `prompts_from` (the prompt count before the command) the window
    also ends once a prompt past it has been seen, a line that is not a
    creature's attack (ATTACKED, #398) or another player's (#441) has
    come, and no piece has come for `quiet` seconds — the answer is
    complete (#248); nothing at all arriving still waits the window out.

    Pieces are glued until one ends in a newline, which is how the
    engine marks the last piece of each line: a styled or linked line
    reaches a script in several pieces, and joining those with newlines
    tore INV LIST's indented items apart (#123). A piece left open when
    the window closes is kept as a line of its own. `quiet` defaults to
    QUIET_SECONDS as it stands at the call, so a test can widen it.
    """
    quiet = QUIET_SECONDS if quiet is None else quiet
    lines = []
    partial = ""
    deadline = clock() + seconds
    last_piece = None
    answered = False  # a line past the creatures' attacks and the players'
    watching = prompts_from is not None
    state = getattr(s, "state", None)
    names = tuple(getattr(state, "room_players", None) or ()) if watching else ()
    while clock() < deadline:
        piece = s.get(timeout=0.1 if watching else 0.5, streams=STORY_STREAMS)
        if piece is None:
            if (
                watching
                and answered
                and (_prompts(s) or 0) > prompts_from
                and clock() - last_piece >= quiet
            ):
                break
            continue
        last_piece = clock()
        partial += piece
        if not partial.endswith("\n"):
            continue
        line, partial = partial.rstrip("\r\n"), ""
        lines.append(line)
        answered = answered or not (
            line.startswith(ATTACKED) or _bystander(line, names)
        )
        if until is not None and until in line:
            break
    if partial:
        lines.append(partial)
    return "\n".join(lines)


def clear(s):
    """Drop the lines a handle has queued unread: what came before a
    command is no answer to it. A session started before Script.clear()
    has only the queue itself, emptied here all the same (#392); a
    test's fake has neither and keeps its lines."""
    method = getattr(s, "clear", None)
    if callable(method):
        method()
        return
    backlog = getattr(s, "_queue", None)
    if backlog is None or not hasattr(backlog, "get_nowait"):
        return
    while True:
        try:
            backlog.get_nowait()
        except Exception:  # queue.Empty
            return


def ask(s, command, seconds, tail_seconds):
    """Send a command and return the game's answer: the lines within
    `seconds` of sending, then — after any roundtime the command opened
    has run out — the lines within `tail_seconds` more. The lines queued
    before the send are dropped first (clear()): a parent that waited
    on a child read the child's stale "What were you referring to?" as
    the answer to its own GET, twice in a minute (2026-09-29, #392).

    Results can land at the END of the roundtime (captured 2026-08-22:
    a 6s blind forage answered only after the old single collect window
    had closed, so the classifier saw just the narration). The roundtime
    isn't announced until the command goes out, so waitrt comes after
    the opening collect, never before it.

    Both windows are ceilings, not waits (#248): each ends once the
    game's prompt has closed the answer and the stream has gone quiet,
    and a command that opened no roundtime gets no tail at all — nothing
    lands later. A handle whose state counts no prompts (a test's fake)
    waits the windows out as before.

    "...wait N seconds." is not an answer: the game did not run the
    command. It is sent again after those seconds, up to WAIT_RETRIES
    times, and the answer of the send the game took comes back (#251:
    a CAST one second after INVOKE's one-second roundtime — the parser's
    clock is whole seconds, and a roundtime ending in the current
    second is still running for a fraction no prompt stamp can show;
    32 refusals in one day's logs). Lich's DragonRealms commons resend
    on the same line (`DRC.bput`, docs/bibliography.md)."""
    boxed = False
    for attempt in range(WAIT_RETRIES + 1):
        clear(s)
        before = _prompts(s)
        s.put(command)
        opening = collect(s, seconds, prompts_from=before)
        if mimed(opening) and not boxed:
            # Nothing ran (#504): the box waited out once, then again —
            # at once when its release came in the same window.
            boxed = True
            over = any(needle in opening.lower() for needle in MIME_OVER)
            if over or wait_mime(s):
                continue
            break
        held = wait_seconds(opening)
        if held is None or attempt == WAIT_RETRIES:
            break
        s.sleep(held + WAIT_PAD)
    if before is not None and roundtime_open(s) is False:
        return opening
    s.waitrt()
    tail = collect(s, tail_seconds, prompts_from=_prompts(s))
    return f"{opening}\n{tail}" if tail else opening
