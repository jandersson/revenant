"""Coins both ways: the game's denomination lists to copper and back,
and INFO's wealth split into carried and owed."""

from client.game import money

# Captured 2026-09-12 (INFO of a debtor carrying nothing).
INFO = (
    "Wealth:\n"
    "  No Kronars.\n"
    "  No Lirums.\n"
    "  No Dokoras.\n"
    "Debt:\n"
    "  You owe 1 gold, 5 silver and 1 bronze Kronars to the Principality of "
    "Zoluren. (1510 copper Kronars)\n"
    "  [You can pay off this debt in person at the respective provincial debt "
    "office or by calling for an urchin runner with BANK DEBT.]\n"
)
INFO_RICH = (
    "Wealth:\n"
    "  2 platinum, 3 silver Kronars (20300 copper Kronars).\n"
    "  11 copper Lirums (11 copper Lirums).\n"
    "  No Dokoras.\n"
    "Debt:\n"
    "  You owe 90 copper Kronars to the Principality of Zoluren. (90 copper Kronars)\n"
)


def test_a_denomination_list_converts_to_copper():
    assert money.to_copper("1 gold, 5 silver and 1 bronze") == 1510
    assert money.to_copper("2 platinum, 3 silver") == 20300
    assert money.to_copper("1,234 copper") == 1234
    assert money.to_copper("No Kronars.") == 0


def test_copper_splits_into_coins_largest_first():
    assert money.split(1510) == [(1, "gold"), (5, "silver"), (1, "bronze")]
    assert money.split(20300) == [(2, "platinum"), (3, "silver")]
    assert money.split(7) == [(7, "copper")]
    assert money.split(0) == []


def test_phrase_reads_like_the_game():
    assert money.phrase(1510, "Kronars") == "1 gold, 5 silver and 1 bronze Kronars"
    assert money.phrase(300) == "3 silver"
    assert money.phrase(0, "Lirums") == "0 copper Lirums"
    assert money.to_copper(money.phrase(123456)) == 123456


def test_info_splits_into_carried_and_owed_per_currency():
    assert money.parse_wealth(INFO) == {"carried": {}, "debt": {"Kronars": 1510}}
    assert money.parse_wealth(INFO_RICH) == {
        "carried": {"Kronars": 20300, "Lirums": 11},
        "debt": {"Kronars": 90},
    }
    assert money.parse_wealth("Wealth:\n  No Kronars.\n") == {"carried": {}, "debt": {}}
