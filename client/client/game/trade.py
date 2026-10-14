"""Trader caravan contracts (;trade, #552): the Zoluren outposts, the
contract's text, and the minister's, clerk's and driver's answers —
;trade's model, Qt-free.

A leg: at the outpost's clerk the contract for this town is handed in
and paid for, PAY CLERK settles the dues, ASK MINISTER FOR CONTRACT
issues the next one (its wholesale price is charged as dues to this
town), GIVE MY CONTRACT TO CLERK loads its crate on the caravan, the
caravan is fed from the feedbag (REMOVE, GIVE <caravan>, WEAR), and
TELL <caravan> TO LEAD TO <town> has the driver lead the character
there. Captured 2026-10-15 on a Crossing → Wolf Clan contract
(docs/trade.md); the rooms are dr-scripts' data/base-town.yaml, the
procedure and the uncaptured wordings its trade.lic.
"""

import re
from collections import namedtuple

from client.game import money

Town = namedtuple("Town", "outpost minister clerk")

# The outposts a caravan reaches by LEAD TO with no ferry or gondola:
# map ids of the outpost (where the caravan waits), the trade minister
# and the shipment clerk (dr-scripts' base-town.yaml).
TOWNS = {
    "Crossing": Town(895, 8915, 8916),
    "Arthe Dale": Town(1073, 8999, 8999),
    "Stone Clan": Town(1169, 8996, 8996),
    "Dirge": Town(1307, 15175, 8919),
    "Wolf Clan": Town(1533, 8997, 8997),
    "Tiger Clan": Town(1885, 1889, 1889),
}

_COIN = r"(\d+) (Kronars|Lirums|Dokoras)"

# ASK MINISTER FOR CONTRACT: "The minister plucks a contract from the
# hands of a passing clerk and hands it to you. "Here we go," she says,
# "We have charged you the wholesale price of 3537 Kronars for the
# goods, ... Also I will charge you 985 in dues which are owed to this
# guild, for a total of 4522."" With dues owed: "The minister reminds
# you that you still owe 2375 Kronars in dues to The Crossing and asks
# that you pay the clerk before she issues you a new contract."
ISSUED = "plucks a contract"
HELD = "You still have another contract"  # trade.lic's wording
_OWED = re.compile(r"still owe " + _COIN + " in dues", re.I)
_WHOLESALE = re.compile(r"wholesale price of " + _COIN, re.I)
_DUES = re.compile(r"charge you (\d+) in dues", re.I)

# PAY CLERK: "You count out some coins, and the clerk notes that your
# dues are settled." The rest are trade.lic's.
SETTLED = ("dues are settled", "You do not owe dues")
PART_PAID = "your dues are now"
NO_COINS = "don't have any coins on you to pay dues"

# GIVE MY CONTRACT TO CLERK opens the same way at both ends: "The
# shipment clerk accepts your contract and peruses it." Loading goes on:
# "... a pair of assistants carefully lift the crate and carry it out
# the door ... "Okay...total fee for transportation additions is 50
# copper Kronars."" Delivery: "The shipment clerk finds everything in
# order with your merchandise. "You're a good Trader, Lanival." he says,
# handing you your payment of 11791 Kronars."
ACCEPTED = "accepts your contract"
LOADED = "transportation additions"
_FEE = re.compile(r"transportation additions is (.+?)\.", re.I)
TOO_HEAVY = "this load would kill"  # trade.lic: a pack animal needs a caravan
DELIVERED = "finds everything in order"
_PAID = re.compile(r"your payment of " + _COIN, re.I)
NO_GOODS = "What have you done with the goods"  # trade.lic

# Feeding: "The driver takes the feedbag from you and begins feeding the
# caravan. The driver hands back the feedbag and says, "They are well
# fed now sir."" A fed animal sniffs at it (trade.lic).
FED = ("takes the feedbag from you", "munches away happily")
NOT_HUNGRY = "sniffs disinterestedly"
_GRASS = re.compile(r"\bsome grass\b", re.I)

# TELL <caravan> TO LEAD TO WOLF CLAN: "The driver of your bullock-drawn
# caravan acknowledges the order to lead to Wolf Clan." Then the caravan
# moves and the character follows it room by room; at the end: "The
# bullock-drawn caravan stops and waits, having arrived at its
# destination." (3½ minutes from the Crossing's Commerce Avenue to Wolf
# Clan's outpost.) The refusals, the guide's surrender and the follow
# line are trade.lic's.
LEADING = "acknowledges the order to lead"
LEAD_REFUSED = ("but turns back and says", "looks at you confused")
ARRIVED = "having arrived at its destination"
LEAD_FAILED = "Your caravan guide comes to you and suggests"
FOLLOWING = "following you"  # "Your bullock-drawn caravan, following you, ..."
FOLLOW_ORDERED = ("make it follow", "order to follow")
WAIT_ORDERED = ("make it wait", "order to wait")

# RECALL CARAVAN: "You recall that your bullock-drawn caravan should be
# located in..." and the room; "You seem to recall that you left your
# ... right behind you" when it is here (trade.lic).
_RECALLED = re.compile(r"recall (?:that )?your (.+?) should be located", re.I)
_BEHIND = re.compile(r"you left your (.+?) right behind you", re.I)
NO_CARAVAN = ("don't recall having a caravan", "don't recall where you left")

Contract = namedtuple(
    "Contract", "origin destination goods worth currency presented expired"
)
_ORIGIN = re.compile(r"Trading Contract Issued by:\s+(?:The )?(.+?)\s*$", re.M)
_DESTINATION = re.compile(
    r"The guild office at (?:The )?(.+?) requires (.+?),?\s*$", re.M
)
_WORTH = re.compile(r"worth " + _COIN + " on delivery", re.I)


def contract(text):
    """READ MY CONTRACT's answer as a Contract, or None with no contract
    in it:

     Trading Contract Issued by:  Crossing
     The guild office at Wolf Clan requires 13 ornate saber hilts,
     ...
     This contract has yet to be presented to the Crossing guild
     clerk.
    You estimate these goods are currently worth 11791 Kronars on delivery.
    """
    text = str(text or "")
    destination = _DESTINATION.search(text)
    if not destination:
        return None
    origin = _ORIGIN.search(text)
    worth = _WORTH.search(text)
    return Contract(
        origin=origin.group(1) if origin else None,
        destination=destination.group(1),
        goods=destination.group(2),
        worth=int(worth.group(1)) if worth else None,
        currency=worth.group(2) if worth else None,
        presented="has yet to be presented" not in text,
        expired="has expired" in text,
    )


def minister(answer):
    """ASK MINISTER FOR CONTRACT's answer: ("issued", (wholesale, dues))
    in copper, ("dues", copper owed), ("held", None), or (None, None)."""
    text = str(answer or "")
    if ISSUED in text:
        wholesale = _WHOLESALE.search(text)
        dues = _DUES.search(text)
        return "issued", (
            int(wholesale.group(1)) if wholesale else None,
            int(dues.group(1)) if dues else None,
        )
    owed = _OWED.search(text)
    if owed:
        return "dues", int(owed.group(1))
    if HELD in text:
        return "held", None
    return None, None


def clerk(answer):
    """GIVE MY CONTRACT TO CLERK's answer: ("loaded", fee in copper),
    ("paid", (copper, currency)), ("no goods", None), ("too heavy",
    None) or (None, None)."""
    text = str(answer or "")
    if DELIVERED in text:
        paid = _PAID.search(text)
        return "paid", (int(paid.group(1)), paid.group(2)) if paid else (None, None)
    if LOADED in text:
        fee = _FEE.search(text)
        return "loaded", money.to_copper(fee.group(1)) if fee else None
    if NO_GOODS in text:
        return "no goods", None
    if TOO_HEAVY in text:
        return "too heavy", None
    return None, None


def caravan(answer):
    """RECALL CARAVAN's answer: (its name, here) — ("bullock-drawn
    caravan", False) when it waits elsewhere — or (None, False)."""
    text = str(answer or "")
    behind = _BEHIND.search(text)
    if behind:
        return behind.group(1), True
    recalled = _RECALLED.search(text)
    if recalled:
        return recalled.group(1), False
    return None, False


def grass(answer):
    """How many bunches of grass LOOK IN MY FEEDBAG lists."""
    return len(_GRASS.findall(str(answer or "")))


def town(name):
    """The TOWNS key a contract or an answer names ("The Crossing" ->
    "Crossing"), or None for a town ;trade does not lead to."""
    name = re.sub(r"^the\s+", "", str(name or "").strip(), flags=re.I).lower()
    for key in TOWNS:
        if key.lower() == name:
            return key
    return None


def contract_noun(name):
    """How GET names a town's contract: its first word ("get my wolf
    contract" for the Wolf Clan contract), trade.lic's way."""
    return f"{str(name).split()[0].lower()} contract"
