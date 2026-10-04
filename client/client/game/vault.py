"""The Carousel vault (;vault): the way in and out and the game's answers.

At a town's Carousel, GO ARCH has the attendant escort the character
into a booth (any of the arches: a bare ARCH takes the first, the
platinum); PULL LEVER opens the booth's door, GO DOOR enters the
chamber, OPEN VAULT opens it. PUT <item> IN VAULT stores, GET <item>
FROM VAULT takes out, RUMMAGE VAULT lists everything. CLOSE VAULT, GO
DOOR back to the booth and GO ARCH back to the Carousel ("The door
slams closed."). Captured on Cecil, 2026-10-04 (Elanthipedia: Vaults).
An item put in the vault and got out again comes back under a new id.
"""

import re

CAROUSEL = "The Carousel"  # a ;go2 title: the nearest town's carousel

# The answers, captured 2026-10-04: "The Dwarven attendant escorts you
# through the platinum arch.", "... as you pull the lever, and the door
# pops open ...", "The vault opens.", "You put your compendium in the
# secure vault.", "You get a grey leather compendium ... from inside a
# secure vault.", "You close the vault.", "The door slams closed."
ESCORTED = ("escorts you through",)
LEVER = ("door pops open",)
OPENED = ("the vault opens", "already open")
STORED = ("in the secure vault",)
TAKEN = ("from inside a secure vault",)
CLOSED = ("you close the vault", "already closed")
LEFT = ("door slams closed",)

CHAMBER = "carousel chamber"  # the room title inside
BOOTH = "carousel booth"

_RUMMAGED = re.compile(r"rummage through .*? and see (.+?)\.?\s*$", re.I | re.M)
# An item listing splits on commas, and on "and" only before the next
# item's article (items.py's rule).
_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and\s+(?=(?:an?|some|the)\s)", re.I)


def said(answer, words):
    lowered = str(answer or "").lower()
    return any(word in lowered for word in words)


def contents(answer):
    """The items RUMMAGE VAULT names, in its order; None when the answer
    is no listing."""
    match = _RUMMAGED.search(str(answer or ""))
    if not match:
        return None
    return [item.strip() for item in _SPLIT.split(match.group(1)) if item.strip()]


def items_of(words):
    """The item names a command line gives, comma-separated: "leather
    compendium, fine scroll" -> ["leather compendium", "fine scroll"]."""
    text = " ".join(str(word) for word in words)
    return [item.strip() for item in text.split(",") if item.strip()]
