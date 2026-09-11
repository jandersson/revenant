"""How ;wealth reads a teller's balance — these tests are the manual.

The balance grammar follows lich's common-money: amounts as
denomination lists, currencies pluralized, everything converted to
copper (platinum 10000 / gold 1000 / silver 100 / bronze 10 / copper 1).
"""

import importlib.util
import pathlib

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

    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
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

    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
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
