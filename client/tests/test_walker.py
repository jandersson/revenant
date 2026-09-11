"""How the walker traverses scripted map edges — these tests are the manual.

Simple embedded-Ruby edges (fput/move string literals, optional
waitrt?) translate into game-command sequences; the walker sends the
preliminaries with roundtime waits and gives the final command the
usual compass-sync and arrival check. Edges with real logic stay
unwalkable.
"""

from types import SimpleNamespace

from client.game import walker
from client.game.mapdb import MapDB, translate_embedded, walkable


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
            # streams=None is the arrival wait: (stream, text) pairs.
            return ("compass", "n s") if streams is None else "compass frame"
        return None

    def echo(self, text):
        self.echoes.append(text)


TREE = MapDB(
    [
        {
            "id": 6153,
            "uid": [224005],
            "title": ["[Wilderness, Deep Forest]"],
            "wayto": {"5705": "climb felled tree"},
        },
        {
            "id": 5705,
            "uid": [224006],
            "title": ["[Wilderness, Deep Forest]"],
            "wayto": {},
        },
    ]
)

# The felled tree west of Crossing, captured 2026-09-11 (#157): a
# circle-1 Paladin (Athletics 7) with a handaxe in hand and plate on was
# turned back two ways, and sat down each time; everyone else in the
# log climbed it freely.
HINDER = "Your oak-hafted handaxe and plate vambraces make the climb more difficult.\n"
REFUSAL = (
    "You pick your way up the tree, but reach a point where your footing "
    "is questionable.  Reluctantly, you climb back down.\n"
)
VERTIGO = (
    "You make your way up the tree.  Partway up, you make the mistake of "
    "looking down.  Struck by vertigo, you cling to the tree for a few "
    "moments, then slowly climb back down.\n"
)


class ClimbHandle(FakeHandle):
    """Each climb answers from a script: "refused" / "vertigo" deliver
    the captured lines and no compass frame; "ok" lands the climb."""

    ANSWERS = {"refused": REFUSAL, "vertigo": VERTIGO}
    SITTING = "You must be standing to do that.\n"

    def __init__(self, uids, answers):
        super().__init__(uids)
        self.answers = list(answers)
        self.pending = []

    def put(self, command):
        super().put(command)
        if command.startswith("climb"):
            answer = self.answers.pop(0)
            if answer == "ok":
                self.state.room_uid = self._uids.pop(0)
                self.pending = [("compass", "n")]
            elif answer == "sitting":
                self.pending = [("", self.SITTING)]  # no hindering line
            else:
                self.pending = [("", HINDER), ("", self.ANSWERS[answer])]

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        return self.pending.pop(0) if self.pending else None


def puts_of(handle):
    return [call[1] for call in handle.calls if call[0] == "put"]


def test_a_climb_turned_back_is_retried_standing_and_unburdened():
    handle = ClimbHandle(uids=[224006], answers=["refused", "ok"])
    handle.state.room_uid = 224005
    assert walker.walk(handle, TREE, [5705], describe="Knife Clan") is True
    # STAND unconditionally: the refusal sits you down, and the posture
    # indicator lands after the text the walker reacts to (captured —
    # both STOWs answered "You must stand first." when STAND was gated
    # on the indicator). The refusal's roundtime is waited out first.
    assert puts_of(handle) == [
        "climb felled tree",
        "stand",
        "stow my handaxe",
        "stow my vambraces",
        "climb felled tree",
    ]
    first_climb = handle.calls.index(("put", "climb felled tree"))
    assert handle.calls[first_climb + 1] == ("waitrt",)
    assert any("stood up, stowed handaxe, vambraces" in echo for echo in handle.echoes)
    assert any("get what you need back out" in echo for echo in handle.echoes)


def test_a_climb_refused_for_sitting_stands_and_retries_without_a_burst():
    # "You must be standing to do that." (captured 2026-09-11, the climb
    # sent while the previous refusal had sat the character down).
    handle = ClimbHandle(uids=[224006], answers=["sitting", "ok"])
    handle.state.room_uid = 224005
    assert walker.walk(handle, TREE, [5705]) is True
    assert puts_of(handle) == ["climb felled tree", "stand", "climb felled tree"]


def test_vertigo_is_a_refusal_too():
    # The second wording (captured on the retry itself): "Struck by
    # vertigo ... then slowly climb back down."
    handle = ClimbHandle(uids=[224006], answers=["vertigo", "ok"])
    handle.state.room_uid = 224005
    assert walker.walk(handle, TREE, [5705]) is True
    assert puts_of(handle).count("climb felled tree") == 2
    assert "retreat" not in puts_of(handle)


def test_a_climb_turned_back_twice_stops_with_what_would_help():
    handle = ClimbHandle(uids=[], answers=["refused", "vertigo"])
    handle.state.room_uid = 224005
    assert walker.walk(handle, TREE, [5705], describe="Knife Clan") is False
    puts = puts_of(handle)
    assert puts.count("climb felled tree") == 2
    assert "retreat" not in puts  # not an engagement: no burst
    advice = next(echo for echo in handle.echoes if "beyond your Athletics" in echo)
    assert "handaxe, vambraces" in advice and ";athletics" in advice


def test_hindering_nouns_are_the_last_word_of_each_item():
    assert walker.hindering_nouns(HINDER) == ["handaxe", "vambraces"]
    assert walker.hindering_nouns(
        "Your heavy backpack makes the climb more difficult."
    ) == ["backpack"]
    assert walker.hindering_nouns("You climb the tree.") == []


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


def test_avoided_rooms_resolve_like_go2_targets():
    db = MapDB(
        [
            {"id": 7, "title": ["[Cougar Cliffs]"], "tags": ["cougars"], "wayto": {}},
            {
                "id": 8,
                "title": ["[Vineyard]"],
                "tags": ["cougars_vineyard"],
                "wayto": {},
            },
            {"id": 9, "title": ["[Safe Road]"], "wayto": {}},
        ]
    )
    assert walker.avoided_rooms(db, ["cougars", "9"]) == {7, 9}
    assert walker.avoided_rooms(db, None) == set()
    # An entry matching nothing (a tag this map lacks) is just empty.
    assert walker.avoided_rooms(db, ["rock_guardians"]) == set()


def test_walk_announces_a_route_forced_through_avoided_rooms():
    # No clean detour exists here, so the walk proceeds — announced
    # before the first step, never silently.
    chain = MapDB(
        [
            {"id": 1, "uid": [201], "title": ["[Road]"], "wayto": {"2": "north"}},
            {
                "id": 2,
                "uid": [202],
                "title": ["[Cougar Cliffs]"],
                "tags": ["cougars"],
                "wayto": {"3": "north"},
            },
            {"id": 3, "uid": [203], "title": ["[Overlook]"], "wayto": {}},
        ]
    )
    handle = FakeHandle(uids=[202, 203])
    handle.state.room_uid = 201
    assert walker.walk(handle, chain, [3], avoid={2}) is True
    warning = next(echo for echo in handle.echoes if "no clean detour" in echo)
    assert "1 avoided room(s)" in warning and "[Cougar Cliffs]" in warning


def test_walk_accepts_arrival_in_a_twin_of_the_planned_room():
    # Captured 2026-09-04 (#137): the plan said 670, the game stamped
    # the uid the map files under its twin 13100 — same room. Only the
    # uid-less twin is linked here, so the plan cannot dodge it.
    db = MapDB(
        [
            {
                "id": 684,
                "uid": [200008],
                "title": ["[[Middens, Alerin Slade]]"],
                "wayto": {"670": "south"},
            },
            {
                "id": 670,
                "title": ["[[Middens, Gravel Way]]"],
                "wayto": {"669": "east", "684": "north"},
            },
            {
                "id": 13100,
                "uid": [200009],
                "title": ["[[Middens, Gravel Way]]"],
                "wayto": {"669": "east", "684": "north"},
            },
            {
                "id": 669,
                "uid": [200010],
                "title": ["[[Middens, Bumboat Row]]"],
                "wayto": {},
            },
        ]
    )
    handle = FakeHandle(uids=[200009, 200010])
    handle.state.room_uid = 200008
    assert walker.walk(handle, db, [669], describe="Bumboat Row") is True
    assert not any("off course" in echo for echo in handle.echoes)
    assert [c for c in handle.calls if c[0] == "put"] == [
        ("put", "south"),
        ("put", "east"),
    ]
