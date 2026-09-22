"""Classes — these tests are the manual for ;teach and ;listen. The
captured lines of 2026-09-22 (a Thief teaching a Paladin Scholarship)
read as a class up, a student in it and the students gone; the
teacher re-offers when they leave, the student holds on the skill's
mindstate and rejoins when the class ends, and each stops on
`return` with the class closed."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import teaching
from client.game.probe import classify

REPO = pathlib.Path(__file__).parents[2]

TEACHING = "You begin to lecture Cecil on the proper use of the Scholarship skill.\n"
OFFERED = (
    "Masah begins to lecture you on the proper usage of the Scholarship skill.\n"
    "  To learn from him, you must LISTEN TO Masah.\n"
)
LISTENING = "You begin to listen to Masah teach the Scholarship skill.\n"
STUDENTS_LEFT = "All of your students have left, so you stop teaching.\n"


def _script(name):
    spec = importlib.util.spec_from_file_location(
        f"{name}_script", REPO / f"scripts/{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


teach = _script("teach")
listen = _script("listen")


def test_the_captured_lines_read_as_the_model_says():
    assert classify(TEACHING.lower(), teaching.TEACH_OUTCOMES) == "teaching"
    assert classify(LISTENING.lower(), teaching.LISTEN_OUTCOMES) == "listening"
    assert (
        classify("what were you referring to?", teaching.TEACH_OUTCOMES) == "no student"
    )
    assert (
        classify("masah is not teaching anything.", teaching.LISTEN_OUTCOMES)
        == "no class"
    )
    assert any(word in STUDENTS_LEFT.lower() for word in teaching.STUDENTS_LEFT)
    # The student's STOP LISTENING, on the teacher's side (2026-09-22).
    for line in (
        "Cecil stops listening to you.",
        "Because you have no more students, your class ends.",
    ):
        assert any(word in line.lower() for word in teaching.STUDENTS_LEFT), line
    assert any(
        word in "you stop listening to fallanor." for word in teaching.CLASS_ENDED
    )
    # Asked again mid-class (captured 2026-09-22): the class is up.
    mid = "Cecil is already listening to you.  He needs to STOP LISTENING before you can teach him.\n"
    assert classify(mid.lower(), teaching.TEACH_OUTCOMES) == "already"
    heard = "You are already listening to someone.  You may wish to STOP LISTENING.\n"
    assert classify(heard.lower(), teaching.LISTEN_OUTCOMES) == "already"
    assert teaching.taught_skill(LISTENING) == "Scholarship"
    assert teaching.taught_skill(OFFERED) == "Scholarship"
    assert teaching.taught_skill(TEACHING) == "Scholarship"
    assert teaching.taught_skill("Recall what?") is None
    # The teacher walking off is the room's line, not a class line.
    import re

    left = re.compile(teaching.left_pattern("masah"), re.IGNORECASE)
    assert left.search("Masah just left.")
    assert left.search("Masah went through a marble arch.")
    assert not left.search("Masah just arrived.")
    room = SimpleNamespace(room_players=["Cecil", "Masah"])
    assert teaching.teacher_present(room, "masah")
    assert not teaching.teacher_present(
        SimpleNamespace(room_players=["Cecil"]), "masah"
    )
    assert teaching.teacher_present(SimpleNamespace(room_players=[]), "masah")


def test_the_commands_and_the_arguments():
    assert (
        teaching.teach_command("scholarship", "cecil") == "teach scholarship to cecil"
    )
    assert teaching.teach_command("small edged") == "teach small edged open"
    assert teaching.listen_command("masah") == "listen to masah"
    assert teaching.listen_command("masah", observe=True) == "listen to masah observe"
    assert teaching.parse_teach_args(["scholarship", "to", "cecil"]) == {
        "skill": "scholarship",
        "student": "cecil",
    }
    assert teaching.parse_teach_args(["small", "edged", "open"]) == {
        "skill": "small edged",
        "student": None,
    }
    assert teaching.parse_listen_args(["masah"]) == {
        "teacher": "masah",
        "skill": "",
        "until": 34,
        "once": False,
        "observe": False,
    }
    assert teaching.parse_listen_args(
        ["masah", "scholarship", "until=30", "once", "observe"]
    ) == {
        "teacher": "masah",
        "skill": "scholarship",
        "until": 30,
        "once": True,
        "observe": True,
    }


class Fake:
    """A handle on a fake clock: `sleep` advances it and steps the
    Scholarship mindstate, a flag fires its line once the clock passes
    `ends_at`, a typed return arrives at `stop_at`, and TEACH/LISTEN
    are answered from `answers` (a list per command prefix, the last
    repeating)."""

    def __init__(self, answers, mindstates=(0,), stop_at=None, ends_at=None):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.mindstates = list(mindstates)
        self.stop_at, self.ends_at = stop_at, ends_at
        self.now = 0.0
        self.fired = False
        self.stopped = False
        self.flags = {}
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Scholarship": {
                    "rank": 11,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            },
            hostiles={},
            room_players=["Masah"],
        )

    def ask(self, s, command, *_):
        self.sent.append(command)
        for prefix, queue in self.answers.items():
            if command.startswith(prefix):
                return queue.pop(0) if len(queue) > 1 else queue[0]
        return ""

    def sleep(self, seconds):
        self.now += seconds
        if self.mindstates:
            self.state.experience["Scholarship"]["mindstate"] = self.mindstates.pop(0)

    def command(self, timeout=None):
        if self.stop_at is not None and not self.stopped and self.now >= self.stop_at:
            self.stopped = True
            return "return"
        return None

    def flag(self, name, *patterns):
        self.flags[name] = patterns

    def flagged(self, name, clear=True):
        # Fires the named flag once the clock passes `ends_at`; a fake
        # built with `fires` names which flag fires (the students
        # leaving by default).
        wanted = getattr(self, "fires", ("students left", "class ended"))
        if (
            name in wanted
            and self.ends_at is not None
            and not self.fired
            and self.now >= self.ends_at
        ):
            self.fired = True
            return f"the {name} line"
        return None

    def unflag(self, name):
        self.flags.pop(name, None)

    def echo(self, text):
        self.echoed.append(text)

    def put(self, command):
        self.sent.append(command)


def run(script, fake, args):
    script.probe = SimpleNamespace(ask=fake.ask)
    parse = teaching.parse_teach_args if script is teach else teaching.parse_listen_args
    script.run(fake, parse(args))
    return "\n".join(fake.echoed)


def test_teach_offers_again_when_the_students_leave_and_stops_on_return():
    fake = Fake({"teach": [TEACHING]}, stop_at=60, ends_at=10)
    out = run(teach, fake, ["scholarship", "to", "cecil"])
    assert "teaching scholarship to cecil" in out
    assert (
        fake.sent.count("teach scholarship to cecil") == 2
    )  # once more after they left
    assert "offering again in 20 s" in out
    assert fake.sent[-1] == "stop teaching" and "stopping as asked (2 offer(s))" in out
    assert not fake.flags  # unflagged at the end
    # An offer that expired untaken is made again at once, no wait.
    expired = Fake({"teach": [TEACHING]}, stop_at=30, ends_at=10)
    expired.fires = ("offer expired",)
    out = run(teach, expired, ["scholarship", "to", "cecil"])
    assert "the offer expired untaken — offering again" in out
    assert expired.sent.count("teach scholarship to cecil") == 2
    refused = Fake({"teach": ["You are not skilled enough to teach that.\n"]})
    out = run(teach, refused, ["scholarship", "to", "cecil"])
    assert "not skilled enough" in out and "no class — stopping" in out


def test_listen_reads_the_skill_holds_on_its_mindstate_and_rejoins():
    fake = Fake(
        {"listen": [LISTENING]}, mindstates=[5, 10, 20, 34, 34, 34, 34], stop_at=None
    )
    out = run(listen, fake, ["masah", "once"])
    assert fake.sent[0] == "listen to masah"
    assert "in masah's class — Scholarship 5/34" in out
    assert fake.sent[-1] == "stop listening" and "Scholarship at 34/34 — done" in out
    # The class ends: LISTEN again after the wait; three refusals end it.
    again = Fake(
        {"listen": [LISTENING, "Masah is not teaching anything.\n"]},
        mindstates=[5] * 200,
        ends_at=10,
    )
    out = run(listen, again, ["masah"])
    assert "the class ended — listening again in 15 s" in out
    assert again.sent.count("listen to masah") == 4  # the join, three refusals
    assert "not teaching anything" in out
    assert "no class offered 3 times — stopping" in out
    # The teacher gone from the room's players ends the class too.
    walked = Fake(
        {"listen": [LISTENING, "Masah is not teaching anything.\n"]},
        mindstates=[5] * 200,
    )
    walked.state.room_players = ["Cecil"]
    out = run(listen, walked, ["masah"])
    assert "the teacher left the room — listening again in 15 s" in out
    assert "no class offered 3 times — stopping" in out
    nobody = Fake({"listen": ["Masah is not teaching anything.\n"]})
    out = run(listen, nobody, ["masah"])
    assert "no class — stopping" in out and "stop listening" not in nobody.sent
