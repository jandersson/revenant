"""How the map dock lays rooms out — these tests are the manual.

The layout engine (client/maplayout.py, Qt-free) places a BFS
neighborhood on grid cells: compass edges step their direction (north
is up), everything else (go/climb/up/down) lands in the nearest free
cell as an "other" edge, and colliding rooms slide instead of
overlapping. The GUI's map dock only draws the result (#56).
"""

from client.mapdb import MapDB
from client.maplayout import ROOM_LIMIT, layout, resolve_room


def _db(*rooms):
    return MapDB(list(rooms))


def _room(room_id, wayto=None, title=None, uid=None):
    return {
        "id": room_id,
        "title": [title or f"[Room {room_id}]"],
        "uid": [uid] if uid else [],
        "wayto": {str(dest): command for dest, command in (wayto or {}).items()},
    }


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
