"""How ;debt pays — these tests are the manual. INFO for the debt and
the coins, the teller for the shortfall one denomination at a time,
the debt office for PAY ALL, INFO again as the judge, and the walk
back."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "debt_script", REPO / "scripts/debt.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01

MAP = MapDB(
    [
        {"id": 100, "uid": [1], "title": ["[Town, Square]"], "wayto": {}},
        {
            "id": 1900,
            "uid": [9001],
            "title": ["[Provincial Bank, Teller]"],
            "tags": ["bank", "crossing bank"],
            "wayto": {},
        },
        {
            "id": 8282,
            "uid": [9002],
            "title": ["[Town Hall, Debtors' Office]"],
            "tags": ["debt"],
            "wayto": {},
        },
    ]
)


def info(carried=0, owed=1510):
    lines = ["Wealth:"]
    lines.append(
        f"  {carried} copper Kronars ({carried} copper Kronars)."
        if carried
        else "  No Kronars."
    )
    lines += ["  No Lirums.", "  No Dokoras."]
    if owed:
        lines += [
            "Debt:",
            f"  You owe some Kronars to the Principality of Zoluren. ({owed} copper Kronars)",
        ]
    return "\n".join(lines) + "\n"


NO_ACCOUNT = (
    'The clerk flips through her ledger then says, "Lanival, you do not seem to '
    "have an account with us.  If you would like to open one, you need only "
    'deposit a few Kronars."\n'
)
PAID = "You pay off your debt.\n"


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
        self.state = SimpleNamespace(name="Lanival", room_uid=1)

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
    s.state.room_uid = db.rooms[min(goals)]["uid"][0]
    return True


def echoes(fake):
    return "\n".join(fake.echoed)


def test_bare_debt_reports_carried_and_owed_and_sends_only_info():
    fake = Fake({"info": [info(carried=300)]})
    script.run(fake, [])
    assert fake.sent == ["info"]
    assert "Kronars: carrying 3 silver, owing 1 gold, 5 silver and 1 bronze" in echoes(
        fake
    )


def test_paying_fetches_the_shortfall_then_pays_at_the_office_and_walks_back():
    fake = Fake(
        {
            "info": [info(carried=300), info(carried=1510), info(carried=0, owed=0)],
            "withdraw": ["The clerk counts out your coins.\n"] * 3,
            "pay": [PAID],
        }
    )
    script.run(fake, ["pay"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{1900}, {8282}, {100}]
    withdrawals = [c for c in fake.sent if c.startswith("withdraw")]
    assert withdrawals == ["withdraw 1 gold", "withdraw 2 silver", "withdraw 1 bronze"]
    assert fake.sent[-2:] == ["pay all", "info"] or "pay all" in fake.sent
    assert "debt: paid 1 gold, 5 silver and 1 bronze Kronars" in echoes(fake)
    assert "you owe nothing" in echoes(fake)


def test_enough_in_hand_skips_the_bank():
    fake = Fake(
        {"info": [info(carried=2000), info(carried=490, owed=0)], "pay": [PAID]}
    )
    script.run(fake, ["pay", "stay"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{8282}]  # no teller, and stay
    assert not any(c.startswith("withdraw") for c in fake.sent)


def test_nothing_owed_sends_no_one_anywhere():
    fake = Fake({"info": [info(carried=5, owed=0)]})
    script.run(fake, ["pay"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == []
    assert "you owe nothing" in echoes(fake)


def test_a_teller_with_no_account_stops_the_run_with_advice():
    fake = Fake({"info": [info(carried=0)], "withdraw": [NO_ACCOUNT]})
    script.run(fake, ["pay"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{1900}]
    assert fake.sent.count("pay all") == 0
    assert "you do not seem to have an account" in echoes(fake)
    assert "GIVE from another character" in echoes(fake)


def test_a_withdrawal_that_left_you_short_stops_before_the_office():
    fake = Fake(
        {
            "info": [info(carried=0), info(carried=1000)],
            "withdraw": ["ok", "ok", "ok"],
        }
    )
    script.run(fake, ["pay"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{1900}]
    assert "still short" in echoes(fake)


def test_a_debt_that_survives_pay_is_reported_not_claimed_paid():
    fake = Fake(
        {
            "info": [info(carried=2000), info(carried=2000, owed=1510)],
            "pay": ['The clerk says, "Not here, friend."\n'],
        }
    )
    script.run(fake, ["pay"], mapdb=MAP, walk_fn=walk)
    assert "still owing 1 gold, 5 silver and 1 bronze Kronars" in echoes(fake)
    assert "debt: paid" not in echoes(fake)
    assert "Not here, friend." in echoes(fake)
