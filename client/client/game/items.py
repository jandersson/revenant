"""Items: a thing named by its id when held and whole otherwise, the
containers INV LIST showed, a listing or a COUNT parsed, "no room".

    items.name(s, "dried red flowers")   # "#<exist>" when a hand holds it, else the name as given
    items.ref(s, "flowers")              # the id, or None
    items.containers(possessions, holding="dried", skip=("mortar",))   # listing order, each once
    items.listed(answer)                 # a LOOK IN answer's items; [] empty, None no listing
    items.listed_nouns(answer)           # their nouns
    items.count(answer)                  # COUNT's pieces, or None
    items.stowed_in(answer)              # the container a STOW answer names
    items.no_room(answer)                # a full container (NO_ROOM, the one table)

A bare noun takes the first item of that noun, whatever kind: name an
item whole, or by its id when a hand holds it (docs/protocol.md
"Items by id").
"""

import re

from client.game import hands
from client.game.possessions import noun_of

_NOTES = """
GET MY ROPE took a looted lead rope (#399), GET MY FLOWERS a fresh stack
among the dried (#406); a held item answers to the id its hand tag
carries (#402). Six container listers, three LOOK IN parsers, two COUNT
parsers and two "no room" tables said these their own way before #407.
"""

# A full container (captured 2026-09-21 #262, 2026-09-28 #283): "There
# isn't any more room in the sack for that.", "...would push you over
# the item limit", "You just can't fit that in there."
NO_ROOM = (
    "any more room",
    "no room for",
    "won't fit",
    "push you over the item limit",
    "you just can't",
    # A full gem pouch (captured 2026-10-03, #436): "You've already got
    # a wealth of gems in there!  You'd better tie it up before putting
    # more gems inside." — never TIEd (#283).
    "wealth of gems",
)
# A LOOK IN or OPEN answer: "In the iron box you see some coins, a ruby
# and a dagger." — and the empty forms.
_LISTED = re.compile(r"you see (.+?)\.?\s*$", re.IGNORECASE | re.MULTILINE)
_EMPTY = ("nothing in", "is empty", "there is nothing")
# An item listing splits on commas, and on "and" only before the next
# item's article: "a salt and pepper shaker" stays whole.
_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and\s+(?=(?:an?|some|the)\s)", re.IGNORECASE)
# COUNT: "You count out 12 pieces of material there."
_PIECES = re.compile(r"count out (\d+) pieces?", re.IGNORECASE)
# STOW's answer names where the item went.
_STOWED_IN = re.compile(
    r"you put your .+? in your (?P<container>[^.]+)\.", re.IGNORECASE
)


def ref(s, noun):
    """The held item's id as a command takes it ("#136104233") when a
    hand holds `noun` and the tag carries an id, else None."""
    for tag in hands.tags(s).values():
        if tag and hands._same(tag.get("noun") or "", noun) and tag.get("exist"):
            return f"#{tag['exist']}"
    return None


def name(s, item):
    """What a command names the item by: its id when a hand holds it,
    else `item` as given — whole, with its adjectives."""
    return ref(s, item) or item


def containers(possessions, holding=None, skip=()):
    """The nouns of the containers INV LIST shows holding something, each
    once in listing order; `holding` narrows to the containers of items
    whose name carries that word (or that a callable accepts), `skip`
    leaves nouns out."""
    by_exist = {item.get("exist"): item for item in possessions or []}
    skipped = {str(noun).lower() for noun in skip}
    found = []
    for item in possessions or []:
        if holding is not None:
            if callable(holding):
                if not holding(item):
                    continue
            elif str(holding).lower() not in str(item.get("name") or "").lower():
                continue
        holder = by_exist.get(item.get("container_exist"))
        if not holder:
            continue
        noun = str(holder.get("noun") or noun_of(holder.get("name") or "")).lower()
        if noun and noun not in skipped and noun not in found:
            found.append(noun)
    return found


def listed(answer):
    """The items a LOOK IN or OPEN answer lists ("In the iron box you see
    some coins, a ruby and a dagger." -> ["some coins", "a ruby", "a
    dagger"]), repeats kept; [] for an empty container; None when the
    answer is no listing at all."""
    match = _LISTED.search(answer or "")
    if not match:
        lowered = (answer or "").lower()
        return [] if any(word in lowered for word in _EMPTY) else None
    return [item.strip() for item in _SPLIT.split(match.group(1)) if item.strip()]


def listed_nouns(answer):
    """The nouns (each item's last word, lowered) a listing names; [] or
    None as listed()."""
    found = listed(answer)
    if found is None:
        return None
    return [noun_of(item).lower() for item in found if noun_of(item)]


def count(answer):
    """COUNT's pieces ("You count out 12 pieces of material there."), or
    None for an answer that gives none."""
    match = _PIECES.search(str(answer or ""))
    return int(match.group(1)) if match else None


def stowed_in(answer):
    """The container a STOW's answer names ("You put your flowers in
    your backpack."), or ""."""
    match = _STOWED_IN.search(str(answer or ""))
    return match.group("container").strip() if match else ""


def no_room(answer):
    """True when the answer says the container is full."""
    lowered = str(answer or "").lower()
    return any(word in lowered for word in NO_ROOM)
