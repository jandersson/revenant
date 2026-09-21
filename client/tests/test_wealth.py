"""How ;wealth tracks money — these tests are the manual: BANK
ACCOUNT asked after login and every interval (or on `now`), every
branch a row, a summary per currency, a silent answer reported;
teller balances overheard.

The balance grammar follows lich's common-money: amounts as
denomination lists, currencies pluralized, everything converted to
copper (platinum 10000 / gold 1000 / silver 100 / bronze 10 / copper 1).
"""

import importlib.util
import pathlib
import sqlite3
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _wealth():
    spec = importlib.util.spec_from_file_location(
        "wealth_script", REPO / "scripts/wealth.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wealth = _wealth()


def test_a_full_denomination_list_converts_to_copper():
    line = (
        'The teller says, "Your current balance is 1 platinum, '
        '3 gold, 5 silver and 2 copper Kronars."'
    )
    assert wealth.parse_balance(line) == ("Kronars", 13_502)


def test_the_as_expected_phrasing_counts_too():
    line = "As expected, there are 20 gold Dokoras."
    assert wealth.parse_balance(line) == ("Dokoras", 20_000)


def test_singular_currency_is_stored_plural():
    line = 'the teller says, "Your current balance is 1 copper Lirum."'
    assert wealth.parse_balance(line) == ("Lirums", 1)


def test_ordinary_text_is_not_a_balance():
    assert wealth.parse_balance("You stroll north.") is None
    assert wealth.parse_balance("The teller eyes you suspiciously.") is None


def test_balances_roundtrip_into_the_wealth_table(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "xp.db"))
    connection = sqlite3.connect(wealth.database_path())
    wealth.record(connection, "Lanival", "Kronars", 13_502)
    stored = connection.execute(
        "SELECT character_name, kind, currency, copper FROM wealth"
    ).fetchall()
    assert stored == [("Lanival", "bank", "Kronars", 13_502)]
    connection.close()


# -- the BANK ACCOUNT report: one row per branch (captured 2026-09-12) -------

REPORT = [
    "You currently have the following amounts on deposit:",
    "        Crossing:      337317 | 33 platinum, 7 gold, 3 silver, 1 bronze, and 7 copper Kronars",
    "           Dirge:        5082 | 5 gold, 8 bronze, and 2 copper Kronars",
    "           Shard:        1494 | 1 gold, 4 silver, 9 bronze, and 4 copper Dokoras",
    "       Surlaenis:      350464 | 35 platinum, 4 silver, 6 bronze, and 4 copper Lirums",
    "",
    "          Totals:",
    "         Kronars:      342399 | 34 platinum, 2 gold, 3 silver, 9 bronze, and 9 copper",
    "          Lirums:      350464 | 35 platinum, 4 silver, 6 bronze, and 4 copper",
    "You have 4 open bank accounts!",
]


def test_a_branch_line_parses_to_bank_currency_and_copper():
    assert wealth.parse_deposit(REPORT[1]) == ("Crossing", "Kronars", 337_317)
    assert wealth.parse_deposit(REPORT[3]) == ("Shard", "Dokoras", 1_494)
    assert wealth.parse_deposit(REPORT[4]) == ("Surlaenis", "Lirums", 350_464)


def test_the_totals_block_and_the_rest_of_the_report_are_not_branches():
    # The Totals lines end in a denomination, not a currency; the
    # branches already add up to them.
    for line in (
        REPORT[0],
        REPORT[6],
        REPORT[7],
        REPORT[8],
        REPORT[9],
        "You stroll north.",
    ):
        assert wealth.parse_deposit(line) is None


def test_branch_rows_share_a_stamp_and_an_old_table_gains_the_bank_column(
    tmp_path, monkeypatch
):
    import sqlite3

    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "xp.db"))
    connection = sqlite3.connect(wealth.database_path())
    # The table as ;sheet created it before the bank column existed.
    connection.execute(
        "CREATE TABLE wealth (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " kind TEXT NOT NULL, currency TEXT NOT NULL, copper INTEGER NOT NULL)"
    )
    stamp = "2026-09-12T00:42:00+00:00"
    for line in REPORT:
        parsed = wealth.parse_deposit(line)
        if parsed:
            bank, currency, copper = parsed
            wealth.record(
                connection, "Lanival", currency, copper, bank=bank, logged_at=stamp
            )
    stored = connection.execute(
        "SELECT logged_at, kind, bank, currency, copper FROM wealth ORDER BY seq"
    ).fetchall()
    assert stored == [
        (stamp, "bank", "Crossing", "Kronars", 337_317),
        (stamp, "bank", "Dirge", "Kronars", 5_082),
        (stamp, "bank", "Shard", "Dokoras", 1_494),
        (stamp, "bank", "Surlaenis", "Lirums", 350_464),
    ]
    connection.close()


# -- the tracker: asks, logs, summarizes ------------------------------------

REPORT_LINES = [
    "You flag down a local you know works with the Estate Holders' Council and "
    "send him to fetch info on your bank accounts.",
    "He returns and hands you a slip of paper with figures on it...",
    *REPORT,
]


INFO_LINES = [
    "Wealth:",
    "  3 silver Kronars (300 copper Kronars).",
    "  No Lirums.",
    "Debt:",
    "  You owe 9 silver and 3 bronze Kronars to the Principality of Zoluren. "
    "(930 copper Kronars)",
]


class Fake:
    """A handle with a fake clock: BANK ACCOUNT answers with the report
    (or nothing), INFO with the wealth block, typed requests arrive
    through command()."""

    def __init__(self, answers=None, requests=(), info=None):
        self.answers = list(answers if answers is not None else [REPORT_LINES])
        self.info = list(INFO_LINES if info is None else info)
        self.requests = list(requests)
        self.now = 1000.0
        self.sent = []
        self.echoed = []
        self.pending = []
        self.args = []
        self.state = SimpleNamespace(name="Lanival")

    def put(self, command):
        self.sent.append(command)
        if command == "bank account" and self.answers:
            self.pending = list(self.answers.pop(0))
        if command == "info":
            self.pending = list(self.info)

    def waitrt(self):
        pass

    def get(self, timeout=None, streams=("",)):
        if self.pending:
            return self.pending.pop(0) + "\n"
        if timeout is None or timeout >= 1:
            self.now += timeout or 1  # the loop's waits pass time; probe's polls don't
        return None

    def command(self, timeout=None):
        return self.requests.pop(0) if self.requests else None

    def echo(self, text):
        self.echoed.append(text)


def run_tracker(fake, args=(), stop_after_sends=1, monkeypatch=None, tmp_path=None):
    """Run main() until the fake has sent `stop_after_sends` BANK ACCOUNTs
    and the report settled, by making the interval end the loop."""
    fake.args = list(args)
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "xp.db"))
    monkeypatch.setattr(wealth, "clock", lambda: fake.now)
    monkeypatch.setattr(wealth, "START_DELAY", 0)
    monkeypatch.setattr(wealth, "REPORT_SETTLE", 2)
    monkeypatch.setattr(wealth, "REPORT_WAIT", 5)
    monkeypatch.setattr(wealth, "INFO_SECONDS", 0.01)
    monkeypatch.setattr(wealth, "INFO_TAIL", 0.01)

    class Stop(Exception):
        pass

    real_get = fake.get

    def get(timeout=None, streams=("",)):
        if fake.now > 1000 + 60 * stop_after_sends:
            raise Stop
        return real_get(timeout, streams)

    fake.get = get
    try:
        wealth.main(fake)
    except Stop:
        pass


def test_the_tracker_asks_on_start_logs_every_branch_and_summarizes(
    tmp_path, monkeypatch
):
    fake = Fake()
    run_tracker(fake, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert fake.sent == ["bank account", "info"]
    connection = sqlite3.connect(wealth.database_path())
    rows = connection.execute(
        "SELECT bank, currency, copper FROM wealth WHERE kind = 'bank' ORDER BY seq"
    ).fetchall()
    assert rows == [
        ("Crossing", "Kronars", 337_317),
        ("Dirge", "Kronars", 5_082),
        ("Shard", "Dokoras", 1_494),
        ("Surlaenis", "Lirums", 350_464),
    ]
    text = "\n".join(fake.echoed)
    assert (
        "Kronars: on deposit 34 platinum, 2 gold, 3 silver, 9 bronze and 9 copper"
        in text
    )
    assert "(Crossing 33 platinum" in text and "Dirge 5 gold" in text
    assert "Dokoras: on deposit 1 gold, 4 silver, 9 bronze and 4 copper" in text
    # INFO's carried and debt are fresh, logged like ;sheet's, and netted
    assert "carrying 3 silver, owing 9 silver and 3 bronze" in text
    held = connection.execute(
        "SELECT kind, currency, copper FROM wealth WHERE kind IN ('carried', 'debt')"
    ).fetchall()
    assert held == [
        ("carried", "Kronars", 300),
        ("carried", "Lirums", 0),
        ("debt", "Kronars", 930),
    ]
    assert "Lirums: on deposit 35 platinum" in text  # deposited, nothing carried


def test_a_bank_account_refused_for_roundtime_is_asked_again(tmp_path, monkeypatch):
    # #268 (2026-09-21): "[wealth]> bank account" / "...wait 1 seconds."
    # was a missed report until the next three-hourly interval.
    fake = Fake(answers=[["...wait 1 seconds."], REPORT_LINES])
    run_tracker(fake, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert fake.sent == ["bank account", "bank account", "info"]
    text = "\n".join(fake.echoed)
    assert "gave no report" not in text
    assert "Kronars: on deposit" in text


def test_a_paid_debt_reaches_the_history_as_a_zero(tmp_path, monkeypatch):
    fake = Fake(info=["Wealth:", "  No Kronars.", "Debt:", "  No debt."])
    run_tracker(fake, monkeypatch=monkeypatch, tmp_path=tmp_path)
    connection = sqlite3.connect(wealth.database_path())
    held = connection.execute(
        "SELECT kind, currency, copper FROM wealth WHERE kind IN ('carried', 'debt')"
    ).fetchall()
    assert held == [("carried", "Kronars", 0), ("debt", "Kronars", 0)]
    text = "\n".join(fake.echoed)
    assert "carrying 0 copper, owing 0 copper" in text


def test_the_summary_nets_the_sheet_s_carried_and_debt(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "xp.db"))
    connection = sqlite3.connect(wealth.database_path())
    wealth.ensure_schema(connection)
    for stamp, kind, copper in (
        ("2026-09-12T10:00:00+00:00", "carried", 5),
        ("2026-09-12T12:00:00+00:00", "carried", 300),
        ("2026-09-12T12:00:00+00:00", "debt", 1510),
    ):
        connection.execute(
            "INSERT INTO wealth (logged_at, character_name, kind, currency, copper)"
            " VALUES (?, 'Lanival', ?, 'Kronars', ?)",
            (stamp, kind, copper),
        )
    connection.commit()
    held = wealth.latest_carried_and_debt(connection, "Lanival")
    assert held == {("carried", "Kronars"): 300, ("debt", "Kronars"): 1510}
    lines = wealth.summary({("Crossing", "Kronars"): 18_939}, held)
    assert lines == [
        "Kronars: on deposit 1 platinum, 8 gold, 9 silver, 3 bronze and 9 copper, "
        "carrying 3 silver, owing 1 gold, 5 silver and 1 bronze — net "
        "1 platinum, 7 gold, 7 silver, 2 bronze and 9 copper"
    ]


def test_now_from_cold_asks_once_and_exits(tmp_path, monkeypatch):
    fake = Fake()
    fake.args = ["now"]
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "xp.db"))
    monkeypatch.setattr(wealth, "clock", lambda: fake.now)
    monkeypatch.setattr(wealth, "REPORT_SETTLE", 2)
    monkeypatch.setattr(wealth, "INFO_SECONDS", 0.01)
    monkeypatch.setattr(wealth, "INFO_TAIL", 0.01)
    wealth.main(fake)  # returns on its own once the report settled
    assert fake.sent == ["bank account", "info"]
    assert any("on deposit" in line for line in fake.echoed)


def test_a_typed_now_asks_again_and_the_interval_asks_by_itself(tmp_path, monkeypatch):
    fake = Fake(
        answers=[REPORT_LINES, REPORT_LINES, REPORT_LINES],
        requests=[None, None, None, "now"],
    )
    monkeypatch.setattr(wealth, "INTERVAL", 30)
    run_tracker(fake, stop_after_sends=2, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert fake.sent.count("bank account") >= 3  # start, the typed now, the interval


def test_a_silent_answer_is_reported_not_retried(tmp_path, monkeypatch):
    fake = Fake(answers=[[]])
    run_tracker(fake, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert fake.sent == ["bank account"]  # no report, no INFO
    assert any("gave no report" in line for line in fake.echoed)
    assert not any("on deposit" in line for line in fake.echoed)
