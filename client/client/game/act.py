"""Ask the game and read what it said — the four helpers every script
used to carry its own copy of (#407): ask, missing, said, unknown.

    answer = act.ask(s, "get my bundling rope")      # the game's case kept
    if act.missing(answer):                          # either not-found wording
        ...
    s.echo(f"skins: {act.said(answer, NO_BUNDLE)}")  # the answer's own line
    act.unknown(s, "skins", "SELL", answer)          # the one report-it echo

ask() is probe.ask with one pair of collection windows (ASK_SECONDS and
TAIL_SECONDS, read at call time, so a test shortens them on this
module) and never lower-cases: the parsers that care about case
(money.parse_wealth, the HEALTH reader) read the answer as the game
wrote it, and probe.classify lowers it itself. The windows are the
largest any script used (;empath's 4 s opening, ;mechlore's 2 s tail):
since #248 they are ceilings, closed by the game's prompt and a quiet
stream, so the larger pair costs nothing live and never cuts a slow
answer short. No script keeps windows of its own.

missing() knows both of the game's wordings for a thing that is not
there, "What were you referring to?" and "I could not find what you
were referring to." (70 and 80 times in a hunt's logs): a table that
knew the first alone let a SEARCH's answer through unrecognized
(2026-09-20) and read a STOW's refusal as a stow (;forage). Twenty-six
scripts spelled the check their own way before this one.

said() is the line to quote in an echo: the one holding a needle the
caller names, never a bystander's — "Sekhhtha goes west." stood in for
"You're not experienced enough to go there." (#359), "Court Advisor
Aaiyaah just arrived." for a LISTEN's refusal (2026-09-23), another
player's dealings with the money-changer for his own answer (#389) —
else the first line, SILENCE when nothing came. A caller with no
wording to name gets the first line and says so.

unknown() is the "please report it" echo, written thirty-eight ways
before: `<prefix>: unrecognized <what> answer '<line>' — please report
it`, the line returned, and a tally's `unrecognized` count stepped
when one is passed (;hunt's end report counts them).
"""

from client.game import probe

ASK_SECONDS = 4  # the opening window after a send
TAIL_SECONDS = 2  # the window after a roundtime the command opened

# The game's two wordings for a thing that is not there; "could not
# find" alone also covers "I could not find a ..." forms.
NOT_FOUND = ("what were you referring", "could not find")

SILENCE = "(silence)"


def ask(s, command, seconds=None, tail=None):
    """The game's answer to `command`, as the game wrote it: the lines
    within `seconds` of the send and, after any roundtime it opened,
    within `tail` more (probe.ask — the queue cleared first, a
    "...wait N seconds" resent). The module's windows when none are
    given."""
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
    """Echo that nothing recognized the answer, the common way, and
    return the line quoted: `<prefix>: unrecognized <what> answer
    '<line>' — please report it` (`what` names the command or the
    step; empty, the echo says "unrecognized answer"). With a `tally`
    (an object counting `unrecognized`), the count steps by one."""
    line = said(answer)
    kind = f"unrecognized {what} answer" if what else "unrecognized answer"
    s.echo(f"{prefix}: {kind} {line!r} — please report it")
    if tally is not None:
        tally.unrecognized += 1
    return line
