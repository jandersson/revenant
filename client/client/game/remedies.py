"""Remedies — the Alchemy craft behind ;remedies (#284): a dried herb
crushed in a mortar into a salve, step by step, each step teaching.

Captured 2026-09-22 at the Crossing Alchemy Society on a rank-2 Paladin
with the society's iron mortar and pestle, 25 dried nemoih and 10
splashes of water (the first live remedy; docs/training.md):

- A raw foraged flower crushes into powder ("You poorly crush the
  jadice flower into some jadice powder.", 10 s) and teaches nothing
  (Alchemy stayed 0/34): Pfanston's 2014 shortcut is gone. A dried
  herb from the society is what a salve starts from.
- Without the page studied: "You cannot figure out how to do that.
  Perhaps finding suitable ingredients and studying some instructions
  would help."
- The book: READ MY BOOK lists chapters; TURN MY BOOK TO CHAPTER 3
  ("External Wound Remedies": page 1 neck, 2 abdominal, 3 chest, 4
  head, 5 back, 6 eye salve); TURN MY BOOK TO PAGE 4 then READ gives
  the ingredients — "(5) prepared herb ... (1) splash of water (1)
  catalyst material"; STUDY MY BOOK: "You peruse the head salve
  instructions and quickly realize the design is far beyond your
  abilities.  You now feel ready to begin the crafting process."
  (12 s) — the warning and the readiness in one answer at rank 2.
- CRUSH MY NEMOIH IN MY MORTAR WITH MY PESTLE: "With short strokes you
  crush some unfinished nemoih salve with your pestle." then a mishap
  line ("The pestle slips and falls upon the dirty floor!  You hastily
  pick it back up.", "Your misguided mashes grind the plant material
  too finely, disrupting the mixture's balance.", "A poorly-timed
  sneeze contaminates the mixture!") and 17-20 s of roundtime; the
  first crush ended "You need another splash of water to continue
  crafting some unfinished nemoih salve.  You believe you can just
  pour or put it inside the mortar and continue crushing the
  unfinished remedy inside." — POUR MY WATER IN MY MORTAR: "You toss
  the water into the mortar and mix it in thoroughly." — and the
  second "As you finish, the mixture begins to transition colors."
  Alchemy went 0/34 clear to rank 3 60% dabbling in four crushes.
- The catalyst request and the finished salve are uncaptured (no
  catalyst on hand: seolarn weed wants foraging rank 70, coal comes
  from mines); the needles below are the pattern of the water line.
- Both hands are the tools': PUT and GET want a free hand ("You need a
  free hand to pick that up."), so the pestle is stowed for every
  fetch and taken back for the crush.

Elanthipedia: Remedies discipline, Remedies products, Crafting (the
first-step table), Work orders; Pfanston's Guide to Remedies for the
herb list. Sources: docs/bibliography.md.
"""

# Chapter 3 of the apprentice remedies book: page and herb per salve
# (Elanthipedia: Remedies products; the book read 2026-09-22).
SALVES = {
    "neck": (1, "georin"),
    "abdominal": (2, "nilos"),
    "chest": (3, "plovik"),
    "head": (4, "nemoih"),
    "back": (5, "hulnik"),
    "eye": (6, "sufil"),
}
CHAPTER = 3
HERB_SALVE = {herb: salve for salve, (_, herb) in SALVES.items()}

# Captured wordings (2026-09-22) — the outcomes CRUSH's answer is read for,
# failures before successes as probe.classify wants.
NO_INSTRUCTIONS = ("cannot figure out how to do that",)
NEED_WATER = ("need another splash of water", "splash of water to continue")
# Uncaptured: the catalyst's turn, by the water line's pattern.
NEED_CATALYST = ("catalyst",)
# Uncaptured: the salve done; the wiki's crafting pages say "you finish
# crafting" / "is complete" for other crafts.
FINISHED = ("finish crafting", "is complete", "you complete", "finished crafting")
CRUSHED = ("you crush some unfinished", "crush the", "crush some")
AS_CRUSHED = ("as crushed as it is going to get",)
MISSING = ("what were you referring", "could not find", "crush what")
FREE_HAND = ("need a free hand",)
STUDIED = ("feel ready to begin",)
TOO_HARD = ("far beyond your abilities",)
POURED = ("mix it in thoroughly", "toss the water")

CRUSH_OUTCOMES = (
    ("no instructions", NO_INSTRUCTIONS),
    ("missing", MISSING),
    ("free hand", FREE_HAND),
    ("as crushed", AS_CRUSHED),
    ("need water", NEED_WATER),
    ("need catalyst", NEED_CATALYST),
    ("finished", FINISHED),
    ("crushed", CRUSHED),
)


def parse_args(args):
    """{"salve", "until", "once", "count"} from ;remedies' arguments: the
    salve to make ("head" by default — nemoih, the herb the society
    sells dried and ;forage finds), until= the Alchemy mindstate to
    stop at (34), `once` to exit at the lock instead of holding,
    count= salves to finish before ending (0: until the lock)."""
    options = {"salve": "head", "until": 34, "once": False, "count": 0}
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "salve" and value in SALVES:
            options["salve"] = value
        elif not sep and key in SALVES:
            options["salve"] = key
        elif sep and key == "until" and value.isdigit():
            options["until"] = int(value)
        elif sep and key == "count" and value.isdigit():
            options["count"] = int(value)
        elif key == "once":
            options["once"] = True
    return options


def herb_for(salve):
    """The dried herb a salve wants: "nemoih" for the head salve."""
    return SALVES[salve][1]


def page_for(salve):
    return SALVES[salve][0]


def crush_command(herb, started):
    """CRUSH the herb the first time, the unfinished salve after."""
    what = "salve" if started else herb
    return f"crush my {what} in my mortar with my pestle"
