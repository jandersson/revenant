"""Fill history.db's kiosk dataset from the game logs (#574).

    uv run python tools/kiosk_backfill.py             add what the logs hold and the tables lack
    uv run python tools/kiosk_backfill.py --dry-run   say what it would add

Each character's game logs that mention a kiosk are read in order as one
stream through client/game/kiosklog.py's scan: the sales seen at every
kiosk in the room, the STUDY readings, the TAPs and resales. A Finesse
PREPARE's mana comes from the debug logs (a script's send or an outside
one; a PREPARE typed in the window is not logged there). Rows already in
the tables are left alone, so a second run adds nothing.
"""

import argparse
import bisect
import re
from datetime import datetime

from client.client_logger import log_dir
from client.game import kiosklog

_GAME = re.compile(r"^game-(?P<name>[A-Za-z]+)-(?P<stamp>\d{8}-\d{6})\.log$")
_PREPARE = re.compile(
    r"^(?P<when>\d\d-\w{3}-\d\d \d\d:\d\d:\d\d) .*(?:\]> |external send from \w+: ')"
    r"prepare fin(?:esse)?(?: (?P<mana>\d+))?'?\s*$",
    re.I,
)


def kiosk_logs(directory):
    """{character: [game logs that mention a kiosk, in time order]}."""
    logs = {}
    for path in sorted(directory.glob("game-*.log")):
        match = _GAME.match(path.name)
        if match and b"kiosk" in path.read_bytes():
            logs.setdefault(match.group("name"), []).append(
                (match.group("stamp"), path)
            )
    return {name: [path for _, path in sorted(paths)] for name, paths in logs.items()}


def finesse_prepares(directory, name):
    """A finesse_mana(epoch) for scan: the mana of the character's last
    Finesse PREPARE at or before then (0 for a bare one), else None."""
    found = []
    for path in sorted(directory.glob(f"revenant_client-{name}-*.log")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if match := _PREPARE.match(line):
                local = datetime.strptime(match.group("when"), "%d-%b-%y %H:%M:%S")
                found.append((local.timestamp(), int(match.group("mana") or 0)))
    found.sort()
    times = [when for when, _ in found]

    def mana(epoch):
        index = bisect.bisect_right(times, epoch)
        return found[index - 1][1] if index else None

    return mana


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    directory = log_dir()
    for name, paths in kiosk_logs(directory).items():
        lines = []
        for path in paths:
            lines += path.read_text(encoding="utf-8", errors="replace").splitlines()
        events = kiosklog.scan(lines, name, finesse_prepares(directory, name))
        added = kiosklog.record(events, dry_run=args.dry_run)
        counts = ", ".join(f"{n} {table[6:]}" for table, n in added.items())
        print(f"{name}: {'would add' if args.dry_run else 'added'} {counts}")


if __name__ == "__main__":
    main()
