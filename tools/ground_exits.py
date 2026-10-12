"""List the bestiary's hunting grounds with a room the map walks no way out of.

A hunt that ends in such a room cannot leave on foot (#541: the yellow
gremlins' village, whose only way back to Fang Cove was a scripted edge
the walker could not read). ;hunt refuses such a ground before setting
out; this sweeps them all toward one place.

    uv run python tools/ground_exits.py 8308             # to a ;go2 target
    uv run python tools/ground_exits.py 8308 --premium   # with Fang Cove's portals
    uv run python tools/ground_exits.py shard --zone yellow_gremlins

Rank gates are ignored (the map's connections, not a character's reach);
the map must be downloaded (any ;go2 does it).
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "client")]

from client.game import hunting, travel  # noqa: E402
from client.game.mapdb import MapDB  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", help="a ;go2 target: room id, tag or title")
    parser.add_argument(
        "--premium", action="store_true", help="Fang Cove's portals open"
    )
    parser.add_argument("--zone", action="append", help="only these zones")
    args = parser.parse_args()
    db = MapDB.load()
    goals = travel.goals_of(db, args.target)
    if not goals:
        sys.exit(f"nothing in the map matches {args.target!r}")

    def path(room, goals):
        return db.path(room, goals, gates=False, premium=args.premium)

    stranded = 0
    for name in args.zone or sorted(hunting.ZONES):
        ground = hunting.ground_rooms(db, name)
        stuck = hunting.stranding_rooms(ground, goals, path)
        if stuck:
            stranded += 1
            print(f"{name}: no walk to {args.target} from room(s) {stuck}")
    print(f"{stranded} ground(s) with a room that cannot walk to {args.target}")


if __name__ == "__main__":
    main()
