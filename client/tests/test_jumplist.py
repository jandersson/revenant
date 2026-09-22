"""The taskbar button's jump list (#226): which tasks it offers and what
each one runs. The shell registration itself is Windows COM and is
checked by hand on the pinned button; install() on another platform is
a no-op that says so.
"""

import subprocess
import sys

from client.gui import jumplist

TWO_ACCOUNTS = {
    "accounts": {
        "TESTACCT": {"account": "TESTACCT", "characters": ["Lanival", "Sable"]},
        "OTHERACCT": {"account": "OTHERACCT", "characters": ["Uthmor"]},
    }
}


def test_the_picker_leads_and_every_cached_character_follows_by_account():
    entries = jumplist.tasks(TWO_ACCOUNTS, ["C:\\app\\Revenant.exe"])
    assert [e["title"] for e in entries] == [
        jumplist.PICK_TITLE,
        "Uthmor",
        "Lanival",
        "Sable",
    ]
    assert entries[0]["arguments"] == "--pick"
    assert entries[1]["arguments"] == "Uthmor"
    assert all(e["exe"] == "C:\\app\\Revenant.exe" for e in entries)
    # several accounts: the tooltip names whose character it is
    assert entries[1]["description"] == "Launch Uthmor (OTHERACCT)"


def test_one_account_keeps_the_tooltips_plain_and_the_legacy_cache_still_lists():
    entries = jumplist.tasks(
        {"account": "TESTACCT", "character": "Lanival"}, ["Revenant.exe"]
    )
    assert [e["title"] for e in entries] == [jumplist.PICK_TITLE, "Lanival"]
    assert entries[1]["description"] == "Launch Lanival"
    assert jumplist.tasks({}, ["Revenant.exe"])[1:] == []


def test_a_source_launcher_carries_its_leading_arguments_quoted_for_the_shell():
    launcher = ["C:\\Python\\pythonw.exe", "C:\\my dev\\revenant\\tools\\desktop.py"]
    entries = jumplist.tasks({"account": "A", "character": "Sable"}, launcher)
    assert entries[0]["exe"] == "C:\\Python\\pythonw.exe"
    assert entries[0]["arguments"] == subprocess.list2cmdline(
        ["C:\\my dev\\revenant\\tools\\desktop.py", "--pick"]
    )
    assert entries[1]["arguments"].endswith(" Sable")


def test_the_packaged_build_runs_its_own_executable(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "C:\\app\\Revenant.exe")
    assert jumplist.launcher_argv() == ["C:\\app\\Revenant.exe"]


def test_from_source_the_shortcuts_windowless_entry_is_preferred(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    pythonw = tmp_path / "pythonw.exe"
    pythonw.write_bytes(b"")
    monkeypatch.setattr(sys, "_base_executable", str(tmp_path / "python.exe"))
    assert jumplist.DESKTOP_ENTRY.exists(), "tools/desktop.py moved"
    assert jumplist.launcher_argv() == [str(pythonw), str(jumplist.DESKTOP_ENTRY)]
    # no real pythonw beside the base interpreter: this interpreter, -m
    pythonw.unlink()
    assert jumplist.launcher_argv() == [sys.executable, "-m", "client.engine.launch"]


def test_install_is_a_no_op_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert jumplist.install({}) is False


def test_played_characters_lead_most_recent_first_and_the_rest_are_left_out():
    entries = jumplist.tasks(TWO_ACCOUNTS, ["Revenant.exe"], played=["sable", "Uthmor"])
    assert [e["title"] for e in entries] == [jumplist.PICK_TITLE, "Sable", "Uthmor"]
    # a snapshot of someone no longer in the roster is no task
    assert jumplist.tasks(TWO_ACCOUNTS, ["Revenant.exe"], played=["Nobody"])[1:] == [
        e for e in jumplist.tasks(TWO_ACCOUNTS, ["Revenant.exe"])[1:]
    ]


def test_the_character_tasks_are_capped():
    many = {"accounts": {"A": {"characters": [f"Name{i}" for i in range(20)]}}}
    entries = jumplist.tasks(many, ["Revenant.exe"])
    assert len(entries) == 1 + jumplist.MAX_CHARACTER_TASKS


def test_played_characters_come_from_the_sheet_snapshots(tmp_path):
    import sqlite3

    db = tmp_path / "history.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE character (seq INTEGER PRIMARY KEY, logged_at TEXT, "
            "character_name TEXT)"
        )
        conn.executemany(
            "INSERT INTO character (logged_at, character_name) VALUES (?, ?)",
            [
                ("2026-09-01T10:00:00", "Lanival"),
                ("2026-09-20T10:00:00", "Sable"),
                ("2026-09-21T10:00:00", "Lanival"),
            ],
        )
    assert jumplist.played_characters(db) == ["Lanival", "Sable"]
    assert jumplist.played_characters(tmp_path / "missing.db") == []
