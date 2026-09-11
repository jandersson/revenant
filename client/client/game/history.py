"""Where the character history lives: ~/.revenant/history.db.

One SQLite file holds everything the scripts log about a character —
experience (`;xp`), sheet snapshots, wealth sightings, inventory — and
beholder renders it. It began life as xp.db when only `;xp` wrote to
it; the name outgrew the contents (#121). This module is the one place
the path is decided, for every writer and reader.

`REVENANT_HISTORY_DB` overrides the location; `REVENANT_XP_DB` still
works as the older spelling. With no override, the first call after
the rename moves an existing xp.db to history.db (its journal with it)
so no history is lost; a history.db already in place is left alone.
"""

import os
from pathlib import Path

DEFAULT_PATH = "~/.revenant/history.db"
LEGACY_PATH = "~/.revenant/xp.db"
ENV = "REVENANT_HISTORY_DB"
LEGACY_ENV = "REVENANT_XP_DB"


def database_path() -> Path:
    """The history database's path, migrating a legacy xp.db in place
    on first use when nothing overrides the location."""
    override = os.environ.get(ENV) or os.environ.get(LEGACY_ENV)
    if override:
        return Path(override).expanduser()
    new, old = Path(DEFAULT_PATH).expanduser(), Path(LEGACY_PATH).expanduser()
    if not new.exists() and old.exists():
        migrate(old, new)
    return new


def migrate(old: Path, new: Path):
    """Move `old` to `new`, sidecar files included (a -journal or -wal
    left by an unclean close belongs with its database)."""
    new.parent.mkdir(parents=True, exist_ok=True)
    os.replace(old, new)
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = old.with_name(old.name + suffix)
        if sidecar.exists():
            os.replace(sidecar, new.with_name(new.name + suffix))
