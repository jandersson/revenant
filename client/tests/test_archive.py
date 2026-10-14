"""How ;archive gathers a machine's logs and history in the shared folder
(#547) — these tests are the manual.

Each machine writes only under <archive_dir>/revenant/<machine>/: logs/
gets every log that is new or has grown since the last copy, and
history.db a whole snapshot of the history database. Nothing there is
ever deleted. Unset, ;archive says how to set it; the session autostarts it
once the setting names a folder.
"""

import importlib.util
import json
import os
import pathlib
import sqlite3
from types import SimpleNamespace

import pytest

from client.game import archive

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "archive_script", REPO / "scripts/archive.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A machine: its logs, its history, its settings, and the shared folder."""
    logs = tmp_path / "logs"
    logs.mkdir()
    shared = tmp_path / "Dropbox"
    shared.mkdir()
    history = tmp_path / "history.db"
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"archive_dir": str(shared), "archive_machine": "desk"})
    )
    monkeypatch.setenv("REVENANT_LOG_DIR", str(logs))
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(history))
    monkeypatch.setenv("REVENANT_SETTINGS", str(settings))
    monkeypatch.delenv("REVENANT_ARCHIVE_DIR", raising=False)
    return SimpleNamespace(logs=logs, shared=shared, history=history, settings=settings)


def write_history(path, rows):
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS mindstate (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " logged_at TEXT, character_name TEXT, skill_name TEXT, mindstate INTEGER)"
    )
    connection.executemany(
        "INSERT INTO mindstate (logged_at, character_name, skill_name, mindstate)"
        " VALUES (?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    connection.close()


def test_logs_new_or_grown_are_copied_and_nothing_there_is_deleted(home):
    game = home.logs / "game-Lanival-20261014-200000.log"
    debug = home.logs / "revenant_client-Lanival-20261014-200000-4242.log"
    game.write_text("<prompt>&gt;</prompt>\n")
    debug.write_text("script started\n")
    (home.logs / ".DS_Store").write_text("")
    dest = home.shared / "revenant" / "desk" / "logs"
    assert archive.copy_logs(home.logs, dest) == [game.name, debug.name]
    assert archive.copy_logs(home.logs, dest) == []  # nothing new
    with game.open("a") as log:  # the session goes on writing
        log.write("You feel fully rested.\n")
    assert archive.copy_logs(home.logs, dest) == [game.name]
    assert (dest / game.name).read_text().endswith("fully rested.\n")
    debug.unlink()  # pruned locally after 7 days
    archive.copy_logs(home.logs, dest)
    assert (dest / debug.name).exists()  # still in the archive
    assert sorted(p.name for p in dest.iterdir()) == sorted([game.name, debug.name])


def test_the_history_snapshot_is_whole_and_taken_only_after_a_write(home):
    write_history(home.history, [("2026-10-14T20:00:00", "Lanival", "Evasion", 12)])
    target = home.shared / "revenant" / "desk" / "history.db"
    writer = sqlite3.connect(home.history)  # a script holding it open
    writer.execute(
        "INSERT INTO mindstate (logged_at, character_name, skill_name, mindstate)"
        " VALUES ('2026-10-14T20:01:00', 'Lanival', 'Evasion', 13)"
    )  # not committed: not in the snapshot
    assert archive.snapshot_history(home.history, target) == archive.TAKEN
    writer.rollback()
    writer.close()
    copy = sqlite3.connect(target)
    assert copy.execute("SELECT mindstate FROM mindstate").fetchall() == [(12,)]
    copy.close()
    assert not any(p.name.endswith(".part") for p in target.parent.iterdir())
    # Unwritten since: no new snapshot to sync.
    later = target.stat().st_mtime + 60
    os.utime(target, (later, later))
    assert archive.snapshot_history(home.history, target) == archive.UNCHANGED
    write_history(home.history, [("2026-10-14T21:00:00", "Lanival", "Evasion", 20)])
    os.utime(home.history, (later + 60, later + 60))
    assert archive.snapshot_history(home.history, target) == archive.TAKEN
    assert (
        archive.snapshot_history(home.shared / "none.db", target) == archive.NO_HISTORY
    )


def test_the_machine_folder_is_the_host_name_or_the_setting():
    assert archive.machine_name({}, host="Lanivals-Laptop.local") == "lanivals-laptop"
    assert archive.machine_name({}, host="DESKTOP-4G2K") == "desktop-4g2k"
    assert (
        archive.machine_name({"archive_machine": "Gaming PC"}, host="x") == "gaming-pc"
    )
    assert archive.machine_name({}, host="!!!") == "machine"


def test_the_shared_folder_is_the_setting_unless_the_environment_names_one(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("REVENANT_ARCHIVE_DIR", raising=False)
    assert archive.shared_dir({}) is None
    assert archive.shared_dir({"archive_dir": "  "}) is None
    assert archive.shared_dir({"archive_dir": str(tmp_path)}) == tmp_path
    monkeypatch.setenv("REVENANT_ARCHIVE_DIR", str(tmp_path / "other"))
    assert archive.shared_dir({"archive_dir": str(tmp_path)}) == tmp_path / "other"


class Handle:
    """The script handle ;archive uses: echo, args, and typed words."""

    def __init__(self, args=(), words=()):
        self.args = list(args)
        self.echoed = []
        self.words = list(words)

    def echo(self, text):
        self.echoed.append(text)

    def command(self, timeout=None):
        if not self.words:
            raise StopIteration  # the test's ;stop archive
        return self.words.pop(0)


def test_archive_now_copies_once_and_says_what(home):
    (home.logs / "game-Lanival-20261014-200000.log").write_text("hello\n")
    write_history(home.history, [("2026-10-14T20:00:00", "Lanival", "Evasion", 12)])
    s = Handle(args=["now"])
    _script().main(s)
    base = home.shared / "revenant" / "desk"
    assert (base / "logs" / "game-Lanival-20261014-200000.log").exists()
    assert (base / "history.db").exists()
    assert s.echoed == [f"archive: 1 log(s) copied, history taken — {base}"]


def test_without_a_shared_folder_archive_says_how_to_set_one(home):
    home.settings.write_text("{}")
    s = Handle(args=["now"])
    _script().main(s)
    assert s.echoed == [
        "archive: no shared folder — set archive_dir in ~/.revenant/settings.json "
        "(a Dropbox folder, say)"
    ]


def test_a_shared_folder_that_is_not_there_is_said_and_nothing_made(home):
    gone = home.shared / "missing"
    home.settings.write_text(json.dumps({"archive_dir": str(gone)}))
    s = Handle(args=["now"])
    _script().main(s)
    assert s.echoed == [f"archive: no folder at {gone} — is the shared folder there?"]
    assert not gone.exists()


def test_the_autostart_copies_at_once_then_every_half_hour_quietly(home, monkeypatch):
    script = _script()
    now = {"t": 0.0}
    monkeypatch.setattr(script, "clock", lambda: now["t"])
    log = home.logs / "game-Lanival-20261014-200000.log"
    log.write_text("one\n")
    copies = []
    real = archive.copy

    def counted(*args):
        copies.append(now["t"])
        return real(*args)

    monkeypatch.setattr(script.archive, "copy", counted)

    class Waiting(Handle):
        def command(self, timeout=None):
            now["t"] += timeout or 0
            if now["t"] > 65 * 60:
                raise StopIteration
            if now["t"] == 10 * 60:
                return "now"  # typed: ;archive now
            return None

    s = Waiting()
    with pytest.raises(StopIteration):
        script.main(s)
    assert copies == [0.0, 10 * 60, 40 * 60]  # at once, the typed now, 30 min on
    said = [t for t in s.echoed if "copied" in t]
    assert len(said) == 1  # only the copy asked for is said
    assert s.echoed[0].startswith("archive: logs and history to ")
