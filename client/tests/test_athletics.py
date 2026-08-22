"""How ;athletics trains — these tests are the manual.

Three modes: bare ;athletics walks to the optimal ladder rung for the
current rank and climbs its loop, advancing when gains go stale;
;athletics list prints the ladder advice; ;athletics <moves> trains a
manual loop in place. All modes pause at mind-lock.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _athletics():
    spec = importlib.util.spec_from_file_location(
        "athletics_script", REPO / "scripts/athletics.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


athletics = _athletics()


class LoopDone(Exception):
    """Raised by the fake handle to end the forever-loops."""


class FakeHandle:
    """A Script-handle stand-in: records the calls, ends after a budget
    of sleeps (the way ;stop ends the thread via ScriptStopped)."""

    def __init__(self, args, mindstates=(), sleeps=10, exp_response=None):
        self.args = args
        self.calls = []
        self.echoes = []
        # Each sleep consumes the next mindstate, so a test scripts the
        # drain: [34, 34, 20] locks for two polls, then resumes.
        self._mindstates = list(mindstates)
        self._sleeps = sleeps
        self._exp_response = exp_response  # the EXP ATHLETICS line, if any
        self.state = SimpleNamespace(experience={})
        self._apply_mindstate(rank=10)

    def _apply_mindstate(self, rank=7):
        if self._mindstates:
            self.state.experience = {
                "Athletics": {
                    "rank": rank,
                    "percent": 0,
                    "mindstate": self._mindstates[0],
                }
            }

    def put(self, command):
        self.calls.append(("put", command))

    def get(self, timeout=None, streams=("",)):
        return self.lines.pop(0) if getattr(self, "lines", None) else None

    def waitrt(self):
        self.calls.append(("waitrt",))

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        self.calls.append(("waitfor",) + patterns)
        return self._exp_response

    def sleep(self, seconds):
        self.calls.append(("sleep", seconds))
        if len(self._mindstates) > 1:
            self._mindstates.pop(0)
            self._apply_mindstate()
        self._sleeps -= 1
        if self._sleeps <= 0:
            raise LoopDone()

    def echo(self, text):
        self.echoes.append(text)


# The trellis and oak rungs, as the community map describes them.
LADDER_MAP = MapDB(
    [
        {
            "id": 13527,
            "title": ["[East Lawn]"],
            "wayto": {"13529": "climb moonstone trellis"},
        },
        {
            "id": 13529,
            "title": ["[Garden]"],
            "wayto": {"13527": "climb moonstone trellis"},
        },
        {"id": 1068, "title": ["[Greensward]"], "wayto": {"14134": "climb oak tree"}},
        {"id": 14134, "title": ["[Tree House]"], "wayto": {"1068": "climb oak tree"}},
    ]
)


def test_list_mode_probes_the_game_when_the_exp_window_is_empty():
    line = "       Athletics:      3 00.00% clear          (0/34)"
    handle = FakeHandle(args=["list"], exp_response=line)
    athletics.main(handle)
    assert [c for c in handle.calls if c[0] == "put"] == [("put", "exp athletics")]
    text = "\n".join(handle.echoes)
    assert "rank 3" in text
    assert "felled tree" in text  # 0-19 rung in reach at rank 3
    assert "Siergelde" not in text  # 20+ rung still gated


def test_list_mode_shows_rungs_for_a_known_rank():
    handle = FakeHandle(args=["list"], mindstates=[5])
    handle.state.experience["Athletics"]["rank"] = 22
    athletics.main(handle)
    text = "\n".join(handle.echoes)
    assert "rank 22" in text
    assert "Siergelde" in text
    assert "felled tree" not in text
    assert "next up at rank 30" in text


def test_recommendations_without_a_rank_show_starting_rungs():
    lines = athletics.recommendations(None)
    text = "\n".join(lines)
    assert "rank unknown" in text
    assert "trellis" in text
    assert "Siergelde" not in text  # gated rungs stay hidden


def test_manual_mode_cycles_commands_with_roundtime_between():
    handle = FakeHandle(args=["climb up | climb down"], sleeps=3)
    with pytest.raises(LoopDone):
        athletics.main(handle)
    assert handle.calls == [
        ("put", "climb up"),
        ("waitrt",),
        ("sleep", athletics.PAUSE),
        ("put", "climb down"),
        ("waitrt",),
        ("sleep", athletics.PAUSE),
        ("put", "climb up"),
        ("waitrt",),
        ("sleep", athletics.PAUSE),
    ]


def test_pauses_while_mind_locked_and_resumes_after_draining():
    handle = FakeHandle(args=["swim north"], mindstates=[34, 34, 20, 20, 20], sleeps=6)
    with pytest.raises(LoopDone):
        athletics.main(handle)
    # Locked: two mindstate polls before anything is sent to the game.
    assert handle.calls[0] == ("sleep", athletics.LOCK_POLL)
    assert handle.calls[1] == ("sleep", athletics.LOCK_POLL)
    assert handle.calls[2] == ("put", "swim north")
    assert any("mind-locked" in echo for echo in handle.echoes)
    assert any("resuming" in echo for echo in handle.echoes)


def test_mindstate_handles_missing_state():
    assert athletics.mindstate(None) is None
    assert athletics.mindstate(SimpleNamespace(experience={})) is None
    entry = {"Athletics": {"rank": 1, "percent": 0, "mindstate": 7}}
    assert athletics.mindstate(SimpleNamespace(experience=entry)) == 7


def test_going_stale_needs_consecutive_low_flat_reports():
    assert not athletics.going_stale([5, 5])  # too few reports
    assert athletics.going_stale([5, 5, 5])
    assert athletics.going_stale([9, 7, 6])  # low and not improving
    assert not athletics.going_stale([5, 8, 12])  # improving
    assert not athletics.going_stale([20, 20, 20])  # healthy mindstate
    assert not athletics.going_stale([5, None, 5])  # unknowns don't count


def test_optimal_rung_is_the_hardest_in_reach():
    # Within the low-0 tie, the later (pear practice) entry wins.
    assert athletics.optimal_rung(3)["label"].startswith("pear tree practice")
    assert athletics.optimal_rung(None)["label"].startswith("pear tree practice")
    assert athletics.optimal_rung(7)["label"].startswith("oak tree")
    assert athletics.optimal_rung(25)["label"].startswith("rise")
    assert athletics.optimal_rung(60)["label"].startswith("mine ladder")
    # The #87 extension: rank 100+ trains in town, on the battlements.
    assert athletics.optimal_rung(144)["label"].startswith("NE gate embrasure")
    # At the 150 tie the later (NE gate, deeper band) entry wins.
    assert athletics.optimal_rung(150)["label"].startswith("NE gate wall")


def test_climb_loop_reads_the_maps_own_edges():
    assert athletics.climb_loop(LADDER_MAP, 13527, 13529) == [
        "climb moonstone trellis",
        "climb moonstone trellis",
    ]
    assert athletics.climb_loop(LADDER_MAP, 13527, 999) is None


def test_rung_plan_paces_travel_climbs_and_spams_practice():
    travel = {"low": 0, "high": 34, "label": "trellis", "bottom": 13527, "top": 13529}
    commands, pace = athletics.rung_plan(LADDER_MAP, travel)
    assert commands == ["climb moonstone trellis", "climb moonstone trellis"]
    assert pace == athletics.CLIMB_TIMER_PACE  # the 45-60s award timer

    practice = {
        "low": 0,
        "high": 80,
        "label": "pear",
        "room": 1455,
        "practice": "pear tree",
    }
    commands, pace = athletics.rung_plan(LADDER_MAP, practice)
    assert commands == ["climb practice pear tree"]
    assert pace == athletics.PAUSE  # timer-exempt: tight loop


def test_auto_mode_walks_to_the_rung_and_advances_when_stale():
    # Rank 3 at start (pear practice rung); the first sleep bumps the
    # fake exp entry to rank 7, so once the pear goes stale the oak
    # rung (5-60) is in reach — but not the apple (10+), so the ladder
    # advances exactly once and then carries on at the oak.
    handle = FakeHandle(args=[], mindstates=[5, 5], sleeps=400)
    handle.state.experience["Athletics"]["rank"] = 3
    walks = []

    def fake_walk(s, db, goals, describe=""):
        walks.append(list(goals))
        return True

    with pytest.raises(LoopDone):
        athletics.auto_train(handle, db=LADDER_MAP, walk=fake_walk)
    assert walks[0] == [1455]  # pear practice room first
    assert ("put", "climb practice pear tree") in handle.calls
    assert walks[1] == [1068]  # then the oak after going stale
    assert any("moving up the ladder" in echo for echo in handle.echoes)
    assert ("put", "climb oak tree") in handle.calls
    # Travel climbs at the oak are paced to the award timer — slept at
    # the lap's end in danger-poll chunks, never as one blind window.
    assert ("sleep", athletics.DANGER_POLL) in handle.calls
    assert ("sleep", athletics.CLIMB_TIMER_PACE) not in handle.calls


def test_auto_mode_stops_cleanly_when_the_walk_fails():
    handle = FakeHandle(args=[], mindstates=[5])
    handle.state.experience["Athletics"]["rank"] = 3

    def failing_walk(s, db, goals, describe=""):
        return False

    athletics.auto_train(handle, db=LADDER_MAP, walk=failing_walk)
    assert any("could not reach" in echo for echo in handle.echoes)
    assert ("put", "climb practice pear tree") not in handle.calls


def _state(**overrides):
    defaults = dict(experience={}, hostiles={}, vitals={}, indicator={})
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class PracticeHandle(FakeHandle):
    """Every practice send is answered by the game — the wording is the
    test's to choose (the #89 capture set)."""

    def __init__(self, *args, response, **kwargs):
        super().__init__(*args, **kwargs)
        self.lines = []
        self.response = response

    def put(self, command):
        super().put(command)
        self.lines.append(self.response)


def test_practice_is_started_once_and_watched_not_spammed():
    # climb practice is a continuous activity (captured 2026-08-22 at
    # the NE gate embrasure, #89): the old per-second re-send earned
    # "You should stop practicing ..." once a second.
    handle = PracticeHandle(
        (),
        mindstates=(5,),
        sleeps=8,
        response="You begin to practice your climbing skills.",
    )
    with pytest.raises(LoopDone):
        athletics.train(handle, ["climb practice embrasure"], practice=True)
    puts = [call for call in handle.calls if call[0] == "put"]
    assert puts == [("put", "climb practice embrasure")]


def test_practice_refusal_counts_as_already_running():
    handle = PracticeHandle(
        (),
        mindstates=(5,),
        sleeps=8,
        response=(
            "You should stop practicing your Athletics skill before you do that."
        ),
    )
    with pytest.raises(LoopDone):
        athletics.train(handle, ["climb practice embrasure"], practice=True)
    puts = [call for call in handle.calls if call[0] == "put"]
    assert len(puts) == 1


def test_practice_restarts_when_the_activity_ends():
    # The end wording is an assumption until captured (#89).
    handle = PracticeHandle(
        (),
        mindstates=(5,),
        sleeps=8,
        response="You stop practicing your climbing.",
    )
    with pytest.raises(LoopDone):
        athletics.train(handle, ["climb practice embrasure"], practice=True)
    puts = [call for call in handle.calls if call[0] == "put"]
    assert len(puts) >= 2


def test_burden_warning_only_when_meaningfully_burdened():
    # Encumbrance penalizes every climb (client/climbs.py's conditions
    # note); auto mode probes ENC once and warns from Somewhat up.
    heavy = FakeHandle((), exp_response="   Encumbrance : Heavily Burdened")
    athletics.check_burden(heavy)
    assert ("put", "encumbrance") in heavy.calls
    assert any("Heavily Burdened" in echo for echo in heavy.echoes)

    light = FakeHandle((), exp_response="   Encumbrance : Light Burden")
    athletics.check_burden(light)
    assert light.echoes == []

    silent = FakeHandle((), exp_response=None)  # ENC answer never came
    athletics.check_burden(silent)
    assert silent.echoes == []


def test_danger_classifies_death_hostiles_and_low_health():
    assert athletics.danger(_state()) is None
    assert athletics.danger(_state(hostiles={"78646435": False})) == "hostiles"
    assert athletics.danger(_state(vitals={"health": 40})) == "hurt"
    assert athletics.danger(_state(vitals={"health": 65})) is None
    # Death outranks everything else.
    assert (
        athletics.danger(
            _state(indicator={"IconDEAD": "y"}, hostiles={"78646435": True})
        )
        == "dead"
    )


class DangerHandle(FakeHandle):
    """Hostiles occupy the room for the first few sleeps, then clear —
    the cougars-arrive capture (#72), with a survivable ending."""

    def __init__(self, *args, hostile_sleeps=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.state.hostiles = {"78646435": False}
        self._hostile_sleeps = hostile_sleeps

    def sleep(self, seconds):
        self._hostile_sleeps -= 1
        if self._hostile_sleeps <= 0:
            self.state.hostiles = {}
        super().sleep(seconds)


def test_train_breaks_off_and_escapes_hostiles():
    handle = DangerHandle((), mindstates=(5,), sleeps=30, hostile_sleeps=2)
    with pytest.raises(LoopDone):
        athletics.train(handle, ["climb rise", "climb down"], pace=0)
    assert any("hostiles here" in echo for echo in handle.echoes)
    assert any("clear of hostiles" in echo for echo in handle.echoes)
    # Escape moved along the training edge, and climbing resumed after.
    assert ("put", "climb rise") in handle.calls


def test_train_keeps_trying_when_escape_fails():
    handle = DangerHandle((), mindstates=(5,), sleeps=12, hostile_sleeps=99)
    with pytest.raises(LoopDone):
        athletics.train(handle, ["climb rise", "climb down"], pace=0)
    assert any("can't get clear" in echo for echo in handle.echoes)


class StalemateHandle(FakeHandle):
    """The cave-bear stalemate (#86), as captured: the bear holds the
    tunnel, every escape climbs into the bear-free crevice below, and
    every re-approach climb summons it right back."""

    TUNNEL, CREVICE = 459003, 459002
    BEAR = {"79912449": True}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state.room_uid = self.TUNNEL
        self.state.hostiles = dict(self.BEAR)

    def put(self, command):
        super().put(command)
        if command.startswith("climb"):
            if self.state.room_uid == self.TUNNEL:
                self.state.room_uid = self.CREVICE
                self.state.hostiles = {}
            else:
                self.state.room_uid = self.TUNNEL
                self.state.hostiles = dict(self.BEAR)


def test_train_gives_up_a_contested_spot():
    # Escape alone just ping-pongs (#86): spawn areas never empty on
    # their own, so the third hostile break-off inside the window ends
    # training here instead of climbing back into the bear forever.
    handle = StalemateHandle((), mindstates=(5,), sleeps=60)
    result = athletics.train(handle, ["climb rise", "climb down"], pace=0)
    assert result == "contested"
    breakoffs = [echo for echo in handle.echoes if "hostiles here" in echo]
    assert len(breakoffs) == athletics.CONTESTED_LIMIT
    assert any("contested" in echo for echo in handle.echoes)


def test_manual_mode_stops_with_advice_when_contested():
    handle = StalemateHandle(["climb rise", "|", "climb down"], sleeps=60)
    handle.state.experience = {"Athletics": {"rank": 30, "percent": 0, "mindstate": 5}}
    athletics.main(handle)
    assert any(";athletics list" in echo for echo in handle.echoes)


class OakCampedHandle(FakeHandle):
    """A creature camps the Greensward (the oak rung's bottom room);
    the Tree House above is clear — the stalemate, auto-mode edition."""

    BEAR = {"79912449": True}

    def _sync(self):
        here = getattr(self.state, "room_uid", None)
        self.state.hostiles = dict(self.BEAR) if here == 1068 else {}

    def put(self, command):
        super().put(command)
        if command == "climb oak tree":
            self.state.room_uid = 14134 if self.state.room_uid == 1068 else 1068
        self._sync()


def test_auto_mode_abandons_a_contested_rung_for_the_next_best():
    # Rank 7: the oak (5-60) is optimal; the camped Greensward turns it
    # contested, and the ladder falls back to the pear practice rung
    # instead of stopping (#86).
    handle = OakCampedHandle(args=[], mindstates=[5], sleeps=200)
    handle.state.experience["Athletics"]["rank"] = 7
    walks = []

    def fake_walk(s, db, goals, describe=""):
        walks.append(list(goals))
        s.state.room_uid = goals[0]
        if hasattr(s, "_sync"):
            s._sync()
        return True

    with pytest.raises(LoopDone):
        athletics.auto_train(handle, db=LADDER_MAP, walk=fake_walk)
    assert walks[0] == [1068]  # the oak bottom first
    assert any("contested" in echo for echo in handle.echoes)
    assert any("abandoning" in echo for echo in handle.echoes)
    assert walks[1] == [1455]  # the pear practice rung, next-best
    assert ("put", "climb practice pear tree") in handle.calls


def test_award_timer_wait_sits_at_the_laps_start_not_mid_loop():
    # Repeat climbs inside the award window grant nothing but cost
    # nothing — the loop closes home first, then sits the window out
    # there in danger-poll chunks, never idling deep in a spawn room.
    handle = FakeHandle((), mindstates=(5,), sleeps=30)
    with pytest.raises(LoopDone):
        athletics.train(
            handle, ["climb up", "climb down"], pace=athletics.CLIMB_TIMER_PACE
        )
    sequence = [call for call in handle.calls if call[0] in ("put", "sleep")]
    first_up = sequence.index(("put", "climb up"))
    first_down = sequence.index(("put", "climb down"))
    between = [
        call for call in sequence[first_up + 1 : first_down] if call[0] == "sleep"
    ]
    assert between and all(seconds <= athletics.PAUSE for _, seconds in between)
    after = [call for call in sequence[first_down + 1 :] if call[0] == "sleep"]
    assert ("sleep", athletics.DANGER_POLL) in after


def test_train_stops_when_dead():
    handle = FakeHandle((), mindstates=(5,), sleeps=50)
    handle.state.indicator = {"IconDEAD": "y"}
    assert athletics.train(handle, ["climb rise"]) == "danger"
    assert not [call for call in handle.calls if call[0] == "put"]
    assert any("dead" in echo for echo in handle.echoes)


class HurtHandle(FakeHandle):
    """Health starts low and recovers after a few polls."""

    def __init__(self, *args, hurt_sleeps=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.state.vitals = {"health": 30}
        self._hurt_sleeps = hurt_sleeps

    def sleep(self, seconds):
        self._hurt_sleeps -= 1
        if self._hurt_sleeps <= 0:
            self.state.vitals = {"health": 100}
        super().sleep(seconds)


def test_train_holds_until_health_recovers():
    handle = HurtHandle((), mindstates=(5,), sleeps=20)
    with pytest.raises(LoopDone):
        athletics.train(handle, ["climb rise"], pace=0)
    assert any("health below" in echo for echo in handle.echoes)
    assert any("health recovered" in echo for echo in handle.echoes)
    assert ("put", "climb rise") in handle.calls


def test_escape_bursts_retreat_retreat_move():
    # The field-proven recipe (docs/combat.md): both retreats and the
    # move go out back to back — no waits between them for a critter
    # to re-advance through.
    handle = DangerHandle((), mindstates=(5,), sleeps=10, hostile_sleeps=1)
    assert athletics.escape(handle, ["climb rise", "climb down"]) is True
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert puts[:3] == ["retreat", "retreat", "climb rise"]


def test_escape_succeeds_when_the_room_changes_despite_hostiles():
    # Two retreats reach missile range, where climbing is legal even
    # with the creature still present — a bear that won't leave must
    # not pin the trainer (captured 2026-08-22).
    class MovingHandle(DangerHandle):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.state.room_uid = 7233

        def sleep(self, seconds):
            # The move landed: new room, hostiles still listed behind us.
            self.state.room_uid = 7234
            FakeHandle.sleep(self, seconds)

    handle = MovingHandle((), mindstates=(5,), sleeps=10, hostile_sleeps=99)
    assert athletics.escape(handle, ["climb ladder", "climb down"]) is True
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert puts == ["retreat", "retreat", "climb ladder"]
