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

One row per hunt in the `hunts` table (#419): the ground, the style,
the minutes on the ground, the kills, the searches with the boxes and
coins they found, the boxes taken and why it ended — the per-hour
yield a search row cannot give. `yields` reads both tables back per
ground, for `;hunt grounds`' measured box rate.
"""

import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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

HUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS hunts (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    ground TEXT NOT NULL,
    style TEXT NOT NULL,
    minutes REAL NOT NULL,
    kills INTEGER NOT NULL,
    searched INTEGER NOT NULL,
    boxes INTEGER NOT NULL,
    coins INTEGER NOT NULL,
    boxes_taken INTEGER NOT NULL,
    reason TEXT NOT NULL
)
"""

HUNT_TEXT = ("character_name", "ground", "style", "reason")
HUNT_NUMBERS = ("minutes", "kills", "searched", "boxes", "coins", "boxes_taken")
HUNT_COLUMNS = ("logged_at",) + HUNT_TEXT + HUNT_NUMBERS

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
    connection.execute(HUNTS_SCHEMA)
    connection.commit()


def _path(path):
    if path is not None:
        return path
    from client.game.history import database_path

    return database_path()


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
        state = getattr(s, "state", None)
        connection = sqlite3.connect(str(_path(path)))
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


def record_hunt(connection, **fields):
    """One `hunts` row from the HUNT_COLUMNS given; returns the seq."""
    row = {column: fields.get(column) for column in HUNT_COLUMNS}
    row["logged_at"] = row["logged_at"] or datetime.now(timezone.utc).isoformat()
    for column in HUNT_TEXT:
        row[column] = row[column] or ""
    for column in HUNT_NUMBERS:
        row[column] = row[column] or 0
    cursor = connection.execute(
        f"INSERT INTO hunts ({', '.join(HUNT_COLUMNS)})"
        f" VALUES ({', '.join('?' * len(HUNT_COLUMNS))})",
        [row[column] for column in HUNT_COLUMNS],
    )
    connection.commit()
    return cursor.lastrowid


def log_hunt(s, path=None, **fields):
    """A finished hunt's totals as a `hunts` row, the character off the
    state. Returns the seq, or None when the write failed (logged,
    never raised)."""
    try:
        state = getattr(s, "state", None)
        connection = sqlite3.connect(str(_path(path)))
        try:
            ensure_schema(connection)
            return record_hunt(
                connection,
                character_name=getattr(state, "name", None) or "unknown",
                **fields,
            )
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("hunt log failed")
        return None


def yields(connection, character=None):
    """Each ground's measured yield, keyed by the ground lower-cased:
    {"searched", "boxes"} off the loot rows (the unknown ones left out)
    and {"hunts", "minutes", "hunt_boxes"} off the hunts rows, 0 where
    a table has none for it."""
    found = {}

    def entry(ground):
        return found.setdefault(
            ground,
            {"searched": 0, "boxes": 0, "hunts": 0, "minutes": 0.0, "hunt_boxes": 0},
        )

    mine, values = (" AND character_name = ?", [character]) if character else ("", [])
    for ground, searched, boxes in connection.execute(
        "SELECT lower(ground), COUNT(*), SUM(outcome = 'box') FROM loot"
        f" WHERE outcome != 'unknown'{mine} GROUP BY lower(ground)",
        values,
    ):
        entry(ground).update(searched=searched, boxes=boxes or 0)
    for ground, hunts, minutes, boxes in connection.execute(
        "SELECT lower(ground), COUNT(*), SUM(minutes), SUM(boxes) FROM hunts"
        f" WHERE 1 = 1{mine} GROUP BY lower(ground)",
        values,
    ):
        entry(ground).update(hunts=hunts, minutes=minutes or 0.0, hunt_boxes=boxes or 0)
    return found


def measured(character=None, path=None):
    """yields() off history.db; {} when there is none or it cannot be
    read (logged, never raised)."""
    try:
        path = _path(path)
        if not Path(path).is_file():
            return {}
        connection = sqlite3.connect(str(path))
        try:
            ensure_schema(connection)
            return yields(connection, character)
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("loot yields failed")
        return {}


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
