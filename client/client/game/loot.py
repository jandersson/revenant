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
it fell. `ignored` reads the profile's `loot_ignore` — the common
metals by default, rare ones kept (#365) — which a hunt never picks up
and ;boxes puts in the room's trash. That is combat-trainer's LootProcess: its `lootables` matched
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

from client.game import items
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

# Elanthipedia's Mining page (2026-09-28): the common metals, the
# profile's default `loot_ignore` — the rare, very rare and quest-only
# ones are kept — and the common alloys pewter (tin and lead), brass
# (zinc and copper) and bronze (tin and copper), Elanthipedia's pages
# of those names: the pewter and brass bars out of boxes the operator
# named on 2026-10-02, bronze beside them in the sack. METAL_FORMS are
# the page's and Category:Crafting materials' names for a piece of
# metal, mined or dropped.
COMMON_METALS = (
    "brass",
    "bronze",
    "copper",
    "covellite",
    "iron",
    "lead",
    "nickel",
    "oravir",
    "pewter",
    "silver",
    "tin",
    "zinc",
)
METAL_FORMS = frozenset(
    {"nugget", "fragment", "lump", "shard", "tear", "bar", "ingot", "fist"}
)

# GET/STOW <item>'s answers, combat-trainer's bput list for its STOW: the
# pickup and what stops it. Failures first, as probe.classify wants. The
# pickup here is GET, so the profile's loot container takes the item
# (combat-trainer's STOW goes to the game's default).
NOT_YOURS = ("is not yours",)
NO_ROOM = items.NO_ROOM  # a full container's wordings, the one table
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
# 'pouch-full' flag): the spare pouch is #283. STOW GEM at a full pouch
# picks the gem up and keeps it in hand (captured 2026-10-03, #436): "You
# pick up a tiny green diopside." then "You've already got a wealth of
# gems in there!  You'd better tie it up before putting more gems
# inside." — the gem goes with the loot (hunt.pocket).
POUCH_FULL = ("too full to fit another gem", "wealth of gems")


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


def ignored(entry, ignore=()):
    """True when the profile's `loot_ignore` names the item: a phrase
    that ends its name, word for word ("embroidery needle" for "an
    embroidery needle"), or a lone metal naming that metal in any form
    ("copper" for "a large copper nugget", never for copper coins)."""
    words = re.findall(r"[a-z'-]+", str(entry or "").lower())
    for item in ignore or ():
        wanted = str(item).strip().lower().split()
        if not wanted or len(wanted) > len(words):
            continue
        if words[-len(wanted) :] == wanted:
            return True
        if len(wanted) == 1 and words[-1] in METAL_FORMS and wanted[0] in words[:-1]:
            return True
    return False


def short_name(entry):
    """The item's last two words ("copper nugget" for "a large copper
    nugget"), one for a one-word name: specific enough that GET and PUT
    take this item and not another of the same noun."""
    words = str(entry or "").split()
    if words and words[0].lower() in ("a", "an", "some", "the"):
        words = words[1:]
    return " ".join(words[-2:]).lower()


def lootable(entry, additions=(), subtractions=(), ignore=()):
    """True for what a hunt takes: coins, a gem, a box, and the profile's
    `loot_additions` (nouns), less its `loot_subtractions` and whatever
    its `loot_ignore` names (so additions "nugget" takes only the rare
    metals)."""
    noun = noun_of(entry)
    if noun in {str(n).strip().lower() for n in subtractions or ()}:
        return False
    if ignored(entry, ignore):
        return False
    if noun in {str(n).strip().lower() for n in additions or ()}:
        return True
    return kind(entry) != "item"
