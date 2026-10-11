"""Every task a giver offers, and how it ended — ;task's log in
history.db (the operator, 2026-10-11: "Start tracking what task givers
assign", after Cormyn's thirteen offers turned out to be three kinds,
every recovery from the same poloh'izh).

One `tasks` row per offer: when, the character, the giver, the kind
(delivery, recovery, searching, or what an uncaptured one read as), the
item, the creature, the area (a search's or a recovery's) or the place
(a delivery's town), the recipient, whether it was accepted, and the
offer's words. The end fills the same row: `done_at`, the pay as the
game counts it (`paid`, `currency`), and for a search the room it was
found in and the SEARCH that found it. `summary` reads the rows back per
giver and kind for ;task history. A logging failure is logged and never
stops a script. `scan` reads the same rows out of a game log's lines,
for tools/task_backfill.py: the offers made before the table (#527).
"""

import logging
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    offered_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    giver TEXT NOT NULL,
    kind TEXT NOT NULL,
    item TEXT NOT NULL,
    creature TEXT NOT NULL,
    area TEXT NOT NULL,
    person TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    text TEXT NOT NULL,
    done_at TEXT,
    paid INTEGER,
    currency TEXT,
    room INTEGER,
    searches INTEGER
)
"""
ENDS = ("done_at", "paid", "currency", "room", "searches")


def _connect(path):
    from client.game.lootlog import db_path

    connection = sqlite3.connect(str(db_path(path)))
    connection.execute(SCHEMA)
    return connection


def now():
    return datetime.now(timezone.utc).isoformat()


def log_offer(character, giver, offer, accepted, path=None, offered_at=None):
    """One row for an offer as ;task read it (at `offered_at`, an ISO
    time, for a backfill); the seq, or None when the write failed."""
    try:
        connection = _connect(path)
        try:
            cursor = connection.execute(
                "INSERT INTO tasks (offered_at, character_name, giver, kind, item,"
                " creature, area, person, accepted, text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    offered_at or now(),
                    character or "unknown",
                    str(giver or "").lower(),
                    str(offer.get("kind") or "unknown"),
                    str(offer.get("item") or ""),
                    str(offer.get("creature") or ""),
                    str(offer.get("area") or offer.get("place") or ""),
                    str(offer.get("person") or ""),
                    int(bool(accepted)),
                    str(offer.get("text") or ""),
                ),
            )
            connection.commit()
            return cursor.lastrowid
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("task log failed")
        return None


def log_end(seq, path=None, **fields):
    """Fill the row's end (ENDS): the pay, done_at, a search's room and
    count. Nothing for a task logged before the table (no seq)."""
    fields = {key: value for key, value in fields.items() if key in ENDS}
    if seq is None or not fields:
        return
    try:
        connection = _connect(path)
        try:
            connection.execute(
                f"UPDATE tasks SET {', '.join(f'{key} = ?' for key in fields)}"
                " WHERE seq = ?",
                [*fields.values(), seq],
            )
            connection.commit()
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("task log failed")


def summary(character=None, path=None):
    """Per giver and kind: {"giver", "kind", "offers", "accepted", "done",
    "where" (Counter of creature and area, or recipient and place), "paid"
    (the counts, one currency each: [(count, currency)]), "minutes" (offer
    to end, the done ones)}, the most offered first."""
    connection = _connect(path)
    try:
        query = (
            "SELECT giver, kind, creature, area, person, accepted, offered_at,"
            " done_at, paid, currency FROM tasks"
        )
        rows = connection.execute(
            query + (" WHERE character_name = ?" if character else ""),
            (character,) if character else (),
        ).fetchall()
    finally:
        connection.close()
    groups = {}
    for (
        giver,
        kind,
        creature,
        area,
        person,
        accepted,
        offered,
        done,
        paid,
        coin,
    ) in rows:
        group = groups.setdefault(
            (giver, kind),
            {
                "giver": giver,
                "kind": kind,
                "offers": 0,
                "accepted": 0,
                "done": 0,
                "where": Counter(),
                "paid": [],
                "minutes": [],
            },
        )
        group["offers"] += 1
        group["accepted"] += accepted
        group["where"][
            " ".join(part for part in (creature or person, area) if part)
        ] += 1
        if done:
            group["done"] += 1
            minutes = (
                datetime.fromisoformat(done) - datetime.fromisoformat(offered)
            ).total_seconds() / 60
            group["minutes"].append(round(minutes))
        if paid is not None:
            group["paid"].append((paid, coin or ""))
    return sorted(groups.values(), key=lambda g: (g["giver"], -g["offers"]))


def describe(group):
    """One line of ;task history: "cormyn recovery: 6 offered, 6 taken,
    6 done — poloh'izh near Hara'jaal, Glaren Kweld x6 — paid 316-777
    Kronars — 40 min median"."""
    parts = [
        f"{group['giver']} {group['kind']}: {group['offers']} offered, "
        f"{group['accepted']} taken, {group['done']} done"
    ]
    if group["where"]:
        parts.append(
            ", ".join(
                f"{where or '?'} x{n}" for where, n in group["where"].most_common()
            )
        )
    by_coin = {}
    for count, coin in group["paid"]:
        by_coin.setdefault(coin, []).append(count)
    if by_coin:
        parts.append(
            "paid "
            + ", ".join(
                f"{min(counts)}-{max(counts)} {coin}"
                if min(counts) != max(counts)
                else f"{counts[0]} {coin}"
                for coin, counts in by_coin.items()
            )
        )
    if group["minutes"]:
        ordered = sorted(group["minutes"])
        parts.append(f"{ordered[len(ordered) // 2]} min median")
    return " — ".join(parts)


# A game log's offer, as the logs from 2026-10-09 on say it: "Cormyn says,
# \"I do have a small favor to ask.  A friend of mine recently lost ...\""
# or "The Ranger Guildleader Kalika says, \"I do have a small task ...\"".
_OFFER = re.compile(r'^(?P<speaker>.+?) says, "I do have a small (?:task|favor)')
_PROMPT = re.compile(r'<prompt time="(?P<time>\d+)"')
_TAG = re.compile(r"<[^>]*>")


def _iso(epoch):
    return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat()


def scan(lines):
    """The offers in a character's game-log lines (raw, tags and all, in
    time order across logs): [{"giver", "offer", "accepted", "offered_at",
    and when paid "done_at", "paid", "currency"}]. Taken by the giver's
    accept ("Here is the item", "you're looking for"), refused by its
    "I guess you do not wish to help me"; paid by the recipient of a
    delivery, else the giver, "hands you 397 Kronars". The journal's
    fuller name of the item ("small hand mirror" for "mirror") wins."""
    from client.game import tasks

    when, offers, pending, open_task = None, [], None, None
    for raw in lines:
        if stamp := _PROMPT.search(raw):
            when = stamp.group("time")
        text = _TAG.sub("", raw).replace("&gt;", ">").strip()
        if not text:
            continue
        if match := _OFFER.match(text):
            pending = {
                "giver": tasks.person_name(match.group("speaker")),
                "offer": {**tasks.parse_offer(text), "text": text},
                "accepted": False,
                "offered_at": _iso(when) if when else now(),
            }
            offers.append(pending)
            continue
        if pending is not None:
            if tasks.DECLINED in text:
                pending = None
            elif tasks.accepted(text) and pending["giver"].lower() in text.lower():
                pending["accepted"] = True
                open_task, pending = pending, None
            continue
        if open_task is None:
            continue
        journal = tasks.parse_journal(text)
        named = str((journal or {}).get("item") or "")
        item = str(open_task["offer"].get("item") or "")
        if named and item and named != item and named.endswith(item):
            open_task["offer"]["item"] = named
        payment = tasks.paid(text)
        if payment:
            offer = open_task["offer"]
            payer = tasks.person_name(offer.get("person") or open_task["giver"])
            if payer.lower() in text.lower():
                open_task["paid"], open_task["currency"] = payment
                open_task["done_at"] = _iso(when) if when else now()
                open_task = None
    return offers
