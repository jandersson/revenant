"""Every machine's logs and history in one shared folder (#547): what
`;archive` copies, and where.

The shared folder is the `archive_dir` setting — a Dropbox folder, say —
and REVENANT_ARCHIVE_DIR overrides it. Each machine writes only under its
own <archive_dir>/revenant/<machine>/:

    logs/        every log in the local log directory, copied when it is
                 new there or has grown since the last copy
    history.db   a snapshot of ~/.revenant/history.db

The game logs are append-only and named by character and start time, so
two machines never write the same file and copying them together loses
nothing. history.db is different: every table keys on its own
autoincrement seq, so two machines' files cannot be synced as one — each
copies a snapshot and tools/history_merge.py (client/game/historymerge.py)
merges them. The snapshot is taken with SQLite's backup API, safe while
scripts write, into a temporary file moved into place, so a sync never
picks up half a database; nothing at the destination is ever deleted.
Each machine keeps writing its own local files, so a sync problem never
touches a running session.
"""

import os
import re
import shutil
import socket
import sqlite3
from pathlib import Path

ENV = "REVENANT_ARCHIVE_DIR"
INTERVAL_MINUTES = 30  # between the autostarted ;archive's copies

# snapshot_history's answers.
TAKEN = "taken"
UNCHANGED = "unchanged"
NO_HISTORY = "no history"


def shared_dir(settings):
    """The shared folder (REVENANT_ARCHIVE_DIR, else the `archive_dir` setting)
    as a Path, or None when neither names one."""
    value = os.environ.get(ENV) or str(settings.get("archive_dir") or "")
    return Path(value).expanduser() if value.strip() else None


def machine_name(settings, host=None):
    """This machine's folder name: the `archive_machine` setting, else the
    host name, lowercased, a trailing .local/.lan/.home dropped, and any
    run of characters but letters, digits, _ and - made one "-"."""
    value = str(settings.get("archive_machine") or "").strip()
    value = (value or host or socket.gethostname()).lower()
    value = re.sub(r"\.(local|lan|home)$", "", value)
    value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-")
    return value or "machine"


def machine_dir(root, machine):
    """<root>/revenant/<machine>: the one folder this machine writes."""
    return Path(root) / "revenant" / machine


def copy_logs(source, dest):
    """Every file in `source` (no subfolders, no dot-files) copied into
    `dest` when it is missing there, a different size, or newer: the
    names copied. A copy goes to a dot-file beside it first and is moved
    into place. Nothing in `dest` is ever deleted — a debug log pruned
    locally after 7 days stays in the archive."""
    source, dest = Path(source), Path(dest)
    copied = []
    if not source.is_dir():
        return copied
    dest.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        if path.name.startswith(".") or not path.is_file():
            continue
        target = dest / path.name
        here = path.stat()
        if target.exists():
            there = target.stat()
            if there.st_size == here.st_size and there.st_mtime >= here.st_mtime:
                continue
        part = dest / f".{path.name}.part"
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
    """One copy into <root>/revenant/<machine>/: (the log names copied,
    the snapshot's answer)."""
    base = machine_dir(root, machine)
    copied = copy_logs(logs, base / "logs")
    return copied, snapshot_history(history, base / "history.db")
