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
script.EVERYTHING_QUIET = 0.3

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
    # TAKE EVERYTHING first; it brought nothing here, so part by part.
    assert takes == [
        "take lanival everything",
        "take lanival chest",
        "take lanival left arm",
    ]
    assert "TAKE EVERYTHING answered '(silence)' — one part at a time" in out
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
    run(fake, ["lanival", "take", "parts"])
    assert "take lanival everything" not in fake.sent
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


def test_take_everything_brings_every_part_over_in_one_transfer():
    # The operator, 2026-09-27: one TAKE EVERYTHING instead of ~40 TAKEs
    # (Elanthipedia: Empath healing). Its lines are the single TAKE's,
    # one "fully healed" per part — an assumption until captured.
    fake = Fake(
        {
            "touch lanival": [TOUCH_TWO, LINK + TOUCH_CLEAN],
            "take lanival everything": (
                "You feel the transfer beginning as a cold stillness settles in "
                "the center of your being...\n"
                + TAKEN.format(part="chest")
                + TAKEN.format(part="left arm")
            ),
        }
    )
    out = run(fake, ["lanival", "take"])
    takes = [c for c in fake.sent if c.startswith("take")]
    assert takes == ["take lanival everything"]
    assert "TAKE EVERYTHING brought 2 part(s) over" in out
    assert "Lanival has no injuries left" in out


def test_the_death_warning_stops_the_heal_at_once():
    fatal = (
        "You realize that you are taking a wound that will kill you if you "
        "finish the transfer.\n"
    )
    fake = Fake({"touch lanival": TOUCH_TWO, "take lanival": fatal})
    out = run(fake, ["lanival"])
    assert "the heal stops here" in out
    assert [c for c in fake.sent if c.startswith("take")] == ["take lanival everything"]
    assert not any(c.startswith(("cast", "prepare")) for c in fake.sent)
    parts = Fake({"touch lanival": TOUCH_TWO, "take lanival": fatal})
    run(parts, ["lanival", "parts"])
    assert [c for c in parts.sent if c.startswith("take")] == ["take lanival chest"]


def test_the_last_round_is_checked_before_saying_hurt():
    fake = Fake(
        {
            "touch lanival": [TOUCH_TWO, TOUCH_TWO, TOUCH_TWO, LINK + TOUCH_CLEAN],
            "take lanival chest": TAKEN.format(part="chest"),
            "take lanival left arm": TAKEN.format(part="left arm"),
        }
    )
    out = run(fake, ["lanival", "take", "parts"])
    assert "Lanival has no injuries left" in out
    assert "still reads hurt" not in out


POISONED = LINK + "Lanival's injuries include...\nLanival has a mild nerve poison.\n"
FLUSHED = (
    "You gesture.\nA sudden wave of heat washes over you as your spell flushes "
    "all poison from your body.\n"
)


def knows(*spells):
    return SimpleNamespace(
        abbreviation=lambda character, spell: "x" if spell in spells else None
    )


def test_poison_is_taken_when_flush_poisons_is_known_and_flushed_after(monkeypatch):
    monkeypatch.setattr(script, "buffs", knows("Flush Poisons"))
    fake = Fake(
        {
            "touch lanival": [POISONED, LINK + TOUCH_CLEAN],
            "take lanival poison": "You feel the poison begin to seep into you.\n",
            "health": [
                "Your body feels at full strength.\nYou have a mild poison.\n",
                CLEAN,
            ],
            "prepare fp": "You feel fully prepared to cast your spell.\n",
            "cast": FLUSHED,
        }
    )
    out = run(fake, ["lanival"])
    assert "take lanival poison" in fake.sent
    assert "TAKE POISON answered" in out
    assert "prepare fp 15" in fake.sent and "cast" in fake.sent
    assert "Flush Poisons cast — the poison is gone" in out
    assert "Lanival has no injuries left" in out


def test_poison_is_left_when_the_empath_cannot_cure_it(monkeypatch):
    monkeypatch.setattr(script, "buffs", knows())
    fake = Fake({"touch lanival": POISONED})
    out = run(fake, ["lanival", "take"])
    assert "take lanival poison" not in fake.sent
    assert "Flush Poisons is not among your recorded spells" in out
