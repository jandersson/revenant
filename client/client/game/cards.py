"""Collectibles into their worn cases — trading cards (#457) and Imperial
diras (#459) — an interlude chore each.

The hunt picks a searched card or dira up and stows it like loot; this
chore moves each one into its case. The case works only open in the
right hand with the item in the left (Elanthipedia: Trading cards, Dira
command; captured on 2026-10-04): REMOVE the case ("You remove a card
collector's case from your belt."), OPEN it, GET the item, CARDS ADD or
DIRA ADD ("You slide a Guildleader Kalika card into your case.", "You
slide an Imperial dira into your case at slot 59."), then CLOSE and WEAR
it ("You attach a coin case to your belt.").

The items: INV LIST's (`s.state.possessions`, by id, any container
but the case) and those a LOOK IN of the loot and default containers
lists since — looked for first, so the case stays on the belt when
there is none. Anything with the kind's noun is tried — the 150 card
names follow no one pattern ("The Kitchen card", "a Famous Faces ...
card") — and the game is the judge: an item the case does not take goes
back where it came from. Every one goes in, duplicates too (CARDS
DUPLICATES, DIRA DUPLICATE list them). It needs both hands empty and
never stows a weapon to make them so (#439): it waits for a safe point
with both free. A ;stop mid-chore wears the case again.

Due: the profile names the kind's case (`card_case`, `dira_case`) and a
container may hold one (`dirty`: at a session's start and whenever the
hunt pockets one, `mark(noun)`). `;break cards` / `;break dira` runs it
now.
"""

from client.game import hands, items
from client.game.creatures import noun_of

# The collections, by the item's noun: the profile key naming the worn
# case, the command that adds the item held in the left hand, and the
# word the echoes count with.
KINDS = {
    "card": {"case": "card_case", "add": "cards add", "label": "card(s)"},
    "dira": {"case": "dira_case", "add": "dira add", "label": "dira(s)"},
}

# The cases' answers (captured 2026-10-04, both cases alike).
REMOVED = ("you remove",)
OPENED = ("you open", "is already open")
ADDED = ("you slide",)
WORN = ("you attach",)
_GOT = ("you get", "you pick", "you remove")

# May a container hold one, per kind? Unknown at a session's start; set
# when the hunt pockets one, cleared by a run that moved them all.
_STATE = {kind: True for kind in KINDS}
# The INV LIST ids tried this session: the listing is from login, and an
# item added since is not got again.
_TRIED = set()


def mark(noun=None):
    """An item went with the loot: the next safe point looks — for its
    kind, or every kind with no noun."""
    for kind in KINDS:
        if noun is None or noun == kind:
            _STATE[kind] = True


def case_word(profile, kind="card"):
    return str(profile.get(KINDS[kind]["case"]) or "").strip()


def due(profile, kind="card"):
    """True when the kind's chore should run on its own now."""
    return bool(case_word(profile, kind)) and _STATE[kind]


def is_item(name, kind="card"):
    return noun_of(name) == kind


def is_card(name):
    return is_item(name, "card")


def case_ref(s, profile, kind="card"):
    """The case as a command names it: its INV LIST id when the listing
    shows it, else MY <case>."""
    word = case_word(profile, kind).lower()
    for item in getattr(getattr(s, "state", None), "possessions", None) or []:
        if item.get("exist") and word in str(item.get("name") or "").lower():
            return f"#{item['exist']}"
    return f"my {word}"


def listed(s, case, kind="card"):
    """The ids of the kind's items INV LIST shows outside the case."""
    exist = case[1:] if case.startswith("#") else None
    return [
        f"#{item['exist']}"
        for item in getattr(getattr(s, "state", None), "possessions", None) or []
        if item.get("exist")
        and is_item(str(item.get("name") or ""), kind)
        and (exist is None or str(item.get("container_exist")) != exist)
        and str(item["exist"]) not in _TRIED
    ]


def _first(answer):
    return (str(answer or "").strip().splitlines() or ["(silence)"])[0]


def _said(answer, words):
    lowered = str(answer or "").lower()
    return any(word in lowered for word in words)


def run(s, profile, ask, prefix="cards", kind="card"):
    """Every item of the kind on the character into its case; the names
    added. Waits (says so, stays due) unless both hands are empty."""
    word = case_word(profile, kind)
    key = KINDS[kind]["case"]
    if not word:
        s.echo(f"{prefix}: no {key} in the profile — nothing to do")
        return []
    if not hands.empty(s):
        s.echo(f"{prefix}: both hands must be empty for the case — it waits")
        return []
    case = case_ref(s, profile, kind)
    gets = found(s, profile, ask, case, kind)
    if not gets:
        _STATE[kind] = False  # nothing to add: the case stays on the belt
        return []
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
        for get, container in gets:
            if get.startswith("get #"):
                _TRIED.add(get[5:])
            name = _add(s, ask, prefix, get, container, kind)
            if name:
                added.append(name)
        _STATE[kind] = False
    finally:
        _put_on(s, case, word, ask, prefix)
    if added:
        label = KINDS[kind]["label"]
        s.echo(f"{prefix}: {len(added)} {label} into the {word}: {', '.join(added)}")
    return added


def found(s, profile, ask, case, kind="card"):
    """The GETs that fetch each item of the kind outside the case, with
    the container it goes back to (None: STOW): INV LIST's by id, then
    those a LOOK IN of the loot and default containers lists. Nothing
    leaves a container yet."""
    gets = [(f"get {ref}", None) for ref in listed(s, case, kind)]
    for container in containers(s, profile, ask):
        answer = ask(s, f"look in my {container}")
        for item in [it for it in items.listed(answer) or [] if is_item(it, kind)]:
            words = item.split()
            noun = (" ".join(words[-2:]) if len(words) > 2 else noun_of(item)).lower()
            gets.append((f"get {noun} from my {container}", container))
    return gets


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


def _add(s, ask, prefix, get, container, kind="card"):
    """GET an item into the left hand and ADD it: its name when it went
    into the case, else None — the item put back, said."""
    before = hands.tags(s)
    answer = ask(s, get)
    held = _arrived(before, hands.tags(s))
    if held is None:
        if _said(answer, _GOT):
            s.echo(f"{prefix}: could not see the {kind} in hand ({_first(answer)!r})")
        return None
    name = str(held.get("name") or held.get("noun") or kind)
    answer = ask(s, KINDS[kind]["add"])
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
