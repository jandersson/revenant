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


class FakeHandle:
    """The script-engine surface ;sheet uses, with per-attempt canned
    answers: responses[command] is a list of answers, consumed one per
    put()."""

    def __init__(self, responses):
        self.responses = {c: list(seqs) for c, seqs in responses.items()}
        self.pending = []
        self.echoed = []
        self.slept = 0
        self.state = None

    def put(self, command):
        seqs = self.responses.get(command, [])
        self.pending = list(seqs.pop(0)) if seqs else []

    def get(self, timeout=None):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def sleep(self, seconds):
        self.slept += seconds


def snapshot_into(monkeypatch, tmp_path, responses):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    monkeypatch.setenv("REVENANT_CHARACTER", "Testchar")
    monkeypatch.setattr(sheet, "COLLECT_SECONDS", 0.05)
    handle = FakeHandle(responses)
    sheet.snapshot(handle)
    connection = sqlite3.connect(tmp_path / "xp.db")
    return handle, connection


def test_snapshot_reasks_a_command_the_game_ate(monkeypatch, tmp_path):
    # Captured 2026-08-22 (#65): the session-start INFO went
    # unanswered while EXP ALL answered fine. The re-ask recovers it.
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [[], INFO_TEXT.splitlines()],
            "exp all": [EXP_ALL_TEXT.splitlines()],
        },
    )
    assert handle.slept > 0  # a retry pause happened
    circle, tdps = connection.execute("SELECT circle, tdps FROM character").fetchone()
    assert (circle, tdps) == (1, 356)
    assert any("circle 1" in line for line in handle.echoed)


def test_snapshot_never_stores_an_all_none_character_row(monkeypatch, tmp_path):
    handle, connection = snapshot_into(
        monkeypatch,
        tmp_path,
        {
            "info": [[], [], []],  # every ask goes unanswered
            "exp all": [EXP_ALL_TEXT.splitlines()],
        },
    )
    assert connection.execute("SELECT count(*) FROM character").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM stats").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM sheet_skills").fetchone()[0] == 6
    assert any("INFO went unanswered" in line for line in handle.echoed)


def test_collect_stops_at_the_answers_final_line():
    handle = FakeHandle({})
    handle.pending = INFO_TEXT.splitlines() + ["later, unrelated text"]
    text = sheet.collect(handle, seconds=5, until=sheet.INFO_END)
    assert "Encumbrance" in text
    # The final line ended the wait: what followed was never consumed.
    assert handle.pending == ["later, unrelated text"]


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
