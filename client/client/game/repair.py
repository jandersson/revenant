"""Gear repaired at a shop, in words: the condition APPRAISE names, the
repairman's quote, the ticket and the pickup — what ;repair reads.

Every weapon, shield and piece of armor wears down in use; a repair
shop's NPC mends any of them for coin (Elanthipedia: Repair — both
Crossing repairers take metal and leather since Tuesday Tidings 77).
The trade is two GIVEs: the first gets an estimate in the province's
copper and the time it takes, a second one soon after pays and hands
back a ticket; the ticket, given back once the time has passed,
returns the item. The condition comes from APPRAISE (QUICK is enough,
5 s): the wiki's ten phrases, each a band of the item's health
(Elanthipedia: Appraisal skill, Condition). The shops are the map's
`repair` tag; the repairman's name per room is dr-scripts'
data/base-town.yaml, and the GIVE answers lich-5's common-items.rb
give_item? patterns where not captured.

Captured 2026-09-24 at Catrox's Forge in the Crossing, a plate at "a
few dents and dings":
  GIVE (quote)    Catrox looks over the plate and says, "That will cost
                  108 Kronars to repair.  Just give it to me again if you
                  want, and I'll have it ready in 5 roisaen."
  GIVE (no coin)  Catrox mutters, "You will need more coin if I am to be
                  repairing that!"   — a second GIVE within seconds; one
                  ~20 s later re-quotes: the offer lapses.
  GIVE (paid)     You hand Catrox 108 Kronars and he gives you back a
                  repair ticket.  Catrox says, "I will complete this work
                  for you in about 5 roisaen.  Please don't lose this
                  ticket!  You must have it to reclaim your plate."
  GIVE (pristine) Catrox shrugs and says, "There isn't a scratch on that,
                  and I'm not one to rob you."
  LOOK AT TICKET  Looking at the Catrox ticket you see it is for some
                  light full plate.  You recall that your plate won't be
                  ready for another 4 roisaen. / ... should be ready any
                  moment now. / ... should be ready by now.
  GIVE TICKET     Catrox smiles and says, "Well that isn't gonna be done
                  for another 4 roisaen." / ... "Well that is almost done,
                  just give me a few more moments here." / You hand
                  Catrox your ticket and are handed back some light full
                  plate.
Crafting tools go to a different shop: the Crossing Engineering
Society's Repairman Rangu, "Only crafting tools are repaired here"
(Elanthipedia: Engineering Society (Crossing); Crafting tools, Repair;
the Forging guide). APPRAISE names no condition for a tool; ANALYZE
does, with the same phrases, 10 s of roundtime, the tool in hand.
Captured 2026-09-26, an iron pestle worn past use:
  ANALYZE         This appears to be a crafting tool and it is battered
                  and practically destroyed.
  ASK ABOUT       Rangu explains, "I can repair any of your crafting
   REPAIRS        tools back to new.  My recommendation is you don't
                  wait until they are mangled beyond recognition, or else
                  you'll pay dearly for it.  Just give me the tool and
                  I'll provide you with an estimate."
  GIVE (quote)    Rangu looks over the pestle and says, "That will cost
                  20 Kronars to repair.  Just give it to me again if you
                  want, and I'll have it ready in 10 roisaen."
  GIVE (no coin)  Rangu beats his fist down upon the counter and
                  exclaims, "Ya'll need more coin if I am to be repairing
                  that!"
  GIVE (paid)     You hand Rangu 20 Kronars and he gives you back a
                  repair ticket.  Rangu says, "I should be having that
                  done for you in about 10 roisaen.  Don't lose this
                  ticket!  You must have it to reclaim your pestle."
                  — the first GIVE after the teller trip, 9 s after the
                  quote: an estimate still standing is paid at once.
  LOOK AT TICKET  Looking at the Rangu ticket you see it is for an iron
                  pestle.  You recall that your pestle won't be ready for
                  another 3 roisaen.
  GIVE TICKET     Rangu grumbles, "Well that isn't gonna be done for
                  another 3 roisaen." / Rangu grumbles, "Well that is
                  almost done, just give me a few more moments here." /
                  You hand Rangu your ticket and are handed back an iron
                  pestle.
His tickets are "Rangu repair ticket"s.

The quote is copper: 200 carried, 92 after the 108. The first ;repair
run (a scimitar, "rather scuffed up", 5 Kronars, 1 roisaen) took GET
MY CATROX TICKET for the stowed ticket and got "You hand Catrox your
ticket and are handed back a watered steel scimitar."
"""

import re

# (phrase, lowest health %, highest) — Elanthipedia: Appraisal skill,
# Condition. APPRAISE says "... and is in pristine condition", "... and
# have a few dents and dings" (captured 2026-09-24); the phrase alone
# is matched.
CONDITIONS = (
    ("in pristine condition", 100, 100),
    ("practically in mint condition", 91, 99),
    ("in good condition", 81, 90),
    ("rather scuffed up", 71, 80),
    ("some minor scratches", 61, 70),
    ("a few dents and dings", 51, 60),
    ("several unsightly notches", 41, 50),
    ("heavily scratched and notched", 31, 40),
    ("battered and practically destroyed", 0, 20),
    ("badly damaged", 21, 30),
)

DEFAULT_FLOOR = 80  # repair a piece whose band tops out at or below this

# The repairman per map room (dr-scripts' data/base-town.yaml,
# metal_repair / leather_repair). A `repair` room missing here has no
# name to GIVE to and is not walked to.
SHOPS = {
    19093: "Catrox",  # Crossing
    1544: "Randal",  # Wolf Clan, outside the Crossing's west gate
    19270: "Ylono",  # Shard
    9639: "Granzer",  # Steelclaw Clan
    8737: "Unspiek",  # Riverhaven
    12218: "Dagul",  # Therenborough
    10752: "Raven",  # Ratha
    96: "Shh'yris",  # Aesry
    7229: "Sefu",  # Aesry
    11807: "Diwitt",  # Mer'Kresh
    11206: "Ladar",  # Hibarnhvidar
    12174: "Tuzra",  # Boar Clan
    12209: "Kamze",  # Langenfirth
    11124: "Fekoeti",  # Muspar'i
    15313: "Ushei",  # Hara'jaal
    51797: "Verrys",  # Leth Deriel
    8391: "Lakyan",  # Fang Cove
    8392: "Osmandikar",  # Fang Cove
}

# The crafting-tool repairman per map room (Elanthipedia: Engineering
# Society (Crossing) — "Only crafting tools are repaired here"). The
# map does not tag his shop `repair`, and lists it twice (the uid-less
# twin too).
TOOL_SHOPS = {
    19209: "Rangu",  # Crossing Engineering Society
    8866: "Rangu",
}

# The GIVE answers, captured unless marked; lich-5's give_item?
# patterns for the rest.
_QUOTE = re.compile(
    r"cost (?P<amount>[\d,]+) (?P<currency>Kronars|Lirums|Dokoras) to repair"
    r".*?ready in (?P<roisaen>\d+) roisaen",
    re.DOTALL,
)
_TICKET = re.compile(
    r"gives you back a repair ticket.*?in about (?P<roisaen>\d+) roisaen", re.DOTALL
)
TICKETED = "gives you back a repair ticket"
_PAID = re.compile(
    r"You hand \S+ (?P<amount>[\d,]+) (?P<currency>Kronars|Lirums|Dokoras)"
)
SHORT = ("need more coin",)
UNDAMAGED = (
    "isn't a scratch on that",
    "that isn't damaged",  # lich-5
    "will not repair something that isn't broken",  # lich-5
)
REFUSED = (
    "don't repair those here",  # lich-5
    "can't fix those",  # lich-5
    "what is it you're trying to give",  # lich-5
    "has declined the offer",  # lich-5
)
BUSY = ("already has an outstanding offer", "only have one outstanding offer")

_NOT_YET = re.compile(r"another (\d+) roisaen")
ALMOST = ("few more moments", "any moment now")
_RETURNED = re.compile(r"handed back (?P<item>[^.]+)\.")
_TICKET_FOR = re.compile(
    r"Looking at the (?P<name>[\w']+) ticket you see it is for (?P<item>[^.]+)\."
)
READY = ("should be ready by now",)

_ARTICLES = ("a ", "an ", "some ", "the ", "a pair of ", "pair of ")


def condition(text):
    """(phrase, lowest %, highest %) for the condition an APPRAISE answer
    names, or None when it names none (a container, a pouch)."""
    lowered = (text or "").lower()
    for phrase, low, high in CONDITIONS:
        if phrase in lowered:
            return phrase, low, high
    return None


def needs_repair(reading, floor=DEFAULT_FLOOR):
    """True when the condition's band tops out at or below `floor` %."""
    return reading is not None and reading[2] <= floor


def classify_give(text):
    """The repairman's answer to a GIVE of an item, as a dict with
    `kind`: "quote" (copper, currency, roisaen), "ticket" (roisaen),
    "short", "undamaged", "refused", "busy" or "unknown"."""
    text = text or ""
    lowered = text.lower()
    ticket = _TICKET.search(text)
    if ticket or TICKETED in lowered:
        paid = _PAID.search(text)
        return {
            "kind": "ticket",
            "roisaen": int(ticket.group("roisaen")) if ticket else None,
            "copper": int(paid.group("amount").replace(",", "")) if paid else None,
            "currency": paid.group("currency") if paid else None,
        }
    quote = _QUOTE.search(text)
    if quote:
        return {
            "kind": "quote",
            "copper": int(quote.group("amount").replace(",", "")),
            "currency": quote.group("currency"),
            "roisaen": int(quote.group("roisaen")),
        }
    for kind, needles in (
        ("short", SHORT),
        ("undamaged", UNDAMAGED),
        ("refused", REFUSED),
        ("busy", BUSY),
    ):
        if any(needle in lowered for needle in needles):
            return {"kind": kind}
    return {"kind": "unknown"}


def classify_pickup(text):
    """The answer to GIVE MY TICKET: {"kind": "returned", "item": name,
    "noun": noun}, {"kind": "wait", "roisaen": n} (n is 0 for "a few
    more moments") or {"kind": "unknown"}."""
    text = text or ""
    returned = _RETURNED.search(text)
    if returned:
        item = returned.group("item").strip()
        return {"kind": "returned", "item": item, "noun": noun_of(item)}
    not_yet = _NOT_YET.search(text)
    if not_yet:
        return {"kind": "wait", "roisaen": int(not_yet.group(1))}
    if any(needle in text.lower() for needle in ALMOST):
        return {"kind": "wait", "roisaen": 0}
    return {"kind": "unknown"}


def read_ticket(text):
    """LOOK AT MY TICKET: {"shop": "Catrox", "item": ..., "roisaen": n or
    0 when ready} or None when no ticket answered."""
    match = _TICKET_FOR.search(text or "")
    if not match:
        return None
    not_yet = _NOT_YET.search(text)
    return {
        "shop": match.group("name"),
        "item": match.group("item").strip(),
        "roisaen": int(not_yet.group(1)) if not_yet else 0,
    }


def noun_of(item):
    """The noun of an item as the game names it: "some light full plate"
    → "plate"."""
    return (item or "").strip().rstrip(".").split()[-1].lower() if item else ""


def bare(item):
    """The item's name without its article ("some light full plate" →
    "light full plate")."""
    lowered = (item or "").strip()
    for article in _ARTICLES:
        if lowered.lower().startswith(article):
            return lowered[len(article) :]
    return lowered


def shop_room(name):
    """The map room of the repairman `name` ("Catrox"), or None."""
    for room, shopkeeper in {**SHOPS, **TOOL_SHOPS}.items():
        if shopkeeper.lower() == (name or "").lower():
            return room
    return None


def candidates(possessions, hands, items=()):
    """The nouns to appraise, each with where it lives — [(noun, "worn" |
    "held")] — `items` when given (each "held" if in a hand, else
    "worn"), else what the hands hold and every worn item at depth 0 of
    the parser's possessions, each noun once."""
    held = [str(h.get("noun") or "") for h in hands if isinstance(h, dict)]
    held = [noun for noun in held if noun]
    if items:
        nouns = [str(item).strip().lower() for item in items if str(item).strip()]
        return [
            (noun, "held" if noun in held else "worn") for noun in dict.fromkeys(nouns)
        ]
    out = [(noun, "held") for noun in dict.fromkeys(held)]
    seen = set(held)
    for item in possessions or []:
        if item.get("depth", 0) != 0 or not item.get("worn"):
            continue
        noun = str(item.get("noun") or "").strip()
        if noun and noun not in seen:
            seen.add(noun)
            out.append((noun, "worn"))
    return out
