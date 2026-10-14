"""How Dropbox sync gathers every machine's logs and history (#547,
#548) — these tests are the manual.

The Dropbox folder is the one Dropbox's info.json names. Each machine
writes only under <Dropbox>/Revenant/<machine>/: logs/ gets every log
that is new or has grown since the last copy, history.db a whole
snapshot of the history. Nothing there is ever deleted. Beholder, with
sync on, reads a merged history rebuilt when a machine's snapshot or
this one's history is newer. The session autostarts ;dropbox once the
Settings checkbox is ticked.
"""

import importlib.util
import json
import os
import pathlib
import sqlite3
from types import SimpleNamespace

import pytest

from client.game import dropbox

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "dropbox_script", REPO / "scripts/dropbox.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A machine: its logs, its history, its settings, and its Dropbox."""
    logs = tmp_path / "logs"
    logs.mkdir()
    box = tmp_path / "Dropbox"
    box.mkdir()
    history = tmp_path / "history.db"
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {"dropbox_sync": True, "dropbox_dir": str(box), "dropbox_machine": "desk"}
        )
    )
    monkeypatch.setenv("REVENANT_LOG_DIR", str(logs))
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(history))
    monkeypatch.setenv("REVENANT_SETTINGS", str(settings))
    monkeypatch.delenv("REVENANT_DROPBOX_DIR", raising=False)
    return SimpleNamespace(logs=logs, box=box, history=history, settings=settings)


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


# -- finding Dropbox ----------------------------------------------------------


def test_the_dropbox_folder_is_the_one_its_info_json_names(tmp_path):
    # Dropbox Help: ~/.dropbox/info.json on macOS and Linux, the personal
    # account before a business one.
    personal, business = tmp_path / "Dropbox Pro", tmp_path / "Dropbox (Work)"
    personal.mkdir()
    business.mkdir()
    (tmp_path / ".dropbox").mkdir()
    (tmp_path / ".dropbox" / "info.json").write_text(
        json.dumps(
            {
                "business": {"path": str(business), "is_team": True},
                "personal": {"path": str(personal), "is_team": False},
            }
        )
    )
    assert dropbox.find_dropbox(home=tmp_path, environ={}) == personal


def test_on_windows_info_json_is_under_appdata_or_localappdata(tmp_path):
    folder = tmp_path / "Dropbox"
    folder.mkdir()
    local = tmp_path / "Local"
    (local / "Dropbox").mkdir(parents=True)
    (local / "Dropbox" / "info.json").write_text(
        json.dumps({"business": {"path": str(folder)}})
    )
    found = dropbox.find_dropbox(
        home=tmp_path / "nobody", environ={"LOCALAPPDATA": str(local)}
    )
    assert found == folder


def test_without_info_json_home_dropbox_is_the_folder_or_there_is_none(tmp_path):
    assert dropbox.find_dropbox(home=tmp_path, environ={}) is None
    (tmp_path / "Dropbox").mkdir()
    assert dropbox.find_dropbox(home=tmp_path, environ={}) == tmp_path / "Dropbox"


def test_a_setting_or_the_environment_names_another_synced_folder(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("REVENANT_DROPBOX_DIR", raising=False)
    monkeypatch.setattr(dropbox, "find_dropbox", lambda: tmp_path / "found")
    assert dropbox.shared_dir({}) == tmp_path / "found"
    assert dropbox.shared_dir({"dropbox_dir": str(tmp_path / "OneDrive")}) == (
        tmp_path / "OneDrive"
    )
    monkeypatch.setenv("REVENANT_DROPBOX_DIR", str(tmp_path / "other"))
    assert dropbox.shared_dir({"dropbox_dir": "x"}) == tmp_path / "other"


def test_the_machine_folder_is_the_host_name_or_the_setting():
    assert dropbox.machine_name({}, host="Lanivals-Laptop.local") == "lanivals-laptop"
    assert dropbox.machine_name({}, host="DESKTOP-4G2K") == "desktop-4g2k"
    assert dropbox.machine_name({"dropbox_machine": "Gaming PC"}, host="x") == (
        "gaming-pc"
    )
    assert dropbox.machine_name({}, host="!!!") == "machine"


# -- the copy -----------------------------------------------------------------


def test_logs_new_or_grown_are_copied_and_nothing_there_is_deleted(home):
    game = home.logs / "game-Lanival-20261014-200000.log"
    debug = home.logs / "revenant_client-Lanival-20261014-200000-4242.log"
    game.write_text("<prompt>&gt;</prompt>\n")
    debug.write_text("script started\n")
    (home.logs / ".DS_Store").write_text("")
    dest = home.box / "Revenant" / "desk" / "logs"
    assert dropbox.copy_logs(home.logs, dest) == [game.name, debug.name]
    assert dropbox.copy_logs(home.logs, dest) == []  # nothing new
    with game.open("a") as log:  # the session goes on writing
        log.write("You feel fully rested.\n")
    assert dropbox.copy_logs(home.logs, dest) == [game.name]
    assert (dest / game.name).read_text().endswith("fully rested.\n")
    debug.unlink()  # pruned locally after 7 days
    dropbox.copy_logs(home.logs, dest)
    assert (dest / debug.name).exists()  # still in Dropbox
    assert sorted(p.name for p in dest.iterdir()) == sorted([game.name, debug.name])


def test_the_history_snapshot_is_whole_and_taken_only_after_a_write(home):
    write_history(home.history, [("2026-10-14T20:00:00", "Lanival", "Evasion", 12)])
    target = home.box / "Revenant" / "desk" / "history.db"
    writer = sqlite3.connect(home.history)  # a script holding it open
    writer.execute(
        "INSERT INTO mindstate (logged_at, character_name, skill_name, mindstate)"
        " VALUES ('2026-10-14T20:01:00', 'Lanival', 'Evasion', 13)"
    )  # not committed: not in the snapshot
    assert dropbox.snapshot_history(home.history, target) == dropbox.TAKEN
    writer.rollback()
    writer.close()
    copy = sqlite3.connect(target)
    assert copy.execute("SELECT mindstate FROM mindstate").fetchall() == [(12,)]
    copy.close()
    assert not any(p.name.endswith(".part") for p in target.parent.iterdir())
    # Unwritten since: no new snapshot to sync.
    later = target.stat().st_mtime + 60
    os.utime(target, (later, later))
    assert dropbox.snapshot_history(home.history, target) == dropbox.UNCHANGED
    write_history(home.history, [("2026-10-14T21:00:00", "Lanival", "Evasion", 20)])
    os.utime(home.history, (later + 60, later + 60))
    assert dropbox.snapshot_history(home.history, target) == dropbox.TAKEN
    assert dropbox.snapshot_history(home.box / "none.db", target) == dropbox.NO_HISTORY


# -- what beholder reads ------------------------------------------------------


def test_with_sync_on_beholder_reads_every_machines_history(home, monkeypatch):
    laptop = home.box / "Revenant" / "laptop"
    laptop.mkdir(parents=True)
    write_history(
        laptop / "history.db", [("2026-10-01T10:00:00", "Sable", "Evasion", 3)]
    )
    write_history(home.history, [("2026-10-14T20:00:00", "Lanival", "Evasion", 12)])
    settings = json.loads(home.settings.read_text())
    merged = dropbox.merged_history(settings, home.history)
    assert merged == home.history.with_name("merged.db")
    connection = sqlite3.connect(merged)
    assert connection.execute(
        "SELECT machine, character_name FROM mindstate ORDER BY logged_at"
    ).fetchall() == [("laptop", "Sable"), ("desk", "Lanival")]
    connection.close()
    assert dropbox.merged_history({"dropbox_sync": False}, home.history) is None


def test_the_merge_is_rebuilt_only_when_a_source_is_newer_and_at_most_once_a_minute(
    home, monkeypatch
):
    write_history(home.history, [("t1", "Lanival", "Evasion", 1)])
    settings = json.loads(home.settings.read_text())
    builds = []
    real = dropbox.rebuild
    monkeypatch.setattr(
        dropbox, "rebuild", lambda *args: builds.append(1) or real(*args)
    )
    now = {"t": home.history.stat().st_mtime + 5}
    monkeypatch.setattr(dropbox, "clock", lambda: now["t"])
    out = dropbox.merged_history(settings, home.history)
    built = out.stat().st_mtime
    assert len(builds) == 1
    dropbox.merged_history(settings, home.history)
    assert len(builds) == 1  # nothing newer
    os.utime(home.history, (built + 10, built + 10))  # ;xp wrote a row
    now["t"] = built + 30
    dropbox.merged_history(settings, home.history)
    assert len(builds) == 1  # newer, but built 30 seconds ago
    now["t"] = built + dropbox.MERGE_SECONDS
    dropbox.merged_history(settings, home.history)
    assert len(builds) == 2


# -- ;dropbox -----------------------------------------------------------------


class Handle:
    """The script handle ;dropbox uses: echo, args, and typed words."""

    def __init__(self, args=(), words=()):
        self.args = list(args)
        self.echoed = []
        self.words = list(words)

    def echo(self, text):
        self.echoed.append(text)

    def command(self, timeout=None):
        if not self.words:
            raise StopIteration  # the test's ;stop dropbox
        return self.words.pop(0)


def test_dropbox_now_copies_once_and_says_what(home):
    (home.logs / "game-Lanival-20261014-200000.log").write_text("hello\n")
    write_history(home.history, [("2026-10-14T20:00:00", "Lanival", "Evasion", 12)])
    s = Handle(args=["now"])
    _script().main(s)
    base = home.box / "Revenant" / "desk"
    assert (base / "logs" / "game-Lanival-20261014-200000.log").exists()
    assert (base / "history.db").exists()
    assert s.echoed == [f"dropbox: 1 log(s) copied, history taken — {base}"]


def test_without_a_dropbox_folder_it_says_how_to_get_one(home, monkeypatch):
    home.settings.write_text(json.dumps({"dropbox_sync": True}))
    monkeypatch.setattr(dropbox, "find_dropbox", lambda: None)
    s = Handle(args=["now"])
    _script().main(s)
    assert s.echoed == [
        "dropbox: no Dropbox folder on this computer — install Dropbox, or set "
        "dropbox_dir in ~/.revenant/settings.json to a synced folder"
    ]


def test_a_folder_that_is_not_there_is_said_and_nothing_made(home):
    gone = home.box / "missing"
    home.settings.write_text(json.dumps({"dropbox_dir": str(gone)}))
    s = Handle(args=["now"])
    _script().main(s)
    assert s.echoed == [f"dropbox: no folder at {gone} — is Dropbox running here?"]
    assert not gone.exists()


def test_the_autostart_copies_at_once_then_every_ten_minutes_quietly(home, monkeypatch):
    script = _script()
    now = {"t": 0.0}
    monkeypatch.setattr(script, "clock", lambda: now["t"])
    (home.logs / "game-Lanival-20261014-200000.log").write_text("one\n")
    copies = []
    real = dropbox.copy

    def counted(*args):
        copies.append(now["t"])
        return real(*args)

    monkeypatch.setattr(script.dropbox, "copy", counted)

    class Waiting(Handle):
        def command(self, timeout=None):
            now["t"] += timeout or 0
            if now["t"] > 25 * 60:
                raise StopIteration
            if now["t"] == 3 * 60:
                return "now"  # typed: ;dropbox now
            return None

    s = Waiting()
    with pytest.raises(StopIteration):
        script.main(s)
    assert copies == [0.0, 3 * 60, 13 * 60, 23 * 60]  # at once, typed, every 10 min
    said = [t for t in s.echoed if "copied" in t]
    assert len(said) == 1  # only the copy asked for is said
    assert s.echoed[0].startswith("dropbox: logs and history to ")
