"""Store items in the Carousel vault, or take them out:  ;vault

    ;vault put <item>[, <item> ...]   walk to the vault and put each item in
    ;vault get <item>[, <item> ...]   take each item out and stow it
    ;vault list                       what the vault holds
    ;vault put ... back               then walk back to where it started (any verb)

What it does
  - Walks to the profile's `vault` (a ;go2 target), else the nearest Carousel.
  - In: GO ARCH, PULL LEVER, GO DOOR, OPEN VAULT. Out, every time: CLOSE VAULT,
    GO DOOR, GO ARCH, back at the Carousel.
  - put: each item is got into a hand and put in by its id.
  - get: each item comes out into a hand and is stowed.
  - Name an item by adjective and noun ("leather compendium"): a bare noun
    takes the first item of it.

When it stops
  - every item done, or one not found (said, the rest still tried)
  - a walk that fails, the attendant, the lever or the vault refusing (said)
  - both hands full at the start, or death

The way in and the game's wordings are client/game/vault.py's; docs/vault.md.
"""

from client.game import hands, travel, vault
from client.game.act import ask, missing, said, unknown

_NOTES = """
Built from Cecil's visits of 2026-10-03 and 2026-10-04 (the runestones,
a scroll, a compendium), every step captured by hand first: the arches
are interchangeable (GO ARCH takes the platinum one, the blackwood one
answered the same), the booth's lever opens the chamber's door, and the
chamber has no exits but the door back to the booth. RUMMAGE answers
"You rummage through a secure vault and see ...". Elanthipedia: Vaults
(rent: 5,000 Kronars a month at the Carousel's desk).
"""


def parse_args(args):
    words = [str(arg) for arg in args or []]
    back = any(word.lower() == "back" for word in words)
    words = [word for word in words if word.lower() != "back"]
    verb = words[0].lower() if words else ""
    return {"verb": verb, "items": vault.items_of(words[1:]), "back": back}


def _title(s):
    return str(getattr(s.state, "room_title", "") or "").lower()


def enter(s, place):
    """From the Carousel to the open vault; None there, else why not.
    `place` tracks how far in the character got: "carousel", "booth",
    "chamber", "open"."""
    answer = ask(s, "go arch")
    if not vault.said(answer, vault.ESCORTED):
        return f"the attendant did not take you in ({said(answer)!r})"
    place[0] = "booth"
    answer = ask(s, "pull lever")
    if not vault.said(answer, vault.LEVER):
        return f"the lever did not open the door ({said(answer)!r})"
    ask(s, "go door")
    if vault.CHAMBER not in _title(s):
        return "the door did not lead into the vault's chamber"
    place[0] = "chamber"
    answer = ask(s, "open vault")
    if not vault.said(answer, vault.OPENED):
        unknown(s, "vault", "open", answer)
        return "the vault did not open"
    place[0] = "open"
    return None


def leave(s, place):
    """Back out to the Carousel from wherever `place` says."""
    if place[0] == "open":
        ask(s, "close vault")
        place[0] = "chamber"
    if place[0] == "chamber":
        ask(s, "go door")
        place[0] = "booth"
    if place[0] == "booth":
        answer = ask(s, "go arch")
        if vault.said(answer, vault.LEFT) or vault.BOOTH not in _title(s):
            place[0] = "carousel"


def _arrived(before, after):
    """The hand's item that was not there before, or None."""
    for side, held in after.items():
        if held and (before.get(side) or {}).get("exist") != held.get("exist"):
            return held
    return None


def _held_named(s, item):
    """A held item whose name holds every word of `item`, or None."""
    words = item.lower().split()
    for held in hands.tags(s).values():
        name = str((held or {}).get("name") or "").lower()
        if held and all(word in name.split() for word in words):
            return held
    return None


def put_in(s, item):
    """GET the item into a hand and PUT it in the vault by its id; True
    when stored."""
    before = hands.tags(s)
    answer = ask(s, f"get my {item}")
    held = _arrived(before, hands.tags(s)) or _held_named(s, item)
    if held is None or not held.get("exist"):
        s.echo(f"vault: no {item} on you ({said(answer)!r})")
        return False
    answer = ask(s, f"put #{held['exist']} in vault")
    if not vault.said(answer, vault.STORED):
        s.echo(f"vault: the {item} did not go in ({said(answer)!r})")
        return False
    s.echo(f"vault: the {held.get('name') or item} is in the vault")
    return True


def take_out(s, item):
    """GET the item from the vault and STOW it; True when taken."""
    before = hands.tags(s)
    answer = ask(s, f"get {item} from vault")
    if missing(answer) or not vault.said(answer, vault.TAKEN):
        s.echo(f"vault: no {item} in the vault ({said(answer)!r})")
        return False
    held = _arrived(before, hands.tags(s))
    name = (held or {}).get("name") or item
    if held and held.get("exist") and hands.stow(s, f"#{held['exist']}", ask):
        s.echo(f"vault: the {name} is out and stowed")
    else:
        s.echo(f"vault: the {name} is out — in hand")
    return True


def run(s, options, profile, db=None, walk=None):
    verb, wanted = options["verb"], options["items"]
    if verb not in ("put", "get", "list") or (verb != "list" and not wanted):
        s.echo("vault: ;vault put <item>[, <item>], ;vault get <item>, ;vault list")
        return "usage"
    if verb != "list" and hands.full(s):
        s.echo("vault: both hands are full — the items need one")
        return "hands full"
    db = db or travel.mapdb()
    start = travel.here(s, db)
    target = str(profile.get("vault") or "").strip() or vault.CAROUSEL
    if not travel.go(s, target, "the vault", db=db, walk=walk):
        return "no walk to the vault"
    place = ["carousel"]
    done = 0
    try:
        why = enter(s, place)
        if why:
            s.echo(f"vault: {why} — stopping")
            return why
        if verb == "list":
            names = vault.contents(ask(s, "rummage vault"))
            if names is None:
                s.echo("vault: the rummage listed nothing")
            else:
                s.echo(f"vault: {len(names)} item(s): " + ", ".join(names))
        for item in wanted:
            done += put_in(s, item) if verb == "put" else take_out(s, item)
    finally:
        leave(s, place)
    if verb != "list":
        what = "stored" if verb == "put" else "taken out"
        s.echo(f"vault: {done} of {len(wanted)} item(s) {what}")
    if options["back"] and start is not None:
        travel.go(s, {start}, "where you started", db=db, walk=walk)
    return "done"


def main(s):
    from client.game.profile import load_profile

    profile = load_profile(getattr(s.state, "name", None) or "")
    run(s, parse_args(s.args), profile)
