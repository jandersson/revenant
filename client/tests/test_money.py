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


def test_a_negative_amount_is_the_minus_sign_before_its_phrase():
    # #333: ;wealth's net for a character owing 2047 copper Kronars and
    # holding none read "-1 platinum, 7 gold, 9 silver, 5 bronze and 3
    # copper" — floor division of a negative total.
    assert money.phrase(-2047) == "-2 gold, 4 bronze and 7 copper"
    assert money.phrase(-1510, "Kronars") == "-1 gold, 5 silver and 1 bronze Kronars"
    assert money.phrase(-3) == "-3 copper"


def test_info_splits_into_carried_and_owed_per_currency():
    assert money.parse_wealth(INFO) == {
        "carried": {"Kronars": 0, "Lirums": 0, "Dokoras": 0},
        "debt": {"Kronars": 1510},
    }
    assert money.parse_wealth(INFO_RICH) == {
        "carried": {"Kronars": 20300, "Lirums": 11, "Dokoras": 0},
        "debt": {"Kronars": 90},
    }


def test_wealth_with_the_debt_section_first_still_reads_the_purse():
    # Captured 2026-09-21 (#266): WEALTH printed Debt above Wealth and
    # ;bank called a 5391-copper purse empty.
    text = (
        "\nDebt:\n  You owe 9 bronze Kronars to the Principality of Zoluren. "
        "(90 copper Kronars)\n  [You can pay off this debt in person at the "
        "respective provincial debt office or by calling for an urchin runner "
        "with BANK DEBT.]\n\nWealth:\n  1 gold, 33 silver, 99 bronze, and 101 "
        "copper Kronars (5391 copper Kronars).\n  No Lirums.\n  No Dokoras.\n"
    )
    assert money.parse_wealth(text) == {
        "carried": {"Kronars": 5391, "Lirums": 0, "Dokoras": 0},
        "debt": {"Kronars": 90},
    }


def test_nothing_carried_and_no_debt_are_zeros_not_silence():
    # Captured 2026-09-12 once the debt was paid: the history must get a
    # zero, or the newest debt row stays the old figure.
    assert money.parse_wealth("Wealth:\n  No Kronars.\nDebt:\n  No debt.\n") == {
        "carried": {"Kronars": 0},
        "debt": {"Kronars": 0},
    }
    assert money.parse_wealth("") == {"carried": {}, "debt": {}}  # unanswered
