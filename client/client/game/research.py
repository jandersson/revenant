"""Research that locks a magic skill: a Barbarian's MEDITATE RESEARCH
(the abilities studied per skill, the answers read, the next skill to
study) and a caster's magical research (the projects, the portion's
answers, RESEARCH STATUS read, Gauge Flow's mana). ;research
(scripts/research.py) is the loop.

A caster's magical research: with Gauge Flow up, RESEARCH <project>
<30-300 seconds> starts a portion; the portions add up to the project's
time (6.5 minutes for STREAM, 10 for AUGMENTATION, UTILITY and
WARDING, 5 for FUNDAMENTAL at a minimum-mana Gauge Flow, up to 20%
less at its cap of 100 mana) and only the breakthrough teaches: the
project's skill to 34/34, FUNDAMENTAL the magic skill and Arcana to
17/34 each. One project at a time. A cast, a PREPARE, a PLAY, a STUDY
or a fight loses the portion in hand; perceiving, appraising and
walking do not (Elanthipedia: Magical research, Gauge Flow). The
start patterns are dr-scripts' researcher.lic's, one per project's
wording. Captured 2026-09-29 on a Moon Mage, Gauge Flow at 98 mana
(DISCERN: "... for a total of 100 streams.", the Spells window
"Gauge Flow  (88 roisaen)"): RESEARCH STATUS idle "You're not
researching anything!", mid-portion "You believe that you're 36%
complete with a portion of research about Mana Stream Theory.  You
estimate that you will complete it a few minutes from now."; the
starts "You confidently begin to bend the mana streams ..."
(AUGMENTATION) and "You focus your magical perception as tightly as
possible, ..." (STREAM), no roundtime; pulses that end nothing ("You
continue to study the mana streams."); a portion's end "You make
definite progress in your project about Augmentation Patterns
Research and decide to take a break.  However, there is still more to
learn before you arrive at a breakthrough."; the last portion's start
"... only requires 182 more seconds of research, so you adjust your
plans accordingly."; the breakthrough "Breakthrough!" on its own line,
then "You have woven an Augmentation pattern ...", Augmentation 0 to
34/34 after 482 s of research. Still the wiki's: a lost portion
("Distracted by your spellcasting, you forget what you were
researching."). crossing-training recasts Gauge Flow below 20 minutes
left before a project.

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

import re

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


# --- A caster's magical research -------------------------------------

# project shorthand -> the skill its breakthrough locks. FUNDAMENTAL
# teaches the guild's magic skill beside Arcana, 17/34 each; Arcana is
# the pool it is chosen by.
PROJECTS = {
    "stream": "Attunement",
    "augmentation": "Augmentation",
    "utility": "Utility",
    "warding": "Warding",
    "fundamental": "Arcana",
}
CASTER_DEFAULT = ("stream", "augmentation", "utility", "warding")
# Words only a caster's research knows: the mode needs no guild then.
CASTER_WORDS = ("stream", "attunement", "fundamental", "arcana")
GAUGE_FLOW = "Gauge Flow"
GAUGE_MINUTES = 20  # crossing-training.lic's floor before a portion
GAUGE_CAP = 100  # the spell's cast cap (Elanthipedia: Gauge Flow)
PORTION_SECONDS = 300  # a portion's most; 30 its least
PORTION_SLACK = 30  # past a portion's length before the wait gives up

# RESEARCH <project> <seconds>, the answer's first match, lower-cased:
# researcher.lic's patterns. "busy" is a portion already running.
START_ANSWERS = (
    ("busy", ("you are already busy",)),
    ("blocked", ("you cannot begin",)),
    ("unknown", ("usage:", "you do not know how to research")),
    (
        "started",
        (
            "you tentatively",
            "you focus",
            "you confidently",
            "you expertly coach",
            "abandoning the normal",
            "you start to research",
            "you begin to bend",
            "with a mixture of rational concern",
        ),
    ),
)
# A portion's end, one line: crossing-training.lic's flags and the wiki.
PORTION_ENDS = (
    ("breakthrough", ("breakthrough!",)),
    ("portion", ("there is still more to learn before",)),
    (
        "lost",
        (
            "distracted by combat",
            "distracted by your spellcasting",
            "distracted by your devices",
            "you lose your focus on your research project",
            "you forget what you were",
        ),
    ),
)
# "you're 36% complete with a portion of research about ..." (captured
# mid-portion) or researcher.lic's "You have completed N% of a project".
_STATUS_PERCENT = re.compile(r"(\d+)% complete|completed (\d+)%")


def _first(answer, table):
    lowered = (answer or "").lower()
    for outcome, phrases in table:
        if any(phrase in lowered for phrase in phrases):
            return outcome
    return None


def start_outcome(answer):
    """RESEARCH <project>'s answer: "started", "busy", "blocked",
    "unknown", or None for a wording the table lacks."""
    return _first(answer, START_ANSWERS)


def portion_end(line):
    """ "breakthrough", "portion" (done, more to learn), "lost", or None
    for a line that ends nothing."""
    return _first(line, PORTION_ENDS)


def research_status(answer):
    """(project, percent) from RESEARCH STATUS: (None, None) when
    nothing is researched, ("other", percent) for a project this table
    does not hold (a symbiosis, SORCERY), the shorthand otherwise —
    crossing-training.lic reads the project by its name's word."""
    lowered = (answer or "").lower()
    if "not researching anything" in lowered:
        return None, None
    match = _STATUS_PERCENT.search(lowered)
    percent = int(match.group(1) or match.group(2)) if match else None
    if not match and "you estimate" not in lowered:
        return None, None  # no project in the answer at all
    for project in PROJECTS:
        if project in lowered:
            return project, percent
    return "other", percent


def project_named(word):
    """The project a word names — a shorthand, a skill ("attunement" is
    STREAM, "arcana" FUNDAMENTAL), a prefix ("aug") — or None."""
    word = word.strip().lower()
    if not word:
        return None
    for project, skill in PROJECTS.items():
        if project.startswith(word) or skill.lower().startswith(word):
            return project
    return None


def wants_caster(args):
    """True when the words name a project only a caster researches."""
    return any(
        str(arg).strip().lower().partition("=")[0] in CASTER_WORDS for arg in args
    )


def parse_caster_args(args):
    """{"projects", "until", "portion", "once"} from ;research's words
    for a caster: project words (stream, augmentation, utility, warding,
    fundamental, or the skills' names) in the order given, none meaning
    CASTER_DEFAULT; until= the mindstate to stop at; portion= the
    seconds per RESEARCH (30-300); `once`."""
    options = {
        "projects": [],
        "until": MIND_LOCK,
        "portion": PORTION_SECONDS,
        "once": False,
    }
    for arg in args:
        key, sep, value = str(arg).strip().lower().partition("=")
        if sep and key == "until" and value.isdigit():
            options["until"] = min(int(value), MIND_LOCK)
        elif sep and key == "portion" and value.isdigit():
            options["portion"] = max(30, min(int(value), PORTION_SECONDS))
        elif not sep and key == "once":
            options["once"] = True
        elif not sep and (project := project_named(key)) is not None:
            if project not in options["projects"]:
                options["projects"].append(project)
    if not options["projects"]:
        options["projects"] = list(CASTER_DEFAULT)
    return options


def gauge_mana(estimate, step):
    """The mana to prepare Gauge Flow with, from DISCERN's (minimum,
    total) estimate: one `step` under the total, never past the cast
    cap — more mana shortens the research — and 0 (the minimum, a bare
    PREPARE) without an estimate or with no room above the minimum."""
    if estimate is None:
        return 0
    minimum, total = estimate
    mana = min(total - step, GAUGE_CAP)
    return mana if mana > minimum else 0
