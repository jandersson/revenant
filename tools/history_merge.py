"""Merge every machine's history into one database for beholder (#547).

    uv run python tools/history_merge.py              every machine in archive_dir -> ~/.revenant/merged.db
    uv run python tools/history_merge.py --dir PATH   the shared folder (default: the archive_dir setting)
    uv run python tools/history_merge.py --out PATH   where the merged database goes

Then read it with a second beholder, beside the session's own on 8050:

    REVENANT_HISTORY_DB=~/.revenant/merged.db uv run beholder --port 8051

Each machine's ;archive puts a snapshot of its history.db under
<archive_dir>/revenant/<machine>/; this machine's own history is read
fresh (a snapshot taken now) instead of the one it copied there. The merged
database is rebuilt from scratch each run — run it again after new
snapshots arrive — and is for reading only: no session should write to
it. A beholder still open on it keeps Windows from replacing the file;
stop that beholder first. The rules are client/game/historymerge.py's.
"""

import argparse
import sys
import tempfile
from pathlib import Path

from client.game import archive, historymerge
from client.game.history import database_path
from client.settings import load_settings

DEFAULT_OUT = "~/.revenant/merged.db"


def run(root, machine, local_history, out):
    """The merge, said: the lines printed, for the caller to show."""
    with tempfile.TemporaryDirectory() as scratch:
        fresh = Path(scratch) / "history.db"
        if archive.snapshot_history(local_history, fresh) == archive.NO_HISTORY:
            fresh = None
        found = historymerge.sources(root, machine, fresh)
        if not found:
            return [f"no history to merge: none here, and no snapshot under {root}"]
        taken, skipped = historymerge.merge(found, out)
    lines = [f"{name}: {rows} rows" for name, rows in taken.items()]
    if skipped:
        lines.append(f"{skipped} rows another machine already gave, kept once")
    lines.append(f"merged {len(taken)} machine(s) into {out}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", help="the shared folder (default: archive_dir)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="the merged database")
    options = parser.parse_args(argv)
    settings = load_settings()
    root = (
        Path(options.dir).expanduser() if options.dir else archive.shared_dir(settings)
    )
    if root is None:
        print("no archive_dir set: merging this machine's history alone")
    elif not root.is_dir():
        print(f"no folder at {root}")
        return 1
    machine = archive.machine_name(settings)
    out = Path(options.out).expanduser()
    for line in run(root, machine, database_path(), out):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
