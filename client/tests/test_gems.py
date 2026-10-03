"""Loose gems into the gem pouch — these tests are the manual. At a safe
point the loot container and the default container are LOOKed IN, and
each gem listed is got from there, checked in hand and PUT in the
pouch by its id; a full pouch gets the gem back in its container and
stops the chore until a gem is pouched elsewhere (client/game/gems.py,
#437)."""

import itertools
from types import SimpleNamespace

import pytest

from client.game import gems, hands, interlude
from client.game.profile import save_profile

# The straw tote, LOOKed IN at 20:52 on 2026-10-03 (the fangs and most
# of the gems left out), and the backpack's one loose gem.
TOTE = (
    "In the straw tote you see some bundling rope, an ilmenite runestone, a wax "
    "label, a jagged wooden fang, a tiny green diopside, a small piece of ivory, "
    "a tiny cinnamon chunk of coral, a piece of black flint and a tiny cinnamon "
    "lapis lazuli."
)
BACKPACK = (
    "In the backpack you see an elegant diamond-hide almanac, a black gem pouch, "
    "a cotton rag, a small clear crystal and a tiny coal nugget."
)
STORE_DEFAULT = "Default:  a rugged backpack\n"
# The tied pouch's answer, captured 2026-10-03.
POUCHED = "You open your pouch and put the {} inside, closing it once more.\n"
# A full untied pouch, captured 2026-10-03 (#436).
FULL = (
    "You've already got a wealth of gems in there!  You'd better tie it up "
    "before putting more gems inside.\n"
)
PROFILE = {"loot_container": "tote", "gem_pouch": "pouch"}


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(gems, "_STATE", {"dirty": True, "full": False})
    monkeypatch.setattr(hands, "_DEFAULTS", {})
    monkeypatch.setattr(interlude, "_PENDING", set())
    monkeypatch.setattr(interlude, "_DEFERRED", {})
    monkeypatch.setattr(interlude, "_PROFILE", {})


class Game:
    """The tote, the backpack, the hands and the pouch; `swap` hands over
    another item than the one asked for, `full` makes the pouch refuse."""

    def __init__(self, s, swap=None, full=False):
        self.s = s
        self.sent = []
        self.swap = swap or {}
        self.full = full
        self.pouched = []
        self.exists = itertools.count(100)
        self.listings = {"tote": TOTE, "backpack": BACKPACK}

    def __call__(self, s, command):
        self.sent.append(command)
        state = s.state
        if command == "store default":
            return STORE_DEFAULT
        if command.startswith("look in my "):
            return self.listings[command[len("look in my ") :]] + "\n"
        if command.startswith("get ") and " from my " in command:
            wanted = command[len("get ") : command.index(" from my ")]
            name = self.swap.get(wanted, f"a tiny {wanted}")
            state.left_hand = {
                "noun": name.split()[-1],
                "exist": str(next(self.exists)),
                "name": name,
            }
            return f"You get {name} from inside your straw tote.\n"
        if command.startswith("put ") and " in my " in command:
            held = state.left_hand
            target = command.rsplit(" in my ", 1)[1]
            if target == "pouch":
                if self.full:
                    return FULL
                state.left_hand = None
                self.pouched.append(held["name"])
                return POUCHED.format(held["noun"])
            state.left_hand = None
            return "You put your item in your straw tote.\n"
        return ""


def handle(**game):
    echoed = []
    s = SimpleNamespace(
        name="train",
        state=SimpleNamespace(
            name="Lanival",
            left_hand=None,
            right_hand={"noun": "scimitar", "exist": "7", "name": "steel scimitar"},
            room_objs="",
            hostiles={},
            stunned=False,
        ),
        dead=False,
        echo=echoed.append,
        echoed=echoed,
        waitrt=lambda: None,
    )
    return s, Game(s, **game)


def test_each_loose_gem_is_got_from_its_container_and_put_in_the_pouch_by_id():
    s, game = handle()
    moved = gems.run(s, PROFILE, game)
    assert moved == [
        "a tiny diopside",
        "a tiny ivory",
        "a tiny coral",
        "a tiny lazuli",
        "a tiny crystal",
    ]
    assert game.sent == [
        "store default",
        "look in my tote",
        "get diopside from my tote",
        "put #100 in my pouch",
        "get ivory from my tote",
        "put #101 in my pouch",
        "get coral from my tote",
        "put #102 in my pouch",
        "get lazuli from my tote",
        "put #103 in my pouch",
        "look in my backpack",
        "get crystal from my backpack",
        "put #104 in my pouch",
    ]
    # The runestone, the fang, the flint, the coal and the spare pouch stay.
    assert not any("runestone" in c or "fang" in c or "coal" in c for c in game.sent)
    assert "gems: 5 loose gem(s) into the pouch" in s.echoed[-1]
    assert not gems.due(PROFILE)  # all moved: clean until a gem goes loose


def test_a_full_pouch_puts_the_gem_back_and_stops_until_a_gem_is_pouched():
    s, game = handle(full=True)
    assert gems.run(s, PROFILE, game) == []
    assert game.sent == [
        "store default",
        "look in my tote",
        "get diopside from my tote",
        "put #100 in my pouch",
        "put #100 in my tote",
    ]
    assert any("the pouch is full" in text and "#283" in text for text in s.echoed)
    assert not gems.due(PROFILE)  # the loose gems stay; no retry every safe point
    gems.room()  # the hunt pouched one: room again
    assert gems.due(PROFILE)


def test_an_item_in_hand_that_is_no_gem_goes_back():
    # The GET took another crystal than the listed gem: the hand decides.
    s, game = handle(swap={"crystal": "an albredine crystal ring"})
    moved = gems.run(s, PROFILE, game)
    assert "a tiny crystal" not in moved
    assert "put #104 in my backpack" in game.sent
    assert any("which is no gem — put back" in text for text in s.echoed)


def test_the_chore_is_due_with_a_pouch_and_runs_at_a_safe_point(monkeypatch):
    s, game = handle()
    monkeypatch.setattr(interlude, "ask", game)
    save_profile("Lanival", {"loot_container": "tote", "gem_pouch": ""})
    assert not interlude._gems_due(s)  # no pouch, no chore
    interlude._PROFILE.clear()
    save_profile("Lanival", PROFILE)
    assert interlude._gems_due(s)
    interlude.run_due(s)
    assert len(game.pouched) == 5
    assert not interlude._gems_due(s)
    gems.mark()  # a gem went with the loot
    assert interlude._gems_due(s)


def test_with_both_hands_full_the_chore_waits_in_a_hunts_clear_room(monkeypatch):
    s, game = handle()
    monkeypatch.setattr(interlude, "ask", game)
    save_profile("Lanival", PROFILE)
    s.state.left_hand = {"noun": "shield", "exist": "8", "name": "target shield"}
    interlude.run_due(s, make_room=False)
    assert game.sent == []
    assert gems.due(PROFILE)
