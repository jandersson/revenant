"""The power-walking model: a loop of street rooms joined by plain
compass moves both ways, the out-and-back visiting order, and the
sixty-second timer per room."""

from client.game import attune
from client.game.mapdb import MapDB


def street(n=6):
    """Rooms 1..n in a line, east/west both ways; a shop off room 2
    ("go forge", one way back "out"); room 8 reachable from 3 only."""
    rooms = []
    for i in range(1, n + 1):
        wayto = {}
        if i > 1:
            wayto[str(i - 1)] = "west"
        if i < n:
            wayto[str(i + 1)] = "east"
        rooms.append(
            {"id": i, "uid": [100 + i], "title": [f"[Street {i}]"], "wayto": wayto}
        )
    rooms[1]["wayto"]["7"] = "go forge"
    rooms.append({"id": 7, "uid": [107], "title": ["[Forge]"], "wayto": {"2": "out"}})
    rooms[2]["wayto"]["8"] = "north"
    rooms.append(
        {"id": 8, "uid": [108], "title": ["[Alley]"], "wayto": {}}
    )  # no way back
    return MapDB(rooms)


MAP = street()


def test_plain_neighbors_are_two_way_compass_moves_only():
    assert attune.plain_neighbors(MAP, 2) == [(1, "west"), (3, "east")]  # not the forge
    assert attune.plain_neighbors(MAP, 3) == [(2, "west"), (4, "east")]  # not the alley
    assert attune.plain_neighbors(MAP, 2, avoid={3}) == [(1, "west")]


def test_the_chain_runs_along_the_street_and_stops_where_it_ends():
    assert attune.chain(MAP, 1, 4) == [1, 2, 3, 4, 5]
    assert attune.chain(MAP, 1, 10) == [1, 2, 3, 4, 5, 6]  # the street runs out
    assert attune.chain(MAP, 3, 2) == [3, 2, 1]  # west is tried first
    assert attune.chain(MAP, 1, 4, avoid={4}) == [1, 2, 3]
    assert attune.chain(MAP, 7, 4) == [7]  # a shop: no street to loop


def test_the_circuit_goes_out_and_back_so_every_room_comes_round():
    assert attune.circuit([1, 2, 3, 4]) == [2, 3, 4, 3, 2, 1]
    assert attune.circuit([1, 2]) == [2, 1]
    assert attune.circuit([1]) == [1]


def test_a_room_pays_again_after_the_minute():
    assert attune.wait_for(5, {}, now=100.0) == 0
    assert attune.wait_for(5, {5: 100.0}, now=130.0) == 30.0
    assert attune.wait_for(5, {5: 100.0}, now=161.0) == 0
