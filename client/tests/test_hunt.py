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
hunt.ADVANCE_WAIT = 0.01
hunt.PREPARE_SECONDS = 0.01
hunt.CAST_GAP_SECONDS = 0

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
    assert "put my handaxe in my sack" not in arena.sent


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
            "get my bundle": [GOT_BUNDLE],
            "skin": [
                PELT_LOOSE
            ],  # the skin goes into the worn bundle: hand stays empty
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    assert arena.sent[:3] == [
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
            "get my bundle": [MISSING],
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
            "get my bundle": [MISSING],
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
    # clear after CORPSE_SWINGS + 1 swings and the ground is lapped out.
    arena = Arena({"attack": [RAT_CORPSE] * 100, "search": [NOTHING] * 100})
    _run(arena, profile=PROFILE | {"skin": False}, travel_first=False)
    assert "search rat" in arena.sent
    rooms_visited = hunt.EMPTY_LAPS * len(GROUND.rooms_tagged("rats")) + 1
    assert arena.sent.count("attack rat") <= (hunt.CORPSE_SWINGS + 1) * rooms_visited
    assert any("only a corpse answers" in text for text in arena.echoed)
    assert any("ground empty" in text for text in arena.echoed)


def test_kill_and_item_nouns_are_read_from_the_game_lines():
    assert hunt.kill_noun("The cougar slowly tips over and falls down.") == "cougar"
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
    # One before the weapon, then one before each of the three swings.
    assert prepares(arena) == [
        "prepare heroic strength 5",
        "prepare heroic strength 10",
        "prepare heroic strength 15",
        "prepare heroic strength 20",
    ]
    assert any("at 5 mana for Augmentation" in text for text in arena.echoed)


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
        "prepare heroic strength 5",
        "prepare heroic strength 10",
        "prepare heroic strength 5",
        "prepare heroic strength 5",
    ]
    assert any("was too much (strained)" in text for text in arena.echoed)


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
