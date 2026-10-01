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
        self.running, self.told, self.started = set(), [], []
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

    # The other-script API: ;bank asks ;wealth for a report (#404).
    def is_running(self, name):
        return name in self.running

    def tell(self, name, word):
        self.told.append((name, word))

    def run(self, name, args=()):
        self.started.append((name, list(args)))
        return True

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


# Captured 2026-09-29 at the Crossing's money-changer (#389): another
# player's exchange, then the changer's refusal of 4 copper Dokoras.
BYSTANDER = "Cache exchanges some words and coins with the money-changer.\n"
TOO_SMALL = (
    "The money-changer says crossly, \"A transaction that small isn't worth my "
    'time.  The minimum is one bronze or ten coppers."\n'
)
WEALTH_SMALL = (
    "Wealth:\n"
    "  2 silver, 3 bronze, and 2 copper Kronars (232 copper Kronars).\n"
    "  No Lirums.\n"
    "  4 copper Dokoras (4 copper Dokoras).\n"
)


def test_a_foreign_coin_under_the_changers_minimum_is_kept_not_exchanged():
    # 2026-09-29: 4 copper Dokoras went to the changer, who refused, and
    # ;bank quoted another player's line as his answer.
    wealth = parse_wealth(WEALTH_SMALL)
    assert bank.foreign(wealth, "kronars") == []
    assert bank.small_change(wealth, "kronars") == [("Dokoras", 4)]
    fake = Fake({"wealth": [WEALTH_SMALL], "deposit": [DEPOSITED]})
    script.run(fake, [], MAP, walk_fn=walk)
    assert fake.sent == ["wealth", "deposit all"]
    out = echoes(fake)
    assert "4 copper Dokoras under the changer's minimum — kept" in out
    assert "nothing foreign" not in out


def test_small_change_alone_walks_nowhere():
    fake = Fake(
        {
            "wealth": [
                WEALTH_SMALL.replace(
                    "2 silver, 3 bronze, and 2 copper Kronars (232 copper Kronars)",
                    "No Kronars",
                )
            ]
        }
    )
    script.run(fake, [], MAP, walk_fn=walk)
    assert fake.sent == ["wealth"]
    assert fake.walks == []
    assert "the purse holds only small change — nothing to bank" in echoes(fake)


def test_the_changers_answer_is_his_own_line_never_a_bystanders():
    fake = Fake(
        {
            "exchange all dokoras": [BYSTANDER + TOO_SMALL],
            "exchange all lirums": [BYSTANDER + "The money-changer shrugs.\n"],
            "exchange all kronars": [BYSTANDER],
        }
    )
    bank.exchange_each(fake, script.ask, "bank", ["dokoras"], "kronars")
    bank.exchange_each(fake, script.ask, "bank", ["lirums"], "kronars")
    bank.exchange_each(fake, script.ask, "bank", ["kronars"], "dokoras")
    assert fake.echoed == [
        "bank: the dokoras are under the changer's minimum — kept",
        "bank: the money-changer answered 'The money-changer shrugs.' to the lirums",
        "bank: the money-changer said nothing to the kronars",
    ]


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
    assert "bank: withdrawing 5 silver, 1 bronze and 2 copper kronars" in echoes(fake)
    assert "bank: kept 512 copper kronars in the purse" in echoes(fake)


def test_a_refused_keep_is_said_and_never_claimed_kept():
    # The keep drew through a loop of the script's own that read no
    # answer: a refusal still said "kept" (#407, the shared loop stops).
    fake = Fake(
        {
            "wealth": [WEALTH_HOME],
            "deposit": [DEPOSITED],
            "withdraw": ["You don't have enough coins in your account.\n"],
        }
    )
    script.run(fake, ["keep=512"], MAP, walk_fn=walk)
    assert fake.sent == ["wealth", "deposit all", "withdraw 5 silver"]
    assert "bank: the teller refused" in echoes(fake)
    assert "kept" not in echoes(fake)


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


# Riverhaven, as the community map writes it: a guild hall that names no
# town, and the bank's rooms with their province (#342).
RIVERHAVEN = MapDB(
    [
        {
            "id": 1,
            "uid": [1],
            "title": ["[Barbarian Guild, Lower Amphitheatre]"],
            "wayto": {"7954": "go bank"},
        },
        {
            "id": 7954,
            "uid": [7954],
            "title": ["[Bank of Riverhaven, Foreign Exchange]"],
            "location": "Therengia",
            "tags": ["exchange"],
            "wayto": {"7953": "west", "1": "out"},
        },
        {
            "id": 7953,
            "uid": [7953],
            "title": ["[Bank of Riverhaven, Teller]"],
            "location": "Therengia",
            "tags": ["bank"],
            "wayto": {"7954": "east"},
        },
    ]
)
WEALTH_RIVERHAVEN = (
    "Wealth:\n"
    "  2 silver, 3 bronze, and 2 copper Kronars (232 copper Kronars).\n"
    "  6 bronze and 5 copper Lirums (65 copper Lirums).\n"
    "  No Dokoras.\n"
)


def test_the_coin_is_the_tellers_not_the_starting_rooms():
    # 2026-09-26 (#342): ;bank from the Barbarian Guild exchanged a
    # Riverhaven purse's Lirums into Kronars, and the teller then had no
    # Lirums to take. The teller the walk ends at is in Therengia.
    fake = Fake(
        {
            "wealth": [WEALTH_RIVERHAVEN],
            "exchange all kronars": [EXCHANGED_LIRUMS],
            "deposit all": [DEPOSITED],
        }
    )
    fake.state.room_title = "[Barbarian Guild, Lower Amphitheatre]"
    script.run(fake, [], RIVERHAVEN, walk_fn=walk)
    assert "exchange all kronars to lirums" in fake.sent
    assert not any(command.startswith("exchange all lirums") for command in fake.sent)
    assert fake.walks == [{7954}, {7953}]


def test_a_rooms_coin_reads_its_title_location_and_map_image():
    def room(**data):
        return MapDB([{"id": 5, "title": ["[Somewhere]"], **data}])

    assert bank.room_currency(room(location="Therengia"), 5) == "lirums"
    assert bank.room_currency(room(location="Qi'Reshalia"), 5) == "lirums"
    assert bank.room_currency(room(location="Forfedhdar"), 5) == "dokoras"
    assert bank.room_currency(room(image="Ilitha, Fang Cove.jpg"), 5) == "dokoras"
    assert bank.room_currency(room(location="Zoluren"), 5) == "kronars"
    assert bank.room_currency(room(), 5) == "kronars"
    assert bank.nearest(RIVERHAVEN, 1, [7953]) == 7953
    assert bank.nearest(RIVERHAVEN, 7953, [7953]) == 7953
    assert bank.nearest(RIVERHAVEN, None, [7953]) is None


def test_a_deposit_has_wealth_report_the_bank_now():
    # #404 (the operator, 2026-10-01): 2,032 Kronars deposited showed in
    # no figure until ;wealth's next three-hourly BANK ACCOUNT.
    fake = Fake({"wealth": [WEALTH_HOME], "deposit": [DEPOSITED]})
    fake.running = {"wealth"}
    script.run(fake, [], MAP, walk_fn=walk)
    assert fake.told == [("wealth", "now")] and fake.started == []
    cold = Fake({"wealth": [WEALTH_HOME], "deposit": [DEPOSITED]})
    script.run(cold, [], MAP, walk_fn=walk)
    assert cold.started == [("wealth", ["now"])]
    empty = Fake({"wealth": [WEALTH_EMPTY]})
    script.run(empty, [], MAP, walk_fn=walk)
    assert empty.told == [] and empty.started == []  # no teller, no report


def test_withdraw_here_draws_by_denomination_and_says_the_tellers_lines():
    # The loop ;bank's keep and ;enc's ballast copied (#407).
    sent, echoed = [], []
    counted = "The clerk counts out {} and hands them over, making a notation in her ledger.\n"

    def ask(s, command):
        sent.append(command)
        return counted.format(command.split(" ", 1)[1])

    handle = SimpleNamespace(echo=echoed.append)
    assert bank.withdraw_here(handle, ask, "tdp", 1250, "Kronars") is True
    assert sent == ["withdraw 1 gold", "withdraw 2 silver", "withdraw 5 bronze"]
    assert echoed[0] == "tdp: withdrawing 1 gold, 2 silver and 5 bronze Kronars"
    assert echoed[1].startswith("tdp: The clerk counts out 1 gold")
    refusing = SimpleNamespace(echo=echoed.append)
    assert (
        bank.withdraw_here(
            refusing,
            lambda s, c: "You do not seem to have an account with us.\n",
            "tdp",
            100,
            "Kronars",
        )
        is False
    )
    assert "the teller refused" in echoed[-1]
    assert bank.refused("You don't have enough coins in your account.")
    assert not bank.refused(counted.format("1 gold"))
