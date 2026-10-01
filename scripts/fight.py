"""Kill everything hostile in the room:  ;fight

One sweep: attacks whatever is engaging you until the room holds no
more hostiles (the crtrStatus state, docs/combat.md), disposing of
each corpse with SEARCH so it never soaks a swing, then exits. Breaks
off with the shared escape (client/game/flight.py: retreat, retreat,
a move, until the room changes) if health falls below 60%, and ends
on death. Bare ATTACK swings at whatever faces you — when nothing
does, FACE NEXT turns to the next attacker (assumption pending
capture). Stop early with:  ;stop fight
"""

import re

from client.game import flight
from client.game.act import ask, missing

HEALTH_FLOOR = 60  # % — below this, escape instead of trading blows
MAX_ACTIONS = 60  # a sweep, not a campaign

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


def main(s):
    if not hostiles(s.state):
        s.echo("fight: nothing hostile here")
        return
    kills = 0
    cleared = False
    for _ in range(MAX_ACTIONS):
        if s.dead:
            s.echo("fight: you are dead — stopping")
            return
        if not hostiles(s.state):
            cleared = True
            break
        current = health(s.state)
        if current is not None and current < HEALTH_FLOOR:
            s.echo(f"fight: health {current}% — breaking off")
            flight.react(s, "fight")
            return
        text = ask(s, "attack")
        lowered = text.lower()
        if any(word in lowered for word in _KILL_WORDS):
            kills += 1
            s.echo(f"fight: {kills} down")
        if any(word in lowered for word in _ALL_DEAD):
            cleared = True  # the game says so; the hostile state lags
            break
        corpse = _DEAD_NOUN.search(text)
        if corpse:
            ask(s, f"search {corpse.group(1)}")
        elif missing(text):
            ask(s, "face next")
    remaining = len(hostiles(s.state))
    if cleared or not remaining:
        s.echo(f"fight: room clear — {kills} kill(s)")
    else:
        s.echo(f"fight: action budget spent with {remaining} hostile(s) left")
