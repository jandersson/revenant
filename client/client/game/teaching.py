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
Scholarship). STOP LISTENING (captured 2026-09-22): the student sees
"You stop listening to Fallanor.", the teacher "Cecil stops listening
to you." and "Because you have no more students, your class ends.";
the teacher logging out and back in keeps the student's listening
state (TEACH then answers "already listening to you" and the lesson
goes on). Uncaptured, read by shape: a LISTEN with no class offered
beyond "isn't teaching a class", a skill the teacher cannot give,
the student's line when the teacher STOPs TEACHING, and STOP
TEACHING's own answer.
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
# The student walking off: "All of your students have left, so you stop
# teaching."; the student's STOP LISTENING (captured 2026-09-22): "Cecil
# stops listening to you." then "Because you have no more students,
# your class ends." Either way the class is over and is offered again.
STUDENTS_LEFT = (
    "all of your students have left",
    "no more students",
    "your class ends",
    "stops listening to you",
)
# An offer not taken up expires (a few minutes, 2026-09-22): "You stop
# trying to teach Parry Ability to Cecil." — the teacher offers again.
# The student joining: "Cecil begins to listen to you teach the Parry
# Ability skill."
OFFER_EXPIRED = ("you stop trying to teach",)
STUDENT_JOINED = ("begins to listen to you",)
# An offer not taken up expires (a few minutes, 2026-09-22): "You stop
# trying to teach Parry Ability to Cecil." — the teacher offers again.
# The student joining: "Cecil begins to listen to you teach the Parry
# Ability skill."
OFFER_EXPIRED = ("you stop trying to teach",)
STUDENT_JOINED = ("begins to listen to you",)
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
# The student sees no class-ended line at all when the teacher walks
# off — only the room's "Masah just left." (captured 2026-09-22, the
# hold went blind for twenty minutes) — so ;listen watches the
# teacher in the room's players and the leaving line both.
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


def left_pattern(teacher):
    """The regex for the teacher leaving the room: "Masah just left.",
    "Masah went through a door", "Masah goes north"."""
    return rf"^{re.escape(teacher)} (just left|went|goes|climbs|runs|leaves)\b"


def teacher_present(state, teacher):
    """True while the teacher is among the room's players (the parser's
    `room_players`); True too when the state lists no players yet, so
    a cold parser never ends a class."""
    players = getattr(state, "room_players", None)
    if not players:
        return True
    return teacher.lower() in {str(name).lower() for name in players}


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
