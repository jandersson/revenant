"""How the walker traverses scripted map edges — these tests are the manual.

Simple embedded-Ruby edges (fput/move string literals, optional
waitrt?) translate into game-command sequences; the walker sends the
preliminaries with roundtime waits and gives the final command the
usual compass-sync and arrival check. Edges with real logic stay
unwalkable.
"""

from types import SimpleNamespace

from client import walker
from client.mapdb import MapDB, translate_embedded, walkable


def test_translate_embedded_handles_lich_styles():
    assert translate_embedded(";e fput 'go gate'") == ["go gate"]
    assert translate_embedded(";e fput 'say grek'; move 'go door'") == [
        "say grek",
        "go door",
    ]
    # waitrt? drops out — the walker waits roundtime around every command.
    assert translate_embedded(";e fput 'go poplar'; waitrt?; fput 'stand'") == [
        "go poplar",
        "stand",
    ]
    assert translate_embedded(";e move(\"climb heavy barricade\"); fput('look')") == [
        "climb heavy barricade",
        "look",
    ]


def test_translate_embedded_refuses_logic():
    for scripted in [
        ";e start_script('bescort', ['airship']);wait_while{running?('bescort')};",
        ";e UserVars.premiumPortal = 'Muspari';move 'go meeting portal'",
        ";e fput 'pull lever' if Room.current.id == 5",
        ";e waitfor 'The ferry arrives'; move 'go ferry'",
        "north",  # not an embedded edge at all
    ]:
        assert translate_embedded(scripted) is None


def test_walkable_accepts_translatable_edges_only():
    assert walkable("north")
    assert walkable(";e fput 'say grek'; move 'go door'")
    assert not walkable(";e start_script('bescort', ['airship'])")
    assert not walkable(1234)


DOOR = MapDB(
    [
        {
            "id": 1,
            "uid": [101],
            "title": ["[Gate]"],
            "wayto": {"2": ";e fput 'say grek'; move 'go door'"},
        },
        {"id": 2, "uid": [102], "title": ["[Hall]"], "wayto": {"1": "out"}},
        {"id": 3, "uid": [999], "title": ["[Cellar]"], "wayto": {}},
    ]
)


class FakeHandle:
    """A Script-handle stand-in for one walk: compass frames appear
    after each movement command; state tracks the arrival uid."""

    def __init__(self, uids):
        self.calls = []
        self.echoes = []
        self.dead = False
        self._uids = list(uids)  # room uid after each compass-waited move
        self.state = SimpleNamespace(room_uid=None, room_title=None, compass=[])

    def put(self, command):
        self.calls.append(("put", command))

    def waitrt(self):
        self.calls.append(("waitrt",))

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None  # no stale compass frames queued
        if self._uids:
            self.state.room_uid = self._uids.pop(0)
            return "compass frame"
        return None

    def echo(self, text):
        self.echoes.append(text)


def test_walk_expands_a_scripted_edge_and_verifies_arrival():
    handle = FakeHandle(uids=[102])
    handle.state.room_uid = 101  # starting at the gate
    assert walker.walk(handle, DOOR, [2], describe="the hall") is True
    assert handle.calls == [
        ("waitrt",),  # step preamble
        ("put", "say grek"),  # preliminary, with its own roundtime wait
        ("waitrt",),
        ("put", "go door"),  # the final command gets the compass sync
        ("waitrt",),  # arrival settle
    ]


def test_walk_stops_when_the_scripted_edge_lands_off_course():
    handle = FakeHandle(uids=[999])  # the cellar, not the hall
    handle.state.room_uid = 101
    assert walker.walk(handle, DOOR, [2], describe="the hall") is False
    assert any("off course" in echo for echo in handle.echoes)


class StallOnceHandle(FakeHandle):
    """The first compass wait stalls (an engaged hostile refuses the
    move); the burst retry's wait succeeds."""

    def __init__(self, uids, hostiles=None):
        super().__init__(uids)
        self.state.hostiles = {"78646435": True} if hostiles is None else hostiles
        self._stalled = False

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if not self._stalled:
            self._stalled = True
            return None  # the refused step: no compass frame arrives
        return super().get(timeout=timeout, streams=streams)


def test_walk_bursts_through_an_engagement(monkeypatch):
    # A hostile refuses the step ("You are engaged to a cave bear at
    # melee range!", captured 2026-08-22): retreat twice to missile
    # range — where movement is legal again — and retry the step.
    handle = StallOnceHandle(uids=[102])
    handle.state.room_uid = 101
    handle.state.room_title = "[Gate]"
    db = MapDB(
        [
            {"id": 1, "uid": [101], "title": ["[Gate]"], "wayto": {"2": "go door"}},
            {"id": 2, "uid": [102], "title": ["[Hall]"], "wayto": {}},
        ]
    )
    assert walker.walk(handle, db, [2], describe="the hall") is True
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert puts == ["go door", "retreat", "retreat", "go door"]


def test_walk_bursts_even_when_hostile_state_is_empty():
    # The #88 capture: engaged at melee while state.hostiles sat empty
    # (the #85 wipe) — the old hostile-gated burst never fired and the
    # walker exited, leaving the character parked in the fight. The
    # burst is unconditional now; a retreat unengaged is harmless.
    handle = StallOnceHandle(uids=[102], hostiles={})
    handle.state.room_uid = 101
    handle.state.room_title = "[Gate]"
    db = MapDB(
        [
            {"id": 1, "uid": [101], "title": ["[Gate]"], "wayto": {"2": "go door"}},
            {"id": 2, "uid": [102], "title": ["[Hall]"], "wayto": {}},
        ]
    )
    assert walker.walk(handle, db, [2], describe="the hall") is True
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert puts == ["go door", "retreat", "retreat", "go door"]


def test_walk_bursts_once_then_stops_on_a_persistent_stall():
    # A stall the burst cannot fix (bad edge, closed door): one retry,
    # then the old stop-and-report behavior — never a retreat loop.
    handle = FakeHandle(uids=[])
    handle.state.room_uid = 101
    db = MapDB(
        [
            {"id": 1, "uid": [101], "title": ["[Gate]"], "wayto": {"2": "go door"}},
            {"id": 2, "uid": [102], "title": ["[Hall]"], "wayto": {}},
        ]
    )
    assert walker.walk(handle, db, [2], describe="the hall") is False
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert puts == ["go door", "retreat", "retreat", "go door"]
    assert any("stalled" in echo for echo in handle.echoes)


def test_walk_refuses_a_dead_character():
    # The cougar lesson (#91): ;go2 bank on a corpse announced a
    # 47-step walk. Dead means no travel — deathwatch owns death.
    handle = FakeHandle([])
    handle.dead = True
    db = MapDB([{"id": 1, "uid": [11], "title": ["[A]"], "wayto": {}}])
    assert walker.walk(handle, db, [1], describe="the bank") is False
    assert handle.calls == []  # not one command left the corpse
    assert any("DEAD" in echo for echo in handle.echoes)


def test_walk_halts_when_death_arrives_mid_route():
    db = MapDB(
        [
            {"id": 1, "uid": [11], "title": ["[A]"], "wayto": {"2": "north"}},
            {"id": 2, "uid": [12], "title": ["[B]"], "wayto": {"3": "north"}},
            {"id": 3, "uid": [13], "title": ["[C]"], "wayto": {}},
        ]
    )

    class DiesOnArrival(FakeHandle):
        def get(self, timeout=None, streams=("",)):
            frame = super().get(timeout, streams)
            if timeout != 0 and frame:
                self.dead = True  # killed stepping into the first room
            return frame

    handle = DiesOnArrival([12])
    handle.state.room_uid = 11
    assert walker.walk(handle, db, [3], describe="the far room") is False
    assert handle.calls.count(("put", "north")) == 1  # step two never sent
    assert any("died en route" in echo for echo in handle.echoes)
