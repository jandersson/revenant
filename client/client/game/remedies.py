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
  it in thoroughly."; the moisturizing ointment asks "another splash
  of alcohol" instead, 2026-10-03, and the grain alcohol is POURed
  alike), "You need another prepared herb to continue
  crafting ..." (PUT MY NEMOIH IN MY MORTAR: "You vigorously rub the
  nemoih alongside the mortar to scrape some shavings into the
  mixture." — one piece, the stack stays in hand), "You need another
  catalyst material to continue crafting ..." (PUT MY NUGGET IN MY
  MORTAR: the same rub line; a rub takes one volume of the nugget —
  a tiny one is gone, a massive one (10) lasts ten, COUNT MY NUGGET
  says how many are left). The finish: "Applying the final touches, you complete
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
  open, a new one replaces it without penalty. The catalyst is a
  massive coal nugget, 212 Kronars for ten rubs at the Crossing Forging
  Society's Supplies (map 8775, item 2); the tiny one there is 31 for
  one rub (item 1).
- Both hands are the tools': PUT and GET want a free hand ("You need a
  free hand to pick that up."), so the pestle is stowed for every
  fetch, and the mortar before the logbook comes out.

Elanthipedia: Remedies discipline, Remedies products, Crafting (the
first-step table), Work orders; Pfanston's Guide to Remedies for the
herb list. Sources: docs/bibliography.md.
"""

import re

from client.game import items, shop

# The apprentice book's recipes as its pages state them (2026-09-22):
# chapter, page, the controlling herb (a 25-piece dried stack per 5-use
# remedy), the second herb the page asks one piece of (or None), the
# finished item's noun, the liquid. Chapter 2 from the pages read;
# chapter 3 from Remedies products (one herb each). The moisturizing
# ointment wants alcohol, not water (#427): "You need another splash
# of alcohol to continue crafting some unfinished moisturizing
# ointment." (captured 2026-10-03), as Remedies products lists it.
RECIPES = {
    "blister cream": (2, 1, "flowers", "nemoih", "cream", "water"),
    "moisturizing ointment": (2, 2, "flowers", "plovik", "ointment", "alcohol"),
    "itch salve": (2, 3, "flowers", "jadice", "salve", "water"),
    "wart salve": (2, 4, "flowers", "sufil", "salve", "water"),
    "neck salve": (3, 1, "georin", None, "salve", "water"),
    "abdominal salve": (3, 2, "nilos", None, "salve", "water"),
    "chest salve": (3, 3, "plovik", None, "salve", "water"),
    "head salve": (3, 4, "nemoih", None, "salve", "water"),
    "back salve": (3, 5, "hulnik", None, "salve", "water"),
    "eye salve": (3, 6, "sufil", None, "salve", "water"),
}
LIQUIDS = ("water", "alcohol")
# The training default: a chapter-3 salve, one herb the society sells.
SALVES = {name.split()[0]: RECIPES[name] for name in RECIPES if RECIPES[name][0] == 3}
CHAPTER = 3
HERB_SALVE = {spec[2]: salve for salve, spec in SALVES.items()}

# Captured wordings — the outcomes CRUSH's answer is read for, failures
# before successes as probe.classify wants.
NO_INSTRUCTIONS = ("cannot figure out how to do that",)
NEED_WATER = ("need another splash of water", "splash of water to continue")
NEED_ALCOHOL = ("need another splash of alcohol", "splash of alcohol to continue")
NEED_HERB = ("need another prepared herb",)
NEED_CATALYST = ("need another catalyst", "catalyst material to continue")
ADDED = ("scrape some shavings",)
FINISHED = ("you complete working on",)
DONE_ALREADY = ("interesting thought really",)
# The rank line can close a crush's window on its own (2026-09-22): a
# rank gained is a crush that taught.
CRUSHED = (
    "you crush some unfinished",
    "crush the",
    "crush some",
    "gained a new rank",
)
AS_CRUSHED = ("as crushed as it is going to get",)
MISSING = ("what were you referring", "could not find", "crush what")
FREE_HAND = ("need a free hand",)
STUDIED = ("feel ready to begin",)
TOO_HARD = ("far beyond your abilities",)
POURED = ("mix it in thoroughly", "toss the water")
# The mortar already holds another remedy in progress (2026-09-23: a
# run that ended on a missing catalyst left a nemoih salve in it, and
# the next order's flowers were refused — "You realize the red flowers
# is not required to continue crafting the nemoih salve, so you
# stop." — until the script spun on Crush what?).
MORTAR_BUSY = ("not required to continue crafting",)
# The mortar measures the herb itself (captured 2026-09-28 on a
# 37-piece stack of pressed and bought red flowers, #370): "The mortar
# can only hold 25 pieces of material.  So you count off and place only
# that many inside." — the rest stays in hand and is stowed. A smaller
# stack makes a smaller remedy (6 pieces made a 1-use cream), which the
# order refuses: "...you notice the workorder calls for stacks of 5 for
# each remedy, and think it best to mark and cut the remedy down to the
# required size before bundling." (below). So a stack short of STACK_PIECES is
# combined with the herb's other stacks first ("You combine the stacks
# of herbs together."), and bought when they are not enough.
MORTAR_FULL = ("can only hold",)
# A herb ;forage herb can gather instead of the Supplies (#370): the
# stack's noun to its forage name (Elanthipedia: Red flower; the plural
# never finds). The profile's `forage_herbs` turns it on.
FORAGE_NAMES = {"flowers": "red flower"}
STACK_PIECES = 25
WRONG_SIZE = ("calls for stacks of",)
COMBINED = ("you combine",)
# A remedy of any size but the order's is refused with that same line,
# short or over (#428), and is brought to size (captured 2026-10-03 on
# blister creams): COUNT "You count out 5 uses remaining."; MARK <it>
# AT 3 "You measure out 3 usable portions from the stack and mark it
# for cutting." (AT its whole size: "There is not enough remedy material
# present to do that."); BREAK, a hand free, "You carefully break off 3
# pieces from the stack." — the original keeps the 3 marked, a new item
# in the free hand the rest ("You can't break it with both hands full!",
# and unmarked "You can't break that."); COMBINE #a WITH #b "You combine
# the stacks of remedies together.", the result a new id. CUT cuts
# nothing. A STOW merges a remedy into a like stack in the container,
# and refuses past its limit: "You just can't make that stack any
# larger." (dr-scripts issue #938, where MARK and BREAK come from).
STACK_USES = 5  # the order's stack: "I need 2 stacks (5 uses each)"
MARKED = ("mark it for cutting",)
BROKEN = ("break off",)
_USES = re.compile(r"count out (\d+) uses? remaining", re.IGNORECASE)


def pieces(answer):
    """COUNT's pieces, or None when the answer gives none (items.count;
    herbstacks imports it here)."""
    return items.count(answer)


def uses(answer):
    """COUNT's uses of a remedy ("You count out 5 uses remaining."), or
    None when the answer gives none."""
    match = _USES.search(str(answer or ""))
    return int(match.group(1)) if match else None


def containers_of(possessions):
    """The container nouns INV LIST shows holding anything, the mortar
    left out, in listing order (items.containers) — where another stack
    of a herb may be."""
    return items.containers(possessions, skip=("mortar",))


def containers_with(possessions, word):
    """The container nouns whose INV LIST contents name `word` ("dried",
    "flowers"), the mortar left out, in listing order (items.containers):
    where a herb may be. The gem pouch was LOOKed IN for herbs until
    2026-10-01 (#402)."""
    return items.containers(possessions, holding=word, skip=("mortar",))


_IN_MORTAR = re.compile(
    r"not required to continue crafting (?:the |some |a |an )?(?P<name>[\w' -]+?)[,.]",
    re.IGNORECASE,
)


def remedy_in_mortar(text):
    """The remedy the mortar already holds, off the refusal of another
    herb: (name as the book knows it, its recipe) — "nemoih salve" is
    the head salve, a chapter-3 remedy named by its herb while
    unfinished — or None when no such line or no such recipe."""
    match = _IN_MORTAR.search(text or "")
    if not match:
        return None
    name = match.group("name").strip().lower()
    spec = recipe(name)
    if spec is not None:
        return name, spec
    herb = name.split()[0]
    salve = HERB_SALVE.get(herb)
    if salve is None:
        return None
    return f"{salve} salve", SALVES[salve]


# LOOK IN MY MORTAR, no roundtime: "In the iron mortar you see some
# unfinished nemoih salve." (2026-09-23) — what a craft finds before it
# starts, whichever run left it.
_UNFINISHED = re.compile(r"unfinished (?P<name>[\w' -]+?)[,.]", re.IGNORECASE)


def unfinished_in_mortar(text):
    """The remedy LOOK IN MY MORTAR shows in progress: (name as the
    book knows it, its recipe), or None for an empty mortar or a
    remedy the book has no page for."""
    match = _UNFINISHED.search(text or "")
    if not match:
        return None
    name = match.group("name").strip().lower()
    spec = recipe(name)
    if spec is not None:
        return name, spec
    salve = HERB_SALVE.get(name.split()[0])
    if salve is None:
        return None
    return f"{salve} salve", SALVES[salve]


# A tool worn past use (captured 2026-09-26): "The iron pestle is far
# too damaged to be used for that." — no "you" in it, so it read as a
# bystander's line and the crushes ran on, 34 in two minutes.
TOOL_WORN = ("far too damaged to be used",)

CRUSH_OUTCOMES = (
    ("tool worn", TOOL_WORN),
    ("no instructions", NO_INSTRUCTIONS),
    ("missing", MISSING),
    ("free hand", FREE_HAND),
    ("as crushed", AS_CRUSHED),
    ("done already", DONE_ALREADY),
    ("need water", NEED_WATER),
    ("need alcohol", NEED_ALCOHOL),
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
# The order's quality is enforced (captured 2026-09-22 on the third
# stack of an easy order at rank 10, after four creams had passed):
# "The work order requires items of a higher quality, so you decide
# against bundling that." The remedy stays in hand, a usable remedy;
# the order still wants its stack.
REJECTED = ("requires items of a higher quality",)
REJECTIONS = 3  # rejected remedies in one order before it is given up
PAID = re.compile(r"are given (\d+) kronars", re.IGNORECASE)
NO_MASTER = ("to whom are you speaking",)
LEVELS = ("easy", "challenging", "hard")
LOGBOOK_ITEM = re.compile(
    r"craft (?:some |a |an )?(?P<item>[\w' -]+?) from any material", re.IGNORECASE
)
ORDER_TRIES = 3  # orders asked for before a run gives up on the master's picks

# The shops that keep an order going (captured 2026-09-22): the Crossing
# Alchemy Society's Supplies (map 8862) sells the dried herbs by the
# 25-piece stack and water by ten splashes (grain alcohol too, ORDER 2,
# from Elanthipedia's Alchemy Society (Crossing) shop list), and the
# Crossing Forging Society's Supplies (8775) the coal nugget that is the
# catalyst — ORDER
# # twice at either, the first quotes ("You can purchase (25 pieces)
# dried red flowers for 343 Kronars.  Just order it again and we'll see
# it done!"), the second buys ("The attendant takes some coins from you
# and hands you (25 pieces) dried red flowers."), into a hand. Hulnik
# and sufil are on no shelf there, so a back or eye salve order is
# asked again. The purchase itself is shop.buy's (client/game/shop.py,
# #407): a wrong quote REFUSEd, a refusal for want of coin said, a
# closing answer it does not know reported and counted.
SUPPLIES = "8862"
CATALYST_SHOP = "8775"
CATALOG = {  # noun: (catalog number, Kronars)
    "water": (1, 62),
    "alcohol": (2, 81),
    "nemoih": (3, 250),
    "plovik": (4, 312),
    "jadice": (5, 375),
    "nilos": (6, 437),
    "georin": (7, 437),
    "flowers": (13, 343),
}
# The massive coal nugget, item 2: a rub takes one volume and it has
# ten (COUNT MY NUGGET read "About 8 volumes" after two rubs,
# 2026-10-08), so 212 Kronars buys ten rubs where ten tiny nuggets
# (item 1, 31 each) cost 310 — the operator: buy massive from now on.
CATALYST_CATALOG = {"nugget": (2, 212)}
CATALYST_RUBS = 10  # rubs a nugget gives: one a volume
# The catalyst is bought as a stock, not an order's worth (#393): the
# Forging Society's Supplies are 22 steps each way, and a two-stack
# order sent the next one there again (2026-09-29). One massive nugget
# is the stock; restock() buys more only when an order owes more rubs.
CATALYST_STOCK = 1
# The quote and the hand-over are shop's now (#407), kept under their
# old names here for what reads them.
BOUGHT = shop.BOUGHT
quote = shop.quote
ROUNDTIME = re.compile(r"roundtime:\s*(\d+)\s*sec", re.IGNORECASE)


def parse_args(args):
    """{"salve", "until", "once", "count", "work", "level", "ledger"} from
    ;remedies' arguments: the salve to train on ("head" by default),
    until= the Alchemy mindstate to stop at (34), `once` to exit at the
    lock, count= remedies (or orders, with work) before ending,
    `work [easy|challenging|hard]` for the society's orders instead of
    the training loop, `ledger` to print the orders' takings, `merge` to
    merge the dried herb stacks and end (#402)."""
    options = {
        "salve": "head",
        "until": 34,
        "once": False,
        "count": 0,
        "work": False,
        "level": "easy",
        "ledger": False,
        "merge": False,
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
        elif key == "ledger":
            options["ledger"] = True
        elif key == "merge":
            options["merge"] = True
        elif key in LEVELS:
            options["level"] = key
    return options


def recipe(name):
    """(chapter, page, herb, extra herb or None, noun, liquid) for an
    item as the master or the book names it ("some blister cream"),
    None for one the book has no page for."""
    key = re.sub(r"^(?:some|a|an)\s+", "", str(name or "").strip().lower())
    return RECIPES.get(key)


def herb_for(salve):
    """The dried herb a chapter-3 salve wants: "nemoih" for the head."""
    return SALVES[salve][2]


def page_for(salve):
    return SALVES[salve][1]


def crush_command(herb, started, noun="salve"):
    """CRUSH the herb the first time, the unfinished remedy — by its
    noun, "salve" or "cream" — after. The mortar and pestle go by their
    bare nouns here: CRUSH's WITH clause refuses the profile's whole
    name ("with my iron pestle": "With what, your hand?  Huh uh.",
    2026-10-06), and by the CRUSH the tools fetched by that name are
    the ones in hand, which MY <noun> reaches first (#478)."""
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


# An order past its due time (captured 2026-09-26): READ MY LOGBOOK
# answers "This logbook is tracking a work order that has expired.  You
# must untie any items bundled with the logbook then ASK the trainer for
# another work order.", and the master, asked anyway, "you realize you
# have items bundled with the logbook, and should untie them before
# getting a new work order."
LOGBOOK_EXPIRED = ("work order that has expired",)
MASTER_UNTIE = ("should untie them", "untie any items bundled")
# An order that runs out while it is worked (captured 2026-09-30, #397):
# BUNDLE answers "This work order has expired.  You should give this
# logbook to a crafting trainer to have it cleared, or ask a trainer for
# a new work order.", and the master, handed the logbook, "Apparently
# the work order time limit has expired.  You should untie any items
# bundled with it and then ask Lanshado for another."
ORDER_EXPIRED = ("work order has expired", "time limit has expired")


def parse_logbook(text):
    """("none" | "open" | "done" | "expired", remaining, roisaen) from
    READ MY LOGBOOK."""
    lowered = (text or "").lower()
    if any(word in lowered for word in LOGBOOK_EXPIRED):
        return "expired", 0, None
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


def roundtime_of(text):
    """The seconds a CRUSH's answer says it cost ("Roundtime: 19 sec."),
    0 when it says none — the ledger's crush_seconds add these up."""
    match = ROUNDTIME.search(text or "")
    return int(match.group(1)) if match else 0


def is_noise(text):
    """True when a CRUSH's answer window holds nothing said to the
    character: another player's line ("Swoth runs south.", 2026-09-22)
    closed the window before the crush's own answer arrived. Not an
    unrecognized answer — the next crush finds the mortar as it is."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return bool(lines) and not any(
        re.search(r"\byou\b|\byour\b", line, re.IGNORECASE) for line in lines
    )


def logbook_item(text):
    """The item an open order in READ MY LOGBOOK tracks ("blister
    cream"), or None — a run resumes the order it left in the logbook
    rather than asking for a new one."""
    match = LOGBOOK_ITEM.search(text or "")
    return match.group("item").strip().lower() if match else None


def building_rooms(rooms, room_id):
    """The map's rooms in the same building as `room_id`, in id order:
    those whose title shares its part before the comma ("Crossing
    Alchemy Society" of "[Crossing Alchemy Society, Tool Shop]"), the
    room itself included. The society's master wanders them (the
    operator, 2026-09-23), so an order is asked wherever he stands."""
    # The map keys its rooms by int; a caller may hold the id as text.
    rooms = rooms or {}
    room = rooms.get(room_id) or rooms.get(str(room_id)) or {}
    if not room and str(room_id).isdigit():
        room = rooms.get(int(room_id)) or {}
    titles = room.get("title") or []
    title = str(titles[0] if isinstance(titles, list) and titles else titles or "")
    building = title.strip("[] ").split(",")[0].strip()
    if not building:
        return []
    found = []
    for rid, other in rooms.items():
        names = other.get("title") or []
        name = str(names[0] if isinstance(names, list) and names else names or "")
        if name.strip("[] ").split(",")[0].strip() == building:
            found.append(str(rid))
    return sorted(found, key=lambda rid: (len(rid), rid))


def sellable(spec):
    """True when every herb and the liquid the recipe wants are on the
    society's Supplies shelves — an order for one that is not is asked
    again."""
    chapter, page, herb, extra, noun, liquid = spec
    return herb in CATALOG and (extra is None or extra in CATALOG) and liquid in CATALOG


def unsold(spec):
    """What of the recipe the Supplies does not sell, as the echo names
    it ("dried sufil", "brine"), or None."""
    chapter, page, herb, extra, noun, liquid = spec
    for wanted in (herb, extra):
        if wanted and wanted not in CATALOG:
            return f"dried {wanted}"
    return None if liquid in CATALOG else liquid


def shortage(why, spec, catalyst):
    """What a craft that ended on `why` ran out of, as (noun, per
    stack, shop, catalog) — the order's controlling herb a stack per
    remedy, any other herb the Supplies sells one stack for many,
    water or alcohol ten splashes at a time, the catalyst one per
    remedy — or None when `why` is not a shortage the shops answer."""
    chapter, page, herb, extra, noun, liquid = spec
    if why == f"dried {herb}":
        return herb, 1, SUPPLIES, CATALOG
    # The game's word, not the order's recipe: a remedy another run left
    # in the mortar asks for its own second herb (#431: a leftover
    # ointment's plovik during an itch salve order) and its own liquid.
    wanted = why[len("dried ") :] if why.startswith("dried ") else ""
    if wanted and wanted in CATALOG:
        return wanted, 0, SUPPLIES, CATALOG
    if why in LIQUIDS:
        return why, 0, SUPPLIES, CATALOG
    if catalyst and why == catalyst:
        return catalyst, 1, CATALYST_SHOP, CATALYST_CATALOG
    return None
