"""Your character's state in one line, as the parser sees it:  ;status

    ;status            room | posture and badges | vitals | hands | hostiles | RT
    ;status watch      print it again whenever it changes, until stopped
    ;status return     (typed while watching) end the watch

The same view scripts use: `from client.game.status import status`,
then `status(s.state).stunned`, `.posture`, `.hands_empty`,
`.roundtime`, `.mindstate("Attunement")` — Lich's stunned?/hidden?/
checkprone idiom over the parser's raw indicator, vitals, hands,
room, hostiles and clock fields (client/game/status.py). It reads
the parser's state only and sends nothing; a state the game has not
pushed yet reads as None or 0, so the line right after login can be
thinner than a minute later. Stop with:  ;stop status
"""

from client.game.status import status

POLL = 0.5  # seconds between looks while watching


def main(s):
    words = [str(a).lower() for a in (s.args or [])]
    view = status(s.state)
    s.echo(f"status: {view.summary()}")
    if "watch" not in words:
        return
    last = view.summary()
    while True:
        line = s.command(timeout=POLL)
        if line and "return" in line.lower():
            s.echo("status: watch ended")
            return
        now = view.summary()
        if now != last:
            s.echo(f"status: {now}")
            last = now
