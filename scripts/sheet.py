"""Snapshot your character sheet into the history database:  ;sheet

Seeds the parser's exp table with every skill from EXP ALL (the window
pushes only the learning ones; a cleared skill stays at 0/34, #295).
Records INFO, EXP ALL and SPELL — stats, circle, TDPs, favors, the full
skill roster with ranks, the rested-experience line (stored, usable,
refresh, in minutes), and the spells: learned spells by chapter,
apprentice spells, cantrips with their keywords, magic feats, and the
spell slots left (#136) — into ~/.revenant/history.db, where beholder
renders the history (#61). SPELL costs no roundtime, so it rides the
schedule; it is asked once per snapshot and a miss waits for the next. Every session snapshots on start and every
three hours after; the sheet moves slowly, so that's plenty. A command
the game leaves unanswered (login noise eats them) is re-asked, and
whatever still won't answer is left out of the snapshot rather than
stored as blanks. ;sheet once takes a single snapshot and exits.

;sheet inv adds your inventory: INV LIST, flattened into rows naming
each item's container and, when the parser saw the listing, the
game's exist ids for the item and its container (#184), so "which
character has that thing?" is a query instead of a login and twins
are told apart. The autostart's first snapshot — the login — takes
it too, roundtime or not (the character is safe at login, and the
possessions are wanted from the first minute); after that it is on
demand only and never scheduled — INV LIST costs a few seconds of
roundtime (4-5s captured), which is fine when you ask for it and not
fine arriving mid-fight. Typed while the script runs (it always does —
it is an autostart), ;sheet inv asks the running script for one
inventory snapshot and the schedule carries on; from cold it takes the
one snapshot and exits, like `once`. ;sheet once at a running script
takes an extra plain snapshot the same way.

;sheet info records INFO alone — the stats, circle, TDPs, favors and
purse — the same way (typed at the running script, or once from
cold): what `;tdp` asks for after a bought point, since TRAIN moves
only a stat and the TDPs (#303).

;stop sheet opts a session out; REVENANT_NO_SHEET=1 disables the
autostart.
"""

import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from client.engine.xml_data import LEARNING_RATES
from client.game.inventory import FOOTER as INV_END
from client.game.money import parse_wealth  # noqa: F401 — the sheet's wealth parser
from client.game.inventory import parse_inventory
from client.game import possessions
from client.game.probe import collect
from client.game.rested import parse_duration, parse_rested  # noqa: F401 — the footer parser, shared with the parser and ;xp (#176)
from client.game.history import database_path as history_database_path

INTERVAL = 3 * 3600  # seconds between snapshots
COLLECT_SECONDS = 5  # patience per ask; the answer's last line ends it early
ATTEMPTS = 3  # re-asks for a command the game left unanswered
RETRY_SLEEP = 5  # seconds between re-asks, letting login noise settle

# The recognizable final line of each command's answer. INFO has no
# reliable one: Wealth and Debt trail Encumbrance, and the Debt block
# only exists for debtors — so INFO runs out its whole window (an
# "Encumbrance" early-exit silently cut the wealth capture off).
INFO_END = None
# EXP ALL's last line; the rested-experience line sits between the TDP
# line and it, so the collect must run past the TDPs (#106).
EXP_ALL_END = "EXP HELP for more information"
# SPELL closes with its preferences line (captured 2026-09-04 and
# 2026-09-05, #136). It costs no roundtime, so it rides the schedule.
SPELL_END = "SPELL STANCE"

# The renaming room answers commands with its own reminder instead of
# their output, so re-asking cannot help — it just burns ATTEMPTS *
# RETRY_SLEEP seconds. Captured 2026-09-03 (#112): a character sent
# there for a name that does not fit the setting answered three EXP ALLs
# with three identical reminders. INFO still answers; EXP ALL does not.
RENAMING_ROOM = "change your name to something which fits"
# An inventory command the game does not recognize is answered with the
# INVENTORY syntax list — a refusal, not silence, so re-asking only
# spends the retries (captured 2026-09-04: three INV FULLs, three help
# texts; the listing command is INV LIST, #127).
INVENTORY_HELP = "The INVENTORY command is the best way"

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
_GUILD = re.compile(r"Guild:\s*([A-Za-z ]+?)\s*$", re.MULTILINE)
_RACE = re.compile(r"Race:\s*([A-Za-z' ]+?)\s\s")
_GENDER = re.compile(r"Gender:\s*(\w+)")
# "You were born on the 1st day of the 4th month of Shorka the Cobra in the
# year of the Golden Panther, 338 years after the victory of Lanival the
# Redeemer." Year 0 is a real answer, not a missing one: characters that
# never finished creation report day 1, month 1, year 0 (#115).
_BORN = re.compile(
    r"born on the (\d+)\w* day of the (\d+)\w* month of .*?"
    r"(\d+) years after the victory",
    re.S,
)
# Two-column EXP ALL rows: "     Light Armor:      3 10% clear (0/34)".
# The % requirement keeps headers and totals out.
_SKILL = re.compile(r"([A-Za-z][A-Za-z' ]+):\s+(\d+)\s+(\d+)%")
# The whole row, for the parser's table: the rate word and the
# mindstate fraction after the percent.
_ROSTER = re.compile(
    r"([A-Za-z][A-Za-z' ]+):\s+(\d+)\s+(\d+)%\s+([a-z][a-z ]*?)\s*\((\d+)/34\)"
)

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
CREATE TABLE IF NOT EXISTS wealth (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    currency TEXT NOT NULL,
    copper INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS character (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    circle INTEGER,
    tdps INTEGER,
    favors INTEGER,
    guild TEXT,
    race TEXT,
    gender TEXT,
    birth_year INTEGER,
    birth_day INTEGER,
    birth_month INTEGER
);
CREATE TABLE IF NOT EXISTS spells (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    name TEXT NOT NULL,
    abbrev TEXT,
    kind TEXT NOT NULL,
    chapter TEXT
);
CREATE TABLE IF NOT EXISTS inventory (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    container TEXT,
    item TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    depth INTEGER NOT NULL
);
"""


def database_path() -> Path:
    """~/.revenant/history.db (once history.db; client/game/history.py migrates)."""
    return history_database_path()


def _add_columns(connection, table, columns):
    present = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    for column, kind in columns:
        if column not in present:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


def ensure_schema(connection):
    connection.executescript(SCHEMA)
    # The exist ids INV LIST's links carry (#184): NULL on rows from
    # before, and on a listing the parser did not see.
    _add_columns(
        connection, "inventory", (("exist", "TEXT"), ("container_exist", "TEXT"))
    )
    # CREATE IF NOT EXISTS won't add columns to a table that already
    # exists, so every column added after the first release needs its
    # own additive migration. Older rows keep NULLs; the next snapshot
    # fills them in.
    for column, kind in (
        ("guild", "TEXT"),  # the ;circle view needs it
        ("race", "TEXT"),  # the identity trio (#115): never changes,
        ("gender", "TEXT"),  # and so was never worth re-reading from
        ("birth_year", "INTEGER"),  # 30 raw game logs
        ("birth_day", "INTEGER"),
        ("birth_month", "INTEGER"),
        ("rexp_stored", "INTEGER"),  # rested experience, minutes (#106):
        ("rexp_usable", "INTEGER"),  # beholder can tell 3x windows from
        ("rexp_refresh", "INTEGER"),  # ordinary training
        ("spell_slots", "INTEGER"),  # SPELL's "You have N spell slots" (#136)
    ):
        try:
            connection.execute(f"ALTER TABLE character ADD COLUMN {column} {kind}")
        except sqlite3.OperationalError:
            pass  # already there
    connection.commit()


def parse_info(text):
    """Stats, circle, guild, TDPs, favors and the identity trio (race,
    gender, birth date) from INFO output.

    Age is deliberately not returned: it is the current Elanthian year
    minus birth_year, which eltime already knows, so storing it would
    go stale while the derived value never does (#115).
    """
    stats = {name: int(value) for name, value in _STAT.findall(text)}
    circle = _CIRCLE.search(text)
    tdps = _TDPS.search(text)
    favors = _FAVORS.search(text)
    guild = _GUILD.search(text)
    race = _RACE.search(text)
    gender = _GENDER.search(text)
    born = _BORN.search(text)
    return {
        "stats": stats,
        "circle": int(circle.group(1)) if circle else None,
        "tdps": int(tdps.group(1)) if tdps else None,
        "favors": int(favors.group(1)) if favors else None,
        "guild": guild.group(1) if guild else None,
        "race": race.group(1).strip() if race else None,
        "gender": gender.group(1) if gender else None,
        "birth_day": int(born.group(1)) if born else None,
        "birth_month": int(born.group(2)) if born else None,
        "birth_year": int(born.group(3)) if born else None,
        "wealth": parse_wealth(text),
    }


# SPELL, captured 2026-09-04 (a circle-1 Paladin: apprentice spells,
# no feats) and 2026-09-05 (a circle-200 Moon Mage: chapters of learned
# spells, cantrips, seventeen feats). Each list is names separated by
# commas and a final "and", an abbreviation in brackets where the game
# has one. A slot-correction line ("[There was an error with the
# number of your available spell slots ...]") appears once and is
# ignored (#136).
_APPRENTICE = re.compile(
    r"From your apprenticeship you remember practicing with the (?P<list>.+?) spells?\."
)
_CHAPTER = re.compile(
    r'In the chapter entitled "(?P<chapter>[^"]+)", you have notes on the '
    r"(?P<list>.+?) spells?\."
)
_CANTRIPS = re.compile(r"^(?P<group>[A-Za-z-]+ Cantrips):\s+(?P<list>.+?)\.\s*$", re.M)
_CANTRIP = re.compile(r'(?P<name>[^,]+?) \(keyword: "(?P<keyword>[^"]+)"\)')
_FEATS = re.compile(r"proficiency with the magic feats? of (?P<list>.+?)\.")
_SLOTS = re.compile(r"You have (?P<slots>\d+) spell slots? available")
_SPELL_ITEM = re.compile(r"^(?P<name>.+?)(?:\s+\[(?P<abbrev>[^\]]+)\])?$")


def _split_list(text):
    """ "A, B [b], and C" / "A and B" / "A" into the items."""
    items = []
    for chunk in re.split(r",\s*", text):
        for part in re.split(r"\s+and\s+", chunk):
            part = re.sub(r"^and\s+", "", part.strip())  # the Oxford ", and"
            if part:
                items.append(part)
    return items


def parse_spells(text):
    """{"spells": [{name, abbrev, kind, chapter}], "slots": int | None}
    out of SPELL's answer. kind is "apprentice", "learned", "cantrip"
    or "feat" — the four things the output keeps apart; a cantrip's
    abbrev is its keyword. An unanswered SPELL parses to no spells and
    slots None."""
    spells = []
    for match in _APPRENTICE.finditer(text):
        for item in _split_list(match.group("list")):
            spells.append(_spell_row(item, "apprentice", None))
    for match in _CHAPTER.finditer(text):
        for item in _split_list(match.group("list")):
            spells.append(_spell_row(item, "learned", match.group("chapter")))
    for match in _CANTRIPS.finditer(text):
        for cantrip in _CANTRIP.finditer(match.group("list")):
            spells.append(
                {
                    "name": cantrip.group("name").strip(),
                    "abbrev": cantrip.group("keyword"),
                    "kind": "cantrip",
                    "chapter": match.group("group"),
                }
            )
    feats = _FEATS.search(text)
    if feats:
        for item in _split_list(feats.group("list")):
            spells.append(
                {"name": item, "abbrev": None, "kind": "feat", "chapter": None}
            )
    slots = _SLOTS.search(text)
    return {"spells": spells, "slots": int(slots.group("slots")) if slots else None}


def _spell_row(item, kind, chapter):
    match = _SPELL_ITEM.match(item)
    return {
        "name": match.group("name").strip(),
        "abbrev": match.group("abbrev"),
        "kind": kind,
        "chapter": chapter,
    }


def parse_exp_all(text):
    """The full roster from EXP ALL: {skill: (rank, percent)}."""
    return {
        skill.strip(): (int(rank), int(percent))
        for skill, rank, percent in _SKILL.findall(text)
        if skill.strip() != "SKILL"
    }


def parse_roster(text):
    """Every EXP ALL row as the parser's exp-window entry: {skill:
    {"rank", "percent", "mindstate", "rate"}}, the skill spelled as the
    game prints it ("Parry Ability"). The exp window only pushes the
    skills that are learning, so this is the one listing that names
    them all (the operator's design, 2026-09-23)."""
    roster = {}
    for skill, rank, percent, rate, mindstate in _ROSTER.findall(text):
        name = skill.strip()
        if name == "SKILL":
            continue
        value = int(mindstate)
        roster[name] = {
            "rank": int(rank),
            "percent": int(percent),
            "mindstate": value,
            "rate": rate.strip() or LEARNING_RATES[min(value, 34)],
        }
    return roster


def seed_experience(state, roster):
    """The parser's exp table filled from the roster: a skill the window
    has not pushed gets the roster's entry, one it has keeps the
    window's (live, and newer than the answer). The names seeded, for
    the echo. A script that starts on a cleared skill then reads 0/34
    and the rank instead of asking EXP and seeding its own spelling
    (#295)."""
    if state is None or not roster:
        return []
    table = dict(getattr(state, "experience", None) or {})
    seeded = []
    for skill, entry in roster.items():
        if skill in table:
            continue
        table[skill] = dict(entry)
        seeded.append(skill)
    if seeded:
        state.experience = table
        state.exp_updated = True
    return seeded


def parse_exp_answer(text):
    """Everything the snapshot takes from EXP ALL: the roster and the
    rested-experience line."""
    return {
        "skills": parse_exp_all(text),
        "roster": parse_roster(text),
        "rested": parse_rested(text),
    }


def insert_snapshot(
    connection,
    character,
    logged_at,
    info,
    skills,
    items=None,
    rested=None,
    spells=None,
):
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
    connection.executemany(
        "INSERT INTO inventory"
        " (logged_at, character_name, container, item, quantity, depth,"
        " exist, container_exist)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                logged_at,
                character,
                row["container"],
                row["item"],
                row["quantity"],
                row["depth"],
                row.get("exist"),
                row.get("container_exist"),
            )
            for row in items or []
        ],
    )
    connection.executemany(
        "INSERT INTO spells"
        " (logged_at, character_name, name, abbrev, kind, chapter)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                logged_at,
                character,
                row["name"],
                row["abbrev"],
                row["kind"],
                row["chapter"],
            )
            for row in (spells or {}).get("spells", [])
        ],
    )
    connection.executemany(
        "INSERT INTO wealth (logged_at, character_name, kind, currency, copper)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (logged_at, character, kind, currency, copper)
            for kind, holdings in info.get("wealth", {}).items()
            for currency, copper in sorted(holdings.items())
        ],
    )
    # An unanswered INFO must leave no trace — an all-None character
    # row reads as data ("circle None") when it's really a gap (#65).
    if info["stats"] or any(
        info[key] is not None for key in ("circle", "tdps", "favors")
    ):
        rested = rested or {}
        connection.execute(
            "INSERT INTO character"
            " (logged_at, character_name, circle, tdps, favors, guild,"
            "  race, gender, birth_year, birth_day, birth_month,"
            "  rexp_stored, rexp_usable, rexp_refresh, spell_slots)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                logged_at,
                character,
                info["circle"],
                info["tdps"],
                info["favors"],
                info["guild"],
                info.get("race"),
                info.get("gender"),
                info.get("birth_year"),
                info.get("birth_day"),
                info.get("birth_month"),
                rested.get("stored"),
                rested.get("usable"),
                rested.get("refresh"),
                (spells or {}).get("slots"),
            ),
        )
    connection.commit()


def blocked_by_renaming(text):
    """True when the answer is the renaming room's reminder rather than
    the command's own output — a refusal, not silence (#112)."""
    return RENAMING_ROOM in text


def refused(text):
    """True when the game answered with a refusal — the renaming room's
    reminder (#112) or the INVENTORY syntax help (#127) — so re-asking
    can only collect the same text again."""
    return blocked_by_renaming(text) or INVENTORY_HELP in text


def ask(s, command, parse, until, answered, attempts=ATTEMPTS):
    """(parsed, blocked) — parse() of the command's answer, re-asking up
    to ATTEMPTS times: a command sent while login noise is still
    settling can go unanswered entirely (captured 2026-08-22 — a
    session-start INFO never answered while the following EXP ALL was,
    storing an all-None character row, #65).

    A refusal stops the retries immediately: the renaming room answers
    everything with the same reminder (#112), and an inventory command
    the game does not know gets the INVENTORY syntax list (#127) — the
    next ask would only collect the same text. An answer carrying
    `until` counts as answered even if it parses to nothing, so an
    untrained character's legitimately empty EXP ALL is not mistaken
    for silence (#113)."""
    result = parse("")
    for attempt in range(attempts):
        if attempt:
            s.sleep(RETRY_SLEEP)
        s.put(command)
        answer = collect(s, COLLECT_SECONDS, until)
        if refused(answer):
            return result, True
        result = parse(answer)
        # The end marker is proof the game replied, even when nothing
        # parsed out of the reply: an untrained character's EXP ALL is
        # a complete answer reading "Total Ranks Displayed: 0", and
        # re-asking it can only ever return the same emptiness (#113).
        if answered(result) or (until is not None and until in answer):
            break
    return result, False


def snapshot(s, inventory=False):
    info, _ = ask(s, "info", parse_info, INFO_END, lambda r: bool(r["stats"]))
    exp, renaming = ask(
        s, "exp all", parse_exp_answer, EXP_ALL_END, lambda r: bool(r["skills"])
    )
    skills, rested = exp["skills"], exp["rested"]
    # The parser's exp table learns every skill the window does not
    # push, under the game's spelling, so scripts never seed their own.
    seeded = seed_experience(getattr(s, "state", None), exp.get("roster") or {})
    if seeded:
        s.echo(
            f"sheet: {len(seeded)} skill(s) the exp window does not show seeded from EXP ALL"
        )
    # SPELL costs no roundtime, so it joins the schedule (#136); the
    # renaming room refuses it like everything else.
    spells = {"spells": [], "slots": None}
    if not renaming:
        spells, _ = ask(
            s,
            "spell",
            parse_spells,
            SPELL_END,
            lambda r: r["slots"] is not None or bool(r["spells"]),
            attempts=1,  # cheap and optional: the next snapshot catches a miss
        )
    # Only when asked for: INV LIST costs 4-5s of roundtime, so it is
    # never part of the scheduled snapshot (#117). The renaming room
    # refuses it like everything else, so it is skipped there (#112).
    items = []
    if inventory and not renaming:
        if s.state is not None:
            s.state.possessions_updated = False
        items, refused_inv = ask(s, "inv list", parse_inventory, INV_END, bool)
        # The parser saw the same listing with its links (#184): its
        # rows carry the exist ids, one row per item, twins apart.
        if getattr(s.state, "possessions_updated", False):
            items = possessions.rows(s.state.possessions) or items
        if refused_inv:
            s.echo(
                "sheet: the game answered INV LIST with its syntax help — "
                "inventory skipped"
            )
    if renaming:
        s.echo(
            "sheet: EXP ALL is unavailable in the renaming room — stats "
            "stored, skills skipped until the character is renamed "
            "(CHECK IN, option 1)"
        )
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
            items,
            rested,
            spells,
        )
    finally:
        connection.close()
    if not info["stats"]:
        s.echo(
            f"sheet: INFO went unanswered — snapshot for {character} "
            f"has {len(skills)} skills only"
        )
        return
    known = [row for row in spells["spells"] if row["kind"] != "feat"]
    slots = spells["slots"]
    s.echo(
        f"sheet: snapshot for {character} — {len(info['stats'])} stats, "
        f"{len(skills)} skills, circle {info['circle']}, {info['tdps']} TDPs, "
        f"{len(known)} spells"
        + (f", {slots} slot(s) free" if slots is not None else "")
    )


def info_snapshot(s):
    """INFO alone into history.db: the stats, circle, TDPs, favors and
    purse, no skills, spells or inventory (#303)."""
    info, _ = ask(s, "info", parse_info, INFO_END, lambda r: bool(r["stats"]))
    if not info["stats"]:
        s.echo("sheet: INFO went unanswered — nothing stored")
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
            connection, character, datetime.now(timezone.utc).isoformat(), info, {}
        )
    finally:
        connection.close()
    s.echo(
        f"sheet: INFO for {character} — {len(info['stats'])} stats, {info['tdps']} TDPs"
    )


def serve(s, request):
    """A line typed at the running script — `;sheet inv` / `;sheet once`
    while the autostart is up lands here, not in s.args (#122): the
    engine hands a running script the rest of the line as a command."""
    words = request.lower().split()
    if "info" in words:
        if s.dead:
            s.echo("sheet: you are a ghost — the sheet can wait")
            return
        info_snapshot(s)
        return
    if "inv" in words or "once" in words:
        if s.dead:
            s.echo("sheet: you are a ghost — the sheet can wait")
            return
        snapshot(s, inventory="inv" in words)
        return
    s.echo(
        f"sheet: unknown request {request!r} — ;sheet inv snapshots the "
        "inventory too, ;sheet once takes a plain snapshot now, ;sheet "
        "info records INFO alone"
    )


def main(s):
    args = [str(arg).lower() for arg in (s.args or [])]
    if "info" in args:
        info_snapshot(s)
        return
    inventory = "inv" in args
    # `inv` is a request, not a schedule: take the snapshot and stop.
    once = inventory or "once" in args
    # The first snapshot of a run — the login, for the autostart —
    # takes the inventory too: the character is safe at login and the
    # possessions are wanted from the first minute (the operator,
    # 2026-09-20); the scheduled snapshots after it stay plain.
    first = True
    while True:
        if s.dead:
            # A ghost answers INFO with a warning, not a sheet — the
            # re-ask loop was interrogating corpses (#93). Defer.
            s.echo("sheet: you are a ghost — the sheet can wait")
            if once:
                return
            s.sleep(60)  # check again once breathing resumes
            continue
        snapshot(s, inventory=inventory or first)
        first = False
        if once:
            return
        # Until the next scheduled snapshot, listen instead of sleeping:
        # the sheet autostarts in every session, so `;sheet inv` always
        # meets a running script and arrives as a request (#122).
        deadline = time.monotonic() + INTERVAL
        while (remaining := deadline - time.monotonic()) > 0:
            request = s.command(timeout=remaining)
            if request is None:
                break  # the interval ran out
            serve(s, request)
