"""How ;xp logs experience history — these tests are the manual.

Every snapshot writes one row per learning skill into the mindstate
table; the Experience dock is the live view, this database is the
history that plots and analysis read (beholder's successor).
"""

import importlib.util
import pathlib
import sqlite3

REPO = pathlib.Path(__file__).parents[2]


def _xp():
    spec = importlib.util.spec_from_file_location("xp_script", REPO / "scripts/xp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


xp = _xp()

EXPERIENCE = {
    "Athletics": {"rank": 346, "percent": 13, "mindstate": 11, "rate": "deliberative"},
    "Attunement": {"rank": 520, "percent": 42, "mindstate": 17, "rate": "scrutinizing"},
}


def test_one_row_per_learning_skill_per_snapshot():
    rows = xp.snapshot_rows(EXPERIENCE, "Testchar", "2026-08-13T02:00:00+00:00")
    assert rows == [
        ("2026-08-13T02:00:00+00:00", "Testchar", "Athletics", 346, 13, 11),
        ("2026-08-13T02:00:00+00:00", "Testchar", "Attunement", 520, 42, 17),
    ]


def test_rows_roundtrip_through_the_database():
    connection = sqlite3.connect(":memory:")
    xp.ensure_schema(connection)
    xp.ensure_schema(connection)  # idempotent: safe on every start
    xp.insert(
        connection, xp.snapshot_rows(EXPERIENCE, "Testchar", "2026-08-13T02:00:00Z")
    )
    stored = connection.execute(
        "SELECT character_name, skill_name, rank, percent, mindstate "
        "FROM mindstate ORDER BY skill_name"
    ).fetchall()
    assert stored == [
        ("Testchar", "Athletics", 346, 13, 11),
        ("Testchar", "Attunement", 520, 42, 17),
    ]
