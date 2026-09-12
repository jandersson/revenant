"""Log skill experience to SQLite for history and analysis:  ;xp

Every minute, snapshots the exp window (skills currently in the learning
queue, with rank / percent / mindstate) into ~/.revenant/history.db
(override with REVENANT_HISTORY_DB), each row flagged `is_rexp` when
rested experience was burning that minute — the EXP footer's usable
figure fell since the last look; NULL the first minute or before the
game has shown the footer — and logs the footer itself to the `rested`
table whenever it changes (stored, usable, refresh in minutes), so
beholder shades the 3x windows exactly and charts the bank's slope
(#176). The Experience dock shows the live view; this file is the
history the ;beholder dashboard plots. Every session starts this
script automatically — ;stop xp opts a session out, REVENANT_NO_XP=1
disables the autostart. Stop with:  ;stop xp
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from client.game.history import database_path as history_database_path
from client.game.rested import burning

INTERVAL = 60  # seconds between snapshots

SCHEMA = """
CREATE TABLE IF NOT EXISTS mindstate (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    percent INTEGER NOT NULL,
    mindstate INTEGER NOT NULL,
    is_rexp INTEGER
);
CREATE TABLE IF NOT EXISTS rested (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    stored INTEGER,
    usable INTEGER,
    refresh INTEGER
);
"""


def database_path() -> Path:
    """~/.revenant/history.db (once history.db; client/game/history.py migrates)."""
    return history_database_path()


def ensure_schema(connection):
    """Both tables, and the is_rexp column on a mindstate table from
    before #176 (NULL on its old rows: unknown, not "no")."""
    connection.executescript(SCHEMA)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(mindstate)")}
    if "is_rexp" not in columns:
        connection.execute("ALTER TABLE mindstate ADD COLUMN is_rexp INTEGER")
    connection.commit()


def snapshot_rows(experience, character, logged_at, is_rexp=None):
    """One insertable row per learning skill in the exp window, each
    carrying whether rested experience burnt this minute (1/0, or
    None for unknown)."""
    flag = None if is_rexp is None else int(bool(is_rexp))
    return [
        (
            logged_at,
            character,
            skill,
            entry["rank"],
            entry["percent"],
            entry["mindstate"],
            flag,
        )
        for skill, entry in sorted(experience.items())
    ]


def insert(connection, rows):
    connection.executemany(
        "INSERT INTO mindstate "
        "(logged_at, character_name, skill_name, rank, percent, mindstate, is_rexp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()


def insert_rested(connection, character, logged_at, reading):
    connection.execute(
        "INSERT INTO rested (logged_at, character_name, stored, usable, refresh)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            logged_at,
            character,
            reading.get("stored"),
            reading.get("usable"),
            reading.get("refresh"),
        ),
    )
    connection.commit()


def snapshot(connection, character, logged_at, experience, reading, seen, logged):
    """One minute's logging: the mindstate rows flagged by the bank's
    movement since `seen` (the previous minute's footer), and a rested
    row when the footer differs from `logged` (the last one written).
    Returns the (seen, logged) pair for the next minute."""
    if experience:
        rows = snapshot_rows(experience, character, logged_at, burning(seen, reading))
        insert(connection, rows)
    if reading and reading != logged:
        insert_rested(connection, character, logged_at, reading)
        logged = reading
    return reading, logged


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
    seen = logged = None
    try:
        while True:
            experience = dict(getattr(s.state, "experience", None) or {})
            reading = getattr(s.state, "rested", None)
            reading = dict(reading) if reading else None
            logged_at = datetime.now(timezone.utc).isoformat()
            seen, logged = snapshot(
                connection, character, logged_at, experience, reading, seen, logged
            )
            s.sleep(INTERVAL)
    finally:
        connection.close()
