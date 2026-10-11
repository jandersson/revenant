"""Backfill history.db's task offers from the game logs (#527).

    uv run python tools/task_backfill.py             add what the logs hold and the table lacks
    uv run python tools/task_backfill.py --dry-run   say what it would add

Each character's game logs are read in order as one stream, since a task
taken in one log is often paid in the next, through
client/game/tasklog.py's scan. A search's room and SEARCH count come from
;task's own "found — ... (search N in room R)" in the debug logs. An
offer already in the table (the same character, giver and minute) is
left alone, so a second run adds nothing.
"""

import argparse
import re
from datetime import datetime, timezone

from client.client_logger import log_dir
from client.game import tasklog

_GAME = re.compile(r"^game-(?P<name>[A-Za-z]+)-(?P<stamp>\d{8}-\d{6})\.log$")
_FOUND = re.compile(
    r"^(?P<when>\d\d-\w{3}-\d\d \d\d:\d\d:\d\d) .*\[task\] task: found .*"
    r"\(search (?P<searches>\d+) in room (?P<room>\d+)\)"
)


def game_logs(directory):
    """{character: [paths in time order]}."""
    logs = {}
    for path in sorted(directory.glob("game-*.log")):
        if match := _GAME.match(path.name):
            logs.setdefault(match.group("name"), []).append(
                (match.group("stamp"), path)
            )
    return {name: [path for _, path in sorted(paths)] for name, paths in logs.items()}


def finds(directory, name):
    """[(utc ISO time, room, searches)] off ;task's found echoes."""
    found = []
    for path in sorted(directory.glob(f"revenant_client-{name}-*.log")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if match := _FOUND.match(line):
                local = datetime.strptime(match.group("when"), "%d-%b-%y %H:%M:%S")
                when = local.astimezone(timezone.utc).isoformat()
                found.append(
                    (when, int(match.group("room")), int(match.group("searches")))
                )
    return found


def known(name, path=None):
    """The (giver, minute) of the offers already in the table."""
    connection = tasklog._connect(path)
    try:
        rows = connection.execute(
            "SELECT giver, offered_at FROM tasks WHERE character_name = ?", (name,)
        ).fetchall()
    finally:
        connection.close()
    return {(giver, offered[:16]) for giver, offered in rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    directory = log_dir()
    added = 0
    for name, paths in game_logs(directory).items():
        lines = []
        for path in paths:
            lines += path.read_text(encoding="utf-8", errors="replace").splitlines()
        offers = tasklog.scan(lines)
        if not offers:
            continue
        found, seen = finds(directory, name), known(name)
        for entry in offers:
            giver, offered = entry["giver"].lower(), entry["offered_at"]
            if (giver, offered[:16]) in seen:
                continue
            end = {k: entry[k] for k in ("done_at", "paid", "currency") if k in entry}
            for when, room, searches in found:
                if offered <= when <= entry.get("done_at", when):
                    end.update(room=room, searches=searches)
            offer = entry["offer"]
            print(
                f"{name} {offered[:16]} {giver} {offer.get('kind')}: "
                f"{offer.get('item') or offer.get('person')}, "
                f"{offer.get('area') or offer.get('place')} — "
                + ("taken" if entry["accepted"] else "declined")
                + (f", paid {end['paid']} {end['currency']}" if "paid" in end else "")
            )
            added += 1
            if not args.dry_run:
                seq = tasklog.log_offer(
                    name, giver, offer, entry["accepted"], offered_at=offered
                )
                tasklog.log_end(seq, **end)
    print(f"{'would add' if args.dry_run else 'added'} {added} offer(s)")


if __name__ == "__main__":
    main()
