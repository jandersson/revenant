"""STORE and STOW GEM / STOW BOX in ;hunt (the operator, 2026-09-26) —
these tests are the manual. The loot kinds' containers are set with
STORE only when they change, remembered per character; a gem or box on
the ground goes in with one STOW, the old GET path when STOW answers
otherwise."""

from types import SimpleNamespace

import hunt_arena
from hunt_arena import KILL, NOTHING, PROFILE, Arena, _run, kill

hunt = hunt_arena.hunt

STORED_BOXES = "You will now store boxes in your canvas sack.\n"  # captured 2026-09-26
STORED_GEMS = "You will now store gems in your gem pouch.\n"


class Asker:
    def __init__(self, answers):
        self.answers = answers
        self.sent, self.echoed = [], []
        self.state = SimpleNamespace(name="Lanival")

    def echo(self, text):
        self.echoed.append(text)


def _ask(asker):
    def ask(s, command):
        asker.sent.append(command)
        for prefix, answer in asker.answers.items():
            if command.startswith(prefix):
                return answer
        return ""

    return ask


def test_store_is_sent_once_and_not_again_until_the_container_changes(monkeypatch):
    asker = Asker({"store boxes": STORED_BOXES, "store gems": STORED_GEMS})
    monkeypatch.setattr(hunt, "ask", _ask(asker))
    profile = {"loot_container": "sack", "gem_pouch": "pouch"}
    assert hunt.set_stores(asker, dict(profile)) == ["box", "gem"]
    assert asker.sent == ["store boxes in my sack", "store gems in my pouch"]
    asker.sent.clear()
    assert hunt.set_stores(asker, dict(profile)) == ["box", "gem"]
    assert asker.sent == []  # the game keeps STORE: nothing to send
    hunt.set_stores(asker, profile | {"loot_container": "backpack"})
    assert asker.sent == ["store boxes in my backpack"]


def test_a_store_the_game_refuses_is_said_and_that_kind_goes_by_hand(monkeypatch):
    asker = Asker(
        {
            "store boxes": "You can only store things in containers that you are wearing.\n"
        }
    )
    monkeypatch.setattr(hunt, "ask", _ask(asker))
    assert hunt.set_stores(asker, {"loot_container": "sack"}) == []
    assert any("boxes picked up by hand" in e for e in asker.echoed)
    asker.sent.clear()
    hunt.set_stores(asker, {"loot_container": "sack"})
    assert asker.sent == ["store boxes in my sack"]  # not remembered: tried again


def test_a_box_on_the_ground_goes_in_with_stow_box(monkeypatch):
    found = iter([["a small wooden coffer"], ["a small wooden coffer"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena(
        {
            "attack": [(KILL, _no_kill), (KILL, kill), (KILL, kill)],
            "loot": [NOTHING] * 3,
            # Captured 2026-09-26 at the goblins, the first STOW BOX.
            "stow box": [
                "You pick up a mud-stained steel crate.\n"
                "You put your crate in your canvas sack.\n"
            ]
            * 3,
        }
    )
    farm = PROFILE | {"skin": False, "box_limit": 2, "until": "boxes"}
    _run(arena, profile=farm, travel_first=False)
    assert arena.sent.count("stow box") == 2
    assert "get coffer" not in arena.sent
    assert any("2 box(es) in the sack — the farm is done" in e for e in arena.echoed)


def _no_kill(arena):
    """The first swing's line, the rat still up (test_hunt's _stands)."""


def test_a_lone_coin_is_picked_up_as_a_coin_not_as_coins(monkeypatch):
    # 2026-09-26: a goblin dropped "8 copper coins (Kronars) and 1 bronze
    # coin (Dokora)"; GET COINS twice took the coppers and answered "What
    # were you referring to?" for the bronze, which stayed on the ground.
    found = iter([["some copper coins", "a bronze coin"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "loot": [NOTHING],
            "get coins": ["You pick up 8 copper Kronars.\n"],
            "get coin": ["You pick up 1 bronze Dokora.\n"],
        }
    )
    _run(arena, profile=PROFILE | {"skin": False, "max_kills": 1}, travel_first=False)
    gets = [c for c in arena.sent if c.startswith("get coin")]
    assert gets == ["get coins", "get coin"]


def test_a_box_farm_fights_on_when_its_weapon_skill_locks(monkeypatch):
    # 2026-09-26: the boxes style's mace mind-locked Small Blunt five kills
    # in and the farm ended "every weapon skill mind-locked" with its box
    # limit far off.
    found = iter([["a small wooden coffer"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "loot": [NOTHING],
            "stow box": [
                "You pick up a mud-stained steel crate.\n"
                "You put your crate in your canvas sack.\n"
            ],
        },
        experience={"Small Blunt": {"rank": 13, "percent": 0, "mindstate": 34}},
    )
    farm = PROFILE | {
        "skin": False,
        "box_limit": 1,
        "until": "boxes",
        "weapons": ["mace:Small Blunt:backpack"],
    }
    _run(arena, profile=farm, travel_first=False)
    assert not any("mind-locked" in e for e in arena.echoed)
    assert any("1 box(es) in the sack — the farm is done" in e for e in arena.echoed)
