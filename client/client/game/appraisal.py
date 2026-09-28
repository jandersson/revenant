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
bundle first, and each pouch or bundle one level inside a worn or held
container besides: the game refuses one where it lies, so it is taken
into a hand by its game id, appraised and put back (targets(), #382).
An item teaches once and then not for a while — one gem pouch took
Appraisal 0 -> 2/34 at rank 1205 and eighteen repeats after it nothing,
while nine tied pouches in turn took it 2 -> 14 and the first pouch
taught again twelve minutes on (2026-09-28) — so each item waits
ITEM_WAIT between its appraisals. dr-scripts' appraisal.lic trains the
same way, cycling a list of the character's items with APPRAISE ... QUICK. One item
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

import re

QUICK = "quick"
CAREFUL = "careful"
# Nouns that teach most, first in the rotation when the character has one.
FAVORED = ("pouch", "bundle")

# An item the game finds nowhere on you (the inventory refusals ;hunt
# and ;perform hold, and APPRAISE's own "Appraise what?  Type APPRAISE
# HELP for more information.", captured 2026-09-11): out of the rotation.
NOT_FOUND = ("what were you referring", "could not find", "don't have", "appraise what")
# An item a container holds, refused where it lies (captured 2026-09-28,
# a gem pouch in a hunting pack): "You can't appraise the fuzzy gem pouch
# in there." — read before REFUSED, which "can't appraise" also matches.
IN_CONTAINER = ("in there",)
# Answers that teach nothing (captured 2026-09-28 on untied gem pouches):
# a closed one, "You'll need to open the fuzzy gem pouch to examine its
# contents.", and an empty one, "There doesn't appear to be anything in
# the fuzzy gem pouch." A tied pouch reads its gems' worth unopened.
CLOSED = ("need to open",)
EMPTY = ("doesn't appear to be anything in",)
# Seconds an item waits between appraisals: a repeat within two minutes
# taught nothing, the same pouch twelve minutes later did (2026-09-28);
# ten is inside that window, to be narrowed by a measurement.
ITEM_WAIT = 600
# The answers of a GET and a PUT that did what was asked.
TAKEN = ("you get", "you pick", "you remove", "already holding")
PUT_BACK = ("you put",)
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


# Where an item's name turns from what it is to how it looks: "a large
# hunting pack crafted from wyvern hide" is a large hunting pack. The
# listing's last word is no noun for such a name, so labels are cut
# here instead (#382: Crannach's rotation echoed "pouch in the hide x37").
_DESCRIBED = re.compile(
    r"\s+(?:crafted|with|bearing|made|of|from|embroidered|trimmed|painted|"
    r"covered|surmounted|displaying|engraved|sealed|tipped|inlaid|wrapped|"
    r"artfully|stitched|decorated|patterned|etched|streaked|studded|set|"
    r"topped|carved|embellished|bound|lined|edged|fit)\b.*$",
    re.IGNORECASE,
)


def label_of(item):
    """What an item is called in the echoes: its name without the
    article, a trailing "(closed)" or its description; the noun when
    the listing gave no name."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", str(item.get("name") or "")).split()
    if name and name[0].lower() in ("a", "an", "some", "the"):
        name = name[1:]
    short = _DESCRIBED.sub("", " ".join(name)).strip()
    return short or str(item.get("noun") or "").strip()


def _target(label, noun, ref, key, fetch=None, back=None):
    return {
        "label": label,
        "noun": noun,
        "ref": ref,
        "fetch": fetch,
        "back": back,
        "key": key,
    }


def targets(possessions, items=()):
    """What to appraise, in order: [{"label", "noun", "ref", "fetch",
    "back", "key"}]. `items` given: each as MY <noun>. Else the last INV
    LIST's possessions: everything worn or held — by its game id
    (#<exist>) when the listing gave one, so twins are two items — and
    each pouch or bundle one level inside a worn or held container,
    fetched with GET #<id> IN #<container> and put back after (#382);
    FAVORED first, those inside after the ones worn."""
    if items:
        nouns = dict.fromkeys(str(item).strip() for item in items if str(item).strip())
        return [_target(noun, noun, f"my {noun}", noun) for noun in nouns]
    possessions = possessions or []
    holders = {item.get("exist"): item for item in possessions if item.get("exist")}
    top, inside, nouns = [], [], set()
    for item in possessions:
        noun = str(item.get("noun") or "").strip()
        exist = item.get("exist")
        if not noun:
            continue
        if item.get("depth", 0) == 0:
            if exist:
                top.append(_target(label_of(item), noun, f"#{exist}", exist))
            elif noun not in nouns:
                nouns.add(noun)
                top.append(_target(noun, noun, f"my {noun}", noun))
            continue
        holder = holders.get(item.get("container_exist"))
        if (
            item.get("depth") == 1
            and noun in FAVORED
            and exist
            and holder is not None
            and holder.get("depth", 0) == 0
        ):
            where = f"#{holder['exist']}"
            inside.append(
                _target(
                    f"{label_of(item)} in the {label_of(holder)}",
                    noun,
                    f"#{exist}",
                    exist,
                    fetch=f"get #{exist} in {where}",
                    back=f"put #{exist} in {where}",
                )
            )
    favored = [target for target in top if target["noun"] in FAVORED]
    rest = [target for target in top if target["noun"] not in FAVORED]
    return favored + inside + rest


def appraise_command(noun, careful=False):
    """APPRAISE MY <noun> QUICK — CAREFUL for the full look; a game id
    (#<exist>) or a "my ..." phrase is used as given."""
    ref = noun if str(noun).startswith(("#", "my ")) else f"my {noun}"
    return f"appraise {ref} {CAREFUL if careful else QUICK}"
