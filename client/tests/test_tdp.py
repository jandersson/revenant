"""The TDP model: the game's quotes parsed, the wiki's cost formula
matching them, and ;tdp's words turned into goals."""

import pytest

from client.game import probe, tdp

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
    "Name: Lanival Redeemer   Race: Dwarf   Guild: Paladin\n"
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
        "race": "Dwarf",
        "guild": "Paladin",
        "circle": None,  # the fixture has no Circle line
    }


def test_parse_info_reads_the_circle():
    # The identity line INFO prints, captured in test_sheet: ";circle"
    # takes the circle from it rather than the sheet's (2026-09-20).
    assert tdp.parse_info("Gender: Male   Age: 20   Circle: 8\n")["circle"] == 8
    assert tdp.parse_info(INFO)["circle"] is None


def test_stats_below_the_racial_start_are_the_points_dr3_hands_back():
    # captured 2026-09-12 (#165): a DR1 Dwarf rolled under the starts
    stats = {
        "Strength": 10,
        "Reflex": 8,
        "Agility": 8,
        "Charisma": 9,
        "Discipline": 8,
        "Stamina": 11,
    }
    assert tdp.below_start("Dwarf", stats) == {
        "Charisma": 10,
        "Discipline": 12,
        "Stamina": 12,
    }
    assert tdp.below_start("Human", {"Strength": 10}) == {}
    assert tdp.below_start("Nobody", stats) == {}
    assert tdp.below_start("Gor'Tog", {"Strength": 16, "Wisdom": 5}) == {"Wisdom": 6}


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


def test_the_captured_train_answers_classify_in_order():
    first = (
        "You consult with the teachers and together decide that it will take 28 moon "
        "cycles until you successfully train your agility to 9 ranks.  There is also "
        "a fee of 56 Kronars to complete this training.\nThat would leave you 319 "
        "time development points afterward.  If this is OK, you will need to STUDY "
        "once again to get your new rank.\n"
    )
    second = (
        "(You now have 319 time development points.)\n(Your debt has increased by "
        "56 Kronars.)\nAfter what seems an astonishing amount of time, you find you "
        "have completed your training in agility.\nYour attempts to train are "
        "praiseworthy, but you must find both the proper place and the proper "
        "teacher first.\n"
    )
    wrong_room = second.splitlines()[-1]
    assert probe.classify(first, tdp.TRAIN_OUTCOMES) == "confirm"
    assert probe.classify(second, tdp.TRAIN_OUTCOMES) == "done"  # despite its last line
    assert probe.classify(wrong_room, tdp.TRAIN_OUTCOMES) == "refused"


# --- TDPs by a plan or the guild's tiers (#230) --------------------------------
def test_parse_info_reads_the_guild():
    assert tdp.parse_info(INFO)["guild"] == "Paladin"


def test_plan_goals_read_stat_targets_and_auto():
    stats = tdp.parse_info(INFO)["stats"]
    assert tdp.plan_goals(["stamina 30", "Strength 20"], stats) == [
        ("Stamina", 30),
        ("Strength", 20),
    ]
    assert tdp.plan_goals(["auto"], stats) is None
    for bad in (["stamina"], ["stamina x"], ["luck 30"]):
        with pytest.raises(ValueError):
            tdp.plan_goals(bad, stats)


def test_next_stat_follows_the_goals_then_says_when_all_are_met():
    stats = tdp.parse_info(INFO)["stats"]  # Stamina 12, Strength 10
    goals = [("Stamina", 12), ("Strength", 12)]
    assert tdp.next_stat(stats, goals) == ("Strength", 10)
    assert tdp.next_stat(stats, [("Stamina", 12)]) is None


def test_auto_follows_the_paladins_tiers_then_balances():
    stats = tdp.parse_info(INFO)["stats"]  # Strength 10, Stamina 12, Reflex 8 ...
    assert tdp.next_stat(stats, None, "Paladin") == (
        "Strength",
        10,
    )  # the lower of the two
    plate = dict(stats, Strength=15, Stamina=15)
    assert tdp.next_stat(plate, None, "Paladin") == ("Reflex", 8)
    ready = dict(plate, Reflex=15, Agility=15, Discipline=15)
    assert tdp.next_stat(ready, None, "Paladin") == (
        "Charisma",
        10,
    )  # the lowest of all
    assert tdp.next_stat(stats, None, "Bard") == ("Reflex", 8)  # no tiers: balanced
