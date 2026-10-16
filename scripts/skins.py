"""Sell your bundle of skins at the nearest tannery:  ;skins

    ;skins               walk to the nearest tannery, sell the bundle, stay there
    ;skins bank          ... then run ;bank and wait for it
    ;skins bank keep=N   ... with keep=N passed on to ;bank
    ;skins back          ... then walk back to where you started (last word: ;skins bank back)
    ;stop skins          quit at once

What it does
  - Takes the bundle off (or out of the loot container, or from a hand) and SELLs it whole.
  - Keeps the rope for the next hunt: into the profile's `loot_container`, else STOWed.
  - Sells only the bundle. A loose skin in a hand or in the loot container stays
    where it is and is named: a hunt bundles every skin, so a loose one is kept
    on purpose or a sign something went wrong.
  - Says what the tanner paid for the bundle.
  - A Trader's kiosk in the room (a `kiosk` or `plinth`): the bundle is TIEd and
    sold to the best kiosk whose quote beats the tanner's, else to the tanner;
    says which and both prices. No rope back from a kiosk: the tanner gives one.
  - Stays at the tannery, since where it started is usually the hunting ground.
  - bank leaves the banking to ;bank (foreign coins exchanged, DEPOSIT ALL);
    a ;bank already running is the operator's and is left alone.

When it stops
  - death
  - no tannery on the map, or none reachable
  - nothing sold and no bank: it ends at the tannery, back or not

Every ;hunt that fought ends with ;skins bank. The profile's `bundle` setting
(docs/hunting.md); Elanthipedia's Bundle command, Falken's Tannery and
Prosperity in Absentia.
"""

import re
from collections import Counter

from client.game import hands, items, money, travel
from client.game.act import ask, missing, said, unknown
from client.game.mapdb import MapDB
from client.game.profile import load_profile
from client.game.walker import locate, walk

# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Sell the bundle of skins you wear at the nearest tannery:  ;skins

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
anyway. Loose animal parts were sold one at a time from 2026-09-21
(#261: nine loose pelts and seven claws filled the sack; #269 read the
sack with LOOK IN) until the operator ruled bundles only (2026-10-01,
#401): a loose skin may be kept on purpose, and one in the bag says a
hunt could not bundle it — the 22 loose pelts #399's lead rope left
were sold unseen that morning. They are named instead: a skin in a
hand (a hunt whose sack had no room left it there, #262) and each skin
noun LOOK IN the loot container lists (one answer, no roundtime). The
rope is put away by its whole name, `bundling rope` (ROPE, the hunt's):
a bare ROPE takes the first rope of any kind, #399's lead rope first.
No bundle to sell, or a tanner who does not pay, stops it with the
answer echoed. `bank` then runs ;bank through the handle and
waits for it — the banking lives there (#235: the money-changer for
every foreign coin, DEPOSIT ALL, `keep=N` withdrawn back) and ;skins
used to carry a second, poorer copy of its last step (the operator,
2026-09-20: "it should just do ;bank"); a ;bank already running is
the operator's and is left alone, said. Selling and banking stay
distinct ;train tasks: the starter plan runs `{"script": "skins"}` and
then `{"script": "bank"}`, each with no skills, once a cycle after the
hunt. Stops on death.
A Trader's kiosk (Elanthipedia: Prosperity in Absentia, #567) buys a
tied bundle or gem pouch from anyone at the shop value times its
owner's markup, -10% to +80%, in Kronars: GIVE KIOSK quotes, the same
GIVE within 10 seconds sells. Kiosks stand in the Crossing's tannery
most days, one wearing the Iridius crystal cube's look ("a luminescent
Iridius crystal plinth protected by a faceted glass-like dragon", noun
plinth). With one listed, ;skins asks the tanner's quote (ASK FALKEN
TO APPRAISE MY BUNDLE, captured 2026-09-12: "...then whispers, "I can
give 111 Kronars for it."", and the SELL paid 111), TIEs the bundle (a
kiosk takes tied ones only; the tanner pays the same for a tight bundle
and hands its rope back, other players' sales in the logs), GIVEs it to
each kiosk once for a quote, and gives the best one that beats the
tanner's its second GIVE. A gem pouch is never offered: the GIVE names
the bundle. Not captured yet: TIE's answer, the kiosk's quote, sale and
refusal lines, and a short-funded kiosk's part payment — the sale is
read off the hand (the bundle gone), the quote as any coin amount, and
an unread quote is echoed for capture.
Stop with:  ;stop skins
"""

# A bundle that is not there, beyond act.NOT_FOUND's two wordings (GET's,
# captured 2026-09-12): the REMOVE refusals, assumptions until captured.
# REMOVE with nothing of the name worn (captured 2026-10-03, #450): "Remove
# what?" — read as a bundle taken off, it led to "Sell what?".
_NO_BUNDLE = ("aren't wearing", "not wearing", "don't have", "remove what")
# The tanner's payment line, captured 2026-09-12.
_PAID = re.compile(r"hands you (\d+) (\w+)")
# The rope the tanner hands back, named whole: ;hunt's ROPE (#399, a
# bare "rope" is the first rope of any kind — a looted lead rope).
ROPE = "bundling rope"
# Animal parts a hunt cuts — the tanner buys them one at a time too
# ("sell my <bundle/skin/pelt/bones/animal part>", Elanthipedia:
# Falken's Tannery), but only a bundle is sold (#401): a loose one is
# named where it lies.
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
# The tanner's quote, captured 2026-09-12 at Falken's: 'The tanner Falken
# looks the lumpy bundle over carefully, then whispers, "I can give 111
# Kronars for it."' — a bare count is copper, as the SELL's "hands you".
_QUOTE = re.compile(r"I can give (.+?) for it")
_TANNER = re.compile(r"\btanner (\w+)")  # "..., the tanner Falken, ..."
# One amount, the game's shape: "1 gold, 5 silver and 1 bronze Kronars", "111 Kronars".
_AMOUNT = r"[\d,]+ (?:platinum|gold|silver|bronze|copper)"
_COINS = re.compile(
    rf"((?:{_AMOUNT}(?:, and |, | and ))*{_AMOUNT}|[\d,]+) (Kronars|Lirums|Dokoras)"
)
# A Trader's kiosk, or one wearing the Iridius crystal cube's look (a
# plinth); at most six to a room (Elanthipedia: Prosperity in Absentia).
# shortcut: only the two nouns seen in the logs; add a look's noun when one shows.
KIOSK_NOUNS = ("kiosk", "plinth")
_ORDINALS = ("", "second ", "third ", "fourth ", "fifth ", "sixth ")
# LOOK IN MY <container>, no roundtime (captured 2026-09-21, #269): "In
# the canvas sack you see a round cambrinth flake, a nemoih root, ...,
# a nuloe stem and a nuloe stem." — the skin nouns it lists are the
# loose parts named.


def listed_nouns(answer):
    """The nouns a LOOK IN answer lists, repeats kept; None when it is no
    listing, [] for an empty container (items.listed_nouns)."""
    return items.listed_nouns(answer)


def take_bundle(s, container):
    """The bundle into a hand — there already (a run stopped between
    REMOVE and SELL left it there, 2026-09-14), off the body, or out of
    the container; False when there is none any place."""
    if hands.holding(s, "bundle"):
        return True
    # By its INV LIST id first (#456): the listing is from login, so an
    # id the game no longer knows is forgotten and the noun follows.
    worn = items.listed_ref(s, "bundle", worn=True)
    if worn:
        if not missing(ask(s, f"remove {worn}"), _NO_BUNDLE):
            return True
        items.forget(worn)
    if not missing(ask(s, "remove my bundle"), _NO_BUNDLE):
        return True
    carried = items.listed_ref(s, "bundle", worn=False)
    if carried:
        if not missing(ask(s, f"get {carried}"), _NO_BUNDLE):
            return True
        items.forget(carried)
    command = f"get my bundle from my {container}" if container else "get my bundle"
    return not missing(ask(s, command), _NO_BUNDLE)


def hand_to_bank(s, args):
    """Run ;bank with `args` (keep=N) and wait for it to end: the purse's
    banking lives there, not here (the operator, 2026-09-20). False,
    said, when it could not start — one already running is the
    operator's own."""
    if not s.run("bank", list(args)):
        s.echo("skins: could not start ;bank — the purse stays as it is")
        return False
    try:
        while s.is_running("bank"):
            s.sleep(1)
    except BaseException:
        s.kill("bank")  # ;stop skins (or its ;hunt) takes the ;bank with it
        raise
    return True


def kiosks(room_objs):
    """The GIVE target of each kiosk the room lists: "kiosk", "second
    kiosk", ..., "plinth"; [] for none."""
    text = str(room_objs or "").lower()
    return [
        ordinal + noun
        for noun in KIOSK_NOUNS
        for ordinal in _ORDINALS[: len(re.findall(rf"\b{noun}\b", text))]
    ]


def kronars(answer):
    """The copper Kronars of the first amount an answer names — its
    denominations ("2 gold and 5 silver Kronars") or a bare count ("111
    Kronars", copper), another province's coin converted; None for none."""
    found = _COINS.search(str(answer or ""))
    if not found:
        return None
    amount = found.group(1).replace(",", "")
    copper = int(amount) if amount.isdigit() else money.to_copper(amount)
    return money.in_kronars(copper, found.group(2))


def _coin(copper):
    return f"{money.short(copper)} Kronars"


def kiosk_sale(s, tanner):
    """The bundle in hand sold to the room's best kiosk when its quote
    beats `tanner`'s: True, said. False leaves the sale to the tanner,
    said whenever a kiosk was there."""
    targets = kiosks(getattr(s.state, "room_objs", ""))
    if not targets:
        return False
    quote = (
        _QUOTE.search(ask(s, f"ask {tanner} to appraise my bundle")) if tanner else None
    )
    offer = kronars(quote.group(1)) if quote else None
    if offer is None:
        s.echo(
            "skins: no tanner's quote to weigh the kiosk against — selling to the tanner"
        )
        return False
    ask(s, "tie my bundle")  # a kiosk buys tied bundles only; the tanner pays the same
    best, price = None, offer
    for target in targets:
        answer = ask(s, f"give my bundle to {target}")
        quoted = kronars(answer)
        if not hands.holding(s, "bundle"):  # sold on the first GIVE after all
            best, price = target, quoted
            break
        if quoted is None:
            unknown(s, "skins", f"{target} quote", answer)
        elif quoted > price:
            best, price = target, quoted
    if best is None:
        s.echo(
            f"skins: no kiosk beats the tanner's {_coin(offer)} — selling to the tanner"
        )
        return False
    # The second GIVE sells; past the quote's 10 seconds it quotes again.
    for _ in range(2):
        if not hands.holding(s, "bundle"):
            break
        answer = ask(s, f"give my bundle to {best}")
        quoted = kronars(answer)
        if hands.holding(s, "bundle") and quoted is not None and quoted <= offer:
            break  # quoted again below the tanner: its funds ran low
    if hands.holding(s, "bundle"):
        s.echo(
            f"skins: the {best} did not buy — {said(answer)} — selling to the tanner"
        )
        return False
    paid = kronars(answer) or price
    amount = f" for {_coin(paid)}" if paid else ""
    s.echo(
        f"skins: sold the bundle to the {best}{amount} — the tanner offered {_coin(offer)}"
    )
    return True


def sell_bundle(s, container):
    """The bundle sold and the rope kept; False, said, when there was
    none to sell or the tanner did not pay."""
    if not take_bundle(s, container):
        where = f"in your {container}" if container else "in hand"
        s.echo(f"skins: no bundle worn or {where} — nothing to sell")
        return False
    tanner = _TANNER.search(str(getattr(s.state, "room_objs", "") or ""))
    tanner = tanner.group(1).lower() if tanner else None
    if kiosk_sale(s, tanner):
        if not hands.holding(s, "rope"):  # the kiosk kept it; a tanner's is free
            ask(s, f"ask {tanner} for rope")
    else:
        answer = ask(s, "sell my bundle")
        paid = _PAID.search(answer)
        if not paid:
            last = answer.strip().splitlines()[-1] if answer.strip() else "no answer"
            s.echo(f"skins: the tanner did not pay — {last}")
            return False
        s.echo(f"skins: sold the bundle for {paid.group(1)} {paid.group(2)}")
    rope = items.ref(s, "rope") or f"my {ROPE}"  # back in hand: its id (#456)
    ask(s, f"put {rope} in my {container}" if container else f"stow {rope}")
    return True


def name_loose(s, container):
    """The loose animal parts named, never sold (#401): a skin in a hand
    and each skin noun LOOK IN the loot container lists, one line. A
    hunt bundles every skin, so a loose one is kept on purpose or says
    something went wrong (the operator, 2026-10-01). The count."""
    held = [noun for noun in hands.nouns(s) if noun in SKIN_NOUNS]
    present = Counter()
    if container:
        listed = listed_nouns(ask(s, f"look in my {container}")) or []
        present = Counter(noun for noun in listed if noun in SKIN_NOUNS)
    parts = []
    if present:
        counts = ", ".join(f"{count} {noun}(s)" for noun, count in present.items())
        parts.append(f"{counts} loose in the {container}")
    parts += [f"a {noun} in hand" for noun in held]
    if parts:
        s.echo(f"skins: {'; '.join(parts)} — left there; only a bundle is sold")
    return sum(present.values()) + len(held)


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
    if not travel.go(s, set(tanneries), "the tannery", db=mapdb, walk=walk_fn):
        s.echo("skins: could not reach a tannery — stopping")
        return
    if s.dead:
        s.echo("skins: you are dead — stopping")
        return
    sold = sell_bundle(s, container)
    name_loose(s, container)
    if bank and not s.dead:
        # Nothing sold still banks: a hunt's search coins are in the
        # purse either way, and ;bank walks nothing when it is empty.
        hand_to_bank(s, keep)
    if not sold and not bank:
        return
    if back and start is not None and locate(mapdb, s.state) != start:
        if not travel.go(s, {start}, "where you started", db=mapdb, walk=walk_fn):
            s.echo("skins: could not walk back — you are at the tannery")


def main(s):
    run(s, list(s.args), MapDB.load())
