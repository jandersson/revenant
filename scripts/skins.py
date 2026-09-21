"""Sell the bundle of skins you wear at the nearest tannery:  ;skins

    ;skins             walk to the nearest tannery, sell the bundle and every loose skin, keep the rope, stay there
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
anyway. Then the loose animal parts: a skin still in a hand (a hunt
whose sack had no room left it there, #262) and each skin noun out
of the loot container — GET, SELL, until none of that noun is left —
the tanner buying them one at a time (Falken's Tannery: "sell my
<bundle/skin/pelt/bones/animal part>"); the count and the sum are
said (#261: nine loose pelts and seven claws filled the sack on
2026-09-21). The single part's payment line is taken for the
bundle's shape until captured. No bundle to sell, or a tanner who
does not pay, stops it with the answer echoed. `bank` then runs ;bank through the handle and
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
# Animal parts the tanner buys one at a time — "sell my <bundle/skin/
# pelt/bones/animal part>" (Elanthipedia: Falken's Tannery) — fetched
# out of the loot container by noun until it holds none (#261: nine
# loose badger pelts and seven claws filled Cecil's sack).
SKIN_NOUNS = (
    "pelt",
    "claw",
    "skin",
    "hide",
    "fur",
    "tooth",
    "fang",
    "tail",
    "paw",
    "scale",
    "feather",
    "horn",
    "tusk",
    "bone",
    "ear",
    "wing",
    "beak",
    "shell",
)
MAX_LOOSE = 60  # parts of one noun sold in a run: the fuse


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


def sell_loose(s, container):
    """Every loose animal part sold, one at a time: one in a hand first
    (a hunt that found no room left it there, #262), then each noun of
    SKIN_NOUNS out of the loot container until it holds none (#261).
    The count and the sum are said; a part the tanner does not pay for
    goes back and is said. True when anything sold."""
    sold, total, unit = 0, 0, ""

    def sell(noun):
        nonlocal sold, total, unit
        paid = _PAID.search(ask(s, f"sell my {noun}"))
        if not paid:
            return False
        sold += 1
        total += int(paid.group(1))
        unit = paid.group(2)
        return True

    for side in ("left", "right"):
        held = getattr(s.state, f"{side}_hand", None)
        noun = held.get("noun") if isinstance(held, dict) else None
        if noun in SKIN_NOUNS and not sell(noun):
            s.echo(f"skins: the tanner did not pay for the {noun} in hand — it stays")
    for noun in SKIN_NOUNS:
        for _ in range(MAX_LOOSE):
            command = (
                f"get my {noun} from my {container}" if container else f"get my {noun}"
            )
            if _missing(ask(s, command)):
                break
            if not sell(noun):
                s.echo(f"skins: the tanner did not pay for a {noun} — put back")
                ask(
                    s,
                    f"put my {noun} in my {container}"
                    if container
                    else f"stow my {noun}",
                )
                break
    if sold:
        s.echo(f"skins: sold {sold} loose skin(s) for {total} {unit}")
    return sold > 0


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
    loose = sell_loose(s, container)
    if bank and not s.dead:
        # Nothing sold still banks: a hunt's search coins are in the
        # purse either way, and ;bank walks nothing when it is empty.
        hand_to_bank(s, keep)
    if not sold and not loose and not bank:
        return
    if back and start is not None and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("skins: could not walk back — you are at the tannery")


def main(s):
    run(s, list(s.args), MapDB.load())
