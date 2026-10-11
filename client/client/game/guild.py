"""The character's guild — the latest ;sheet snapshot's, else INFO's — and its circle.

Scripts that act by guild ask here: ;research picks the caster's mode
or the Barbarian's, ;hunt refuses an Empath (empathic shock, #444).
history.db's `character` table holds what ;sheet read at login and
every three hours; INFO answers when it holds nothing yet (read-only,
no roundtime).
"""

import sqlite3

from client.game.act import ask
from client.game.history import database_path
from client.game.tdp import parse_info


def snapshot_guild(name):
    """The guild of the latest ;sheet snapshot in history.db, or None."""
    return _snapshot(name, "guild")


def snapshot_circle(name):
    """The circle of the latest ;sheet snapshot in history.db, or None."""
    return _snapshot(name, "circle")


def _snapshot(name, column):
    try:
        connection = sqlite3.connect(database_path())
    except sqlite3.Error:
        return None
    try:
        row = connection.execute(
            f"SELECT {column} FROM character WHERE character_name = ?"
            f" AND {column} IS NOT NULL ORDER BY logged_at DESC LIMIT 1",
            (name,),
        ).fetchone()
    except sqlite3.Error:
        row = None  # no table yet: ;sheet has never run here
    finally:
        connection.close()
    return row[0] if row else None


def character_guild(s):
    """The character's guild: the latest ;sheet snapshot's, else INFO's
    (read-only, no roundtime); None when neither says."""
    name = getattr(s.state, "name", None)
    guild = snapshot_guild(name) if name else None
    return guild or parse_info(ask(s, "info") or "").get("guild")


def is_empath(guild):
    """True for the Empath guild, however the snapshot spelled it."""
    return str(guild or "").strip().lower() == "empath"
