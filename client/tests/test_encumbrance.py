"""The encumbrance model: the wiki's capacity formula, the bands a
level implies, the points that lighten it, and the readings' log."""

import sqlite3

from client.game import encumbrance as enc


def test_the_formula_reproduces_the_wiki_example():
    # 10 Strength and 10 Stamina carry 480 stones with no burden
    assert enc.capacity(1, 10, 10) == 480
    assert enc.capacity(2, 10, 10) == 560  # 0.4 x 7 x 20 = 56 → 560


def test_a_level_is_a_band_of_weights():
    # captured 2026-09-12: Very Heavy Burden at Strength 10, Stamina 11
    assert enc.band("Very Heavy Burden", 10, 11) == (840, 930)
    assert enc.band("None", 10, 11) == (0, 510)
    assert enc.band("Squashed", 10, 11) is None
    assert enc.level_for(900, 10, 11) == "Very Heavy Burden"
    assert enc.level_for(840, 10, 11) == "Heavy Burden"
    assert enc.level_for(100000, 10, 11) == "It's amazing you aren't squashed!"


def test_points_that_lighten_a_level_span_the_band_until_the_weight_is_known():
    # Heavy Burden holds up to 40 x (Str + Sta): 22 → 880, 23 → 920, 24 → 960
    assert enc.points_to_lighten("Very Heavy Burden", 10, 11) == (1, 3)
    assert enc.points_to_lighten("Very Heavy Burden", 10, 11, weight=900) == (2, 2)
    assert enc.points_to_lighten("Very Heavy Burden", 10, 11, weight=841) == (1, 1)
    assert enc.points_to_lighten("None", 10, 11) is None


def test_the_level_line_parses_from_info_and_from_the_command():
    assert enc.parse_level("  Encumbrance : Very Heavy Burden\n") == "Very Heavy Burden"
    assert (
        enc.parse_level(
            "         TDPs : 401\n  Encumbrance : None\n         Luck : Lucky"
        )
        == "None"
    )
    assert enc.parse_level("Encumbrance : Wobbly") is None
    assert enc.level_index("very heavy burden") == 6


def test_coins_are_a_fifth_of_a_stone():
    assert enc.coins_for(50) == 250
    assert enc.coins_for(1) == 5


def test_readings_log_and_summarize():
    connection = sqlite3.connect(":memory:")
    enc.record(connection, "Lanival", 10, 11, "Very Heavy Burden", 0, "reading")
    enc.record(connection, "Lanival", 10, 11, "Overburdened", 100, "ballast")
    enc.record(connection, "Sable", 12, 12, "None", 0, "")
    entries = enc.rows(connection, character="Lanival")
    assert [e["level"] for e in entries] == ["Very Heavy Burden", "Overburdened"]
    lines = enc.summarize(entries)
    assert lines[0].endswith("Str 10 Sta 11: Very Heavy Burden — reading")
    assert lines[1].endswith("Str 10 Sta 11: Overburdened +100 st — ballast")
