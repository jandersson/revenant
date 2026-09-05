"""What gates your next circle:  ;circle

Computes the guildleader's answer locally: the latest ;sheet snapshot
(~/.revenant/history.db) against your guild's circle-requirement table
(client/circles.py, from Elanthipedia; all eleven circled guilds),
printed per knowledge set with have/need ranks. Nothing is sent to the game — run
;sheet once first if the snapshot might be stale; the snapshot's age
is echoed. The model and its captured guildleader validation live in
docs/circles.md.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from client import circles
from client.history import database_path as history_database_path


def database_path() -> Path:
    """~/.revenant/history.db (once history.db; client/history.py migrates)."""
    return history_database_path()


def latest_snapshot(connection, character=None):
    """The newest sheet snapshot: (character, logged_at, circle,
    {skill: (rank, percent)}), or None without one."""
    where, args = "", ()
    if character:
        where, args = " WHERE character_name = ?", (character,)
    try:
        row = connection.execute(
            "SELECT character_name, max(logged_at) FROM sheet_skills" + where, args
        ).fetchone()
    except sqlite3.OperationalError:
        return None  # no table yet: ;sheet has never run against this db
    if not row or row[1] is None:
        return None
    character, logged_at = row
    ranks = {
        skill: (rank, percent)
        for skill, rank, percent in connection.execute(
            "SELECT skill_name, rank, percent FROM sheet_skills"
            " WHERE character_name = ? AND logged_at = ?",
            (character, logged_at),
        )
    }
    circle, guild = None, None
    try:
        row = connection.execute(
            "SELECT circle, guild FROM character WHERE character_name = ?"
            " AND circle IS NOT NULL ORDER BY logged_at DESC LIMIT 1",
            (character,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None  # a db from before guild tracking
    if row:
        circle, guild = row
    return character, logged_at, circle, guild, ranks


def snapshot_age(logged_at):
    then = datetime.fromisoformat(logged_at)
    minutes = (datetime.now(timezone.utc) - then).total_seconds() / 60
    return f"{minutes / 60:.1f}h" if minutes >= 90 else f"{minutes:.0f}m"


def main(s):
    name = (s.state.name if s.state else None) or os.environ.get("REVENANT_CHARACTER")
    connection = sqlite3.connect(database_path())
    try:
        snapshot = latest_snapshot(connection, name)
    finally:
        connection.close()
    if snapshot is None:
        s.echo("circle: no sheet snapshot yet — run ;sheet once first")
        return
    character, logged_at, circle, guild, ranks = snapshot
    if circle is None or guild is None:
        s.echo("circle: the snapshot predates circle/guild tracking — run ;sheet once")
        return
    unmet = circles.gates(ranks, circle, guild)
    if unmet is None:
        s.echo(f"circle: {circles.explain_no_gates(guild)}")
        return
    for line in circles.describe(unmet, circle + 1):
        s.echo(f"circle: {line}")
    s.echo(
        f"circle: from {character}'s sheet snapshot of {snapshot_age(logged_at)}"
        " ago (;sheet once refreshes)"
    )
