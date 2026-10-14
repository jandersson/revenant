"""Dropbox sync (#547, #548, #549): every machine's logs and history
gathered in Dropbox, and beholder reading all of them — one checkbox in
File → Settings, nothing to run by hand.

With `dropbox_sync` on, each session autostarts ;dropbox, which every
INTERVAL_MINUTES copies into <Dropbox>/Revenant/:

    <Character>/<log>.<machine>.log    every log that is new there or has
                                       grown since the last copy, filed
                                       by the character its name carries
    _other/<log>.<machine>.log         a log with no character in its name
    _history/history.<machine>.db      a snapshot of ~/.revenant/history.db,
                                       every character inside

A character's folder holds its logs from every machine, each machine
named in the file; _other and _history start with an underscore, which
no character name can.

and beholder, asked for the history, reads merged_history(): one
database rebuilt from every machine's snapshot and this machine's own
history (client/game/historymerge.py), at most once a minute and only
when a source is newer.

The Dropbox folder is the one Dropbox's own info.json names
(Dropbox Help: "How to find the Dropbox folder on a computer"), the
personal account before a business one, else ~/Dropbox; the
`dropbox_dir` setting or REVENANT_DROPBOX_DIR names any other synced
folder instead. <machine> is the host name, or `dropbox_machine`.

The game logs are append-only and named by character and start time,
so two machines never write the same file and copying them together
loses nothing. history.db is different: every table keys on its own
autoincrement seq, so two machines' files cannot be synced as one —
each copies a snapshot and the merge joins them. The snapshot is taken
with SQLite's backup API, safe while scripts write, into a temporary
file moved into place, so a sync never picks up half a database.
Nothing in Dropbox is ever deleted, and each machine keeps writing its
own local files, so a sync problem never touches a running session.
"""

import json
import os
import re
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

from client.game import historymerge

ENV = "REVENANT_DROPBOX_DIR"
FOLDER = "Revenant"  # inside the Dropbox folder: one folder per character below it
OTHER = "_other"  # the logs whose names carry no character
HISTORY = "_history"  # one history snapshot per machine
# The character a log's name carries: game-, lnet-, revenant_client- and
# drive-<Name>-<YYYYMMDD>-<HHMMSS> (client_logger.py, tools/drive.py).
_CHARACTER = re.compile(r"^[a-z_]+-([A-Za-z]+)-\d{8}-\d{6}")
INTERVAL_MINUTES = 10  # between ;dropbox's copies
MERGE_SECONDS = 60  # the merged history is rebuilt at most this often

# snapshot_history's answers.
TAKEN = "taken"
UNCHANGED = "unchanged"
NO_HISTORY = "no history"

clock = time.time  # tests replace it
_MERGING = threading.Lock()  # beholder's callbacks run on several threads


def info_files(home=None, environ=None):
    """Where Dropbox keeps info.json: ~/.dropbox/ on macOS and Linux,
    %APPDATA%\\Dropbox\\ or %LOCALAPPDATA%\\Dropbox\\ on Windows."""
    home = Path(home) if home is not None else Path.home()
    environ = os.environ if environ is None else environ
    places = [home / ".dropbox" / "info.json"]
    for variable in ("APPDATA", "LOCALAPPDATA"):
        if environ.get(variable):
            places.append(Path(environ[variable]) / "Dropbox" / "info.json")
    return places


def find_dropbox(home=None, environ=None):
    """The Dropbox folder on this computer, or None: the path info.json
    names (the personal account first), else ~/Dropbox when it exists."""
    home = Path(home) if home is not None else Path.home()
    for place in info_files(home, environ):
        try:
            accounts = json.loads(place.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for kind in ("personal", "business"):
            entry = accounts.get(kind) if isinstance(accounts, dict) else None
            path = entry.get("path") if isinstance(entry, dict) else None
            if path and Path(path).is_dir():
                return Path(path)
    fallback = home / "Dropbox"
    return fallback if fallback.is_dir() else None


def shared_dir(settings):
    """The folder synced between machines: REVENANT_DROPBOX_DIR, else
    the `dropbox_dir` setting, else the Dropbox folder found here; None
    when there is none."""
    value = os.environ.get(ENV) or str(settings.get("dropbox_dir") or "")
    if value.strip():
        return Path(value).expanduser()
    return find_dropbox()


def machine_name(settings, host=None):
    """This machine's folder name: the `dropbox_machine` setting, else
    the host name, lowercased, a trailing .local/.lan/.home dropped, and
    any run of characters but letters, digits, _ and - made one "-"."""
    value = str(settings.get("dropbox_machine") or "").strip()
    value = (value or host or socket.gethostname()).lower()
    value = re.sub(r"\.(local|lan|home)$", "", value)
    value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-")
    return value or "machine"


def character_of(name):
    """The character a log's file name carries, or None (a process
    before login, the legacy logs)."""
    match = _CHARACTER.match(name)
    return match.group(1).capitalize() if match else None


def tagged(name, machine):
    """The log's name with its machine before .log:
    game-Lanival-20261014-200000.calculon.log (a rotated debug log's
    .log.1 likewise)."""
    if ".log" in name:
        return name.replace(".log", f".{machine}.log", 1)
    return f"{name}.{machine}"


def log_target(root, name, machine):
    """Where a log goes: <root>/Revenant/<Character or _other>/<tagged>."""
    folder = character_of(name) or OTHER
    return Path(root) / FOLDER / folder / tagged(name, machine)


def history_target(root, machine):
    """Where this machine's history snapshot goes."""
    return Path(root) / FOLDER / HISTORY / f"history.{machine}.db"


def copy_logs(source, root, machine):
    """Every file in `source` (no subfolders, no dot-files) copied to its
    log_target when it is missing there, a different size, or newer: the
    names copied. A copy goes to a dot-file beside it first and is moved
    into place. Nothing in Dropbox is ever deleted — a debug log pruned
    locally after 7 days stays there."""
    source = Path(source)
    copied = []
    if not source.is_dir():
        return copied
    for path in sorted(source.iterdir()):
        if path.name.startswith(".") or not path.is_file():
            continue
        target = log_target(root, path.name, machine)
        target.parent.mkdir(parents=True, exist_ok=True)
        here = path.stat()
        if target.exists():
            there = target.stat()
            if there.st_size == here.st_size and there.st_mtime >= here.st_mtime:
                continue
        part = target.with_name(f".{target.name}.part")
        shutil.copy2(path, part)  # the mtime too: the next look compares it
        os.replace(part, target)
        copied.append(path.name)
    return copied


def snapshot_history(source, target):
    """A whole, consistent copy of the history database at `target`:
    TAKEN; UNCHANGED when the database has not been written since the
    last snapshot; NO_HISTORY when there is none yet."""
    source, target = Path(source), Path(target)
    if not source.exists():
        return NO_HISTORY
    if target.exists() and source.stat().st_mtime < target.stat().st_mtime:
        return UNCHANGED
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(f".{target.name}.part")
    if part.exists():
        part.unlink()
    reader = sqlite3.connect(source)
    try:
        writer = sqlite3.connect(part)
        try:
            reader.backup(writer)
        finally:
            writer.close()
    finally:
        reader.close()
    os.replace(part, target)
    return TAKEN


def copy(root, machine, logs, history):
    """One copy into <root>/Revenant/: (the log names copied, the
    snapshot's answer)."""
    copied = copy_logs(logs, root, machine)
    return copied, snapshot_history(history, history_target(root, machine))


def merged_history(settings, local):
    """The history every machine logged, for beholder: merged.db beside
    `local` (this machine's history.db), rebuilt first when a source is
    newer than it and the last build is MERGE_SECONDS old. None when
    Dropbox sync is off or there is no folder — read `local` then."""
    if not settings.get("dropbox_sync"):
        return None
    root = shared_dir(settings)
    if root is None or not root.is_dir():
        return None
    local = Path(local)
    out = local.with_name("merged.db")
    with _MERGING:
        snapshots = sorted((root / FOLDER / HISTORY).glob("history.*.db"))
        newest = max(
            (path.stat().st_mtime for path in [*snapshots, local] if path.exists()),
            default=0.0,
        )
        built = out.stat().st_mtime if out.exists() else None
        stale = built is None or newest > built
        if stale and (built is None or clock() - built >= MERGE_SECONDS):
            try:
                rebuild(root, machine_name(settings), local, out)
            except (OSError, sqlite3.Error):
                pass  # a file in use (Windows) or mid-sync: the last build stands
    return out if out.exists() else None


def rebuild(root, machine, local, out):
    """merged.db rebuilt: this machine's history read from a fresh
    snapshot, so the merge never holds the live file's lock while the
    session writes."""
    with tempfile.TemporaryDirectory() as scratch:
        fresh = Path(scratch) / "history.db"
        if snapshot_history(local, fresh) == NO_HISTORY:
            fresh = None
        found = historymerge.sources(Path(root) / FOLDER / HISTORY, machine, fresh)
        if found:
            historymerge.merge(found, out)
