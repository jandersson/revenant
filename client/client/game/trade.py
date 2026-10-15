"""Trader caravan contracts (;trade, #552): the outposts of Zoluren,
Ilithi and Riverhaven, the contract's text, and the minister's, clerk's
and driver's answers — ;trade's model, Qt-free.

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

# Zoluren's outposts: map ids of the outpost (where the caravan waits),
# the trade minister and the shipment clerk (dr-scripts' base-town.yaml).
TOWNS = {
    "Crossing": Town(895, 8915, 8916),
    "Arthe Dale": Town(1073, 8999, 8999),
    "Stone Clan": Town(1169, 8996, 8996),
    "Dirge": Town(1307, 15175, 8919),
    "Wolf Clan": Town(1533, 8997, 8997),
    "Tiger Clan": Town(1885, 1889, 1889),
    "Leth Deriel": Town(2039, 9004, 9004),
    # Ilithi: Shard's outpost is Brickwell Tower's courtyard. Elanthipedia's
    # Trade Route puts the leads between Shard's East Bridge and Derelict
    # Road, Whistling Wood, "nowhere near the Darkling Wood outpost", so
    # that stretch is walked with the caravan following.
    "Shard": Town(8191, 8197, 8193),
    "Fayrin's Rest": Town(2840, 19278, 19278),
    "Steelclaw Clan": Town(2874, 19399, 19399),
    "Darkling Wood": Town(2702, 14636, 14636),
    # Therengia: Riverhaven's outpost is Town Hall Road, the clerk down
    # its alley; the rest of the province waits (#555).
    "Riverhaven": Town(386, 7876, 13751),
}
ILITHI = ("Shard", "Fayrin's Rest", "Steelclaw Clan", "Darkling Wood")
THERENGIA = ("Riverhaven",)

# Leth Deriel is across the Segoltha: the caravan is walked from the
# Crossing's outpost onto Alfren's Ferry and off at the south bank,
# following the character aboard ("Your weathered caravan arrived at
# the ferry Hodierna's Grace, following you."; the captain: "Only a
# small transportation fee of 77 kronars for your goods today"), then
# led on as LEAD TO LETH ("acknowledges the order to lead to Leth
# Deriel"). Captured 2026-10-15; trade.lic's do_lead_to the way.
ACROSS = "Leth Deriel"
FERRY_SOUTH = 1904  # Southern Trade Route, Segoltha South Bank
LEAD_NAMES = {"Leth Deriel": "leth", "Darkling Wood": "darkling"}  # trade.lic's

# Riverhaven is across the Faldesu from Zoluren, driven by hand on
# 2026-10-15 (#555): LEAD TO DIRGE ends at Gateway Road, LEAD TO
# RIVERHAVEN from there at North Road, Ferry, and the caravan follows
# aboard the ferry ("came through the ferry His Daring Exploit,
# following you") and off at Riverhaven's dock; the captain wants
# Lirums ("a transportation fee of 152 lirums" for the character and
# 260 jars of eel) and refuses without them ("You haven't got enough
# lirums to pay for your trip."). Back, a lead to Dirge starts one room
# south of the north-road dock (Elanthipedia: Trade Route).
VIA_DIRGE = "Dirge"
RIVERBANK = 1384  # North Road, Riverbank
FALDESU_LIRUMS = 500  # copper on hand for the ferry, a margin over 152

_COIN = r"(\d+) (Kronars|Lirums|Dokoras)"

# ASK MINISTER FOR CONTRACT: "The minister plucks a contract from the
# hands of a passing clerk and hands it to you. "Here we go," she says,
# "We have charged you the wholesale price of 3537 Kronars for the
# goods, ... Also I will charge you 985 in dues which are owed to this
# guild, for a total of 4522."" With dues owed: "The minister reminds
# you that you still owe 2375 Kronars in dues to The Crossing and asks
# that you pay the clerk before she issues you a new contract."
#
# The broker, ASK BROKER FOR CONTRACT, issues a contract for another
# province in the same words ("The broker plucks a contract ...", "The
# broker reminds you that you still owe 4048 Kronars in dues ...", the
# Crossing, 2026-10-15; Shard's Provincial Broker the same that afternoon).
BROKERS = {"Crossing": 11995, "Shard": 14305}
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
# fed now sir."" Not hungry, ten legs of seventeen on 2026-10-15: "You
# offer the tan canvas feedbag to the caravan driver. He calls over to
# you, "Nope, they are all set for now."" The other two are trade.lic's.
FED = ("takes the feedbag from you", "munches away happily")
NOT_HUNGRY = ("they are all set for now", "sniffs disinterestedly")
_GRASS = re.compile(r"\bsome grass\b", re.I)

# FORAGE GRASS (the game logs since 2026-08): "You manage to find some
# grass." puts it in a hand; a miss is "You forage around but are unable
# to find anything." or the dragon's-egg line, a few seconds' roundtime.
GRASS_FOUND = "find some grass"
FORAGE_BLOCKED = ("at least one hand free", "too cluttered", "futile")

# TELL <caravan> TO LEAD TO WOLF CLAN: "You pass on the order to lead to
# your driver, who makes sure your bullock-drawn caravan does your
# bidding." — after "The driver of your bullock-drawn caravan
# acknowledges the order to lead to Wolf Clan." to Wolf Clan, alone to
# Arthe Dale (2026-10-15: the first live ;trade took that for a refusal
# and the caravan led off without it). Then the caravan moves and the
# character follows it room by room; at the end: "The bullock-drawn
# caravan stops and waits, having arrived at its destination." (3½
# minutes from the Crossing's Commerce Avenue to Wolf Clan's outpost.)
# The refusals, the guide's surrender and the follow line are trade.lic's.
LEADING = "You pass on the order to lead"
LEAD_REFUSED = ("but turns back and says", "looks at you confused")
ARRIVED = "having arrived at its destination"
LEAD_FAILED = "Your caravan guide comes to you and suggests"
FOLLOWING = "following you"  # "Your bullock-drawn caravan, following you, ..."
FOLLOW_ORDERED = ("make it follow", "order to follow")
WAIT_ORDERED = ("make it wait", "order to wait")

# RECALL CARAVAN: "You recall that your bullock-drawn caravan should be
# located in..." and the room; nearby, "You seem to recall your
# bullock-drawn caravan should be somewhere to the east." (a ;trade at
# Arthe Dale's clerk took that for no caravan, 2026-10-15); "You seem to
# recall that you left your ... right behind you" when it is here
# (trade.lic).
_RECALLED = re.compile(r"recall (?:that )?your (.+?) should be\b", re.I)
_BEHIND = re.compile(r"you left your (.+?) right behind you", re.I)
NO_CARAVAN = ("don't recall having a caravan", "don't recall where you left")

# The storage box (35th circle and up): OPEN STORAGE BOX ON <caravan>,
# then RUMMAGE IN STORAGE BOX ON <caravan>: "You rummage through a
# storage box but there is nothing in there." Closed, the RUMMAGE answers
# "While it's closed?" RETURN CARAVAN at a shipment clerk: "... everything
# appears to be in order with your caravan, so you're free to go now. ..."
# As the clerk makes note of your return, another worker goes outside to
# retrieve your caravan." Captured at Stone Clan, 2026-10-15.
BOX_EMPTY = "there is nothing in there"

# RENT CARAVAN at a shipment clerk, the Crossing, 2026-10-14: "The clerk
# nods and says, "All right, that's a 400 Kronars fee for a rental....""
# then "You count out your 400 Kronars and pay the clerk, who sends his
# assistant out to get your transportation together." The caravan waits
# at the outpost. Short: "You attempt to pay the clerk, but you don't have
# enough money. ... "Sorry, can't put it in your dues. Ya gotta pay up
# front."" (Elanthipedia: Trader, 400 Kronars at any Zoluren outpost.)
# Shard's clerk, 2026-10-15: "that's a 288 Dokoras fee for a rental".
# Riverhaven's is assumed: 400 Kronars at the wiki's rate, as Shard's is.
RENT_FEE = {"Kronars": 400, "Dokoras": 288, "Lirums": 320}
RENTED = "get your transportation together"
RENT_SHORT = "don't have enough money"
RETURNED = ("free to go now", "retrieve your caravan")

Contract = namedtuple(
    "Contract", "origin destination goods worth currency presented expired"
)
# Read with its whitespace collapsed: the familiar stream's lines reached
# the script without their breaks, and the origin ran on into the next
# line (2026-10-15: a contract issued and never loaded was led off
# unloaded). Each field ends at the next one's words instead.
_ORIGIN = re.compile(r"Issued by: (?:The )?(.+?) The guild office at")
_DESTINATION = re.compile(r"The guild office at (?:The )?(.+?) requires (.+?), to be")
_WORTH = re.compile(r"worth " + _COIN + " on delivery", re.I)
# READ pushes the contract to the familiar stream (<pushStream
# id="familiar">); its last line is the estimate.
READ_END = "on delivery"


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
    text = re.sub(r"\s+", " ", str(text or ""))
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
    """ASK MINISTER (or BROKER) FOR CONTRACT's answer: ("issued",
    (wholesale, dues)) in copper, ("dues", copper owed), ("held", None),
    or (None, None)."""
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
    caravan", False) when it waits elsewhere — or (None, False). The
    name is the first word and the noun: GIVE POLISHED WOOD CARAVAN
    answered "What is it you're trying to give?" (Steelclaw Clan,
    2026-10-15; an item is ADJECTIVE NOUN, act.py), trade.lic's way."""
    text = str(answer or "")
    behind = _BEHIND.search(text)
    recalled = _RECALLED.search(text)
    found = behind or recalled
    if not found:
        return None, False
    words = found.group(1).split()
    name = " ".join((words[0], words[-1])) if len(words) > 2 else " ".join(words)
    return name, behind is not None


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


def coin(name):
    """The coin a town's minister charges and its clerk pays: Dokoras in
    Ilithi, Lirums in Therengia, Kronars in Zoluren."""
    if name in ILITHI:
        return "Dokoras"
    return "Lirums" if name in THERENGIA else "Kronars"


def lead_name(name):
    """The words LEAD TO takes for a town: "leth" for Leth Deriel
    (trade.lic's), else its name."""
    return LEAD_NAMES.get(name, str(name).lower())


def contract_noun(name):
    """How GET names a town's contract: its first word ("get my wolf
    contract" for the Wolf Clan contract), trade.lic's way."""
    return f"{str(name).split()[0].lower()} contract"
