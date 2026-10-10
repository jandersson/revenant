"""How ;harajaal gets a character onto the Tasia'zaul's dock in Ratha —
these tests are the manual (#515). A gold lirum in the purse (;bank
fetches it when short), Kretsky asked, the password said, the ramp the
guard waves you down; the slate's schedule said. The quest mode asks
the three first-tier wanderers first, each found by ;seek. Wordings
captured 2026-10-10 at the Uasin Dock."""

import importlib.util
import pathlib
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "harajaal_script", REPO / "scripts/harajaal.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()


def wealth(copper):
    return (
        "Wealth:\n  No Kronars.\n"
        + (
            f"  1 gold Lirums ({copper} copper Lirums).\n"
            if copper
            else "  No Lirums.\n"
        )
        + "  No Dokoras.\n"
    )


GRIN = "Kretsky grins with mischief in his eyes.\n"
SAID = 'You say, "Seordbluef."\n'
DOWN = (
    "A guard stops you with his hand stretched out.  You pass him 1000 lirums and "
    "he waves you down a ramp.\n[Uasin Dock, Port of Ratha]\n"
)
NO_COIN = (
    "A guard frowns at you.\n"
    'A guard whispers, "HEH!  Come back when you got hard coin!"\n'
)
SLATE = (
    "The schedule reads:\nThe Tasia'zaul is on its way from Hara'jaal.  Expected "
    "return time is 15 roisaen past the Anlas of Anduwen (2 hours 58 minutes).\n"
)


class Fake:
    """A handle and the game: WEALTH answers the purse, which ;bank (run
    through the handle) fills; the ramp lets you down with a gold lirum
    on you and keeps you up without; ;seek leaves the room listing the
    wanderers it was given."""

    def __init__(self, copper=1000, bank_gives=1000, wanderers=()):
        self.copper = copper
        self.bank_gives = bank_gives
        self.wanderers = set(wanderers)
        self.sent, self.echoed, self.started = [], [], []
        self.state = SimpleNamespace(room_objs="", room_players=[])

    def ask(self, s, command, seconds=None, tail=None):
        self.sent.append(command)
        if command == "wealth":
            return wealth(self.copper)
        if command.startswith("ask kretsky"):
            return GRIN
        if command.startswith("say "):
            return SAID
        if command == "go ramp":
            return DOWN if self.copper >= 1000 else NO_COIN
        if command == "read slate board":
            return SLATE
        return f"{command.split()[1].capitalize()} mutters something.\n"

    def run(self, name, args=()):
        self.started.append((name, list(args)))
        if name == "bank":
            self.copper += self.bank_gives
        if name == "seek" and args[0] in self.wanderers:
            self.state.room_objs = f"You also see {args[0]} and a crate."
        elif name == "seek":
            self.state.room_objs = "You also see a crate."
        return True

    def is_running(self, name):
        return False

    def sleep(self, seconds):
        pass

    def echo(self, text):
        self.echoed.append(text)


def walk_to_kretsky(walked):
    def go(s, room):
        walked.append(room)
        return True

    return go


def run(fake, quest=False):
    script.ask = fake.ask
    walked = []
    outcome = script.run(fake, {"quest": quest}, walk_to_kretsky(walked))
    return outcome, walked


def test_with_a_gold_lirum_kretsky_the_password_and_down_the_ramp():
    fake = Fake(copper=1000)
    outcome, walked = run(fake)
    assert outcome == "down"
    assert walked == [4632] and fake.started == []
    assert fake.sent == [
        "wealth",
        "ask kretsky about hara'jaal",
        "say seordbluef",
        "go ramp",
        "read slate board",
    ]
    assert any("2 hours 58 minutes" in e for e in fake.echoed)


def test_short_of_a_gold_lirum_bank_fetches_it_first():
    fake = Fake(copper=724)
    outcome, _ = run(fake)
    assert outcome == "down"
    assert fake.started == [("bank", ["keep=1000", "lirums=1000"])]


def test_no_gold_lirum_after_bank_stops_before_the_walk():
    fake = Fake(copper=0, bank_gives=0)
    outcome, walked = run(fake)
    assert outcome == "coin" and walked == []
    assert any("guard wants 1000 lirums" in e for e in fake.echoed)


def test_the_guard_keeping_you_up_top_is_said_in_his_words():
    fake = Fake(copper=1000)
    fake.ask_ramp = fake.ask

    def ask(s, command, seconds=None, tail=None):
        return NO_COIN if command == "go ramp" else fake.ask_ramp(s, command)

    script.ask = ask
    outcome = script.run(fake, {"quest": False}, walk_to_kretsky([]))
    assert outcome == "refused"
    assert any("Come back when you got hard coin" in e for e in fake.echoed)


def test_quest_asks_each_wanderer_seek_found_before_kretsky():
    fake = Fake(copper=1000, wanderers=("hedgewizard", "Raif", "Glath"))
    outcome, _ = run(fake, quest=True)
    assert outcome == "down"
    assert [args[0] for name, args in fake.started if name == "seek"] == [
        "hedgewizard",
        "Raif",
        "Glath",
    ]
    asks = [c for c in fake.sent if c.startswith("ask ") and "kretsky" not in c]
    assert asks == [
        "ask hedgewizard about rumors",
        "ask Raif about pirates",
        "ask Glath about baron",
        "ask Glath about enclave",
    ]


def test_quest_stops_when_seek_finds_no_wanderer():
    fake = Fake(copper=1000, wanderers=("hedgewizard",))
    outcome, walked = run(fake, quest=True)
    assert outcome == "wanderer" and walked == []
    assert any("no Raif found" in e for e in fake.echoed)
