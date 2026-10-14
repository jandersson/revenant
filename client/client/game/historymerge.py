"""Every machine's history in one database (#547): what
tools/history_merge.py builds for beholder.

Each machine's ;archive copies a snapshot of its history.db to the shared
folder (client/game/archive.py). Those files cannot simply be joined: every table
keys on its own autoincrement seq, so two machines number their rows
over each other. merge() rebuilds one database from all of them:

- every table of every source, its columns the union of theirs (an
  older machine's rows read NULL in a column only newer code writes),
  plus a `machine` column naming where each row was logged
- seq, and every column ending in _seq (box_drops.loot_seq,
  box_contents.drop_seq: another table's seq), shifted by the machine's
  offset — its place in name order times OFFSET — so the references
  still point at their rows
- a row identical in every column, seq included, to one an earlier
  machine already gave is the same row (a history.db once copied from
  one machine to the other), kept once
- the sources' indexes, rebuilt (never unique: two machines' rows may
  repeat what one machine's could not)

The output is rebuilt from scratch on every run, so running it again
after the next snapshots never doubles a row. It is written to a
temporary file beside it and moved into place.
"""

import os
import re
import sqlite3
from pathlib import Path

OFFSET = 1_000_000_000  # seq values a machine may use before the next one's


def quoted(name):
    return '"' + str(name).replace('"', '""') + '"'


def sources(root, machine, local_history):
    """{machine: history path}: every machine's snapshot under
    <root>/revenant/*/history.db, with `local_history` — a fresh
    snapshot of this machine's own, taken by the caller so the merge
    never holds the live file's lock — in place of the one it copied there
    up to half an hour ago. `root` None: this machine's history alone."""
    found = {}
    if root is not None:
        for snapshot in sorted(Path(root, "revenant").glob("*/history.db")):
            found[snapshot.parent.name] = snapshot
    if local_history is not None and Path(local_history).exists():
        found[machine] = Path(local_history)
    return found


def tables(connection):
    return [
        name
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def columns(connection, table):
    """[(name, declared type)] in the table's order."""
    return [
        (row[1], row[2] or "")
        for row in connection.execute(f"PRAGMA table_info({quoted(table)})")
    ]


def shifted(name):
    return name == "seq" or name.endswith("_seq")


def make_room(target, schema, table, cols):
    """The table in `target` with every column of `cols`: created at
    first sight (seq the key, `machine` last), widened after."""
    if table not in schema:
        parts = [
            f"{quoted(name)} INTEGER PRIMARY KEY"
            if name == "seq"
            else f"{quoted(name)} {kind}".strip()
            for name, kind in cols
        ]
        parts.append('"machine" TEXT')
        target.execute(f"CREATE TABLE {quoted(table)} ({', '.join(parts)})")
        schema[table] = [name for name, _ in cols]
        return
    for name, kind in cols:
        if name not in schema[table]:
            target.execute(
                f"ALTER TABLE {quoted(table)} ADD COLUMN {quoted(name)} {kind}".strip()
            )
            schema[table].append(name)


_INDEX = re.compile(
    r"^CREATE\s+(UNIQUE\s+)?INDEX\s+(IF\s+NOT\s+EXISTS\s+)?", re.IGNORECASE
)


def copy_table(source, target, table, cols, machine, offset, earlier):
    """One source table's rows into `target`, shifted and named by
    machine, past the rows an earlier machine gave (`earlier`, hashes of
    whole rows, grown with this machine's): (rows taken, rows skipped).
    A 64-bit hash stands for a row: two different rows sharing one in a
    history of millions is a chance of about one in ten million."""
    names = [name for name, _ in cols]
    shift = [shifted(name) for name in names]
    mine, counts = set(), {"taken": 0, "skipped": 0}

    def rows():
        select = ", ".join(quoted(name) for name in names)
        for row in source.execute(f"SELECT {select} FROM {quoted(table)}"):
            key = hash(row)
            if key in earlier:
                counts["skipped"] += 1
                continue
            mine.add(key)
            counts["taken"] += 1
            yield tuple(
                value + offset if move and isinstance(value, int) else value
                for value, move in zip(row, shift)
            ) + (machine,)

    into = ", ".join([*(quoted(name) for name in names), '"machine"'])
    marks = ", ".join("?" * (len(names) + 1))
    target.executemany(f"INSERT INTO {quoted(table)} ({into}) VALUES ({marks})", rows())
    earlier |= mine
    return counts["taken"], counts["skipped"]


def merge(found, out):
    """`found` ({machine: path}, from sources()) merged into `out`:
    ({machine: rows taken}, rows skipped as another machine's copy)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(f".{out.name}.part")
    if part.exists():
        part.unlink()
    target = sqlite3.connect(part)
    taken, skipped = {}, 0
    schema, seen, indexes = {}, {}, []
    try:
        for place, (machine, path) in enumerate(sorted(found.items())):
            uri = f"{Path(path).resolve().as_uri()}?mode=ro"
            source = sqlite3.connect(uri, uri=True)
            try:
                taken[machine] = 0
                for table in tables(source):
                    cols = columns(source, table)
                    make_room(target, schema, table, cols)
                    earlier = seen.setdefault(table, set())
                    rows, copies = copy_table(
                        source, target, table, cols, machine, place * OFFSET, earlier
                    )
                    taken[machine] += rows
                    skipped += copies
                indexes += [
                    sql
                    for (sql,) in source.execute(
                        "SELECT sql FROM sqlite_master WHERE type = 'index'"
                        " AND sql IS NOT NULL"
                    )
                ]
            finally:
                source.close()
        for sql in dict.fromkeys(indexes):
            try:
                target.execute(_INDEX.sub("CREATE INDEX IF NOT EXISTS ", sql, count=1))
            except sqlite3.Error:
                pass  # an index the merged table cannot carry: left out
        target.commit()
    finally:
        target.close()
    os.replace(part, out)
    return taken, skipped
