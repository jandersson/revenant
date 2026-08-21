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
    assert athletics.optimal_rung(100)["label"].startswith("mine ladder")


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
    # Travel climbs at the oak are paced to the award timer.
    assert ("sleep", athletics.CLIMB_TIMER_PACE) in handle.calls


def test_auto_mode_stops_cleanly_when_the_walk_fails():
    handle = FakeHandle(args=[], mindstates=[5])
    handle.state.experience["Athletics"]["rank"] = 3

    def failing_walk(s, db, goals, describe=""):
        return False

    athletics.auto_train(handle, db=LADDER_MAP, walk=failing_walk)
    assert any("could not reach" in echo for echo in handle.echoes)
    assert ("put", "climb practice pear tree") not in handle.calls
