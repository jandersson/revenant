"""The Traders' commodity pits (;commodities, #557): the three boards,
the pit clerk's ORDER, the shipment clerk's SELL, and the plan — the
good to buy here and the pit to carry it to — ;commodities' model,
Qt-free.

A trade: READ BOARD in a pit, ORDER <n> <good> at its pit clerk (the
price per unit plus the guild's cut of about 3%, from the purse), the
goods go onto a pack animal the guild lends at the town's outpost, the
animal is walked to another pit's town (TELL <animal> TO FOLLOW, room by
room), and SELL <n> <good> at that town's shipment clerk pays the board
price, no cut. Captured by hand on 2026-10-15 (5 saffron, Leth Deriel to
the Crossing; 50 diamonds, the Crossing to Arthe Dale); the stock bands
are Elanthipedia's Commodity Trading table.
"""

import math
import re
from collections import namedtuple

# Each pit's room; its town's shipment clerk and outpost (where the
# animal waits, it will not come indoors) are trade.TOWNS'.
PITS = {
    "Crossing": 19275,  # [Traders' Guild, The Pit], south of the Shipment Center
    "Arthe Dale": 9000,  # [Swotting Hall, Trader's Pit], west of the Trader's Center
    "Leth Deriel": 13550,  # [Eshar's Trading Post, The Pit], west of the Main Room
}

SURPLUS = "Surplus!"
GOOD_STORES = "Good Stores"
GOING_FAST = "Going Fast"
NEARLY_OUT = "Nearly Out!"
SOLD_OUT = "*SOLD OUT!*"
STOCK = (SURPLUS, GOOD_STORES, GOING_FAST, NEARLY_OUT, SOLD_OUT)

# The lowest unit count of Going Fast, Good Stores and Surplus for each
# good (Elanthipedia: Commodity Trading, "currently off"); Nearly Out
# starts at 1. Copper's Surplus reads 80-100 there under a Good Stores of
# 126-199: 200 here. Diamonds bear it out: 50 sold into Arthe Dale's
# Good Stores read Surplus! after (2026-10-15).
BANDS = {
    "diamonds": (10, 50, 80),
    "gold": (10, 50, 80),
    "silver": (20, 100, 160),
    "saffron": (7, 46, 77),
    "pearls": (10, 50, 80),
    "silk": (8, 50, 79),
    "brass": (15, 75, 120),
    "cinnamon": (16, 100, 156),
    "slate": (18, 100, 158),
    "limes": (8, 49, 78),
    "purple dye": (8, 48, 80),
    "bronze": (11, 62, 100),
    "oranges": (16, 97, 158),
    "lead": (28, 151, 240),
    "velvet": (8, 48, 80),
    "lace": (8, 48, 80),
    "taffelberries": (16, 98, 156),  # the wiki's "Taffleberries"
    "amber": (33, 164, 232),
    "copper": (23, 126, 200),
    "acanth": (19, 98, 159),
    "myrrh": (10, 61, 98),
    "indigo": (18, 98, 158),
    "papyrus": (15, 75, 120),
    "iron ore": (49, 267, 377),
    "barley": (37, 210, 318),
    "oats": (32, 175, 276),
    "wool": (39, 203, 319),
    "wheat": (37, 213, 317),
    "corn": (30, 243, 307),
    "deobar oil": (23, 126, 200),
    "cotton": (50, 249, 400),
    "salt": (50, 262, 417),
    "apples": (32, 184, 278),
    "charcoal": (71, 386, 558),
}
# The guild's cut on an ORDER: 99 on 3,520 (2.8%) and 2,712 on 84,250
# (3.2%), 2026-10-15; a margin over both.
CUT = 0.035
MIN_PROFIT = 2000  # copper Kronars a trade must clear to be worth the walk

Board = namedtuple("Board", "town goods")  # goods: {good: (price, stock word)}
Plan = namedtuple("Plan", "good units buy sell bought sold profit")

# READ BOARD pushes the board to the familiar stream, like a contract:
#            The Crossing Trader Guild Commodity Pit Board
# Commodity       Price   Units         Commodity       Price   Units
# -------------------------------------------------------------------------
# Diamonds        1685  Good Stores     Pearls          725   Good Stores
# Iron ore        77    Surplus!        Charcoal        49    Nearly Out!
# The familiar lines may reach a script without their breaks (a
# contract's did, 2026-10-15), so a row is read by its fields alone.
_TITLE = re.compile(
    r"(?:The )?(" + "|".join(PITS) + r") Trader Guild Commodity Pit Board"
)
_ROW = re.compile(
    r"([A-Z][a-z]+(?: [a-z]+)?) +(\d+) +("
    + "|".join(re.escape(word) for word in STOCK)
    + ")"
)
# ORDER 50 DIAMONDS: "The clerk nods as he checks out your order.  He
# accepts your payment of 84250 Kronars plus the usual cut of 2712 to
# the guild, bringing the total to 86962.  He nods to his assistants,
# who start to pack up your purchases." Then the animal: "We're going to
# give you Tosspot to haul your things.  She's waiting outside the
# shipping office, ..." or, one already lent, "The clerk nod in approval
# at your a lumbering auroch."; "There's a 25 copper kronar fee for the
# transportation additions." ORDER alone: "To purchase goods, ORDER
# <amount> <commodity>. ..."
_ORDER = re.compile(r"payment of (\d+) Kronars plus the usual cut of (\d+)", re.I)
# SELL 50 DIAMONDS at the shipment clerk: "The clerk looks over a
# clipboard on which he has the latest buying prices for the town.
# "Well, Lanival," he nods, "I can pay you 96950 kronars for your
# pouches of diamonds at this time.  So, here you go."" At the pit
# clerk: "I could not find what you were referring to."
_SALE = re.compile(r"I can pay you (\d+) kronars for your", re.I)


def board(text):
    """READ BOARD's answer as a Board (the town as PITS names it, each
    good lowercased to its (price, stock word)), or None with no board
    in it."""
    text = str(text or "")
    title = _TITLE.search(text)
    if not title:
        return None
    goods = {
        good.lower(): (int(price), stock)
        for good, price, stock in _ROW.findall(text[title.end() :])
    }
    return Board(title.group(1), goods)


def order(answer):
    """The pit clerk's answer to ORDER: (price, cut) in copper Kronars,
    or None when it bought nothing."""
    found = _ORDER.search(str(answer or ""))
    return (int(found.group(1)), int(found.group(2))) if found else None


def sale(answer):
    """The shipment clerk's answer to SELL: the copper Kronars paid, or
    None when it bought nothing."""
    found = _SALE.search(str(answer or ""))
    return int(found.group(1)) if found else None


def held(good, stock):
    """The units a pit surely holds of `good` at that stock word: its
    band's lowest count (0 sold out or for a good with no bands)."""
    bands = BANDS.get(good)
    if bands is None or stock == SOLD_OUT:
        return 0
    if stock == NEARLY_OUT:
        return 1
    return bands[(GOING_FAST, GOOD_STORES, SURPLUS).index(stock)]


def room(good, stock):
    """The units a pit can take of `good` and stay short of Surplus,
    counting from its band's lowest: a pit with a surplus buys none (the
    Trader Novice Guide). A pit higher in its band than that tips over;
    the 50 diamonds that did were all paid at the board price."""
    bands = BANDS.get(good)
    if bands is None or stock == SURPLUS:
        return 0
    return max(0, bands[2] - 1 - held(good, stock))


def cost(price, units):
    """An ORDER's estimated total: the units at `price` and the cut."""
    return math.ceil(price * units * (1 + CUT))


def plan(boards, here):
    """The best trade from the pit `here` against the other boards
    ({town: {good: (price, stock)}}): a Plan — the good, the units (what
    `here` surely holds, what the buyer takes short of Surplus), the
    towns, the estimated total paid and sold for, the profit — or None
    with none clearing MIN_PROFIT."""
    best = None
    for good, (price, stock) in boards.get(here, {}).items():
        for town, goods in boards.items():
            if town == here or good not in goods:
                continue
            bid, bid_stock = goods[good]
            units = min(held(good, stock), room(good, bid_stock))
            if units <= 0:
                continue
            bought, sold = cost(price, units), bid * units
            if best is None or sold - bought > best.profit:
                best = Plan(good, units, here, town, bought, sold, sold - bought)
    return best if best is not None and best.profit >= MIN_PROFIT else None
