"""Encumbrance as a function of load and stats — the model behind ;enc.

The game reports a burden level, not a weight, and Elanthipedia's
Encumbrance page gives the rule that ties the two: with the levels
numbered 1 (None) to 12 (squashed), a character can carry up to
10 x ceil(0.4 x (level + 5) x (Strength + Stamina)) stones at that
level (its worked example: 10 Strength and 10 Stamina carry 480 stones
with none). So each level is a band of weights, every point of
Strength or Stamina widens every band by 4 x (level + 5) stones, and
the burden you see says which band your load falls in. The formula is
the wiki's (a pre-DR3 page) and held on 2026-09-12: ballast pinned a
load to 890-900 stones at 10 + 11, the rule said two points, and two
points of Stamina read Heavy Burden. Coins weigh 0.2 stones each,
which makes them the instrument. Rows go to history.db's `encumbrance` table, one per
reading: stats, level, ballast, note. Model: docs/encumbrance.md.
"""

import re
import sqlite3
from datetime import datetime, timezone

LEVELS = (
    "None",
    "Light Burden",
    "Somewhat Burdened",
    "Burdened",
    "Heavy Burden",
    "Very Heavy Burden",
    "Overburdened",
    "Very Overburdened",
    "Extremely Overburdened",
    "Tottering Under Burden",
    "Are you even able to move?",
    "It's amazing you aren't squashed!",
)
COIN_STONES = 0.2  # a coin of any metal weighs a fifth of a stone
# "  Encumbrance : Very Heavy Burden" — INFO's line and ENCUMBRANCE's answer alike.
_LEVEL = re.compile(r"Encumbrance\s*:\s*(.+?)\s*$", re.MULTILINE)


def level_index(name):
    """1 for None ... 12 for squashed; None for a name the game never uses."""
    lowered = (name or "").strip().lower()
    for index, level in enumerate(LEVELS, 1):
        if level.lower() == lowered:
            return index
    return None


def parse_level(text):
    """The burden level named in INFO or ENCUMBRANCE's answer, or None."""
    match = _LEVEL.search(text)
    if not match:
        return None
    name = match.group(1)
    return name if level_index(name) else None


def capacity(level, strength, stamina):
    """The most stones carried at burden `level` (1-12), per the wiki."""
    # integer arithmetic: 0.4 x (L + 5) x (Str + Sta) is 2(L + 5)(Str + Sta) / 5,
    # and a float ceiling turns the wiki's 48.0 into 49
    return 10 * -(-2 * (level + 5) * (strength + stamina) // 5)


def band(name, strength, stamina):
    """(over, up_to): a load at burden `name` weighs more than `over`
    and at most `up_to` stones; over is 0 for None."""
    index = level_index(name)
    if index is None:
        return None
    over = capacity(index - 1, strength, stamina) if index > 1 else 0
    return over, capacity(index, strength, stamina)


def level_for(weight, strength, stamina):
    """The burden name a load of `weight` stones gives these stats."""
    for index, name in enumerate(LEVELS, 1):
        if weight <= capacity(index, strength, stamina):
            return name
    return LEVELS[-1]


def points_to_lighten(name, strength, stamina, weight=None):
    """How many points of Strength or Stamina (they count alike) drop
    the burden one level: (fewest, most) over the band when the weight
    is unknown, the exact count when it is known. None at None."""
    index = level_index(name)
    if index is None or index == 1:
        return None
    over, up_to = band(name, strength, stamina)
    weights = [weight] if weight is not None else [over + 1, up_to]
    counts = []
    for stones in weights:
        points = 0
        while capacity(index - 1, strength + points, stamina) < stones:
            points += 1
        counts.append(points)
    return (min(counts), max(counts)) if weight is None else (counts[0], counts[0])


def coins_for(stones):
    """Coins that weigh `stones`: 5 to the stone."""
    return int(round(stones / COIN_STONES))


SCHEMA = """
CREATE TABLE IF NOT EXISTS encumbrance (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    strength INTEGER,
    stamina INTEGER,
    level TEXT NOT NULL,
    ballast_stones INTEGER NOT NULL,
    note TEXT NOT NULL
)
"""
COLUMNS = (
    "logged_at",
    "character_name",
    "strength",
    "stamina",
    "level",
    "ballast_stones",
    "note",
)


def ensure_schema(connection):
    connection.execute(SCHEMA)
    connection.commit()


def record(connection, character, strength, stamina, level, ballast_stones=0, note=""):
    ensure_schema(connection)
    connection.execute(
        f"INSERT INTO encumbrance ({', '.join(COLUMNS)}) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            character,
            strength,
            stamina,
            level,
            ballast_stones,
            note,
        ),
    )
    connection.commit()


def rows(connection, character=None):
    ensure_schema(connection)
    where, values = "", []
    if character:
        where, values = " WHERE character_name = ?", [character]
    cursor = connection.execute(
        f"SELECT {', '.join(COLUMNS)} FROM encumbrance{where} ORDER BY seq", values
    )
    return [dict(zip(COLUMNS, row)) for row in cursor.fetchall()]


def summarize(entries):
    lines = []
    for entry in entries:
        stamp = (entry["logged_at"] or "")[:16].replace("T", " ")
        ballast = f" +{entry['ballast_stones']} st" if entry["ballast_stones"] else ""
        note = f" — {entry['note']}" if entry["note"] else ""
        lines.append(
            f"{stamp} Str {entry['strength']} Sta {entry['stamina']}: "
            f"{entry['level']}{ballast}{note}"
        )
    return lines


def open_history(path):
    connection = sqlite3.connect(path)
    ensure_schema(connection)
    return connection
