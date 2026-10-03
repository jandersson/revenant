"""Loose gems into the gem pouch — an interlude chore (#437).

A gem goes loose when the pouch refuses it: the hunt's pocket and
;boxes put it with the loot, a STOW puts it in the default container.
Once the pouch had room again (TIEd, 70 → 500) nothing moved those
back: 16 sat in Cecil's straw tote and one in his backpack
(2026-10-03), pouched by hand at the operator's word.

The chore LOOKs IN the loot container and the default container
(STORE DEFAULT, read once), and for each gem noun listed GETs it FROM
that container and PUTs it, by its id, in a gem pouch (`put()`). The
item that landed in hand is checked again: anything not a gem goes
back. With every pouch full the gem goes back in its container and
the chore stops until a gem is pouched elsewhere (`room()`). Never a
DROP.

The pouch is named by its id too (#456): MY POUCH is whichever pouch
the game finds first, and with a worn tied pouch and a spare in the
backpack (#437), or a second pouch once the first is full (#283),
that is the wrong one. INV LIST's links give every pouch's id
(`s.state.possessions`); `put()` tries the worn ones first, then the
rest in the listing's order, and remembers for the session each one
that answered full — a tied pouch never gives a gem back. Without a
listing that shows a pouch it names MY <gem_pouch>, as before.

Due: the profile names a `gem_pouch` and a `loot_container`, the
containers may hold a loose gem (`dirty`: at a session's start and
whenever a gem went with the loot, `mark()`), and the pouch is not
known full. `;break gems` runs it now, whatever the flags say.
"""

import re

from client.game import hands, items
from client.game.act import NOT_FOUND
from client.game.creatures import noun_of
from client.game.loot import GEM_NOUNS, POUCH_FULL, POUCHED

_GOT = ("you get", "you pick", "you remove")

# May a container hold a loose gem? Unknown at a session's start; set
# when a gem went with the loot, cleared by a run that moved them all.
# A full pouch stops the chore until a gem is pouched elsewhere. A
# reload of this module starts both over, which costs one LOOK.
_STATE = {"dirty": True, "full": False}
# The pouches, by id, that answered full this session: skipped by
# `put()` until a reload of this module forgets them.
_FULL = set()


def mark():
    """A gem went with the loot: the next safe point looks."""
    _STATE["dirty"] = True


def room():
    """A gem went into the pouch: it has room again."""
    _STATE["full"] = False


def due(profile):
    """True when the chore should run on its own now."""
    pouch = str(profile.get("gem_pouch") or "").strip()
    container = str(profile.get("loot_container") or "").strip()
    if not pouch or not container:
        return False
    return _STATE["dirty"] and not _STATE["full"]


def is_gem(name):
    return noun_of(name) in GEM_NOUNS


def pouches(s, profile):
    """The gem pouches a gem may go in, as a command names them —
    "#145599919" — worn first, then in INV LIST's order, those that
    answered full this session left out. The profile's `gem_pouch`
    names them; among several matches only the gem pouches count (a
    coin pouch is no place for a gem). Without a listing that shows one:
    ["my <gem_pouch>"], whichever the game finds first; [] with no
    `gem_pouch`."""
    word = str(profile.get("gem_pouch") or "").strip().lower()
    if not word:
        return []
    pattern = re.compile(rf"\b{re.escape(word)}\b")
    found = [
        item
        for item in getattr(getattr(s, "state", None), "possessions", None) or []
        if item.get("exist") and pattern.search(str(item.get("name") or "").lower())
    ]
    found = [item for item in found if "gem" in item["name"].lower().split()] or found
    if not found:
        return [f"my {word}"]
    found.sort(key=lambda item: not item.get("worn"))  # stable: worn first
    return [f"#{item['exist']}" for item in found if str(item["exist"]) not in _FULL]


def by_id(s, profile):
    """True when INV LIST showed a gem pouch with room, so `put()` names
    the pouches by id rather than MY <gem_pouch> — the one STORE GEMS
    just found full."""
    return any(target.startswith("#") for target in pouches(s, profile))


def pouched(answer):
    """True when the PUT's answer says the gem went into the pouch."""
    lowered = str(answer or "").lower()
    return any(word in lowered for word in POUCHED) and not full(answer)


def full(answer):
    """True when the PUT's answer says the pouch has no room."""
    lowered = str(answer or "").lower()
    return items.no_room(answer) or any(word in lowered for word in POUCH_FULL)


def put(s, profile, ref, ask):
    """PUT the held gem (`ref`: "#id" or "my <noun>") in the first gem
    pouch with room: (True, the answer) when one took it, else (False,
    the last answer). A pouch that answers full is remembered and the
    next one tried; one the game no longer knows (the listing is from
    login) is passed over, MY <gem_pouch> tried last in its stead;
    any other refusal ends it."""
    targets = pouches(s, profile)
    answer = ""
    stale = False
    for target in targets:
        answer = ask(s, f"put {ref} in {target}")
        if pouched(answer):
            return True, answer
        if full(answer):
            if target.startswith("#"):
                _FULL.add(target[1:])
            continue
        if target.startswith("#") and any(
            word in str(answer).lower() for word in NOT_FOUND
        ):
            stale = True
            continue
        return False, answer
    fallback = f"my {str(profile.get('gem_pouch') or '').strip().lower()}"
    if stale and fallback not in targets:
        answer = ask(s, f"put {ref} in {fallback}")
        return pouched(answer), answer
    return False, answer


def _arrived(before, after):
    """The hand's item that was not there before the GET, or None."""
    for side, held in after.items():
        if held and (before.get(side) or {}).get("exist") != held.get("exist"):
            return held
    return None


def _ref(held):
    """The PUT's name for the item in hand: its id, else MY <noun>."""
    exist = str(held.get("exist") or "")
    return f"#{exist}" if exist else f"my {held.get('noun')}"


def containers(s, profile, ask):
    """The loot container, then the default container when it is
    another one; never the pouch itself."""
    pouch = str(profile.get("gem_pouch") or "").strip().lower()
    found = []
    for name in (
        str(profile.get("loot_container") or "").strip().lower(),
        hands.default_container(s, ask),
    ):
        if name and name != pouch and name not in found:
            found.append(name)
    return found


def run(s, profile, ask, prefix="gems"):
    """Every loose gem in the containers into the pouch; the names
    moved. A full pouch stops it (said) with the rest left where they
    are."""
    pouch = str(profile.get("gem_pouch") or "").strip()
    if not pouch:
        s.echo(f"{prefix}: no gem_pouch in the profile — nothing to do")
        return []
    _STATE["full"] = False  # tried now: the PUT says whether it is
    moved = []
    for container in containers(s, profile, ask):
        answer = ask(s, f"look in my {container}")
        listed = items.listed(answer)
        if listed is None:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"{prefix}: could not read the {container} ({first!r})")
            continue
        for item in [item for item in listed if is_gem(item)]:
            outcome = pouch_one(s, item, container, pouch, ask, prefix)
            if outcome == "full":
                _STATE["full"] = True
                s.echo(
                    f"{prefix}: the {pouch} is full — the loose gems stay in the "
                    f"{container} (carry a spare pouch, #283)"
                )
                _say(s, prefix, pouch, moved)
                return moved
            if outcome:
                moved.append(outcome)
    _STATE["dirty"] = False
    _say(s, prefix, pouch, moved)
    return moved


def _say(s, prefix, pouch, moved):
    if moved:
        s.echo(
            f"{prefix}: {len(moved)} loose gem(s) into the {pouch}: {', '.join(moved)}"
        )


def pouch_one(s, item, container, pouch, ask, prefix):
    """GET the listed gem from the container, check what came to hand,
    PUT it in the pouch: its name when pouched, "full" when the pouch
    refused it (the gem back in the container), None otherwise, said."""
    noun = noun_of(item)
    before = hands.tags(s)
    answer = ask(s, f"get {noun} from my {container}")
    held = _arrived(before, hands.tags(s))
    if held is None:
        if any(word in answer.lower() for word in _GOT):
            ask(s, f"put my {noun} in my {container}")
            s.echo(f"{prefix}: could not see the {noun} in hand — put back")
        else:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"{prefix}: no {noun} came out of the {container} ({first!r})")
        return None
    name = str(held.get("name") or held.get("noun") or noun)
    ref = _ref(held)
    if not is_gem(name):
        ask(s, f"put {ref} in my {container}")
        s.echo(f"{prefix}: got {name}, which is no gem — put back")
        return None
    ok, answer = put(s, {"gem_pouch": pouch}, ref, ask)
    if ok:
        return name
    ask(s, f"put {ref} in my {container}")
    if full(answer):
        return "full"
    first = (answer.strip().splitlines() or ["(silence)"])[0]
    s.echo(f"{prefix}: the {pouch} answered {first!r} to the {name} — put back")
    return None
