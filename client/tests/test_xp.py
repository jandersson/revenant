"""How ;xp logs experience history — these tests are the manual.

Every snapshot writes one row per learning skill into the mindstate
table; the Experience dock is the live view, this database is the
history that plots and analysis read (beholder's successor).
"""

import importlib.util
import pathlib
import sqlite3

from client.game.rested import Minute

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


def window(reading, count):
    return {"reading": reading, "count": count, "window": True, "source": "window"}


def answer(reading, count):
    return {"reading": reading, "count": count, "window": False, "source": "exp"}


def test_a_minute_logs_the_flag_from_the_banks_movement_and_the_footer_once():
    # #176: the flag comes from the usable figure falling; #346: it stays
    # up while the footer sits between falls. The footer goes to the
    # rested table only when it changed.
    connection = sqlite3.connect(":memory:")
    xp.ensure_schema(connection)
    full = {"stored": 345, "usable": 331, "refresh": 79}
    less = {"stored": 344, "usable": 330, "refresh": 78}
    minute, logged = Minute(), None
    for at, experience, found in (
        ("T1", EXPERIENCE, window(full, 1)),
        ("T2", EXPERIENCE, window(less, 5)),
        ("T3", EXPERIENCE, window(less, 9)),
        ("T4", {}, window(less, 12)),
    ):
        now = int(at[1])
        logged = xp.snapshot(
            connection, "Lanival", at, experience, now, found, minute, logged
        )
    flags = connection.execute(
        "SELECT logged_at, is_rexp FROM mindstate WHERE skill_name = 'Athletics'"
        " ORDER BY seq"
    ).fetchall()
    # T1: no fall seen yet, so the reading's age says it (#176's NULL
    # before); T4: nothing learning.
    assert flags == [("T1", 1), ("T2", 1), ("T3", 1)]
    assert connection.execute(
        "SELECT logged_at, stored, usable, refresh, source FROM rested ORDER BY seq"
    ).fetchall() == [("T1", 345, 331, 79, "window"), ("T2", 344, 330, 78, "window")]
    # No footer yet (a session before the first pulse): rows unflagged.
    none = {"reading": None, "count": 0, "window": True, "source": "window"}
    xp.snapshot(connection, "Lanival", "T5", EXPERIENCE, 5, none, Minute(), None)
    assert connection.execute(
        "SELECT is_rexp FROM mindstate WHERE logged_at = 'T5'"
    ).fetchall() == [(None,), (None,)]


def test_an_empty_window_flags_from_the_last_exp_answer_and_logs_each_one():
    # One account's exp window leaves the footer empty (2026-09-28): the
    # EXP answers' footers are all there is — ;sheet's EXP ALL at login,
    # a script's EXP ATTUNEMENT later.
    connection = sqlite3.connect(":memory:")
    xp.ensure_schema(connection)
    login = {"stored": 360, "usable": 360, "refresh": 1409}
    later = {"stored": 349, "usable": 349, "refresh": 1312}
    minute, logged = Minute(), None
    for at, now, found in (
        ("T0", 0, answer(login, 1)),
        ("T1", 1, answer(login, 1)),  # no new answer: not logged again
        ("T2", 97, answer(later, 2)),
        ("T3", 98, answer(later, 3)),  # the same figures, a fresh answer
        ("T4", 500, answer(later, 3)),  # 402 minutes on: it may have run out
    ):
        logged = xp.snapshot(
            connection, "Lanival", at, EXPERIENCE, now, found, minute, logged
        )
    flags = connection.execute(
        "SELECT logged_at, is_rexp FROM mindstate WHERE skill_name = 'Athletics'"
        " ORDER BY seq"
    ).fetchall()
    assert flags == [("T0", 1), ("T1", 1), ("T2", 1), ("T3", 1), ("T4", None)]
    assert connection.execute(
        "SELECT logged_at, usable, source FROM rested ORDER BY seq"
    ).fetchall() == [("T0", 360, "exp"), ("T2", 349, "exp"), ("T3", 349, "exp")]


def test_the_parsers_footer_reads_old_and_new_parsers_alike():
    # A parser from before the EXP answers' footers: every reading is
    # the window's, and a changed reading dates it.
    old = type("State", (), {"rested": {"stored": 1, "usable": 1, "refresh": 2}})()
    assert xp.footer(old) == {
        "reading": {"stored": 1, "usable": 1, "refresh": 2},
        "count": None,
        "window": True,
        "source": "window",
    }
    new = type(
        "State",
        (),
        {
            "rested": None,
            "rested_count": 0,
            "rested_window": False,
            "rested_source": None,
        },
    )()
    assert xp.footer(new)["window"] is False
    assert xp.footer(None)["reading"] is None


def test_a_rested_table_from_before_the_source_gains_the_column():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE rested (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT NOT NULL, character_name TEXT NOT NULL,"
        " stored INTEGER, usable INTEGER, refresh INTEGER)"
    )
    connection.execute(
        "INSERT INTO rested (logged_at, character_name, stored, usable, refresh)"
        " VALUES ('T', 'Lanival', 1, 1, 1)"
    )
    xp.ensure_schema(connection)
    assert connection.execute("SELECT source FROM rested").fetchall() == [(None,)]
