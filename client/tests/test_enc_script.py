"""How ;enc reads and pins a burden — these tests are the manual."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import encumbrance as enc

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location("enc_script", REPO / "scripts/enc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01

INFO = "     Strength :  10              Reflex :  10\n      Stamina :  11\n         TDPs : 401\n"
COUNTED = "The clerk counts out {} {} Kronars and hands them over, making a notation in her ledger.\n"


class Fake:
    """A handle whose ENCUMBRANCE answer follows the coins it holds: the
    load `weight` plus the ballast, judged by the wiki's formula."""

    def __init__(self, weight, strength=10, stamina=11, refuse_at=None):
        self.weight, self.strength, self.stamina = weight, strength, stamina
        self.refuse_at = refuse_at
        self.coins = 0
        self.sent, self.echoed, self.pending = [], [], []
        self.args = []
        self.state = SimpleNamespace(name="Lanival")

    def level(self):
        return enc.level_for(
            self.weight + self.coins * enc.COIN_STONES, self.strength, self.stamina
        )

    def put(self, command):
        self.sent.append(command)
        words = command.split()
        if command == "info":
            self.pending = [line + "\n" for line in INFO.splitlines()]
        elif command == "encumbrance":
            self.pending = [f"  Encumbrance : {self.level()}\n"]
        elif words[0] == "withdraw":
            count, denomination = int(words[1]), words[2]
            coins = (
                count * {"gold": 1, "silver": 1, "bronze": 1, "copper": 1}[denomination]
            )
            if self.refuse_at is not None and self.coins + coins > self.refuse_at:
                self.pending = ["The clerk says you do not have enough for that.\n"]
                return
            self.coins += count  # a coin is a coin, whatever the metal
            self.pending = [COUNTED.format(count, denomination)]
        elif words[0] == "deposit":
            self.coins -= int(words[1])
            self.pending = ["The clerk records the deposit in her ledger.\n"]

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def echoes(fake):
    return "\n".join(fake.echoed)


def test_a_reading_names_the_band_and_the_points(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    fake = Fake(weight=900)
    fake.args = []
    script.main(fake)
    assert fake.sent == ["info", "encumbrance"]
    assert "Very Heavy Burden at Strength 10 + Stamina 11" in echoes(fake)
    assert "over 840 and up to 930 stones" in echoes(fake)
    assert (
        "1 to 3 point(s) of Strength or Stamina would make it Heavy Burden"
        in echoes(fake)
    )
    db = enc.open_history(script.database_path())
    assert [r["note"] for r in enc.rows(db)] == ["reading"]


def test_ballast_pins_the_load_and_deposits_the_coins_back(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    fake = Fake(weight=900)  # 30 stones under the Very Heavy ceiling of 930
    script.ballast(fake, 50, mapdb=None)
    withdrawals = [c for c in fake.sent if c.startswith("withdraw")]
    assert withdrawals == ["withdraw 250 copper"]  # one step of 50 stones flipped it
    assert "+50 stones of coins → Overburdened" in echoes(fake)
    assert "the load weighs over 880 and up to 930 stones" in echoes(fake)
    assert "at 881 stones, 2 point(s)" in echoes(
        fake
    ) and "at 930 stones, 3 point(s)" in echoes(fake)
    assert fake.coins == 0 and "deposit 250 copper" in fake.sent
    db = enc.open_history(script.database_path())
    assert [r["note"] for r in enc.rows(db)] == [
        "ballast start",
        "ballast",
        "pinned 880-930 stones",
    ]


def test_ballast_takes_several_steps_when_the_load_sits_low_in_its_band(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    fake = Fake(weight=845)
    script.ballast(fake, 50, mapdb=None)
    assert [c for c in fake.sent if c.startswith("withdraw")] == [
        "withdraw 250 copper"
    ] * 2
    assert "the load weighs over 830 and up to 880 stones" in echoes(fake)
    assert fake.coins == 0


def test_a_refusal_stops_the_run_with_the_coins_returned(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    fake = Fake(weight=845, refuse_at=300)
    script.ballast(fake, 50, mapdb=None)
    assert "the teller refused" in echoes(fake)
    assert fake.coins == 0
    assert "pinned" not in echoes(fake)


def test_show_lists_the_readings(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    fake = Fake(weight=900)
    fake.args = ["show"]
    script.main(fake)
    assert "nothing logged yet" in echoes(fake)
    fake.args = ["log", "stowed", "the", "greaves"]
    script.main(fake)
    fake.args = ["show"]
    script.main(fake)
    assert any("Very Heavy Burden — stowed the greaves" in line for line in fake.echoed)


def test_ballast_from_none_pins_without_advice_about_a_lighter_level(
    tmp_path, monkeypatch
):
    # captured 2026-09-12: the worn-plate run started at None and crashed
    # after the flip, before the pinned row, when it reached for a level
    # below None; the coins went back on the crash path
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    fake = Fake(weight=480)  # None at 10 + 11 holds up to 510
    script.ballast(fake, 50, mapdb=None)
    assert "the load weighs over 460 and up to 510 stones" in echoes(fake)
    assert fake.coins == 0
    db = enc.open_history(script.database_path())
    assert enc.rows(db)[-1]["note"] == "pinned 460-510 stones"
