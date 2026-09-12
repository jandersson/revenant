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
    rows = xp.snapshot_rows(EXPERIENCE, "Lanival", "2026-08-13T02:00:00+00:00")
    assert rows == [
        ("2026-08-13T02:00:00+00:00", "Lanival", "Athletics", 346, 13, 11, None),
        ("2026-08-13T02:00:00+00:00", "Lanival", "Attunement", 520, 42, 17, None),
    ]
    # The rested flag rides every row of the minute (#176).
    rows = xp.snapshot_rows(EXPERIENCE, "Lanival", "2026-08-13T02:01:00+00:00", True)
    assert [row[-1] for row in rows] == [1, 1]


def test_rows_roundtrip_through_the_database():
    connection = sqlite3.connect(":memory:")
    xp.ensure_schema(connection)
    xp.ensure_schema(connection)  # idempotent: safe on every start
    xp.insert(
        connection, xp.snapshot_rows(EXPERIENCE, "Lanival", "2026-08-13T02:00:00Z")
    )
    stored = connection.execute(
        "SELECT character_name, skill_name, rank, percent, mindstate, is_rexp "
        "FROM mindstate ORDER BY skill_name"
    ).fetchall()
    assert stored == [
        ("Lanival", "Athletics", 346, 13, 11, None),
        ("Lanival", "Attunement", 520, 42, 17, None),
    ]


def test_a_mindstate_table_from_before_the_flag_gains_the_column():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE mindstate (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " skill_name TEXT NOT NULL, rank INTEGER NOT NULL,"
        " percent INTEGER NOT NULL, mindstate INTEGER NOT NULL)"
    )
    connection.execute(
        "INSERT INTO mindstate (logged_at, character_name, skill_name, rank,"
        " percent, mindstate) VALUES ('2026-08-13T02:00:00Z', 'Lanival',"
        " 'Athletics', 346, 13, 11)"
    )
    xp.ensure_schema(connection)
    assert connection.execute("SELECT is_rexp FROM mindstate").fetchall() == [(None,)]
    assert connection.execute("SELECT COUNT(*) FROM rested").fetchone() == (0,)


def test_a_minute_logs_the_flag_from_the_banks_movement_and_the_footer_once():
    # #176: the flag is the usable figure falling since the previous
    # minute; the footer goes to the rested table only when it changed.
    connection = sqlite3.connect(":memory:")
    xp.ensure_schema(connection)
    full = {"stored": 345, "usable": 331, "refresh": 79}
    less = {"stored": 344, "usable": 330, "refresh": 78}
    seen = logged = None
    seen, logged = xp.snapshot(
        connection, "Lanival", "T1", EXPERIENCE, full, seen, logged
    )
    seen, logged = xp.snapshot(
        connection, "Lanival", "T2", EXPERIENCE, less, seen, logged
    )
    seen, logged = xp.snapshot(
        connection, "Lanival", "T3", EXPERIENCE, less, seen, logged
    )
    seen, logged = xp.snapshot(connection, "Lanival", "T4", {}, less, seen, logged)
    flags = connection.execute(
        "SELECT logged_at, is_rexp FROM mindstate WHERE skill_name = 'Athletics'"
        " ORDER BY seq"
    ).fetchall()
    assert flags == [("T1", None), ("T2", 1), ("T3", 0)]  # T4: nothing learning
    assert connection.execute(
        "SELECT logged_at, stored, usable, refresh FROM rested ORDER BY seq"
    ).fetchall() == [("T1", 345, 331, 79), ("T2", 344, 330, 78)]
    # No footer yet (a session before the first pulse): rows unflagged.
    seen, logged = xp.snapshot(
        connection, "Lanival", "T5", EXPERIENCE, None, None, None
    )
    assert connection.execute(
        "SELECT is_rexp FROM mindstate WHERE logged_at = 'T5'"
    ).fetchall() == [(None,), (None,)]
