"""Work orders ledgered — the pay and the expenses of every order
;remedies work hands in, so the craft's profit is read off the data
(the operator, 2026-09-22: "track expenses and profit in work orders").

One row per order in history.db's `work_orders` table (beside `;xp`'s
mindstates and `;climbexp`'s climbs): the discipline and level, the
item and the stacks, the pay, and two costs. `cost` is what the order
consumed at the society's catalog prices — a stack of the controlling
herb per remedy, a piece of the second herb, a splash of water and a
catalyst each — the same whoever paid for it; `spent` is the coin that
left the purse while the order was open, which lands a ten-splash
water or a spare stack on the order that bought it. Profit is pay less
cost, cash flow pay less spent; over many orders the two converge.
Time is kept two ways: `minutes`, the order's wall clock from the
master's word to the pay (the walks and purchases in it), and
`crush_seconds`, the roundtime the crushes themselves cost — the
number that moves when better tools shorten the roundtime (the
operator, 2026-09-22), read as seconds a crush.
`;remedies ledger` prints the totals, the per-item averages and the
last orders. Rows are data for a human decision (which tier, which
item), never a trigger.
"""

import json
import sqlite3
from datetime import datetime, timezone

from client.game.remedies import CATALOG, CATALYST_CATALOG

SCHEMA = """
CREATE TABLE IF NOT EXISTS work_orders (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    discipline TEXT NOT NULL,
    level TEXT NOT NULL,
    item TEXT NOT NULL,
    stacks INTEGER NOT NULL,
    quality TEXT NOT NULL,
    earned INTEGER NOT NULL,
    cost INTEGER NOT NULL,
    spent INTEGER NOT NULL,
    crushes INTEGER,
    rank_before INTEGER,
    rank_after INTEGER,
    minutes INTEGER,
    crush_seconds INTEGER,
    extra TEXT NOT NULL
)
"""

COLUMNS = (
    "logged_at",
    "character_name",
    "discipline",
    "level",
    "item",
    "stacks",
    "quality",
    "earned",
    "cost",
    "spent",
    "crushes",
    "rank_before",
    "rank_after",
    "minutes",
    "crush_seconds",
    "extra",
)
# Columns added after the table first shipped, with their types, so
# a history.db from an earlier evening grows them in place.
ADDED = (("crush_seconds", "INTEGER"),)

STACK = 25  # pieces in a dried stack, one remedy
SPLASHES = 10  # splashes of water in a purchase
SHOWN = 5  # the last orders ;remedies ledger lists


def open_ledger(path):
    connection = sqlite3.connect(str(path))
    connection.execute(SCHEMA)
    present = {row[1] for row in connection.execute("PRAGMA table_info(work_orders)")}
    for column, kind in ADDED:
        if column not in present:
            connection.execute(f"ALTER TABLE work_orders ADD COLUMN {column} {kind}")
    connection.commit()
    return connection


def material_cost(spec, catalyst, catalog=CATALOG, catalyst_catalog=CATALYST_CATALOG):
    """What one remedy of `spec` consumes at the catalog's prices: the
    controlling herb's stack, one piece of the second herb, one splash
    of water and one catalyst — 390 Kronars for blister cream with a
    coal nugget. An unpriced herb or catalyst counts nothing."""
    chapter, page, herb, extra, noun = spec
    cost = catalog.get(herb, (0, 0))[1]
    if extra:
        cost += catalog.get(extra, (0, 0))[1] / STACK
    cost += catalog.get("water", (0, 0))[1] / SPLASHES
    cost += catalyst_catalog.get(catalyst or "", (0, 0))[1]
    return round(cost)


def record(connection, **fields):
    """One row; unknown keys go into `extra` as JSON. Returns the seq."""
    row = {column: None for column in COLUMNS}
    extra = {}
    for key, value in fields.items():
        if key in row:
            row[key] = value
        else:
            extra[key] = value
    row["logged_at"] = row["logged_at"] or datetime.now(timezone.utc).isoformat()
    row["extra"] = json.dumps(extra, sort_keys=True)
    row["quality"] = row["quality"] or ""
    cursor = connection.execute(
        f"INSERT INTO work_orders ({', '.join(COLUMNS)}) "
        f"VALUES ({', '.join('?' * len(COLUMNS))})",
        [row[column] for column in COLUMNS],
    )
    connection.commit()
    return cursor.lastrowid


def rows(connection, character=None, discipline=None):
    """The rows, oldest first, as dicts; filtered when asked."""
    clauses, values = [], []
    if character:
        clauses.append("character_name = ?")
        values.append(character)
    if discipline:
        clauses.append("discipline = ?")
        values.append(discipline)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    cursor = connection.execute(
        f"SELECT {', '.join(COLUMNS)} FROM work_orders{where} ORDER BY seq", values
    )
    return [dict(zip(COLUMNS, row)) for row in cursor.fetchall()]


def totals(entries):
    """{"orders", "earned", "cost", "spent", "profit", "cash", "crushes"}
    over the rows: profit is pay less materials, cash pay less coin
    spent."""
    earned = sum(entry["earned"] for entry in entries)
    cost = sum(entry["cost"] for entry in entries)
    spent = sum(entry["spent"] for entry in entries)
    return {
        "orders": len(entries),
        "earned": earned,
        "cost": cost,
        "spent": spent,
        "profit": earned - cost,
        "cash": earned - spent,
        "crushes": sum(entry["crushes"] or 0 for entry in entries),
        "crush_seconds": sum(entry.get("crush_seconds") or 0 for entry in entries),
        "minutes": sum(entry.get("minutes") or 0 for entry in entries),
    }


def ledger_lines(entries, shown=SHOWN):
    """The ;remedies ledger printout: the totals, one line per item
    and level with the average pay, cost and profit an order of it
    brought, and the last `shown` orders."""
    if not entries:
        return ["no work orders on record"]
    sums = totals(entries)
    lines = [
        f"{sums['orders']} order(s): {sums['earned']:,} Kronars paid, "
        f"{sums['cost']:,} in materials, {sums['profit']:,} profit; "
        f"{sums['spent']:,} spent from the purse, {sums['cash']:,} kept; "
        f"{sums['minutes']} min, {per_crush(sums['crush_seconds'], sums['crushes'])} a crush"
    ]
    groups = {}
    for entry in entries:
        groups.setdefault((entry["item"], entry["level"]), []).append(entry)
    for (item, level), group in sorted(groups.items()):
        count = len(group)
        pay = sum(entry["earned"] for entry in group) // count
        cost = sum(entry["cost"] for entry in group) // count
        stacks = sum(entry["stacks"] for entry in group)
        crushes = sum(entry["crushes"] or 0 for entry in group)
        seconds = sum(entry.get("crush_seconds") or 0 for entry in group)
        lines.append(
            f"{item} ({level}) x{count}, {stacks} stack(s): "
            f"{pay:,} pay, {cost:,} cost, {pay - cost:,} profit an order, "
            f"{per_crush(seconds, crushes)} a crush"
        )
    for entry in entries[-shown:]:
        lines.append(summarize(entry))
    return lines


def per_crush(seconds, crushes):
    """ "15 s" — the roundtime an average crush cost, "? s" unknown."""
    if not crushes or not seconds:
        return "? s"
    return f"{round(seconds / crushes)} s"


def summarize(entry):
    """One order on one line."""
    stamp = (entry["logged_at"] or "")[:16].replace("T", " ")
    ranks = ""
    if entry.get("rank_before") is not None and entry.get("rank_after") is not None:
        ranks = f", rank {entry['rank_before']}->{entry['rank_after']}"
    minutes = f", {entry['minutes']} min" if entry.get("minutes") is not None else ""
    crushing = ""
    if entry.get("crush_seconds"):
        crushing = (
            f" ({entry['crush_seconds']} s crushing, "
            f"{per_crush(entry['crush_seconds'], entry['crushes'])} each)"
        )
    return (
        f"{stamp} {entry['item']} x{entry['stacks']} ({entry['level']}): "
        f"paid {entry['earned']:,}, cost {entry['cost']:,}, spent {entry['spent']:,}, "
        f"{entry['crushes'] or 0} crush(es){crushing}{ranks}{minutes}"
    )
