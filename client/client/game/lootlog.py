"""Each LOOT's outcome logged per creature, so a hunting ground's box
drop rate is read off data rather than guessed (#329).

One row per search in history.db's `loot` table: the creature as the
answer names it, the room and the hunting ground, the outcome — box,
treasure (coins, gems, an item), nothing, or unknown when the answer
held neither line — what it carried and the box noun. The game
publishes no rate: LOOT with no option is the Goods option, which
"first checks for a box, and if it finds none, then treasure is
generated", a creature giving one or the other, never both
(Elanthipedia: Loot command), and a creature page only says whether
it has boxes at all ("Has Boxes=yes"). Captured wordings: "You search
the scavenger goblin." then "The goblin was carrying a poorly made
iron box!" or "The goblin was carrying 9 copper coins (Kronars) and 1
bronze coin (Kronar)!", and "You find nothing of interest." for an
empty one (2026-09-26). ;hunt writes a row after every LOOT; `rates`
reads them back. A logging failure is logged and never stops a hunt.
"""

import logging
import re
import sqlite3
from datetime import datetime, timezone

from client.game.loot import BOX_NOUNS

SCHEMA = """
CREATE TABLE IF NOT EXISTS loot (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    creature TEXT NOT NULL,
    room INTEGER,
    ground TEXT NOT NULL,
    outcome TEXT NOT NULL,
    carried TEXT NOT NULL,
    box TEXT
)
"""

COLUMNS = (
    "logged_at",
    "character_name",
    "creature",
    "room",
    "ground",
    "outcome",
    "carried",
    "box",
)

OUTCOMES = ("box", "treasure", "nothing", "unknown")

_SEARCHED = re.compile(r"^You search the (.+?)\.$", re.IGNORECASE)
_CARRYING = re.compile(r"\bwas carrying (.+?)!?$", re.IGNORECASE)
_NOTHING = ("find nothing", "nothing of value", "nothing of interest")


def parse(answer):
    """LOOT's answer as {"creature", "outcome", "carried", "box"}, or None
    when it is no search at all (the creature gone, a refusal)."""
    creature = ""
    carried = ""
    empty = False
    for raw in str(answer or "").splitlines():
        line = raw.strip()
        if match := _SEARCHED.match(line):
            creature = match.group(1).strip().lower()
        elif match := _CARRYING.search(line):
            carried = match.group(1).strip()
        elif any(phrase in line.lower() for phrase in _NOTHING):
            empty = True
    if not (creature or carried or empty):
        return None
    box = None
    if carried:
        words = re.findall(r"[\w'-]+", carried.lower())
        box = next((word for word in words if word in BOX_NOUNS), None)
        outcome = "box" if box else "treasure"
    elif empty:
        outcome = "nothing"
    else:
        outcome = "unknown"  # the window closed before the carried line
    return {"creature": creature, "outcome": outcome, "carried": carried, "box": box}


def ensure_schema(connection):
    connection.execute(SCHEMA)
    connection.commit()


def record(connection, **fields):
    """One row from the COLUMNS given; returns the seq."""
    row = {column: fields.get(column) for column in COLUMNS}
    row["logged_at"] = row["logged_at"] or datetime.now(timezone.utc).isoformat()
    for text_column in ("creature", "ground", "carried"):
        row[text_column] = row[text_column] or ""
    cursor = connection.execute(
        f"INSERT INTO loot ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
        [row[column] for column in COLUMNS],
    )
    connection.commit()
    return cursor.lastrowid


def log(s, answer, ground="", path=None):
    """A hunt's LOOT answer recorded with what the state knows for free.
    Returns the seq, or None when the answer is no search or the write
    failed (logged, never raised)."""
    parsed = parse(answer)
    if parsed is None:
        return None
    try:
        if path is None:
            from client.game.history import database_path

            path = database_path()
        state = getattr(s, "state", None)
        connection = sqlite3.connect(str(path))
        try:
            ensure_schema(connection)
            return record(
                connection,
                character_name=getattr(state, "name", None) or "unknown",
                room=getattr(state, "room_uid", None),
                ground=ground or "",
                **parsed,
            )
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("loot log failed")
        return None


def rates(connection, character=None, ground=None):
    """Searches per creature with how many gave a box, treasure or
    nothing, the unknown ones left out, most searched first:
    [{"creature", "searched", "box", "treasure", "nothing"}]."""
    clauses, values = ["outcome != 'unknown'"], []
    if character:
        clauses.append("character_name = ?")
        values.append(character)
    if ground:
        clauses.append("ground = ?")
        values.append(ground)
    cursor = connection.execute(
        "SELECT creature, COUNT(*),"
        " SUM(outcome = 'box'), SUM(outcome = 'treasure'), SUM(outcome = 'nothing')"
        f" FROM loot WHERE {' AND '.join(clauses)}"
        " GROUP BY creature ORDER BY COUNT(*) DESC, creature",
        values,
    )
    keys = ("creature", "searched", "box", "treasure", "nothing")
    return [dict(zip(keys, row)) for row in cursor.fetchall()]
