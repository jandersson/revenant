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


def sheet_snapshot(connection, character):
    """The newest ;sheet roster for a character: (logged_at, circle,
    guild, {skill: (rank, percent)}), or None before any snapshot."""
    row = connection.execute(
        "SELECT max(logged_at) FROM sheet_skills WHERE character_name = ?",
        (character,),
    ).fetchone()
    if not row or row[0] is None:
        return None
    logged_at = row[0]
    ranks = {
        r["skill_name"]: (r["rank"], r["percent"])
        for r in connection.execute(
            "SELECT skill_name, rank, percent FROM sheet_skills"
            " WHERE character_name = ? AND logged_at = ?",
            (character, logged_at),
        )
    }
    circle, guild = None, None
    try:
        latest = connection.execute(
            "SELECT circle, guild FROM character WHERE character_name = ?"
            " AND circle IS NOT NULL ORDER BY logged_at DESC LIMIT 1",
            (character,),
        ).fetchone()
    except sqlite3.OperationalError:
        latest = None  # a db from before guild tracking
    if latest:
        circle, guild = latest["circle"], latest["guild"]
    return logged_at, circle, guild, ranks


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


def latest_character(connection):
    """The most recently logged character, or None on an empty table —
    the dock view's fallback when no character is named."""
    row = connection.execute(
        "SELECT character_name FROM mindstate ORDER BY logged_at DESC LIMIT 1"
    ).fetchone()
    return row["character_name"] if row else None


def history_since(connection, character, since_iso):
    """Time series per skill from a cutoff onward — the dock's recent
    window. Same shape as history(); ISO-8601 UTC strings compare as
    time, so the cutoff is a plain string comparison."""
    rows = connection.execute(
        "SELECT skill_name, logged_at, mindstate, rank"
        "  FROM mindstate"
        " WHERE character_name = ? AND logged_at >= ?"
        " ORDER BY logged_at",
        (character, since_iso),
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


def _sheet_roster(connection, character, logged_at):
    return {
        row["skill_name"]: (row["rank"], row["percent"])
        for row in connection.execute(
            "SELECT skill_name, rank, percent FROM sheet_skills"
            " WHERE character_name = ? AND logged_at = ?",
            (character, logged_at),
        )
    }


def sheet_with_deltas(connection, character):
    """The newest full roster with rank gained since the previous
    snapshot: (logged_at, [{skill_name, rank, percent, gained}]),
    sorted by skill. gained is None for a skill's first appearance —
    including everything in the very first snapshot. None before any
    snapshot at all."""
    times = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT logged_at FROM sheet_skills"
            " WHERE character_name = ? ORDER BY logged_at DESC LIMIT 2",
            (character,),
        )
    ]
    if not times:
        return None
    latest = _sheet_roster(connection, character, times[0])
    previous = _sheet_roster(connection, character, times[1]) if len(times) > 1 else {}
    rows = [
        {
            "skill_name": skill,
            "rank": rank,
            "percent": percent,
            "gained": (rank - previous[skill][0]) if skill in previous else None,
        }
        for skill, (rank, percent) in sorted(latest.items())
    ]
    return times[0], rows


def stats_with_deltas(connection, character):
    """The newest stats with change since the previous snapshot:
    (logged_at, [{stat, value, gained}]), or None before any."""
    times = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT logged_at FROM stats"
            " WHERE character_name = ? ORDER BY logged_at DESC LIMIT 2",
            (character,),
        )
    ]
    if not times:
        return None

    def values(logged_at):
        return {
            row["stat"]: row["value"]
            for row in connection.execute(
                "SELECT stat, value FROM stats"
                " WHERE character_name = ? AND logged_at = ?",
                (character, logged_at),
            )
        }

    latest = values(times[0])
    previous = values(times[1]) if len(times) > 1 else {}
    rows = [
        {
            "stat": stat,
            "value": value,
            "gained": (value - previous[stat]) if stat in previous else None,
        }
        for stat, value in sorted(latest.items())
    ]
    return times[0], rows


def sheet_history(connection, character):
    """Circle, TDPs and favors over time, from every ;sheet snapshot:
    {"times": [...], "circle": [...], "tdps": [...], "favors": [...]}."""
    history = {"times": [], "circle": [], "tdps": [], "favors": []}
    for row in connection.execute(
        "SELECT logged_at, circle, tdps, favors FROM character"
        " WHERE character_name = ? ORDER BY logged_at",
        (character,),
    ):
        history["times"].append(row["logged_at"])
        history["circle"].append(row["circle"])
        history["tdps"].append(row["tdps"])
        history["favors"].append(row["favors"])
    return history


def stats_history(connection, character):
    """Per-stat progression: {stat: {"times": [...], "values": [...]}}."""
    series = {}
    for row in connection.execute(
        "SELECT logged_at, stat, value FROM stats"
        " WHERE character_name = ? ORDER BY logged_at",
        (character,),
    ):
        points = series.setdefault(row["stat"], {"times": [], "values": []})
        points["times"].append(row["logged_at"])
        points["values"].append(row["value"])
    return series
