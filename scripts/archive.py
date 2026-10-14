"""Copy this machine's logs and history to the shared folder:  ;archive

    ;archive          (autostarts once `archive_dir` is set) copy now, then every 30 minutes
    ;archive now      copy once and end; typed at the running ;archive, copy now
    ;stop archive     stop

What it copies, to <archive_dir>/revenant/<machine>/
  - logs/: every log in ~/.revenant/logs that is new or has grown since the last copy
  - history.db: a snapshot of ~/.revenant/history.db, taken safely while scripts write to it
  - Nothing there is ever deleted; this machine's own files stay where they are.

Setup, in ~/.revenant/settings.json
  - `archive_dir`: the shared folder, a Dropbox folder say (it must exist)
  - `archive_machine`: this machine's folder name there (default: the host name)
  - REVENANT_NO_ARCHIVE=1 skips the autostart for one launch

tools/history_merge.py merges every machine's history for beholder; docs/running.md.
The model is client/game/archive.py's.
"""

import time

from client.client_logger import log_dir
from client.game import archive
from client.game.history import database_path
from client.settings import load_settings

clock = time.monotonic  # tests replace it
POLL = 5  # seconds between looks for a typed word


def copy_once(s, root, machine, say):
    """One copy; True when it ran. With `say`, what was copied is echoed
    — the autostart's half-hourly copies stay quiet unless one fails."""
    if not root.is_dir():
        s.echo(f"archive: no folder at {root} — is the shared folder there?")
        return False
    try:
        copied, snapshot = archive.copy(root, machine, log_dir(), database_path())
    except OSError as error:
        s.echo(f"archive: the copy to {root} failed — {error}")
        return False
    if say:
        s.echo(
            f"archive: {len(copied)} log(s) copied, history {snapshot} — "
            f"{archive.machine_dir(root, machine)}"
        )
    return True


def main(s):
    settings = load_settings()
    root = archive.shared_dir(settings)
    if root is None:
        s.echo(
            "archive: no shared folder — set archive_dir in ~/.revenant/settings.json "
            "(a Dropbox folder, say)"
        )
        return
    machine = archive.machine_name(settings)
    if "now" in [str(arg).lower() for arg in s.args or []]:
        copy_once(s, root, machine, say=True)
        return
    s.echo(
        f"archive: logs and history to {archive.machine_dir(root, machine)} every "
        f"{archive.INTERVAL_MINUTES} minutes; ;archive now copies at once, ;stop archive stops"
    )
    next_copy, say = clock(), False
    while True:
        if clock() >= next_copy:
            copy_once(s, root, machine, say)
            next_copy, say = clock() + archive.INTERVAL_MINUTES * 60, False
        request = s.command(timeout=POLL)
        if request is not None and "now" in request.lower():
            next_copy, say = clock(), True
