"""How ;hunt runs a training loop from a profile — these tests are the manual.

Ready the weapon and stance, attack the prey until the room is empty,
skin and search each kill (skins into the loot container, gems into the
pouch), move along the ground's rooms, and end on the health floor, a
stop word, mind-lock, the kill fuse, or an empty ground — walking home
after. The game wordings here are the assumptions docs/hunting.md lists.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.mapdb import MapDB
from client.profile import DEFAULTS

REPO = pathlib.Path(__file__).parents[2]


def _hunt():
    spec = importlib.util.spec_from_file_location(
        "hunt_script", REPO / "scripts/hunt.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hunt = _hunt()
hunt.COLLECT_SECONDS = 0.01
hunt.TAIL_SECONDS = 0.01
hunt.SETTLE_SECONDS = 0.0
hunt.EMPTY_ROOM_WAIT = 0

YARD = "[Barana's Shipyard, Lumber Storage]"
GROUND = MapDB(
    [
        {
            "id": 6046,
            "uid": [21101],
            "title": [YARD],
            "tags": ["rats"],
            "wayto": {"6047": "east"},
        },
        {
            "id": 6047,
            "uid": [21102],
            "title": [YARD],
            "tags": ["rats"],
            "wayto": {"6046": "west"},
        },
        {"id": 1, "uid": [1], "title": ["[Town Green]"], "tags": ["home"], "wayto": {}},
    ]
)

PROFILE = DEFAULTS | {
    "weapon": "handaxe",
    "weapon_container": "sack",
    "stance": "100 80 0",
    "prey": "rat",
    "skin": True,
    "loot_container": "sack",
    "home": "home",
}

KILL = "The rat slowly tips over and falls down."
SKINNED = "You skin the rat, obtaining a rat pelt."
NOTHING = "You search the rat.\nYou find nothing of value."


class Arena:
    """A scripted fight: each command prefix has a queue of answers, and
    an answer may be (text, effect) where effect(arena) changes state —
    the kill that empties the hostile list."""

    def __init__(
        self, answers, hostiles=("1",), health=100, room=6046, experience=None
    ):
        self.answers = {prefix: list(queue) for prefix, queue in answers.items()}
        self.sent = []
        self.echoed = []
        self.commands = []
        self.pending = []
        self.walks = []
        self.arrivals = {}  # room -> hostiles present on arrival
        self.room = room
        self.dead = False
        self.state = SimpleNamespace(
            name="Lanival",
            hostiles={exist: True for exist in hostiles},
            vitals={"health": health},
            compass=["west"],
            room_title=YARD,
            experience=experience or {},
            room=room,  # what the stubbed locate() answers
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command.startswith(prefix) and queue:
                answer = queue.pop(0)
                if isinstance(answer, tuple):
                    answer, effect = answer
                    effect(self)
                self.pending = [line + "\n" for line in answer.splitlines()]
                return

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


def kill(arena):
    arena.state.hostiles.clear()


@pytest.fixture
def travel(monkeypatch):
    """walk() and locate() over the Arena's own idea of where it is."""

    def walk(s, db, goals, describe="", avoid=()):
        s.walks.append(set(goals))
        s.room = s.state.room = min(goals)
        if s.room in s.arrivals:
            s.state.hostiles = dict(s.arrivals[s.room])
        return True

    monkeypatch.setattr(hunt, "walk", walk)
    monkeypatch.setattr(hunt, "locate", lambda db, state: state.room)
    return walk


def _run(arena, profile=PROFILE, travel_first=True):
    hunt.hunt(arena, dict(profile), GROUND, travel=travel_first)
    return arena


def test_readies_the_weapon_and_stance_walks_to_the_ground_then_hunts(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    )
    assert arena.walks[0] == {6046, 6047}
    assert arena.sent[:3] == [
        "get my handaxe from my sack",
        "stance set 100 80 0",
        "attack rat",
    ]
    assert any(text.startswith("hunt: rat down (1)") for text in arena.echoed)


def test_a_kill_is_skinned_stowed_and_searched(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    )
    after_kill = arena.sent[arena.sent.index("attack rat") + 1 :]
    assert after_kill[:3] == ["skin rat", "put my pelt in my sack", "search rat"]
    assert any("1 kill(s), 1 skin(s)" in text for text in arena.echoed)


def test_skinning_off_in_the_profile_skips_the_knife(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "search": [NOTHING]}),
        profile=PROFILE | {"skin": False},
    )
    assert not any(command.startswith("skin") for command in arena.sent)
    assert "search rat" in arena.sent


def test_a_gem_found_on_the_corpse_goes_in_the_pouch(travel):
    found = "You search the rat.\nYou find a small ruby."
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [found]}),
        profile=PROFILE | {"gem_pouch": "pouch"},
    )
    assert "get ruby" in arena.sent
    assert "put my ruby in my pouch" in arena.sent


def test_what_the_pouch_refuses_is_stowed_like_loot(travel):
    found = "You search the rat.\nYou find a rusty nail."
    arena = _run(
        Arena(
            {
                "attack": [(KILL, kill)],
                "skin": [SKINNED],
                "search": [found],
                "put my nail": ["You can't put that in there."],
            }
        ),
        profile=PROFILE | {"gem_pouch": "pouch"},
    )
    assert "put my nail in my pouch" in arena.sent
    assert "put my nail in my sack" in arena.sent


def test_an_empty_ground_ends_the_hunt_and_walks_home(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    )
    assert any("ground empty" in text for text in arena.echoed)
    assert arena.walks[-1] == {1}
    assert arena.sent[-1] == "put my handaxe in my sack"


def test_an_empty_room_moves_to_the_next_room_of_the_ground(travel):
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]}, hostiles=()
    )
    arena.arrivals = {6047: {"2": True}}
    _run(arena, travel_first=False)
    assert arena.walks[0] == {6047}
    assert "attack rat" in arena.sent
    assert any("hunt: room empty — moving on" == text for text in arena.echoed)


def test_below_the_health_floor_the_hunt_breaks_off_and_goes_home(travel):
    arena = _run(Arena({"attack": []}, health=40), travel_first=False)
    assert arena.sent[2:5] == ["retreat", "retreat", "west"]
    assert not any(command.startswith("attack") for command in arena.sent)
    assert any("health 40% below the floor" in text for text in arena.echoed)
    assert arena.walks[-1] == {1}


def test_the_stop_word_ends_the_hunt_before_the_next_swing(travel):
    arena = Arena({"attack": []})
    arena.commands = ["stop"]
    _run(arena, travel_first=False)
    assert not any(command.startswith("attack") for command in arena.sent)
    assert any("stopped on request" in text for text in arena.echoed)


def test_mind_locked_training_skills_end_the_hunt(travel):
    arena = Arena({"attack": []}, experience={"Small Edged": {"mindstate": 34}})
    _run(arena, profile=PROFILE | {"train_skills": ["Small Edged"]}, travel_first=False)
    assert not any(command.startswith("attack") for command in arena.sent)
    assert any("mind-locked" in text for text in arena.echoed)


def test_a_skill_not_yet_in_the_exp_window_counts_as_unlocked():
    state = SimpleNamespace(experience={"Evasion": {"mindstate": 34}})
    assert hunt.locked(state, ["Evasion", "Small Edged"]) is False
    assert hunt.locked(state, ["Evasion"]) is True
    assert hunt.locked(state, []) is False


def test_the_kill_fuse_ends_the_hunt(travel):
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]},
    )
    _run(arena, profile=PROFILE | {"max_kills": 1}, travel_first=False)
    assert any("kill fuse reached" in text for text in arena.echoed)


def test_a_corpse_soaking_swings_is_searched_away(travel):
    # docs/combat.md: after a kill, ATTACK resolves to the body.
    arena = Arena(
        {
            "attack": [("The rat is already quite dead.", kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena, travel_first=False)
    assert "search rat" in arena.sent


def test_nothing_to_skin_with_turns_skinning_off_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "skin": ["You have nothing to skin with!"],
            "search": [NOTHING, NOTHING],
        }
    )
    _run(arena, travel_first=False)
    assert arena.sent.count("skin rat") == 1
    assert any("skinning is off for this run" in text for text in arena.echoed)


def test_an_unrecognized_skin_answer_is_reported_not_guessed(travel):
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": ["The rat twitches."], "search": [NOTHING]}
    )
    _run(arena, travel_first=False)
    assert any(
        text.startswith("hunt: unrecognized skin answer 'The rat twitches.'")
        for text in arena.echoed
    )
    assert any("1 unrecognized answer(s)" in text for text in arena.echoed)


def test_kill_and_item_nouns_are_read_from_the_game_lines():
    assert hunt.kill_noun("The cougar slowly tips over and falls down.") == "cougar"
    assert hunt.kill_noun("A large rat goes still.") == "rat"
    assert hunt.kill_noun("You miss.") is None
    assert hunt.items_in("You skin the rat, obtaining a rat pelt.") == ["pelt"]
    assert hunt.items_in("You find a small ruby. You find some coins.") == [
        "ruby",
        "coins",
    ]
