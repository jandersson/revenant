"""How the walker traverses scripted map edges — these tests are the manual.

Simple embedded-Ruby edges (fput/move string literals, optional
waitrt?) translate into game-command sequences; the walker sends the
preliminaries with roundtime waits and gives the final command the
usual compass-sync and arrival check. Edges with real logic stay
unwalkable.
"""

from types import SimpleNamespace

import pytest

from client.game import walker
from client.game.mapdb import MapDB, ride_of, RIDE_SECONDS, translate_embedded, walkable


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


# The map's Faldesu crossing, verbatim (#205).
FALDESU_NORTH = (
    ";e start_script('bescort', ['faldesu', 'haven']);wait_while{running?('bescort')};"
)
FALDESU_SOUTH = (
    ";e start_script('bescort', ['faldesu', 'crossing']);"
    "wait_while{running?('bescort')};"
)


def test_a_bescort_route_the_walker_rides_is_walkable_and_named():
    assert ride_of(FALDESU_NORTH) == "faldesu"
    assert ride_of(FALDESU_SOUTH) == "faldesu"
    assert walkable(FALDESU_NORTH)
    assert ride_of(";e start_script('bescort', ['airship'])") is None
    assert ride_of("north") is None
    # The Marsh's swim edge names the route inside a branch with no dock
    # to wait at: not a ride (it sent the walker to wait at a bridge).
    marsh = (
        ";e if Script.exists?('bescort') then start_script('bescort', "
        "['faldesu', 'haven']);wait_while{running?('bescort')}; else "
        "fput 'dive river';pause;waitrt?;fput 'swim n' end"
    )
    assert ride_of(marsh) is None
    assert not walkable(marsh)
    assert not walkable(";e start_script('bescort', ['airship'])")


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


# Going down (captured 2026-09-12 on the Arthe Dale oak, a rank-10
# climber): both read as a stall until the walker learned them, and the
# stall's retreat burst went out in a tree house.
NO_PURCHASE = (
    "You attempt to climb down the tree, but you can't seem to find purchase.\n"
)
HARD_GOING = (
    "You start down the tree, but you find it hard going.  Rather than "
    "risking a fall, you make your way back up.\n"
)
DIZZY = (
    "Trying to judge the climb, you peer over the edge.  A wave of dizziness "
    "hits you, and you back away from the tree.\n"
)


class ClimbHandle(FakeHandle):
    """Each climb answers from a script: "refused" / "vertigo" deliver
    the captured lines and no compass frame; "ok" lands the climb."""

    ANSWERS = {
        "refused": REFUSAL,
        "vertigo": VERTIGO,
        "purchase": NO_PURCHASE,
        "hard_going": HARD_GOING,
        "dizzy": DIZZY,
    }
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


# --- the Faldesu ferry (#205) --------------------------------------------
FERRY = MapDB(
    [
        {
            "id": 1385,
            "uid": [10385],
            "title": ["[North Road, Ferry]"],
            "wayto": {"470": FALDESU_NORTH, "1384": "south"},
        },
        {
            "id": 470,
            "uid": [10470],
            "title": ["[Riverhaven, Ferry Dock]"],
            "wayto": {"1385": FALDESU_SOUTH, "471": "east"},
        },
        {"id": 471, "uid": [10471], "title": ["[Riverhaven, Pier]"], "wayto": {}},
        {"id": 1384, "uid": [10384], "title": ["[North Road]"], "wayto": {}},
    ]
)


class FerryHandle(FakeHandle):
    """GO FERRY answers from a script with the captured wordings (#205):
    "away" (the ferry is out; the dock's story then brings one in, or
    not), "aboard" (the fee, then the ferry's room — a compass frame),
    "debt" (no lirums: the captain's grumble, the debt line, and aboard
    all the same) or "fare" (refused and left on the dock, uncaptured).
    The crossing's story docks the ferry (or not); GO DOCK lands with a
    compass frame like any move."""

    AWAY = "I could not find what you were referring to.\n"
    FEE = (
        "The Captain stops you and requests a transportation fee of 30 lirums "
        "as you board the craft.\n"
    )
    NO_LIRUMS = (
        '"Hey," he says, "You haven\'t got enough lirums to pay for your trip.  '
        'Come back when you can afford the fare."\n'
    )
    ON_DEBT = (
        "The Captain frowns.  \"But I see you're pretty young and don't have the "
        "sense to keep enough coins on ya fer emergencies, so I'll just add it "
        "to yer debt.\n[Your debt to the province of Therengia is being "
        "increased by 30 lirums.]\n"
    )
    ARRIVES = 'The ferry "Her Opulence" pulls up to the dock.\n'
    LANDS = (
        'The ferry "Her Opulence" reaches the dock and its crew ties the ferry off.\n'
    )

    def __init__(self, uids, answers, arrives=True, lands=True):
        super().__init__(uids)
        self.answers = list(answers)
        self.arrives = arrives
        self.lands = lands
        self.answer = None  # (stream, text) items for the arrival wait
        self.story = []  # story pieces for the dock's and the crossing's waits

    def put(self, command):
        super().put(command)
        if command == "go ferry":
            answer = self.answers.pop(0)
            if answer == "away":
                self.answer = [("", self.AWAY)]
                self.story = [self.ARRIVES] if self.arrives else []
            elif answer in ("aboard", "debt"):
                lines = [self.FEE]
                if answer == "debt":
                    lines += [self.NO_LIRUMS, self.ON_DEBT]
                self.answer = [("", line) for line in lines] + [("compass", "")]
                self.story = [self.LANDS] if self.lands else []
            else:
                self.answer = [("", self.FEE), ("", self.NO_LIRUMS)]
                self.story = []
        elif command == "go dock":
            self.state.room_uid = self._uids.pop(0)
            self.answer = [("compass", "e")]
        else:
            self.answer = None  # a plain move: the base handle's compass

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if streams is None:
            if self.answer is None:
                return super().get(timeout, streams)
            return self.answer.pop(0) if self.answer else None
        return self.story.pop(0) if self.story else None


@pytest.fixture
def quick_ferry(monkeypatch):
    monkeypatch.setattr(walker, "FERRY_ANSWER_SECONDS", 0.05)
    monkeypatch.setattr(walker, "FERRY_WAIT_SECONDS", 0.15)
    monkeypatch.setattr(walker, "FERRY_POLL_SECONDS", 0.05)


ALFREN_SOUTH = (
    ";e if Script.exists?('bescort'); start_script('bescort', ['ferry', 'leth']); "
    "wait_while{ running?('bescort') }; else; echo 'ESCORT REQUIRED'; end"
)


def test_alfrens_ferry_is_a_ride_in_its_if_form():
    from client.game.mapdb import ride_args

    assert ride_of(ALFREN_SOUTH) == "ferry"
    assert ride_args(ALFREN_SOUTH) == "leth"
    assert walkable(ALFREN_SOUTH)


def test_the_ferry_edge_is_routed_at_its_own_cost():
    assert FERRY.graph[1385][470]["seconds"] == RIDE_SECONDS
    assert FERRY.path(1385, [471]) == [(470, FALDESU_NORTH), (471, "east")]


def test_walk_waits_for_the_ferry_boards_crosses_and_steps_off(quick_ferry):
    handle = FerryHandle(uids=[10470, 10471], answers=["away", "aboard"])
    handle.state.room_uid = 10385
    assert walker.walk(handle, FERRY, [471], describe="the pier") is True
    assert puts_of(handle) == ["go ferry", "go ferry", "go dock", "east"]
    assert any("no ferry at the dock" in echo for echo in handle.echoes)
    assert any("aboard the ferry — fare 30 lirums" in echo for echo in handle.echoes)


def test_a_fare_put_on_the_debt_still_boards(quick_ferry):
    # The first ride (2026-09-18): the walker stopped on "afford the
    # fare" while the character stood on the deck.
    handle = FerryHandle(uids=[10470], answers=["debt"])
    handle.state.room_uid = 10385
    assert walker.walk(handle, FERRY, [470]) is True
    assert puts_of(handle) == ["go ferry", "go dock"]
    assert any("on your Therengian debt" in echo for echo in handle.echoes)


def test_a_refusal_that_leaves_you_on_the_dock_stops_the_walk(quick_ferry):
    handle = FerryHandle(uids=[10470], answers=["fare"])
    handle.state.room_uid = 10385
    assert walker.walk(handle, FERRY, [470]) is False
    assert puts_of(handle) == ["go ferry"]
    assert any("refused the fare" in echo for echo in handle.echoes)


def test_a_ferry_that_never_comes_stops_the_walk(quick_ferry):
    handle = FerryHandle(uids=[10470], answers=["away"] * 20, arrives=False)
    handle.state.room_uid = 10385
    assert walker.walk(handle, FERRY, [470]) is False
    assert "go dock" not in puts_of(handle)
    assert any("no ferry came" in echo for echo in handle.echoes)


def test_a_ferry_that_is_out_is_tried_again_every_poll(quick_ferry):
    handle = FerryHandle(
        uids=[10470], answers=["away", "away", "aboard"], arrives=False
    )
    handle.state.room_uid = 10385
    assert walker.walk(handle, FERRY, [470]) is True
    assert puts_of(handle)[:4] == ["go ferry", "go ferry", "go ferry", "go dock"]


def test_a_crossing_that_never_docks_stops_the_walk(quick_ferry):
    handle = FerryHandle(uids=[10470], answers=["aboard"], lands=False)
    handle.state.room_uid = 10385
    assert walker.walk(handle, FERRY, [470]) is False
    assert "go dock" not in puts_of(handle)
    assert any("never docked" in echo for echo in handle.echoes)


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


def test_a_descent_turned_back_is_a_refusal_not_a_stall():
    # 2026-09-12: "can't seem to find purchase" and "make your way back
    # up" were unknown, so the walker waited out the arrival timeout,
    # declared a stall and sent retreat twice from a tree house.
    for first in ("purchase", "hard_going", "dizzy"):
        handle = ClimbHandle(uids=[224006], answers=[first, "ok"])
        handle.state.room_uid = 224005
        assert walker.walk(handle, TREE, [5705]) is True
        assert puts_of(handle).count("climb felled tree") == 2
        assert "retreat" not in puts_of(handle)


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


def test_walk_retries_without_a_burst_where_the_only_exit_is_out():
    # The bank lobby (#171, captured 2026-09-12): a stall on the way
    # into the teller room sent retreat twice — "You are already as far
    # away as you can get!" — and stopped in the lobby. Where the
    # compass shows "out" alone nothing engages, so the step is retried
    # on its own.
    handle = StallOnceHandle(uids=[102], hostiles={})
    handle.state.room_uid = 101
    handle.state.room_title = "[Lobby]"
    handle.state.compass = ["out"]
    db = MapDB(
        [
            {"id": 1, "uid": [101], "title": ["[Lobby]"], "wayto": {"2": "go window"}},
            {"id": 2, "uid": [102], "title": ["[Teller]"], "wayto": {}},
        ]
    )
    assert walker.walk(handle, db, [2], describe="the teller") is True
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert puts == ["go window", "go window"]


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


def test_every_climb_the_walker_sends_is_logged(tmp_path, monkeypatch):
    # #159: a refused climb, its retry that went up — two rows in the
    # climbs table, with the refusal's kind and the wording, no INFO asked.
    from client.game import climblog

    path = tmp_path / "history.db"
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(path))
    handle = ClimbHandle(uids=[224006], answers=["refused", "ok"])
    handle.state.room_uid = 224005
    handle.state.name = "Lanival"
    handle.state.experience = {"Athletics": {"rank": 7, "percent": 0, "mindstate": 2}}
    assert walker.walk(handle, TREE, [5705]) is True
    rows = climblog.rows(climblog.open_history(path))
    assert [row["outcome"] for row in rows] == ["footing", "up"]
    assert "footing is questionable" in rows[0]["wording"]
    assert rows[0]["hindering"].startswith("Your oak-hafted handaxe")
    assert rows[0]["athletics_rank"] == 7 and rows[0]["obstacle"] == "climb felled tree"
    assert not any(call == ("put", "info") for call in handle.calls)


# --- a way closed to the character (#209) ----------------------------------
GATED = MapDB(
    [
        {
            "id": 818,
            "uid": [10818],
            "title": ["[The Crossing, Northeast Customs]"],
            "wayto": {"15122": "go trail", "817": "west"},
        },
        {
            "id": 15122,
            "uid": [15122],
            "title": ["[Paladins' Guild, Holy Warrior's Promenade]"],
            "wayto": {"11716": "south"},
        },
        {"id": 817, "uid": [10817], "title": ["[Street]"], "wayto": {"816": "west"}},
        {"id": 816, "uid": [10816], "title": ["[Street]"], "wayto": {"11716": "north"}},
        {"id": 11716, "uid": [11716], "title": ["[Paladins' Guild, Library]"]},
    ]
)
NOT_EXPERIENCED = "You're not experienced enough to go there.\n"  # captured 2026-09-18


class GateHandle(FakeHandle):
    """The trail answers the refusal and no compass frame; every other
    move lands like any move."""

    def __init__(self, uids):
        super().__init__(uids)
        self.pending = []

    def put(self, command):
        super().put(command)
        if command == "go trail":
            self.pending = [("", NOT_EXPERIENCED)]

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if self.pending:
            return self.pending.pop(0)
        if command_was_trail(self):
            return None  # no arrival follows the refusal
        return super().get(timeout, streams)


def command_was_trail(handle):
    return puts_of(handle)[-1:] == ["go trail"]


def test_a_closed_way_is_routed_around_without_a_retreat():
    handle = GateHandle(uids=[10817, 10816, 11716])
    handle.state.room_uid = 10818
    assert walker.walk(handle, GATED, [11716], describe="the library") is True
    assert puts_of(handle) == ["go trail", "west", "west", "north"]
    assert any("closed to you" in echo for echo in handle.echoes)
    assert any("going round" in echo for echo in handle.echoes)


def test_a_closed_edge_is_out_of_the_route_for_the_rest_of_the_walk():
    route = GATED.path(818, [11716], closed={(818, 15122)})
    assert [dest for dest, _ in route] == [817, 816, 11716]
    assert GATED.path(818, [11716])[0] == (15122, "go trail")


def test_every_way_closed_stops_the_walk():
    lone = MapDB(
        [
            {"id": 1, "uid": [1], "title": ["[A]"], "wayto": {"2": "go trail"}},
            {"id": 2, "uid": [2], "title": ["[B]"]},
        ]
    )
    handle = GateHandle(uids=[])
    handle.state.room_uid = 1
    assert walker.walk(handle, lone, [2]) is False
    assert puts_of(handle) == ["go trail"]
    assert not any(put == "retreat" for put in puts_of(handle))
    assert any("no walkable path" in echo for echo in handle.echoes)


# --- the Obsidian Pass gondola (#211) ---------------------------------------
GONDOLA_SOUTH = (
    ";e if Script.exists?('bescort'); start_script('bescort', ['gondola', 'south']); "
    "wait_while{running?('bescort')}; else; result = dothistimeout 'go gondola', 5, "
    "/no wooden gondola here|Gondola, Cab/; end;"
)
GONDOLA = MapDB(
    [
        {
            "id": 2249,
            "uid": [12249],
            "title": ["[Obsidian Pass, Platform]"],
            "wayto": {"2904": GONDOLA_SOUTH, "2246": "go ridge"},
        },
        {
            "id": 2904,
            "uid": [12904],
            "title": ["[Obsidian Pass, Platform]"],
            "wayto": {"2903": "go frame"},
        },
        {"id": 2903, "uid": [12903], "title": ["[Obsidian Pass, Frame]"]},
        {"id": 2246, "uid": [12246], "title": ["[Obsidian Pass, Ridge]"]},
    ]
)


def test_the_gondola_edge_is_a_ride_in_its_if_form_with_its_direction():
    from client.game.mapdb import ride_args

    assert ride_of(GONDOLA_SOUTH) == "gondola"
    assert ride_args(GONDOLA_SOUTH) == "south"
    assert ride_args(FALDESU_NORTH) == "haven"
    assert walkable(GONDOLA_SOUTH)
    assert GONDOLA.graph[2249][2904]["seconds"] == RIDE_SECONDS


class GondolaHandle(FakeHandle):
    """GO GONDOLA answers "away" (no cab; the platform's story then
    brings it) or "aboard" (the cab, a compass frame); the ride's story
    ends with the soft bump; OUT lands like any move."""

    # Captured 2026-09-18 on the first ride.
    AWAY = (
        "There is no wooden gondola here.  You'll have to wait for it to come "
        "back around.\n"
    )
    DOOR = "The gondola stops on the platform and the door silently swings open.\n"
    BUMP = "With a soft bump, the gondola comes to a stop at its destination.\n"

    def __init__(self, uids, answers):
        super().__init__(uids)
        self.answers = list(answers)
        self.answer = None
        self.story = []

    def put(self, command):
        super().put(command)
        if command == "go gondola":
            answer = self.answers.pop(0)
            if answer == "away":
                self.answer, self.story = [("", self.AWAY)], [self.DOOR]
            else:
                self.answer, self.story = [("compass", "")], [self.BUMP]
        elif command == "out":
            self.state.room_uid = self._uids.pop(0)
            self.answer = [("compass", "")]
        elif command in ("north", "south"):
            self.answer = []  # the cab's way: no room change
        else:
            self.answer = None

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if streams is None:
            if self.answer is None:
                return super().get(timeout, streams)
            return self.answer.pop(0) if self.answer else None
        return self.story.pop(0) if self.story else None


def test_walk_waits_for_the_gondola_rides_it_and_steps_off(monkeypatch):
    monkeypatch.setattr(walker, "GONDOLA_ANSWER_SECONDS", 0.05)
    monkeypatch.setattr(walker, "GONDOLA_WAIT_SECONDS", 0.05)
    handle = GondolaHandle(uids=[12904, 12903], answers=["away", "aboard"])
    handle.state.room_uid = 12249
    assert walker.walk(handle, GONDOLA, [2903], describe="the frame") is True
    assert puts_of(handle) == ["go gondola", "go gondola", "south", "out", "go frame"]
    assert any("no gondola at the platform" in echo for echo in handle.echoes)
    assert any("aboard the gondola" in echo for echo in handle.echoes)


# --- a climb turned back twice is a closed edge (#211) ----------------------
AROUND = MapDB(
    [
        {
            "id": 6153,
            "uid": [224005],
            "title": ["[Wilderness, Deep Forest]"],
            "wayto": {"5705": "climb felled tree", "6154": "west"},
        },
        {"id": 5705, "uid": [224006], "title": ["[Wilderness, Deep Forest]"]},
        {
            "id": 6154,
            "uid": [224007],
            "title": ["[Wilderness, Long Way]"],
            "wayto": {"5705": "north"},
        },
    ]
)


class ClimbAroundHandle(ClimbHandle):
    """The climb answers the script; a plain move lands from the uids."""

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if self.pending:
            return self.pending.pop(0)
        if streams is None and puts_of(self)[-1:] != ["climb felled tree"]:
            return FakeHandle.get(self, timeout, streams)
        return None


def test_a_climb_turned_back_twice_is_routed_around():
    handle = ClimbAroundHandle(uids=[224007, 224006], answers=["refused", "vertigo"])
    handle.state.room_uid = 224005
    assert walker.walk(handle, AROUND, [5705], describe="the far side") is True
    puts = puts_of(handle)
    assert puts.count("climb felled tree") == 2
    assert puts[-2:] == ["west", "north"]
    assert "retreat" not in puts
    assert any("going round" in echo for echo in handle.echoes)


# --- an exit the game cannot find is a closed edge --------------------------
PANEL = MapDB(
    [
        {
            "id": 9953,
            "uid": [19953],
            "title": ["[Riverbank Mudflats]"],
            "wayto": {"9954": "go panel", "9952": "south"},
        },
        {"id": 9954, "uid": [19954], "title": ["[Riverbank Mudflats, Rough Stairway]"]},
        {
            "id": 9952,
            "uid": [19952],
            "title": ["[Riverbank Mudflats]"],
            "wayto": {"9954": "north"},
        },
    ]
)
NOT_FOUND = "I could not find what you were referring to.\n"  # captured 2026-09-18


class NoWayHandle(FakeHandle):
    def __init__(self, uids):
        super().__init__(uids)
        self.pending = []

    def put(self, command):
        super().put(command)
        if command == "go panel":
            self.pending = [("", NOT_FOUND)]

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if self.pending:
            return self.pending.pop(0)
        if puts_of(self)[-1:] == ["go panel"]:
            return None
        return super().get(timeout, streams)


def test_an_exit_the_game_cannot_find_is_routed_around():
    handle = NoWayHandle(uids=[19952, 19954])
    handle.state.room_uid = 19953
    assert walker.walk(handle, PANEL, [9954]) is True
    assert puts_of(handle) == ["go panel", "south", "north"]
    assert "retreat" not in puts_of(handle)
    assert any("closed to you" in echo for echo in handle.echoes)


# Captured 2026-09-18 on Obsidian Pass's silverwood branch: the dizziness
# refusal names the branch, not a tree.
DIZZY_BRANCH = (
    "Trying to judge the climb, you peer over the edge.  A wave of dizziness "
    "hits you, and you back away from the branch.\n"
)


def test_the_dizziness_refusal_is_known_for_any_climb():
    assert any(needle in DIZZY_BRANCH for needle in walker.CLIMB_REFUSALS)


class BranchHandle(ClimbAroundHandle):
    """The branch: dizziness first (a stall until the table knew it),
    then hard going on the retry."""

    ANSWERS = dict(ClimbHandle.ANSWERS, branch=DIZZY_BRANCH)


def test_a_climb_refused_on_the_stall_retry_is_routed_around_too(monkeypatch):
    # Even when the first answer reads as a stall, a refusal on the
    # retry closes the edge instead of stopping the walk.
    monkeypatch.setattr(
        walker,
        "CLIMB_REFUSALS",
        tuple(n for n in walker.CLIMB_REFUSALS if "back away" not in n),
    )
    handle = BranchHandle(uids=[224007, 224006], answers=["branch", "hard_going"])
    handle.state.room_uid = 224005
    assert walker.walk(handle, AROUND, [5705]) is True
    puts = puts_of(handle)
    assert puts.count("climb felled tree") == 2
    assert puts[-2:] == ["west", "north"]
    assert any("turned back for you" in echo for echo in handle.echoes)
