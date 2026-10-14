"""Dropbox sync: this machine's logs and history copied to Dropbox:  ;dropbox

    ;dropbox          (autostarts with Dropbox sync on) copy now, then every 10 minutes
    ;dropbox now      copy once and end; typed at the running ;dropbox, copy now
    ;stop dropbox     stop

Turn it on in File → Settings: "Sync logs and history through Dropbox".

What it does
  - Copies every log that is new or has grown to <Dropbox>/Revenant/<Character>/,
    this machine's name in each file's (game-Lanival-<stamp>.<machine>.log).
  - A log whose name carries no character (before late September 2026) is filed by
    best effort: its login line, the game log of its stamp, or the session before it;
    _other/ when nothing says.
  - Copies a snapshot of the history to <Dropbox>/Revenant/_history/history.<machine>.db.
  - Nothing there is ever deleted.
  - Beholder then shows every machine's history, not this one's alone.
  - The Dropbox folder is found on its own; `dropbox_dir` in settings.json names
    another synced folder, `dropbox_machine` this machine's name there.
  - REVENANT_NO_DROPBOX=1 skips the autostart for one launch.

The model is client/game/dropbox.py's; docs/running.md.
"""

import time

from client.client_logger import log_dir
from client.game import dropbox
from client.game.history import database_path
from client.settings import load_settings

clock = time.monotonic  # tests replace it
POLL = 5  # seconds between looks for a typed word


def copy_once(s, root, machine, say):
    """One copy; True when it ran. With `say`, what was copied is echoed
    — the autostart's copies stay quiet unless one fails."""
    if not root.is_dir():
        s.echo(f"dropbox: no folder at {root} — is Dropbox running here?")
        return False
    try:
        copied, snapshot = dropbox.copy(root, machine, log_dir(), database_path())
    except OSError as error:
        s.echo(f"dropbox: the copy to {root} failed — {error}")
        return False
    if say:
        where = root / dropbox.FOLDER
        s.echo(f"dropbox: {len(copied)} log(s) copied, history {snapshot} — {where}")
    return True


def main(s):
    settings = load_settings()
    root = dropbox.shared_dir(settings)
    if root is None:
        s.echo(
            "dropbox: no Dropbox folder on this computer — install Dropbox, or set "
            "dropbox_dir in ~/.revenant/settings.json to a synced folder"
        )
        return
    machine = dropbox.machine_name(settings)
    if "now" in [str(arg).lower() for arg in s.args or []]:
        copy_once(s, root, machine, say=True)
        return
    s.echo(
        f"dropbox: logs and history to {root / dropbox.FOLDER} as {machine} every "
        f"{dropbox.INTERVAL_MINUTES} minutes; ;dropbox now copies at once, "
        ";stop dropbox stops"
    )
    next_copy, say = clock(), False
    while True:
        if clock() >= next_copy:
            copy_once(s, root, machine, say)
            next_copy, say = clock() + dropbox.INTERVAL_MINUTES * 60, False
        request = s.command(timeout=POLL)
        if request is not None and "now" in request.lower():
            next_copy, say = clock(), True
