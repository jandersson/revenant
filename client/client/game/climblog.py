"""Climb attempts logged with their context, so an obstacle's threshold
can be read off the data (#159).

One row per attempt in history.db's `climbs` table: the obstacle and
room, the outcome (up, footing, vertigo, posture, other) with the
game's wording and the hindering-items line, Athletics rank and
mindstate, the stats INFO gave, encumbrance, health, and APPRAISE's
answer — the factors Elanthipedia's Athletics page names. ;climbexp
writes the rows and ;climbexp show reads them back; the walker's
climb retry (#157) shares the wordings through refusal_kind. Rows are
data for a human decision (what to train), never a trigger.
"""

import json
import sqlite3
from datetime import datetime, timezone

from client.game.walker import CLIMB_REFUSALS, POSTURE_REFUSALS, hindering_nouns

SCHEMA = """
CREATE TABLE IF NOT EXISTS climbs (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    experiment TEXT NOT NULL,
    phase TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    room INTEGER,
    obstacle TEXT NOT NULL,
    outcome TEXT NOT NULL,
    wording TEXT NOT NULL,
    hindering TEXT NOT NULL,
    athletics_rank INTEGER,
    athletics_mindstate INTEGER,
    agility INTEGER,
    strength INTEGER,
    tdps INTEGER,
    encumbrance TEXT,
    health INTEGER,
    appraise TEXT,
    extra TEXT NOT NULL
)
"""

COLUMNS = (
    "logged_at",
    "character_name",
    "experiment",
    "phase",
    "attempt",
    "room",
    "obstacle",
    "outcome",
    "wording",
    "hindering",
    "athletics_rank",
    "athletics_mindstate",
    "agility",
    "strength",
    "tdps",
    "encumbrance",
    "health",
    "appraise",
    "extra",
)


def ensure_schema(connection):
    connection.execute(SCHEMA)
    connection.commit()


def refusal_kind(text):
    """What a climb's story text says happened when no room change
    followed: footing, vertigo, posture (the walker's captured
    wordings, #157), other when a "climb back down" line has a new
    shape, None when nothing there reads as a refusal."""
    lowered = text.lower()
    if "footing is questionable" in lowered:
        return "footing"
    if "vertigo" in lowered:
        return "vertigo"
    if any(needle.lower() in lowered for needle in POSTURE_REFUSALS):
        return "posture"
    if any(needle in lowered for needle in CLIMB_REFUSALS):
        return "other"
    return None


def hindering_line(text):
    """The "... make the climb more difficult." line itself, or ""."""
    for line in text.splitlines():
        if hindering_nouns(line):
            return line.strip()
    return ""


def record(connection, **fields):
    """One row; unknown keys go into `extra` as JSON. Returns the seq."""
    row = {column: None for column in COLUMNS}
    extra = {}
    for key, value in fields.items():
        if key in row:
            row[key] = value
        else:
            extra[key] = value
    row["logged_at"] = row["logged_at"] or datetime.now(timezone.utc).isoformat()
    row["extra"] = json.dumps(extra, sort_keys=True)
    for text_column in ("wording", "hindering"):
        row[text_column] = row[text_column] or ""
    cursor = connection.execute(
        f"INSERT INTO climbs ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
        [row[column] for column in COLUMNS],
    )
    connection.commit()
    return cursor.lastrowid


def rows(connection, experiment=None, character=None):
    """The rows, oldest first, as dicts; filtered when asked."""
    clauses, values = [], []
    if experiment:
        clauses.append("experiment = ?")
        values.append(experiment)
    if character:
        clauses.append("character_name = ?")
        values.append(character)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    cursor = connection.execute(
        f"SELECT {', '.join(COLUMNS)} FROM climbs{where} ORDER BY seq", values
    )
    return [dict(zip(COLUMNS, row)) for row in cursor.fetchall()]


def summarize(entries):
    """One line per row for ;climbexp show."""
    lines = []
    for entry in entries:
        stamp = (entry["logged_at"] or "")[11:19]
        load = f" [{entry['hindering']}]" if entry["hindering"] else ""
        lines.append(
            f"{stamp} {entry['phase']}#{entry['attempt']} {entry['outcome']}: "
            f"Ath {entry['athletics_rank']} Agi {entry['agility']} "
            f"Str {entry['strength']} enc {entry['encumbrance']} "
            f"hp {entry['health']}{load}"
        )
    return lines


def open_history(path):
    connection = sqlite3.connect(path)
    ensure_schema(connection)
    return connection
