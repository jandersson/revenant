"""Log skill experience to SQLite for history and analysis:  ;xp

Every minute, snapshots the exp window (skills currently in the learning
queue, with rank / percent / mindstate) into ~/.revenant/xp.db
(override with REVENANT_XP_DB). The Experience dock shows the live
view; this file is the history — plots and analysis read it later
(beholder's successor, issue #33). Stop with:  ;stop xp
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

INTERVAL = 60  # seconds between snapshots

SCHEMA = """
CREATE TABLE IF NOT EXISTS mindstate (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    percent INTEGER NOT NULL,
    mindstate INTEGER NOT NULL
)
"""


def database_path() -> Path:
    return Path(os.environ.get("REVENANT_XP_DB", "~/.revenant/xp.db")).expanduser()


def ensure_schema(connection):
    connection.execute(SCHEMA)
    connection.commit()


def snapshot_rows(experience, character, logged_at):
    """One insertable row per learning skill in the exp window."""
    return [
        (
            logged_at,
            character,
            skill,
            entry["rank"],
            entry["percent"],
            entry["mindstate"],
        )
        for skill, entry in sorted(experience.items())
    ]


def insert(connection, rows):
    connection.executemany(
        "INSERT INTO mindstate "
        "(logged_at, character_name, skill_name, rank, percent, mindstate) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()


def main(s):
    character = (
        (s.state.name if s.state else None)
        or os.environ.get("REVENANT_CHARACTER")
        or "unknown"
    )
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    ensure_schema(connection)
    s.echo(f"logging experience for {character} to {path} every {INTERVAL}s")
    try:
        while True:
            experience = dict(getattr(s.state, "experience", None) or {})
            if experience:
                logged_at = datetime.now(timezone.utc).isoformat()
                insert(connection, snapshot_rows(experience, character, logged_at))
            s.sleep(INTERVAL)
    finally:
        connection.close()
