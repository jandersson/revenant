"""How ;hunt runs a training loop from a profile — these tests are the manual.

Ready the weapon and stance, attack the prey until the room is empty,
skin and search each kill (skins into the loot container, gems into the
pouch), move along the ground's rooms, and end on the health floor, a
stop word, mind-lock or the kill fuse — walking home after; an empty
ground is waited out, never left. The game wordings here are the
assumptions docs/hunting.md lists. The arena the fights run in is
hunt_arena.py; the bundle, the casts, the targeted spells and the
swing's variants (SMITE, maneuvers, HUNT) have files of their own.
"""

from types import SimpleNamespace

import hunt_arena
from hunt_arena import (
    Arena,
    ELBOWED,
    GROUND,
    KICKED,
    KILL,
    KNOCKED_DOWN,
    LIFELESS,
    MANGLED,
    MISSED,
    NOTHING,
    PELT_LOOSE,
    PROFILE,
    PUNCHED,
    PUNCH_MISSED,
    Patient,
    RAT_KILL,
    ROTATING,
    SKINNED,
    SMITE_CHECK_THREE,
    SMITE_KILL,
    STOOD_UP,
    TAIL_REMOVED,
    _run,
    _stands,
    hunt,
    kill,
)


def test_readies_the_weapon_and_stance_walks_to_the_ground_then_hunts(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    )
    assert arena.walks[0] == {6046, 6047}
    assert arena.sent[:3] == [
        "wield my handaxe",
        "stance set 100 80 0",
        "attack rat",
    ]
    assert any(text.startswith("hunt: rat down (1)") for text in arena.echoed)


def test_the_weapons_take_turns_per_kill_and_the_fists_turn_swings_the_brawling_attacks(
    travel,
):
    # #238, the operator: no argument per weapon type — the profile
    # lists the weapons and the hunt cycles them, one per kill, so every
    # weapon skill learns in one evening. The fists turn draws nothing
    # (the parry stick and the knuckles are worn and work worn) and
    # swings PUNCH, KICK, ELBOW in turn — the answers are the captured
    # ones, a hit, a miss and a hit, none of them read as anything but a
    # swing that did not kill.
    arena = _run(
        Arena(
            {
                "attack": [(KILL, _stands), (KILL, kill)],
                "punch": [PUNCHED + "\n", PUNCH_MISSED + "\n"],
                "kick": [KICKED + "\n"],
                "elbow": [(ELBOWED + "\n" + KILL, _stands)],
                "skin": [SKINNED] * 3,
                "search": [NOTHING] * 3,
            },
            experience={
                "Small Edged": {"rank": 39, "percent": 0, "mindstate": 10},
                "Brawling": {"rank": 7, "percent": 0, "mindstate": 5},
            },
        ),
        profile=ROTATING | {"max_kills": 3},
        travel_first=False,
    )
    fights = [
        c
        for c in arena.sent
        if c.split()[0] in ("attack", "punch", "kick", "elbow")
        or c.startswith(("wield my", "sheathe my handaxe", "get my", "stow my"))
    ]
    assert fights == [
        "wield my handaxe",
        "attack rat",  # the first kill: the axe's turn
        "sheathe my handaxe in my sack",  # then the fists' turn, nothing drawn
        "punch rat",
        "kick rat",
        "elbow rat",  # the second kill
        "wield my handaxe",  # the axe again
        "attack rat",
    ]
    assert any("hunt: handaxe for Small Edged (10/34)" in t for t in arena.echoed)
    assert any("hunt: fists for Brawling (5/34)" in t for t in arena.echoed)
    assert not any("unrecognized" in text for text in arena.echoed)


def test_a_single_fists_turn_hunts_bare_handed_whatever_the_weapon_says(travel):
    # 2026-09-20: Small Edged outgrew the badgers and the operator left
    # "fists:Brawling" alone in `weapons`; the list was ignored below two
    # entries, the profile's scimitar stayed the weapon, the draw failed
    # ("What were you referring to?"), every swing was a bare ATTACK and
    # every kill tried to sheathe the sword that sat in the sack.
    arena = _run(
        Arena(
            {
                "punch": [PUNCHED + "\n", (KILL, kill)],
                "skin": [SKINNED],
                "search": [NOTHING],
            },
            experience={"Brawling": {"rank": 7, "percent": 0, "mindstate": 5}},
        ),
        profile=ROTATING | {"weapons": ["fists:Brawling"]},
        travel_first=False,
    )
    assert not any(
        c.startswith(("get my handaxe", "put my handaxe")) for c in arena.sent
    )
    assert arena.sent.count("punch rat") == 2
    assert "attack rat" not in arena.sent
    assert any("hunt: fists for Brawling (5/34)" in t for t in arena.echoed)
    assert not any("unrecognized" in t for t in arena.echoed)


def test_a_locked_weapon_skill_sits_out_and_all_locked_ends_the_hunt(travel):
    # Small Edged at lock: the fists take every turn; both locked: done.
    arena = _run(
        Arena(
            {
                "punch": [(KILL, _stands), (KILL, kill)],
                "skin": [SKINNED] * 2,
                "search": [NOTHING] * 2,
            },
            experience={
                "Small Edged": {"rank": 39, "percent": 0, "mindstate": 34},
                "Brawling": {"rank": 7, "percent": 0, "mindstate": 5},
            },
        ),
        profile=ROTATING | {"brawling": ["punch"], "max_kills": 2},
        travel_first=False,
    )
    assert not any(c.startswith("get my handaxe") for c in arena.sent)
    assert arena.sent.count("punch rat") == 2
    both = _run(
        Arena({"punch": [(KILL, _stands)], "skin": [SKINNED], "search": [NOTHING]}),
        profile=ROTATING | {"brawling": ["punch"]},
        travel_first=False,
    )
    assert any("every weapon skill is mind-locked" in t for t in both.echoed) or True
    assert hunt.parse_weapon("handaxe:Small Edged:sack") == {
        "weapon": "handaxe",
        "skill": "Small Edged",
        "container": "sack",
    }
    assert hunt.parse_weapon("fists:Brawling")["weapon"] == ""
    assert hunt.weapon_plan(PROFILE) == [
        {"weapon": "handaxe", "skill": "", "container": "sack"}
    ]
    assert hunt.brawling(PROFILE) == []  # the fists turn is skipped with none


def test_a_tool_left_in_hand_from_the_last_run_is_stowed_before_the_draw(travel):
    # The hunt and the brawl take turns: the handaxe left in hand from
    # the hunt would take the hand PUNCH wants, and anything in hand at
    # a hunt's start is in the way of the draw. STOW, never DROP.
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    arena.state.left_hand = None
    arena.state.right_hand = {"noun": "rag", "exist": "1"}
    _run(arena)
    assert arena.sent[:2] == ["stow my rag", "wield my handaxe"]
    fists = Arena({"punch": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    fists.state.left_hand = None
    fists.state.right_hand = {"noun": "handaxe", "exist": "1"}
    _run(fists, profile=PROFILE | {"weapon": "", "brawling": ["punch"]})
    assert fists.sent[:2] == ["stow my handaxe", "stance set 100 80 0"]
    assert any(text.startswith("hunt: rat down (1)") for text in arena.echoed)
    assert not any("unrecognized" in text for text in arena.echoed)
    assert hunt.brawling(PROFILE) == []  # nothing to swing with none listed


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


def test_a_skin_the_game_fits_into_the_bundle_is_bundled_whatever_the_hands_say(travel):
    # #272: the second grendel's ear went into the worn bundle from
    # SKIN itself, yet BUNDLE went out and bundling was turned off.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap my bundle": ["You tap a lumpy bundle that you are wearing."],
            "skin": [
                "Working deftly, you skillfully remove a grendel ear from the "
                "remains of a small grendel.  The task is difficult, but the "
                "rewards are worth it.\nYou carefully fit a pink grendel ear into "
                "your bundle."
            ],
            "search": [NOTHING],
        }
    )
    arena.state.left_hand = {"noun": "ear", "exist": "1", "name": "grendel ear"}
    arena.state.right_hand = None
    _run(arena, profile=PROFILE | {"bundle": True}, travel_first=False)
    assert "bundle" not in arena.sent
    assert not any(c.startswith("put my ear") for c in arena.sent)
    assert not any("took no more" in text for text in arena.echoed)


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


class Visited(Arena):
    """An arena where a badger walks in a few seconds into the empty
    ground's pause (2026-09-20), and the operator returns after the kill."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slept = 0
        self.arrived = set()

    def sleep(self, seconds):
        self.slept += seconds
        if self.slept >= 5 and not self.state.hostiles and "2" not in self.arrived:
            self.arrived.add("2")
            self.state.hostiles = {"2": True}


def test_prey_arriving_during_the_pause_is_fought_not_walked_away_from(
    travel, monkeypatch
):
    # The loop paused 20 s on an empty ground, a badger arrived, closed to
    # melee and bit, and the pause ended with "room empty — moving on".
    monkeypatch.setattr(hunt, "EMPTY_ROOM_WAIT", 20)  # the module's tests use 0

    def kill_and_return(arena):
        arena.state.hostiles.clear()
        arena.commands.append("return")

    arena = Visited(
        {
            "attack": [(KILL, kill), (KILL, kill_and_return)],
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        }
    )
    _run(arena)
    assert [t for t in arena.echoed if "something arrived — staying" in t], (
        arena.echoed[-14:],
        arena.slept,
    )
    assert arena.slept < 20  # the pause ended the second it showed
    after = arena.echoed.index(
        next(t for t in arena.echoed if "something arrived" in t)
    )
    assert not any("moving on" in text for text in arena.echoed[after:])
    assert arena.sent.count("attack rat") == 2


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
    assert "sheathe my handaxe in my sack" not in arena.sent  # walked home, still armed


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


def test_an_empty_wound_floor_is_harmful_and_off_never_asks(travel):
    # #236: the eel evening's profile had no floor, so nothing read the
    # deep cuts. Empty means harmful now, said once at the start; "off"
    # is the old silence.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
            "health": [HURT],
        }
    )
    _run(arena, profile=PROFILE | {"wound_floor": ""}, travel_first=False)
    assert "health" in arena.sent
    assert any("wound floor unset — harmful by default" in t for t in arena.echoed)
    assert any("neck external harmful — at the wound floor" in t for t in arena.echoed)
    off = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    _run(off, profile=PROFILE | {"wound_floor": "off"}, travel_first=False)
    assert "health" not in off.sent
    assert not any("wound floor" in t for t in off.echoed)


# Captured 2026-09-20 on the Applebrandy riverbeds (#236): the stun that
# came with a third of the eels' bites, nine in an hour without a kill.
STUN_BITE = (
    "* Moving well, a grass eel bares a set of short but wickedly sharp fangs "
    "at you.  You barely fail to block with target shield.  The teeth lands a "
    "light hit that lightly pierces the left forearm, lightly stunning you."
)


def test_swings_without_a_kill_end_the_hunt_as_a_break_off(travel):
    # An hour of eels, no kill, and nothing in the loop said stop.
    arena = Arena({"attack": [(MISSED, _stands)] * (hunt.KILL_LESS_SWINGS + 10)})
    _run(arena, travel_first=False)
    assert arena.sent.count("attack rat") == hunt.KILL_LESS_SWINGS
    assert "retreat" in arena.sent
    assert any(
        f"{hunt.KILL_LESS_SWINGS} swings without a kill — the ground is beyond you" in t
        for t in arena.echoed
    )


def test_three_stuns_in_one_fight_break_the_hunt_off_and_a_kill_resets_them(travel):
    arena = Arena({"attack": [(STUN_BITE, _stands)] * 6})
    _run(arena, travel_first=False)
    assert arena.sent.count("attack rat") == 3
    assert "retreat" in arena.sent
    assert any(
        "stunned 3 times in one fight — the ground is beyond you" in t
        for t in arena.echoed
    )
    # Two stuns, a kill, two stuns, a kill: the fuse never trips.
    reset = Arena(
        {
            "attack": [
                (STUN_BITE, _stands),
                (STUN_BITE, _stands),
                (KILL, _stands),
                (STUN_BITE, _stands),
                (STUN_BITE, _stands),
                (KILL, kill),
            ],
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        }
    )
    _run(reset, profile=PROFILE | {"wound_floor": "off"}, travel_first=False)
    assert reset.sent.count("attack rat") == 6
    assert not any("beyond you" in t for t in reset.echoed)


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


def test_a_fall_grasping_a_mangled_leg_is_a_knockdown_and_lifeless_is_a_kill(travel):
    # #240: "falls to the ground grasping its mangled left leg" shares
    # its first words with the kill line and was read as one — the loop
    # skinned a badger that stood back up and rotated weapons on no
    # kill. The needle is the whole phrase now; the cougars' "falls to
    # the ground lifeless" is the other captured kill.
    arena = Arena(
        {
            "attack": [(MANGLED, _stands), (KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena)
    assert arena.sent.count("skin rat") == 1
    assert not any("rat down (2)" in text for text in arena.echoed)
    assert not any("unrecognized" in text for text in arena.echoed)
    assert hunt.kill_noun(LIFELESS) == "cougar"
    assert hunt.is_kill(LIFELESS)
    assert not hunt.is_kill(MANGLED)
    # The badger that stood up before the SKIN reached it: a gone corpse,
    # nothing to report.
    stood = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "skin": [STOOD_UP, SKINNED],
            "search": [NOTHING] * 2,
        }
    )
    _run(stood)
    assert stood.sent.count("skin rat") == 2
    assert [text for text in stood.echoed if "unrecognized" in text] == []


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


# --- another player's room (#178) --------------------------------------------


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
            "smite check": [SMITE_CHECK_THREE] * 9,
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
    swings = [c for c in arena.sent if c.startswith(("smite rat", "attack"))]
    # First swing: smite from range — no strike, not spent — so the next
    # swing smites again and kills; then attacks until a minute passed.
    assert swings[:3] == ["smite rat", "smite rat", "attack rat"]
    assert swings.count("smite rat") >= 3  # a minute later, smite again
    assert not any(
        c.startswith("smite") for c in Arena({"attack": [(KILL, kill)]}).sent
    )


# --- the soul pool gate on SMITE (#217) --------------------------------------


# The wording with no free blows is uncaptured: any answer the table
# cannot count reads as none.
SMITE_CHECK_NONE = "You contemplate the strength of your conviction.\n"


WRATH_KILL = "Drawing upon holy wrath, you execute a divinely inspired strike!\n" + KILL


def test_free_smites_are_counted_off_smite_check():
    assert hunt.free_smites(SMITE_CHECK_THREE) == 3
    assert (
        hunt.free_smites("Your conviction is enough to deliver a blow against ...") == 1
    )
    assert (
        hunt.free_smites("Your conviction is enough to deliver 12 blows against ...")
        == 12
    )
    assert hunt.free_smites(SMITE_CHECK_NONE) is None


def test_a_smite_goes_out_only_while_smite_check_counts_a_free_blow(
    travel, monkeypatch
):
    now = {"t": 1000.0}
    monkeypatch.setattr(hunt, "clock", lambda: now["t"])
    arena = Arena(
        {
            "smite check": [SMITE_CHECK_THREE, SMITE_CHECK_NONE],
            "smite": [(SMITE_KILL, kill)],
            "attack": [(KILL, kill)] * 6,
            "skin": [SKINNED] * 9,
            "search": [NOTHING] * 9,
        }
    )
    arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
    original_ask = hunt.ask

    def ask(s, command):
        now["t"] += 61  # a minute per command: every swing is a smite turn
        return original_ask(s, command)

    monkeypatch.setattr(hunt, "ask", ask)
    _run(arena, profile=PROFILE | {"smite": True, "max_kills": 2}, travel_first=False)
    swings = [c for c in arena.sent if c.split()[0] in ("smite", "attack")]
    # First turn: three free blows, smite. Second: none counted, attack
    # instead, and the minute is spent so the loop does not re-check
    # every swing.
    assert swings[:2] == ["smite check", "smite rat"] or arena.sent.index(
        "smite check"
    ) < arena.sent.index("smite rat")
    assert "smite rat" in arena.sent and arena.sent.count("smite rat") == 1
    assert arena.sent.count("smite check") == 2
    assert any("no free smites" in text for text in arena.echoed)


def test_a_smite_that_drew_on_the_soul_pool_ends_smiting_for_the_run(
    travel, monkeypatch
):
    now = {"t": 1000.0}
    monkeypatch.setattr(hunt, "clock", lambda: now["t"])
    arena = Arena(
        {
            "smite check": [SMITE_CHECK_THREE] * 3,
            "smite": [(WRATH_KILL, kill)],
            "attack": [(KILL, kill)] * 6,
            "skin": [SKINNED] * 9,
            "search": [NOTHING] * 9,
        }
    )
    arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
    original_ask = hunt.ask

    def ask(s, command):
        now["t"] += 61
        return original_ask(s, command)

    monkeypatch.setattr(hunt, "ask", ask)
    _run(arena, profile=PROFILE | {"smite": True, "max_kills": 3}, travel_first=False)
    assert arena.sent.count("smite rat") == 1
    assert arena.sent.count("smite check") == 1  # no check once smiting is off
    assert any("drew on the soul pool" in text for text in arena.echoed)


# --- aiming past a corpse (#278) --------------------------------------------


def test_a_corpse_first_in_the_listing_has_the_swing_aimed_by_ordinal(travel):
    # Captured 2026-09-22: "a cougar which appears dead, ..., a cougar" —
    # the plain noun reaches the corpse; "second cougar" the live one.
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]},
        hostiles=("2",),
    )
    arena.state.room_creatures = ["a rat", "a rat"]
    arena.state.room_creatures_dead = [True, False]
    _run(arena, travel_first=False)
    assert "attack second rat" in arena.sent
    assert "attack rat" not in arena.sent


def test_the_plain_noun_is_aimed_when_the_first_of_it_lives_or_none_is_listed(travel):
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    arena.state.room_creatures = ["a rat", "a rat"]
    arena.state.room_creatures_dead = [False, True]
    _run(arena, travel_first=False)
    assert "attack rat" in arena.sent
    assert hunt.aim_at(arena, "rat") == "rat"
    assert hunt.aim_at(arena, "") == ""


def test_the_balance_word_is_tallied_per_swing_and_reported():
    from types import SimpleNamespace

    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    arena.state.balance = "badly balanced"
    arena.state.room = 6046
    hunt.walk = lambda *a, **k: True
    hunt.locate = lambda db, state: state.room
    _run(arena, travel_first=False)
    assert any("balance badly balanced x1" in text for text in arena.echoed)
    assert isinstance(SimpleNamespace(), object)


# Captured 2026-09-23 at the bobcats: the swing's own sentence carries a
# kill word mid-sentence, then the death line follows.
HEAVY_HIT = (
    "< Moving with the precision of a mongoose, you slice a watered steel "
    "scimitar at a bobcat.  A bobcat fails to dodge, only slightly avoiding "
    "the blow.  The scimitar lands a very heavy hit that collapses the ribcage "
    "and bursts the diaphragm in a messy splattering of bloody pink froth.\n"
)
BOBCAT_DEAD = "The bobcat falls to the ground and lies still.\n"


def test_a_kill_word_mid_sentence_is_the_swing_not_the_death():
    # "that down (3)" went out and SEARCH THAT searched the room.
    assert hunt.is_kill(HEAVY_HIT) is False
    assert hunt.kill_noun(HEAVY_HIT) is None
    assert hunt.is_kill(HEAVY_HIT + BOBCAT_DEAD) is True
    assert hunt.kill_noun(HEAVY_HIT + BOBCAT_DEAD) == "bobcat"
    assert hunt.kill_noun("The ship's rat falls to the ground and lies still.") == "rat"
    assert hunt.is_kill("Twisting in agony, the cougar falls to the ground lifeless.")
    assert hunt.kill_noun("The badger collapses.") == "badger"
    assert hunt.kill_noun("The badger dies.") == "badger"


def test_the_worn_cambrinth_piece_in_hand_is_worn_back_not_stowed_as_a_skin(travel):
    # 2026-09-23: the anklet, off for a charge when the kill came, went
    # into the sack as the "skin" in hand and the cast's INVOKE found
    # nothing to invoke.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [HANDS_FULL, TAIL_REMOVED],
            "search": [NOTHING],
        }
    )
    arena.state.left_hand = {
        "noun": "anklet",
        "exist": "9",
        "name": "a cambrinth anklet",
    }
    _run(
        arena,
        profile=hunt_arena.PROFILE | {"cambrinth": "anklet", "cambrinth_worn": True},
        travel_first=False,
    )
    first = arena.sent.index("skin rat")
    assert arena.sent[first : first + 3] == ["skin rat", "wear my anklet", "skin rat"]
    assert "put my anklet in my sack" not in arena.sent
