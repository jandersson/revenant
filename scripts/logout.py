"""Log this character out — QUIT, from inside the session:  ;logout

    ;logout            QUIT the game; the session ends with the link

The game keeps a character in the world when a front end merely
closes ("Closing your front end does NOT necessarily drop your
character from the game! Type QUIT or EXIT!"), so a log-out is QUIT.
`;train` logs a helper character out after a class through this
script (client/game/helper.py, 2026-09-22): a script's own QUIT never
met the session's policy, which refused an outside one until #434
(2026-10-03) and lets it through behind the gate now. Nothing is
stowed or walked first — the character logs out where it stands, as
`;deathwatch` does.
"""


def main(s):
    s.echo("logout: QUIT")
    s.put("quit")
