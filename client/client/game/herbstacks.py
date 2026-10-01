"""Herb stacks merged: every stack of a dried herb in a container
combined into full stacks and at most one short one (#402).

Stacks come apart in many places — the mortar takes 25 pieces of a
bigger one, a pressed find runs over the cap, a refused combine keeps
two — and nothing joined them again: Cecil carried 15 stacks of dried
red flowers on 2026-10-01 while ;remedies foraged for more. ;remedies
merges before every run, and `;remedies merge` on its own.

How a stack behaves (an experiment on Cecil's dried red flowers,
2026-10-01, #402; held its first test that day):

- A stack holds at most STACK_CAP (75) pieces.
- COMBINE, a stack in each hand, answers "You combine the stacks of
  herbs together." (one stack left, in the left hand, a new item),
  "You combine the stacks of herbs together, but some was left over."
  (a full stack and the rest, two new items), or "That stack of herbs is
  too large to add more to." (one was full; nothing moves).
- A held item answers to its id: COUNT #<exist>, PUT #<exist> IN MY
  BACKPACK, COMBINE #<a> WITH #<b>, the id the hand tags carry — the
  merge never relies on which stack a bare noun names (the one just
  fetched, or the rest after an overflow: not settled). A merge or an
  overflow gives new ids; the rest of an overflow lands in the left hand.
- A hand tag's name can drop an adjective: flowers dried at the society's
  press tag as "red flowers" while GET and LOOK call them "some dried red
  flowers", and they combine with bought ones. The GET's answer, not the
  tag, says what came out.
- A stack PUT back goes to the front of the container. An ordinal on the
  noun alone (GET MY NINTH FLOWERS) reaches every item of that noun; one
  with an adjective (MY FIFTH DRIED FLOWERS) stops at the first other
  kind — fresh red flowers and jadice flowers are "flowers" too — so the
  merge counts plain nouns and reads the GET's answer for the herb.
"""

import re

from client.game.remedies import pieces

STACK_CAP = 75
MERGED = ("you combine the stacks",)
LEFT_OVER = ("some was left over",)
FULL = ("too large to add more to",)
_MISSING = ("what were you referring", "could not find")
ORDINALS = (
    "",
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
_DRIED = re.compile(r"\b(?:some|an?) (dried [a-z' -]+?)(?=,| and |\.|$)", re.IGNORECASE)


def dried_herbs(listing):
    """The dried herbs a LOOK IN answer lists more than once, by their
    whole name ("dried red flowers"), in listing order."""
    counts = {}
    for name in _DRIED.findall(listing or ""):
        name = name.strip().lower()
        counts[name] = counts.get(name, 0) + 1
    return [name for name, count in counts.items() if count > 1]


def _missing(answer):
    lowered = str(answer or "").lower()
    return any(word in lowered for word in _MISSING)


def held(s):
    """{exist: name} for what the hands hold, off the parser's hand tags."""
    state = getattr(s, "state", None)
    found = {}
    for side in ("left_hand", "right_hand"):
        hand = getattr(state, side, None)
        if isinstance(hand, dict) and hand.get("exist"):
            found[str(hand["exist"])] = str(hand.get("name") or "").lower()
    return found


def merge(s, ask, herb, container):
    """Every stack of `herb` ("dried red flowers") in `container` merged,
    both hands free on entry and on return: full stacks and other kinds
    of the same noun go back to the front, the next GET reaches past
    them by ordinal, and the short stack held takes the next one into it.
    (stacks found, stacks left), or None when an answer or a hand was not
    what the experiment saw — what is in hand put back, nothing lost."""
    noun = herb.split()[-1]
    skip = 0  # items put back at the container's front
    found = 0
    kept = 0  # the herb's own stacks among them
    short = None  # the id of the short stack held

    def put(item, herb_stack=True):
        nonlocal skip, kept
        ask(s, f"put #{item} in my {container}")
        skip += 1
        kept += herb_stack

    def count(item):
        return pieces(ask(s, f"count #{item}")) or 0

    def give_up():
        for item in held(s):
            ask(s, f"put #{item} in my {container}")
        return None

    while skip < len(ORDINALS):
        which = f"{ORDINALS[skip]} " if skip else ""
        answer = ask(s, f"get my {which}{noun} from my {container}")
        if _missing(answer):
            break
        fetched = [item for item in held(s) if item != short]
        if len(fetched) != 1:
            return give_up()
        item = fetched[0]
        if herb not in answer.lower():
            put(item, herb_stack=False)  # another kind of the same noun
            continue
        found += 1
        if short is None:
            if count(item) >= STACK_CAP:
                put(item)
            else:
                short = item
            continue
        joined = ask(s, f"combine #{item} with #{short}").lower()
        if any(word in joined for word in FULL):
            put(item)  # the short one is under the cap: this one is full
        elif any(word in joined for word in MERGED):
            stacks = list(held(s))
            if len(stacks) == 1:
                short = stacks[0]
                if count(short) >= STACK_CAP:
                    put(short)
                    short = None
            elif len(stacks) == 2 and any(word in joined for word in LEFT_OVER):
                full = next((x for x in stacks if count(x) >= STACK_CAP), None)
                if full is None:
                    return give_up()
                put(full)
                short = next(x for x in stacks if x != full)
            else:
                return give_up()
        else:
            return give_up()
    if short is not None:
        put(short)
    return found, kept
