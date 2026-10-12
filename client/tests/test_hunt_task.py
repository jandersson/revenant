"""How ;hunt task runs an item recovery (#509) — these tests are the manual.

;task records the recovery; ;hunt task takes its area as the ground,
fights whatever engages, and ends when a kill's death line drops the
item: GET it by its ADJECTIVE NOUN, write its id into the task's record
for ;task's GIVE, stow it, and go home as any hunt does. No mind-lock
ends it. The death lines were captured on the poloh'izh hunted by hand
(2026-10-10).
"""

import pytest

from client.game import tasks

from hunt_arena import KILL, NOTHING, PROFILE, Arena, GROUND, hunt, kill

# The death lines, as captured: a kill without the item, and the kill
# that drops it (bold, on the story stream, before the kill line).
NO_DROP_KILL = (
    "Although azure poloh'izh dies, you do not see the object you are looking "
    "for.\nThe azure poloh'izh falls to the ground and lies still."
)
DROP_KILL = (
    "As grey poloh'izh dies, you see it drop a worn gauntlet onto the ground.\n"
    "The grey poloh'izh falls to the ground and lies still."
)
PICKED_UP = "You pick up a worn gauntlet."
GAUNTLET = {"noun": "gauntlet", "name": "worn gauntlet", "exist": "176392386"}

RECOVERY = {
    "kind": "recovery",
    "giver": "cormyn",
    "item": "worn gauntlet",
    "creature": "poloh'izh",
    "area": "near Barana's Shipyard, Lumber Storage",
}

TASK_PROFILE = PROFILE | {"skin": False}


@pytest.fixture(autouse=True)
def _records(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))


def picked(arena):
    arena.state.left_hand = dict(GAUNTLET)


def run_task(arena, profile=TASK_PROFILE):
    tasks.record("Lanival", RECOVERY)
    overlaid, ground = hunt.task_profile(arena, dict(profile), GROUND)
    hunt.hunt(arena, overlaid, GROUND, travel_first=False, ground=ground)
    return "\n".join(arena.echoed)


def test_the_task_lays_its_area_and_item_over_the_profile():
    arena = Arena({})
    tasks.record("Lanival", RECOVERY)
    profile, ground = hunt.task_profile(arena, dict(TASK_PROFILE), GROUND)
    assert ground == [6046, 6047]  # the rooms titled with the area
    assert profile["until"] == "task" and profile["task_item"] == "worn gauntlet"
    assert profile["prey"] == ""  # whatever engages: the offer's noun is plural
    assert profile["weapon"] == "handaxe"  # the profile's own weapons


def test_no_recovery_in_hand_is_said_and_nothing_hunted():
    arena = Arena({})
    assert hunt.task_profile(arena, dict(TASK_PROFILE), GROUND) == (None, None)
    assert "no item recovery in hand" in "\n".join(arena.echoed)


def test_the_drop_ends_the_hunt_the_item_taken_by_its_adjective_noun(travel):
    arena = Arena(
        {
            "attack": [(NO_DROP_KILL, lambda a: None), (DROP_KILL, kill)],
            "loot": [NOTHING, NOTHING],
            "get worn gauntlet": [(PICKED_UP, picked)],
        }
    )
    out = run_task(arena)
    assert "get worn gauntlet" in arena.sent
    assert "put my gauntlet in my sack" in arena.sent
    assert "the task's worn gauntlet dropped — picked up" in out
    # The id goes into the record: ;task GIVEs this gauntlet, not another.
    assert tasks.load("Lanival")["exist"] == "176392386"
    assert sum(command.startswith("attack") for command in arena.sent) == 2


def test_a_locked_skill_does_not_end_a_task_hunt(travel):
    arena = Arena(
        {
            "attack": [(DROP_KILL, kill)],
            "loot": [NOTHING],
            "get worn gauntlet": [(PICKED_UP, picked)],
        },
        experience={"Small Edged": {"mindstate": 34}},
    )
    out = run_task(arena, TASK_PROFILE | {"train_skills": ["Small Edged"]})
    assert "mind-locked" not in out
    assert "the task's worn gauntlet dropped — picked up" in out


def test_a_get_that_takes_nothing_is_said_and_the_hunt_ends(travel):
    arena = Arena(
        {
            "attack": [(DROP_KILL, kill)],
            "loot": [NOTHING],
            "get worn gauntlet": ["What were you referring to?"],
        }
    )
    out = run_task(arena)
    assert "did not take it — it lies here" in out
    assert "exist" not in tasks.load("Lanival")


def test_the_drop_pattern_names_the_item_and_get_takes_two_words():
    import re

    pattern = re.compile(tasks.drop_pattern("small hand mirror"), re.IGNORECASE)
    assert pattern.search(
        "As amber poloh'izh dies, you see it drop a small hand mirror onto the ground."
    )
    assert not pattern.search(DROP_KILL)
    # Ioun's offer said "ring", the journal "pearl ring" (2026-10-11).
    ring = re.compile(tasks.drop_pattern("ring"), re.IGNORECASE)
    assert ring.search(
        "As grey poloh'izh dies, you see it drop a pearl ring onto the ground."
    )
    assert not ring.search(
        "As grey poloh'izh dies, you see it drop a pearl earring onto the ground."
    )
    assert tasks.item_words("small hand mirror") == "hand mirror"
    assert tasks.item_words("worn gauntlet") == "worn gauntlet"


# A skinning task (#509), as ;task records the Sand Spit barkeep's
# (2026-10-12): the creature's hides, a count, each GIVE one item.
SKINNING = {
    "kind": "skinning",
    "giver": "barkeep",
    "item": "storm bull hide",
    "creature": "storm bull",
    "count": 2,
}
HIDE = "You skin the rat, obtaining a storm bull hide."  # the shape of SKINNED


@pytest.fixture
def bull_yard(monkeypatch):
    """The arena's yard as a bestiary zone of storm bulls."""
    from client.game import hunting

    zone = ("Zoluren", (6046, 6047), (("Storm bull", 550, 750),), ())
    monkeypatch.setitem(hunting.ZONES, "yard_bulls", zone)


def test_a_skinning_task_hunts_the_creatures_ground_and_keeps_the_hides_loose(
    bull_yard,
):
    arena = Arena({})
    tasks.record("Lanival", SKINNING)
    profile, ground = hunt.task_profile(arena, dict(TASK_PROFILE), GROUND)
    assert ground == [6046, 6047]  # the zone that lists storm bulls
    assert profile["prey"] == "bull" and profile["until"] == "task"
    assert profile["skin"] is True and profile["bundle"] is False  # one GIVE, one hide
    assert profile["task_hides"] == 2


def test_a_skinning_hunt_ends_at_the_tasks_count(bull_yard, travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill), (KILL, kill)],
            "skin": [HIDE, HIDE, HIDE],
            "loot": [NOTHING] * 3,
        }
    )
    tasks.record("Lanival", SKINNING)
    overlaid, ground = hunt.task_profile(arena, dict(TASK_PROFILE), GROUND)
    overlaid["prey"] = ""  # the arena's creature is no bull
    hunt.hunt(arena, overlaid, GROUND, travel_first=False, ground=ground)
    out = "\n".join(arena.echoed)
    assert "2 storm bull hide(s) cut — the task's count" in out
    assert sum(command.startswith("attack") for command in arena.sent) == 2
    assert arena.sent.count("put my hide in my sack") == 2
    assert not any(command.startswith("bundle") for command in arena.sent)


def test_a_skinning_hunt_with_nothing_to_skin_with_ends_at_the_first_skin(
    bull_yard, travel
):
    # The game skins with a worn knife or the wielded blade; with neither,
    # the first SKIN says so and the hunt kills no more.
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "skin": ["You have nothing to skin with."],
            "loot": [NOTHING] * 2,
        }
    )
    tasks.record("Lanival", SKINNING)
    overlaid, ground = hunt.task_profile(arena, dict(TASK_PROFILE), GROUND)
    overlaid["prey"] = ""
    hunt.hunt(arena, overlaid, GROUND, travel_first=False, ground=ground)
    assert "skinning is off — no storm bull hide can be cut" in "\n".join(arena.echoed)
    assert sum(command.startswith("attack") for command in arena.sent) == 1


def test_no_ground_for_the_creature_is_said():
    arena = Arena({})
    tasks.record("Lanival", {**SKINNING, "creature": "glass dragon"})
    assert hunt.task_profile(arena, dict(TASK_PROFILE), GROUND) == (None, None)
    assert "no ground on record has glass dragons" in "\n".join(arena.echoed)
