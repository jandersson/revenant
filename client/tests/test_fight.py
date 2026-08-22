"""How ;fight sweeps a room — these tests are the manual.

Attack whatever engages you until state.hostiles empties, SEARCH each
corpse away (captured: corpses keep their noun and soak swings), and
break off with the burst-escape below the health floor
(docs/combat.md).
"""

import importlib.util
import pathlib
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _fight():
    spec = importlib.util.spec_from_file_location(
        "fight_script", REPO / "scripts/fight.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fight = _fight()


class FakeHandle:
    """Scripted arena: each attack consumes the next answer; hostiles
    drain as the answers say things died."""

    def __init__(self, answers, hostiles, health=100, compass=("north",)):
        self.answers = list(answers)
        self.sent = []
        self.echoed = []
        self.state = SimpleNamespace(
            hostiles=dict(hostiles),
            vitals={"health": health},
            compass=list(compass),
        )
        self.pending = []

    def put(self, command):
        self.sent.append(command)
        if command == "attack" and self.answers:
            answer, drop = self.answers.pop(0)
            self.pending = [answer]
            for exist in drop:
                self.state.hostiles.pop(exist, None)

    def get(self, timeout=None):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def test_fight_sweeps_until_no_hostiles_remain(monkeypatch):
    monkeypatch.setattr(fight, "COLLECT_SECONDS", 0.02)
    handle = FakeHandle(
        answers=[
            ("The cougar slowly tips over and falls down.", ["1"]),
            ("The cougar is already quite dead.", []),
            ("The cougar slowly tips over and falls down.", ["2"]),
        ],
        hostiles={"1": True, "2": False},
    )
    fight.main(handle)
    # The corpse-soaked swing triggered a search before the next kill.
    assert "search cougar" in handle.sent
    assert any("room clear — 2 kill(s)" in echo for echo in handle.echoed)


def test_fight_breaks_off_below_the_health_floor(monkeypatch):
    monkeypatch.setattr(fight, "COLLECT_SECONDS", 0.02)
    handle = FakeHandle(answers=[], hostiles={"1": True}, health=45)
    fight.main(handle)
    # The burst-escape, in order, with the room's first exit.
    assert handle.sent[:3] == ["retreat", "retreat", "north"]
    assert any("health 45%" in echo for echo in handle.echoed)


def test_fight_declines_a_quiet_room():
    handle = FakeHandle(answers=[], hostiles={})
    fight.main(handle)
    assert handle.sent == []
    assert any("nothing hostile" in echo for echo in handle.echoed)
