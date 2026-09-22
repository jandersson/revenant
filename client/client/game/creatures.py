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
"""

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
