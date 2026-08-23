"""Log your bank balance whenever a teller states it:  ;wealth

A passive listener: banks only reveal balances at the teller, so this
watches the game text for the balance phrasings ("Your current balance
is ...", "As expected, there are ...") and records each sighting into
~/.revenant/xp.db as a `bank` wealth row — the same table ;sheet fills
with carried coin and debt, and the beholder Wealth view reads. Purely
observational: it never sends a command, so it is safe dead or alive.
Stop with:  ;stop wealth

Balance grammar per lich's common-money (amounts like "1 platinum,
3 gold, 5 silver and 2 copper" convert at 10000/1000/100/10/1).
"""

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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


def database_path() -> Path:
    return Path(os.environ.get("REVENANT_XP_DB", "~/.revenant/xp.db")).expanduser()


SCHEMA = """
CREATE TABLE IF NOT EXISTS wealth (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    currency TEXT NOT NULL,
    copper INTEGER NOT NULL
)
"""


def record(connection, character, currency, copper):
    connection.execute(SCHEMA)
    connection.execute(
        "INSERT INTO wealth (logged_at, character_name, kind, currency, copper)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            character,
            "bank",
            currency,
            copper,
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
    try:
        while True:
            line = s.get(timeout=5)
            if line is None:
                continue
            parsed = parse_balance(line)
            if parsed is None:
                continue
            currency, copper = parsed
            record(connection, character, currency, copper)
            s.echo(f"bank balance noted: {copper} copper {currency}")
    finally:
        connection.close()
