"""Appraising your own things — the model behind ;appraise (#275).

Appraisal trains by APPRAISE <item>: every appraisal of an item on you
teaches the skill at any rank, and the most per look comes from a
valuable or many-part item — a full gem pouch, a bundle, a weapon, a
piece of armor — else "appraise all of your inventory, the more
valuable, the better" (Elanthipedia: Appraisal skill). QUICK cuts the
roundtime (down to 2 s with ranks against 4 s plain or CAREFUL;
Elanthipedia: Appraise command). Creatures teach nothing below 76
ranks and other players are never appraised ("uncouth"), so the
rotation is the character's own possessions: the profile's
`appraisal_items` when set, else the parser's `possessions` at depth 0
— worn and held, exact as of the last INV LIST — with a gem pouch and a
bundle first. dr-scripts' appraisal.lic trains the same way, cycling a
list of the character's items with APPRAISE ... QUICK. One item
appraisal is captured (2026-09-11, a plate mask at Appraisal rank 2,
by hand): the hindrance lines, "You guess that the plate mask is highly
protected against damage and is in pristine condition.", "It appears
that the plate mask can be worn on the nose.", "The plate mask has a
bit of weight to it.", "You are confident that the plate mask is worth
about 193 Kronars." and "Roundtime: 8 sec." — the certainty words
("guess", "confident", the wiki's "certain") grade with the ranks, so
;appraise reads no success wording: any answer that is not a refusal
below is an appraisal, and the first of a run is echoed so more become
fixtures. Model: docs/training.md.
"""

QUICK = "quick"
CAREFUL = "careful"
# Nouns that teach most, first in the rotation when the character has one.
FAVORED = ("pouch", "bundle")

# An item the game finds nowhere on you (the inventory refusals ;hunt
# and ;perform hold, and APPRAISE's own "Appraise what?  Type APPRAISE
# HELP for more information.", captured 2026-09-11): out of the rotation.
NOT_FOUND = ("what were you referring", "could not find", "don't have", "appraise what")
# An item APPRAISE will not look at (wording uncaptured; the verbs the
# game uses for a refused command elsewhere): dropped from the rotation.
REFUSED = (
    "cannot appraise",
    "can't appraise",
    "unable to appraise",
    "not something you can",
)


def parse_args(args):
    """{"items", "careful", "until", "once"} from ;appraise's arguments:
    items= a comma-separated list of your own ([] means the profile's,
    else the possessions), `careful` for full appraisals (QUICK
    otherwise), until= the mindstate to stop at (34), `once` to exit at
    the lock instead of holding for the drain."""
    options = {"items": [], "careful": False, "until": 34, "once": False}
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "items":
            options["items"] = [
                item.strip() for item in value.split(",") if item.strip()
            ]
        elif sep and key == "until" and value.isdigit():
            options["until"] = int(value)
        elif key == "careful":
            options["careful"] = True
        elif key == "once":
            options["once"] = True
    return options


def rotation(possessions, items=()):
    """The nouns to appraise, in order: `items` as given when any; else
    the possessions' nouns at depth 0 (worn and held, the containers and
    not what they hold), FAVORED nouns first, each noun once, in the
    listing's order. [] when there is nothing to go on."""
    if items:
        return list(
            dict.fromkeys(str(item).strip() for item in items if str(item).strip())
        )
    nouns = []
    for item in possessions or []:
        if item.get("depth", 0) != 0:
            continue
        noun = str(item.get("noun") or "").strip()
        if noun and noun not in nouns:
            nouns.append(noun)
    favored = [noun for noun in nouns if noun in FAVORED]
    return favored + [noun for noun in nouns if noun not in FAVORED]


def appraise_command(noun, careful=False):
    """APPRAISE MY <noun> QUICK — CAREFUL for the full look."""
    return f"appraise my {noun} {CAREFUL if careful else QUICK}"
