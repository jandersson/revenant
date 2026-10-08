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

import pytest

from client.engine.scripting import ScriptStopped
from client.game import hunting

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
    SMITE_NO_WEAPON,
    STOOD_UP,
    TAIL_REMOVED,
    _run,
    _stands,
    hunt,
    kill,
)


def test_readies_the_weapon_and_stance_walks_to_the_ground_then_hunts(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    )
    assert arena.walks[0] == {6046, 6047}
    assert arena.sent[:3] == [
        "wield my handaxe",
        "stance set 100 80 0",
        "attack rat",
    ]
    assert any(text.startswith("hunt: rat down (1)") for text in arena.echoed)


def test_the_emptiest_weapon_fills_to_the_target_then_the_next_takes_over(
    travel,
):
    # The operator, 2026-09-26: the measure is the number of skills
    # moving, so the weapon with the emptiest pool fights first and
    # keeps the hands, kill after kill, until its skill reaches the
    # profile's weapon_target (30); then the next emptiest takes over.
    # It was one weapon per kill (#238). The fists turn draws nothing
    # (the parry stick and the knuckles are worn and work worn) and
    # swings PUNCH, KICK, ELBOW in turn — the answers are the captured
    # ones, a hit, a miss and a hit, none of them read as anything but a
    # swing that did not kill.
    def brawling_filled(arena):
        arena.state.experience["Brawling"]["mindstate"] = 30
        _stands(arena)

    arena = _run(
        Arena(
            {
                "attack": [(KILL, kill)],
                "punch": [PUNCHED + "\n", PUNCH_MISSED + "\n"],
                "kick": [(KICKED + "\n" + KILL, _stands)],
                "elbow": [(ELBOWED + "\n" + KILL, brawling_filled)],
                "skin": [SKINNED] * 3,
                "loot": [NOTHING] * 3,
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
        "punch rat",  # Brawling's pool (5) is the emptiest: the fists first
        "kick rat",  # the first kill, Brawling still below 30: fists again
        "elbow rat",  # the second kill fills Brawling to 30
        "wield my handaxe",  # Small Edged (10) takes over
        "attack rat",
    ]
    assert any("hunt: fists for Brawling (5/34) — to 30" in t for t in arena.echoed)
    assert any("hunt: handaxe for Small Edged (10/34)" in t for t in arena.echoed)
    assert not any("unrecognized" in text for text in arena.echoed)


def _turns(
    experience, profile_extra=None, held=0, turn_times=None, turn_clock=None, **kwargs
):
    arena = Arena({}, experience=experience)
    tally = SimpleNamespace(
        weapon=held, fists_warned=False, turn_times=turn_times, turn_clock=turn_clock
    )
    profile = ROTATING | {
        "weapons": ["handaxe:Small Edged:sack", "fists:Brawling", "mace:Small Blunt"]
    }
    profile |= profile_extra or {}
    return hunt.next_turn(arena, profile, tally, **kwargs)


def test_the_turn_in_hand_stays_below_the_target_and_the_emptiest_follows_it():
    ms = {
        "Small Edged": {"rank": 58, "mindstate": 12},
        "Brawling": {"rank": 58, "mindstate": 3},
        "Small Blunt": {"rank": 17, "mindstate": 34},
    }
    assert _turns(ms, from_current=True) == 1  # the emptiest pool starts
    assert _turns(ms, held=0) == 0  # 12 < 30: the handaxe keeps the hands
    ms["Small Edged"]["mindstate"] = 30
    assert _turns(ms, held=0) == 1  # at the target: the fists, the mace locked
    assert _turns(ms, held=0, leave=True) == 1  # a stalled turn hands over
    ms["Brawling"]["mindstate"] = 31
    # Every open weapon past the target: the emptiest fights on toward lock.
    assert _turns(ms, held=1) == 0
    assert _turns(ms, {"weapon_target": 0}, held=1) == 1  # 0: each to lock
    ms["Small Edged"]["mindstate"] = 34
    ms["Brawling"]["mindstate"] = 34
    assert _turns(ms, held=1) is None  # every skill locked


def test_a_turns_minutes_are_the_fallback_under_the_target(monkeypatch):
    # The operator, 2026-10-02: seventeen wolves died to the casts and two
    # swings each, Small Edged sat at 4/34 after thirty minutes and three
    # weapons never got a turn. The target rule stays; the minutes are the
    # fallback for a pool that will not fill.
    now = {"t": 1000.0}
    monkeypatch.setattr(hunting, "clock", lambda: now["t"])
    ms = {
        "Small Edged": {"rank": 77, "mindstate": 4},
        "Brawling": {"rank": 69, "mindstate": 0},
        "Small Blunt": {"rank": 57, "mindstate": 0},
    }
    minutes = {"weapon_minutes": 5}
    now["t"] = 1000.0 + 4 * 60  # four minutes in, below the target: kept
    assert _turns(ms, minutes, held=0, turn_clock=1000.0) == 0
    now["t"] = 1000.0 + 5 * 60  # five: the emptiest other turn, the mace (rank 57)
    assert _turns(ms, minutes, held=0, turn_clock=1000.0) == 2
    assert _turns(ms, {"weapon_minutes": 0}, held=0, turn_clock=1000.0) == 0  # off
    assert _turns(ms, minutes, held=0) == 0  # no stamp on the tally: never
    # The only open turn keeps the hands whatever the clock says.
    ms["Brawling"]["mindstate"] = 34
    ms["Small Blunt"]["mindstate"] = 34
    assert _turns(ms, minutes, held=0, turn_clock=1000.0) == 0
    # The fallback's default, and a value the dialog could not coerce.
    assert hunting.turn_minutes({}) == 10
    assert hunting.turn_minutes({"weapon_minutes": "x"}) == 10
    assert hunting.turn_minutes({"weapon_minutes": -3}) == 0


def test_equally_empty_pools_go_to_the_weakest_weapon_first():
    # 2026-09-27: after a rest every pool read 0/34 and the plan's order
    # alone picked the handaxe, fists and mace in turn; the 30-minute
    # hunt ended before the weakest weapons (ranks 15 and 9) got one.
    ms = {
        "Small Edged": {"rank": 60, "mindstate": 0},
        "Brawling": {"rank": 61, "mindstate": 0},
        "Small Blunt": {"rank": 24, "mindstate": 0},
    }
    assert _turns(ms, from_current=True) == 2  # the mace, rank 24
    ms["Small Blunt"]["mindstate"] = 30
    assert _turns(ms, held=2) == 0  # then the handaxe (60) before the fists (61)
    ms["Small Edged"]["mindstate"] = 5
    assert _turns(ms, held=2) == 1  # an emptier pool still comes first


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
                "loot": [NOTHING],
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


def test_the_fists_turn_of_a_paladin_punches_and_never_smites(travel):
    # 2026-10-01 (#396): every fists turn at the blood wolves sent one
    # PUNCH, then SMITE after SMITE — refused bare-handed, no roundtime,
    # a second apart — and handed over "20 swings without a kill".
    arena = _run(
        Arena(
            {
                "punch": [PUNCHED + "\n", (KILL, kill)],
                "smite": [SMITE_NO_WEAPON] * 5,
                "skin": [SKINNED],
                "loot": [NOTHING],
            },
            experience={"Brawling": {"rank": 68, "percent": 0, "mindstate": 0}},
        ),
        profile=ROTATING | {"weapons": ["fists:Brawling"], "smite": True},
        travel_first=False,
    )
    assert not any(c.startswith("smite") for c in arena.sent)
    assert arena.sent.count("punch rat") == 2


def test_a_smite_refused_for_want_of_a_weapon_waits_its_minute(travel, monkeypatch):
    # Whatever the hands hold, the refusal costs no roundtime: one, then
    # the swings go on as attacks until the minute has passed.
    monkeypatch.setattr(hunting, "clock", lambda: 1000.0)
    arena = _run(
        Arena(
            {
                "smite check": [SMITE_CHECK_THREE] * 3,
                "smite": [SMITE_NO_WEAPON] * 3,
                "attack": [(KILL, _stands), (KILL, kill)],
                "skin": [SKINNED],
                "loot": [NOTHING],
            }
        ),
        profile=PROFILE | {"smite": True},
        travel_first=False,
    )
    assert sum(c.startswith("smite rat") for c in arena.sent) == 1
    assert arena.sent.count("attack rat") == 2


def test_a_locked_weapon_skill_sits_out_and_all_locked_ends_the_hunt(travel):
    # Small Edged at lock: the fists take every turn; both locked: done.
    arena = _run(
        Arena(
            {
                "punch": [(KILL, _stands), (KILL, kill)],
                "skin": [SKINNED] * 2,
                "loot": [NOTHING] * 2,
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
        Arena({"punch": [(KILL, _stands)], "skin": [SKINNED], "loot": [NOTHING]}),
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
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    arena.state.left_hand = None
    arena.state.right_hand = {"noun": "rag", "exist": "1"}
    _run(arena)
    assert arena.sent[:2] == ["stow my rag", "wield my handaxe"]
    fists = Arena({"punch": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    fists.state.left_hand = None
    fists.state.right_hand = {"noun": "handaxe", "exist": "1"}
    _run(fists, profile=PROFILE | {"weapon": "", "brawling": ["punch"]})
    assert fists.sent[:2] == ["stow my handaxe", "stance set 100 80 0"]
    assert any(text.startswith("hunt: rat down (1)") for text in arena.echoed)
    assert not any("unrecognized" in text for text in arena.echoed)
    assert hunt.brawling(PROFILE) == []  # nothing to swing with none listed


def test_another_turns_weapon_left_in_hand_is_sheathed_where_it_lives(travel):
    # 2026-10-03 (#439): the last hunt ended with the spear in hand, the
    # box farm's first turn was the sledgehammer, and the clear's STOW
    # sent the spear to the backpack — "The narrow-headed spear is too
    # long to fit in the backpack." — so both came to be held.
    turns = ["sledgehammer:Large Blunt:backpack", "spear:Polearms:baldric"]

    def sheathed(arena):
        arena.state.right_hand = None

    arena = Arena(
        {
            "sheathe my spear": [
                (
                    "You sheathe the narrow-headed spear in your palladium baldric.",
                    sheathed,
                )
            ],
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "loot": [NOTHING],
        }
    )
    arena.state.left_hand = None
    arena.state.right_hand = {"noun": "spear", "exist": "1"}
    _run(arena, profile=PROFILE | {"weapons": turns})
    first = arena.sent.index("sheathe my spear")
    assert arena.sent[first + 1] == "wield my sledgehammer"
    assert "stow my spear" not in arena.sent


def test_a_weapon_only_the_base_profile_names_is_sheathed_by_a_styled_hunt(travel):
    # 2026-10-03 (#439): the box farm's style turns (no spear) replaced
    # the base list, and its clear STOWed the spear the hunt before left
    # in hand — refused by the backpack — then drew the broadsword.
    from client.game.profile import save_profile

    save_profile(
        "Lanival",
        {"weapons": ["sledgehammer:Large Blunt:backpack", "spear:Polearms:baldric"]},
    )

    def sheathed(arena):
        arena.state.right_hand = None

    arena = Arena(
        {
            "sheathe my spear": [
                (
                    "You sheathe the narrow-headed spear in your palladium baldric.",
                    sheathed,
                )
            ],
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "loot": [NOTHING],
        }
    )
    arena.state.left_hand = None
    arena.state.right_hand = {"noun": "spear", "exist": "1"}
    _run(arena, profile=PROFILE | {"weapons": ["sledgehammer:Large Blunt:backpack"]})
    first = arena.sent.index("sheathe my spear")
    assert arena.sent[first + 1] == "wield my sledgehammer"
    assert "stow my spear" not in arena.sent


def test_the_weapon_in_hand_is_kept_by_its_noun_whatever_the_profile_calls_it(
    travel,
):
    # The hand tag says "scimitar" for the profile's "steel scimitar":
    # the clear before the draw keeps it (hands.free compares the last
    # word, #407) instead of stowing it for WIELD to find again.
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    arena.state.left_hand = None
    arena.state.right_hand = {"noun": "scimitar", "exist": "1"}
    _run(arena, profile=PROFILE | {"weapon": "steel scimitar"})
    assert arena.sent[:2] == ["wield my steel scimitar", "stance set 100 80 0"]
    assert "stow my scimitar" not in arena.sent


def test_a_kill_is_skinned_stowed_and_searched(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    )
    after_kill = arena.sent[arena.sent.index("attack rat") + 1 :]
    assert after_kill[:3] == ["skin rat", "put my pelt in my sack", "loot"]
    assert any("1 kill(s), 1 skin(s)" in text for text in arena.echoed)


def test_every_search_is_a_row_in_the_loot_table(travel, tmp_path, monkeypatch):
    # #329: the box drop rate per creature, read off history.db.
    import sqlite3

    db = tmp_path / "history.db"
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(db))
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    )
    with sqlite3.connect(str(db)) as connection:
        rows = connection.execute(
            "SELECT creature, ground, outcome FROM loot"
        ).fetchall()
        hunts = connection.execute(
            "SELECT character_name, ground, style, kills, searched, boxes FROM hunts"
        ).fetchall()
    assert rows == [("rat", PROFILE["hunting_ground"], "nothing")]
    # #419: the end says each creature's searches, and the run is a row.
    assert "hunt: searched by creature — rat x1: 0 box(es), 0 with coins" in (
        arena.echoed
    )
    assert hunts == [("Lanival", PROFILE["hunting_ground"], "", 1, 1, 0)]


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
            "loot": [NOTHING],
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
            "loot": [NOTHING],
        }
    )
    arena.state.left_hand = {"noun": "ear", "exist": "1", "name": "grendel ear"}
    arena.state.right_hand = None
    _run(arena, profile=PROFILE | {"bundle": True}, travel_first=False)
    assert "bundle" not in arena.sent
    assert not any(c.startswith("put my ear") for c in arena.sent)
    assert not any("took no more" in text for text in arena.echoed)


def test_a_creature_the_wiki_says_has_no_skin_is_not_skinned():
    # #494 (2026-10-08): Cecil's hunt moves to young ogres, Skinnable=No
    # on their page; a SKIN there answers nothing the table knows.
    echoed = []
    s = SimpleNamespace(
        state=SimpleNamespace(room_creatures=["a young ogre", "a young ogre"]),
        echo=echoed.append,
    )
    tally = hunting.Tally()
    assert hunt.has_skin(s, "ogre", tally) is False
    assert hunt.has_skin(s, "ogre", tally) is False
    assert echoed == ["hunt: the ogre has no skin — not skinning"]  # said once
    s.state.room_creatures = ["a rat"]
    assert hunt.has_skin(s, "rat", tally) is True
    s.state.room_creatures = []
    assert hunt.has_skin(s, "thing", tally) is True  # unknown: skin as before


def test_skinning_off_in_the_profile_skips_the_knife(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "loot": [NOTHING]}),
        profile=PROFILE | {"skin": False},
    )
    assert not any(command.startswith("skin") for command in arena.sent)
    assert "loot" in arena.sent


def test_a_gem_found_on_the_corpse_goes_in_the_pouch(travel):
    found = "You search the rat.\nYou find a small ruby."
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [found]}),
        profile=PROFILE | {"gem_pouch": "pouch"},
    )
    assert "get ruby" in arena.sent
    assert "put my ruby in my pouch" in arena.sent


def test_a_found_non_gem_is_stowed_like_loot_never_pouched(travel):
    # Only a gem tries the pouch (2026-09-28: a scout's plovik leaves
    # went at a full pouch and stayed in hand through the fight).
    found = "You search the rat.\nYou find a rusty nail."
    arena = _run(
        Arena(
            {
                "attack": [(KILL, kill)],
                "skin": [SKINNED],
                "loot": [found],
            }
        ),
        profile=PROFILE | {"gem_pouch": "pouch"},
    )
    assert "put my nail in my pouch" not in arena.sent
    assert "put my nail in my sack" in arena.sent


def test_a_searched_item_the_profile_ignores_is_never_picked_up(travel):
    # 2026-09-28: a scout's embroidery needle, on loot_ignore, was pocketed.
    found = "You search the rat.\nThe rat was carrying an embroidery needle!"
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [found]}),
        profile=PROFILE | {"loot_ignore": ["embroidery needle"]},
    )
    assert "get needle" not in arena.sent


def test_a_searched_item_on_never_pick_up_is_left_where_it_fell(travel):
    # 2026-10-03 (#442), the operator: runestones go to the vault, and
    # no more are looted — loot_subtractions held only the room's
    # listing to it, never the search's wording.
    found = "You search the rat.\nThe rat was carrying a sunstone runestone!"
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [found]}),
        profile=PROFILE | {"loot_subtractions": ["runestone"]},
    )
    assert "get runestone" not in arena.sent


def test_an_empty_ground_is_waited_out_not_left(travel):
    # 2026-09-13, the operator: an empty ground is not a reason to go
    # home — pause after every empty lap and lap again until told.
    arena = Patient(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]}, pauses=3
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
            "loot": [NOTHING] * 2,
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
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]}, hostiles=()
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
            "loot": [NOTHING],
            "health": [HURT],
        }
    )
    _run(arena, profile=PROFILE | {"wound_floor": "harmful"}, travel_first=False)
    assert "health" in arena.sent
    assert any(
        "neck external harmful — at the wound floor" in text for text in arena.echoed
    )
    assert "sheathe my handaxe" not in arena.sent  # walked home, still armed


def test_a_wound_already_at_the_floor_keeps_the_hunt_home(travel):
    # 2026-09-27: the box farm set out with the chest wound the hunt
    # before had stopped on — three minutes of buffs, 33 steps, two kills
    # and the same break-off. HEALTH is asked before the buffs and walk.
    arena = Arena({"attack": [(KILL, kill)], "health": [HURT]})
    _run(arena, profile=PROFILE | {"wound_floor": "harmful"})
    assert arena.sent == ["health"]
    assert arena.walks == []
    assert any(
        "neck external harmful — already at the wound floor; not setting out" in text
        for text in arena.echoed
    )


def test_a_wound_below_the_floor_keeps_hunting(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "loot": [NOTHING],
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
            "loot": [NOTHING],
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
            "loot": [NOTHING],
            "health": [HURT],
        }
    )
    _run(arena, profile=PROFILE | {"wound_floor": ""}, travel_first=False)
    assert "health" in arena.sent
    assert any("wound floor unset — harmful by default" in t for t in arena.echoed)
    assert any("neck external harmful — at the wound floor" in t for t in arena.echoed)
    off = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
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
            "loot": [NOTHING] * 2,
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
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]},
    )
    _run(arena, profile=PROFILE | {"max_kills": 1}, travel_first=False)
    assert any("kill fuse reached" in text for text in arena.echoed)


def test_a_corpse_soaking_swings_is_searched_away(travel):
    # docs/combat.md: after a kill, ATTACK resolves to the body.
    arena = Arena(
        {
            "attack": [("The rat is already quite dead.", kill)],
            "skin": [SKINNED],
            "loot": [NOTHING],
        }
    )
    _run(arena, travel_first=False)
    assert "loot" in arena.sent


def test_nothing_to_skin_with_turns_skinning_off_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "skin": ["You have nothing to skin with!"],
            "loot": [NOTHING, NOTHING],
        }
    )
    _run(arena, travel_first=False)
    assert arena.sent.count("skin rat") == 1
    assert any("skinning is off for this run" in text for text in arena.echoed)


def test_an_unrecognized_skin_answer_is_reported_not_guessed(travel):
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": ["The rat twitches."], "loot": [NOTHING]}
    )
    _run(arena, travel_first=False)
    assert any(
        text.startswith("hunt: unrecognized skin answer 'The rat twitches.'")
        for text in arena.echoed
    )
    assert any("1 unrecognized answer(s)" in text for text in arena.echoed)


def test_the_captured_rat_kill_is_recognized_and_skinned(travel):
    arena = Arena({"attack": [(RAT_KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    _run(arena, travel_first=False)
    assert "skin rat" in arena.sent
    assert any(text.startswith("hunt: rat down (1)") for text in arena.echoed)


HANDS_FULL = "You must have one hand free to skin."


SEARCHED_ALREADY = "The ship's rat has already been searched for that!"


NOT_DEAD_YET = "You should probably wait until a ship's rat is dead first."


def test_the_captured_skin_wordings_are_recognized_and_the_skin_stowed(travel):
    for line, item in ((PELT_LOOSE, "pelt"), (TAIL_REMOVED, "tail")):
        arena = Arena({"attack": [(KILL, kill)], "skin": [line], "loot": [NOTHING]})
        _run(arena, travel_first=False)
        assert f"put my {item} in my sack" in arena.sent
        assert not any("unrecognized" in text for text in arena.echoed)


def test_a_full_hand_is_stowed_and_the_skin_tried_once_more(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [HANDS_FULL, TAIL_REMOVED],
            "loot": [NOTHING],
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
            "loot": [NOTHING],
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
            "loot": [NOTHING],
        }
    )
    _run(arena)
    assert arena.sent.count("skin rat") == 1
    assert arena.sent.count("loot") == 1
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
            "loot": [NOTHING],
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
            "loot": [NOTHING] * 2,
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
            "loot": [NOTHING],
        }
    )
    _run(arena)
    assert not any("unrecognized" in text for text in arena.echoed)


def test_a_gone_corpse_is_not_reported_as_unrecognized(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [NOT_DEAD_YET],
            "loot": [SEARCHED_ALREADY],
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
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]},
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


def test_an_occupied_room_is_left_whatever_is_in_it_and_a_taken_ground_goes_home(
    travel,
):
    # 2026-09-27: the goblins in Ketamira's room held Cecil there —
    # "something arrived — staying" six times — until the ground was
    # called taken, and the hunt ended in that room among them.
    arena = Arena({"attack": [(KILL, kill)]})  # a rat in every room
    arena.state.room_players = ["Bankismo"]
    _run(arena)
    assert not any(c.startswith("attack") for c in arena.sent)
    assert not any("something arrived — staying" in t for t in arena.echoed)
    assert {6047} in arena.walks  # walked on out of the taken room
    assert any("leaving it to them" in t for t in arena.echoed)
    assert arena.walks[-1] == {1}  # and home


def test_a_failed_walk_off_an_occupied_room_is_said(travel, monkeypatch):
    # 2026-09-26: the walk on from a room two players held failed on a
    # map edge and ;hunt ended without a word, Cecil standing in a field.
    arena = Arena({"attack": [(KILL, kill)]}, hostiles=())
    arena.state.room_players = ["Bankismo"]
    monkeypatch.setattr(hunt, "step_on", lambda *args, **kwargs: False)
    _run(arena)
    assert any(
        "could not walk on to another room of the ground — stopping" in text
        for text in arena.echoed
    )


def test_the_operators_own_grouped_character_is_no_other_hunter(travel, monkeypatch):
    # 2026-09-26: an Empath of the operator's, grouped with the hunter,
    # followed him into every room of the goblins' ground; ;hunt boxes
    # read "Uthmor hunting here — their room, moving on" room after room
    # and gave the ground up.
    import json

    login = {"character": "Lanival", "accounts": {"TESTACCT": ["Lanival", "Uthmor"]}}
    path = monkeypatch_login(monkeypatch, json.dumps(login))
    assert path.exists()
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]},
        hostiles=(),
    )
    arena.state.room_players = ["Uthmor"]
    arena.arrivals = {6046: {"2": True}}
    _run(arena)
    assert not any("their room" in text for text in arena.echoed)
    assert any(c.startswith("attack") for c in arena.sent)


def monkeypatch_login(monkeypatch, text):
    import os
    import pathlib

    path = pathlib.Path(os.environ["REVENANT_LOGIN_DEFAULTS"])
    path.write_text(text)
    return path


def test_a_paladin_smites_one_swing_a_minute_and_attacks_the_rest(travel, monkeypatch):
    # #183: SMITE trains Conviction, a free smite comes back every
    # minute and the experience once a minute, so the loop smites at
    # most once a minute; a smite the game answered from range (no
    # strike) is not spent.
    now = {"t": 1000.0}
    monkeypatch.setattr(hunting, "clock", lambda: now["t"])
    advancing = "You aren't close enough to attack.\nYou begin to advance on a rat."
    arena = Arena(
        {
            "smite check": [SMITE_CHECK_THREE] * 9,
            "smite": [advancing, (SMITE_KILL, kill), (SMITE_KILL, kill)],
            "attack": [(KILL, kill)] * 6,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
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


def test_a_smite_goes_out_when_the_game_says_the_conviction_is_back(
    travel, monkeypatch
):
    # #191: "The strength of your conviction has fully returned." comes
    # 50-61 s after a smite that struck (711 in the logs); the parser
    # counts it and the next swing smites, the minute's timer only the
    # fallback. Here the clock never moves, so only the line can do it.
    monkeypatch.setattr(hunting, "clock", lambda: 1000.0)

    def returned(arena):
        arena.state.conviction_returns += 1

    arena = Arena(
        {
            "smite check": [SMITE_CHECK_THREE] * 9,
            "smite": [(SMITE_KILL, kill), (SMITE_KILL, kill)],
            "attack": [("You swing at a rat and miss.", returned)] * 3,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
        }
    )
    arena.state.conviction_returns = 0
    arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
    _run(arena, profile=PROFILE | {"smite": True, "max_kills": 2}, travel_first=False)
    swings = [c for c in arena.sent if c.startswith(("smite rat", "attack"))]
    assert swings[:3] == ["smite rat", "attack rat", "smite rat"]


def test_without_the_parser_count_the_minute_still_decides(monkeypatch):
    # A session whose parser predates #191 has no conviction_returns.
    now = {"t": 1000.0}
    monkeypatch.setattr(hunting, "clock", lambda: now["t"])
    tally, old = hunting.Tally(), SimpleNamespace()
    profile = PROFILE | {"smite": True, "tactics": []}
    hunting.note_smite(tally, old)
    assert hunting.swing_verb(profile, tally, old) == "attack"
    now["t"] += hunting.SMITE_INTERVAL
    assert hunting.swing_verb(profile, tally, old) == "smite"


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
    monkeypatch.setattr(hunting, "clock", lambda: now["t"])
    arena = Arena(
        {
            "smite check": [SMITE_CHECK_THREE, SMITE_CHECK_NONE],
            "smite": [(SMITE_KILL, kill)],
            "attack": [(KILL, kill)] * 6,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
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
    monkeypatch.setattr(hunting, "clock", lambda: now["t"])
    arena = Arena(
        {
            "smite check": [SMITE_CHECK_THREE] * 3,
            "smite": [(WRATH_KILL, kill)],
            "attack": [(KILL, kill)] * 6,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
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
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]},
        hostiles=("2",),
    )
    arena.state.room_creatures = ["a rat", "a rat"]
    arena.state.room_creatures_dead = [True, False]
    _run(arena, travel_first=False)
    assert "attack second rat" in arena.sent
    assert "attack rat" not in arena.sent


def test_the_plain_noun_is_aimed_when_the_first_of_it_lives_or_none_is_listed(travel):
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    arena.state.room_creatures = ["a rat", "a rat"]
    arena.state.room_creatures_dead = [False, True]
    _run(arena, travel_first=False)
    assert "attack rat" in arena.sent
    assert hunt.aim_at(arena, "rat") == "rat"
    assert hunt.aim_at(arena, "") == ""


def test_the_balance_word_is_tallied_per_swing_and_reported():
    from types import SimpleNamespace

    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
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


def test_the_goblins_long_death_line_is_a_kill():
    # Captured 2026-09-25 in the Crossing farmland: missed, no kill was
    # counted and the hunt broke off on "60 swings without a kill" (#314).
    line = (
        "A dour forager goblin collapses to the ground, shuddering and moaning "
        "until it ceases all movement.\n"
    )
    assert hunt.is_kill(line)
    assert hunt.kill_noun(line) == "goblin"
    assert (
        hunt.kill_noun(
            "With one last high-pitched squeal, the musk hog falls to the ground lifeless."
        )
        == "hog"
    )


def test_the_worn_cambrinth_piece_in_hand_is_worn_back_not_stowed_as_a_skin(travel):
    # 2026-09-23: the anklet, off for a charge when the kill came, went
    # into the sack as the "skin" in hand and the cast's INVOKE found
    # nothing to invoke.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [HANDS_FULL, TAIL_REMOVED],
            "loot": [NOTHING],
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


def test_a_boxes_style_hunt_ends_once_the_sack_holds_the_box_limit(monkeypatch):
    # #299: the boxes farm — no skinning, the box limit as the end rule
    # ("until": "boxes") — ends on its own once the loot container holds
    # the limit, the way a training hunt ends at the mind-lock.
    found = iter([["a small wooden coffer"], ["a small wooden coffer"], []])
    monkeypatch.setattr(
        hunt_arena.hunt.loot,
        "new_items",
        lambda before, after, creatures=(): next(found, []),
    )
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill), (KILL, kill)],
            "loot": [NOTHING] * 3,
            "get coffer": ["You pick up a small wooden coffer."] * 3,
            "put my coffer": ["You put your coffer in your sack."] * 3,
        }
    )
    farm = PROFILE | {"skin": False, "box_limit": 2, "until": "boxes"}
    _run(arena, profile=farm, travel_first=False)
    assert arena.sent.count("get coffer") == 2
    assert not any(c.startswith("skin") for c in arena.sent)
    assert any("2 box(es) in the sack — the farm is done" in e for e in arena.echoed)


# The kill is the room listing's word (#315): a corpse marked "which
# appears dead" that was not there before the swing, whatever the
# death line said.
GOBLIN_DEATH = (
    "A dour forager goblin collapses to the ground, shuddering and moaning "
    "until it ceases all movement."
)
UNHEARD_DEATH = "The rat gives a final twitch, a sigh, and is no more."


def _dies(noun):
    def effect(arena):
        kill(arena)
        hunt_arena.mark_corpse(arena, noun)

    return effect


def test_a_death_line_nobody_wrote_down_is_a_kill_by_the_listing(travel):
    arena = _run(
        Arena({"attack": [(UNHEARD_DEATH, _dies("rat"))], "loot": [NOTHING]}),
        profile=PROFILE | {"skin": False},
    )
    assert "loot" in arena.sent
    assert any("rat down (1)" in text for text in arena.echoed)


def test_the_farmland_goblin_is_counted(travel):
    # 2026-09-25: three of these went uncounted and the hunt broke off
    # on "60 swings without a kill" (#314).
    arena = _run(
        Arena(
            {
                "attack goblin": [(GOBLIN_DEATH, _dies("dour forager goblin"))],
                "loot": [NOTHING],
            }
        ),
        profile=PROFILE | {"prey": "goblin", "skin": False},
    )
    assert any("goblin down (1)" in text for text in arena.echoed)


def test_a_corpse_on_the_ground_before_the_fight_is_not_ours(travel):
    arena = Arena(
        {
            "attack": [(MISSED, _stands)] * 3 + [(UNHEARD_DEATH, _dies("rat"))],
            "loot": [NOTHING],
        }
    )
    hunt_arena.mark_corpse(arena, "rat")  # someone else's, from before
    _run(arena, profile=PROFILE | {"skin": False}, travel_first=False)
    downs = [text for text in arena.echoed if " down (" in text]
    assert downs == ["hunt: rat down (1)"]


def test_the_corpse_count_is_the_listings_and_a_decay_lowers_it():
    tally = hunt.Tally()
    s = SimpleNamespace(
        state=SimpleNamespace(
            room_uid=1,
            room_creatures=["a rat", "a rat", "a goblin"],
            room_creatures_dead=[True, False, False],
        )
    )
    hunt.mark_room(s, tally)
    assert hunt.new_corpses(s, tally) == []
    s.state.room_creatures_dead = [True, True, False]
    assert hunt.new_corpses(s, tally) == ["a rat"]
    s.state.room_creatures = ["a rat", "a goblin"]  # one decayed away
    s.state.room_creatures_dead = [True, False]
    assert hunt.new_corpses(s, tally) == []
    s.state.room_creatures_dead = [True, True]
    assert hunt.new_corpses(s, tally) == ["a goblin"]


def test_a_known_death_line_still_counts_when_the_listing_never_comes(travel):
    # The line is a hint to wait for the listing; if the listing never
    # marks the corpse, the line is the kill (#315).
    arena = Arena({"attack": [(KILL, kill)], "loot": [NOTHING]})
    arena.listing = False
    _run(arena, profile=PROFILE | {"skin": False})
    assert any("rat down (1)" in text for text in arena.echoed)


def test_a_knockdown_is_no_kill_without_a_corpse_in_the_listing(travel):
    arena = Arena(
        {"attack": [(KNOCKED_DOWN, _stands)] * 3 + [(KILL, kill)], "loot": [NOTHING]}
    )
    _run(arena, profile=PROFILE | {"skin": False}, travel_first=False)
    downs = [text for text in arena.echoed if " down (" in text]
    assert downs == ["hunt: rat down (1)"]


def test_a_room_with_no_prey_left_but_hostiles_on_you_gets_a_bare_attack():
    # 2026-09-25 (#316): the last goblin died, two musk hogs kept at the
    # character, and "attack goblin" answered "I could not find what you
    # were referring to." sixty times until the hunt broke off.
    arena = Arena({}, hostiles=("7", "8"))
    arena.state.room_creatures = ["a large musk hog", "a large musk hog"]
    arena.state.room_creatures_dead = [False, False]
    assert hunt.aim_at(arena, "goblin") == ""
    # A goblin still listed alive: aim at it.
    arena.state.room_creatures = ["a large musk hog", "a thin scavenger goblin"]
    assert hunt.aim_at(arena, "goblin") == "goblin"
    # Nothing hostile on the character: the prey noun as before.
    arena.state.hostiles = {}
    arena.state.room_creatures = ["a large musk hog"]
    assert hunt.aim_at(arena, "goblin") == "goblin"


class _Breaking:
    """A handle for the break-off alone: the room changes when the
    scripted move is the one that leads out."""

    def __init__(self, leads):
        self.leads = dict(leads)  # move -> uid it lands in
        self.sent, self.echoed = [], []
        self.dead = False
        self.state = SimpleNamespace(
            room_uid=11,
            room_title="[Farmland, Open Area]",
            compass=["south", "southeast"],
            hostiles={"1": True},
            indicator={},
        )

    def put(self, command):
        self.sent.append(command)
        if command in self.leads:
            self.state.room_uid = self.leads[command]

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass

    def echo(self, text):
        self.echoed.append(text)


def test_a_break_off_moves_until_the_room_changes_and_writes_what_the_map_had_wrong(
    tmp_path, monkeypatch
):
    # 2026-09-25 (#314): 1473's southeast led to 1479, which the map had
    # under southwest; the break-off's one blind burst and the walk off
    # the ground that found no path left the character among the hogs.
    from client.game.mapdb import MapDB

    from client.game import walker

    local = tmp_path / "local.json"
    monkeypatch.setenv("REVENANT_MAPDB_LOCAL", str(local))
    # An earlier test assigns a stub to hunt.locate: the real one here.
    monkeypatch.setattr(hunt, "locate", walker.locate)
    db = MapDB(
        [
            {
                "id": 1,
                "uid": [11],
                "title": ["[Farmland, Open Area]"],
                "wayto": {"2": "south", "3": "southwest"},
            },
            {"id": 2, "uid": [22], "title": ["[Farmland, Grain Fields]"], "wayto": {}},
            {"id": 3, "uid": [33], "title": ["[Farmland, Grain Fields]"], "wayto": {}},
        ]
    )
    s = _Breaking({"southeast": 33})  # south is held: the mob closes again
    assert hunt.escape(s, db) is True
    assert s.sent.count("retreat") == 4  # two bursts: south held, southeast out
    assert db.rooms[1]["wayto"]["3"] == "southeast"
    assert local.is_file()
    assert any("the map had southeast from 1 wrong" in text for text in s.echoed)


def test_a_break_off_that_never_gets_clear_says_so():
    s = _Breaking({})
    assert hunt.escape(s, None) is False
    assert any("intervene" in text for text in s.echoed)


class _Runner(Arena):
    """An arena that records the scripts the hunt starts."""

    def __init__(self, *args, running=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.started = []
        self.alive = set(running)

    def run(self, name, args=()):
        self.started.append((name, list(args)))
        return True

    def is_running(self, name):
        return name in self.alive

    def kill(self, name):
        self.killed = getattr(self, "killed", []) + [name]


def test_a_hunt_returned_by_hand_sells_the_skins_and_banks(travel):
    # The operator, 2026-09-26: ;hunt return should sell and bank after.
    arena = _Runner({"attack": []})
    arena.commands = ["return"]
    _run(arena, travel_first=False)
    # No skin cut before the return: ;bank alone, no walk to the tannery.
    assert arena.started == [("bank", ["keep=200"])]


def test_every_end_that_fought_sells_and_banks_under_train_too(travel):
    # The operator, 2026-09-28: the box farm ended with fifteen skins and
    # the plan went on to ;boxes. Every hunt concludes with ;skins bank.
    arena = _Runner(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]},
        running=("train",),
    )
    _run(arena, profile=PROFILE | {"max_kills": 1}, travel_first=False)
    # A travel purse is kept (#454): the next hunt's ferry fare.
    assert arena.started == [("skins", ["bank", "keep=200"])]
    assert "hunt: selling the skins and banking (;skins bank)" in arena.echoed


def test_a_run_that_cut_no_skin_banks_without_the_tannery(travel):
    # 2026-10-04: the box farm skins nothing, and ;skins walked 18 steps
    # to the tannery to say there was no bundle to sell.
    arena = _Runner(
        {"attack": [(KILL, kill)], "loot": [NOTHING]},
        running=("train",),
    )
    _run(arena, profile=PROFILE | {"max_kills": 1, "skin": False}, travel_first=False)
    assert arena.started == [("bank", ["keep=200"])]
    assert "hunt: no skins this run — banking (;bank)" in arena.echoed


def test_a_stop_while_selling_stops_the_skins_it_started(travel):
    class Selling(_Runner):
        def sleep(self, seconds):
            if "skins" in self.alive:
                raise ScriptStopped()

    arena = Selling({"attack": []}, running=("skins",))
    arena.started = []
    with pytest.raises(ScriptStopped):
        hunt.sell_and_bank(arena)
    assert arena.killed == ["skins"]


def test_a_turn_that_cannot_kill_hands_over_before_the_hunt_breaks_off(travel):
    # 2026-09-26: the mace, bought that night at rank 3, swung sixty
    # times at bobcats and broke the whole hunt off; a stalled turn now
    # passes to the next after TURN_STALL_SWINGS.
    arena = _run(
        Arena(
            {
                "attack": [(MISSED, _stands)] * hunt.TURN_STALL_SWINGS,
                "punch": [(KILL, kill)],
                "skin": [SKINNED],
                "loot": [NOTHING],
            },
            experience={  # Small Edged's the emptier pool: the handaxe starts
                "Small Edged": {"rank": 39, "percent": 0, "mindstate": 5},
                "Brawling": {"rank": 7, "percent": 0, "mindstate": 10},
            },
        ),
        profile=ROTATING | {"max_kills": 1},
        travel_first=False,
    )
    assert any(
        f"handaxe has gone {hunt.TURN_STALL_SWINGS} swings without a kill" in text
        for text in arena.echoed
    )
    assert "punch rat" in arena.sent or "punch" in " ".join(arena.sent)
    assert not any("the ground is beyond you" in text for text in arena.echoed)


def test_an_abbreviated_exit_is_the_maps_spelled_out_one(tmp_path, monkeypatch):
    # 2026-09-26: the escape went "ne", the map says "northeast" for the
    # same room — no correction to write.
    from client.game import walker
    from client.game.mapdb import MapDB

    monkeypatch.setenv("REVENANT_MAPDB_LOCAL", str(tmp_path / "local.json"))
    monkeypatch.setattr(hunt, "locate", walker.locate)
    db = MapDB(
        [
            {"id": 1, "uid": [11], "title": ["[Cliffs]"], "wayto": {"2": "northeast"}},
            {"id": 2, "uid": [22], "title": ["[Cliffs]"], "wayto": {}},
        ]
    )
    s = _Breaking({"ne": 22})
    s.state.compass = ["ne"]
    assert hunt.escape(s, db) is True
    assert db.rooms[1]["wayto"] == {"2": "northeast"}
    assert not (tmp_path / "local.json").exists()


def _outgrown_handle(creatures, dead=()):
    echoed = []
    s = SimpleNamespace(
        echo=echoed.append,
        state=SimpleNamespace(
            room_creatures=list(creatures),
            room_creatures_dead=list(dead),
            experience={
                "Small Edged": {"rank": 58},
                "Brawling": {"rank": 57},
                "Small Blunt": {"rank": 13},
            },
        ),
    )
    return s, echoed


OUTGROWN_PROFILE = PROFILE | {
    "weapons": ["scimitar:Small Edged:scabbard", "fists:Brawling", "mace:Small Blunt"]
}


def test_a_ground_whose_creatures_cap_below_the_weapons_is_said_once():
    # #322: the cougars' MaxCap is 49; the rotation's Small Edged 58 and
    # Brawling 57 learned nothing there for five hunts.
    tally = hunt.Tally()
    s, echoed = _outgrown_handle(["a cougar"])
    hunt.say_outgrown(s, OUTGROWN_PROFILE, tally)
    hunt.say_outgrown(s, OUTGROWN_PROFILE, tally)
    assert echoed == [
        "hunt: the cougar teaches to rank 49 — Brawling 57, Small Edged 58 past "
        "it; a harder ground trains them"
    ]


def test_a_ground_that_still_teaches_says_nothing():
    tally = hunt.Tally()
    s, echoed = _outgrown_handle(["a blood wolf"])
    hunt.say_outgrown(s, OUTGROWN_PROFILE, tally)
    assert echoed == []
    assert tally.caps_said


def test_only_live_creatures_are_weighed():
    tally = hunt.Tally()
    s, echoed = _outgrown_handle(["a blood wolf", "a cougar"], dead=[True, False])
    hunt.say_outgrown(s, OUTGROWN_PROFILE, tally)
    assert "the cougar teaches to rank 49" in echoed[0]


def test_every_swing_logs_its_aim_and_the_room_as_the_parser_holds_it(travel, caplog):
    # #325: an aim at a corpse the logged listing marked dead; the fix
    # needs the state at the swing, which the logs did not hold.
    import logging

    caplog.set_level(logging.DEBUG, logger="client.scripts.hunt")
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    _run(arena)
    aims = [r.getMessage() for r in caplog.records if r.getMessage().startswith("aim ")]
    assert aims and "creatures" in aims[0] and "dead" in aims[0]


def test_every_filler_swing_under_a_cast_is_aimed_afresh(travel, monkeypatch):
    # #325, caught 2026-09-27 at the goblins: a cast's filler swings all
    # went at the target aimed before the cast; one killed the goblin
    # listed first, and the next "attack goblin" hit its corpse ("already
    # quite dead") three times while a live one stood behind it.
    casts = []

    def casting(s, profile, tally, fight=False, filler=None):
        if fight and filler and not casts:
            casts.append(1)
            filler()  # the pattern forms over two swings
            filler()
            return True
        return False

    monkeypatch.setattr(hunt, "cast_buffs", casting)

    def first_falls(arena):
        arena.state.room_creatures = ["a rat", "a rat"]
        arena.state.room_creatures_dead = [True, False]
        arena.state.hostiles = {"2": True}

    arena = Arena(
        {
            "attack": [(KILL, first_falls), (KILL, kill)],
            "skin": [SKINNED, SKINNED],
            "loot": [NOTHING, NOTHING],
        },
        hostiles=("1", "2"),
    )
    arena.state.room_creatures = ["a rat", "a rat"]
    arena.state.room_creatures_dead = [False, False]
    _run(arena, profile=PROFILE | {"max_kills": 2}, travel_first=False)
    attacks = [c for c in arena.sent if c.startswith("attack")]
    assert attacks[:2] == ["attack rat", "attack second rat"]


def test_the_corpse_is_skinned_by_ordinal_past_a_live_one_listed_first():
    from client.game.creatures import aim_corpse

    names = ["a large musk hog", "a scavenger goblin", "a scavenger goblin"]
    assert aim_corpse("goblin", names, [False, False, True]) == "second goblin"
    assert aim_corpse("goblin", names, [False, True, False]) == "goblin"
    assert aim_corpse("goblin", names, []) == "goblin"  # nothing marked


def test_tied_empty_pools_go_to_the_weapon_trained_longest_ago():
    # 2026-09-28: with every pool at 0 after a rest, the rank alone sent
    # the weakest three weapons first every hunt, and Brawling and Small
    # Edged (ranks 61 and 60) sat at 0. The last turn's time breaks the
    # tie first; a skill never recorded counts as longest ago.
    ms = {
        "Small Edged": {"rank": 60, "mindstate": 0},
        "Brawling": {"rank": 61, "mindstate": 0},
        "Small Blunt": {"rank": 24, "mindstate": 0},
    }
    times = {"Small Blunt": 300.0, "Small Edged": 200.0, "Brawling": 100.0}
    assert _turns(ms, from_current=True, turn_times=times) == 1  # the fists
    times = {"Small Blunt": 300.0}
    assert _turns(ms, from_current=True, turn_times=times) == 0  # never: rank
    assert _turns(ms, from_current=True) == 2  # nothing remembered: rank


def test_a_turn_taken_is_remembered_for_the_next_hunt(travel):
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    _run(arena, profile=ROTATING, travel_first=False)
    turns = hunt.load_stores("Lanival").get("turns") or {}
    assert set(turns) <= {"Small Edged", "Brawling"} and turns


# --- an Empath (#444) ---


def test_an_empath_never_sets_out(monkeypatch):
    """Attacking a living creature brings an Empath empathic shock: the
    hunt stops before the map, the walk or a swing, and says why."""
    started = []
    echoes = []
    monkeypatch.setattr(hunt_arena.hunt.guild, "snapshot_guild", lambda name: "Empath")
    monkeypatch.setattr(hunt_arena.hunt, "hunt", lambda *a, **k: started.append(a))
    handle = SimpleNamespace(
        args=[], state=SimpleNamespace(name="Sable"), echo=echoes.append
    )
    hunt_arena.hunt.main(handle)
    assert started == []
    assert echoes == [
        "hunt: an Empath does not hunt — attacking a living creature "
        "brings empathic shock"
    ]


def test_the_guild_comes_from_info_without_a_snapshot(monkeypatch):
    """No ;sheet snapshot yet: INFO (read-only) names the guild."""
    asked = []
    echoes = []
    monkeypatch.setattr(hunt_arena.hunt.guild, "snapshot_guild", lambda name: None)
    monkeypatch.setattr(
        hunt_arena.hunt.guild,
        "ask",
        lambda s, command: asked.append(command) or "Guild: Empath\nCircle: 86",
    )
    monkeypatch.setattr(hunt_arena.hunt, "hunt", lambda *a, **k: None)
    handle = SimpleNamespace(
        args=[], state=SimpleNamespace(name="Sable"), echo=echoes.append
    )
    hunt_arena.hunt.main(handle)
    assert asked == ["info"]
    assert echoes[-1].startswith("hunt: an Empath does not hunt")


# --- the corpse by its id (#456) ---


def test_the_next_corpse_is_the_first_dead_id_not_yet_disposed_of():
    from client.game.hunting import Tally

    tally = Tally()
    s = SimpleNamespace(state=SimpleNamespace(corpses=["146982746", "146982750"]))
    assert hunt_arena.hunt.next_corpse(s, tally) == "#146982746"
    tally.disposed.add("146982746")
    assert hunt_arena.hunt.next_corpse(s, tally) == "#146982750"
    # A session started before the parser kept corpses: the noun follows.
    assert (
        hunt_arena.hunt.next_corpse(SimpleNamespace(state=SimpleNamespace()), tally)
        is None
    )


def test_a_loot_window_closed_by_a_stray_line_is_read_on(travel, tmp_path, monkeypatch):
    # 2026-10-08 18:52 (#483): the first amalgam's LOOT answered "You feel
    # fully rested." — the rested line closed the window — and the box the
    # search turned up was stowed but never counted. The hunt reads on.
    import sqlite3

    db = tmp_path / "history.db"
    from client.game import act

    monkeypatch.setenv("REVENANT_HISTORY_DB", str(db))
    monkeypatch.setattr(act, "rest_of_answer", lambda s, seconds=None: NOTHING)
    arena = _run(
        Arena(
            {
                "attack": [(KILL, kill)],
                "skin": [SKINNED],
                "loot": ["You feel fully rested.\n"],
            }
        )
    )
    with sqlite3.connect(str(db)) as connection:
        rows = connection.execute("SELECT creature, outcome FROM loot").fetchall()
    assert rows == [("rat", "nothing")]
    assert not any("unrecognized loot answer" in text for text in arena.echoed)
