"""How ;appraise trains — these tests are the manual. It APPRAISEs the
items on you in rotation, quick, drops what the game cannot find, holds
at mind-lock and ends on a typed return, a danger or an empty rotation
(#275)."""

import importlib.util
import pathlib
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "appraise_script", REPO / "scripts/appraise.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

MISSING = "What were you referring to?\n"
# The success wording is uncaptured (2026-09-22); the wiki's certainty line.
CERTAIN = "You are certain that the scimitar weighs exactly 52 stones.\n"

POSSESSIONS = [
    {"noun": "scimitar", "depth": 0},
    {"noun": "sack", "depth": 0},
    {"noun": "pouch", "depth": 0},
]


class Fake:
    """A handle whose Appraisal mindstate advances one step per APPRAISE
    answered; a typed "return" arrives after `stop_after` appraisals."""

    def __init__(self, mindstates, stop_after=None, missing=(), possessions=None):
        self.mindstates = list(mindstates)
        self.stop_after = stop_after
        self.missing = set(missing)
        self.appraised = 0
        self.slept = 0
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Appraisal": {
                    "rank": 8,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            }
            if self.mindstates
            else {},
            hostiles={},
            possessions=POSSESSIONS if possessions is None else possessions,
        )

    def ask(self, s, command, *_):
        self.sent.append(command)
        if command.startswith("appraise my "):
            noun = command.split()[2]
            if noun in self.missing:
                return MISSING
            self.appraised += 1
            if self.mindstates:
                self.state.experience["Appraisal"]["mindstate"] = self.mindstates.pop(0)
            return CERTAIN.replace("scimitar", noun)
        if command == "exp appraisal":
            return "Appraisal:   8 11% dabbling  (1/34)\n"
        return ""

    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return None

    def command(self, timeout=None):
        if self.stop_after is not None and self.appraised >= self.stop_after:
            self.stop_after = None
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.slept += seconds
        if self.mindstates:
            self.state.experience["Appraisal"]["mindstate"] = self.mindstates.pop(0)


def run(fake, args=()):
    script.probe = SimpleNamespace(ask=fake.ask)
    script.run(fake, script.parse_args(list(args)))
    return "\n".join(fake.echoed)


def appraisals(fake):
    return [c for c in fake.sent if c.startswith("appraise ")]


def test_it_appraises_the_inventory_in_rotation_pouch_first_until_mind_lock():
    fake = Fake(mindstates=[1, 5, 10, 20, 30, 34])
    out = run(fake, ["once"])
    assert appraisals(fake) == [
        "appraise my pouch quick",
        "appraise my scimitar quick",
        "appraise my sack quick",
        "appraise my pouch quick",
        "appraise my scimitar quick",
    ]
    assert (
        "appraise: 3 item(s) in rotation (pouch, scimitar, sack) — Appraisal 1/34"
        in out
    )
    assert "appraise: pouch answered 'you are certain that the pouch weighs" in out
    assert out.count("answered") == 1  # the first answer only, for the capture
    assert "Appraisal at 34/34 — done" in out


def test_an_item_the_game_cannot_find_leaves_the_rotation_and_an_empty_one_ends():
    fake = Fake(mindstates=[1] + [5] * 20, missing={"sack"}, stop_after=4)
    out = run(fake)
    assert "appraise my sack quick" in fake.sent
    assert appraisals(fake).count("appraise my sack quick") == 1
    assert "the game finds no sack — out of the rotation (2 left)" in out
    assert "stopping as asked" in out

    gone = Fake(mindstates=[1, 5], missing={"pouch", "scimitar", "sack"})
    out = run(gone)
    assert "nothing left to appraise — stopping" in out


def test_the_items_argument_and_careful_replace_the_inventory_and_quick():
    fake = Fake(mindstates=[1, 5, 34])
    run(fake, ["items=shield,zills", "careful", "once"])
    assert appraisals(fake)[:2] == [
        "appraise my shield careful",
        "appraise my zills careful",
    ]


def test_it_holds_at_the_lock_and_appraises_again_once_drained(monkeypatch):
    # Locked at the start; the hold's polls read 34, 30, then 27 — below
    # 28 — and a lap runs; a typed return after two appraisals ends it.
    monkeypatch.setattr(script, "LOCK_POLL", 1)
    fake = Fake(mindstates=[34, 34, 30, 27, 5, 6], stop_after=2)
    out = run(fake, ["until=34"])
    assert "mind-locked (34/34) — holding until it drains" in out
    assert "drained to 27/34 — appraising again" in out
    assert appraisals(fake) == ["appraise my pouch quick", "appraise my scimitar quick"]
    assert fake.slept == 3
    assert "stopping as asked" in out


def test_no_appraisal_in_exp_and_nothing_on_you_are_said_and_end():
    fake = Fake(mindstates=[], possessions=[])
    fake.ask = lambda s, command, *_: "" if command == "exp appraisal" else ""
    out = run(fake)
    assert "EXP shows no Appraisal — nothing to train" in out
    assert appraisals(fake) == []

    bare = Fake(mindstates=[1], possessions=[])
    out = run(bare)
    assert "nothing to appraise — items=<noun,noun>" in out


def test_danger_ends_the_run():
    fake = Fake(mindstates=[1, 5, 5, 5])
    fake.state.hostiles = {"1": True}
    out = run(fake)
    assert "hostiles in the room — stopping" in out
    assert appraisals(fake) == []


def test_the_exp_window_without_the_skill_is_asked_and_seeded():
    fake = Fake(mindstates=[])
    fake.state.experience = {}
    run(fake, ["once"])
    assert fake.sent[0] == "exp appraisal"
    assert fake.state.experience["Appraisal"] == {
        "rank": 8,
        "percent": 0,
        "mindstate": 1,
        "rate": "dabbling",
    }
