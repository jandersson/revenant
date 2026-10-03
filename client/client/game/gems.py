"""Loose gems into the gem pouch — an interlude chore (#437).

A gem goes loose when the pouch refuses it: the hunt's pocket and
;boxes put it with the loot, a STOW puts it in the default container.
Once the pouch had room again (TIEd, 70 → 500) nothing moved those
back: 16 sat in Cecil's straw tote and one in his backpack
(2026-10-03), pouched by hand at the operator's word.

The chore LOOKs IN the loot container and the default container
(STORE DEFAULT, read once), and for each gem noun listed GETs it FROM
that container and PUTs it, by its id, in the profile's `gem_pouch`.
The item that landed in hand is checked again: anything not a gem
goes back. A pouch that refuses (full) gets the gem back in its
container and the chore stops until a gem is pouched elsewhere
(`room()`) — the second pouch is #283. Never a DROP.

Due: the profile names a `gem_pouch` and a `loot_container`, the
containers may hold a loose gem (`dirty`: at a session's start and
whenever a gem went with the loot, `mark()`), and the pouch is not
known full. `;break gems` runs it now, whatever the flags say.
"""

from client.game import hands, items
from client.game.creatures import noun_of
from client.game.loot import GEM_NOUNS, POUCH_FULL, POUCHED

_GOT = ("you get", "you pick", "you remove")

# May a container hold a loose gem? Unknown at a session's start; set
# when a gem went with the loot, cleared by a run that moved them all.
# A full pouch stops the chore until a gem is pouched elsewhere. A
# reload of this module starts both over, which costs one LOOK.
_STATE = {"dirty": True, "full": False}


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
                    f"{container} (a second pouch is #283)"
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
    answer = ask(s, f"put {ref} in my {pouch}")
    lowered = answer.lower()
    if any(word in lowered for word in POUCHED) and not any(
        word in lowered for word in POUCH_FULL
    ):
        return name
    ask(s, f"put {ref} in my {container}")
    if items.no_room(answer) or any(word in lowered for word in POUCH_FULL):
        return "full"
    first = (answer.strip().splitlines() or ["(silence)"])[0]
    s.echo(f"{prefix}: the {pouch} answered {first!r} to the {name} — put back")
    return None
