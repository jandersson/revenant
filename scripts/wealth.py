"""Track your money: the BANK ACCOUNT report now and every few hours:  ;wealth

    ;wealth          (autostarts) ask BANK ACCOUNT after login and every 3 hours,
                     log every branch, and keep listening for tellers
    ;wealth now      ask again now — typed at the running script, or from cold
                     for one report and out

BANK ACCOUNT works from anywhere: a local runs to the Estate Holders'
Council and comes back with a slip listing every branch (captured
2026-09-12, "You flag down a local you know works with the Estate
Holders' Council ..."); the option is free on a Premium account and an
urchin-runner (SimuCoins) service otherwise, so a silent answer is
reported as such and not retried until the next interval. Each branch
line becomes a `bank` wealth row in ~/.revenant/history.db (the branch
in the `bank` column, the report's own copper total as the amount; its
Totals block is skipped, the branches add up to it), and the report is
echoed as a summary per currency: on deposit, carried and owed as
;sheet last recorded them from INFO, and the net. A teller's balance
line ("Your current balance is ...", "As expected, there are ...")
heard in passing is logged the same way. The beholder Wealth view
reads the table, newest row per item. Stop with:  ;stop wealth;
REVENANT_NO_WEALTH=1 or the Settings dialog turns the autostart off.

Balance grammar per lich's common-money (amounts like "1 platinum,
3 gold, 5 silver and 2 copper" convert at 10000/1000/100/10/1).
"""

import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from client.game.history import database_path as history_database_path
from client.game.money import phrase, to_copper

INTERVAL = 3 * 3600  # seconds between BANK ACCOUNT asks
START_DELAY = 20  # seconds after the start before the first ask: login noise
REPORT_WAIT = 20  # seconds a report gets to arrive before it counts as none
REPORT_SETTLE = 3  # seconds of silence after a branch line that end a report
NO_REPORT = (
    "bank account gave no report — the ACCOUNT option is free on a Premium "
    "account and an urchin-runner service otherwise"
)
clock = time.monotonic  # tests replace it

_BALANCE = re.compile(
    r"(?:current balance is|As expected, there are) "
    r"(?P<amounts>.+?) (?P<currency>Kronars?|Lirums?|Dokoras?)\b"
)
# A branch line of the BANK ACCOUNT report: name, the copper total,
# a bar, the denominations, the currency last. The Totals block's
# lines end in a denomination, not a currency, so they never match.
_DEPOSIT = re.compile(
    r"^\s*(?P<bank>[A-Za-z][A-Za-z' \-]*?):\s+(?P<copper>\d+)\s*\|\s.*?"
    r"\b(?P<currency>Kronars|Lirums|Dokoras)\s*$"
)
_REPORT_END = re.compile(r"You have \d+ open bank accounts?")


def parse_balance(line):
    """(currency, copper) from a teller's balance line, or None."""
    match = _BALANCE.search(line)
    if not match:
        return None
    total = to_copper(match.group("amounts"))
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


def latest_carried_and_debt(connection, character):
    """{(kind, currency): copper} — the newest carried and debt rows
    ;sheet logged from INFO, per currency."""
    ensure_schema(connection)
    latest = {}
    for kind, currency, copper in connection.execute(
        "SELECT kind, currency, copper FROM wealth"
        " WHERE character_name = ? AND kind IN ('carried', 'debt')"
        " ORDER BY logged_at, seq",
        (character,),
    ):
        latest[(kind, currency)] = copper
    return latest


def summary(report, held):
    """Lines per currency: on deposit (branches), carried, owed, net.
    report is {(bank, currency): copper}; held is latest_carried_and_debt's."""
    lines = []
    currencies = sorted({c for _, c in report} | {c for _, c in held})
    for currency in currencies:
        branches = {b: v for (b, c), v in report.items() if c == currency}
        deposited = sum(branches.values())
        carried = held.get(("carried", currency), 0)
        owed = held.get(("debt", currency), 0)
        where = ", ".join(f"{b} {phrase(v)}" for b, v in sorted(branches.items()))
        lines.append(
            f"{currency}: on deposit {phrase(deposited)}"
            + (f" ({where})" if len(branches) > 1 else "")
            + f", carrying {phrase(carried)}, owing {phrase(owed)}"
            f" — net {phrase(deposited + carried - owed)}"
        )
    return lines


def main(s):
    character = (
        (s.state.name if s.state else None)
        or os.environ.get("REVENANT_CHARACTER")
        or "unknown"
    )
    once = "now" in [str(arg).lower() for arg in (s.args or [])]
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    if not once:
        s.echo(
            "tracking money — BANK ACCOUNT now and every 3 hours, tellers "
            "overheard; ;wealth now asks again, ;stop wealth stops"
        )
    next_ask = clock() + (0 if once else START_DELAY)
    asked_at = None  # when the last BANK ACCOUNT went out, until answered
    report, report_stamp, last_branch_at = {}, None, None

    def finish():
        nonlocal asked_at, report, report_stamp, last_branch_at
        for line in summary(report, latest_carried_and_debt(connection, character)):
            s.echo(f"wealth: {line}")
        asked_at, report, report_stamp, last_branch_at = None, {}, None, None

    try:
        while True:
            request = s.command(timeout=0)
            if request is not None and "now" in request.lower():
                next_ask = clock()
            if clock() >= next_ask:
                s.put("bank account")
                asked_at, next_ask = clock(), clock() + INTERVAL
                report, report_stamp = {}, None
            line = s.get(timeout=1)
            if line is None:
                if (
                    report
                    and last_branch_at
                    and clock() - last_branch_at > REPORT_SETTLE
                ):
                    finish()
                    if once:
                        return
                elif asked_at and not report and clock() - asked_at > REPORT_WAIT:
                    s.echo(f"wealth: {NO_REPORT}")
                    asked_at = None
                    if once:
                        return
                continue
            balance = parse_balance(line)
            if balance is not None:
                currency, copper = balance
                record(connection, character, currency, copper)
                s.echo(f"bank balance noted: {phrase(copper, currency)}")
                continue
            if "on deposit" in line:
                report_stamp = datetime.now(timezone.utc).isoformat()
                continue
            deposit = parse_deposit(line)
            if deposit is not None:
                bank, currency, copper = deposit
                record(
                    connection,
                    character,
                    currency,
                    copper,
                    bank=bank,
                    logged_at=report_stamp,
                )
                report[(bank, currency)] = copper
                last_branch_at = clock()
                continue
            if report and _REPORT_END.search(line):
                finish()
                if once:
                    return
    finally:
        connection.close()
