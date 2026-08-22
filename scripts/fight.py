"""Kill everything hostile in the room:  ;fight

One sweep: attacks whatever is engaging you until the room holds no
more hostiles (the crtrStatus state, docs/combat.md), disposing of
each corpse with SEARCH so it never soaks a swing, then exits. Breaks
off with the burst-escape recipe (retreat, retreat, first exit) if
health falls below 60%. Bare ATTACK swings at whatever faces you —
when nothing does, FACE NEXT turns to the next attacker (assumption
pending capture). Stop early with:  ;stop fight
"""

import re
import time

HEALTH_FLOOR = 60  # % — below this, escape instead of trading blows
MAX_ACTIONS = 60  # a sweep, not a campaign
COLLECT_SECONDS = 4

_DEAD_NOUN = re.compile(r"The (\w+) is already quite dead")
_KILL_WORDS = ("tips over", "goes still", "falls down", " dies", "collapses")
# Bare ATTACK with every attacker dead (captured 2026-08-22):
# "There is nothing else to face!  What are you trying to attack?"
_ALL_DEAD = ("nothing else to face", "what are you trying to attack")


def hostiles(state):
    return dict(getattr(state, "hostiles", None) or {})


def health(state):
    vitals = getattr(state, "vitals", None) or {}
    return vitals.get("health")


def collect(s, seconds):
    pieces = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = s.get(timeout=0.5)
        if line is not None:
            pieces.append(line)
    return "\n".join(pieces)


def escape(s):
    """The burst: retreat to disengagement and step out before anything
    re-advances (docs/combat.md — spaced commands lose the race)."""
    exits = list(getattr(s.state, "compass", None) or [])
    direction = exits[0] if exits else "out"
    s.put("retreat")
    s.put("retreat")
    s.put(direction)
    s.echo(f"fight: breaking off — retreating {direction}")


def main(s):
    if not hostiles(s.state):
        s.echo("fight: nothing hostile here")
        return
    kills = 0
    cleared = False
    for _ in range(MAX_ACTIONS):
        if not hostiles(s.state):
            cleared = True
            break
        current = health(s.state)
        if current is not None and current < HEALTH_FLOOR:
            escape(s)
            s.echo(f"fight: health {current}% — out, stopping")
            return
        s.put("attack")
        s.waitrt()
        text = collect(s, COLLECT_SECONDS)
        lowered = text.lower()
        if any(word in lowered for word in _KILL_WORDS):
            kills += 1
            s.echo(f"fight: {kills} down")
        if any(word in lowered for word in _ALL_DEAD):
            cleared = True  # the game says so; the hostile state lags
            break
        corpse = _DEAD_NOUN.search(text)
        if corpse:
            s.put(f"search {corpse.group(1)}")
            s.waitrt()
            collect(s, 1.5)
        elif "referring" in lowered:
            s.put("face next")
            collect(s, 1.5)
    remaining = len(hostiles(s.state))
    if cleared or not remaining:
        s.echo(f"fight: room clear — {kills} kill(s)")
    else:
        s.echo(f"fight: action budget spent with {remaining} hostile(s) left")
