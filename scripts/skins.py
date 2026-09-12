"""Sell the bundle of skins you wear at the nearest tannery:  ;skins

    ;skins             walk to the nearest tannery, sell the bundle, keep the rope, stay there
    ;skins back        ... and walk back to where you started

A worn lumpy bundle takes every skin ;hunt cuts (the profile's
`bundle` setting) and sells as one item: the tanner pays the appraised
price for the whole bundle and hands the bundling rope back
(Elanthipedia: Bundle command, Falken's Tannery). Captured 2026-09-12
in the Crossing with seven rat skins: "You ask the tanner Falken to buy
a lumpy bundle." / "The tanner Falken ponders over the bundle for a
while, then hands you 111 Kronars." / "And there's your rope back
again." The script walks to the nearest room the map tags `tannery`,
takes the bundle off (or out of the loot container when it is not
worn), SELLs it from the hand, echoes what the tanner paid, puts the
rope into the loot container the profile names (or STOWs it) for the
next hunt's first skin, and stays at the tannery — where it started
is usually the hunting ground, and the first scripted run (2026-09-12)
walked back into the rats with the weapon stowed; `back` walks back
anyway. No bundle to sell, or a tanner who does not pay, stops it
with the answer echoed. Stops on death.
Stop with:  ;stop skins
"""

import re

from client.game import probe
from client.game.mapdb import MapDB
from client.game.profile import load_profile
from client.game.walker import locate, walk

COLLECT_SECONDS = 3
TAIL_SECONDS = 1.5

# A bundle that is not there: REMOVE and GET answer this (captured for
# GET 2026-09-12; the REMOVE refusals are assumptions until captured).
_NO_BUNDLE = ("what were you referring", "aren't wearing", "not wearing", "don't have")
# The tanner's payment line, captured 2026-09-12.
_PAID = re.compile(r"hands you (\d+) (\w+)")


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def _missing(answer):
    lowered = answer.lower()
    return any(needle in lowered for needle in _NO_BUNDLE)


def take_bundle(s, container):
    """The bundle into a hand — off the body, or out of the container;
    False when there is none either place."""
    if not _missing(ask(s, "remove my bundle")):
        return True
    command = f"get my bundle from my {container}" if container else "get my bundle"
    return not _missing(ask(s, command))


def run(s, words, mapdb, walk_fn=walk, profile=None):
    back = bool(words) and words[-1].lower() == "back"
    if profile is None:
        profile = load_profile(getattr(s.state, "name", None) or "")
    container = profile["loot_container"]
    tanneries = mapdb.rooms_tagged("tannery")
    if not tanneries:
        s.echo("skins: the map has no room tagged 'tannery'")
        return
    start = locate(mapdb, s.state)
    if not walk_fn(s, mapdb, set(tanneries), describe="the tannery"):
        s.echo("skins: could not reach a tannery — stopping")
        return
    if s.dead:
        s.echo("skins: you are dead — stopping")
        return
    if not take_bundle(s, container):
        where = f"in your {container}" if container else "in hand"
        s.echo(f"skins: no bundle worn or {where} — nothing to sell")
        return
    answer = ask(s, "sell my bundle")
    paid = _PAID.search(answer)
    if not paid:
        last = answer.strip().splitlines()[-1] if answer.strip() else "no answer"
        s.echo(f"skins: the tanner did not pay — {last}")
        return
    s.echo(f"skins: sold the bundle for {paid.group(1)} {paid.group(2)}")
    ask(s, f"put my rope in my {container}" if container else "stow my rope")
    if back and start is not None and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("skins: could not walk back — you are at the tannery")


def main(s):
    run(s, list(s.args), MapDB.load())
