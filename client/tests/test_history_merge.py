"""How every machine's history becomes one database for beholder (#547)
— these tests are the manual.

tools/history_merge.py reads each machine's snapshot in the shared
folder, this machine's own history fresh, and rebuilds one database:
every row of every machine with a `machine` column, each machine's seq
(and the *_seq columns that point at another table's rows) shifted so
the machines' numbers never collide, a row two machines both hold (a
history.db copied between them) kept once.
"""

import importlib.util
import json
import pathlib
import sqlite3

import pytest

from client.game import historymerge
from client.game.historymerge import OFFSET

REPO = pathlib.Path(__file__).parents[2]

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
    assert not (tmp_path / ".merged.db.part").exists()


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
    shared = tmp_path / "Dropbox"
    for machine in ("desk", "laptop"):
        (shared / "revenant" / machine).mkdir(parents=True)
        history(shared / "revenant" / machine / "history.db")
    fresh = history(tmp_path / "fresh.db")
    assert historymerge.sources(shared, "laptop", fresh) == {
        "desk": shared / "revenant" / "desk" / "history.db",
        "laptop": fresh,  # this machine's own, newer than its copy there
    }
    assert historymerge.sources(None, "laptop", fresh) == {"laptop": fresh}
    assert historymerge.sources(None, "laptop", None) == {}


def _tool():
    spec = importlib.util.spec_from_file_location(
        "history_merge_tool", REPO / "tools/history_merge.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def machine(tmp_path, monkeypatch):
    shared = tmp_path / "Dropbox"
    (shared / "revenant" / "desk").mkdir(parents=True)
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"archive_dir": str(shared), "archive_machine": "laptop"})
    )
    monkeypatch.setenv("REVENANT_SETTINGS", str(settings))
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.delenv("REVENANT_ARCHIVE_DIR", raising=False)
    return shared


def test_the_tool_merges_the_desks_snapshot_with_this_laptops_history(
    machine, tmp_path, capsys
):
    history(
        machine / "revenant" / "desk" / "history.db",
        mindstate=[("2026-10-01T10:00:00", "Lanival", "Evasion", 20)],
    )
    history(
        tmp_path / "history.db",
        mindstate=[("2026-10-14T20:00:00", "Lanival", "Evasion", 4)],
    )
    out = tmp_path / "merged.db"
    assert _tool().main(["--out", str(out)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "desk: 1 rows",
        "laptop: 1 rows",
        f"merged 2 machine(s) into {out}",
    ]
    assert rows(out, "SELECT machine, mindstate FROM mindstate ORDER BY logged_at") == [
        ("desk", 20),
        ("laptop", 4),
    ]


def test_the_tool_names_a_shared_folder_that_is_not_there(machine, tmp_path, capsys):
    assert _tool().main(["--dir", str(tmp_path / "nowhere")]) == 1
    assert capsys.readouterr().out.strip() == f"no folder at {tmp_path / 'nowhere'}"
