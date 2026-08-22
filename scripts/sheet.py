"""Snapshot your character sheet into the history database:  ;sheet

Records INFO and EXP ALL — stats, circle, TDPs, favors, and the full
skill roster with ranks — into ~/.revenant/xp.db, where beholder
renders the history (#61). Every session snapshots on start and every
three hours after; the sheet moves slowly, so that's plenty. A command
the game leaves unanswered (login noise eats them) is re-asked, and
whatever still won't answer is left out of the snapshot rather than
stored as blanks. ;sheet once takes a single snapshot and exits.
;stop sheet opts a session out; REVENANT_NO_SHEET=1 disables the
autostart.
"""

import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

INTERVAL = 3 * 3600  # seconds between snapshots
COLLECT_SECONDS = 5  # patience per ask; the answer's last line ends it early
ATTEMPTS = 3  # re-asks for a command the game left unanswered
RETRY_SLEEP = 5  # seconds between re-asks, letting login noise settle

# The recognizable final line of each command's answer.
INFO_END = "Encumbrance"
EXP_ALL_END = "Time Development Points"

STAT_NAMES = (
    "Strength",
    "Reflex",
    "Agility",
    "Charisma",
    "Discipline",
    "Wisdom",
    "Intelligence",
    "Stamina",
)
_STAT = re.compile(rf"({'|'.join(STAT_NAMES)})\s*:\s*(\d+)")
_CIRCLE = re.compile(r"Circle:\s*(\d+)")
_TDPS = re.compile(r"TDPs\s*:\s*(\d+)")
_FAVORS = re.compile(r"Favors\s*:\s*(\d+)")
# Two-column EXP ALL rows: "     Light Armor:      3 10% clear (0/34)".
# The % requirement keeps headers and totals out.
_SKILL = re.compile(r"([A-Za-z][A-Za-z' ]+):\s+(\d+)\s+(\d+)%")

SCHEMA = """
CREATE TABLE IF NOT EXISTS stats (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    stat TEXT NOT NULL,
    value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sheet_skills (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    percent INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS character (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    circle INTEGER,
    tdps INTEGER,
    favors INTEGER
);
"""


def database_path() -> Path:
    return Path(os.environ.get("REVENANT_XP_DB", "~/.revenant/xp.db")).expanduser()


def ensure_schema(connection):
    connection.executescript(SCHEMA)
    connection.commit()


def parse_info(text):
    """Stats, circle, TDPs and favors from INFO output."""
    stats = {name: int(value) for name, value in _STAT.findall(text)}
    circle = _CIRCLE.search(text)
    tdps = _TDPS.search(text)
    favors = _FAVORS.search(text)
    return {
        "stats": stats,
        "circle": int(circle.group(1)) if circle else None,
        "tdps": int(tdps.group(1)) if tdps else None,
        "favors": int(favors.group(1)) if favors else None,
    }


def parse_exp_all(text):
    """The full roster from EXP ALL: {skill: (rank, percent)}."""
    return {
        skill.strip(): (int(rank), int(percent))
        for skill, rank, percent in _SKILL.findall(text)
        if skill.strip() != "SKILL"
    }


def insert_snapshot(connection, character, logged_at, info, skills):
    connection.executemany(
        "INSERT INTO stats (logged_at, character_name, stat, value)"
        " VALUES (?, ?, ?, ?)",
        [(logged_at, character, stat, value) for stat, value in info["stats"].items()],
    )
    connection.executemany(
        "INSERT INTO sheet_skills"
        " (logged_at, character_name, skill_name, rank, percent)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (logged_at, character, skill, rank, percent)
            for skill, (rank, percent) in sorted(skills.items())
        ],
    )
    # An unanswered INFO must leave no trace — an all-None character
    # row reads as data ("circle None") when it's really a gap (#65).
    if info["stats"] or any(
        info[key] is not None for key in ("circle", "tdps", "favors")
    ):
        connection.execute(
            "INSERT INTO character (logged_at, character_name, circle, tdps, favors)"
            " VALUES (?, ?, ?, ?, ?)",
            (logged_at, character, info["circle"], info["tdps"], info["favors"]),
        )
    connection.commit()


def collect(s, seconds, until=None):
    """Main-stream text for a window after a command. INFO and EXP ALL
    answer in multi-line, multi-column blocks; their last line
    (`until`) ends the wait early, the window bounds it otherwise."""
    pieces = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = s.get(timeout=0.5)
        if line is None:
            continue
        pieces.append(line)
        if until is not None and until in line:
            break
    return "\n".join(pieces)


def ask(s, command, parse, until, answered):
    """parse() of the command's answer, re-asking up to ATTEMPTS times:
    a command sent while login noise is still settling can go
    unanswered entirely (captured 2026-08-22 — a session-start INFO
    never answered while the following EXP ALL was, storing an
    all-None character row, #65)."""
    result = parse("")
    for attempt in range(ATTEMPTS):
        if attempt:
            s.sleep(RETRY_SLEEP)
        s.put(command)
        result = parse(collect(s, COLLECT_SECONDS, until))
        if answered(result):
            break
    return result


def snapshot(s):
    info = ask(s, "info", parse_info, INFO_END, lambda r: bool(r["stats"]))
    skills = ask(s, "exp all", parse_exp_all, EXP_ALL_END, bool)
    if not info["stats"] and not skills:
        s.echo("sheet: nothing parsed from INFO / EXP ALL — is the game answering?")
        return
    character = (
        (s.state.name if s.state else None)
        or os.environ.get("REVENANT_CHARACTER")
        or "unknown"
    )
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        ensure_schema(connection)
        insert_snapshot(
            connection,
            character,
            datetime.now(timezone.utc).isoformat(),
            info,
            skills,
        )
    finally:
        connection.close()
    if not info["stats"]:
        s.echo(
            f"sheet: INFO went unanswered — snapshot for {character} "
            f"has {len(skills)} skills only"
        )
        return
    s.echo(
        f"sheet: snapshot for {character} — {len(info['stats'])} stats, "
        f"{len(skills)} skills, circle {info['circle']}, {info['tdps']} TDPs"
    )


def main(s):
    once = bool(s.args) and s.args[0] == "once"
    while True:
        snapshot(s)
        if once:
            return
        s.sleep(INTERVAL)
