"""Grid layout for the map dock, Qt-free (issue #56).

layout() places a BFS neighborhood of rooms around a center room on
integer grid cells, following the community map's directional edges
(north = one cell up, southeast = one cell down-right, ...); the GUI
only draws the result. Non-directional edges (go gate, climb wall, up/
down/out, translated ";e" sequences) place their rooms in the nearest
free cell and render as a distinct edge kind. When two rooms contend
for one cell — the classic MUD-mapper collision — the loser slides
further along its direction or into the nearest free cell; perfect
geography is a non-goal (#56).
"""

import json

from client.mapdb import local_mapdb_path, walkable

# Screen-oriented grid steps: y grows downward, north is up.
DIRECTION_VECTORS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
    "northeast": (1, -1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (-1, 1),
    "n": (0, -1),
    "s": (0, 1),
    "e": (1, 0),
    "w": (-1, 0),
    "ne": (1, -1),
    "nw": (-1, -1),
    "se": (1, 1),
    "sw": (-1, 1),
}

ROOM_LIMIT = 80  # rooms per neighborhood — plenty for a screen
DIRECTION_STRETCH = 4  # how far a directional step slides to dodge a collision
SPIRAL_LIMIT = 5  # how far out the free-cell search rings reach


def direction_vector(command):
    """The grid step for a movement command, or None when it has none."""
    if not isinstance(command, str):
        return None
    return DIRECTION_VECTORS.get(command.strip().lower())


def resolve_room(db, uid, title):
    """The map room for a "room" stream frame: uid exactly when the map
    knows it, an unambiguous title otherwise, else None (off the map).
    Colliding titles stay None — the dock says so instead of guessing."""
    if uid:
        mapped = db.room_by_uid(uid)
        if mapped is not None:
            return mapped
    if title:
        candidates = db.rooms_titled(title)
        if len(candidates) == 1:
            return candidates[0]
    return None


def local_room_ids():
    """Ids of the personal survey overlay's rooms (drawn distinctly)."""
    path = local_mapdb_path()
    if not path.is_file():
        return set()
    try:
        with open(path) as stream:
            rooms = json.load(stream)
        return {int(room["id"]) for room in rooms}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def _neighbors(db, room_id):
    """Walkable (dest, command) pairs, deterministically ordered."""
    wayto = db.rooms[room_id].get("wayto") or {}
    pairs = []
    for dest, command in wayto.items():
        if not str(dest).isdigit():
            continue
        dest = int(dest)
        if dest in db.rooms and walkable(command):
            pairs.append((dest, command))
    return sorted(pairs)


def _spiral(origin):
    """Cells around origin, nearest ring first, deterministic order."""
    x, y = origin
    for ring in range(1, SPIRAL_LIMIT + 1):
        cells = [
            (x + dx, y + dy)
            for dx in range(-ring, ring + 1)
            for dy in range(-ring, ring + 1)
            if max(abs(dx), abs(dy)) == ring
        ]
        yield from sorted(cells, key=lambda c: (abs(c[0] - x) + abs(c[1] - y), c))


def _place(origin, vector, occupied):
    """A free cell for a room next to origin: along its direction (sliding
    outward past collisions), else the nearest free cell, else None."""
    x, y = origin
    if vector:
        for stretch in range(1, DIRECTION_STRETCH + 1):
            cell = (x + vector[0] * stretch, y + vector[1] * stretch)
            if cell not in occupied:
                return cell
    for cell in _spiral(origin):
        if cell not in occupied:
            return cell
    return None


def layout(db, center, limit=ROOM_LIMIT):
    """Positions and edges for the neighborhood around a center room.

    Returns ({room_id: (x, y)}, [(a, b, kind)]) with the center at
    (0, 0); kind is "direction" for compass edges (drawn straight) and
    "other" for everything else (go/climb/up/down, drawn dashed). Every
    room gets its own cell; edges appear once per room pair."""
    positions = {center: (0, 0)}
    occupied = {(0, 0)}
    edges = []
    seen_pairs = set()
    frontier = [center]
    while frontier:
        next_frontier = []
        for room_id in frontier:
            for dest, command in _neighbors(db, room_id):
                vector = direction_vector(command)
                if dest not in positions and len(positions) < limit:
                    cell = _place(positions[room_id], vector, occupied)
                    if cell is None:
                        continue
                    positions[dest] = cell
                    occupied.add(cell)
                    next_frontier.append(dest)
                if dest in positions:
                    pair = (min(room_id, dest), max(room_id, dest))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        kind = "direction" if vector else "other"
                        edges.append((room_id, dest, kind))
        frontier = next_frontier
    return positions, edges
