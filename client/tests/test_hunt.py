"""How ;hunt runs a training loop from a profile — these tests are the manual.

Ready the weapon and stance, attack the prey until the room is empty,
skin and search each kill (skins into the loot container, gems into the
pouch), move along the ground's rooms, and end on the health floor, a
stop word, mind-lock or the kill fuse — walking home after; an empty
ground is waited out, never left. The game wordings here are the
assumptions docs/hunting.md lists.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game import buffs
from client.game.mapdb import MapDB
from client.game.profile import DEFAULTS

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
hunt.MAX_ITERATIONS = 400  # a ground the arena cannot fill ends on the fuse
hunt.ADVANCE_WAIT = 0.01
buffs.PREPARE_SECONDS = 0.01
buffs.CAST_GAP_SECONDS = 0

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
            "wayto": {"6046": "west", "6048": "north"},
        },
        {
            "id": 6048,
            "uid": [21103],
            "title": ["[Barana's Shipyard, Gate]"],
            "tags": [],
            "wayto": {"6047": "south"},
        },
        {"id": 1, "uid": [1], "title": ["[Town Green]"], "tags": ["home"], "wayto": {}},
    ]
)

PROFILE = DEFAULTS | {
    "weapon": "handaxe",
    "cast_gap": 0,  # the cadence tests count casts per swing
    "weapon_container": "sack",
    "stance": "100 80 0",
    "prey": "rat",
    "skin": True,
    "loot_container": "sack",
    "home": "home",
}

# The kill line as captured on a rat (2026-09-05) and a badger
# (2026-09-14). "The rat slowly tips over and falls down." stood here
# until 2026-09-14: it is a knockdown (#197), see KNOCKED_DOWN.
KILL = "The rat falls to the ground and lies still."
KNOCKED_DOWN = (
    "The rat slowly tips over and falls down.\nYou also see a rat that appears stunned."
)
# Captured 2026-09-13 (#183): SMITE's own line, then the swing as usual.
SMITE_KILL = (
    "Drawing strength from your conviction, you execute a divinely inspired "
    "strike!\n" + KILL
)
# Captured 2026-09-05, the first live ;hunt: the kill line the script
# did not know, and the corpse answer with a two-word noun.
RAT_KILL = "The ship's rat falls to the ground and lies still."
RAT_CORPSE = "The ship's rat is already quite dead."
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


def test_a_held_skinning_knife_is_fetched_stowed_and_never_taken_for_the_skin(travel):
    # Grek's skinning knife (2026-09-14) cannot be worn: the hunt GETs
    # it before the cut and stows it after, and the hand it sits in is
    # not the skin's hand — with a worn bundle the cut goes straight in.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap my bundle": ["You tap a lumpy bundle that you are wearing."],
            "get my knife": ["You get a skinning knife from inside your canvas sack."],
            "skin": [
                "Working deftly, you skillfully remove a curved claw from the "
                "remains of a rat.\nYou carefully fit a curved claw into your bundle."
            ],
            "search": [NOTHING],
        }
    )
    arena.state.left_hand = {"noun": "knife", "exist": "1", "name": "skinning knife"}
    arena.state.right_hand = {
        "noun": "handaxe",
        "exist": "2",
        "name": "oak-hafted handaxe",
    }
    _run(arena, profile=PROFILE | {"skin_knife": "knife", "bundle": True})
    after_kill = arena.sent[arena.sent.index("attack rat") + 1 :]
    assert after_kill[:3] == ["get my knife", "skin rat", "put my knife in my sack"]
    assert "bundle" not in arena.sent
    assert not any("took no more" in text for text in arena.echoed)
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


class Patient(Arena):
    """An arena whose operator types ;hunt return once the loop has
    paused on an empty ground the given number of times."""

    def __init__(self, *args, pauses=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.pauses = pauses

    def echo(self, text):
        super().echo(text)
        if "ground empty" in text:
            self.pauses -= 1
            if self.pauses == 0:
                self.commands.append("return")


def test_an_empty_ground_is_waited_out_not_left(travel):
    # 2026-09-13, the operator: an empty ground is not a reason to go
    # home — pause after every empty lap and lap again until told.
    arena = Patient(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]}, pauses=3
    )
    _run(arena)
    waits = [text for text in arena.echoed if "ground empty" in text]
    assert len(waits) == 3 and "looking again" in waits[0]
    laps = sum(1 for text in arena.echoed if text == "hunt: room empty — moving on")
    assert laps >= 3 * hunt.EMPTY_LAPS * 2  # kept lapping between the pauses
    assert any("returning on request" in text for text in arena.echoed)
    assert arena.walks[-1] == {1}  # then home, on the word


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


def test_a_break_off_with_no_home_leaves_the_ground(travel):
    # #185 (2026-09-13): the loop broke off on the health floor with no
    # home and ended on the ground; the rats killed the character two
    # and a half hours later. Now: the nearest room off the ground.
    arena = _run(
        Arena({"attack": []}, health=40),
        profile=PROFILE | {"home": ""},
        travel_first=False,
    )
    assert arena.sent[2:5] == ["retreat", "retreat", "west"]
    assert arena.walks[-1] == {6048}  # the gate, the only room off the ground
    assert any("left the ground for" in text for text in arena.echoed)
    assert any("set home" in text for text in arena.echoed)


def test_off_ground_is_the_rooms_one_move_outside():
    assert hunt.off_ground(GROUND, [6046, 6047]) == {6048}
    assert hunt.off_ground(GROUND, [6048]) == {6047}


HURT = "Your body feels slightly battered.\nYou have deep cuts across the neck.\n"


def test_a_wound_at_the_floor_breaks_the_hunt_off_after_a_kill(travel):
    # HEALTH is asked after each kill; "deep cuts across the neck" is
    # harmful, the profile's floor.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
            "health": [HURT],
        }
    )
    _run(arena, profile=PROFILE | {"wound_floor": "harmful"}, travel_first=False)
    assert "health" in arena.sent
    assert any(
        "neck external harmful — at the wound floor" in text for text in arena.echoed
    )
    assert "put my handaxe in my sack" not in arena.sent  # walked home, still armed


def test_a_wound_below_the_floor_keeps_hunting(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
            "health": [HURT],
        }
    )
    _run(arena, profile=PROFILE | {"wound_floor": "severe"}, travel_first=False)
    assert "health" in arena.sent
    assert not any("wound floor" in text for text in arena.echoed)


def test_health_is_also_asked_when_the_bar_drops_mid_fight(travel):
    def hurt(arena):
        arena.state.vitals["health"] = 80

    arena = Arena(
        {
            "attack": [("You miss.", hurt), (KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
            "health": [CLEAN_HEALTH, CLEAN_HEALTH],
        }
    )
    _run(arena, profile=PROFILE | {"wound_floor": "harmful"}, travel_first=False)
    assert arena.sent.index("health") < arena.sent.index("skin rat")


def test_no_wound_floor_never_asks_health(travel):
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    _run(arena, travel_first=False)
    assert "health" not in arena.sent


CLEAN_HEALTH = "Your body feels at full strength.\nYou have no significant injuries.\n"


def test_the_return_word_ends_the_hunt_before_the_next_swing(travel):
    arena = Arena({"attack": []})
    arena.commands = ["return"]
    _run(arena, travel_first=False)
    assert not any(command.startswith("attack") for command in arena.sent)
    assert any("returning on request" in text for text in arena.echoed)


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


def test_the_captured_rat_kill_is_recognized_and_skinned(travel):
    arena = Arena(
        {"attack": [(RAT_KILL, kill)], "skin": [SKINNED], "search": [NOTHING]}
    )
    _run(arena, travel_first=False)
    assert "skin rat" in arena.sent
    assert any(text.startswith("hunt: rat down (1)") for text in arena.echoed)


# Captured 2026-09-12, the second live ;hunt: two skin successes the
# table did not know (the tail's line landed after the roundtime and
# the tail stayed in hand, so the next three skins refused), and the
# answers a corpse noun gets once the corpse is gone and a live rat
# matches it instead.
PELT_LOOSE = (
    "With preternatural poise, you work loose a sterling example of a rat "
    "pelt from the rat carcass."
)
TAIL_REMOVED = (
    "Working deftly, you skillfully remove a rat tail from the remains of a "
    "ship's rat.  The task is difficult, but the rewards are worth it."
)
HANDS_FULL = "You must have one hand free to skin."
SEARCHED_ALREADY = "The ship's rat has already been searched for that!"
NOT_DEAD_YET = "You should probably wait until a ship's rat is dead first."


def test_the_captured_skin_wordings_are_recognized_and_the_skin_stowed(travel):
    for line, item in ((PELT_LOOSE, "pelt"), (TAIL_REMOVED, "tail")):
        arena = Arena({"attack": [(KILL, kill)], "skin": [line], "search": [NOTHING]})
        _run(arena, travel_first=False)
        assert f"put my {item} in my sack" in arena.sent
        assert not any("unrecognized" in text for text in arena.echoed)


def test_a_full_hand_is_stowed_and_the_skin_tried_once_more(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [HANDS_FULL, TAIL_REMOVED],
            "search": [NOTHING],
        }
    )
    arena.state.left_hand = {"noun": "tail", "exist": "1", "name": "rat tail"}
    _run(arena, travel_first=False)
    first = arena.sent.index("skin rat")
    assert arena.sent[first : first + 4] == [
        "skin rat",
        "put my tail in my sack",
        "skin rat",
        "put my tail in my sack",
    ]


def test_a_full_hand_the_parser_cannot_name_is_stowed_by_side(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [HANDS_FULL, PELT_LOOSE],
            "search": [NOTHING],
        }
    )
    _run(arena, travel_first=False)
    first = arena.sent.index("skin rat")
    assert arena.sent[first : first + 3] == ["skin rat", "stow left", "skin rat"]


def test_a_knockdown_is_not_a_kill(travel):
    # #197: every capture of "slowly tips over and falls down" (a cougar
    # 2026-08-22, rats 2026-09-12/13, a badger 2026-09-14) was a stunned,
    # prone creature that stood back up; the loop had skinned and
    # searched it and counted a kill. Now it swings on.
    arena = Arena(
        {
            "attack": [(KNOCKED_DOWN, _stands), (KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena)
    assert arena.sent.count("skin rat") == 1
    assert arena.sent.count("search rat") == 1
    assert any("1 kill(s), 1 skin(s)" in text for text in arena.echoed)
    assert not any("rat down (2)" in text for text in arena.echoed)


def test_a_skin_that_found_the_live_one_is_a_gone_corpse_too(travel):
    # Captured 2026-09-14 on a striped badger: SKIN badger after the
    # kill reached the live badger still in the room.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": ["You can't skin something that's not dead!"],
            "search": [NOTHING],
        }
    )
    _run(arena)
    assert not any("unrecognized" in text for text in arena.echoed)


def test_a_gone_corpse_is_not_reported_as_unrecognized(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [NOT_DEAD_YET],
            "search": [SEARCHED_ALREADY],
        }
    )
    _run(arena, travel_first=False)
    assert not any("unrecognized" in text for text in arena.echoed)
    assert any("1 kill(s), 0 skin(s)" in text for text in arena.echoed)


# --- bundling (#174) -------------------------------------------------------
# Captured 2026-09-12 at Falken's Tannery; the hand tags, not a wording,
# say whether a skin went into the worn bundle.
BUNDLED = "You bundle up your rat pelt with your bundling rope."
GOT_BUNDLE = "You get a lumpy bundle from inside your canvas sack."
MISSING = "What were you referring to?"
NOT_FOUND = "I could not find what you were referring to."  # TAP, captured 2026-09-12
BUNDLING = PROFILE | {"bundle": True, "home": ""}


def _hands(arena, left=None, right={"noun": "handaxe"}):
    arena.state.left_hand = left
    arena.state.right_hand = right


def skin_in_hand(arena):
    arena.state.left_hand = {"noun": "pelt", "exist": "1", "name": "rat pelt"}


def hand_empty(arena):
    arena.state.left_hand = None


def test_a_bundle_kept_in_the_sack_is_worn_before_the_weapon_is_drawn(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": ["You tap a lumpy bundle inside your canvas sack."],
            "get my bundle": [GOT_BUNDLE],
            "skin": [
                PELT_LOOSE
            ],  # the skin goes into the worn bundle: hand stays empty
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    assert arena.sent[:4] == [
        "tap my bundle",
        "get my bundle from my sack",
        "wear my bundle",
        "get my handaxe from my sack",
    ]
    after_skin = arena.sent[arena.sent.index("skin rat") + 1 :]
    assert after_skin[0] == "search rat"  # nothing stowed, nothing bundled by hand
    assert any("1 kill(s), 1 skin(s)" in text for text in arena.echoed)


def test_the_first_skin_starts_the_bundle_and_wears_it(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": [NOT_FOUND],
            "skin": [(PELT_LOOSE, skin_in_hand)],
            "get my rope": ["You get a bundling rope from inside your canvas sack."],
            "bundle": [(BUNDLED, hand_empty)],
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    first = arena.sent.index("skin rat")
    assert arena.sent[first : first + 7] == [
        "skin rat",
        "put my handaxe in my sack",
        "get my rope from my sack",
        "bundle",
        "wear my bundle",
        "get my handaxe from my sack",
        "search rat",
    ]
    assert any("bundle started and worn" in text for text in arena.echoed)


def test_without_a_rope_the_skin_is_stowed_and_the_run_says_so_once(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda arena: None), (KILL, kill)],
            "tap": [NOT_FOUND],
            "skin": [(PELT_LOOSE, skin_in_hand), (PELT_LOOSE, skin_in_hand)],
            "get my rope": [MISSING],
            "search": [NOTHING, NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING | {"max_kills": 2}, travel_first=False)
    assert "get my rope from my sack" in arena.sent
    assert arena.sent.count("get my rope from my sack") == 1
    assert arena.sent.count("put my pelt in my sack") == 2
    assert sum("no bundling rope" in text for text in arena.echoed) == 1


def test_an_attack_from_range_waits_for_melee_before_the_next(travel):
    # Captured 2026-09-12: ATTACK beyond melee advances first, and a
    # second ATTACK meanwhile only answers "already advancing".
    advancing = (
        "You aren't close enough to attack.\nYou begin to advance on a ship's rat."
    )
    arena = Arena(
        {
            "attack": [advancing, (KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena, profile=PROFILE | {"max_kills": 1}, travel_first=False)
    assert arena.sent.count("attack rat") == 2
    assert not any("unrecognized" in text for text in arena.echoed)


def test_the_weapon_stays_in_hand_at_every_end(travel):
    # A stowed weapon parries nothing: the stop word among three live
    # rats stowed the handaxe and left him taking bites (2026-09-12).
    # Home or not, hostiles or not, the hunt ends with it in hand.
    for profile, hostiles_left in (
        (PROFILE | {"home": "", "max_kills": 1}, True),
        (PROFILE | {"max_kills": 1}, False),
    ):
        effect = (lambda arena: None) if hostiles_left else kill
        arena = Arena(
            {"attack": [(KILL, effect)], "skin": [SKINNED], "search": [NOTHING]}
        )
        _run(arena, profile=profile, travel_first=False)
        assert not any(command.startswith("put my handaxe") for command in arena.sent)


def test_a_corpse_that_keeps_answering_ends_the_room_not_the_evening(travel):
    # 2026-09-05: the hostile state still listed the corpse and the loop
    # swung at it five times. Disposed of once, then the room is clear.
    # The hostile state never empties here, so each room is declared
    # clear after CORPSE_SWINGS + 1 swings and the ground is lapped
    # until the pause, where the operator's word ends it.
    arena = Patient({"attack": [RAT_CORPSE] * 100, "search": [NOTHING] * 100})
    _run(arena, profile=PROFILE | {"skin": False}, travel_first=False)
    assert "search rat" in arena.sent
    rooms_visited = hunt.EMPTY_LAPS * len(GROUND.rooms_tagged("rats")) + 1
    assert arena.sent.count("attack rat") <= (hunt.CORPSE_SWINGS + 1) * rooms_visited
    assert any("only a corpse answers" in text for text in arena.echoed)
    assert any("ground empty" in text for text in arena.echoed)


def test_kill_and_item_nouns_are_read_from_the_game_lines():
    assert hunt.kill_noun("The cougar falls to the ground and lies still.") == "cougar"
    assert hunt.kill_noun("The cougar slowly tips over and falls down.") is None
    assert hunt.kill_noun(RAT_KILL) == "rat"
    assert hunt._DEAD_NOUN.search(RAT_CORPSE).group(2) == "rat"
    assert hunt.kill_noun("A large rat goes still.") == "rat"
    assert hunt.kill_noun("You miss.") is None
    assert hunt.items_in("You skin the rat, obtaining a rat pelt.") == ["pelt"]
    assert hunt.items_in(PELT_LOOSE) == ["pelt"]
    assert hunt.items_in(TAIL_REMOVED) == ["tail"]
    assert hunt.items_in("You find a small ruby. You find some coins.") == [
        "ruby",
        "coins",
    ]


# --- buffs ------------------------------------------------------------------
# Captured 2026-09-12: Heroic Strength prepared and cast by a circle-1
# Paladin (docs/hunting.md). The Spells window says when it has run out.
PREPARED = "You begin chanting a prayer to invoke the Heroic Strength spell."
CAST = (
    "You gesture.\nThe spell takes effect, the invisible flame of your soul "
    "intertwining with your flesh.  You feel holy strength and vigor course "
    "through your body."
)
BUFFED = PROFILE | {"buffs": ["heroic strength"], "home": ""}


def test_buffs_are_cast_before_the_weapon_is_drawn(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [PREPARED],
            "cast": [CAST],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena, profile=BUFFED | {"max_kills": 1}, travel_first=False)
    assert arena.sent[:4] == [
        "prepare heroic strength",
        "cast",
        "get my handaxe from my sack",
        "stance set 100 80 0",
    ]
    assert arena.sent.count("cast") == 1  # no Spells window: the timer holds it
    assert "hunt: cast heroic strength" in arena.echoed


def test_a_buff_the_spells_window_lists_is_not_recast_until_it_runs_out(travel):
    def running(arena):
        arena.state.active_spells = {"Heroic Strength": 10}

    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED, PREPARED],
            "cast": [(CAST, running), (CAST, running)],
            "skin": [SKINNED, SKINNED],
            "search": [NOTHING, NOTHING],
        }
    )
    arena.state.active_spells = {}
    _run(arena, profile=BUFFED | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("cast") == 1

    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED, PREPARED],
            "cast": [CAST, CAST],
            "skin": [SKINNED, SKINNED],
            "search": [NOTHING, NOTHING],
        }
    )
    arena.state.active_spells = {}  # never lists it: at the start, then before each swing
    _run(arena, profile=BUFFED | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("cast") == 3


def test_a_buff_that_will_not_prepare_is_dropped_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": ["You don't know that spell."],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena, profile=BUFFED | {"max_kills": 1}, travel_first=False)
    assert "cast" not in arena.sent
    assert arena.sent.count("prepare heroic strength") == 1
    assert any("cannot prepare heroic strength" in text for text in arena.echoed)


# --- training casts ----------------------------------------------------------
STRAINED = (
    "You have to strain to harness the energy for this spell, and you aren't "
    "sure you can get enough to cast it.\n" + PREPARED
)
TRAINING = BUFFED | {"train_casting": "Augmentation"}


def _exp(mindstate):
    return {"Augmentation": {"rank": 3, "percent": 66, "mindstate": mindstate}}


def prepares(arena):
    return [command for command in arena.sent if command.startswith("prepare")]


def test_training_casts_ramp_the_mana_between_swings(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED] * 5,
            "cast": [CAST] * 5,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 3}, travel_first=False)
    # One before the weapon, then one before each of the three swings:
    # the minimum first, then two more mana each time.
    assert prepares(arena) == [
        "prepare heroic strength",
        "prepare heroic strength 2",
        "prepare heroic strength 4",
        "prepare heroic strength 6",
    ]
    assert any("at minimum mana for Augmentation" in text for text in arena.echoed)


def test_the_strain_warning_caps_the_mana_one_step_under(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED, STRAINED, PREPARED, PREPARED],
            "cast": [CAST] * 4,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 3}, travel_first=False)
    assert prepares(arena) == [
        "prepare heroic strength",
        "prepare heroic strength 2",
        "prepare heroic strength",
        "prepare heroic strength",
    ]
    assert any("was too much (strained)" in text for text in arena.echoed)


def test_a_backfire_at_minimum_mana_ends_the_training_casts(travel):
    # Captured 2026-09-12: 5 mana "barely backfires" on a circle-1
    # Paladin. Below the minimum there is nowhere to go, so training
    # casts stop; the buff itself is still tried when it runs out.
    backfire = "You gesture.\nYour spell barely backfires."
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED] * 3,
            "cast": [backfire] * 3,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare heroic strength"] * 2
    assert any("training casts off" in text for text in arena.echoed)


# Captured 2026-09-14 on a round cambrinth flake (1 mana).
GOT_FLAKE = "You get a round cambrinth flake from inside your canvas sack."
CHARGED = (
    "You harness a small amount of energy and attempt to channel it into your "
    "cambrinth flake.\nYou are able to channel all the energy into the flake.\n"
    "The cambrinth flake absorbs all of the energy.\nRoundtime: 2 sec."
)
FLAKE_FULL = (
    "You are able to channel all the energy into the flake.\nThe cambrinth flake "
    "is already holding as much power as you could possibly charge it with.\n"
    "Your harnessed energy dissipates uselessly.\nRoundtime: 4 sec."
)
NOT_CHANNELLED = (
    "You harness a small amount of energy and attempt to channel it into your "
    "cambrinth armband.\nYou fail to channel any of the energy into the armband."
)
INVOKED = (
    "The cambrinth flake pulses with Holy energy.  You reach for its center and "
    "forge a magical link to it, readying all of its mana for your use.\n"
    "Roundtime: 1 sec."
)
SNAP_CAST = (
    "You gesture.\nYour cambrinth flake emits a loud *snap* as it discharges all "
    "its power to aid your spell.\nYour soul and body intertwine tighter, the "
    "bond renewed by the spell."
)
CAMBRINTH = TRAINING | {"cambrinth": "flake", "cambrinth_mana": 1}


def test_a_cambrinth_piece_is_charged_and_invoked_into_the_training_cast(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "get my flake": [GOT_FLAKE] * 3,
            "charge my flake": [CHARGED, FLAKE_FULL, FLAKE_FULL],
            "prepare": [PREPARED] * 4,
            "invoke my flake": [INVOKED] * 3,
            "cast": [CAST, SNAP_CAST, SNAP_CAST, SNAP_CAST],
            "stow my flake": ["You put your flake in your canvas sack."] * 3,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10) | {"Arcana": {"rank": 1, "percent": 36, "mindstate": 3}},
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=CAMBRINTH | {"max_kills": 2}, travel_first=False)
    first = arena.sent.index("get my flake")
    assert arena.sent[first : first + 6] == [
        "get my flake",
        "charge my flake 1",
        "prepare heroic strength",
        "invoke my flake",
        "cast",
        "stow my flake",
    ]
    # One training cast at the start and one before each of two swings;
    # the later ones found the flake still full, invoked all the same.
    assert arena.sent.count("charge my flake 1") == 3
    assert arena.sent.count("invoke my flake") == 3
    assert any("charged the flake with 1 mana for Arcana" in t for t in arena.echoed)
    assert any("(+flake)" in t for t in arena.echoed)


def test_a_piece_that_outranks_arcana_is_off_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "get my armband": [
                "You get a braided cambrinth armband from inside your sack."
            ],
            "charge my armband": [NOT_CHANNELLED],
            "prepare": [PREPARED] * 4,
            "cast": [CAST] * 4,
            "stow my armband": ["You put your armband in your canvas sack."],
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(
        arena,
        profile=CAMBRINTH
        | {"cambrinth": "armband", "cambrinth_mana": 3, "max_kills": 2},
        travel_first=False,
    )
    assert arena.sent.count("charge my armband 3") == 1
    assert "invoke my armband" not in arena.sent
    assert "stow my armband" in arena.sent
    assert any("outranks Arcana" in t for t in arena.echoed)
    assert len(prepares(arena)) >= 2  # the training casts go on without it


def test_cambrinth_alone_drives_the_training_cadence_until_arcana_locks(travel):
    profile = BUFFED | {"train_casting": "", "cambrinth": "flake", "cambrinth_mana": 1}
    for arcana, charges in ((3, 2), (34, 0)):  # the start, then before the swing
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "get my flake": [GOT_FLAKE] * 2,
                "charge my flake": [CHARGED, FLAKE_FULL],
                "prepare": [PREPARED] * 3,
                "invoke my flake": [INVOKED] * 2,
                "cast": [SNAP_CAST] * 3,
                "stow my flake": ["You put your flake in your canvas sack."] * 2,
                "skin": [SKINNED],
                "search": [NOTHING],
            },
            experience={"Arcana": {"rank": 1, "percent": 0, "mindstate": arcana}},
        )
        arena.state.vitals["mana"] = 100
        _run(arena, profile=profile | {"max_kills": 1}, travel_first=False)
        assert arena.sent.count("charge my flake 1") == charges, arcana


def test_the_profile_cast_gap_paces_the_training_casts(travel, monkeypatch):
    # #189: at a 20-second gap the first badger fight was seven swings
    # to the badger's 42, a cambrinth cycle being eight commands. The
    # profile's cast_gap (60 s by default) spaces the casts; 0 casts
    # before every swing.
    now = {"t": 1000.0}
    monkeypatch.setattr(buffs, "monotonic", lambda: now["t"])
    original_ask = hunt.ask

    def ask(s, command):
        now["t"] += 7  # every command costs a swing's worth of time
        return original_ask(s, command)

    monkeypatch.setattr(hunt, "ask", ask)
    casts = {}
    for gap in (0, 60):
        arena = Arena(
            {
                "attack": [(KILL, lambda a: None)] * 5 + [(KILL, kill)],
                "prepare": [PREPARED] * 9,
                "cast": [CAST] * 9,
                "skin": [SKINNED] * 6,
                "search": [NOTHING] * 6,
            },
            experience=_exp(10),
        )
        arena.state.vitals["mana"] = 100
        _run(
            arena,
            profile=TRAINING | {"cast_gap": gap, "max_kills": 6},
            travel_first=False,
        )
        casts[gap] = arena.sent.count("cast")
    assert casts[0] == 7  # before the weapon is drawn, then before every swing
    assert 1 < casts[60] < 4  # a kill is three commands, so one cast in three


def test_no_training_cast_at_lock_or_under_the_mana_floor(travel):
    for experience, mana in ((_exp(34), 100), (_exp(10), 20)):
        arena = Arena(
            {
                "attack": [(KILL, lambda a: None), (KILL, kill)],
                "prepare": [PREPARED] * 3,
                "cast": [CAST] * 3,
                "skin": [SKINNED] * 2,
                "search": [NOTHING] * 2,
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = mana
        _run(arena, profile=TRAINING | {"max_kills": 2}, travel_first=False)
        # The buff itself is still cast once (no Spells window: the timer holds it).
        assert prepares(arena) == ["prepare heroic strength"]


def test_a_bundle_worn_from_the_last_run_is_left_where_it_is(travel):
    # Captured 2026-09-12: the second bundled run began with a GET from
    # the sack that missed the bundle still on his shoulder; TAP says
    # "that you are wearing", and nothing needs fetching.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": ["You tap a lumpy bundle that you are wearing."],
            "skin": [PELT_LOOSE],
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    assert arena.sent[:2] == ["tap my bundle", "get my handaxe from my sack"]
    assert "wear my bundle" not in arena.sent
    after_skin = arena.sent[arena.sent.index("skin rat") + 1 :]
    assert after_skin[0] == "search rat"
    assert "hunt: bundle worn — skins go straight into it" in arena.echoed


# --- another player's room (#178) -------------------------------------------


def test_an_occupied_room_of_the_ground_is_theirs_so_the_hunt_moves_on(travel):
    # 2026-09-12: ;hunt fought rats in a shipyard room two other players
    # were hunting. A player already in the room on arrival makes it
    # theirs: move on without a swing, settle only in an empty one.
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]},
        hostiles=(),
    )
    arena.state.room_players = ["Bankismo"]
    arena.arrivals = {6047: {"2": True}}
    original_walk = hunt.walk

    def walk(s, db, goals, describe="", avoid=()):
        result = original_walk(s, db, goals, describe=describe, avoid=avoid)
        s.state.room_players = [] if s.room == 6047 else ["Bankismo"]
        return result

    hunt.walk = walk
    _run(arena)  # travel first: arrives in 6046, Bankismo's room
    assert arena.walks[1] == {6047}
    attacks = [c for c in arena.sent if c.startswith("attack")]
    assert attacks  # fought in 6047, the empty room ...
    assert any("their room, moving on" in text for text in arena.echoed)


def test_a_ground_with_someone_in_every_room_is_left_to_them(travel):
    arena = Arena({"attack": [(KILL, kill)]}, hostiles=())
    arena.state.room_players = ["Bankismo"]
    _run(arena)
    assert not any(c.startswith("attack") for c in arena.sent)
    assert any("leaving it to them" in text for text in arena.echoed)


def test_a_paladin_smites_one_swing_a_minute_and_attacks_the_rest(travel, monkeypatch):
    # #183: SMITE trains Conviction, a free smite comes back every
    # minute and the experience once a minute, so the loop smites at
    # most once a minute; a smite the game answered from range (no
    # strike) is not spent.
    now = {"t": 1000.0}
    monkeypatch.setattr(hunt, "clock", lambda: now["t"])
    advancing = "You aren't close enough to attack.\nYou begin to advance on a rat."
    arena = Arena(
        {
            "smite": [advancing, (SMITE_KILL, kill), (SMITE_KILL, kill)],
            "attack": [(KILL, kill)] * 6,
            "skin": [SKINNED] * 9,
            "search": [NOTHING] * 9,
        }
    )
    arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}

    def tick(seconds):
        now["t"] += seconds

    original_ask = hunt.ask

    def ask(s, command):
        tick(7)  # a swing's roundtime; the minute passes after nine swings
        return original_ask(s, command)

    monkeypatch.setattr(hunt, "ask", ask)
    _run(arena, profile=PROFILE | {"smite": True, "max_kills": 4}, travel_first=False)
    swings = [c for c in arena.sent if c.startswith(("smite", "attack"))]
    # First swing: smite from range — no strike, not spent — so the next
    # swing smites again and kills; then attacks until a minute passed.
    assert swings[:3] == ["smite rat", "smite rat", "attack rat"]
    assert swings.count("smite rat") >= 3  # a minute later, smite again
    assert not any(
        c.startswith("smite") for c in Arena({"attack": [(KILL, kill)]}).sent
    )


# --- debilitation ----------------------------------------------------------
# Stun Foe's cast at minimum mana, captured 2026-09-14 on a striped
# badger (#192) — the wiki's "brilliant stream of pure white light" is
# the line at more mana; the resist and failure wordings are still
# uncaptured.
STUNNED = (
    "You gesture at a rat.\nA stream of dull golden light jumps from you to a "
    "rat, which warps into a spiraling force as it slams into it!\n"
    "You also see a rat that appears stunned."
)
SF_PREPARED = "You begin chanting a prayer to invoke the Stun Foe spell."
STUNNING = PROFILE | {"debilitation": "stun foe"}
# DISCERN's estimate is the wiki's until captured (#202).
DISCERNED = "You think you could weave at most 27 mana streams into this spell."
DEBIL_OPEN = {"Debilitation": {"rank": 1, "percent": 0, "mindstate": 5}}


def test_the_debilitation_spell_is_cast_at_the_prey_before_the_swing(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, _stands), (KILL, kill)],
            "prepare": [SF_PREPARED] * 3,
            "cast": [STUNNED] * 3,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 3}, travel_first=False)
    # DISCERN first, before the weapon is drawn (#202); the cast in the fight.
    # PREPARE, the swing while the pattern forms (its kill skinned and
    # searched, the pattern holding), CAST (#203).
    assert arena.sent[:5] == [
        "discern stun foe",
        "get my handaxe from my sack",
        "stance set 100 80 0",
        "prepare stun foe",
        "attack rat",
    ]
    assert arena.sent.index("cast rat") < arena.sent.index("prepare stun foe 2")
    # The mana climbs a step per cast that took, like the training casts.
    assert prepares(arena) == [
        "prepare stun foe",
        "prepare stun foe 2",
        "prepare stun foe 4",
    ]
    assert any("for Debilitation" in text for text in arena.echoed)


def test_no_debilitation_cast_at_lock_under_the_mana_floor_or_with_no_spell(travel):
    locked = {"Debilitation": {"rank": 1, "percent": 0, "mindstate": 34}}
    for profile, experience, mana in (
        (STUNNING, locked, 100),
        (STUNNING, DEBIL_OPEN, 20),
        (PROFILE, DEBIL_OPEN, 100),
    ):
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "prepare": [SF_PREPARED],
                "cast": [STUNNED],
                "skin": [SKINNED],
                "search": [NOTHING],
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = mana
        _run(arena, profile=profile | {"max_kills": 1}, travel_first=False)
        assert prepares(arena) == []


def test_a_collapse_at_minimum_mana_turns_the_debilitation_spell_off(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [SF_PREPARED] * 2,
            "cast": ["You gesture.\nYour spell barely backfires."] * 2,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare stun foe"]
    assert any("off for this run" in text for text in arena.echoed)


def test_the_debilitation_and_training_casts_take_turns(travel):
    # Both due before every swing (cast_gap 0): the buff trains first,
    # the stun takes the next swing, and so on — never two casts before
    # one swing.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "prepare": [PREPARED, SF_PREPARED, PREPARED, SF_PREPARED],
            "cast": [CAST, STUNNED, CAST, STUNNED],
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=_exp(10) | DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(
        arena,
        profile=TRAINING | {"debilitation": "stun foe", "max_kills": 3},
        travel_first=False,
    )
    assert prepares(arena) == [
        "prepare heroic strength",  # before the weapon is drawn
        "prepare stun foe",  # swing 1: the buff went last, the stun's turn
        "prepare heroic strength 2",  # swing 2
        "prepare stun foe 2",  # swing 3
    ]


# --- targeted magic --------------------------------------------------------
# Footman's Strike (#200): the cast line is the wiki's "You gesture at
# <target> with your <weapon>." until captured; the hit, resist and
# unarmed-failure wordings are still to capture.
STRUCK = "You gesture at a rat with your handaxe."
FS_PREPARED = "You begin chanting a prayer to invoke the Footman's Strike spell."
STRIKING = PROFILE | {"targeted": "footman's strike"}
# TARGET's wordings are the wiki's until captured (#203).
TARGETING = "You begin to weave mana lines into a target pattern around a rat."
# The operator's DISCERN, captured 2026-09-18 (#203): the description,
# the rank the spell wants, the refusal, 13 seconds of roundtime.
DISCERN_REFUSED = (
    "Footman's Strike draws on the caster's melee weapon in hand as a focus for "
    "the spell, which dictates the shape of its manifestation.\n\nThis is a "
    "targeted spell, which must be TARGETed at a specific opponent.  This spell "
    "does slice and impact damage.  It requires a minimum of two mana streams, "
    "and can expand to a maximum of fifty mana streams woven into it.  To begin "
    "to be able to cast this spell, you will need to reach the rank of a "
    "promising novice.  By the time you have mastered this spell, you will be "
    "ranked as a genius in your abilities as a caster.  It requires the Targeted "
    "Magic skill to cast effectively.\n\nYou don't think you are able to cast "
    "this spell.\nRoundtime: 13 sec."
)
TM_OPEN = {"Targeted Magic": {"rank": 1, "percent": 0, "mindstate": 5}}
TM_LOCKED = {"Targeted Magic": {"rank": 1, "percent": 0, "mindstate": 34}}


def test_the_targeted_spell_is_cast_at_the_prey_before_the_swing(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, _stands), (KILL, kill)],
            "prepare": [FS_PREPARED] * 3,
            "cast": [STRUCK] * 3,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
            "discern": [DISCERNED],
            "target": [TARGETING] * 3,
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 3}, travel_first=False)
    # Only in the fight, the weapon drawn: the spell takes it as its focus.
    # Targeted magic: PREPARE, TARGET the prey, the swing while the
    # pattern forms, CAST at the pattern (#203).
    assert arena.sent[:6] == [
        "discern footman's strike",
        "get my handaxe from my sack",
        "stance set 100 80 0",
        "prepare footman's strike",
        "target rat",
        "attack rat",
    ]
    assert arena.sent.index("cast") < arena.sent.index("prepare footman's strike 2")
    assert "cast rat" not in arena.sent
    assert prepares(arena) == [
        "prepare footman's strike",
        "prepare footman's strike 2",
        "prepare footman's strike 4",
    ]
    assert any("for Targeted Magic" in text for text in arena.echoed)


def test_no_targeted_cast_at_lock_under_the_mana_floor_or_with_no_spell(travel):
    for profile, experience, mana in (
        (STRIKING, TM_LOCKED, 100),
        (STRIKING, TM_OPEN, 20),
        (PROFILE, TM_OPEN, 100),
    ):
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "prepare": [FS_PREPARED],
                "cast": [STRUCK],
                "skin": [SKINNED],
                "search": [NOTHING],
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = mana
        _run(arena, profile=profile | {"max_kills": 1}, travel_first=False)
        assert prepares(arena) == []


def test_each_targeted_slot_is_gated_on_its_own_skill(travel):
    # Debilitation locked, Targeted Magic open: the strike goes out and
    # the stun stays home — and the other way round.
    both = STRIKING | {"debilitation": "stun foe", "max_kills": 1}
    for experience, expected in (
        (DEBIL_OPEN | TM_LOCKED, ["prepare stun foe"]),
        (
            {"Debilitation": {"rank": 1, "percent": 0, "mindstate": 34}} | TM_OPEN,
            ["prepare footman's strike"],
        ),
    ):
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "prepare": [SF_PREPARED, FS_PREPARED],
                "cast": [STUNNED, STRUCK],
                "skin": [SKINNED],
                "search": [NOTHING],
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = 100
        _run(arena, profile=both, travel_first=False)
        assert prepares(arena) == expected


def test_a_collapse_at_minimum_mana_turns_the_targeted_spell_off(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [FS_PREPARED] * 2,
            "cast": ["You gesture.\nYour spell barely backfires."] * 2,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare footman's strike"]
    assert any("off for this run" in text for text in arena.echoed)


def test_the_buff_debilitation_and_targeted_casts_take_turns(travel):
    # All three due before every swing (cast_gap 0): the buff trains
    # before the weapon is drawn, then stun, strike, buff, stun, strike
    # — never two casts before one swing.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 4 + [(KILL, kill)],
            "prepare": [PREPARED, SF_PREPARED, FS_PREPARED] * 2,
            "cast": [CAST, STUNNED, STRUCK] * 2,
            "skin": [SKINNED] * 5,
            "search": [NOTHING] * 5,
        },
        experience=_exp(10) | DEBIL_OPEN | TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(
        arena,
        profile=TRAINING
        | {"debilitation": "stun foe", "targeted": "footman's strike", "max_kills": 5},
        travel_first=False,
    )
    assert prepares(arena) == [
        "prepare heroic strength",  # before the weapon is drawn
        "prepare stun foe",  # swing 1
        "prepare footman's strike",  # swing 2
        "prepare heroic strength 2",  # swing 3
        "prepare stun foe 2",  # swing 4
        "prepare footman's strike 2",  # swing 5
    ]


# Captured 2026-09-18 (#202): Footman's Strike, a basic spell, at
# Targeted Magic rank 1.
LACKING = (
    "You gesture at a rat with your handaxe.\nCurrently lacking the skill to "
    "complete the pattern, your spell fails completely."
)
TM_RANK_1 = {"Targeted Magic": {"rank": 1, "percent": 0, "mindstate": 0}}


def test_a_strike_the_ranks_cannot_carry_is_off_for_the_run_with_the_rank_named(
    travel,
):
    # The loop used to take "fails completely" for a cast that landed,
    # step the mana up and prepare it again every rotation.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 3 + [(KILL, kill)],
            "prepare": [FS_PREPARED] * 4,
            "cast": [LACKING] * 4,
            "skin": [SKINNED] * 4,
            "search": [NOTHING] * 4,
            "discern": [DISCERNED],
        },
        experience=TM_RANK_1,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 4}, travel_first=False)
    assert prepares(arena) == ["prepare footman's strike"]
    assert any(
        "footman's strike fails for lack of Targeted Magic ranks (1) — off for this run"
        in text
        for text in arena.echoed
    )
    assert not any("for Targeted Magic" in text for text in arena.echoed)


def test_discern_saying_no_spares_the_prepare_and_names_the_rank(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [FS_PREPARED] * 2,
            "cast": [LACKING] * 2,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
            "discern": [DISCERN_REFUSED],
        },
        experience=TM_RANK_1,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("discern footman's strike") == 1
    assert prepares(arena) == []
    assert any(
        "DISCERN says footman's strike needs Targeted Magic 10 (promising novice); "
        "Targeted Magic is 1 — off for this run" in text
        for text in arena.echoed
    )


def test_rank_floor_reads_the_title_discern_names():
    assert buffs.rank_floor(DISCERN_REFUSED) == (10, "promising novice")
    assert buffs.rank_floor("reach the rank of a lowly novice.") == (1, "lowly novice")
    assert buffs.rank_floor("reach the rank of an adept.") == (200, "adept")
    assert buffs.rank_floor("You don't think you are able to cast this spell.") is None


def test_the_swing_goes_out_while_the_training_cast_prepares(travel):
    # cast_gap 0: the buff trains before every swing — PREPARE, the
    # swing, CAST, never a swing on its own while a cast is due (#203).
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "prepare": [PREPARED] * 4,
            "cast": [CAST] * 4,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 3}, travel_first=False)
    fight = arena.sent[arena.sent.index("stance set 100 80 0") + 1 :]
    casts = [c for c in fight if c.split()[0] in ("prepare", "attack", "cast")]
    assert casts == [
        "prepare heroic strength 2",
        "attack rat",
        "cast",
        "prepare heroic strength 4",
        "attack rat",
        "cast",
        "prepare heroic strength 6",
        "attack rat",
        "cast",
    ]


def test_a_foe_down_under_the_filler_swing_releases_the_targeted_pattern(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [SF_PREPARED],
            "cast": [STUNNED],
            "skin": [SKINNED],
            "search": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert "release" in arena.sent
    assert "cast rat" not in arena.sent
    assert any("stun foe released" in text for text in arena.echoed)


def test_a_missing_target_releases_the_pattern_before_the_swing(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [FS_PREPARED],
            "target": ["What were you referring to?"],
            "skin": [SKINNED],
            "search": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 1}, travel_first=False)
    assert arena.sent.index("release") < arena.sent.index("attack rat")
    assert "cast" not in arena.sent


def test_discern_goes_out_once_per_slot_and_not_for_an_empty_one(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "prepare": [SF_PREPARED] * 3,
            "cast": [STUNNED] * 3,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
            "discern": [DISCERNED] * 3,
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 3}, travel_first=False)
    discerns = [c for c in arena.sent if c.startswith("discern")]
    assert discerns == ["discern stun foe"]


def test_a_buff_the_ranks_cannot_carry_is_off_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [PREPARED] * 2,
            "cast": [
                "You gesture.\nCurrently lacking the skill to complete the pattern, your spell fails completely."
            ]
            * 2,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        }
    )
    _run(arena, profile=BUFFED | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare heroic strength"]
    assert any(
        "heroic strength fails for lack of ranks — off for this run" in text
        for text in arena.echoed
    )


# --- tracks ----------------------------------------------------------------
# Captured 2026-09-14 (#194): HUNT's answer, a numbered list, an 8-second
# roundtime; the empty answer is the wiki's.
TRACKED = (
    "You take note of all the tracks in the area, so that you can hunt anything "
    "nearby down.\nTo the east:\n  1)   a rat\nRoundtime: 8 sec."
)
PERCEPTION_OPEN = {"Perception": {"rank": 10, "percent": 0, "mindstate": 3}}
TRACKING = PROFILE | {"perception": True}


def _ticking(monkeypatch, seconds):
    """A clock that advances `seconds` per command sent."""
    now = {"t": 1000.0}
    monkeypatch.setattr(hunt, "clock", lambda: now["t"])
    original_ask = hunt.ask

    def ask(s, command):
        now["t"] += seconds
        return original_ask(s, command)

    monkeypatch.setattr(hunt, "ask", ask)


def test_a_hunt_for_tracks_when_the_room_empties_once_per_timer(travel, monkeypatch):
    # Three kills empty three rooms in turn; the fuse ends the run at
    # the third. With the clock frozen the second emptying is inside
    # the 75-second timer; ticking 30 s a command, a kill is 90 s and
    # every emptying earns a HUNT.
    for seconds, hunts in ((0, 1), (30, 2)):
        _ticking(monkeypatch, seconds)
        arena = Arena(
            {
                "attack": [(KILL, kill)] * 3,
                "hunt": [TRACKED] * 3,
                "skin": [SKINNED] * 3,
                "search": [NOTHING] * 3,
            },
            experience=PERCEPTION_OPEN,
        )
        arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
        _run(arena, profile=TRACKING | {"max_kills": 3}, travel_first=False)
        assert arena.sent.count("hunt") == hunts, seconds
        first = arena.sent.index("hunt")
        assert (
            arena.sent[first - 1] == "search rat"
        )  # after the corpse, before the move
        assert any(f"{hunts} HUNT(s)" in text for text in arena.echoed)


def test_no_hunt_for_tracks_at_lock_or_with_the_flag_off(travel):
    locked = {"Perception": {"rank": 10, "percent": 0, "mindstate": 34}}
    for profile, experience in ((TRACKING, locked), (PROFILE, PERCEPTION_OPEN)):
        arena = Arena(
            {
                "attack": [(KILL, kill)] * 2,
                "hunt": [TRACKED] * 2,
                "skin": [SKINNED] * 2,
                "search": [NOTHING] * 2,
            },
            experience=experience,
        )
        arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
        _run(arena, profile=profile | {"max_kills": 2}, travel_first=False)
        assert "hunt" not in arena.sent


def test_three_unknown_hunt_answers_turn_tracking_off(travel, monkeypatch):
    _ticking(monkeypatch, 30)
    arena = Arena(
        {
            "attack": [(KILL, kill)] * 5,
            "hunt": ["You can't hunt here."] * 5,
            "skin": [SKINNED] * 5,
            "search": [NOTHING] * 5,
        },
        experience=PERCEPTION_OPEN,
    )
    arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
    _run(arena, profile=TRACKING | {"max_kills": 5}, travel_first=False)
    assert arena.sent.count("hunt") == 3
    assert any("tracking off for this run" in text for text in arena.echoed)


# --- tactics ---------------------------------------------------------------
# Captured 2026-09-14 on a striped badger (#190): each maneuver's line,
# then a balance line and a 3-second roundtime; Tactics entered the exp
# window at rank 3 on the first BOB.
BOBBED = (
    "You bob suddenly, lowering yourself into a smaller target.\n"
    "[You're nimbly balanced and in superior position.]\nRoundtime: 3 sec."
)
CIRCLED = (
    "You sidestep a rat suddenly, moving in a short circle around it.\n"
    "[You're nimbly balanced and opponent has slight advantage.]\nRoundtime: 3 sec."
)
WEAVED = (
    "You weave back and forth, trying to distract your opponent.\n"
    "[You're slightly off balance with opponent in better position.]\n"
    "Roundtime: 3 sec."
)
TACTICAL = PROFILE | {"tactics": ["bob", "circle"]}
TACTICS_OPEN = {"Tactics": {"rank": 3, "percent": 0, "mindstate": 1}}


def _stands(arena):
    """A kill line whose rat stays: the room keeps its hostile."""


def test_every_third_swing_is_the_next_maneuver_while_tactics_is_unlocked(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 5 + [(KILL, kill)],
            "bob": [BOBBED] * 3,
            "circle": [CIRCLED] * 3,
            "skin": [SKINNED] * 9,
            "search": [NOTHING] * 9,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"max_kills": 6}, travel_first=False)
    swings = [c for c in arena.sent if c.split()[0] in ("attack", "bob", "circle")]
    assert swings == [
        "attack rat",
        "attack rat",
        "bob rat",
        "attack rat",
        "attack rat",
        "circle rat",
        "attack rat",
        "attack rat",
    ]
    assert any("2 maneuver(s)" in text for text in arena.echoed)


def test_no_maneuver_once_tactics_locks_or_with_none_listed(travel):
    locked = {"Tactics": {"rank": 3, "percent": 0, "mindstate": 34}}
    for profile, experience in ((TACTICAL, locked), (PROFILE, TACTICS_OPEN)):
        arena = Arena(
            {
                "attack": [(KILL, _stands)] * 5 + [(KILL, kill)],
                "bob": [BOBBED] * 3,
                "circle": [CIRCLED] * 3,
                "skin": [SKINNED] * 6,
                "search": [NOTHING] * 6,
            },
            experience=experience,
        )
        _run(arena, profile=profile | {"max_kills": 6}, travel_first=False)
        assert not any(c.startswith(("bob", "circle")) for c in arena.sent)
        assert not any("maneuver" in text for text in arena.echoed)


def test_a_smite_keeps_its_minute_ahead_of_the_maneuvers(travel, monkeypatch):
    monkeypatch.setattr(hunt, "clock", lambda: 1000.0)  # one smite, never again
    arena = Arena(
        {
            "smite": [(SMITE_KILL, _stands)],
            "attack": [(KILL, _stands)] * 3 + [(KILL, kill)],
            "bob": [BOBBED],
            "circle": [CIRCLED],
            "skin": [SKINNED] * 6,
            "search": [NOTHING] * 6,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"smite": True, "max_kills": 5}, travel_first=False)
    swings = [
        c for c in arena.sent if c.split()[0] in ("attack", "smite", "bob", "circle")
    ]
    assert swings == [
        "smite rat",
        "attack rat",
        "bob rat",
        "attack rat",
        "attack rat",
        "circle rat",
        "attack rat",
    ]


def test_a_maneuver_from_range_advances_like_an_attack(travel):
    advancing = "You aren't close enough to attack.\nYou begin to advance on a rat."
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, _stands), (KILL, kill)],
            "weave": [advancing],
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=TACTICS_OPEN,
    )
    _run(
        arena,
        profile=PROFILE | {"tactics": ["weave"], "max_kills": 3},
        travel_first=False,
    )
    assert "weave rat" in arena.sent
    assert not any("unrecognized" in text for text in arena.echoed)


def test_a_maneuver_answered_with_nothing_known_three_times_turns_tactics_off(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 11 + [(KILL, kill)],
            "bob": ["You can't do that right now."] * 5,
            "skin": [SKINNED] * 12,
            "search": [NOTHING] * 12,
        },
        experience=TACTICS_OPEN,
    )
    _run(
        arena,
        profile=PROFILE | {"tactics": ["bob"], "max_kills": 12},
        travel_first=False,
    )
    assert arena.sent.count("bob rat") == 3
    assert sum("unrecognized bob" in text for text in arena.echoed) == 3
    assert any("tactics off for this run" in text for text in arena.echoed)


def test_without_smite_every_swing_is_attack(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    )
    assert not any(c.startswith("smite") for c in arena.sent)


def test_a_room_full_of_creatures_is_hunted_not_left(travel):
    # #178 asked for a crowd threshold; the operator's answer (2026-09-12):
    # a hunt farms, so a full room is fought one at a time, never skipped.
    arena = Arena({"attack": [(KILL, kill)]})
    arena.state.room_creatures = ["a ship's rat"] * 5
    _run(arena)
    assert arena.walks[0] == {6046, 6047}
    assert any(c.startswith("attack") for c in arena.sent)
    assert not any("crowd" in text for text in arena.echoed)


# --- the injuries panel as the wound floor's pre-check (#163) ----------------


def test_a_clean_injuries_panel_skips_health_and_a_lit_one_asks(travel):
    # The game pushes the panel on every change, so an empty one means
    # nothing is hurt and HEALTH need not be asked after the kill.
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    arena.state.injuries = {}
    _run(arena, profile=PROFILE | {"wound_floor": "harmful"}, travel_first=False)
    assert "health" not in arena.sent

    lit = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
            "health": [
                "Your body feels at full strength.\nYou have no significant injuries."
            ],
        }
    )
    lit.state.injuries = {"head": ("wound", 1)}
    _run(lit, profile=PROFILE | {"wound_floor": "harmful"}, travel_first=False)
    assert "health" in lit.sent


def test_a_worn_cambrinth_piece_is_removed_for_the_charge_and_worn_again(travel):
    # The anklet (2026-09-20): worn between casts, since a worn piece
    # refuses a charge, so the cycle is REMOVE, CHARGE, PREPARE, INVOKE,
    # CAST, WEAR instead of GET ... STOW.
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "remove my anklet": [
                "You remove a simple cambrinth anklet from your ankle.\n"
            ]
            * 3,
            "charge my anklet": [CHARGED.replace("flake", "anklet")] * 3,
            "prepare": [PREPARED] * 4,
            "invoke my anklet": [INVOKED.replace("flake", "anklet")] * 3,
            "cast": [CAST, SNAP_CAST, SNAP_CAST, SNAP_CAST],
            "wear my anklet": ["You attach a simple cambrinth anklet to your ankle.\n"]
            * 3,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10) | {"Arcana": {"rank": 17, "percent": 0, "mindstate": 3}},
    )
    arena.state.vitals["mana"] = 100
    worn = TRAINING | {
        "cambrinth": "anklet",
        "cambrinth_mana": 12,
        "cambrinth_worn": True,
    }
    _run(arena, profile=worn | {"max_kills": 2}, travel_first=False)
    first = arena.sent.index("remove my anklet")
    assert arena.sent[first : first + 6] == [
        "remove my anklet",
        "charge my anklet 12",
        "prepare heroic strength",
        "invoke my anklet",
        "cast",
        "wear my anklet",
    ]
    assert "get my anklet" not in arena.sent and "stow my anklet" not in arena.sent
