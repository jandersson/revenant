"""How ;bank banks the purse — these tests are the manual. WEALTH read,
the foreign coins exchanged at the money-changer into the province's
own, everything deposited at the teller, a `keep` withdrawn back and
`back` walked. The wordings are the Crossing's, captured 2026-09-20."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import bank
from client.game.mapdb import MapDB
from client.game.money import parse_wealth

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "bank_script", REPO / "scripts/bank.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01

MAP = MapDB(
    [
        {
            "id": 1,
            "uid": [1],
            "title": ["[The Crossing, Herald Street]"],
            "wayto": {"1902": "north"},
        },
        {
            "id": 1902,
            "uid": [1902],
            "title": ["[Provincial Bank, Money-changer]"],
            "tags": ["exchange"],
            "wayto": {"1900": "west"},
        },
        {
            "id": 1900,
            "uid": [1900],
            "title": ["[Provincial Bank, Teller]"],
            "tags": ["bank"],
            "wayto": {},
        },
    ]
)

WEALTH_MIXED = (
    "Wealth:\n"
    "  2 silver, 3 bronze, and 2 copper Kronars (232 copper Kronars).\n"
    "  1 silver, 8 bronze, and 4 copper Lirums (184 copper Lirums).\n"
    "  5 silver, 10 bronze, and 12 copper Dokoras (612 copper Dokoras).\n"
)
WEALTH_HOME = "Wealth:\n  10 silver, 1 bronze, and 16 copper Kronars (1026 copper Kronars).\n  No Lirums.\n  No Dokoras.\n"
WEALTH_EMPTY = "Wealth:\n  No Kronars.\n  No Lirums.\n  No Dokoras.\n"
EXCHANGED_DOKORAS = "You hand your money to the money-changer.  After collecting a modest fee, he hands you 8 silver, and 6 copper Kronars.\n"
EXCHANGED_LIRUMS = "You hand your money to the money-changer.  After collecting a modest fee, he hands you 2 silver, 1 bronze, and 8 copper Kronars.\n"
DEPOSITED = (
    "The clerk slides a small metal box across the counter into which you drop all "
    "your Kronars.  She counts them carefully and records the deposit in her ledger.\n"
)


class Fake:
    """A handle whose answers come from a queue per command prefix."""

    def __init__(self, answers):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.walks = []
        self.pending = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival", room_uid=1, room_title="[The Crossing, Herald Street]"
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

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    room = min(goals)
    s.state.room_uid = db.rooms[room]["uid"][0]
    s.state.room_title = db.rooms[room]["title"][0]
    return True


def echoes(fake):
    return "\n".join(fake.echoed)


def test_foreign_coins_are_the_ones_not_the_provinces_and_handed_reads_the_change():
    wealth = parse_wealth(WEALTH_MIXED)
    assert bank.foreign(wealth, "kronars") == ["lirums", "dokoras"]
    assert bank.foreign(wealth, "dokoras") == ["kronars", "lirums"]
    assert bank.foreign(parse_wealth(WEALTH_HOME), "kronars") == []
    assert (
        bank.exchange_command("dokoras", "kronars") == "exchange all dokoras to kronars"
    )
    assert bank.handed(EXCHANGED_DOKORAS) == "8 silver, and 6 copper Kronars"
    assert bank.handed("The money-changer shrugs.\n") is None
    assert bank.home_currency("[Provincial Bank, Money-changer]") == "kronars"


def test_bank_exchanges_every_foreign_coin_then_deposits_all():
    fake = Fake(
        {
            "wealth": [WEALTH_MIXED],
            "exchange all lirums": [EXCHANGED_LIRUMS],
            "exchange all dokoras": [EXCHANGED_DOKORAS],
            "deposit": [DEPOSITED],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk)
    assert fake.sent == [
        "wealth",
        "exchange all lirums to kronars",
        "exchange all dokoras to kronars",
        "deposit all",
    ]
    assert fake.walks == [{1902}, {1900}]
    assert "bank: exchanged your dokoras for 8 silver, and 6 copper Kronars" in echoes(
        fake
    )
    assert "bank: deposited all your coins — the clerk recorded it" in echoes(fake)


def test_home_coins_only_skip_the_money_changer_and_an_empty_purse_walks_nowhere():
    fake = Fake({"wealth": [WEALTH_HOME], "deposit": [DEPOSITED]})
    script.run(fake, [], MAP, walk_fn=walk)
    assert fake.sent == ["wealth", "deposit all"]
    assert fake.walks == [{1900}]
    assert "nothing foreign in the purse — kronars only" in echoes(fake)
    empty = Fake({"wealth": [WEALTH_EMPTY]})
    script.run(empty, [], MAP, walk_fn=walk)
    assert empty.sent == ["wealth"] and empty.walks == []
    assert "the purse is empty" in echoes(empty)


def test_keep_withdraws_the_amount_back_and_back_walks_home():
    fake = Fake({"wealth": [WEALTH_HOME], "deposit": [DEPOSITED], "withdraw": [""] * 3})
    script.run(fake, ["back", "keep=512"], MAP, walk_fn=walk)
    assert fake.sent == [
        "wealth",
        "deposit all",
        "withdraw 5 silver",
        "withdraw 1 bronze",
        "withdraw 2 copper",
    ]
    assert fake.walks == [{1900}, {1}]
    assert "bank: kept 512 copper kronars in the purse" in echoes(fake)


def test_an_empty_purse_with_a_keep_fetches_it_from_the_teller():
    # 2026-09-22: the alchemy kit to buy with nothing in the purse; the
    # session refuses an outside WITHDRAW, so the script's own is the way.
    fake = Fake({"wealth": [WEALTH_EMPTY], "withdraw": [""] * 2})
    script.run(fake, ["keep=2500", "back"], MAP, walk_fn=walk)
    assert fake.sent == ["wealth", "withdraw 2 gold", "withdraw 5 silver"]
    assert fake.walks == [{1900}, {1}]
    assert "withdrawing the 2500 copper keep" in echoes(fake)
    assert "bank: kept 2500 copper kronars in the purse" in echoes(fake)


def test_parse_args():
    assert script.parse_args(["back", "keep=500"]) == {"back": True, "keep": 500}
    assert script.parse_args([]) == {"back": False, "keep": 0}
