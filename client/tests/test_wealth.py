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
