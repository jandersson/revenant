"""How every machine's history becomes one database for beholder (#547,
#548) — these tests are the manual.

With Dropbox sync on, beholder merges each machine's snapshot in Dropbox
with this machine's own history, fresh, into one database:
every row of every machine with a `machine` column, each machine's seq
(and the *_seq columns that point at another table's rows) shifted so
the machines' numbers never collide, a row two machines both hold (a
history.db copied between them) kept once.
"""

import sqlite3

from client.game import historymerge
from client.game.historymerge import OFFSET


SCHEMA = (
    "CREATE TABLE IF NOT EXISTS mindstate (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " logged_at TEXT NOT NULL, character_name TEXT NOT NULL, skill_name TEXT,"
    " mindstate INTEGER)",
    "CREATE TABLE IF NOT EXISTS loot (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " logged_at TEXT NOT NULL, character_name TEXT NOT NULL, item TEXT)",
    "CREATE TABLE IF NOT EXISTS box_drops (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " logged_at TEXT NOT NULL, character_name TEXT NOT NULL, loot_seq INTEGER)",
)


def history(path, mindstate=(), loot=(), drops=()):
    """A history.db as the scripts write it: rows given without seq."""
    connection = sqlite3.connect(path)
    for statement in SCHEMA:
        connection.execute(statement)
    connection.executemany(
        "INSERT INTO mindstate (logged_at, character_name, skill_name, mindstate)"
        " VALUES (?, ?, ?, ?)",
        mindstate,
    )
    connection.executemany(
        "INSERT INTO loot (logged_at, character_name, item) VALUES (?, ?, ?)", loot
    )
    connection.executemany(
        "INSERT INTO box_drops (logged_at, character_name, loot_seq) VALUES (?, ?, ?)",
        drops,
    )
    connection.commit()
    connection.close()
    return path


def rows(path, sql):
    connection = sqlite3.connect(path)
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def test_two_machines_rows_are_one_table_each_named_by_its_machine(tmp_path):
    desk = history(
        tmp_path / "desk.db",
        mindstate=[("2026-10-01T10:00:00", "Lanival", "Evasion", 20)],
    )
    laptop = history(
        tmp_path / "laptop.db",
        mindstate=[
            ("2026-10-12T09:00:00", "Lanival", "Evasion", 3),
            ("2026-10-12T09:01:00", "Sable", "Athletics", 7),
        ],
    )
    out = tmp_path / "merged.db"
    taken, skipped = historymerge.merge({"laptop": laptop, "desk": desk}, out)
    assert taken == {"desk": 1, "laptop": 2} and skipped == 0
    # Machines in name order: desk keeps its seq, laptop's move up by OFFSET.
    assert rows(
        out,
        "SELECT seq, machine, character_name, mindstate FROM mindstate ORDER BY seq",
    ) == [
        (1, "desk", "Lanival", 20),
        (OFFSET + 1, "laptop", "Lanival", 3),
        (OFFSET + 2, "laptop", "Sable", 7),
    ]


def test_a_row_pointing_at_another_tables_seq_still_finds_it(tmp_path):
    # box_drops.loot_seq is the loot row the box came in (box_contents'
    # drop_seq likewise): shifted with the seq it names.
    desk = history(tmp_path / "desk.db", loot=[("t1", "Lanival", "a coin")])
    laptop = history(
        tmp_path / "laptop.db",
        loot=[("t2", "Sable", "a strongbox")],
        drops=[("t2", "Sable", 1)],
    )
    out = tmp_path / "merged.db"
    historymerge.merge({"desk": desk, "laptop": laptop}, out)
    assert rows(
        out,
        "SELECT loot.item FROM box_drops JOIN loot ON loot.seq = box_drops.loot_seq",
    ) == [("a strongbox",)]


def test_a_history_once_copied_between_machines_is_counted_once(tmp_path):
    # The laptop's history began as a copy of the desk's: the first two
    # rows are in both files, the same in every column, seq included.
    shared = [
        ("2026-08-20T10:00:00", "Lanival", "Evasion", 5),
        ("2026-08-20T10:01:00", "Lanival", "Evasion", 6),
    ]
    desk = history(tmp_path / "desk.db", mindstate=shared)
    laptop = history(tmp_path / "laptop.db", mindstate=shared)
    history(laptop, mindstate=[("2026-10-12T09:00:00", "Lanival", "Evasion", 9)])
    out = tmp_path / "merged.db"
    taken, skipped = historymerge.merge({"desk": desk, "laptop": laptop}, out)
    assert taken == {"desk": 2, "laptop": 1} and skipped == 2
    assert [m for (m,) in rows(out, "SELECT mindstate FROM mindstate")] == [5, 6, 9]


def test_a_column_only_the_newer_machine_writes_reads_null_on_the_older(tmp_path):
    old = history(tmp_path / "old.db", mindstate=[("t1", "Lanival", "Evasion", 5)])
    new = history(tmp_path / "new.db", mindstate=[("t2", "Lanival", "Evasion", 6)])
    connection = sqlite3.connect(new)
    connection.execute("ALTER TABLE mindstate ADD COLUMN is_rexp INTEGER")
    connection.execute("UPDATE mindstate SET is_rexp = 1")
    connection.commit()
    connection.close()
    out = tmp_path / "merged.db"
    historymerge.merge({"new": new, "old": old}, out)
    assert rows(out, "SELECT machine, is_rexp FROM mindstate ORDER BY logged_at") == [
        ("old", None),
        ("new", 1),
    ]


def test_merging_again_rebuilds_and_never_doubles_a_row(tmp_path):
    desk = history(tmp_path / "desk.db", mindstate=[("t1", "Lanival", "Evasion", 5)])
    out = tmp_path / "merged.db"
    historymerge.merge({"desk": desk}, out)
    history(desk, mindstate=[("t2", "Lanival", "Evasion", 6)])
    historymerge.merge({"desk": desk}, out)
    assert rows(out, "SELECT count(*) FROM mindstate") == [(2,)]
    assert not list(tmp_path.glob(".merged.db*.part"))


def test_an_index_a_source_carries_is_rebuilt(tmp_path):
    desk = history(tmp_path / "desk.db", mindstate=[("t1", "Lanival", "Evasion", 5)])
    connection = sqlite3.connect(desk)
    connection.execute(
        "CREATE UNIQUE INDEX by_moment ON mindstate (character_name, logged_at)"
    )
    connection.commit()
    connection.close()
    out = tmp_path / "merged.db"
    historymerge.merge({"desk": desk}, out)
    assert rows(
        out,
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'by_moment'",
    ) == [("by_moment",)]


def test_the_sources_are_every_snapshot_and_this_machines_own_history(tmp_path):
    base = tmp_path / "Dropbox" / "Revenant"
    for machine in ("desk", "laptop"):
        (base / machine).mkdir(parents=True)
        history(base / machine / "history.db")
    fresh = history(tmp_path / "fresh.db")
    assert historymerge.sources(base, "laptop", fresh) == {
        "desk": base / "desk" / "history.db",
        "laptop": fresh,  # this machine's own, newer than its copy there
    }
    assert historymerge.sources(None, "laptop", fresh) == {"laptop": fresh}
    assert historymerge.sources(None, "laptop", None) == {}
