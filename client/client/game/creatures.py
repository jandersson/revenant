"""Aiming at one creature among several of the same noun — "second cougar" (#278).

The room's listing names its creatures in order with repeats
("a cougar which appears dead, a rise in the cliff, a cougar and a
cougar", captured 2026-09-22), and the game counts them by ordinal:
the first "cougar" is the corpse, the live ones are "second cougar"
and "third cougar". A swing at the plain noun lands on the corpse
("already quite dead") and is spent. `aim` gives the phrase for the
first live one of a noun; `ordinals` the whole listing's phrases.
lich-5's `add_ordinals_to_duplicates` and `find_dead_npcs`
(drinfomon/drdefs.rb) do the same for dr-scripts; the parser's
`room_creatures` and `room_creatures_dead` are the input here.

`outgrown` is the other question a room's creatures answer: which
trained skills they can no longer teach. A creature teaches a skill
fully below its MinCap, less up to its MaxCap, and nothing past it
(Elanthipedia's Critter template, generated into creatures_data.py by
tools/creature_tables.py); on 2026-09-26 cougars (MaxCap 49) had
taught Small Edged 58 and Brawling 57 nothing for five hunts (#322).
"""

from client.game.creatures_data import CAPS

_ARTICLES = ("a", "an", "the", "some")

ORDINALS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
)


def noun_of(name):
    """The last word of a listing name: "a striped badger" -> "badger"."""
    words = str(name or "").split()
    return words[-1].lower() if words else ""


def phrase(noun, k):
    """The k-th (1-based) thing of a noun as the game counts it: the
    first is the plain noun, the rest "second noun", "third noun"...."""
    if k <= 1:
        return noun
    ordinal = ORDINALS[k - 1] if k - 1 < len(ORDINALS) else f"{k}th"
    return f"{ordinal} {noun}"


def ordinals(names):
    """Every creature of the listing as the game would have it aimed at:
    ["cougar", "second cougar", "third cougar"] — one count per noun,
    corpses counted like the living."""
    seen = {}
    phrases = []
    for name in names or []:
        noun = noun_of(name)
        seen[noun] = seen.get(noun, 0) + 1
        phrases.append(phrase(noun, seen[noun]))
    return phrases


def caps_of(name):
    """(creature, (level, MinCap, MaxCap)) for a listing name, or None:
    the longest run of its last words the table knows, so the game's
    random adjectives drop away ("a dour forager goblin" -> "forager
    goblin")."""
    words = str(name or "").lower().split()
    if words and words[0] in _ARTICLES:
        words = words[1:]
    for start in range(len(words)):
        key = " ".join(words[start:])
        if key in CAPS:
            return key, CAPS[key]
    return None


def outgrown(names, ranks):
    """What the creatures in `names` can no longer teach: (top, past) —
    top the known creature with the highest MaxCap as (name, MaxCap),
    past the [(skill, rank)] of `ranks` ({skill: rank}) at or above
    it. (None, []) when no name is in the table."""
    known = {}
    for name in names or []:
        hit = caps_of(name)
        if hit:
            known[hit[0]] = hit[1][2]
    if not known:
        return None, []
    creature = max(known, key=known.get)
    cap = known[creature]
    past = sorted(
        (skill, rank)
        for skill, rank in ranks.items()
        if rank is not None and rank >= cap
    )
    return (creature, cap), past


def aim(noun, names, dead=()):
    """The phrase that reaches the first live creature of `noun` in the
    listing: the plain noun when the first of them lives (or when the
    listing does not show the noun at all), "second noun" and so on
    when corpses of it come first. The plain noun when every one listed
    is dead: the game then says so and the hunt disposes of it."""
    noun = str(noun or "").strip().lower()
    if not noun:
        return noun
    dead = list(dead or [])
    k = 0
    for index, name in enumerate(names or []):
        if noun_of(name) != noun:
            continue
        k += 1
        if not (index < len(dead) and dead[index]):
            return phrase(noun, k)
    return noun
