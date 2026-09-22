"""Classes — TEACH and LISTEN, the model behind ;teach and ;listen
(2026-09-22): a teacher offers a skill, a student joins, both learn
until one of them moves.

Captured 2026-09-22 in the Paladins' Guild Chambers, a Thief teaching
a Paladin Scholarship: TEACH SCHOLARSHIP TO CECIL — "You begin to
lecture Cecil on the proper use of the Scholarship skill." (the
student sees "Masah begins to lecture you on the proper usage of the
Scholarship skill.  To learn from him, you must LISTEN TO Masah.");
LISTEN TO MASAH — "You begin to listen to Masah teach the Scholarship
skill."; the student walking off, on the teacher's side — "All of
your students have left, so you stop teaching." The student learns
the skill taught and Scholarship, LISTEN <teacher> OBSERVE weights it
toward Scholarship, and an offer not taken up expires on its own
(Elanthipedia: Teach command, Listen command). Both sides asked
again mid-class: TEACH — "Cecil is already listening to you.  He
needs to STOP LISTENING before you can teach him." (the class is
up); LISTEN — "You are already listening to someone.  You may wish
to STOP LISTENING." (in it; the skill is then the argument's or
Scholarship). Uncaptured, read by shape: a LISTEN with no class
offered, a skill the teacher cannot give, the student's line when
the teacher stops, and STOP TEACHING's and STOP LISTENING's answers.
"""

import re

# The teacher's answers to TEACH, failures before successes.
TEACHING = ("you begin to lecture",)
ALREADY_TEACHING = ("already teaching", "already listening to you")
CANNOT_TEACH = (
    "not skilled enough",
    "don't know enough",
    "cannot teach",
    "unable to teach",
)
NO_STUDENT = ("what were you referring", "could not find", "who are you")
STUDENTS_LEFT = ("all of your students have left",)
TEACH_OUTCOMES = (
    ("no student", NO_STUDENT),
    ("cannot", CANNOT_TEACH),
    ("already", ALREADY_TEACHING),
    ("teaching", TEACHING),
)

# The student's answers to LISTEN, failures before successes.
LISTENING = ("you begin to listen to",)
ALREADY_LISTENING = ("already listening",)
NO_CLASS = (
    "not teaching",
    "isn't teaching",
    "no one is teaching",
    "nobody is teaching",
    "not offering",
    "what were you referring",
    "could not find",
)
CLASS_ENDED = (
    "stops teaching",
    "you stop listening",
    "class has ended",
    "no longer teaching",
    "stopped teaching",
)
LISTEN_OUTCOMES = (
    ("no class", NO_CLASS),
    ("already", ALREADY_LISTENING),
    ("listening", LISTENING),
)
TAUGHT = re.compile(
    r"teach the (?P<skill>[\w' ]+?) skill|us(?:e|age) of the (?P<skill2>[\w' ]+?) skill",
    re.I,
)


def teach_command(skill, student=None):
    """TEACH <skill> TO <student>, or TEACH <skill> OPEN for anyone."""
    if student:
        return f"teach {skill} to {student}"
    return f"teach {skill} open"


def listen_command(teacher, observe=False):
    return f"listen to {teacher}" + (" observe" if observe else "")


def taught_skill(text):
    """The skill a class is in, off either side's line ("teach the
    Scholarship skill", "use of the Scholarship skill"), or None."""
    match = TAUGHT.search(text or "")
    if not match:
        return None
    return (match.group("skill") or match.group("skill2")).strip()


def parse_teach_args(args):
    """{"skill", "student"} from `;teach scholarship to cecil` or
    `;teach scholarship open`; a skill of several words keeps them."""
    words = [str(arg).strip() for arg in args if str(arg).strip()]
    lowered = [word.lower() for word in words]
    student = None
    if "to" in lowered:
        cut = lowered.index("to")
        student = " ".join(words[cut + 1 :]) or None
        words = words[:cut]
    elif lowered and lowered[-1] == "open":
        words = words[:-1]
    return {"skill": " ".join(words), "student": student}


def parse_listen_args(args):
    """{"teacher", "skill", "until", "once", "observe"} from `;listen
    masah [scholarship] [until=30] [once] [observe]`: the skill named
    is the one whose mindstate the hold watches, else the class's."""
    options = {"teacher": "", "skill": "", "until": 34, "once": False, "observe": False}
    rest = []
    for arg in args:
        word = str(arg).strip()
        key, sep, value = word.lower().partition("=")
        if sep and key == "until" and value.isdigit():
            options["until"] = int(value)
        elif key == "once":
            options["once"] = True
        elif key == "observe":
            options["observe"] = True
        elif word:
            rest.append(word)
    if rest:
        options["teacher"] = rest[0]
        options["skill"] = " ".join(rest[1:])
    return options
