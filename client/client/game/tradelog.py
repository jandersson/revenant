"""Every caravan contract, from the minister to the pay — ;trade's log in
history.db (the operator, 2026-10-15: "Create a database to track the
trading contracts").

One `contracts` row per contract: when the minister issued it, the
character, the town it came from and the one it goes to, the goods, the
wholesale price and the dues charged at the issue, the contract's own
estimate of its worth on delivery, the coin, and its province: Zoluren,
Ilithi or Therengia, or Interprovince when the destination is in another
province (filled in for the rows logged before the column). The clerk's loading
adds the transport fee; the delivery fills `delivered_at` and `paid`.
`summary` reads the rows back per route for ;trade history: count,
delivered, the pay, the cost (wholesale, dues and fee) and the minutes
from issue to pay, the money in Kronars (the pay in the contract's own
coin, the cost in the origin's, at money.KRONAR_RATES). `leg_minutes` is
each route's shortest delivered contract, ;trade circuit's measure of a
leg. A logging failure is logged and never stops a script.
"""

import logging
import sqlite3
from datetime import datetime, timezone

from client.game import money, trade

SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    issued_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    goods TEXT NOT NULL,
    wholesale INTEGER,
    dues INTEGER,
    worth INTEGER,
    currency TEXT,
    fee INTEGER,
    delivered_at TEXT,
    paid INTEGER,
    province TEXT
)
"""


def _home(town):
    if town in trade.ILITHI:
        return "Ilithi"
    if town in trade.THERENGIA:
        return "Therengia"
    if town in trade.FORFEDHDAR:
        return "Forfedhdar"
    return "Zoluren" if town in trade.TOWNS else None


def province(origin, destination):
    """A contract's province: its origin's, Zoluren, Ilithi or Therengia,
    or "Interprovince" when the destination is in another province; None
    for an origin ;trade does not know."""
    home = _home(origin)
    if home is None:
        return None
    return home if _home(destination) == home else "Interprovince"


def _connect(path):
    from client.game.lootlog import db_path

    connection = sqlite3.connect(str(db_path(path)))
    connection.execute(SCHEMA)
    present = {row[1] for row in connection.execute("PRAGMA table_info(contracts)")}
    if "province" not in present:
        connection.execute("ALTER TABLE contracts ADD COLUMN province TEXT")
        rows = connection.execute("SELECT seq, origin, destination FROM contracts")
        connection.executemany(
            "UPDATE contracts SET province = ? WHERE seq = ?",
            [(province(origin, to), seq) for seq, origin, to in rows.fetchall()],
        )
        connection.commit()
    return connection


def now():
    return datetime.now(timezone.utc).isoformat()


def _write(sql, values, path):
    try:
        connection = _connect(path)
        try:
            cursor = connection.execute(sql, values)
            connection.commit()
            return cursor.lastrowid
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("contract log failed")
        return None


def log_issue(character, origin, contract, wholesale=None, dues=None, path=None):
    """One row for a contract the minister issued (`contract` is
    trade.contract's reading); the seq, or None when the write failed.
    A contract already logged and open (one READ back after a stop
    between the minister and the clerk) keeps its row: one per town."""
    open_row = _open_seq(character, origin, contract, path)
    if open_row is not None:
        return open_row
    return _write(
        "INSERT INTO contracts (issued_at, character_name, origin, destination,"
        " goods, wholesale, dues, worth, currency, province)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            now(),
            character or "unknown",
            origin,
            contract.destination,
            contract.goods,
            wholesale,
            dues,
            contract.worth,
            contract.currency,
            province(origin, contract.destination),
        ),
        path,
    )


def _open_seq(character, origin, contract, path=None):
    """The seq of an undelivered row for this contract, or None."""
    try:
        connection = _connect(path)
    except sqlite3.Error:
        return None
    try:
        row = connection.execute(
            "SELECT seq FROM contracts WHERE character_name = ? AND origin = ?"
            " AND destination = ? AND goods = ? AND delivered_at IS NULL"
            " ORDER BY seq DESC LIMIT 1",
            (character or "unknown", origin, contract.destination, contract.goods),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    return row[0] if row else None


def log_fee(seq, fee, path=None):
    """The clerk's transport fee for the crate, on the contract's row."""
    if seq is not None and fee is not None:
        _write("UPDATE contracts SET fee = ? WHERE seq = ?", (fee, seq), path)


def log_delivery(character, destination, paid, path=None):
    """The pay on the oldest undelivered row of the character's for
    `destination`: a contract read back after a restart is found by its
    town, no seq kept. Nothing when no row is open (a contract issued
    before the table)."""
    return _write(
        "UPDATE contracts SET delivered_at = ?, paid = ? WHERE seq = ("
        "SELECT seq FROM contracts WHERE character_name = ? AND destination = ?"
        " AND delivered_at IS NULL ORDER BY seq LIMIT 1)",
        (now(), paid, character or "unknown", destination),
        path,
    )


def _minutes(start, end):
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    except (TypeError, ValueError):
        return None
    return delta.total_seconds() / 60


def leg_minutes(character=None, path=None):
    """{(origin, destination): minutes}: the shortest issue-to-pay time
    of a delivered contract per route — the direct leg's, which a crate
    carried along a circuit (#556) can only lengthen."""
    connection = _connect(path)
    try:
        rows = connection.execute(
            "SELECT origin, destination, issued_at, delivered_at FROM contracts"
            " WHERE delivered_at IS NOT NULL"
            + (" AND character_name = ?" if character else ""),
            (character,) if character else (),
        ).fetchall()
    finally:
        connection.close()
    legs = {}
    for origin, destination, issued, delivered in rows:
        minutes = _minutes(issued, delivered)
        if minutes is not None:
            key = (origin, destination)
            legs[key] = min(minutes, legs.get(key, minutes))
    return legs


def summary(character=None, path=None):
    """Per route, the most run first: {"origin", "destination",
    "contracts", "delivered", "paid", "cost" (wholesale, dues and fee of
    the delivered ones), "profit", "minutes" (issue to pay, the
    delivered ones' mean, None with none)}; the money in copper Kronars."""
    connection = _connect(path)
    try:
        rows = connection.execute(
            "SELECT origin, destination, wholesale, dues, fee, paid, currency,"
            " issued_at, delivered_at FROM contracts"
            + (" WHERE character_name = ?" if character else ""),
            (character,) if character else (),
        ).fetchall()
    finally:
        connection.close()
    routes = {}
    for (
        origin,
        destination,
        wholesale,
        dues,
        fee,
        paid,
        coin,
        issued,
        delivered,
    ) in rows:
        route = routes.setdefault(
            (origin, destination),
            {
                "origin": origin,
                "destination": destination,
                "contracts": 0,
                "delivered": 0,
                "paid": 0,
                "cost": 0,
                "minutes": [],
            },
        )
        route["contracts"] += 1
        if delivered is None:
            continue
        route["delivered"] += 1
        # The contract's own coin: a broker's for Riverhaven pays Lirums.
        route["paid"] += money.in_kronars(paid, coin or trade.coin(destination))
        route["cost"] += money.in_kronars(
            (wholesale or 0) + (dues or 0) + (fee or 0), trade.coin(origin)
        )
        minutes = _minutes(issued, delivered)
        if minutes is not None:
            route["minutes"].append(minutes)
    out = []
    for route in routes.values():
        times = route.pop("minutes")
        route["profit"] = route["paid"] - route["cost"]
        route["minutes"] = sum(times) / len(times) if times else None
        out.append(route)
    return sorted(out, key=lambda route: (-route["contracts"], route["origin"]))


def describe(route):
    """One ;trade history line: "Crossing → Wolf Clan: 3 contracts, 3
    delivered, paid 35,373, profit 21,657 Kronars, 8 min each"."""
    line = (
        f"{route['origin']} → {route['destination']}: {route['contracts']}"
        f" contract{'s' if route['contracts'] != 1 else ''},"
        f" {route['delivered']} delivered"
    )
    if route["delivered"]:
        line += f", paid {route['paid']:,}, profit {route['profit']:,} Kronars"
    if route["minutes"] is not None:
        line += f", {route['minutes']:.0f} min each"
    return line
