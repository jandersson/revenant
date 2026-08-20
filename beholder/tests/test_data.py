"""How beholder reads the ;xp history database."""

import pytest

from beholder import data

# Mirrors the schema scripts/xp.py creates.
SCHEMA = """
CREATE TABLE mindstate (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    percent INTEGER NOT NULL,
    mindstate INTEGER NOT NULL
)
"""

ROWS = [
    # (logged_at, character, skill, rank, percent, mindstate)
    ("2026-08-16T10:00:00+00:00", "Testchar", "Sorcery", 100, 10, 5),
    ("2026-08-16T10:00:00+00:00", "Testchar", "Evasion", 200, 20, 10),
    ("2026-08-16T10:01:00+00:00", "Testchar", "Sorcery", 100, 12, 7),
    ("2026-08-16T10:01:00+00:00", "Testchar", "Evasion", 200, 21, 9),
    ("2026-08-16T10:00:30+00:00", "Otherchar", "Athletics", 50, 5, 3),
]


@pytest.fixture
def connection(tmp_path):
    connection = data.connect(tmp_path / "xp.db")
    connection.execute(SCHEMA)
    connection.executemany(
        "INSERT INTO mindstate "
        "(logged_at, character_name, skill_name, rank, percent, mindstate) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ROWS,
    )
    connection.commit()
    yield connection
    connection.close()


def test_characters_are_distinct_and_sorted(connection):
    assert data.characters(connection) == ["Otherchar", "Testchar"]


def test_skills_are_per_character_and_sorted(connection):
    assert data.skills(connection, "Testchar") == ["Evasion", "Sorcery"]
    assert data.skills(connection, "Otherchar") == ["Athletics"]


def test_latest_snapshot_returns_only_the_newest_tick(connection):
    snapshot = data.latest_snapshot(connection, "Testchar")
    assert [row["skill_name"] for row in snapshot] == ["Evasion", "Sorcery"]
    assert all(row["logged_at"] == "2026-08-16T10:01:00+00:00" for row in snapshot)
    assert snapshot[1] == {
        "skill_name": "Sorcery",
        "rank": 100,
        "percent": 12,
        "mindstate": 7,
        "logged_at": "2026-08-16T10:01:00+00:00",
    }


def test_history_is_per_skill_series_oldest_first(connection):
    series = data.history(connection, "Testchar", ["Sorcery"])
    assert series == {
        "Sorcery": {
            "times": ["2026-08-16T10:00:00+00:00", "2026-08-16T10:01:00+00:00"],
            "mindstate": [5, 7],
            "rank": [100, 100],
        }
    }


def test_history_filters_to_requested_skills_and_character(connection):
    series = data.history(connection, "Testchar", ["Evasion", "Athletics"])
    assert list(series) == ["Evasion"]  # Athletics belongs to Otherchar


def test_history_without_skills_is_empty(connection):
    assert data.history(connection, "Testchar", []) == {}


def test_unknown_character_yields_empty_results(connection):
    assert data.skills(connection, "Nobody") == []
    assert data.latest_snapshot(connection, "Nobody") == []
    assert data.history(connection, "Nobody", ["Sorcery"]) == {}


def test_database_path_honors_the_xp_scripts_override(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_XP_DB", str(tmp_path / "elsewhere.db"))
    assert data.database_path() == tmp_path / "elsewhere.db"
