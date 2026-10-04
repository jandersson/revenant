"""Trading cards into the card collector's case — an interlude chore (#457).

The hunt picks a searched card up and stows it like loot; this chore
moves each one into the worn case. CARDS works only with the case open
in the right hand and the card in the left (Elanthipedia: Trading
cards; captured on 2026-10-04): REMOVE the case ("You remove a card
collector's case from your belt."), OPEN it, GET the card, CARDS ADD
("You slide a Guildleader Kalika card into your case."), then CLOSE
and WEAR it ("You attach a card collector's case to your belt.").

The cards: INV LIST's (`s.state.possessions`, by id, any container
but the case) and those a LOOK IN of the loot and default containers
lists since. Anything whose noun is "card" is tried — the 150 names
follow no one pattern ("The Kitchen card", "a Famous Faces ... card")
— and the game is the judge: an item CARDS ADD does not take goes
back where it came from. Every card goes in, duplicates too (CARDS
DUPLICATES lists them). It needs both hands empty and never stows a
weapon to make them so (#439): it waits for a safe point with both
free. A ;stop mid-chore wears the case again.

Due: the profile names a `card_case` and a container may hold a card
(`dirty`: at a session's start and whenever the hunt pockets one,
`mark()`). `;break cards` runs it now.
"""

from client.game import hands, items
from client.game.creatures import noun_of

# The case's answers (captured 2026-10-04).
REMOVED = ("you remove",)
OPENED = ("you open", "is already open")
ADDED = ("you slide",)
WORN = ("you attach",)
_GOT = ("you get", "you pick", "you remove")

_STATE = {"dirty": True}
# The INV LIST ids tried this session: the listing is from login, and a
# card added since is not got again.
_TRIED = set()


def mark():
    """A card went with the loot: the next safe point looks."""
    _STATE["dirty"] = True


def due(profile):
    """True when the chore should run on its own now."""
    return bool(str(profile.get("card_case") or "").strip()) and _STATE["dirty"]


def is_card(name):
    return noun_of(name) == "card"


def case_ref(s, profile):
    """The case as a command names it: its INV LIST id when the listing
    shows it, else MY <card_case>."""
    word = str(profile.get("card_case") or "").strip().lower()
    for item in getattr(getattr(s, "state", None), "possessions", None) or []:
        if item.get("exist") and word in str(item.get("name") or "").lower():
            return f"#{item['exist']}"
    return f"my {word}"


def listed_cards(s, case):
    """The ids of the cards INV LIST shows outside the case: "#id"s."""
    exist = case[1:] if case.startswith("#") else None
    return [
        f"#{item['exist']}"
        for item in getattr(getattr(s, "state", None), "possessions", None) or []
        if item.get("exist")
        and is_card(str(item.get("name") or ""))
        and (exist is None or str(item.get("container_exist")) != exist)
        and str(item["exist"]) not in _TRIED
    ]


def _first(answer):
    return (str(answer or "").strip().splitlines() or ["(silence)"])[0]


def _said(answer, words):
    lowered = str(answer or "").lower()
    return any(word in lowered for word in words)


def run(s, profile, ask, prefix="cards"):
    """Every card on the character into the case; the names added. Waits
    (says so, stays due) unless both hands are empty."""
    word = str(profile.get("card_case") or "").strip()
    if not word:
        s.echo(f"{prefix}: no card_case in the profile — nothing to do")
        return []
    if not hands.empty(s):
        s.echo(f"{prefix}: both hands must be empty for the case — the cards wait")
        return []
    case = case_ref(s, profile)
    answer = ask(s, f"remove {case}")
    if not _said(answer, REMOVED):
        s.echo(f"{prefix}: the {word} did not come off ({_first(answer)!r})")
        return []
    added = []
    try:
        answer = ask(s, f"open {case}")
        if not _said(answer, OPENED):
            s.echo(f"{prefix}: the {word} did not open ({_first(answer)!r})")
            return []
        for ref in listed_cards(s, case):
            _TRIED.add(ref[1:])
            name = _add(s, ask, prefix, f"get {ref}", None)
            if name:
                added.append(name)
        for container in containers(s, profile, ask):
            answer = ask(s, f"look in my {container}")
            for item in [item for item in items.listed(answer) or [] if is_card(item)]:
                words = item.split()
                noun = (
                    " ".join(words[-2:]) if len(words) > 2 else noun_of(item)
                ).lower()
                name = _add(
                    s, ask, prefix, f"get {noun} from my {container}", container
                )
                if name:
                    added.append(name)
        _STATE["dirty"] = False
    finally:
        _put_on(s, case, word, ask, prefix)
    if added:
        s.echo(f"{prefix}: {len(added)} card(s) into the {word}: {', '.join(added)}")
    return added


def containers(s, profile, ask):
    """The loot container, then the default container when it is
    another one."""
    found = []
    for name in (
        str(profile.get("loot_container") or "").strip().lower(),
        hands.default_container(s, ask),
    ):
        if name and name not in found:
            found.append(name)
    return found


def _add(s, ask, prefix, get, container):
    """GET a card into the left hand and CARDS ADD it: its name when it
    went into the case, else None — the item put back, said."""
    before = hands.tags(s)
    answer = ask(s, get)
    held = _arrived(before, hands.tags(s))
    if held is None:
        if _said(answer, _GOT):
            s.echo(f"{prefix}: could not see the card in hand ({_first(answer)!r})")
        return None
    name = str(held.get("name") or held.get("noun") or "card")
    answer = ask(s, "cards add")
    if _said(answer, ADDED):
        return name
    ref = f"#{held['exist']}" if held.get("exist") else f"my {held.get('noun')}"
    ask(s, f"put {ref} in my {container}" if container else f"stow {ref}")
    s.echo(f"{prefix}: the case would not take {name} ({_first(answer)!r}) — put back")
    return None


def _arrived(before, after):
    """The hand's item that was not there before the GET, or None."""
    for side, held in after.items():
        if held and (before.get(side) or {}).get("exist") != held.get("exist"):
            return held
    return None


def _put_on(s, case, word, ask, prefix):
    """CLOSE and WEAR the case — after a ;stop too (a cleanup put)."""
    try:
        ask(s, f"close {case}")
        answer = ask(s, f"wear {case}")
    except Exception:
        hands.cleanup(s, f"wear {case}")
        raise
    if not _said(answer, WORN):
        s.echo(f"{prefix}: the {word} is still in hand ({_first(answer)!r}) — wear it")
