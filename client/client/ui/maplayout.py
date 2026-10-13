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

from client.game.mapdb import local_mapdb_path, walkable

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
# The median distance between compass neighbours on the community map's
# images, measured 2026-10-13 (38 px over 23,839 pairs): one step, one cell.
IMAGE_PIXELS_PER_CELL = 38
MIN_GAP = 0.4  # cells; rooms closer than this would overlap in the dock


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


def _image_spot(room):
    """(image, (x, y)) for the centre of a room's box on its map image,
    or None when the map draws it nowhere."""
    image, coords = room.get("image"), room.get("image_coords")
    if not image or not isinstance(coords, list) or len(coords) != 4:
        return None
    x1, y1, x2, y2 = coords
    return image, ((x1 + x2) / 2, (y1 + y2) / 2)


def _image_positions(db, center, rooms):
    """{room: (x, y)} in cells from the center for the rooms drawn on the
    center's map image, in the given order; a room drawn on top of one
    already placed is left out (it goes on the grid)."""
    anchor = _image_spot(db.rooms[center])
    if anchor is None:
        return {}
    image, (cx, cy) = anchor
    spots = {}
    for room_id in rooms:
        spot = _image_spot(db.rooms[room_id])
        if spot is None or spot[0] != image:
            continue
        x = (spot[1][0] - cx) / IMAGE_PIXELS_PER_CELL
        y = (spot[1][1] - cy) / IMAGE_PIXELS_PER_CELL
        if all(
            abs(x - sx) >= MIN_GAP or abs(y - sy) >= MIN_GAP
            for sx, sy in spots.values()
        ):
            spots[room_id] = (x, y)
    return spots


def layout(db, center, limit=ROOM_LIMIT):
    """Positions and edges for the neighborhood around a center room.

    Returns ({room_id: (x, y)}, [(a, b, kind)]) with the center at
    (0, 0); kind is "direction" for compass edges (drawn straight) and
    "other" for everything else (go/climb/up/down, drawn dashed). Rooms
    on the center's map image sit at their drawn spots (float cells),
    the rest on integer grid cells; edges appear once per room pair."""
    positions, edges = _bfs(db, center, limit, {})
    pinned = _image_positions(db, center, positions)
    if pinned:
        # The same neighborhood again, the drawn rooms pinned first so
        # the grid ones fill in around them.
        positions, edges = _bfs(db, center, limit, pinned)
    return positions, edges


def _bfs(db, center, limit, pinned):
    """layout() for a given set of pinned positions."""
    positions = {center: (0, 0)}
    occupied = {(round(x), round(y)) for x, y in pinned.values()} | {(0, 0)}
    edges = []
    seen_pairs = set()
    frontier = [center]
    while frontier:
        next_frontier = []
        for room_id in frontier:
            for dest, command in _neighbors(db, room_id):
                vector = direction_vector(command)
                if dest not in positions and len(positions) < limit:
                    if dest in pinned:
                        positions[dest] = pinned[dest]
                    else:
                        x, y = positions[room_id]
                        cell = _place((round(x), round(y)), vector, occupied)
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
