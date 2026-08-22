"""How ;sheet parses and stores the character sheet — the manual.

Fixtures mirror captured INFO / EXP ALL output (2026-08-22), scrubbed
to synthetic identity per the no-PII rule; the numeric layout is real.
"""

import importlib.util
import pathlib
import sqlite3

REPO = pathlib.Path(__file__).parents[2]


def _sheet():
    spec = importlib.util.spec_from_file_location(
        "sheet_script", REPO / "scripts/sheet.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sheet = _sheet()

INFO_TEXT = """Name: Testchar Example   Race: Human   Guild: Commoner
Gender: Male   Age: 20   Circle: 1
     Strength :  10              Reflex :  14
      Agility :   9            Charisma :  10
   Discipline :   5              Wisdom :   6
 Intelligence :   8             Stamina :   8
Concentration : 317    Max : 317
       Favors : 0
         TDPs : 356
  Encumbrance : None
"""

EXP_ALL_TEXT = """Circle: 1
Showing all skills that you have skill in.
          SKILL: Rank/Percent towards next rank/Amount learning/Mindstate Fraction
     Light Armor:      3 10% clear          (0/34)       Defending:      2 36% clear          (0/34)
         Evasion:      3 34% clear          (0/34)       Athletics:     22 17% clear          (0/34)
 Mechanical Lore:      3 00% clear          (0/34)         Tactics:      1 28% clear          (0/34)
Total Ranks Displayed: 66
Time Development Points: 356  Favors: 0  Deaths: 0  Departs: 0
"""


def test_parse_info_reads_stats_circle_tdps_favors():
    info = sheet.parse_info(INFO_TEXT)
    assert info["stats"] == {
        "Strength": 10,
        "Reflex": 14,
        "Agility": 9,
        "Charisma": 10,
        "Discipline": 5,
        "Wisdom": 6,
        "Intelligence": 8,
        "Stamina": 8,
    }
    assert info["circle"] == 1
    assert info["tdps"] == 356
    assert info["favors"] == 0


def test_parse_exp_all_reads_both_columns():
    skills = sheet.parse_exp_all(EXP_ALL_TEXT)
    assert skills["Athletics"] == (22, 17)
    assert skills["Light Armor"] == (3, 10)
    assert skills["Mechanical Lore"] == (3, 0)
    assert len(skills) == 6
    assert "SKILL" not in skills  # the header row never parses as a skill


def test_snapshot_rows_roundtrip_through_the_database():
    connection = sqlite3.connect(":memory:")
    sheet.ensure_schema(connection)
    sheet.ensure_schema(connection)  # idempotent
    sheet.insert_snapshot(
        connection,
        "Testchar",
        "2026-08-22T12:00:00+00:00",
        sheet.parse_info(INFO_TEXT),
        sheet.parse_exp_all(EXP_ALL_TEXT),
    )
    assert connection.execute("SELECT count(*) FROM stats").fetchone()[0] == 8
    assert connection.execute("SELECT count(*) FROM sheet_skills").fetchone()[0] == 6
    circle, tdps, favors = connection.execute(
        "SELECT circle, tdps, favors FROM character"
    ).fetchone()
    assert (circle, tdps, favors) == (1, 356, 0)
    top = connection.execute(
        "SELECT skill_name, rank FROM sheet_skills ORDER BY rank DESC LIMIT 1"
    ).fetchone()
    assert tuple(top) == ("Athletics", 22)
