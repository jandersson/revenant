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
back. A worn pouch that answered full is TIEd in place when untied (70
becomes 500) or swapped for the spare INV LIST showed (the spare worn,
tied first if it is the untied full one; the full one taken off and
stowed; STORE GEMS reset — #283). With every pouch full the gem goes
back in its container and
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

from client.game import hands, items, stores
from client.game.act import NOT_FOUND, missing
from client.game.creatures import noun_of
from client.game.loot import GEM_NOUNS, POUCH_FULL, POUCHED

_GOT = ("you get", "you pick", "you remove")
# A pouch WORN (captured 2026-10-03): "You attach a black gem pouch to
# your belt."; STORE GEMS reset (2026-09-26): "You will now store gems in
# your black gem pouch."
WORN = ("you attach", "you put on", "you wear", "you slip", "you hang", "you tie")
STORED = ("you will now store",)
_REFUSED = ("free hand", "can't", "cannot", "unable")

# May a container hold a loose gem? Unknown at a session's start; set
# when a gem went with the loot, cleared by a run that moved them all.
# A full pouch stops the chore until a gem is pouched elsewhere. A
# reload of this module starts both over, which costs one LOOK.
_STATE = {"dirty": True, "full": False}
# The pouches, by id, that answered full this session: skipped by
# `put()` until a reload of this module forgets them.
_FULL = set()
# Of those, the ones that answered the untied pouch's full ("wealth of
# gems", 70): a TIE makes room (500) — the operator's rule, 2026-10-03.
_UNTIED = set()


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
    found = _listed(s, word)
    if not found:
        return [f"my {word}"]
    return [f"#{item['exist']}" for item in found if str(item["exist"]) not in _FULL]


def _listed(s, word):
    """The gem pouches INV LIST showed, worn first (stable), as the
    listing's own dicts — the `worn` flag is updated by swap()."""
    pattern = re.compile(rf"\b{re.escape(word)}\b")
    found = [
        item
        for item in getattr(getattr(s, "state", None), "possessions", None) or []
        if item.get("exist") and pattern.search(str(item.get("name") or "").lower())
    ]
    found = [item for item in found if "gem" in item["name"].lower().split()] or found
    found.sort(key=lambda item: not item.get("worn"))
    return found


def worn_full(s, profile):
    """True when the worn gem pouch answered full this session and a TIE
    or a swap can make room: the worn one is untied (a TIE in place), or
    another listed pouch has room or is untied (#283)."""
    word = str(profile.get("gem_pouch") or "").strip().lower()
    listed = _listed(s, word) if word else []
    worn = next((item for item in listed if item.get("worn")), None)
    if worn is None or str(worn["exist"]) not in _FULL:
        return False
    if str(worn["exist"]) in _UNTIED:
        return True
    return _spare(listed, worn) is not None


def _spare(listed, worn):
    """The pouch to swap in: one with room first, else an untied full one
    (a TIE makes room), never the worn one; None without."""
    others = [item for item in listed if item is not worn]
    for item in others:
        if str(item["exist"]) not in _FULL:
            return item
    for item in others:
        if str(item["exist"]) in _UNTIED:
            return item
    return None


def swap(s, profile, ask, prefix="gems"):
    """Room for gems again when the worn pouch answered full (#283): an
    untied worn pouch is TIEd in place (REMOVE, TIE, WEAR — 70 becomes
    500, the operator's rule of 2026-10-03); a tied one is swapped for
    the spare INV LIST showed — the spare GOT (TIEd first when it is the
    untied full one), WORN, the full one REMOVEd and STOWed, STORE GEMS
    pointed at the pouch again (the operator, 2026-10-07: "swap with the
    spare"). One free hand does it, one item at a time. False, said,
    with no spare or a refusal; a pouch taken off goes back on. Never a
    DROP."""
    word = str(profile.get("gem_pouch") or "").strip().lower()
    listed = _listed(s, word) if word else []
    worn = next((item for item in listed if item.get("worn")), None)
    if worn is None:
        s.echo(f"{prefix}: no worn {word} in the listing — nothing to swap")
        return False
    if str(worn["exist"]) in _UNTIED:
        return _tie_worn(s, worn, word, ask, prefix)
    spare = _spare(listed, worn)
    if spare is None:
        s.echo(
            f"{prefix}: the {word} is full and no spare {word} is on you — ask the "
            "appraiser for one (#283)"
        )
        return False
    answer = ask(s, f"get #{spare['exist']}")
    if _refused(answer):
        s.echo(f"{prefix}: the spare {word} did not come to hand ({_first(answer)!r})")
        return False
    if str(spare["exist"]) in _UNTIED and not _tie(s, spare, word, ask, prefix):
        hands.stow(s, f"#{spare['exist']}", ask=ask)
        return False
    answer = ask(s, f"wear #{spare['exist']}")
    if _refused(answer):
        hands.stow(s, f"#{spare['exist']}", ask=ask)
        s.echo(f"{prefix}: could not wear the spare {word} ({_first(answer)!r})")
        return False
    answer = ask(s, f"remove #{worn['exist']}")
    if _refused(answer):
        s.echo(f"{prefix}: could not take the full {word} off ({_first(answer)!r})")
        return False
    if not hands.stow(s, f"#{worn['exist']}", ask=ask):
        ask(s, f"wear #{worn['exist']}")
        s.echo(f"{prefix}: nowhere to stow the full {word} — worn again")
    stored = any(
        w in str(ask(s, f"store gems in {word}") or "").lower() for w in STORED
    )
    worn["worn"] = False
    spare["worn"] = True  # the listing, until the next INV LIST
    _FULL.discard(str(spare["exist"]))
    _STATE["full"] = False
    s.echo(
        f"{prefix}: the full {word} swapped for the spare — worn now"
        + ("" if stored else ", STORE GEMS not reset: STORE GEMS IN POUCH by hand")
    )
    return True


def _tie_worn(s, worn, word, ask, prefix):
    """The untied worn pouch TIEd in place: REMOVE, TIE, WEAR."""
    answer = ask(s, f"remove #{worn['exist']}")
    if _refused(answer):
        s.echo(
            f"{prefix}: could not take the {word} off to tie it ({_first(answer)!r})"
        )
        return False
    tied = _tie(s, worn, word, ask, prefix)
    ask(s, f"wear #{worn['exist']}")
    return tied


def _tie(s, pouch, word, ask, prefix):
    """TIE the held untied full pouch: 70 gems become a tied 500 (permanent;
    the operator's rule). True unless refused; the pouch leaves _FULL."""
    answer = ask(s, f"tie #{pouch['exist']}")
    if _refused(answer):
        s.echo(f"{prefix}: could not tie the full {word} ({_first(answer)!r})")
        return False
    _UNTIED.discard(str(pouch["exist"]))
    _FULL.discard(str(pouch["exist"]))
    _STATE["full"] = False
    s.echo(f"{prefix}: the full {word} tied off — it holds 500 now (#283)")
    return True


def _refused(answer):
    lowered = str(answer or "").lower()
    return missing(answer) or any(word in lowered for word in _REFUSED)


def _first(answer):
    return (str(answer or "").strip().splitlines() or ["(silence)"])[0]


def by_id(s, profile):
    """True when INV LIST showed a gem pouch with room, so `put()` names
    the pouches by id rather than MY <gem_pouch> — the one STORE GEMS
    just found full."""
    return any(target.startswith("#") for target in pouches(s, profile))


def pouched(answer):
    """True when the PUT's answer says the gem went into the pouch."""
    lowered = str(answer or "").lower()
    return any(word in lowered for word in POUCHED) and not full(answer)


def untied_full(answer):
    """True for the untied pouch's full — "You've already got a wealth of
    gems in there!  You'd better tie it up..." — which a TIE cures."""
    return "wealth of gems" in str(answer or "").lower()


def full(answer):
    """True when the PUT's answer says the pouch has no room."""
    lowered = str(answer or "").lower()
    return items.no_room(answer) or any(word in lowered for word in POUCH_FULL)


def put(s, profile, ref, ask):
    """The held gem (`ref`: "#id" or "my <noun>") into a gem pouch:
    (True, the answer) when one took it, else (False, the last answer).
    STOW first when the hunt's stores file says STORE GEMS points at
    the pouch — one command, the game's own routing, no listing needed
    (the operator, 2026-10-07: "doesn't STOW GEM work better than PUT
    MY X IN MY Y?"); its full answer marks the worn pouch. Then PUT in
    the listed pouches by id: a pouch that answers full is remembered
    and the next one tried; one the game no longer knows (the listing
    is from login) is passed over, MY <gem_pouch> tried last in its
    stead; any other refusal ends it."""
    word = str(profile.get("gem_pouch") or "").strip().lower()
    if word and _store_is_pouch(s, word):
        answer = ask(s, f"stow {ref}")
        lowered = str(answer or "").lower()
        if pouched(answer) and word in lowered:
            return True, answer
        if full(answer):
            worn = next((item for item in _listed(s, word) if item.get("worn")), None)
            if worn is not None:
                _FULL.add(str(worn["exist"]))
                if untied_full(answer):
                    _UNTIED.add(str(worn["exist"]))
        elif "you put" in lowered:
            return False, answer  # STORE sent it elsewhere: not in hand now
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
                if untied_full(answer):
                    _UNTIED.add(target[1:])
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


def _store_is_pouch(s, word):
    """True when ;hunt last set STORE GEMS at the profile's pouch
    (client/game/stores.py), so a bare STOW of a gem reaches it."""
    name = getattr(getattr(s, "state", None), "name", None)
    return str(stores.load(name).get("gems") or "").strip().lower() == word


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
            if worn_full(s, profile) and swap(s, profile, ask, prefix):
                if outcome == "full":
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
