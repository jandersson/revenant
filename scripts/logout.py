"""Log this character out — QUIT, from inside the session:  ;logout

    ;logout            QUIT the game; the session ends with the link

The game keeps a character in the world when a front end merely
closes ("Closing your front end does NOT necessarily drop your
character from the game! Type QUIT or EXIT!"), so a log-out is QUIT.
The session's policy refuses a QUIT sent from outside (#161), which
is right for a stranger's line and wrong for the operator's own loop:
`;train` logs a helper character out after a class through this
script (client/game/helper.py, 2026-09-22), and a script's own QUIT
passes. Nothing is stowed or walked first — the character logs out
where it stands, as `;deathwatch` does.
"""


def main(s):
    s.echo("logout: QUIT")
    s.put("quit")
