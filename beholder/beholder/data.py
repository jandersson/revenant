"""Queries over the experience history the ;xp script logs to xp.db.

The database is written by scripts/xp.py: one `mindstate` row per
learning skill per minute (logged_at is ISO-8601 UTC, so text ordering
is time ordering). Everything here is stdlib sqlite3 — connections are
cheap, and Dash callbacks run on worker threads, so callers open a
fresh connection per request instead of sharing one.
"""

import os
import sqlite3
from pathlib import Path


def database_path() -> Path:
    """The xp.db location, shared with scripts/xp.py."""
    return Path(os.environ.get("REVENANT_XP_DB", "~/.revenant/xp.db")).expanduser()


def connect(path=None):
    """Read-only: the dashboard must never create an empty xp.db as a
    side effect of being opened before ;xp has ever run — a missing
    file raises OperationalError, which callers already treat as the
    no-history-yet state."""
    connection = sqlite3.connect(f"file:{path or database_path()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def characters(connection):
    """Every character with logged history, sorted by name."""
    rows = connection.execute(
        "SELECT DISTINCT character_name FROM mindstate ORDER BY character_name"
    )
    return [row["character_name"] for row in rows]


def skills(connection, character):
    """Every skill a character has history for, sorted by name."""
    rows = connection.execute(
        "SELECT DISTINCT skill_name FROM mindstate"
        " WHERE character_name = ? ORDER BY skill_name",
        (character,),
    )
    return [row["skill_name"] for row in rows]


def latest_snapshot(connection, character):
    """The newest logged row per skill for a character — the learning
    queue as of the last ;xp tick, one dict per skill, sorted by name."""
    rows = connection.execute(
        "SELECT skill_name, rank, percent, mindstate, logged_at"
        "  FROM mindstate"
        " WHERE character_name = ?"
        "   AND logged_at = (SELECT max(logged_at) FROM mindstate"
        "                     WHERE character_name = ?)"
        " ORDER BY skill_name",
        (character, character),
    )
    return [dict(row) for row in rows]


def history(connection, character, skill_names):
    """Time series per skill: {skill: {"times": [...], "mindstate": [...],
    "rank": [...]}}, oldest first. Skills without history are absent."""
    if not skill_names:
        return {}
    placeholders = ", ".join("?" for _ in skill_names)
    rows = connection.execute(
        "SELECT skill_name, logged_at, mindstate, rank"
        "  FROM mindstate"
        " WHERE character_name = ?"
        f"   AND skill_name IN ({placeholders})"
        " ORDER BY logged_at",
        (character, *skill_names),
    )
    series = {}
    for row in rows:
        points = series.setdefault(
            row["skill_name"], {"times": [], "mindstate": [], "rank": []}
        )
        points["times"].append(row["logged_at"])
        points["mindstate"].append(row["mindstate"])
        points["rank"].append(row["rank"])
    return series
