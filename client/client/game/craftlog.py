"""What a craft made and how well: the crafting dataset in history.db
(the operator, 2026-10-12: "we finish crafting an item and we analyze
an item, we record its quality and the character's skill").

One `crafts` row per finished item: when, the character, the
discipline, the item, ANALYZE's quality word and its rank on the
game's scale (Elanthipedia: Crafting, Product Quality: 0 practically
worthless to 12 masterfully-crafted), the skill with its rank and
percent at the finish, the difficulty ANALYZE names ("extremely easy"),
and ANALYZE's text whole for what a later reading wants. A logging
failure is logged and never stops a script.

ANALYZE MY CREAM on a finished blister cream (captured 2026-10-12, 4 s
roundtime): "This appears to be a type of basic wound remedy that is of
exceptional quality." and "The cream is an extremely easy piece to
make."
"""

import logging
import re
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS crafts (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    made_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    discipline TEXT NOT NULL,
    item TEXT NOT NULL,
    quality TEXT NOT NULL,
    quality_rank INTEGER,
    skill TEXT NOT NULL,
    skill_rank INTEGER,
    skill_percent INTEGER,
    difficulty TEXT NOT NULL,
    text TEXT NOT NULL
)
"""
# Lowest to highest: the index is the game's ordinal.
QUALITIES = (
    "practically worthless",
    "dismal",
    "poorly-crafted",
    "below-average",
    "mediocre",
    "about average",
    "above-average",
    "well-crafted",
    "finely-crafted",
    "superior",
    "exceptional",
    "outstanding",
    "masterfully-crafted",
)
_QUALITY = re.compile(r"is of (?P<quality>[\w' -]+?) quality")
_DIFFICULTY = re.compile(r"is an? (?P<difficulty>[\w' -]+?) piece to make")


def read(text):
    """(quality word, its rank or None, difficulty) from ANALYZE's
    answer; "" for what it does not say."""
    text = str(text or "")
    quality = _QUALITY.search(text)
    difficulty = _DIFFICULTY.search(text)
    word = quality.group("quality").strip().lower() if quality else ""
    return (
        word,
        QUALITIES.index(word) if word in QUALITIES else None,
        difficulty.group("difficulty").strip().lower() if difficulty else "",
    )


def log(character, discipline, item, text, skill, rank, percent, path=None):
    """One row for a finished item and ANALYZE's `text`; the quality
    word, or None when the write failed."""
    from client.game.lootlog import db_path

    quality, ordinal, difficulty = read(text)
    try:
        connection = sqlite3.connect(str(db_path(path)))
        try:
            connection.execute(SCHEMA)
            connection.execute(
                "INSERT INTO crafts (made_at, character_name, discipline, item,"
                " quality, quality_rank, skill, skill_rank, skill_percent,"
                " difficulty, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    character or "unknown",
                    discipline,
                    item,
                    quality,
                    ordinal,
                    skill,
                    rank,
                    percent,
                    difficulty,
                    str(text or ""),
                ),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error:
        logging.getLogger(__name__).exception("craft not logged")
        return None
    return quality
