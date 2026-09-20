"""What gates your next circle:  ;circle

    ;circle          the gates: INFO's circle and guild now, the exp window's ranks over the latest ;sheet snapshot
    ;circle fresh    run ;sheet first (EXP and INFO, no roundtime), then the gates

Computes the guildleader's answer locally: the latest ;sheet snapshot
(~/.revenant/history.db) against your guild's circle-requirement table
(client/game/circles.py, from Elanthipedia; all eleven circled guilds),
printed per knowledge set with have/need ranks. The circle and the
guild come from INFO, asked first — read-only, no roundtime — so the
conclusion is the character's now, not the sheet's (a snapshot
several circles old gated circle 6 for a character past it, the
operator, 2026-09-20); the snapshot's circle stands in when INFO
answers nothing. The exp window's ranks are laid over the snapshot,
so a skill that ranked since the sheet was taken counts at its
current rank (Performance 2 → 3 in an hour of playing, 2026-09-18); a
skill the window does not list is the snapshot's. `fresh` runs
;sheet and waits for it. The snapshot's age is echoed. The model and
its captured guildleader validation live in docs/circles.md.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from client.game import circles, probe
from client.game.history import database_path as history_database_path
from client.game.tdp import parse_info

INFO_SECONDS = 3  # INFO's block, collected
INFO_TAIL = 1


def database_path() -> Path:
    """~/.revenant/history.db (once history.db; client/game/history.py migrates)."""
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


SHEET_WAIT = 60  # seconds for a fresh snapshot under `fresh`


def refresh(s, name):
    """A fresh ;sheet snapshot: the autostart runs in every session, so
    it is asked for one (`;sheet once` handed to it, #122); from cold
    ;sheet once is started. Waits until the snapshot's stamp moves;
    False, said so, when nothing came in SHEET_WAIT seconds."""
    before = snapshot_stamp(name)
    if s.is_running("sheet"):
        s.tell("sheet", "once")
    elif not s.run("sheet", ["once"]):
        s.echo("circle: ;sheet did not start — reading the last snapshot")
        return False
    for _ in range(SHEET_WAIT):
        if snapshot_stamp(name) != before:
            return True
        s.sleep(1)
    s.echo(f"circle: no fresh sheet in {SHEET_WAIT}s — reading the last snapshot")
    return False


def snapshot_stamp(name):
    """The latest snapshot's logged_at for the character, or None."""
    connection = sqlite3.connect(database_path())
    try:
        row = latest_snapshot(connection, name)
    finally:
        connection.close()
    return row[1] if row else None


def live_circle(s):
    """INFO's (circle, guild) now — read-only, no roundtime — or (None,
    None) when INFO answered nothing parseable."""
    info = parse_info(probe.ask(s, "info", INFO_SECONDS, INFO_TAIL))
    return info.get("circle"), info.get("guild")


def main(s):
    name = (s.state.name if s.state else None) or os.environ.get("REVENANT_CHARACTER")
    if str((getattr(s, "args", None) or [""])[0]).lower() == "fresh":
        refresh(s, name)
    connection = sqlite3.connect(database_path())
    try:
        snapshot = latest_snapshot(connection, name)
    finally:
        connection.close()
    if snapshot is None:
        s.echo("circle: no sheet snapshot yet — run ;sheet once first")
        return
    character, logged_at, circle, guild, ranks = snapshot
    now_circle, now_guild = live_circle(s)
    if now_circle is not None:
        circle, guild = now_circle, now_guild or guild
    if circle is None or guild is None:
        s.echo(
            "circle: INFO gave no circle and the snapshot predates circle/guild "
            "tracking — run ;sheet once"
        )
        return
    live = getattr(s.state, "experience", None) if s.state else None
    ranks = circles.overlay_live(ranks, live)
    unmet = circles.gates(ranks, circle, guild)
    if unmet is None:
        s.echo(f"circle: {circles.explain_no_gates(guild)}")
        return
    for line in circles.describe(unmet, circle + 1):
        s.echo(f"circle: {line}")
    s.echo(
        f"circle: circle {circle} {guild} "
        + ("from INFO now" if now_circle is not None else "from the sheet")
        + f", ranks from {character}'s sheet snapshot of {snapshot_age(logged_at)}"
        " ago"
        + (" with the exp window's ranks over it" if live else "")
        + " (;circle fresh runs ;sheet first)"
    )
