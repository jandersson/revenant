"""The TDP model: the game's quotes parsed, the wiki's cost formula
matching them, and ;tdp's words turned into goals."""

import pytest

from client.game import tdp

# Captured 2026-09-12, a Dwarf Paladin at Agility 8 with 347 TDPs.
AGILITY = (
    "Your base Agility is eight (8).\n"
    "It will cost you 28 TDPs to raise your Agility from 8 to 9.\n"
    "Agility helps you hit with weapons, improves manual tasks such as "
    "skinning or disarming.  It contributes to defensive Reflex contests, "
    "among other things.\n"
    "You currently have 347 TDPs available.\n"
    "Use INFO to view all your statistics at once.\n"
)
PROJECT = "It will cost you 132 TDPs to reach 12 points in Agility.\n"
TDP = "You have 347 TDPs.\n"
INFO = (
    "     Strength :  10              Reflex :   8\n"
    "      Agility :   8            Charisma :  10\n"
    "   Discipline :  12              Wisdom :  10\n"
    " Intelligence :  10             Stamina :  12\n"
    "         TDPs : 347\n"
)


def test_the_stat_command_gives_value_next_cost_and_tdps():
    assert tdp.parse_stat_answer(AGILITY) == {
        "stat": "Agility",
        "value": 8,
        "next_cost": 28,
        "tdps": 347,
    }


def test_tdp_project_gives_the_whole_climb():
    assert tdp.parse_project(PROJECT) == {"stat": "Agility", "goal": 12, "cost": 132}
    assert tdp.parse_project("Huh?") is None


def test_tdp_and_info_give_the_points_on_hand():
    assert tdp.parse_tdps(TDP) == 347
    assert tdp.parse_tdps("You have -3 TDPs.") == -3
    assert tdp.parse_info(INFO) == {
        "stats": {
            "Strength": 10,
            "Reflex": 8,
            "Agility": 8,
            "Charisma": 10,
            "Discipline": 12,
            "Wisdom": 10,
            "Intelligence": 10,
            "Stamina": 12,
        },
        "tdps": 347,
    }


def test_the_wiki_formula_reproduces_the_captured_quotes():
    # A Dwarf's +1 on Agility: 3 x 8 + 1 x (8 // 2) = 28
    assert tdp.point_cost(8, modifier=1) == 28
    assert tdp.cost_to(8, 12, modifier=1) == 132  # 28 + 31 + 35 + 38
    assert tdp.modifier_from(8, 28) == 1
    # The wiki's own worked example: a Gor'Tog's Strength, 21 → 22
    assert tdp.point_cost(21, modifier=-3) == 33
    assert tdp.modifier_from(21, 33) == -3
    # Plain, and the 100+ multiplier the wiki states
    assert tdp.point_cost(10) == 30
    assert tdp.point_cost(100) == 1500


def test_affordable_counts_the_points_the_tdps_cover():
    assert tdp.affordable(8, 12, 28, 347) == 4
    assert tdp.affordable(8, 12, 28, 100) == 3  # 28 + 31 + 35 = 94, the 38 is short
    assert tdp.affordable(8, 12, 28, 27) == 0


def test_stat_names_match_by_unambiguous_prefix():
    assert tdp.stat_name("agi") == "Agility"
    assert tdp.stat_name("STRENGTH") == "Strength"
    assert tdp.stat_name("st") is None  # Strength or Stamina
    assert tdp.stat_name("luck") is None


STATS = {"Agility": 8, "Strength": 10}


def test_goals_come_from_words():
    assert tdp.parse_goals(["agility", "12"], STATS) == [("Agility", 12)]
    assert tdp.parse_goals(["strength", "+2"], STATS) == [("Strength", 12)]
    assert tdp.parse_goals(["agility"], STATS) == [("Agility", 9)]
    assert tdp.parse_goals(["agility", "strength", "11"], STATS) == [
        ("Agility", 9),
        ("Strength", 11),
    ]


@pytest.mark.parametrize(
    "words, complaint",
    [
        (["12"], "name a stat first"),
        (["agility", "8"], "already 8"),
        (["agility", "up"], "neither a stat nor a number"),
        (["wisdom", "12"], "INFO gave no value"),
        (["wisdom"], "INFO gave no value"),
    ],
)
def test_bad_goal_words_are_refused_with_the_reason(words, complaint):
    with pytest.raises(ValueError, match=complaint):
        tdp.parse_goals(words, STATS)
