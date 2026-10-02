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
- The Society's bought "(25 pieces) dried red flowers" do not answer to
  the word "dried" at all (#420, 2026-10-02: GET MY DRIED FLOWERS and
  LOOK AT MY DRIED FLOWERS not found, MY RED FLOWERS and MY FLOWERS
  resolving them, INV SEARCH listing two); the dry press's stacks do.
  `get_dried` reaches a stack by whichever name works: "dried <herb>"
  first, then the plain noun's ordinals with the GET's answer judging.
"""

import re

from client.game import act, hands, items
from client.game.remedies import pieces

STACK_CAP = 75
MERGED = ("you combine the stacks",)
LEFT_OVER = ("some was left over",)
FULL = ("too large to add more to",)
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


_SOURCE = re.compile(r"from (?:inside )?your ([a-z' -]+?)[.,]", re.IGNORECASE)


def get_dried(s, ask, herb, container=None):
    """GET a dried stack of `herb` ("flowers") into a hand by the name
    that reaches it: MY DRIED <herb> first (the dry press's stacks answer
    to it), then the plain noun's ordinals container by container, the
    GET's own answer judging — a stack whose answer lacks "dried" (a
    fresh one, jadice flowers) goes back where it came from, to the
    container's front, and the next ordinal reaches past it (#420).
    `container` names the one to walk; without it every container INV
    LIST shows is walked in turn, the gem pouch left out — a bare MY
    SECOND <herb> took nothing while a bought stack sat in the backpack
    (2026-10-02, 17:36), the merge's FROM MY <container> form reaches it
    (#402). The GET's answer, or None when no dried stack came."""
    where = f" from my {container}" if container else ""
    mine = "" if container else "my "
    answer = ask(s, f"get {mine}dried {herb}{where}")
    if not act.missing(answer):
        return answer  # silence passes, as the plain GET's did before
    if container is None:
        possessions = getattr(getattr(s, "state", None), "possessions", None)
        places = items.containers(possessions, skip=("pouch",)) if possessions else []
        for place in places:
            found = _walk(s, ask, herb, place)
            if found is not None:
                return found
        if places:
            return None
    return _walk(s, ask, herb, container)


def _walk(s, ask, herb, container):
    """The plain noun's ordinals in `container` (none: the bare form),
    a stack that is not dried put back to the front; the GET's answer
    for the first dried one, else None."""
    where = f" from my {container}" if container else ""
    mine = "" if container else "my "
    for skip, ordinal in enumerate(ORDINALS):
        before = set(held(s))
        which = f"{ordinal} " if ordinal else ""
        answer = ask(s, f"get {mine}{which}{herb}{where}")
        if not answer.strip() or act.missing(answer):
            return None
        if "dried" in answer.lower():
            return answer
        # Another kind of the same noun: back to where it came from.
        new = [item for item in held(s) if item not in before]
        token = f"#{new[0]}" if len(new) == 1 else f"my {herb}"
        source = _SOURCE.search(answer)
        back = (source.group(1).split()[-1] if source else None) or container
        if back:
            ask(s, f"put {token} in my {back}")
        else:
            hands.stow(s, token if token.startswith("#") else herb, ask=ask)
    return None


def dried_herbs(listing):
    """The dried herbs a LOOK IN answer lists more than once, by their
    whole name ("dried red flowers"), in listing order."""
    counts = {}
    for name in _DRIED.findall(listing or ""):
        name = name.strip().lower()
        counts[name] = counts.get(name, 0) + 1
    return [name for name, count in counts.items() if count > 1]


def held(s):
    """{exist: name} for what the hands hold, off the parser's hand tags
    (hands.tags), left then right."""
    return {
        str(tag["exist"]): str(tag.get("name") or "").lower()
        for tag in hands.tags(s).values()
        if tag and tag.get("exist")
    }


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
        if act.missing(answer):
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
