"""Queries over the experience history the ;xp script logs to history.db.

The database is written by scripts/xp.py: one `mindstate` row per
learning skill per minute (logged_at is ISO-8601 UTC, so text ordering
is time ordering). Everything here is stdlib sqlite3 — connections are
cheap, and Dash callbacks run on worker threads, so callers open a
fresh connection per request instead of sharing one.
"""

import os
import sqlite3
from pathlib import Path


def database_path() -> Path:
    """The history database, shared with the scripts that write it:
    ~/.revenant/history.db, once xp.db (#121). client/game/history.py owns the
    rule and the one-time rename; without the client package (a
    dashboard-only install) the same rule is applied here."""
    try:
        from client.game.history import database_path as shared
    except ImportError:  # pragma: no cover — the workspace always has it
        override = os.environ.get("REVENANT_HISTORY_DB") or os.environ.get(
            "REVENANT_XP_DB"
        )
        return Path(override or "~/.revenant/history.db").expanduser()
    return shared()


def connect(path=None):
    """Read-only: the dashboard must never create an empty history.db as a
    side effect of being opened before ;xp has ever run — a missing
    file raises OperationalError, which callers already treat as the
    no-history-yet state."""
    connection = sqlite3.connect(f"file:{path or database_path()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _sheet_roster(connection, character, logged_at):
    """One ;sheet snapshot's skills: {skill: (rank, percent)}."""
    return {
        row["skill_name"]: (row["rank"], row["percent"])
        for row in connection.execute(
            "SELECT skill_name, rank, percent FROM sheet_skills"
            " WHERE character_name = ? AND logged_at = ?",
            (character, logged_at),
        )
    }


def sheet_snapshot(connection, character):
    """The newest ;sheet roster for a character: (logged_at, circle,
    guild, {skill: (rank, percent)}), or None before any snapshot."""
    row = connection.execute(
        "SELECT max(logged_at) FROM sheet_skills WHERE character_name = ?",
        (character,),
    ).fetchone()
    if not row or row[0] is None:
        return None
    logged_at = row[0]
    ranks = _sheet_roster(connection, character, logged_at)
    circle, guild = None, None
    try:
        latest = connection.execute(
            "SELECT circle, guild FROM character WHERE character_name = ?"
            " AND circle IS NOT NULL ORDER BY logged_at DESC LIMIT 1",
            (character,),
        ).fetchone()
    except sqlite3.OperationalError:
        latest = None  # a db from before guild tracking
    if latest:
        circle, guild = latest["circle"], latest["guild"]
    return logged_at, circle, guild, ranks


def characters(connection):
    """Every character with any logged history, sorted by name.

    The union matters: `mindstate` is written by ;xp while a character
    trains, `character` by ;sheet at login. A character snapshotted but
    never trained has a full sheet and no mindstate row, and listing
    only the latter hid 20 of 30 characters from the picker — including
    the sheet data the Circle-gates view was built to show (#116).
    """
    names = set()
    for table in ("mindstate", "character"):
        # Either table may be absent: a database written before ;sheet
        # existed has no character table, and one from a fresh sweep may
        # have no mindstate yet. Whichever is there still answers.
        try:
            names.update(
                row["character_name"]
                for row in connection.execute(
                    f"SELECT DISTINCT character_name FROM {table}"  # noqa: S608
                )
            )
        except sqlite3.OperationalError:
            pass
    return sorted(names)


def identity(connection, character):
    """Who a character is, from the newest ;sheet snapshot: a dict of
    race, gender, guild, circle and the birth date, or None when the
    character has no sheet at all.

    Age is deliberately absent — it is the current Elanthian year minus
    birth_year, and the caller computes it so it cannot go stale (#115).
    Rows snapshotted before those columns existed carry NULLs.
    """
    try:
        row = connection.execute(
            "SELECT character_name, race, gender, guild, circle,"
            " birth_year, birth_day, birth_month, logged_at"
            " FROM character WHERE character_name = ?"
            " ORDER BY logged_at DESC LIMIT 1",
            (character,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None  # a db from before the identity columns
    return dict(row) if row else None


def spells(connection, character):
    """The newest SPELL snapshot's rows for a character: [{name, abbrev,
    kind, chapter}], feats included, and the spell slots left:
    ({"rows": [...], "slots": int | None}); empty before any (#136)."""
    empty = {"rows": [], "slots": None}
    try:
        latest = connection.execute(
            "SELECT max(logged_at) FROM spells WHERE character_name = ?",
            (character,),
        ).fetchone()[0]
        slots = connection.execute(
            "SELECT spell_slots FROM character WHERE character_name = ?"
            " AND spell_slots IS NOT NULL ORDER BY logged_at DESC LIMIT 1",
            (character,),
        ).fetchone()
    except sqlite3.OperationalError:
        return empty  # a database from before the spells table
    rows = []
    if latest:
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT name, abbrev, kind, chapter FROM spells"
                " WHERE character_name = ? AND logged_at = ?"
                " ORDER BY kind, chapter, name",
                (character, latest),
            )
        ]
    return {"rows": rows, "slots": slots[0] if slots else None}


def skills(connection, character):
    """Every skill a character has history for, sorted by name."""
    rows = connection.execute(
        "SELECT DISTINCT skill_name FROM mindstate"
        " WHERE character_name = ? ORDER BY skill_name",
        (character,),
    )
    return [row["skill_name"] for row in rows]


def latest_character(connection):
    """The most recently logged character, or None on an empty table —
    the dock view's fallback when no character is named."""
    # Training history first, then the newest sheet, so a freshly swept
    # database still opens on a character (#116). Either table may be
    # missing entirely.
    for table in ("mindstate", "character"):
        try:
            row = connection.execute(
                f"SELECT character_name FROM {table}"  # noqa: S608
                " ORDER BY logged_at DESC LIMIT 1"
            ).fetchone()
        except sqlite3.OperationalError:
            continue
        if row:
            return row["character_name"]
    return None


def _mindstate_series(rows):
    """Time-ordered mindstate rows grouped per skill: {skill: {"times":
    [...], "mindstate": [...], "rank": [...]}}."""
    series = {}
    for row in rows:
        points = series.setdefault(
            row["skill_name"], {"times": [], "mindstate": [], "rank": []}
        )
        points["times"].append(row["logged_at"])
        points["mindstate"].append(row["mindstate"])
        points["rank"].append(row["rank"])
    return series


def history_since(connection, character, since_iso):
    """Time series per skill from a cutoff onward — the dock's recent
    window. Same shape as history(); ISO-8601 UTC strings compare as
    time, so the cutoff is a plain string comparison."""
    return _mindstate_series(
        connection.execute(
            "SELECT skill_name, logged_at, mindstate, rank"
            "  FROM mindstate"
            " WHERE character_name = ? AND logged_at >= ?"
            " ORDER BY logged_at",
            (character, since_iso),
        )
    )


def latest_snapshot(connection, character):
    """The newest logged row per skill for a character — the learning
    queue as of the last ;xp tick, one dict per skill, sorted by name."""
    rows = connection.execute(
        "SELECT skill_name, rank, percent, mindstate, logged_at"
        "  FROM mindstate"
        " WHERE character_name = ?"
        "   AND logged_at = (SELECT max(logged_at) FROM mindstate"
        "                     WHERE character_name = ?)"
        " ORDER BY skill_name",
        (character, character),
    )
    return [dict(row) for row in rows]


def history(connection, character, skill_names):
    """Time series per skill: {skill: {"times": [...], "mindstate": [...],
    "rank": [...]}}, oldest first. Skills without history are absent."""
    if not skill_names:
        return {}
    placeholders = ", ".join("?" for _ in skill_names)
    return _mindstate_series(
        connection.execute(
            "SELECT skill_name, logged_at, mindstate, rank"
            "  FROM mindstate"
            " WHERE character_name = ?"
            f"   AND skill_name IN ({placeholders})"
            " ORDER BY logged_at",
            (character, *skill_names),
        )
    )


def sheet_with_deltas(connection, character):
    """The newest full roster with rank gained since the previous
    snapshot: (logged_at, [{skill_name, rank, percent, gained}]),
    sorted by skill. gained is None for a skill's first appearance —
    including everything in the very first snapshot. None before any
    snapshot at all."""
    times = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT logged_at FROM sheet_skills"
            " WHERE character_name = ? ORDER BY logged_at DESC LIMIT 2",
            (character,),
        )
    ]
    if not times:
        return None
    latest = _sheet_roster(connection, character, times[0])
    previous = _sheet_roster(connection, character, times[1]) if len(times) > 1 else {}
    rows = [
        {
            "skill_name": skill,
            "rank": rank,
            "percent": percent,
            "gained": (rank - previous[skill][0]) if skill in previous else None,
        }
        for skill, (rank, percent) in sorted(latest.items())
    ]
    return times[0], rows


def stats_with_deltas(connection, character):
    """The newest stats with change since the previous snapshot:
    (logged_at, [{stat, value, gained}]), or None before any."""
    times = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT logged_at FROM stats"
            " WHERE character_name = ? ORDER BY logged_at DESC LIMIT 2",
            (character,),
        )
    ]
    if not times:
        return None

    def values(logged_at):
        return {
            row["stat"]: row["value"]
            for row in connection.execute(
                "SELECT stat, value FROM stats"
                " WHERE character_name = ? AND logged_at = ?",
                (character, logged_at),
            )
        }

    latest = values(times[0])
    previous = values(times[1]) if len(times) > 1 else {}
    rows = [
        {
            "stat": stat,
            "value": value,
            "gained": (value - previous[stat]) if stat in previous else None,
        }
        for stat, value in sorted(latest.items())
    ]
    return times[0], rows


def sheet_history(connection, character):
    """Circle, TDPs and favors over time, from every ;sheet snapshot:
    {"times": [...], "circle": [...], "tdps": [...], "favors": [...]}."""
    history = {"times": [], "circle": [], "tdps": [], "favors": []}
    for row in connection.execute(
        "SELECT logged_at, circle, tdps, favors FROM character"
        " WHERE character_name = ? ORDER BY logged_at",
        (character,),
    ):
        history["times"].append(row["logged_at"])
        history["circle"].append(row["circle"])
        history["tdps"].append(row["tdps"])
        history["favors"].append(row["favors"])
    return history


XP_INTERVAL_SECONDS = 60  # ;xp's cadence: a flagged minute lasts this long
XP_GAP_SECONDS = 180  # flagged rows further apart than this are two runs


def rexp_history(connection, character):
    """Rested experience over time — every ;sheet snapshot that carried
    the EXP footer (#106) and every change ;xp logged to the rested
    table (#176), merged oldest first: {"times": [...], "stored":
    [...], "usable": [...], "refresh": [...]} in hours. Empty before
    either source exists or recorded the line."""
    history = {"times": [], "stored": [], "usable": [], "refresh": []}
    rows = []
    for query in (
        "SELECT logged_at, rexp_stored AS stored, rexp_usable AS usable,"
        " rexp_refresh AS refresh FROM character"
        " WHERE character_name = ? AND rexp_stored IS NOT NULL",
        "SELECT logged_at, stored, usable, refresh FROM rested"
        " WHERE character_name = ? AND stored IS NOT NULL",
    ):
        try:
            rows += [
                (row["logged_at"], row["stored"], row["usable"], row["refresh"])
                for row in connection.execute(query, (character,))
            ]
        except sqlite3.OperationalError:  # no such column or table: older data
            continue
    for logged_at, stored, usable, refresh in sorted(rows):
        history["times"].append(logged_at)
        history["stored"].append(stored / 60)
        history["usable"].append((usable or 0) / 60)
        history["refresh"].append((refresh or 0) / 60)
    return history


def rexp_windows(connection, character):
    """When the 3x conversion was open: [(start, end)] ISO pairs. Exact
    where ;xp flagged its rows (#176): each run of consecutive minutes
    logged with is_rexp set is one window, closing a minute after its
    last row; a row flagged 0 or a gap ends the run. Before the first
    flagged row, the older guess from the ;sheet snapshots (#106): a
    window per snapshot with usable hours, closing at the next
    snapshot or when the hours would have burnt out, whichever comes
    first — coarse, but it tells a rested run from an ordinary one."""
    exact = _flagged_windows(connection, character)
    first_flag = exact[0][0] if exact else None
    history = rexp_history(connection, character)
    windows = []
    times = history["times"]
    for index, start in enumerate(times):
        if first_flag is not None and start >= first_flag:
            break
        usable = history["usable"][index]
        if usable <= 0:
            continue
        burnt_out = _plus_hours(start, usable)
        following = times[index + 1] if index + 1 < len(times) else burnt_out
        end = min(following, burnt_out)
        if first_flag is not None:
            end = min(end, first_flag)
        windows.append((start, end))
    return windows + (exact or [])


def _flagged_windows(connection, character):
    """The runs of minutes ;xp flagged is_rexp, or None when the column
    or the flags do not exist yet (a database from before #176)."""
    try:
        rows = connection.execute(
            "SELECT DISTINCT logged_at, is_rexp FROM mindstate"
            " WHERE character_name = ? AND is_rexp IS NOT NULL"
            " ORDER BY logged_at",
            (character,),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None
    windows = []
    start = last = None
    for row in rows:
        moment = row["logged_at"]
        if row["is_rexp"] and start is not None:
            if _seconds_between(last, moment) <= XP_GAP_SECONDS:
                last = moment
                continue
            windows.append((start, _plus_seconds(last, XP_INTERVAL_SECONDS)))
            start = None
        if row["is_rexp"]:
            start = last = moment
        elif start is not None:
            windows.append((start, _plus_seconds(last, XP_INTERVAL_SECONDS)))
            start = None
    if start is not None:
        windows.append((start, _plus_seconds(last, XP_INTERVAL_SECONDS)))
    return windows


def _seconds_between(earlier, later):
    from datetime import datetime

    return (
        datetime.fromisoformat(later) - datetime.fromisoformat(earlier)
    ).total_seconds()


def _plus_seconds(iso, seconds):
    from datetime import datetime, timedelta

    return (datetime.fromisoformat(iso) + timedelta(seconds=seconds)).isoformat()


def _plus_hours(iso, hours):
    from datetime import datetime, timedelta

    moment = datetime.fromisoformat(iso)
    return (moment + timedelta(hours=hours)).isoformat()


def stats_history(connection, character):
    """Per-stat progression: {stat: {"times": [...], "values": [...]}}."""
    series = {}
    for row in connection.execute(
        "SELECT logged_at, stat, value FROM stats"
        " WHERE character_name = ? ORDER BY logged_at",
        (character,),
    ):
        points = series.setdefault(row["stat"], {"times": [], "values": []})
        points["times"].append(row["logged_at"])
        points["values"].append(row["value"])
    return series


def wealth_current(connection, character):
    """The newest known figure per item — (kind, currency, bank) — as
    (logged_at, [{kind, currency, copper, bank}]), carried coin first,
    debts after, then bank branches; logged_at is the newest of them.
    Items come from different moments (;sheet's INFO snapshot, a
    teller, the BANK ACCOUNT report ;wealth logs per branch), so the
    latest of each is the picture, not the latest single snapshot.
    None before any. A wealth table from before the bank column reads
    with bank None."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(wealth)")}
    bank = "bank" if "bank" in columns else "NULL AS bank"
    latest = {}
    for row in connection.execute(
        f"SELECT logged_at, kind, currency, copper, {bank} FROM wealth"
        " WHERE character_name = ? ORDER BY logged_at, seq",
        (character,),
    ):
        latest[(row["kind"], row["currency"], row["bank"])] = dict(row)
    if not latest:
        return None
    rows = sorted(
        latest.values(), key=lambda r: (r["kind"], r["currency"], r["bank"] or "")
    )
    logged_at = max(r["logged_at"] for r in rows)
    return logged_at, [
        {k: r[k] for k in ("kind", "currency", "copper", "bank")} for r in rows
    ]


def wealth_history(connection, character):
    """Carried copper over time, one series per currency:
    {currency: {"times": [...], "values": [...]}}. Debt excluded —
    it charts as its own story if it ever grows one."""
    series = {}
    for row in connection.execute(
        "SELECT logged_at, currency, copper FROM wealth"
        " WHERE character_name = ? AND kind = 'carried'"
        " ORDER BY logged_at",
        (character,),
    ):
        points = series.setdefault(row["currency"], {"times": [], "values": []})
        points["times"].append(row["logged_at"])
        points["values"].append(row["copper"])
    return series
