"""How the map dock lays rooms out — these tests are the manual.

The layout engine (client/ui/maplayout.py, Qt-free) places a BFS
neighborhood where the community map draws it: rooms on the center's
map image at their image_coords, scaled to cells (#542). The rest go on
grid cells: compass edges step their direction (north is up), everything
else (go/climb/up/down) lands in the nearest free cell as an "other"
edge, and colliding rooms slide instead of overlapping. The GUI's map
dock only draws the result (#56).
"""

from client.game.mapdb import MapDB
from client.ui.maplayout import IMAGE_PIXELS_PER_CELL, ROOM_LIMIT, layout, resolve_room

PX = IMAGE_PIXELS_PER_CELL
COVE = "Ilitha, Fang Cove.jpg"


def _db(*rooms):
    return MapDB(list(rooms))


def _room(room_id, wayto=None, title=None, uid=None, image=None, at=None):
    """at=(x, y) draws the room's 24-pixel box centred there on image."""
    room = {
        "id": room_id,
        "title": [title or f"[Room {room_id}]"],
        "uid": [uid] if uid else [],
        "wayto": {str(dest): command for dest, command in (wayto or {}).items()},
    }
    if at:
        room["image"] = image or COVE
        room["image_coords"] = [at[0] - 12, at[1] - 12, at[0] + 12, at[1] + 12]
    return room


def test_a_corridor_lays_out_on_a_line():
    db = _db(
        _room(1, {2: "east"}),
        _room(2, {1: "west", 3: "east"}),
        _room(3, {2: "west"}),
    )
    positions, edges = layout(db, 1)
    assert positions == {1: (0, 0), 2: (1, 0), 3: (2, 0)}
    assert (1, 2, "direction") in edges
    assert (2, 3, "direction") in edges


def test_compass_directions_step_their_vectors_north_up():
    db = _db(
        _room(1, {2: "north", 3: "southeast", 4: "up"}),
        _room(2),
        _room(3),
        _room(4),
    )
    positions, edges = layout(db, 1)
    assert positions[2] == (0, -1)  # screen coordinates: north is up
    assert positions[3] == (1, 1)
    # Up has no compass vector: nearest free cell, "other" edge.
    assert positions[4] not in ((0, -1), (1, 1), (0, 0))
    assert (1, 4, "other") in edges


def test_colliding_rooms_slide_instead_of_overlapping():
    # 2 and 3 both want the cell north of 1 (the classic mapper
    # collision, via a diagonal detour); every room keeps its own cell.
    db = _db(
        _room(1, {2: "north", 4: "east"}),
        _room(2),
        _room(4, {3: "northwest"}),
        _room(3),
    )
    positions, _ = layout(db, 1)
    assert len(set(positions.values())) == len(positions)


def test_go_edges_render_dashed_but_still_connect():
    db = _db(
        _room(1, {2: "go gate"}),
        _room(2, {1: "go gate"}),
    )
    positions, edges = layout(db, 1)
    assert 2 in positions
    assert edges == [(1, 2, "other")]


def test_untranslatable_scripted_edges_stay_off_the_map():
    db = _db(
        _room(1, {2: ";e start_script('bribe'); fput 'go gate'"}),
        _room(2),
    )
    positions, edges = layout(db, 1)
    assert 2 not in positions
    assert edges == []


def test_the_neighborhood_is_capped():
    corridor = [_room(i, {i + 1: "east", i - 1: "west"}) for i in range(1, 200)]
    db = _db(*corridor)
    positions, _ = layout(db, 100)
    assert len(positions) == ROOM_LIMIT
    assert positions[100] == (0, 0)  # the center anchors the origin


def test_each_room_pair_gets_one_edge():
    db = _db(
        _room(1, {2: "east"}),
        _room(2, {1: "west"}),
    )
    _, edges = layout(db, 1)
    assert edges == [(1, 2, "direction")]


def test_rooms_on_the_centers_image_sit_where_the_map_draws_them():
    # Fate's Fortune Lane's north exit leads to a walkway the map draws
    # far up the image and to the east; the dock follows the drawing.
    db = _db(
        _room(1, {2: "north", 3: "west"}, at=(740, 1245)),
        _room(2, {1: "south"}, at=(740 + 2 * PX, 1245 - 8 * PX)),
        _room(3, {1: "east"}, at=(740 - PX / 2, 1245)),
    )
    positions, edges = layout(db, 1)
    assert positions == {1: (0, 0), 2: (2, -8), 3: (-0.5, 0)}
    assert (1, 2, "direction") in edges


def test_a_room_without_coords_or_on_another_image_goes_on_the_grid():
    db = _db(
        _room(1, {2: "east", 3: "go building", 4: "north"}, at=(500, 500)),
        _room(2, at=(500 + 3 * PX, 500)),
        _room(3),  # an interior the map draws nowhere
        _room(4, image="Zoluren, 1, Crossing.gif", at=(500, 500 - 7 * PX)),
    )
    positions, _ = layout(db, 1)
    assert positions[2] == (3, 0)
    assert positions[4] == (0, -1)  # one compass step, not the other image's spot
    assert positions[3] == (-1, 0)  # the nearest free cell, as before


def test_a_grid_room_never_takes_the_cell_a_drawn_room_sits_in():
    # 3 (no coords) is met first and would step east onto 2's drawn spot.
    db = _db(
        _room(1, {3: "east", 4: "south"}, at=(500, 500)),
        _room(3),
        _room(4, {2: "northeast"}, at=(500, 500 + 2 * PX)),
        _room(2, at=(500 + PX, 500)),
    )
    positions, _ = layout(db, 1)
    assert positions[2] == (1, 0)
    assert positions[3] != (1, 0)


def test_rooms_drawn_on_the_same_spot_do_not_overlap():
    db = _db(
        _room(1, {2: "east", 3: "go door"}, at=(500, 500)),
        _room(2, at=(500 + PX, 500)),
        _room(3, at=(500 + PX, 500)),  # the map draws it on top of 2
    )
    positions, _ = layout(db, 1)
    assert positions[2] == (1, 0)
    assert positions[3] not in ((0, 0), (1, 0))


def test_a_center_without_coords_keeps_the_grid_for_every_room():
    db = _db(
        _room(1, {2: "east"}),
        _room(2, {3: "east"}, at=(500, 500)),
        _room(3, at=(500 + 5 * PX, 500)),
    )
    positions, _ = layout(db, 1)
    assert positions == {1: (0, 0), 2: (1, 0), 3: (2, 0)}


def test_resolve_room_prefers_uid_and_refuses_ambiguous_titles():
    db = _db(
        _room(1, title="[High Street]", uid=901),
        _room(2, title="[High Street]", uid=902),
        _room(3, title="[The Square]", uid=903),
    )
    assert resolve_room(db, 902, "[High Street]") == 2
    # Unmapped uid, unique title: the title carries it.
    assert resolve_room(db, 999999, "[The Square]") == 3
    # Colliding title without a known uid: off the map, never a guess.
    assert resolve_room(db, None, "[High Street]") is None
    assert resolve_room(db, None, None) is None
