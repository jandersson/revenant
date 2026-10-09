"""How ;gaze trains — these tests are the manual (#500). It takes the
sanowret crystal in hand, waits for full concentration, GAZEs, reads
the lecture to its end, waits for the refill, holds at mind-lock, and
stows the crystal at every end. The wordings are the wiki's verb
template until captured."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import gaze

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "gaze_script", REPO / "scripts/gaze.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

GOT = "You get a frost-red sanowret crystal from inside your backpack.\n"
GAZED = (
    "You gaze intently into your frost-red sanowret crystal, seeking the promise of "
    "hidden knowledge as light dances across its surface.\n"
    "Knowledge from your sanowret crystal about Attunement rings clear in your mind:\n"
)
LECTURE_END = (
    "The light and crystal sound of your sanowret crystal fades slightly as you come "
    "to the end of the knowledge about Attunement.  You feel quite enlightened, if a "
    "bit mentally tired.\n"
)
EXHALED = (
    "You exhale softly on your frost-red sanowret crystal, and scintillating sparks of "
    "light dance across its surface.\nYou hear in your mind a quiet recollection of "
    "wisdom.  Though you think that you could get more knowledge if you were to GAZE "
    "into the crystal, you come away from the experience with a further understanding "
    "of Arcana as the scintillating lights fade again.\n"
)


class Fake:
    """A handle whose Arcana mindstate follows a script of values, one per
    GAZE; concentration drops by half on a gaze and refills ten points a
    second of sleep."""

    def __init__(self, mindstates, crystal=True, stop_at=None, refuse=0):
        self.mindstates = list(mindstates)
        self.crystal = crystal
        self.stop_at = stop_at
        self.refuse = refuse
        self.stopped = False
        self.now = 1000.0
        self.sent, self.echoed, self.slept = [], [], []
        self.pending = []
        self.lines = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            experience={
                "Arcana": {
                    "rank": 30,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            },
            vitals={"concentration": 100},
            hostiles={},
            left_hand=None,
            right_hand=None,
        )

    def _next(self):
        if self.mindstates:
            self.state.experience["Arcana"]["mindstate"] = self.mindstates.pop(0)

    def put(self, command):
        self.sent.append(command)
        answer = ""
        if command.startswith("get my") and self.crystal:
            answer = GOT
            self.state.right_hand = {
                "noun": "crystal",
                "name": "frost-red sanowret crystal",
            }
        elif command.startswith("get my"):
            answer = "What were you referring to?\n"
        elif command.startswith("gaze"):
            if self.refuse > 0:
                self.refuse -= 1
                answer = "You are too distracted to focus on the crystal right now.\n"
            else:
                answer = GAZED
                self.lines = [line + "\n" for line in LECTURE_END.splitlines()]
                self.state.vitals["concentration"] = 49
                self.now += 30
                self._next()
        elif command.startswith("exhale"):
            answer = EXHALED
            self.state.vitals["concentration"] = 49
            self._next()
        elif command.startswith("stow my"):
            answer = "You put your crystal in your backpack.\n"
            self.state.right_hand = None
        self.pending = [line + "\n" for line in answer.splitlines()]

    def get(self, timeout=None, streams=("",)):
        if self.pending:
            return self.pending.pop(0)
        return self.lines.pop(0) if self.lines else None

    def command(self, timeout=None):
        if self.stop_at is not None and not self.stopped and self.now >= self.stop_at:
            self.stopped = True
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds
        bar = self.state.vitals
        bar["concentration"] = min(100, bar["concentration"] + 10 * seconds)
        if any("mind-locked" in line for line in self.echoed):
            self._next()


def run(fake, args=()):
    return script.run(fake, script.parse_args(list(args)))


def test_the_model_waits_on_the_bar_and_names_the_command():
    assert gaze.ready({"concentration": 100})
    assert not gaze.ready({"concentration": 99})
    assert gaze.ready({})  # no bar read yet: never wait on nothing
    assert gaze.ready(None)
    assert gaze.command() == "gaze my sanowret crystal"
    assert gaze.command(exhale=True) == "exhale on my sanowret crystal"
    assert script.parse_args(
        ["exhale", "until=30", "once", "crystal=achaedi crystal"]
    ) == {
        "exhale": True,
        "until": 30,
        "once": True,
        "crystal": "achaedi crystal",
    }


def test_it_gazes_at_full_concentration_and_waits_for_the_refill_between():
    fake = Fake([10, 20, 30, 34])
    assert run(fake, ["once"]) == "locked"
    gazes = [c for c in fake.sent if c.startswith("gaze")]
    assert fake.sent[0] == "get my sanowret crystal"
    assert gazes == ["gaze my sanowret crystal"] * 3
    # Each gaze halves the bar; the refill is waited out before the next,
    # in the loop's one-second slices (a typed return lands within one).
    assert fake.slept and set(fake.slept) == {1}
    assert sum(fake.slept) >= 3 * 5  # three refills of 51 points at 10 a second
    assert fake.sent[-1] == "stow my sanowret crystal"  # at the end, in hand no more
    assert fake.state.right_hand is None
    assert "gaze: Arcana at 34/34 — done" in fake.echoed


def test_exhale_is_the_quick_half_lesson():
    fake = Fake([10, 34])
    assert run(fake, ["exhale", "once"]) == "locked"
    assert "exhale on my sanowret crystal" in fake.sent
    assert not any(c.startswith("gaze") for c in fake.sent)


def test_no_crystal_on_you_ends_before_any_gaze():
    fake = Fake([10], crystal=False)
    assert run(fake) == "no crystal"
    assert not any(c.startswith("gaze") for c in fake.sent)
    assert any("no sanowret crystal on you" in t for t in fake.echoed)


def test_a_refusal_is_reported_and_three_in_a_row_end_the_run():
    fake = Fake([10, 10, 10, 10], refuse=3)
    why = run(fake)
    assert why == "GAZE refused 3 times in a row"
    assert sum("unrecognized GAZE answer" in t for t in fake.echoed) == 1  # said once
    assert fake.sent[-1] == "stow my sanowret crystal"


def test_gazes_without_gain_end_the_run():
    fake = Fake([10, 10, 10, 10, 10])
    assert run(fake) == "4 gazes without gain"


def test_a_typed_return_during_the_hold_stows_the_crystal():
    fake = Fake([34, 34, 34, 34], stop_at=1010.0)
    why = run(fake)
    assert why == "return"
    assert fake.sent[-1] == "stow my sanowret crystal"
