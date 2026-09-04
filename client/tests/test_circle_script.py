"""How ;circle answers — the manual.

The script computes the guildleader's advice from the latest ;sheet
snapshot in xp.db; nothing is sent to the game. The model itself is
pinned in test_circles; here we cover the script's reading and report.
"""

import importlib.util
import pathlib
import sqlite3

from test_circles import ROSTER
from test_sheet import sheet

REPO = pathlib.Path(__file__).parents[2]


def _circle():
    spec = importlib.util.spec_from_file_location(
        "circle_script", REPO / "scripts/circle.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


circle = _circle()


class FakeHandle:
    state = None

    def __init__(self):
        self.echoed = []

    def echo(self, text):
        self.echoed.append(text)


def seed_snapshot(path, character="Lanival", logged_at="2026-08-22T12:00:00+00:00"):
    connection = sqlite3.connect(path)
    sheet.ensure_schema(connection)
    connection.executemany(
        "INSERT INTO sheet_skills"
        " (logged_at, character_name, skill_name, rank, percent)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (logged_at, character, skill, rank, percent)
            for skill, (rank, percent) in ROSTER.items()
        ],
    )
    connection.execute(
        "INSERT INTO character"
        " (logged_at, character_name, circle, tdps, favors, guild)"
        " VALUES (?, ?, 1, 356, 0, 'Thief')",
        (logged_at, character),
    )
    connection.commit()
    connection.close()


def test_circle_reports_gates_from_the_latest_snapshot(monkeypatch, tmp_path):
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    monkeypatch.setenv("REVENANT_XP_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle()
    circle.main(handle)
    text = "\n".join(handle.echoed)
    assert "gates to circle 2:" in text
    assert "armor: 1st Armor (Light Armor) 3/4" in text
    assert "weapon: 1st Weapon (Small Edged) 3/6, Parry Ability 1/2" in text
    assert "1st Supernatural (Augmentation) 1/2" in text
    assert "8th Survival (First Aid) 1/2" in text
    assert "from Lanival's sheet snapshot" in text


def test_circle_without_a_snapshot_points_at_sheet(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "xp.db"))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle()
    circle.main(handle)
    assert any("run ;sheet once first" in line for line in handle.echoed)


def test_circle_for_a_guild_without_circles(monkeypatch, tmp_path):
    database = tmp_path / "xp.db"
    seed_snapshot(database)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE character SET guild = 'Commoner'")
    connection.commit()
    connection.close()
    monkeypatch.setenv("REVENANT_XP_DB", str(database))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    handle = FakeHandle()
    circle.main(handle)
    assert any("no circle requirements" in line for line in handle.echoed)
