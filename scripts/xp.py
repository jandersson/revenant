"""Log skill experience to SQLite for history and analysis:  ;xp

Every minute, snapshots the exp window (skills currently in the learning
queue, with rank / percent / mindstate) into ~/.revenant/history.db
(override with REVENANT_HISTORY_DB), each row flagged `is_rexp` when
rested experience was burning that minute — the EXP footer's usable
figure fell within the last eleven minutes (client/game/rested.py's
Burn: the footer does not tick every minute, #346); NULL the first
minute or before the game has shown the footer — and logs the footer itself to the `rested`
table whenever it changes (stored, usable, refresh in minutes, and its
source: "window" for the exp window's pulse, "exp" for an EXP answer's
footer, logged on every reading), so beholder shades the 3x windows
exactly and charts the bank's slope (#176). An account whose exp
window leaves the footer empty has only the EXP answers' readings;
its rows are flagged from the last one's age (rested.Minute), NULL
where the bank may have run out since. The Experience dock shows the live view; this file is the
history the ;beholder dashboard plots. Every session starts this
script automatically — ;stop xp opts a session out, REVENANT_NO_XP=1
disables the autostart. Stop with:  ;stop xp
"""

import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from client.game.history import database_path as history_database_path
from client.game.rested import Minute

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
    refresh INTEGER,
    source TEXT
);
"""


def database_path() -> Path:
    """~/.revenant/history.db (once history.db; client/game/history.py migrates)."""
    return history_database_path()


def ensure_schema(connection):
    """Both tables, the is_rexp column on a mindstate table from before
    #176 (NULL on its old rows: unknown, not "no"), and the source column
    on a rested table from before the EXP answers' footers (NULL: the
    window's)."""
    connection.executescript(SCHEMA)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(mindstate)")}
    if "is_rexp" not in columns:
        connection.execute("ALTER TABLE mindstate ADD COLUMN is_rexp INTEGER")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(rested)")}
    if "source" not in columns:
        connection.execute("ALTER TABLE rested ADD COLUMN source TEXT")
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


def insert_rested(connection, character, logged_at, reading, source="window"):
    connection.execute(
        "INSERT INTO rested (logged_at, character_name, stored, usable, refresh,"
        " source) VALUES (?, ?, ?, ?, ?, ?)",
        (
            logged_at,
            character,
            reading.get("stored"),
            reading.get("usable"),
            reading.get("refresh"),
            source,
        ),
    )
    connection.commit()


def footer(state):
    """The parser's rested state: {"reading", "count", "window",
    "source"}. A parser from before the EXP answers' footers has
    neither count nor window, and every reading it holds is the
    window's."""
    reading = getattr(state, "rested", None) if state is not None else None
    return {
        "reading": dict(reading) if reading else None,
        "count": getattr(state, "rested_count", None),
        "window": getattr(state, "rested_window", True) is not False,
        "source": getattr(state, "rested_source", None) or "window",
    }


def draining(experience):
    """True when some pool holds experience: only then does the bank burn."""
    return any((entry or {}).get("mindstate") for entry in experience.values())


def snapshot(connection, character, logged_at, experience, now, found, minute, logged):
    """One minute's logging: the mindstate rows flagged by `minute` (a
    rested.Minute fed the parser's footer, `found`, once a minute; `now`
    a clock in minutes), and a rested row when the footer differs from
    the last one written, or for every new EXP answer's reading.
    `logged` is (reading, count) last written; returned for the next
    minute."""
    reading, count = found["reading"], found["count"]
    flag = minute.step(
        reading,
        now,
        window=found["window"],
        draining=draining(experience),
        count=count,
    )
    if experience:
        insert(connection, snapshot_rows(experience, character, logged_at, flag))
    last_reading, last_count = logged or (None, None)
    fresh = count is not None and count != last_count and found["source"] == "exp"
    if reading and (reading != last_reading or fresh):
        insert_rested(connection, character, logged_at, reading, found["source"])
        logged = (reading, count)
    return logged


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
    minute, logged = Minute(), None
    try:
        while True:
            experience = dict(getattr(s.state, "experience", None) or {})
            found = footer(s.state)
            logged_at = datetime.now(timezone.utc).isoformat()
            logged = snapshot(
                connection,
                character,
                logged_at,
                experience,
                time.monotonic() / 60,
                found,
                minute,
                logged,
            )
            s.sleep(INTERVAL)
    finally:
        connection.close()
