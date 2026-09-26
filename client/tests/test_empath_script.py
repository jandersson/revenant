"""How ;empath runs — these tests are the manual. TOUCH the patient, TAKE
the wounds most urgent first with the link renewed only when it lapses,
TOUCH again for what that bared, then heal yourself worst first until
HEALTH reads clean. Wordings captured 2026-09-26 (client/game/empathy.py)."""

import importlib.util
import pathlib
from types import SimpleNamespace

from test_empathy import TOUCH_CLEAN

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "empath_script", REPO / "scripts/empath.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.TOUCH_SECONDS = 0.3
script.TAKE_SECONDS = 0.3
script.PREPARE_SECONDS = 0.3

LINK = (
    "You touch Lanival.\n"
    "You sense a successful empathic link has been forged between you and Lanival.\n"
)
TOUCH_TWO = (
    LINK + "Lanival's injuries include...\n"
    "Wounds to the LEFT ARM:\n"
    "  Fresh External:  cuts and bruises about the left arm -- minor\n"
    "Wounds to the CHEST:\n"
    "  Fresh External:  cuts and bruises about the chest area -- minor\n"
    "\nLanival has normal vitality.\n"
)
TAKEN = "You sense that Lanival's external {part} wounds are fully healed.\n"
NO_LINK = "You have no empathic link with Lanival and cannot transfer his wounds.\n"
HURT = (
    "Your body feels at full strength.\n"
    "You have cuts and bruises about the left arm, cuts and bruises about the "
    "chest area.\n"
)
HALF = (
    "Your body feels at full strength.\nYou have cuts and bruises about the left arm.\n"
)
CLEAN = "Your body feels at full strength.\nYou have no significant injuries.\n"
HEALED = "You gesture.\nThe external wounds on your {part} appear completely healed.\n"


class Fake:
    """A handle: put() queues the answer for the command's prefix (a list
    is consumed in order); get() hands its lines out; ask() answers at
    once for probe.ask."""

    def __init__(self, answers, mana=100):
        self.answers = {
            k: list(v) if isinstance(v, list) else [v] for k, v in answers.items()
        }
        self.sent, self.echoed, self.pending = [], [], []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(vitals={"mana": mana})

    def _answer(self, command):
        self.sent.append(command)
        for prefix, queue in self.answers.items():
            if command.startswith(prefix):
                return queue.pop(0) if len(queue) > 1 else queue[0]
        return ""

    def put(self, command, cleanup=False):
        self.pending = self._answer(command).splitlines(keepends=True)

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def ask(self, s, command, *_):
        return self._answer(command)

    def command(self, timeout=None):
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def run(fake, words):
    script.probe = SimpleNamespace(ask=fake.ask)
    script.run(fake, words)
    return "\n".join(fake.echoed)


def test_the_patient_is_touched_once_and_the_torso_taken_before_the_arm():
    fake = Fake(
        {
            "touch lanival": [TOUCH_TWO, LINK + TOUCH_CLEAN],
            "take lanival chest": TAKEN.format(part="chest"),
            "take lanival left arm": TAKEN.format(part="left arm"),
            "health": [HURT, HALF, CLEAN],
            "prepare hw": "You feel fully prepared to cast your spell.\n",
            "cast chest": HEALED.format(part="chest"),
            "cast left arm": HEALED.format(part="left arm"),
        }
    )
    out = run(fake, ["lanival"])
    takes = [c for c in fake.sent if c.startswith("take")]
    assert takes == ["take lanival chest", "take lanival left arm"]
    assert fake.sent.count("touch lanival") == 2  # a round, then the check
    assert "Lanival has no injuries left" in out
    casts = [c for c in fake.sent if c.startswith("cast")]
    assert casts == ["cast chest", "cast left arm"]
    assert "healed — 2 cast(s)" in out


def test_a_lapsed_link_is_renewed_with_one_touch_and_the_take_sent_again():
    fake = Fake(
        {
            "touch lanival": [TOUCH_TWO, LINK, LINK + TOUCH_CLEAN],
            "take lanival chest": [NO_LINK, TAKEN.format(part="chest")],
            "take lanival left arm": TAKEN.format(part="left arm"),
        }
    )
    run(fake, ["lanival", "take"])
    assert fake.sent.count("take lanival chest") == 2
    assert fake.sent.count("touch lanival") == 3
    assert not any(c.startswith("cast") for c in fake.sent)  # take only


def test_a_patient_who_is_not_here_ends_it_with_no_transfer():
    fake = Fake({"touch lanival": "Touch what?\n"})
    out = run(fake, ["lanival", "take"])
    assert "is lanival here?" in out
    assert not any(c.startswith("take") for c in fake.sent)


def test_self_heal_stops_when_the_mana_runs_low():
    fake = Fake({"health": HURT}, mana=10)
    out = run(fake, ["self"])
    assert "mana below 20%" in out
    assert not any(c.startswith("prepare") for c in fake.sent)
