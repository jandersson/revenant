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

APPRAISE FOCUS <item> (200 ranks and up, #383) is a research-style
project beside the rotation: its breakthrough pays Appraisal and then
boosts the drain of the item's skill for 20 to 60 minutes by Appraisal
rank (a locked or trapped box: Locksmithing; yourself: Evasion; a
shield: Shield Usage; a concept word such as OFFENSE: Tactics) until
"Your focused insight of <skill> has been fully explored." One project
at a time, never beside a magical research project, and appraising
items does not interrupt it (Elanthipedia: Appraisal skill, Magical
research). Captured 2026-09-29: APPRAISE FOCUS CHECK with nothing
running, "You feel ready for any sort of appraisal focus.", and the
focus with a RESEARCH portion running, "You are already working on a
different research project." (the research went on). Still the wiki's
and dr-scripts' appraisal.lic's: the start "You carefully examine your
deobar coffer, focusing beyond any individual details. ...", the
CHECK's "You are currently ..." (a project runs) and "You have
completed ..." (the boost runs). appraisal.lic answers "You will lose
your progress" by sending the focus again; here it is a refusal, since
what would be lost is a research project.
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


# APPRAISE FOCUS (#383).
FOCUS_RANKS = 200
# Words APPRAISE FOCUS takes as concepts, not items (appraisal.lic's).
FOCUS_CONCEPTS = (
    "defense",
    "arcane",
    "recall",
    "logic",
    "offense",
    "magic",
    "khri",
    "inner fire",
)
# APPRAISE FOCUS <item>'s answer, the first match, lower-cased.
FOCUS_ANSWERS = (
    # Captured 2026-09-29 with a RESEARCH portion running: "You are
    # already working on a different research project." — read before
    # "running", which "you are already" also matches.
    ("research", ("you will lose your progress", "different research project")),
    ("running", ("you are already",)),
    ("boost", ("you currently feel",)),
    ("refused", ("you can't seem", "you cant seem", "you can not seem")),
    ("started", ("you carefully",)),
)
# APPRAISE FOCUS CHECK's answer.
FOCUS_CHECK = (
    ("running", ("you are currently",)),
    ("boost", ("you have completed",)),
)
# The project's lines as they arrive, in any answer.
FOCUS_EVENTS = (
    ("breakthrough", ("breakthrough!",)),
    ("explored", ("has been fully explored",)),
)


def _first(text, table):
    lowered = (text or "").lower()
    for outcome, phrases in table:
        if any(phrase in lowered for phrase in phrases):
            return outcome
    return None


def focus_command(item):
    """APPRAISE FOCUS MY <item>, or APPRAISE FOCUS <concept>."""
    item = str(item).strip().lower()
    if item in FOCUS_CONCEPTS or item.startswith(("#", "my ")):
        return f"appraise focus {item}"
    return f"appraise focus my {item}"


def focus_outcome(answer):
    """APPRAISE FOCUS's answer: "started", "running" (a project already),
    "boost" (the last one's boost still runs), "refused" (not a thing
    to focus on), "research" (a magical research project would be
    lost), or None for a wording the table lacks."""
    return _first(answer, FOCUS_ANSWERS)


def focus_check(answer):
    """APPRAISE FOCUS CHECK: "running", "boost", or None (no project and
    no boost, or a wording the table lacks)."""
    return _first(answer, FOCUS_CHECK)


def focus_events(text):
    """The focus lines in `text`, in table order: "breakthrough",
    "explored"."""
    lowered = (text or "").lower()
    return [
        event
        for event, phrases in FOCUS_EVENTS
        if any(phrase in lowered for phrase in phrases)
    ]


def parse_args(args):
    """{"items", "careful", "until", "once", "focus"} from ;appraise's
    arguments: items= a comma-separated list of your own ([] means the
    profile's, else the possessions), `careful` for full appraisals
    (QUICK otherwise), until= the mindstate to stop at (34), `once` to
    exit at the lock instead of holding for the drain, focus= the item
    or concept for APPRAISE FOCUS beside the rotation ("" for none)."""
    options = {
        "items": [],
        "careful": False,
        "until": 34,
        "once": False,
        "focus": "",
    }
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "items":
            options["items"] = [
                item.strip() for item in value.split(",") if item.strip()
            ]
        elif sep and key == "focus" and value.strip():
            options["focus"] = value.strip().replace("_", " ")
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
