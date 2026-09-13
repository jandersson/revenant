"""How ;forage trains Outdoorsmanship — these tests are the manual.

COLLECT <item> PRACTICE in a room the map tags with the item (walking
to the nearest one otherwise), the roundtime waited out, until the
skill mind-locks, a count runs out, "return" is typed, danger, or
three empty answers in a row before anything was found (ten after: a
failed try answers the same as an empty room). The wordings were
captured on the first run, 2026-09-14.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _forage():
    spec = importlib.util.spec_from_file_location(
        "forage_script", REPO / "scripts/forage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


forage = _forage()
forage.COLLECT_SECONDS = 0.01
forage.TAIL_SECONDS = 0.01

STREET = "[The Crossing, Hodierna Way]"
MAP = MapDB(
    [
        {
            "id": 732,
            "uid": [1732],
            "title": [STREET],
            "tags": ["rock", "dirt"],
            "wayto": {"733": "east"},
        },
        {
            "id": 733,
            "uid": [1733],
            "title": ["[The Crossing, Alamhif Trace]"],
            "tags": [],
            "wayto": {"732": "west"},
        },
    ]
)

EMPTY = "You forage around but are unable to find anything.\nRoundtime: 6 sec."
PRACTICED = (
    "You wander around and poke your fingers into a few places, wondering what "
    "you might find.\nRoundtime: 6 sec."
)
FOUND = "You find something dead and lifeless, is this what you were looking for?"
TRIED = (
    "You are certain you could find what you were looking for, if you had a bit "
    "more luck.\nRoundtime: 6 sec."
)
ODD = "Something odd happens.\nRoundtime: 15 sec."


class Fake:
    """A script handle: each COLLECT gets the next scripted answer."""

    def __init__(self, answers, experience=None, room=732, hostiles=None):
        self.answers = list(answers)
        self.sent = []
        self.echoed = []
        self.commands = []
        self.pending = []
        self.walks = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience=experience or {},
            hostiles=hostiles or {},
            room=room,
            room_title=STREET,
        )

    def put(self, command):
        self.sent.append(command)
        answer = self.answers.pop(0) if self.answers else ""
        self.pending = [line + "\n" for line in answer.splitlines()]

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def command(self, timeout=None):
        return self.commands.pop(0) if self.commands else None

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


@pytest.fixture
def travel(monkeypatch):
    def walk(s, db, goals, describe="", avoid=()):
        s.walks.append(set(goals))
        s.state.room = min(goals)
        return True

    monkeypatch.setattr(forage, "walk", walk)
    monkeypatch.setattr(forage, "locate", lambda db, state: state.room)
    return walk


def _exp(mindstate):
    return {"Outdoorsmanship": {"rank": 5, "percent": 0, "mindstate": mindstate}}


def test_the_arguments_are_the_item_a_count_and_here():
    assert forage.parse_args([]) == {"item": "rock", "count": 0, "here": False}
    assert forage.parse_args(["dirt", "5", "here"]) == {
        "item": "dirt",
        "count": 5,
        "here": True,
    }


def test_collects_the_item_with_practice_until_the_count_runs_out(travel):
    s = Fake([PRACTICED, FOUND, PRACTICED], experience=_exp(10))
    reason, collected = forage.run(s, forage.parse_args(["rock", "3"]), db=MAP)
    assert s.sent == ["collect rock practice"] * 3
    assert (reason, collected) == ("3 collect(s) done", 3)
    assert s.walks == []  # room 732 has rocks on the map
    assert not any("unrecognized" in text for text in s.echoed)


def test_stops_at_mind_lock_before_collecting(travel):
    s = Fake([PRACTICED], experience=_exp(34))
    reason, collected = forage.run(s, forage.parse_args([]), db=MAP)
    assert (reason, collected) == ("Outdoorsmanship mind-locked", 0)
    assert s.sent == []


def test_walks_to_the_nearest_room_the_map_tags_with_the_item(travel):
    s = Fake([PRACTICED], experience=_exp(10), room=733)
    forage.run(s, forage.parse_args(["rock", "1"]), db=MAP)
    assert s.walks == [{732}]
    assert s.sent == ["collect rock practice"]
    # `here` collects where you stand, map or no map.
    s = Fake([PRACTICED], experience=_exp(10), room=733)
    forage.run(s, forage.parse_args(["rock", "1", "here"]), db=MAP)
    assert s.walks == []
    # An item the map knows nowhere is refused with the way round.
    s = Fake([PRACTICED], experience=_exp(10))
    reason, _ = forage.run(s, forage.parse_args(["moss"]), db=MAP)
    assert reason == "no room to collect in"
    assert any("try ;forage moss here" in text for text in s.echoed)


def test_three_empty_answers_before_any_find_end_the_run_ten_after(travel):
    s = Fake([EMPTY, EMPTY, EMPTY, PRACTICED], experience=_exp(10))
    reason, collected = forage.run(s, forage.parse_args([]), db=MAP)
    assert (len(s.sent), collected) == (3, 0)
    assert reason == "nothing to collect here (3 empty answers in a row)"
    # A failed try in a room with rocks answers the same as an empty
    # room (2026-09-14): once something was found, ten in a row it is.
    s = Fake([PRACTICED] + [EMPTY] * 10 + [PRACTICED], experience=_exp(10))
    reason, collected = forage.run(s, forage.parse_args([]), db=MAP)
    assert (len(s.sent), collected) == (11, 1)
    assert reason == "nothing to collect here (10 empty answers in a row)"
    s = Fake([PRACTICED, EMPTY, EMPTY, EMPTY, PRACTICED], experience=_exp(10))
    reason, collected = forage.run(s, forage.parse_args(["rock", "2"]), db=MAP)
    assert (reason, collected) == ("2 collect(s) done", 2)


def test_a_near_miss_counts_as_a_try_and_keeps_the_run_going(travel):
    # "... if you had a bit more luck." says the item is here (2026-09-14).
    s = Fake([EMPTY, EMPTY, TRIED, EMPTY, EMPTY, EMPTY], experience=_exp(10))
    reason, collected = forage.run(s, forage.parse_args([]), db=MAP)
    assert (len(s.sent), collected) == (6, 1)
    assert reason.startswith("nothing to collect here (3")
    assert not any("unrecognized" in text for text in s.echoed)


def test_an_answer_outside_the_table_is_reported_once_and_counts(travel):
    s = Fake([ODD] * 3, experience=_exp(10))
    reason, collected = forage.run(s, forage.parse_args(["rock", "3"]), db=MAP)
    assert collected == 3
    assert sum("unrecognized collect answer" in text for text in s.echoed) == 1


def test_return_danger_and_death_end_the_run(travel):
    s = Fake([PRACTICED] * 3, experience=_exp(10))
    s.commands = ["return"]
    assert forage.run(s, forage.parse_args([]), db=MAP) == ("returning on request", 0)
    s = Fake([PRACTICED], experience=_exp(10), hostiles={"1": True})
    assert forage.run(s, forage.parse_args([]), db=MAP)[0] == "hostiles in the room"
    s = Fake([PRACTICED], experience=_exp(10))
    s.dead = True
    assert forage.run(s, forage.parse_args([]), db=MAP)[0] == "you are dead"
