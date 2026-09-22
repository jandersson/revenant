"""What a script may DROP: an allowlist, and the one way to drop — into
the room's trash when it has one.

Nothing the client sends drops an item unless the item is on the list:
a dropped item is a lost item (the operator's rule, 2026-09-12). The
built-in list is the foraged junk a training loop makes and discards
on purpose — ;mechlore's grass and the grass rope it braids — and
nothing else; settings.json's `droppable` (a list of item names as
typed after DROP MY) extends it for a character's own junk (the
remedies an order rejects: cream, salve, ointment, 2026-09-22). Every
script drops through drop() below, which refuses anything else with
an echo and sends nothing; a hand is freed with STOW, a load lightened
by stowing or banking coins, never by dropping.

A listed item goes into the room's trash receptacle when the listing
shows one (the operator, 2026-09-22): PUT MY <item> IN <bucket>, the
noun read off the parser's `room_objs` — the Crossing's streets keep
"a bucket", "a waste bin", "a large waste bucket", "a round metal
bucket", "a wooden bin", "a waste basket", "a garbage chute" (every
one seen in the game logs of 2026-09) — and DROP MY <item> only where
none stands. The receptacle's answer is uncaptured: one that reads as
a refusal ("What were you referring to?", "can't") falls back to the
DROP.

Names are matched whole, so "grass rope" is droppable and "rope" is
not — the bundling rope ;hunt's skins ride on is "bundling rope".
"""

import re

from client.settings import setting

DEFAULT_DROPPABLE = ("grass", "grass rope")

# The nouns a trash receptacle ends in, as the room listing names them.
# Whole words: "cabin" holds no bin.
RECEPTACLE = re.compile(
    r"\b(?:waste |garbage |trash |rubbish |refuse |metal |wooden |pine |large |round |small )*"
    r"(bucket|bin|basket|chute)\b",
    re.IGNORECASE,
)
PUT_REFUSALS = ("referring", "can't", "cannot", "won't fit", "no room")


def droppable_items() -> frozenset:
    """The built-in list plus settings.json's `droppable`, lowercased."""
    extra = setting("droppable") or []
    if isinstance(extra, str):
        extra = extra.split(",")
    names = [str(name).strip().lower() for name in extra if str(name).strip()]
    return frozenset(name.lower() for name in DEFAULT_DROPPABLE) | frozenset(names)


def droppable(item) -> bool:
    return str(item or "").strip().lower() in droppable_items()


def receptacle(room_objs):
    """The trash receptacle's noun in a room listing ("bucket" for "a
    wrought-iron bench and a bucket"), or None."""
    match = RECEPTACLE.search(room_objs or "")
    return match.group(1).lower() if match else None


def drop(s, item, ask):
    """Dispose of MY <item> through the script's ask(), when the item is
    on the list — into the room's receptacle when the listing shows
    one, else DROP; otherwise an echo saying so, nothing sent, and
    None."""
    if not droppable(item):
        s.echo(
            f"drop refused: {item!r} is not on the droppable list — stow it "
            "instead, or add it to settings.json's `droppable`"
        )
        return None
    bin_noun = receptacle(getattr(getattr(s, "state", None), "room_objs", ""))
    if bin_noun:
        answer = ask(s, f"put my {item} in {bin_noun}")
        if not any(word in (answer or "").lower() for word in PUT_REFUSALS):
            return answer
    return ask(s, f"drop my {item}")
