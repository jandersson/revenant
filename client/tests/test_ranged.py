"""A ranged turn's shot and its ammunition (client/game/ranged.py, #578):
LOAD, AIM, the aim waited out, FIRE, and the stones STOWed again — on
its own, then inside ;hunt's arena (hunt_arena.py)."""

import pytest

from client.game import ranged
from hunt_arena import PROFILE, RAT_CORPSE, Arena, _run, kill

# Captured 2026-10-17 on a hide sling, small rocks (Milgrym's Weapons,
# ten for 12 Kronars) in a thigh quiver, at the Crossing's ship rats.
LOADED = (
    "You reach into your quiver to load the hide sling with a small rock.\n"
    "Roundtime 3 sec."
)
NO_AMMO = "You don't have the proper ammunition readily available for your hide sling."
NOT_AMMO = "You can not load the hide sling with a rock!"  # a foraged rock
AIMING = "You begin to target a ship's rat."
BEST = "You think you have your best shot possible now."
LODGED = (
    "< Moving with indomitable grace, you fire a small rock at a ship's rat.  "
    "A ship's rat fails to evade, failing miserably.  The rock lands an "
    "apocalyptic strike (So that's what it felt like when Grazhir shattered!) "
    "that nicks the rat's neck, lightly stunning it.\n"
    "The small rock lodges itself shallowly into the ship's rat!\n"
    "[You're winded, solidly balanced and in strong position.]\n"
    "[Roundtime 1 sec.]"
)
KILLED = (
    "< Moving as a single sinuous force, you fire a small rock at a ship's rat.  "
    "A ship's rat attempts to dodge, mis-stepping and blundering into the blow.  "
    "The rock lands an apocalyptic strike (So that's what it felt like when "
    "Grazhir shattered!) that skewers a perfect hole between the shoulder "
    "blades (Heart Burn!).\n"
    "The small rock lodges itself savagely into the ship's rat!\n"
    "The ship's rat falls to the ground and lies still.\n"
    "[You're solidly balanced]\n"
    "[Roundtime 1 sec.]"
)
SEARCHED = (
    "You search the ship's rat.\nLodged into it was a small rock and a small rock."
)
PICKED = "You pick up a small rock.\nYou put your rock in your thigh quiver."
STOW_WHAT = "Stow what?  Type 'STOW HELP' for details."
NO_HAND = "You need a free hand to pick that up."
# Captured on the first live ;hunt with the sling: a killing shot that
# did not lodge, and STOW MY SMALL ROCK's answer to it.
AT_FEET = (
    "< Driving in with an overwhelming assault, you fire a small rock at a "
    "ship's rat.  A ship's rat fails to evade, taking the full blow.  The rock "
    "lands an apocalyptic strike (So that's what it felt like when Grazhir "
    "shattered!) that tears the left leg from the socket when the small rock "
    "gets jammed between thigh and hip.\n"
    "The small rock lands at your feet!\n"
    "The ship's rat falls to the ground and lies still."
)
FEET_PICKED = (
    "You pick up the rock lying at your feet.\nYou put your rock in your thigh quiver."
)


class Fake:
    """An ask that answers each command by prefix and keeps what went out."""

    def __init__(self, answers):
        self.answers = {prefix: list(queue) for prefix, queue in answers.items()}
        self.sent = []

    def ask(self, s, command):
        self.sent.append(command)
        for prefix, queue in self.answers.items():
            if command.startswith(prefix) and queue:
                return queue.pop(0)
        return ""


@pytest.fixture
def waits(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ranged.probe, "collect", lambda s, seconds, until=None: calls.append(until)
    )
    return calls


def test_the_ammunition_a_shot_fired_as_stow_names_it():
    assert ranged.ammo_of(LODGED) == "small rock"
    assert (
        ranged.ammo_of("You fire a matte indurium sphere at a goblin.")
        == "matte sphere"
    )
    assert ranged.ammo_of("You fire an arrow at a goblin.") == "arrow"
    assert ranged.ammo_of(AIMING) == ""


def test_both_load_refusals_read_as_no_ammunition():
    assert ranged.out_of_ammo(NO_AMMO)
    assert ranged.out_of_ammo(NOT_AMMO)
    assert not ranged.out_of_ammo(LOADED)


def test_only_the_three_ranged_skills_shoot():
    assert ranged.is_ranged("Slings") and ranged.is_ranged("Bow")
    assert ranged.is_ranged("Crossbow")
    assert not ranged.is_ranged("Light Thrown") and not ranged.is_ranged("")


def test_a_shot_loads_aims_waits_for_the_full_aim_and_fires(waits):
    fake = Fake({"load": [LOADED], "aim": [AIMING], "fire": [LODGED]})
    assert ranged.shoot(None, "second rat", fake.ask) == LODGED
    assert fake.sent == ["load", "aim second rat", "fire"]
    assert waits == [ranged.BEST_SHOT]


def test_an_aim_already_full_fires_at_once(waits):
    fake = Fake({"load": [LOADED], "aim": [AIMING + "\n" + BEST], "fire": [LODGED]})
    ranged.shoot(None, "", fake.ask)
    assert fake.sent == ["load", "aim", "fire"]
    assert waits == []


def test_a_shot_at_the_feet_is_stowed_again(waits):
    fake = Fake(
        {
            "load": [LOADED],
            "aim": [AIMING + "\n" + BEST],
            "fire": [AT_FEET],
            "stow my small rock": [FEET_PICKED],
        }
    )
    assert ranged.shoot(None, "rat", fake.ask) == AT_FEET
    assert fake.sent[-1] == "stow my small rock"
    assert fake.sent.count("stow my small rock") == 1


def test_no_aim_without_ammunition_and_no_fire_at_a_corpse(waits):
    fake = Fake({"load": [NO_AMMO]})
    assert ranged.shoot(None, "rat", fake.ask) == NO_AMMO
    assert fake.sent == ["load"]
    fake = Fake({"load": [LOADED], "aim": [RAT_CORPSE]})
    assert ranged.shoot(None, "rat", fake.ask) == RAT_CORPSE
    assert "fire" not in fake.sent


def test_the_stones_on_the_floor_are_stowed_until_none_is_left():
    fake = Fake({"stow small rock": [PICKED, PICKED, STOW_WHAT]})
    assert ranged.pick_up(None, "small rock", fake.ask) == (2, STOW_WHAT)
    fake = Fake({"stow small rock": [NO_HAND]})
    assert ranged.pick_up(None, "small rock", fake.ask) == (0, NO_HAND)
    fake = Fake({"stow small rock": [PICKED] * 20})
    assert ranged.pick_up(None, "small rock", fake.ask, most=3)[0] == 3


SLINGING = PROFILE | {
    "weapon": "",
    "weapons": ["sling:Slings"],
    "skin": False,
    "max_kills": 1,
}


@pytest.mark.usefixtures("fast_clock")
def test_a_sling_turn_shoots_the_rat_and_picks_its_stones_back_up(travel):
    arena = Arena(
        {
            "load": [LOADED] * 2,
            "aim": [AIMING + "\n" + BEST] * 2,
            "fire": [LODGED, (KILLED, kill)],
            "loot": [SEARCHED],
            "stow small rock": [PICKED, PICKED, STOW_WHAT],
        }
    )
    _run(arena, profile=SLINGING, travel_first=False)
    assert not any(command.startswith("attack") for command in arena.sent)
    assert arena.sent.count("fire") == 2
    after = arena.sent[arena.sent.index("loot") :]
    assert after.count("stow small rock") == 3
    assert any("2 shot(s), 2 small rock(s) picked up" in text for text in arena.echoed)


@pytest.mark.usefixtures("fast_clock")
def test_no_ammunition_ends_the_hunt(travel):
    arena = Arena({"load": [NO_AMMO]})
    _run(arena, profile=SLINGING, travel_first=False)
    assert not any(command.startswith(("aim", "fire")) for command in arena.sent)
    assert any("no ammunition — " + NO_AMMO in text for text in arena.echoed)
