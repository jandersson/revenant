"""The loot sweep — what the profile's `loot_ignore` names, taken out of
the loot container and put in the room's trash, beside a bin (#378).

;boxes trashes a `loot_ignore` item only as it comes out of a box, and
keeps it where no bin stands (#365); a hunt never pockets one now, but
what was kept stayed in the sack for good. The sweep is an interlude
chore (client/game/interlude.py): due once the profile's `loot_sweep`
is on, the container may hold such an item (at a session's start, and
whenever discard.trash() had to keep one) and the room shows a trash
receptacle. `;break sweep` is the dry run: it names what the sweep
would trash and moves nothing.

The guards, the operator's worry being a real item trashed (2026-09-28):
1. GET only `from my <loot_container>`, by the listed item's two-word
   name; never a worn item or another container.
2. The item that landed in hand — the parser's own name for it — is
   checked again, and anything the list does not name goes back.
3. Each item trashed is named in full.
4. A one-word entry takes only a metal lump ("copper" for "a copper
   nugget"): "needle" alone would take every needle, so the sweep says
   so and leaves it to ;hunt and ;boxes, which only never pick it up.
A PUT the bin refuses puts the item back. Never a DROP.
"""

import re

from client.game import discard, hands, items
from client.game.loot import METAL_FORMS, ignored, short_name

_GOT = ("you get", "you pick", "you remove")

# May the loot container hold an item the list names? Unknown at a
# session's start; set by discard.trash() keeping one, cleared by a
# sweep. A reload of this module starts it over, which costs one LOOK.
_STATE = {"dirty": True, "warned": False}


def mark():
    """An item the list names was kept (no bin): the next bin sweeps."""
    _STATE["dirty"] = True


def dirty():
    return _STATE["dirty"]


def listed_items(answer):
    """The items a LOOK IN answer lists, repeats kept; [] for an empty
    container; None when the answer is no listing (items.listed)."""
    return items.listed(answer)


def broad(ignore):
    """The one-word entries that are not common metals: the sweep takes
    them only as a metal lump, never as a name's last word."""
    from client.game.loot import COMMON_METALS

    return [
        str(entry).strip()
        for entry in ignore or ()
        if len(str(entry).split()) == 1
        and str(entry).strip().lower() not in COMMON_METALS
    ]


def sweepable(name, ignore):
    """True when the sweep may trash the item: an entry of two words or
    more ends its name, or a one-word entry names the metal of a lump
    (nugget, bar, ingot, ...)."""
    phrases = [entry for entry in ignore or () if len(str(entry).split()) > 1]
    if ignored(name, phrases):
        return True
    words = re.findall(r"[a-z'-]+", str(name or "").lower())
    if not words or words[-1] not in METAL_FORMS:
        return False
    singles = {str(e).strip().lower() for e in ignore or () if len(str(e).split()) == 1}
    return any(word in singles for word in words[:-1])


def _arrived(before, after):
    """The hand's item that was not there before the GET, or None."""
    for side, held in after.items():
        if held and (before.get(side) or {}).get("exist") != held.get("exist"):
            return held
    return None


def _warn(s, prefix, ignore):
    wide = broad(ignore)
    if wide:
        s.echo(
            f"{prefix}: {', '.join(wide)} — one word, so the sweep takes "
            "it only as a metal lump; name the item whole to sweep it"
        )


def run(s, profile, ask, prefix="sweep", dry=False):
    """LOOK IN the loot container and trash what the list names, beside
    a bin; `dry` only names it. The full names trashed (or, dry, the
    ones that would be)."""
    container = str(profile.get("loot_container") or "").strip()
    ignore = profile.get("loot_ignore") or []
    if not container:
        s.echo(f"{prefix}: no loot_container in the profile — nothing to sweep")
        return []
    if dry or not _STATE["warned"]:
        _warn(s, prefix, ignore)
        _STATE["warned"] = True
    answer = ask(s, f"look in my {container}")
    items = listed_items(answer)
    if items is None:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"{prefix}: could not read the {container} ({first!r}) — no sweep")
        return []
    doomed = [item for item in items if sweepable(item, ignore)]
    if dry:
        s.echo(
            f"{prefix}: would trash from the {container}: {', '.join(doomed)}"
            if doomed
            else f"{prefix}: nothing in the {container} that loot_ignore names"
        )
        return doomed
    _STATE["dirty"] = False
    trashed = []
    for item in doomed:
        name = sweep_one(s, item, container, ignore, ask, prefix)
        if name:
            trashed.append(name)
    return trashed


def sweep_one(s, item, container, ignore, ask, prefix):
    """GET the listed item from the container, check what came to hand,
    PUT it in the room's bin; the full name trashed, or None with the
    item back in the container, said."""
    wanted = short_name(item)
    before = hands.tags(s)
    answer = ask(s, f"get {wanted} from my {container}")
    held = _arrived(before, hands.tags(s))
    if held is None:
        if any(word in answer.lower() for word in _GOT):
            # Taken, but the hands show nothing new: back it goes, unseen.
            ask(s, f"put my {wanted} in my {container}")
            s.echo(f"{prefix}: could not see the {wanted} in hand — put back")
        else:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"{prefix}: no {wanted} came out of the {container} ({first!r})")
        return None
    name = str(held.get("name") or held.get("noun") or "")
    mine = short_name(name) or str(held.get("noun") or wanted)
    if not sweepable(name, ignore):
        ask(s, f"put my {mine} in my {container}")
        s.echo(f"{prefix}: got {name}, which loot_ignore does not name — put back")
        return None
    if discard.trash(s, mine, ask) is None:
        ask(s, f"put my {mine} in my {container}")
        s.echo(f"{prefix}: the bin would not take {name} — put back")
        return None
    s.echo(f"{prefix}: trashed {name} from the {container}")
    return name
