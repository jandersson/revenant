"""Sell the bundle of skins you wear at the nearest tannery:  ;skins

    ;skins             walk to the nearest tannery, sell the bundle, keep the rope, stay there
    ;skins bank        ... then run ;bank and wait for it (the money-changer for foreign coins, DEPOSIT ALL; keep=N is passed on)
    ;skins back        ... and walk back to where you started (bank back: both)

A worn lumpy bundle takes every skin ;hunt cuts (the profile's
`bundle` setting) and sells as one item: the tanner pays the appraised
price for the whole bundle and hands the bundling rope back
(Elanthipedia: Bundle command, Falken's Tannery). Captured 2026-09-12
in the Crossing with seven rat skins: "You ask the tanner Falken to buy
a lumpy bundle." / "The tanner Falken ponders over the bundle for a
while, then hands you 111 Kronars." / "And there's your rope back
again." The script walks to the nearest room the map tags `tannery`,
takes the bundle off (or out of the loot container when it is not
worn; one already in a hand — a run stopped between REMOVE and SELL,
2026-09-14 — is sold as it is), SELLs it from the hand, echoes what the tanner paid, puts the
rope into the loot container the profile names (or STOWs it) for the
next hunt's first skin, and stays at the tannery — where it started
is usually the hunting ground, and the first scripted run (2026-09-12)
walked back into the rats with the weapon stowed; `back` walks back
anyway. No bundle to sell, or a tanner who does not pay, stops it
with the answer echoed. `bank` then runs ;bank through the handle and
waits for it — the banking lives there (#235: the money-changer for
every foreign coin, DEPOSIT ALL, `keep=N` withdrawn back) and ;skins
used to carry a second, poorer copy of its last step (the operator,
2026-09-20: "it should just do ;bank"); a ;bank already running is
the operator's and is left alone, said. Selling and banking stay
distinct ;train tasks: the starter plan runs `{"script": "skins"}` and
then `{"script": "bank"}`, each with no skills, once a cycle after the
hunt. Stops on death.
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


def in_hand(s):
    """True when the parser's hand tags show the bundle held already —
    a run stopped between REMOVE and SELL left it there (2026-09-14)."""
    for side in ("left", "right"):
        held = getattr(s.state, f"{side}_hand", None)
        if isinstance(held, dict) and held.get("noun") == "bundle":
            return True
    return False


def take_bundle(s, container):
    """The bundle into a hand — there already, off the body, or out of
    the container; False when there is none any place."""
    if in_hand(s):
        return True
    if not _missing(ask(s, "remove my bundle")):
        return True
    command = f"get my bundle from my {container}" if container else "get my bundle"
    return not _missing(ask(s, command))


def hand_to_bank(s, args):
    """Run ;bank with `args` (keep=N) and wait for it to end: the purse's
    banking lives there, not here (the operator, 2026-09-20). False,
    said, when it could not start — one already running is the
    operator's own."""
    if not s.run("bank", list(args)):
        s.echo("skins: could not start ;bank — the purse stays as it is")
        return False
    while s.is_running("bank"):
        s.sleep(1)
    return True


def sell_bundle(s, container):
    """The bundle sold and the rope kept; False, said, when there was
    none to sell or the tanner did not pay."""
    if not take_bundle(s, container):
        where = f"in your {container}" if container else "in hand"
        s.echo(f"skins: no bundle worn or {where} — nothing to sell")
        return False
    answer = ask(s, "sell my bundle")
    paid = _PAID.search(answer)
    if not paid:
        last = answer.strip().splitlines()[-1] if answer.strip() else "no answer"
        s.echo(f"skins: the tanner did not pay — {last}")
        return False
    s.echo(f"skins: sold the bundle for {paid.group(1)} {paid.group(2)}")
    ask(s, f"put my rope in my {container}" if container else "stow my rope")
    return True


def run(s, words, mapdb, walk_fn=walk, profile=None):
    lowered = [word.lower() for word in words]
    back = bool(lowered) and lowered[-1] == "back"
    bank = "bank" in lowered
    keep = [word for word in lowered if word.startswith("keep=")]
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
    sold = sell_bundle(s, container)
    if bank and not s.dead:
        # Nothing sold still banks: a hunt's search coins are in the
        # purse either way, and ;bank walks nothing when it is empty.
        hand_to_bank(s, keep)
    if not sold and not bank:
        return
    if back and start is not None and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("skins: could not walk back — you are at the tannery")


def main(s):
    run(s, list(s.args), MapDB.load())
