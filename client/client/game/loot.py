"""What a SEARCH left on the ground, read off the room's listing rather
than the wording — a hunt grabs its loot whatever the game called it
(the operator, 2026-09-23: "it should grab loot").

The search's answer names the yield in words the script may not know
("The grendel was carrying some waermodi stones, 7 copper coins
(Kronars), and 1 bronze coin (Dokora)!" went unread for a night, #292),
but the room's listing — the parser's `room_objs`, "You also see some
bronze coins, some copper coins, a dented iron box, a small grendel
which appears dead and a war club." — shows what landed. `new_items`
is the listing after the search less the listing before it, counted
(coins repeat), less corpses and creatures; `kind` sorts each entry
into coins (GET COINS, #291), a box (into the loot container, never
opened by the hunt) or an item (the pouch, else stowed). A weapon a
grendel dropped ("a war club") is an item like any other and is
stowed; nothing here drops anything.
"""

import re
from collections import Counter

from client.game.creatures import noun_of

CORPSE = "which appears dead"
COIN = re.compile(r"\bcoins?\b", re.IGNORECASE)
BOX_NOUNS = frozenset(
    {"box", "chest", "coffer", "casket", "trunk", "strongbox", "crate", "caddy"}
)
GEM_WORDS = ("stone", "stones", "gem", "gems")


def entries(listing):
    """The listing's entries, in order: "You also see a, b and c." ->
    ["a", "b", "c"]; [] for an empty room."""
    text = str(listing or "").strip()
    text = (
        re.sub(r"^you also see\s+", "", text, flags=re.IGNORECASE).rstrip(".").strip()
    )
    if not text:
        return []
    parts = [part.strip() for part in text.split(", ")]
    if parts and " and " in parts[-1]:
        head, _, tail = parts[-1].rpartition(" and ")
        parts[-1:] = [head.strip(), tail.strip()]
    return [part for part in parts if part]


def new_items(before, after, creatures=()):
    """The entries `after` holds more of than `before`, each as many
    times as it is new, corpses and the room's creatures left out."""
    names = {str(name).lower() for name in creatures or ()}
    extra = Counter(entries(after)) - Counter(entries(before))
    found = []
    for entry, count in extra.items():
        lowered = entry.lower()
        if CORPSE in lowered or lowered in names:
            continue
        found.extend([entry] * count)
    return found


def kind(entry):
    """ "coins", "box" or "item" for a listing entry."""
    lowered = entry.lower()
    if COIN.search(lowered):
        return "coins"
    if noun_of(lowered) in BOX_NOUNS:
        return "box"
    return "item"
