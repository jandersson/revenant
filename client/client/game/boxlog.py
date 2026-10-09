"""What each opened box held, told to the creature and the ground that
dropped it (#423).

Three tables in history.db. `box_drops`: one row per box ;hunt picks up —
the box's item id, its noun and description, the creature searched, the
ground, the room and the `loot` row of that search. `box_contents`: one
row per box ;boxes opens — the id, the trap and lock readings (1-17, 0
for none, NULL unread), the coins in copper per currency (`kronars`,
`lirums`, `dokoras`: one box held Kronars and Dokoras, #425) and their
worth in copper Kronars at money.KRONAR_RATES (`coins`, `currency`
"Kronars"; a row from before #425 has one currency for all its coins),
the items kept and the items trashed, and the ground and creature it
came from with how that was decided:

- "id": a `box_drops` row of the same character, id and noun. The id is
  the game's item id; a box keeps it from pickup to opening within one
  login (the copper box 139883771, 2026-10-02: STOW BOX at prompt
  1790949704, ;boxes 23 minutes later), and a new login renumbers
  every item (docs/protocol.md).
- "batch": no id on record (picked up before the parser kept them, or
  across a relog), so the boxes found since the last ;boxes run — the
  `loot` rows with a box — stand in: when they were all on one ground
  the ground is that one, and the creature too when it was one kind.
- "": neither.

A third table, `box_attempts` (#493): one row per DISARM or PICK
;boxes sends — the verb, the reading it was made at, the class the
answer got, the lockpick, Locksmithing's rank and mindstate at the
time, the seconds it took — so a ground's boxes are judged by the
attempts that failed as well as the boxes that opened, and the
readings calibrate against rank.

`measured` reads the copper Kronars per box back per ground, for ;hunt
grounds; `past` (beyond) says whether a creature's boxes are beyond the
character — its last three all put back too hard, none opened — so
;hunt leaves them (#495: thirteen ogre boxes in the tote at
Locksmithing 53). A logging failure is logged and never stops a script.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from client.game import lootlog, money

DROPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS box_drops (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    box_id TEXT,
    noun TEXT NOT NULL,
    description TEXT NOT NULL,
    creature TEXT NOT NULL,
    ground TEXT NOT NULL,
    room INTEGER,
    loot_seq INTEGER
)
"""

CONTENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS box_contents (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_at TEXT NOT NULL,
    run_started TEXT NOT NULL,
    character_name TEXT NOT NULL,
    box_id TEXT,
    noun TEXT NOT NULL,
    trap INTEGER,
    lock INTEGER,
    coins INTEGER NOT NULL,
    currency TEXT NOT NULL,
    items TEXT NOT NULL,
    trashed TEXT NOT NULL,
    ground TEXT NOT NULL,
    creature TEXT NOT NULL,
    source TEXT NOT NULL,
    drop_seq INTEGER,
    kronars INTEGER,
    lirums INTEGER,
    dokoras INTEGER
)
"""
# The copper per currency (#425), added to a table from before it.
CURRENCY_COLUMNS = ("kronars", "lirums", "dokoras")

# One row per DISARM or PICK ;boxes sends (#493): the verb ("identify",
# "disarm", "pick", "open"), the reading of 1-17 the attempt was made at
# (NULL unread), the class ;boxes gave the answer ("disarmed",
# "unlocked", "retry", "sprung", "broken pick", "too hard", ... or
# "unknown"), the lockpick kind, Locksmithing's rank and mindstate off
# the exp window at the time, and the seconds from the send to the
# answer. Joins box_drops and box_contents by box_id, and the run by
# run_started.
ATTEMPTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS box_attempts (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    run_started TEXT NOT NULL,
    character_name TEXT NOT NULL,
    box_id TEXT,
    noun TEXT NOT NULL,
    verb TEXT NOT NULL,
    reading INTEGER,
    outcome TEXT NOT NULL,
    lockpick TEXT NOT NULL,
    rank INTEGER,
    mindstate INTEGER,
    seconds REAL
)
"""
ATTEMPT_COLUMNS = (
    "logged_at",
    "run_started",
    "character_name",
    "box_id",
    "noun",
    "verb",
    "reading",
    "outcome",
    "lockpick",
    "rank",
    "mindstate",
    "seconds",
)

DROP_COLUMNS = (
    "logged_at",
    "character_name",
    "box_id",
    "noun",
    "description",
    "creature",
    "ground",
    "room",
    "loot_seq",
)
CONTENT_COLUMNS = (
    "opened_at",
    "run_started",
    "character_name",
    "box_id",
    "noun",
    "trap",
    "lock",
    "coins",
    "currency",
    "items",
    "trashed",
    "ground",
    "creature",
    "source",
    "drop_seq",
    *CURRENCY_COLUMNS,
)
_TEXT = (
    "noun",
    "description",
    "creature",
    "ground",
    "currency",
    "source",
    "verb",
    "outcome",
    "lockpick",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(connection):
    lootlog.ensure_schema(connection)  # the batch attribution reads `loot`
    connection.execute(DROPS_SCHEMA)
    connection.execute(CONTENTS_SCHEMA)
    connection.execute(ATTEMPTS_SCHEMA)
    present = {row[1] for row in connection.execute("PRAGMA table_info(box_contents)")}
    for column in CURRENCY_COLUMNS:
        if column not in present:
            connection.execute(f"ALTER TABLE box_contents ADD COLUMN {column} INTEGER")
    connection.commit()


def _insert(connection, table, columns, fields):
    row = {column: fields.get(column) for column in columns}
    for column in _TEXT:
        if column in row:
            row[column] = row[column] or ""
    for column in ("items", "trashed"):
        if column in row:
            row[column] = "; ".join(row[column] or ())
    if "coins" in row:
        row["coins"] = row["coins"] or 0
    cursor = connection.execute(
        f"INSERT INTO {table} ({', '.join(columns)})"
        f" VALUES ({', '.join('?' * len(columns))})",
        [row[column] for column in columns],
    )
    connection.commit()
    return cursor.lastrowid


def _character(s):
    return getattr(getattr(s, "state", None), "name", None) or "unknown"


def record_drop(connection, **fields):
    """One `box_drops` row from the DROP_COLUMNS given; returns the seq."""
    fields["logged_at"] = fields.get("logged_at") or now()
    if fields.get("box_id") is not None:
        fields["box_id"] = str(fields["box_id"])
    return _insert(connection, "box_drops", DROP_COLUMNS, fields)


def log_drop(s, path=None, **fields):
    """A box picked up, as a `box_drops` row; the seq, or None when the
    write failed (logged, never raised)."""
    try:
        connection = sqlite3.connect(str(lootlog.db_path(path)))
        try:
            ensure_schema(connection)
            return record_drop(connection, character_name=_character(s), **fields)
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("box drop log failed")
        return None


def record_attempt(connection, **fields):
    """One `box_attempts` row (#493); returns the seq."""
    fields["logged_at"] = fields.get("logged_at") or now()
    fields["run_started"] = fields.get("run_started") or fields["logged_at"]
    if fields.get("box_id") is not None:
        fields["box_id"] = str(fields["box_id"])
    fields["outcome"] = fields.get("outcome") or "unknown"
    return _insert(connection, "box_attempts", ATTEMPT_COLUMNS, fields)


def log_attempt(s, path=None, **fields):
    """A DISARM or PICK sent, as a `box_attempts` row; the seq, or None
    when the write failed (logged, never raised)."""
    try:
        connection = sqlite3.connect(str(lootlog.db_path(path)))
        try:
            ensure_schema(connection)
            return record_attempt(connection, character_name=_character(s), **fields)
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("box attempt log failed")
        return None


def attribute(connection, character, box_id, noun, run_started):
    """{"ground", "creature", "source", "drop_seq"} for a box opened in
    the run that began at `run_started`: by its id, else by the batch
    of boxes found since the character's previous ;boxes run, else
    unknown (the module docstring)."""
    if box_id:
        row = connection.execute(
            "SELECT seq, ground, creature FROM box_drops"
            " WHERE character_name = ? AND box_id = ? AND lower(noun) = lower(?)"
            " ORDER BY seq DESC LIMIT 1",
            (character, str(box_id), noun),
        ).fetchone()
        if row:
            return {
                "ground": row[1],
                "creature": row[2],
                "source": "id",
                "drop_seq": row[0],
            }
    (since,) = connection.execute(
        "SELECT MAX(opened_at) FROM box_contents"
        " WHERE character_name = ? AND run_started < ?",
        (character, run_started),
    ).fetchone()
    found = connection.execute(
        "SELECT DISTINCT lower(ground), creature FROM loot"
        " WHERE character_name = ? AND outcome = 'box'"
        " AND logged_at > ? AND logged_at < ?",
        (character, since or "", run_started),
    ).fetchall()
    grounds = {ground for ground, _ in found}
    if len(grounds) == 1:
        creatures = {creature for _, creature in found}
        return {
            "ground": grounds.pop(),
            "creature": creatures.pop() if len(creatures) == 1 else "",
            "source": "batch",
            "drop_seq": None,
        }
    return {"ground": "", "creature": "", "source": "", "drop_seq": None}


def record_opened(connection, **fields):
    """One `box_contents` row, its origin decided by attribute(); returns
    the attribution. Coins given per currency (`kronars`, `lirums`,
    `dokoras`) make `coins` their worth in copper Kronars."""
    if any(fields.get(column) is not None for column in CURRENCY_COLUMNS):
        fields["coins"] = sum(
            money.in_kronars(fields.get(column) or 0, column)
            for column in CURRENCY_COLUMNS
        )
        fields["currency"] = "Kronars"
    fields["opened_at"] = fields.get("opened_at") or now()
    fields["run_started"] = fields.get("run_started") or fields["opened_at"]
    if fields.get("box_id") is not None:
        fields["box_id"] = str(fields["box_id"])
    origin = attribute(
        connection,
        fields.get("character_name") or "unknown",
        fields.get("box_id"),
        fields.get("noun") or "",
        fields["run_started"],
    )
    fields.update(origin)
    _insert(connection, "box_contents", CONTENT_COLUMNS, fields)
    return origin


def log_opened(s, path=None, **fields):
    """A box opened, as a `box_contents` row; the attribution, or None
    when the write failed (logged, never raised)."""
    try:
        connection = sqlite3.connect(str(lootlog.db_path(path)))
        try:
            ensure_schema(connection)
            return record_opened(connection, character_name=_character(s), **fields)
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("box contents log failed")
        return None


BEYOND_BOXES = 3  # the creature's last boxes that must all have beaten the character


def verdicts(connection, character, creature, boxes=BEYOND_BOXES):
    """The last `boxes` boxes of `creature` that ;boxes worked — its
    `box_attempts` joined to the `box_drops` rows of the same character
    and id — as [(box_id, opened, too_hard)], newest first (#495)."""
    rows = connection.execute(
        "SELECT d.box_id,"
        " SUM(CASE WHEN a.verb = 'open' AND a.outcome = 'open' THEN 1 ELSE 0 END),"
        " SUM(CASE WHEN a.outcome = 'too hard' THEN 1 ELSE 0 END),"
        " MAX(a.seq) AS last"
        " FROM box_attempts a JOIN box_drops d"
        " ON d.box_id = a.box_id AND d.character_name = a.character_name"
        " WHERE a.character_name = ? AND lower(d.creature) = lower(?)"
        " GROUP BY d.box_id ORDER BY last DESC LIMIT ?",
        (character, str(creature or ""), boxes),
    ).fetchall()
    return [(box_id, bool(opened), bool(hard)) for box_id, opened, hard, _ in rows]


def beyond(connection, character, creature, boxes=BEYOND_BOXES):
    """True when the creature's last `boxes` boxes all went back too hard
    and none opened (#495): the measured answer to whether this
    character can pick this creature's boxes. Fewer boxes on record, or
    one opened among them, is no verdict."""
    found = verdicts(connection, character, creature, boxes)
    return len(found) >= boxes and all(hard and not opened for _, opened, hard in found)


def past(character, creature, path=None, boxes=BEYOND_BOXES):
    """beyond() off history.db; False when there is none or it cannot be
    read (logged, never raised)."""
    if not creature:
        return False
    try:
        path = lootlog.db_path(path)
        if not Path(path).is_file():
            return False
        connection = sqlite3.connect(str(path))
        try:
            ensure_schema(connection)
            return beyond(connection, character, creature, boxes)
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("box verdict failed")
        return False


def origin(s, box_id, noun, run_started, path=None):
    """attribute() off history.db for a box in hand; {} when the
    database cannot be read (logged, never raised)."""
    try:
        connection = sqlite3.connect(str(lootlog.db_path(path)))
        try:
            ensure_schema(connection)
            return attribute(connection, _character(s), box_id, noun, run_started)
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("box origin failed")
        return {}


def values(connection, character=None):
    """{ground lower-cased: {"opened", "coins"}}: the boxes opened that
    were told to a ground and what they held in copper Kronars, each
    row's coins converted from its currency (#425)."""
    mine, args = (" AND character_name = ?", [character]) if character else ("", [])
    found = {}
    for ground, coins, currency in connection.execute(
        "SELECT lower(ground), coins, currency FROM box_contents"
        f" WHERE ground != ''{mine}",
        args,
    ):
        entry = found.setdefault(ground, {"opened": 0, "coins": 0})
        entry["opened"] += 1
        entry["coins"] += money.in_kronars(coins or 0, currency)
    return found


def measured(character=None, path=None):
    """values() off history.db; {} when there is none or it cannot be
    read (logged, never raised)."""
    try:
        path = lootlog.db_path(path)
        if not Path(path).is_file():
            return {}
        connection = sqlite3.connect(str(path))
        try:
            ensure_schema(connection)
            return values(connection, character)
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("box values failed")
        return {}
