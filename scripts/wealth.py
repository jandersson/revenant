"""Log your bank balances whenever the game states them:  ;wealth

A passive listener for two things banks say. A teller's balance line
("Your current balance is ...", "As expected, there are ...") becomes
a `bank` wealth row in ~/.revenant/history.db. The BANK ACCOUNT
report — the runner's slip listing every branch, captured 2026-09-12:

            Crossing:     3373173 | 337 platinum, 3 gold, 1 silver, 7 bronze, and 3 copper Kronars
               Dirge:        5082 | 5 gold, 8 bronze, and 2 copper Kronars

— becomes one `bank` row per branch, the branch in the `bank` column,
the report's own copper total as the amount (its Totals block, per
currency, is skipped: the branches add up to it). The same table
;sheet fills with carried coin and debt, and the beholder Wealth view
reads, newest row per item. Purely observational: it never sends a
command, so it is safe dead or alive. Stop with:  ;stop wealth

Balance grammar per lich's common-money (amounts like "1 platinum,
3 gold, 5 silver and 2 copper" convert at 10000/1000/100/10/1).
"""

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from client.game.history import database_path as history_database_path

COPPER_PER = {
    "platinum": 10_000,
    "gold": 1_000,
    "silver": 100,
    "bronze": 10,
    "copper": 1,
}

_BALANCE = re.compile(
    r"(?:current balance is|As expected, there are) "
    r"(?P<amounts>.+?) (?P<currency>Kronars?|Lirums?|Dokoras?)\b"
)
_AMOUNT = re.compile(
    r"(?P<count>[\d,]+)\s+(?P<denomination>platinum|gold|silver|bronze|copper)"
)
# A branch line of the BANK ACCOUNT report: name, the copper total,
# a bar, the denominations, the currency last. The Totals block's
# lines end in a denomination, not a currency, so they never match.
_DEPOSIT = re.compile(
    r"^\s*(?P<bank>[A-Za-z][A-Za-z' \-]*?):\s+(?P<copper>\d+)\s*\|\s.*?"
    r"\b(?P<currency>Kronars|Lirums|Dokoras)\s*$"
)


def parse_balance(line):
    """(currency, copper) from a teller's balance line, or None."""
    match = _BALANCE.search(line)
    if not match:
        return None
    total = 0
    for amount in _AMOUNT.finditer(match.group("amounts")):
        count = int(amount.group("count").replace(",", ""))
        total += count * COPPER_PER[amount.group("denomination")]
    currency = match.group("currency")
    if not currency.endswith("s"):
        currency += "s"
    return currency, total


def parse_deposit(line):
    """(bank, currency, copper) from a BANK ACCOUNT branch line, or None."""
    match = _DEPOSIT.match(line)
    if not match:
        return None
    return (
        match.group("bank").strip(),
        match.group("currency"),
        int(match.group("copper")),
    )


def database_path() -> Path:
    """~/.revenant/history.db (once history.db; client/game/history.py migrates)."""
    return history_database_path()


SCHEMA = """
CREATE TABLE IF NOT EXISTS wealth (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    currency TEXT NOT NULL,
    copper INTEGER NOT NULL,
    bank TEXT
)
"""


def ensure_schema(connection):
    """The table, and the `bank` column on a table from before it."""
    connection.execute(SCHEMA)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(wealth)")}
    if "bank" not in columns:
        connection.execute("ALTER TABLE wealth ADD COLUMN bank TEXT")
    connection.commit()


def record(connection, character, currency, copper, bank=None, logged_at=None):
    """One `bank` row; a report's branches share a logged_at."""
    ensure_schema(connection)
    connection.execute(
        "INSERT INTO wealth (logged_at, character_name, kind, currency, copper, bank)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            logged_at or datetime.now(timezone.utc).isoformat(),
            character,
            "bank",
            currency,
            copper,
            bank,
        ),
    )
    connection.commit()


def main(s):
    character = (
        (s.state.name if s.state else None)
        or os.environ.get("REVENANT_CHARACTER")
        or "unknown"
    )
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    s.echo("listening for bank balances — ;stop wealth to stop")
    report_stamp = None  # one stamp for every branch of one report
    try:
        while True:
            line = s.get(timeout=5)
            if line is None:
                report_stamp = None
                continue
            balance = parse_balance(line)
            if balance is not None:
                currency, copper = balance
                record(connection, character, currency, copper)
                s.echo(f"bank balance noted: {copper} copper {currency}")
                continue
            deposit = parse_deposit(line)
            if deposit is None:
                if "on deposit" in line:
                    report_stamp = datetime.now(timezone.utc).isoformat()
                continue
            bank, currency, copper = deposit
            record(
                connection,
                character,
                currency,
                copper,
                bank=bank,
                logged_at=report_stamp,
            )
            s.echo(f"bank balance noted: {bank} {copper} copper {currency}")
    finally:
        connection.close()
