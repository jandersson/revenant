"""Whether the guards want you — RECALL WARRANT, read back:  ;warrant

    ;warrant            ask the game and print the answer

The town's guards capture a wanted character in time as they pass,
and SURRENDER clears the charges (Elanthipedia: Justice); RECALL
WARRANT is the free way to know first — captured 2026-09-22 on a
Thief: "Taking a moment to think, you are certain you do not have any
outstanding warrants." `client/game/justice.py` holds the wording and
`parse_warrants`, for any script that walks a character into a town.
The wanted wording is uncaptured and is said as such when it comes.
Stop with:  ;stop warrant (it ends on its own within seconds).
"""

from client.game import probe
from client.game.justice import COMMAND, describe, parse_warrants

COLLECT_SECONDS = 3
TAIL_SECONDS = 1


def check(s):
    """RECALL WARRANT asked; False clean, True wanted, None unknown."""
    answer = probe.ask(s, COMMAND, COLLECT_SECONDS, TAIL_SECONDS)
    wanted = parse_warrants(answer)
    if wanted is None:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"warrant: unrecognized answer {first!r} — please report it")
    return wanted


def main(s):
    s.echo(f"warrant: {describe(check(s))}")
