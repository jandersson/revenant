"""How the walker takes the ice road between Shard and Hibarnhvidar and
the stone wall on the way to it (2026-10-11) — these tests are the
manual. The road is twelve `;e move 'se'; pause 11` edges: the move, then
the map's own pause, slept, never sent. Seord Kerwaith's stone wall is a
hidden door: GO STONE WALL, and while it is shut ("I could not find what
you were referring to.") TURN BASIN (TORCH from the tunnel) and GO again."""

import pytest

from client.game import walker
from client.game.mapdb import MapDB

from test_walker import FakeHandle, puts_of

ICE_ROAD = MapDB(
    [
        {
            "id": 4543,
            "uid": [1],
            "title": ["[Seord Kerwaith, Squat Cavern]"],
            "wayto": {"4540": ";e result = dothistimeout 'go stone wall', 2, /x/"},
        },
        {
            "id": 4540,
            "uid": [2],
            "title": ["[Cragstone Vale, Tunnel]"],
            "wayto": {"4543": ";e result = dothistimeout 'go stone wall', 2, /x/"},
        },
        {
            "id": 4430,
            "uid": [3],
            "title": ["[Himineldar Shel, Rope Bridge]"],
            "wayto": {"4429": ";e move 'nw'; pause 11"},
        },
        {
            "id": 4429,
            "uid": [4],
            "title": ["[Himineldar Shel, Mountain Road]"],
            "wayto": {"4430": ";e move 'se'; pause 11"},
        },
    ]
)

SHUT = "I could not find what you were referring to."


class RoadHandle(FakeHandle):
    """GO STONE WALL is answered SHUT while `shut`; TURN BASIN (or TORCH)
    opens it. The ice road's moves land one room on."""

    MOVES = {
        (1, "go stone wall"): 2,
        (2, "go stone wall"): 1,
        (3, "nw"): 4,
        (4, "se"): 3,
    }

    def __init__(self, uid, shut=True):
        super().__init__([])
        self.shut = shut
        self.lands = None
        self.answer = None
        self.state.room_uid = uid

    def put(self, command):
        super().put(command)
        uid = self.state.room_uid
        self.lands = None
        if command.startswith("turn "):
            self.shut = False
        elif command == "go stone wall" and self.shut:
            self.answer = SHUT
        elif command == "look":
            self.lands = uid
        else:
            self.lands = self.MOVES.get((uid, command))

    def get(self, timeout=None, streams=("",)):
        if timeout == 0 or streams is not None:
            return None
        if self.answer:
            answer, self.answer = self.answer, None
            return ("", answer)
        if self.lands is None:
            return None
        self.state.room_uid, self.lands = self.lands, None
        return ("compass", "")


@pytest.fixture
def quick_door(monkeypatch):
    monkeypatch.setattr(walker, "DOOR_ANSWER_SECONDS", 0.05)


def test_the_ice_road_moves_at_the_maps_pace_and_sends_no_pause():
    handle = RoadHandle(3)
    assert walker.walk(handle, ICE_ROAD, [4429]) is True
    assert puts_of(handle) == ["nw"]
    assert ("sleep", 11.0) in handle.calls  # the pause 11 is slept, not sent


def test_a_shut_stone_wall_is_opened_with_the_basin_and_walked_through(quick_door):
    handle = RoadHandle(1)
    assert walker.walk(handle, ICE_ROAD, [4540]) is True
    assert puts_of(handle) == ["go stone wall", "turn basin", "go stone wall", "look"]


def test_an_open_wall_is_walked_through_and_the_torch_opens_it_from_the_tunnel(
    quick_door,
):
    handle = RoadHandle(1, shut=False)
    assert walker.walk(handle, ICE_ROAD, [4540]) is True
    assert puts_of(handle) == ["go stone wall", "look"]
    handle = RoadHandle(2)
    assert walker.walk(handle, ICE_ROAD, [4543]) is True
    assert "turn torch" in puts_of(handle)
    assert ICE_ROAD.graph[4543][4540]["seconds"] == 2.0  # a door, not a ride
