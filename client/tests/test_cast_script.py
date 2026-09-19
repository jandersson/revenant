"""How ;cast trains magic standing still — these tests are the manual.
The hunt's cast cycle (GET, CHARGE, PREPARE, INVOKE, CAST, stow) on
the profile's first buff with the mana ramp, a POWER once a minute,
the lock held or left, and a typed return."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import buffs

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "cast_script", REPO / "scripts/cast.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01
script.POLL = 0.01
script.LOCK_POLL = 0.01
buffs.PREPARE_SECONDS = 0.01

# The hunt's captured wordings (client/game/buffs.py, 2026-09-12/14).
ANSWERS = {
    "get": ["You get a round cambrinth flake.\n"] * 9,
    "charge": [
        "You are able to channel all the energy into the flake.\nThe cambrinth flake absorbs all of the energy.\n"
    ]
    * 9,
    "prepare": ["You begin chanting a prayer to invoke the Heroic Strength spell.\n"]
    * 9,
    "invoke": [
        "You reach for its center and forge a magical link to it, readying all of its mana for your use.\n"
    ]
    * 9,
    "cast": [
        "You gesture.\nThe spell takes effect, the invisible flame of your soul intertwining with your flesh.\n"
    ]
    * 9,
    "stow": [""] * 9,
    "power": [
        "You reach out with your weak senses and see glowing streams of golden Holy mana radiating through the area.\n"
    ]
    * 9,
}
PROFILE = {
    "buffs": ["heroic strength"],
    "train_casting": "Augmentation",
    "cambrinth": "flake",
    "cambrinth_mana": 1,
    "cast_gap": 60,
}


class Fake:
    def __init__(self, answers, experience, mana=100):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.pending = []
        self.dead = False
        self.commands = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience=experience,
            vitals={"mana": mana},
            hostiles={},
            active_spells={},
            left_hand=None,
            right_hand=None,
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if queue else ""
                self.pending = [line + "\n" for line in text.splitlines()]
                return

    def get(self, timeout=None, streams=("",)):
        if timeout == 0 or not self.pending:
            return None
        return self.pending.pop(0)

    def command(self, timeout=None):
        return self.commands.pop(0) if self.commands else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def echoes(fake):
    return "\n".join(fake.echoed)


def learning(mindstate):
    return {
        "Augmentation": {"rank": 10, "percent": 0, "mindstate": mindstate},
        "Arcana": {"rank": 2, "percent": 0, "mindstate": mindstate},
        "Attunement": {"rank": 44, "percent": 0, "mindstate": mindstate},
    }


def test_one_pass_powers_charges_and_casts_the_first_buff_then_returns(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(script, "clock", lambda: now[0])
    monkeypatch.setattr(buffs, "monotonic", lambda: now[0])
    fake = Fake(ANSWERS, learning(10))
    fake.commands = [None, "return"]
    script.run(fake, [], PROFILE)
    assert fake.sent == [
        "power",
        "get my flake",
        "charge my flake 1",
        "prepare heroic strength",
        "invoke my flake",
        "cast",
        "stow my flake",
    ]
    assert "cast heroic strength at minimum mana for Augmentation (+flake)" in echoes(
        fake
    )
    assert "watching Augmentation, Arcana, Attunement" in echoes(fake)
    assert "cast: stopping" in echoes(fake)  # the return, noticed in the pause


def test_nopower_and_a_spell_of_your_own_skip_the_perceive(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(script, "clock", lambda: now[0])
    monkeypatch.setattr(buffs, "monotonic", lambda: now[0])
    fake = Fake(ANSWERS, learning(10))
    fake.commands = [None, "return"]
    script.run(fake, ["nopower", "spell=aspirant's aegis", "skill=Warding"], PROFILE)
    assert "power" not in fake.sent
    assert "prepare aspirant's aegis" in fake.sent
    assert "for Warding" in echoes(fake)


def test_the_lock_ends_a_once_run_and_holds_otherwise(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(script, "clock", lambda: now[0])
    monkeypatch.setattr(buffs, "monotonic", lambda: now[0])
    locked = Fake(ANSWERS, learning(34))
    script.run(locked, ["once"], PROFILE)
    assert locked.sent == []
    assert "at 34/34 — done" in echoes(locked)
    held = Fake(ANSWERS, learning(34))
    held.commands = [None, "return"]  # the second look lands inside the hold's pause
    script.run(held, [], PROFILE)
    assert "mind-locked — holding" in echoes(held)
    assert held.sent == []


def test_no_buff_and_no_spell_is_nothing_to_cast():
    fake = Fake(ANSWERS, learning(10))
    script.run(fake, [], {**PROFILE, "buffs": []})
    assert fake.sent == [] and "nothing to cast" in echoes(fake)


def test_parse_args():
    options = script.parse_args(
        ["until=30", "once", "nopower", "spell=Heroic Strength"]
    )
    assert options == {
        "spell": "Heroic Strength",
        "skill": "",
        "until": 30,
        "once": True,
        "power": False,
    }


def test_a_song_playing_stops_the_run_with_the_reason(monkeypatch):
    # Captured 2026-09-20 on the gondola with ;perform running.
    now = [1000.0]
    monkeypatch.setattr(script, "clock", lambda: now[0])
    monkeypatch.setattr(buffs, "monotonic", lambda: now[0])
    busy = dict(ANSWERS, power=["You are a bit too busy performing to do that.\n"])
    fake = Fake(busy, learning(10))
    script.run(fake, [], PROFILE)
    assert fake.sent == ["power"]
    assert "refuses spellwork while a song plays" in echoes(fake)
    # The same refusal at the charge, with POWER off.
    quiet = dict(ANSWERS, charge=["You should stop playing before you do that.\n"])
    fake = Fake(quiet, learning(10))
    script.run(fake, ["nopower"], PROFILE)
    assert "refuses spellwork while a song plays" in echoes(fake)
