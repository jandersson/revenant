"""A Barbarian's MEDITATE RESEARCH: the abilities studied per skill, the
answers read, the next skill to study. ;research (scripts/research.py)
is the loop.

MEDITATE RESEARCH <ability> is "the Barbarian equivalent of magic
research": it teaches the skill of the named ability — Augmentation,
Warding or Utility — whether or not the ability is known, costs a
moderate roundtime and has a cooldown of about a minute; an ability
that trains Debilitation teaches nothing researched, since Debilitation
is a combat skill learned only against an opponent (Elanthipedia:
Barbarian new player guide, Meditations). The default ability per skill
is dr-scripts' combat-trainer.lic's "Barb Research" picks — MONKEY
(Monkey Form, Augmentation), TURTLE (Turtle Form, Warding), PREDICTION
(Prediction, Utility; the skills from Elanthipedia's Barbarian/Ability
Tree) — and its two patterns are this module's table.

Captured 2026-09-26 on a circle-1 Barbarian with no abilities learned:
"You clear your mind and begin to meditate upon the training you have
received." / "Roundtime: 8 sec." (6 to 10 s over five researches), and
a few seconds later "You recall that Monkey Form is a Basic ability in
the Path of the Flame.  Practicing these movement styles will ..." —
"Turtle Form is an Expert ability" for TURTLE. Each research put the
skill at dabbling (Augmentation 1.00 to 1.04, Warding 0.00 to 0.07)
and taught Inner Fire as well (learning, then perusing to attentive;
Inner Fire ranked 1 to 2 within two minutes). The pool was clear
again before the next research a minute on, so the skills keep tying
at 0 and a tie goes to the skill researched longest ago — the first
live run alternated MONKEY and TURTLE and never reached PREDICTION
while a tie went to the first named. Researches 61 s apart drew no
cooldown answer. Still uncaptured: "What did you want to research"
(combat-trainer's) and the non-Barbarian's "You attempt to meditate,
but have trouble concentrating." (Elanthipedia: Meditate command).
Qt-free, reloadable.
"""

# The ability researched per skill when the arguments name none.
DEFAULT_ABILITIES = {
    "Augmentation": "monkey",
    "Warding": "turtle",
    "Utility": "prediction",
}
SKILLS = tuple(DEFAULT_ABILITIES)
MIND_LOCK = 34
GAP_SECONDS = 60  # the guide's "cooldown of about ~1 minute"

# (outcome, phrases) — the answer's first match, lower-cased.
ANSWERS = (
    ("begun", ("you clear your mind and begin to meditate",)),
    ("unknown", ("what did you want to research",)),
    ("not a barbarian", ("have trouble concentrating",)),
)


def research_command(ability):
    """The command that researches `ability`."""
    return f"meditate research {ability.strip().lower()}"


def classify(answer):
    """The outcome of a MEDITATE RESEARCH answer — "begun", "unknown",
    "not a barbarian" — or None for a wording the table lacks."""
    lowered = (answer or "").lower()
    for outcome, phrases in ANSWERS:
        if any(phrase in lowered for phrase in phrases):
            return outcome
    return None


def _skill_named(word):
    """The skill a word names ("aug", "Warding"), or None."""
    word = word.strip().lower()
    if not word:
        return None
    for skill in SKILLS:
        if skill.lower().startswith(word):
            return skill
    return None


def parse_args(args):
    """{"abilities", "until", "gap", "once"} from ;research's arguments.

    A skill word ("augmentation", "warding", "util") picks that skill
    with its default ability; "skill=ability" ("augmentation=buffalo")
    picks it with that ability; none of either means all three skills.
    until= the mindstate to stop at (34), gap= the seconds between
    researches (60), `once` to exit at the lock instead of holding for
    the drain. Words it does not know are left out."""
    options = {"abilities": {}, "until": MIND_LOCK, "gap": GAP_SECONDS, "once": False}
    for arg in args:
        key, sep, value = str(arg).strip().lower().partition("=")
        if sep and key == "until" and value.isdigit():
            options["until"] = min(int(value), MIND_LOCK)
        elif sep and key == "gap" and value.isdigit():
            options["gap"] = int(value)
        elif not sep and key == "once":
            options["once"] = True
        elif (skill := _skill_named(key)) is not None:
            ability = value.strip() if sep else ""
            options["abilities"][skill] = ability or DEFAULT_ABILITIES[skill]
    if not options["abilities"]:
        options["abilities"] = dict(DEFAULT_ABILITIES)
    return options


def next_skill(mindstates, until, researched=None):
    """The skill to research next: the emptiest pool among those below
    `until`; on a tie the one researched longest ago — never researched
    first, then the first named; None when every one is there.
    `mindstates` maps skill to mindstate, None for a skill the exp
    window does not list yet (a pool never filled: 0); `researched`
    maps skill to the round it was last researched in."""
    researched = researched or {}
    open_skills = [
        (value or 0, researched.get(skill, -1), index, skill)
        for index, (skill, value) in enumerate(mindstates.items())
        if (value or 0) < until
    ]
    return min(open_skills)[3] if open_skills else None
