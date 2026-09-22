"""Remedies — the Alchemy craft behind ;remedies (#284): a dried herb
crushed in a mortar into a remedy step by step, each step teaching, and
the society's work orders that pay for the herbs.

Captured 2026-09-22 at the Crossing Alchemy Society on a rank-2 to
rank-7 Paladin with the society's iron mortar and pestle (the first
live remedies; docs/training.md):

- A raw foraged flower crushes into powder ("You poorly crush the
  jadice flower into some jadice powder.", 10 s) and teaches nothing
  (Alchemy stayed 0/34): Pfanston's 2014 shortcut is gone. A dried
  herb from the society is what a remedy starts from.
- The book: READ MY BOOK lists chapters; TURN MY BOOK TO CHAPTER 2
  ("Simple Remedies": page 1 blister cream, 2 moisturizing ointment,
  3 itch salve, 4 wart salve, 5 stomach tonic) or 3 ("External Wound
  Remedies": 1 neck, 2 abdominal, 3 chest, 4 head, 5 back, 6 eye
  salve); TURN MY BOOK TO PAGE N then READ gives the ingredients, and
  they are the page's, not the wiki's: blister cream is "(5) prepared
  herb (pieces per use, known to provide minor external healing over
  the entire body)" — red flowers — "(1) splash of water", "(1)
  prepared herb (pieces total, known to heal external wounds of the
  head)" — nemoih — and "(1) catalyst material"; the head salve is
  five nemoih, water and a catalyst. STUDY MY BOOK: "You now feel
  ready to begin the crafting process." (with "far beyond your
  abilities" at rank 2, "confidently discern most of the design's
  minutiae" at rank 6). The readiness is spent by the next attempt,
  a failed one included: a crush of the wrong herb answered "You
  cannot figure out how to do that.  Perhaps finding suitable
  ingredients and studying some instructions would help." and the
  right herb answered the same until the page was studied again.
- CRUSH MY <herb> IN MY MORTAR WITH MY PESTLE: "With short strokes you
  crush some unfinished blister cream with your pestle." then a
  quality line ("Only once do you slip and poke a finger into the
  mixture.", "Your experience with alchemy is beginning to show in
  the mixing process.", "A poorly-timed sneeze contaminates the
  mixture!") and 9-22 s of roundtime. The requests, each ending "You
  believe you can just pour or put it inside the mortar and continue
  crushing the unfinished remedy inside.": "You need another splash
  of water to continue crafting some unfinished blister cream." (POUR
  MY WATER IN MY MORTAR: "You toss the water into the mortar and mix
  it in thoroughly."), "You need another prepared herb to continue
  crafting ..." (PUT MY NEMOIH IN MY MORTAR: "You vigorously rub the
  nemoih alongside the mortar to scrape some shavings into the
  mixture." — one piece, the stack stays in hand), "You need another
  catalyst material to continue crafting ..." (PUT MY NUGGET IN MY
  MORTAR: the same rub line; a tiny coal nugget is one use and is
  gone). The finish: "Applying the final touches, you complete
  working on some blister cream." ("some dirty nemoih salve" at rank
  2). A CRUSH at a finished remedy: "Interesting thought really...
  but no." A 25-piece stack of the controlling herb is one 5-use
  remedy — the order's unit — so PUT the stack in whole.
- Work orders: GET MY LOGBOOK, ASK LANSHADO FOR EASY REMEDIES WORK
  (he stands in the Tool Shop): "Lanshado shuffles through some notes
  and says, "Alright, this is an order for some blister cream. I need
  2 stacks (5 uses each) finely-crafted, made from any material and
  due in 65 roisaen.  Please complete the items, bundle them with
  your logbook and then give me the logbook to complete this order.
  Good luck!"" and "You seem to recall this item being somewhere in
  chapter 2 of the instruction book." READ MY LOGBOOK: "This logbook
  is tracking a work order requiring you to craft some blister cream
  from any material.  You must bundle and deliver 2 more within the
  next 64 roisaen." / "This work order appears to be complete.  Now
  give it to a crafting trainer within the next 22 roisaen to
  receive payment." / "This logbook is not currently tracking any
  work orders." BUNDLE MY CREAM WITH MY LOGBOOK (the remedy in one
  hand, the logbook in the other): "You notate the cream in the
  logbook then bundle it up for delivery." GIVE MY LOGBOOK TO
  LANSHADO: "You hand Lanshado your logbook and bundled items, and
  are given 1146 Kronars in return." — 686 of dried red flowers and
  two 31-copper nuggets in, at Alchemy 6; asked while an order is
  open, a new one replaces it without penalty. A tiny coal nugget is
  31 Kronars at the Crossing Forging Society's Supplies (map 8775).
- Both hands are the tools': PUT and GET want a free hand ("You need a
  free hand to pick that up."), so the pestle is stowed for every
  fetch, and the mortar before the logbook comes out.

Elanthipedia: Remedies discipline, Remedies products, Crafting (the
first-step table), Work orders; Pfanston's Guide to Remedies for the
herb list. Sources: docs/bibliography.md.
"""

import re

# The apprentice book's recipes as its pages state them (2026-09-22):
# chapter, page, the controlling herb (a 25-piece dried stack per 5-use
# remedy), the second herb the page asks one piece of (or None), the
# finished item's noun. Chapter 2 from the pages read; chapter 3 from
# Remedies products (one herb each).
RECIPES = {
    "blister cream": (2, 1, "flowers", "nemoih", "cream"),
    "moisturizing ointment": (2, 2, "flowers", "plovik", "ointment"),
    "itch salve": (2, 3, "flowers", "jadice", "salve"),
    "wart salve": (2, 4, "flowers", "sufil", "salve"),
    "neck salve": (3, 1, "georin", None, "salve"),
    "abdominal salve": (3, 2, "nilos", None, "salve"),
    "chest salve": (3, 3, "plovik", None, "salve"),
    "head salve": (3, 4, "nemoih", None, "salve"),
    "back salve": (3, 5, "hulnik", None, "salve"),
    "eye salve": (3, 6, "sufil", None, "salve"),
}
# The training default: a chapter-3 salve, one herb the society sells.
SALVES = {name.split()[0]: RECIPES[name] for name in RECIPES if RECIPES[name][0] == 3}
CHAPTER = 3
HERB_SALVE = {spec[2]: salve for salve, spec in SALVES.items()}

# Captured wordings — the outcomes CRUSH's answer is read for, failures
# before successes as probe.classify wants.
NO_INSTRUCTIONS = ("cannot figure out how to do that",)
NEED_WATER = ("need another splash of water", "splash of water to continue")
NEED_HERB = ("need another prepared herb",)
NEED_CATALYST = ("need another catalyst", "catalyst material to continue")
ADDED = ("scrape some shavings",)
FINISHED = ("you complete working on",)
DONE_ALREADY = ("interesting thought really",)
CRUSHED = ("you crush some unfinished", "crush the", "crush some")
AS_CRUSHED = ("as crushed as it is going to get",)
MISSING = ("what were you referring", "could not find", "crush what")
FREE_HAND = ("need a free hand",)
STUDIED = ("feel ready to begin",)
TOO_HARD = ("far beyond your abilities",)
POURED = ("mix it in thoroughly", "toss the water")

CRUSH_OUTCOMES = (
    ("no instructions", NO_INSTRUCTIONS),
    ("missing", MISSING),
    ("free hand", FREE_HAND),
    ("as crushed", AS_CRUSHED),
    ("done already", DONE_ALREADY),
    ("need water", NEED_WATER),
    ("need herb", NEED_HERB),
    ("need catalyst", NEED_CATALYST),
    ("finished", FINISHED),
    ("crushed", CRUSHED),
)

# The work order as the master states it and the logbook tracks it.
ORDER = re.compile(
    r"an order for (?:some |a |an )?(?P<item>[\w' -]+?)\.\s+I need (?P<count>\d+) "
    r"stacks? \(5 uses each\) (?P<quality>[\w-]+),.*?due in (?P<due>\d+) roisaen",
    re.IGNORECASE | re.DOTALL,
)
LOGBOOK_MORE = re.compile(
    r"deliver (\d+) more within the next (\d+) roisaen", re.IGNORECASE
)
LOGBOOK_DONE = ("appears to be complete",)
LOGBOOK_NONE = ("not currently tracking",)
BUNDLED = ("bundle it up for delivery",)
PAID = re.compile(r"are given (\d+) kronars", re.IGNORECASE)
NO_MASTER = ("to whom are you speaking",)
LEVELS = ("easy", "challenging", "hard")
LOGBOOK_ITEM = re.compile(
    r"craft (?:some |a |an )?(?P<item>[\w' -]+?) from any material", re.IGNORECASE
)
ORDER_TRIES = 3  # orders asked for before a run gives up on the master's picks

# The shops that keep an order going (captured 2026-09-22): the Crossing
# Alchemy Society's Supplies (map 8862) sells the dried herbs by the
# 25-piece stack and water by ten splashes, and the Crossing Forging
# Society's Supplies (8775) the coal nugget that is the catalyst — ORDER
# # twice at either, the first quotes ("You can purchase (25 pieces)
# dried red flowers for 343 Kronars.  Just order it again and we'll see
# it done!"), the second buys ("The attendant takes some coins from you
# and hands you (25 pieces) dried red flowers."), into a hand. Hulnik
# and sufil are on no shelf there, so a back or eye salve order is
# asked again. A refusal for want of coin is uncaptured: any answer
# that is not the hand-over ends the purchase, said.
SUPPLIES = "8862"
CATALYST_SHOP = "8775"
CATALOG = {  # noun: (catalog number, Kronars)
    "water": (1, 62),
    "nemoih": (3, 250),
    "plovik": (4, 312),
    "jadice": (5, 375),
    "nilos": (6, 437),
    "georin": (7, 437),
    "flowers": (13, 343),
}
CATALYST_CATALOG = {"nugget": (1, 31)}
QUOTE = re.compile(
    r"you can purchase (?P<item>.+?) for (?P<price>[\d,]+) kronars", re.IGNORECASE
)
BOUGHT = ("takes some coins from you and hands you",)


def parse_args(args):
    """{"salve", "until", "once", "count", "work", "level"} from
    ;remedies' arguments: the salve to train on ("head" by default),
    until= the Alchemy mindstate to stop at (34), `once` to exit at the
    lock, count= remedies (or orders, with work) before ending,
    `work [easy|challenging|hard]` for the society's orders instead of
    the training loop."""
    options = {
        "salve": "head",
        "until": 34,
        "once": False,
        "count": 0,
        "work": False,
        "level": "easy",
    }
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "salve" and value in SALVES:
            options["salve"] = value
        elif not sep and key in SALVES:
            options["salve"] = key
        elif sep and key == "until" and value.isdigit():
            options["until"] = int(value)
        elif sep and key == "count" and value.isdigit():
            options["count"] = int(value)
        elif key == "once":
            options["once"] = True
        elif key == "work":
            options["work"] = True
        elif key in LEVELS:
            options["level"] = key
    return options


def recipe(name):
    """(chapter, page, herb, extra herb or None, noun) for an item as
    the master or the book names it ("some blister cream"), None for
    one the book has no page for."""
    key = re.sub(r"^(?:some|a|an)\s+", "", str(name or "").strip().lower())
    return RECIPES.get(key)


def herb_for(salve):
    """The dried herb a chapter-3 salve wants: "nemoih" for the head."""
    return SALVES[salve][2]


def page_for(salve):
    return SALVES[salve][1]


def crush_command(herb, started, noun="salve"):
    """CRUSH the herb the first time, the unfinished remedy — by its
    noun, "salve" or "cream" — after."""
    what = noun if started else herb
    return f"crush my {what} in my mortar with my pestle"


def parse_order(text):
    """{"item", "count", "quality", "due"} from the master's answer, or
    None when it holds no order."""
    match = ORDER.search(text or "")
    if not match:
        return None
    return {
        "item": match.group("item").strip().lower(),
        "count": int(match.group("count")),
        "quality": match.group("quality").lower(),
        "due": int(match.group("due")),
    }


def parse_logbook(text):
    """("none" | "open" | "done", remaining, roisaen) from READ MY
    LOGBOOK."""
    lowered = (text or "").lower()
    if any(word in lowered for word in LOGBOOK_DONE):
        due = re.search(r"within the next (\d+) roisaen", lowered)
        return "done", 0, int(due.group(1)) if due else None
    match = LOGBOOK_MORE.search(lowered)
    if match:
        return "open", int(match.group(1)), int(match.group(2))
    return "none", 0, None


def payment(text):
    """The Kronars a GIVE of the logbook earned, or None."""
    match = PAID.search(text or "")
    return int(match.group(1)) if match else None


def logbook_item(text):
    """The item an open order in READ MY LOGBOOK tracks ("blister
    cream"), or None — a run resumes the order it left in the logbook
    rather than asking for a new one."""
    match = LOGBOOK_ITEM.search(text or "")
    return match.group("item").strip().lower() if match else None


def sellable(spec):
    """True when every herb the recipe wants is on the society's
    Supplies shelves — an order for one that is not is asked again."""
    chapter, page, herb, extra, noun = spec
    return herb in CATALOG and (extra is None or extra in CATALOG)


def quote(text):
    """(item, Kronars) from the shop's ORDER quote, or None."""
    match = QUOTE.search(text or "")
    if not match:
        return None
    return match.group("item").strip().lower(), int(
        match.group("price").replace(",", "")
    )


def shortage(why, spec, catalyst):
    """What a craft that ended on `why` ran out of, as (noun, per
    stack, shop, catalog) — the controlling herb a stack per remedy,
    the second herb one stack for many, water ten splashes at a time,
    the catalyst one per remedy — or None when `why` is not a
    shortage."""
    chapter, page, herb, extra, noun = spec
    if why == f"dried {herb}":
        return herb, 1, SUPPLIES, CATALOG
    if extra and why == f"dried {extra}":
        return extra, 0, SUPPLIES, CATALOG
    if why == "water":
        return "water", 0, SUPPLIES, CATALOG
    if catalyst and why == catalyst:
        return catalyst, 1, CATALYST_SHOP, CATALYST_CATALOG
    return None
