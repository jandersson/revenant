"""What gates your next circle:  ;circle

Computes the guildleader's answer locally: the latest ;sheet snapshot
(~/.revenant/xp.db) against the guild's circle-requirement table
(client/circles.py, from Elanthipedia; Thief for now), printed per
knowledge set with have/need ranks. Nothing is sent to the game — run
;sheet once first if the snapshot might be stale; the snapshot's age
is echoed. The model and its captured guildleader validation live in
docs/circles.md.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from client import circles


def database_path() -> Path:
    return Path(os.environ.get("REVENANT_XP_DB", "~/.revenant/xp.db")).expanduser()


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
    circle = connection.execute(
        "SELECT circle FROM character WHERE character_name = ?"
        " AND circle IS NOT NULL ORDER BY logged_at DESC LIMIT 1",
        (character,),
    ).fetchone()
    return character, logged_at, circle[0] if circle else None, ranks


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
    character, logged_at, circle, ranks = snapshot
    if circle is None:
        s.echo("circle: the snapshot has no circle recorded — run ;sheet once")
        return
    unmet = circles.gates(ranks, circle)
    for line in circles.describe(unmet, circle + 1):
        s.echo(f"circle: {line}")
    s.echo(
        f"circle: from {character}'s sheet snapshot of {snapshot_age(logged_at)}"
        " ago (;sheet once refreshes)"
    )
