"""Every commodity board read and every commodity trade — ;commodities'
log in history.db (#557): watched over days, the boards say how fast a
pit's surplus drains and its prices drift.

`commodities`: one row per good per board read — the time, the
character, the pit's town, the good, its price and its stock word.
`commodity_trades`: one row per ORDER — the good, the units, the town
bought in, the price paid and the guild's cut, the town it is carried
to; the sale fills in where it sold, the pay and the time. The money is
copper Kronars. A logging failure is logged and never stops a script.
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS commodities (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    read_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    pit TEXT NOT NULL,
    good TEXT NOT NULL,
    price INTEGER NOT NULL,
    stock TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS commodity_trades (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name TEXT NOT NULL,
    good TEXT NOT NULL,
    units INTEGER NOT NULL,
    bought_at TEXT NOT NULL,
    bought_in TEXT NOT NULL,
    price INTEGER,
    cut INTEGER,
    sold_in TEXT,
    sold_at TEXT,
    sold_for INTEGER
);
"""
FRESH_HOURS = 6  # a board older than this is no plan's buyer


def _connect(path):
    from client.game.lootlog import db_path

    connection = sqlite3.connect(str(db_path(path)))
    connection.executescript(SCHEMA)
    return connection


def now():
    return datetime.now(timezone.utc).isoformat()


def _write(sql, rows, path):
    """`sql` once per row of `rows`; the last row's id, or None when the
    write failed (logged)."""
    try:
        connection = _connect(path)
        try:
            cursor = None
            for row in rows:
                cursor = connection.execute(sql, row)
            connection.commit()
            return cursor.lastrowid if cursor is not None else None
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("commodity log failed")
        return None


def log_board(character, board, path=None):
    """One row per good of a commodities.Board read now."""
    stamp = now()
    _write(
        "INSERT INTO commodities (read_at, character_name, pit, good, price, stock)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (stamp, character or "unknown", board.town, good, price, stock)
            for good, (price, stock) in board.goods.items()
        ],
        path,
    )


def latest(hours=FRESH_HOURS, path=None):
    """Each pit's last board read within `hours`: {town: (read_at,
    {good: (price, stock)})}."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    connection = _connect(path)
    try:
        rows = connection.execute(
            "SELECT c.pit, c.read_at, c.good, c.price, c.stock FROM commodities c"
            " JOIN (SELECT pit, MAX(read_at) AS last FROM commodities"
            " WHERE read_at >= ? GROUP BY pit) m"
            " ON c.pit = m.pit AND c.read_at = m.last",
            (since,),
        ).fetchall()
    finally:
        connection.close()
    out = {}
    for pit, read_at, good, price, stock in rows:
        out.setdefault(pit, (read_at, {}))[1][good] = (price, stock)
    return out


def log_buy(character, good, units, bought_in, price, cut, sold_in, path=None):
    """One row for an ORDER, `sold_in` the town it is carried to; the
    seq, or None when the write failed."""
    return _write(
        "INSERT INTO commodity_trades (character_name, good, units, bought_at,"
        " bought_in, price, cut, sold_in) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(character or "unknown", good, units, now(), bought_in, price, cut, sold_in)],
        path,
    )


def open_trade(character, path=None):
    """The character's oldest trade bought and not sold: (seq, good,
    units, bought_in, price, cut, sold_in), or None."""
    connection = _connect(path)
    try:
        return connection.execute(
            "SELECT seq, good, units, bought_in, price, cut, sold_in"
            " FROM commodity_trades WHERE character_name = ? AND sold_at IS NULL"
            " ORDER BY seq LIMIT 1",
            (character or "unknown",),
        ).fetchone()
    finally:
        connection.close()


def log_sale(seq, sold_in, sold_for, path=None):
    """The sale on trade `seq`: where, the pay, now."""
    if seq is not None:
        _write(
            "UPDATE commodity_trades SET sold_in = ?, sold_at = ?, sold_for = ?"
            " WHERE seq = ?",
            [(sold_in, now(), sold_for, seq)],
            path,
        )
