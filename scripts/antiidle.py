"""Keep the connection alive: nudge the game every few minutes.

Run:   ;antiidle          (5-minute nudges)
       ;antiidle 120      (custom interval, in seconds)
Stop:  ;stop antiidle
"""


def main(s):
    interval = int(s.args[0]) if s.args else 300
    s.echo(f"nudging every {interval}s — ;stop antiidle to end")
    while True:
        s.sleep(interval)
        s.put("time")
