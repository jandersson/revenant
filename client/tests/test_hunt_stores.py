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
            # Uncaptured: combat-trainer's STOW success words ("You pick up").
            "stow box": ["You pick up a small wooden coffer and put it in your sack."]
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
