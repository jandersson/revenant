"""The kiosk dataset in history.db (#574): every kiosk event a character
saw, read back out of the game logs — sales to any kiosk in the room,
STUDY readings, and the owner's TAPs and resales.

`kiosk_sales`: a stranger's sale ("...Asab places his bundle in the
crystalline kiosk..."): the time, the observer, the room, the kiosk's
look, its owner when the lines named one, the seller, pouch or bundle.
The same sale seen by two characters is kept once. `kiosk_readings`:
each STUDY, and each ASK MY TESSERA ABOUT REPORT (from any room): the kiosk, its owner, whether it is the reader's, the
markup, and for the owner's own the reserve and the stored pouches and
bundles in copper — the reserve's fall between readings is what the
sellers were paid. `kiosk_resales`: each TAP and its sale: the kind, the
stored value tapped (unknown when the kiosk bought that kind after the
last reading), the buyer's quote and pay, whether Finesse was up
and the mana of its last PREPARE (0 a bare one, the minimum), and
Trading's mindstate before and after. The money is copper Kronars.

An owner is read off the lines that name one: a cast ("The tessera held
by X ... a Y unfolds from nothingness"), a refresh ("X gestures at a
Y"), a TAP ("which X removes") or a Trader's STUDY ("its owner is X"),
anywhere while that kiosk stands, so a sale before the line that names
its owner gets it too; a sale at a look the room lists twice has none.
Trading's mindstate "after" is its highest from the TAP to the sale:
the lesson lands with the buyer's quote, before the SELL. `scan` is pure; `record` adds what the tables lack, so a
rerun adds nothing (tools/kiosk_backfill.py).
"""

import html
import re
import sqlite3
from datetime import datetime, timezone

from client.game import kiosk

SCHEMA = """
CREATE TABLE IF NOT EXISTS kiosk_sales (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    seen_at TEXT NOT NULL,
    observer TEXT NOT NULL,
    room TEXT,
    kiosk TEXT NOT NULL,
    owner TEXT,
    seller TEXT NOT NULL,
    kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kiosk_readings (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    read_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    room TEXT,
    kiosk TEXT,
    owner TEXT,
    mine INTEGER NOT NULL,
    markup INTEGER,
    reserve INTEGER,
    pouch INTEGER,
    bundle INTEGER
);
CREATE TABLE IF NOT EXISTS kiosk_resales (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tapped_at TEXT NOT NULL,
    character_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    stored INTEGER,
    buyer TEXT,
    offered INTEGER,
    paid INTEGER,
    sold_at TEXT,
    finesse INTEGER NOT NULL,
    finesse_mana INTEGER,
    trading_before INTEGER,
    trading_after INTEGER
);
"""
SAME_SALE_SECONDS = 5  # two observers' clocks for one sale
FINESSE_SECONDS = 120  # the Spells window lists Finesse about once a minute

_PROMPT = re.compile(r'<prompt time="(\d+)"')
_ROOM = re.compile(r"<streamWindow id='room'[^>]*subtitle=\" - \[([^\]]+)\]")
_TRADING = re.compile(r"<component id='exp Trading'>(.*?)</component>")
_OBJS = re.compile(r"<component id='room objs'>(.*?)</component>")
_MINDSTATE = re.compile(r"\[(\d+)/34\]")
_TAG = re.compile(r"<[^>]*>")
# Elements whose text is no story: the prepared spell (<spell>None</spell>
# glued to the cast's line), the hands, the prompt, the components.
_HIDDEN = re.compile(r"<(spell|left|right|prompt|component)\b[^>]*>.*?</\1>")
_KIOSK = r"an? ([^,.]+?(?:kiosk|plinth)[^,.]*?)"
_SALE = re.compile(
    rf"\b{_KIOSK} ripples like water, and the surface spirals open, revealing an "
    r"empty interior chamber\.\s+(\w+) places \w+ (pouch|bundle) in the",
    re.I,
)
_TAP = re.compile(
    rf"\b{_KIOSK} ripples like water, .*?revealing a crystalline (pouch|bundle) "
    r"dusted in frost, which (\w+) removes?",
    re.I,
)
_CAST = re.compile(r"tessera held by (\w+) extends")
_GESTURE = re.compile(rf"\b(\w+) gestures at {_KIOSK}, which responds", re.I)
_SHATTER = re.compile(rf"\b{_KIOSK} shatters", re.I)
_OTHERS = re.compile(rf"As you are not the owner of {_KIOSK}, it rearranges", re.I)
_OWNER_NAME = re.compile(r"its owner is (\w+)")
_BUY = re.compile(r"\bYou ask (?:the )?(.+?) to buy a crystalline")
_FINESSE = re.compile(r"\bFinesse\s+\(\d+ roisaen\)")
STUDY_LINES = 30  # a STUDY's answer, the owner's verbs included


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _look(text):
    return " ".join(text.lower().split())


class _Scan:
    def __init__(self, character, finesse_mana):
        self.me = character
        self.finesse_mana = finesse_mana
        self.now = None
        self.room = None
        self.trading = None
        self.finesse_seen = None
        self.standing = {}  # look -> {owner}, shared by every row of that kiosk
        self.mine = {"look": None}  # the own kiosk, its look learned late
        self.doubled = set()  # looks the room lists more than once
        self.reading = None  # the last own STUDY's reading
        self.sold_since = set()  # (look, kind) sold since that reading
        self.study = None  # [lines] of a STUDY being read
        self.resale = None
        self.out = []

    def owners(self, look):
        return self.standing.setdefault(look, set())

    def grown(self, look, owner):
        """A cast grows a new kiosk: the rows after it are its own, and
        beside another owner's kiosk of the same look they are either's."""
        owners = self.standing.get(look) or set()
        self.standing[look] = owners | {owner} if owners - {owner} else {owner}
        if owner == self.me:
            self.mine = {"look": look}

    def own(self, look, owner):
        if owner.lower() == "you":
            owner = self.me
        self.owners(look).add(owner)
        if owner == self.me:
            if self.mine["look"] not in (None, look):
                self.mine = {}  # a refresh or TAP at another look: another kiosk
            self.mine["look"] = look

    def emit(self, table, **row):
        self.out.append((table, row))

    def raw(self, line):
        prompt = _PROMPT.search(line)
        if prompt:
            self.now = int(prompt.group(1))
        room = _ROOM.search(line)
        if room:
            self.room = room.group(1)
        objs = _OBJS.search(line)
        if objs:
            looks = [_look(name) for _, name in kiosk.listing(objs.group(1))]
            self.doubled = {look for look in looks if looks.count(look) > 1}
        trading = _TRADING.search(line)
        if trading:
            state = _MINDSTATE.search(trading.group(1))
            self.trading = int(state.group(1)) if state else 0
            if self.resale:
                after = self.resale.get("trading_after") or 0
                self.resale["trading_after"] = max(after, self.trading)
                if self.resale.get("sold_at"):
                    self.close_resale()
        story = _TAG.sub("", _HIDDEN.sub("", line))
        for plain in html.unescape(story).splitlines():
            if plain.strip() and self.now is not None:
                self.plain(plain.strip())

    def plain(self, text):
        if self.study is not None:
            self.study.append(text)
            if text.startswith("Roundtime") or len(self.study) > STUDY_LINES:
                self.close_study()
            return
        if (
            "As you examine your kiosk" in text
            or "Audit-abstraction follows" in text  # the tessera's report
            or _OTHERS.search(text)
        ):
            self.study = [text]
            return
        if _FINESSE.search(text):
            self.finesse_seen = self.now
            return
        if sale := _SALE.search(text):
            look = _look(sale.group(1))
            self.emit(
                "kiosk_sales",
                seen_at=_iso(self.now),
                observer=self.me,
                room=self.room,
                kiosk=look,
                owner=None if look in self.doubled else self.owners(look),
                seller=sale.group(2),
                kind=sale.group(3).lower(),
            )
            self.sold_since.add((look, sale.group(3).lower()))
            return
        if tap := _TAP.search(text):
            look, kind, owner = _look(tap.group(1)), tap.group(2).lower(), tap.group(3)
            self.own(look, owner)
            if owner.lower() == "you":
                self.open_resale(kind, look)
            return
        if cast := _CAST.search(text):
            if look := kiosk.cast_name(text):
                self.grown(_look(look), cast.group(1))
            return
        if "Your tessera" in text and (look := kiosk.cast_name(text)):
            self.grown(_look(look), self.me)
            return
        if "You gesture at" in text and (look := kiosk.cast_name(text)):
            self.own(_look(look), self.me)
            return
        if gesture := _GESTURE.search(text):
            self.own(_look(gesture.group(2)), gesture.group(1))
            return
        if shatter := _SHATTER.search(text):
            look = _look(shatter.group(1))
            self.standing.pop(look, None)  # the next of that look is another kiosk
            if look == self.mine["look"]:
                self.mine = {"look": None}
            return
        if self.resale:
            self.read_resale(text)

    def close_study(self):
        text = "\n".join(self.study)
        self.study = None
        reading = kiosk.read_study(text)
        if not reading and (report := kiosk.read_report(text)):
            # From any room: the kiosk's own room is in the report.
            reading = {**report, "owner": True}
        if not reading:
            return
        if reading["owner"]:
            self.reading = reading
            self.sold_since = set()
            look, owner = self.mine, self.me  # the look resolved at the end
        else:
            look = _look(_OTHERS.search(text).group(1))
            named = _OWNER_NAME.search(text)
            if named:
                self.own(look, named.group(1))
            owner = named.group(1) if named else self.owners(look)
        self.emit(
            "kiosk_readings",
            read_at=_iso(self.now),
            character_name=self.me,
            room=reading.get("room") or self.room,
            kiosk=look,
            owner=owner,
            mine=int(reading["owner"]),
            markup=reading["markup"],
            reserve=reading.get("reserve"),
            pouch=reading.get("pouch"),
            bundle=reading.get("bundle"),
        )

    def open_resale(self, kind, look):
        self.close_resale()
        stored = (self.reading or {}).get(kind)
        if (look, kind) in self.sold_since:
            stored = None  # the TAP names no amount: more was bought since
        self.resale = {
            "tapped_at": _iso(self.now),
            "character_name": self.me,
            "kind": kind,
            "stored": min(stored, kiosk.TAP_MAX) if stored else None,
            "trading_before": self.trading,
        }

    def read_resale(self, text):
        resale = self.resale
        if resale.get("sold_at"):
            return
        if (offer := kiosk.offered(text)) is not None:
            resale["offered"] = offer
        elif buy := _BUY.match(text):
            resale["buyer"] = buy.group(1)
        elif resale.get("buyer") and (paid := kiosk.paid(text)) is not None:
            resale["paid"], resale["sold_at"] = paid, _iso(self.now)
            up = (
                self.finesse_seen is not None
                and self.now - self.finesse_seen <= FINESSE_SECONDS
            )
            resale["finesse"] = int(up)
            resale["finesse_mana"] = self.finesse_mana(self.now) if up else None

    def close_resale(self):
        if self.resale:
            self.emit("kiosk_resales", **{"finesse": 0, **self.resale})
        self.resale = None


def scan(lines, character, finesse_mana=lambda epoch: None):
    """[(table, row)] for every kiosk event in one character's game log
    lines (raw, as the log keeps them), in order. `finesse_mana(epoch)`
    is the mana of the last Finesse PREPARE before then, or None."""
    state = _Scan(character, finesse_mana)
    for line in lines:
        state.raw(line)
    if state.study is not None:
        state.close_study()
    state.close_resale()
    for _, row in state.out:
        if isinstance(row.get("kiosk"), dict):
            row["kiosk"] = row["kiosk"].get("look")
        if isinstance(row.get("owner"), set):
            owners = row["owner"]
            row["owner"] = next(iter(owners)) if len(owners) == 1 else None
    return state.out


def _connect(path):
    from client.game.lootlog import db_path

    connection = sqlite3.connect(str(db_path(path)))
    connection.executescript(SCHEMA)
    return connection


def _present(connection, table, row):
    if table == "kiosk_sales":
        return connection.execute(
            "SELECT seq, owner FROM kiosk_sales WHERE kiosk = ? AND seller = ? AND kind = ?"
            " AND (observer = ? AND seen_at = ? OR observer != ? AND"
            " abs(julianday(seen_at) - julianday(?)) * 86400 <= ?)",
            (
                row["kiosk"],
                row["seller"],
                row["kind"],
                row["observer"],
                row["seen_at"],
                row["observer"],
                row["seen_at"],
                SAME_SALE_SECONDS,
            ),
        ).fetchone()
    if table == "kiosk_readings":
        return connection.execute(
            "SELECT 1 FROM kiosk_readings WHERE character_name = ? AND read_at = ?"
            " AND kiosk IS ?",
            (row["character_name"], row["read_at"], row["kiosk"]),
        ).fetchone()
    return connection.execute(
        "SELECT 1 FROM kiosk_resales WHERE character_name = ? AND tapped_at = ?",
        (row["character_name"], row["tapped_at"]),
    ).fetchone()


def record(events, path=None, dry_run=False):
    """Add the events `scan` found that the tables lack: {table: added}."""
    added = {"kiosk_sales": 0, "kiosk_readings": 0, "kiosk_resales": 0}
    connection = _connect(path)
    try:
        for table, row in events:
            if found := _present(connection, table, row):
                if table == "kiosk_sales" and found[1] is None and row["owner"]:
                    # The same sale, seen by an observer who knew the owner.
                    if not dry_run:
                        connection.execute(
                            "UPDATE kiosk_sales SET owner = ? WHERE seq = ?",
                            (row["owner"], found[0]),
                        )
                continue
            added[table] += 1
            if not dry_run:
                columns = ", ".join(row)
                marks = ", ".join("?" for _ in row)
                connection.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({marks})",
                    tuple(row.values()),
                )
        connection.commit()
    finally:
        connection.close()
    return added
