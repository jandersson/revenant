"""What a SEARCH left on the ground, read off the room's listing rather
than the wording — a hunt grabs its loot whatever the game called it
(the operator, 2026-09-23: "it should grab loot"), the way dr-scripts'
combat-trainer does.

The search's answer names the yield in words the script may not know
("The grendel was carrying some waermodi stones, 7 copper coins
(Kronars), and 1 bronze coin (Dokora)!" went unread for a night, #292),
but the room's listing — the parser's `room_objs`, "You also see some
bronze coins, some copper coins, a dented iron box, a small grendel
which appears dead and a war club." — shows what landed. `new_items`
is the listing after the search less the listing before it, counted
(coins repeat), less corpses and creatures; `lootable` keeps what a
hunt wants — coins, a gem, a box — plus the profile's `loot_additions`
and less its `loot_subtractions`, so a grendel's war club stays where
it fell. That is combat-trainer's LootProcess: its `lootables` matched
against DRRoom.room_objs, the gem and box nouns from dr-scripts'
base-items.yaml (GEM_NOUNS and BOX_NOUNS below are those lists), the
pickup one STOW with its answers read (STOW_OUTCOMES is its list: "You
stop as you realize the ... is not yours" is another hunter's loot,
"There isn't any more room" and "push you over the item limit" make the
noun unlootable for the rest of the run so it is not retried every
kill), and `box_loot_limit` as the profile's `box_limit`. Where
combat-trainer DROPs what it cannot stow, this leaves it on the ground
and says so — nothing here drops anything. Sources:
docs/bibliography.md.
"""

import re
from collections import Counter

from client.game.creatures import noun_of

CORPSE = "which appears dead"
COIN = re.compile(r"\bcoins?\b", re.IGNORECASE)
# dr-scripts data/base-items.yaml box_nouns and gem_nouns (2026-09-23).
BOX_NOUNS = frozenset(
    {
        "coffer",
        "strongbox",
        "chest",
        "caddy",
        "trunk",
        "casket",
        "skippet",
        "crate",
        "box",
    }
)
GEM_NOUNS = frozenset(
    """tsavorite zircon quartz chalcedony diopside coral moonstone onyx topaz amber
    pearl chryso lazuli turquoise bloodstone hematite morganite sapphire agate
    carnelian diamond crystal emerald ruby tourmaline tanzanite jade ivory sunstone
    iolite beryl garnet alexandrite amethyst citrine aquamarine star-stone kunzite
    stones spinel opal peridot andalusite chrysoprase chrysoberyl""".split()
)

# GET/STOW <item>'s answers, combat-trainer's bput list for its STOW: the
# pickup and what stops it. Failures first, as probe.classify wants. The
# pickup here is GET, so the profile's loot container takes the item
# (combat-trainer's STOW goes to the game's default).
NOT_YOURS = ("is not yours",)
NO_ROOM = ("isn't any more room", "push you over the item limit", "you just can't")
GONE = (
    "stow what",
    "what were you referring",
    "rapidly decays away",
    "cracks and rots away",
    "can't be picked up",
)
HELD = ("already in your inventory",)
FREE_HAND = ("need a free hand",)
STOWED = ("you pick up", "you put", "you get", "you open")
STOW_OUTCOMES = (
    ("not yours", NOT_YOURS),
    ("no room", NO_ROOM),
    ("gone", GONE),
    ("held", HELD),
    ("free hand", FREE_HAND),
    ("stowed", STOWED),
)
# A gem pouch answers a STOW of a gem when it is full (combat-trainer's
# 'pouch-full' flag): the spare pouch is #283.
POUCH_FULL = ("too full to fit another gem",)


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
    """ "coins", "box", "gem" or "item" for a listing entry."""
    lowered = entry.lower()
    if COIN.search(lowered):
        return "coins"
    noun = noun_of(lowered)
    if noun in BOX_NOUNS:
        return "box"
    if noun in GEM_NOUNS:
        return "gem"
    return "item"


def lootable(entry, additions=(), subtractions=()):
    """True for what a hunt takes: coins, a gem, a box, and the profile's
    `loot_additions` (nouns), less its `loot_subtractions`."""
    noun = noun_of(entry)
    if noun in {str(n).strip().lower() for n in subtractions or ()}:
        return False
    if noun in {str(n).strip().lower() for n in additions or ()}:
        return True
    return kind(entry) != "item"
