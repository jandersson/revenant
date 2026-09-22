"""Loot read off the room's listing — these tests are the manual. What
a SEARCH left on the ground is the listing after less the listing
before, coins counted, corpses and creatures left out, each entry
sorted into coins, a box or an item (2026-09-23, #291/#292)."""

from client.game import loot

BEFORE = (
    "You also see some bronze coins, some copper coins, a small grendel which "
    "appears dead and a war club."
)
AFTER = (
    "You also see some bronze coins, some copper coins, some waermodi stones, "
    "some bronze coins, some copper coins, a dented iron box, a small grendel, "
    "a war club and a small grendel which appears dead."
)


def test_the_listing_splits_into_entries():
    assert loot.entries(BEFORE) == [
        "some bronze coins",
        "some copper coins",
        "a small grendel which appears dead",
        "a war club",
    ]
    assert loot.entries("You also see a bucket.") == ["a bucket"]
    assert loot.entries("") == [] and loot.entries(None) == []


def test_what_the_search_left_is_the_difference_less_corpses_and_creatures():
    found = loot.new_items(BEFORE, AFTER, creatures=["a small grendel"])
    assert sorted(found) == sorted(
        [
            "some bronze coins",
            "some copper coins",
            "some waermodi stones",
            "a dented iron box",
        ]
    )
    assert loot.new_items(AFTER, AFTER) == []
    assert loot.new_items("", "You also see a mud-stained iron chest.") == [
        "a mud-stained iron chest"
    ]


def test_the_hunt_grabs_what_the_search_left_by_the_listing():
    # The search's answer may say anything; the listing's difference
    # is what gets picked up: coins GOT, the box into the loot
    # container, the stones pouched, the corpse and the live grendel
    # left alone. The wording path then skips what was taken.
    import importlib.util
    import pathlib
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "hunt_for_loot", pathlib.Path(__file__).parents[2] / "scripts/hunt.py"
    )
    hunt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hunt)
    sent = []
    state = SimpleNamespace(room_objs=BEFORE, room_creatures=["a small grendel"])

    def ask(s, command, *_):
        sent.append(command)
        if command.startswith("search"):
            state.room_objs = AFTER
            return "You search the small grendel.\nThe grendel was carrying some waermodi stones, 7 copper coins (Kronars), and 1 bronze coin (Dokora)!\n"
        return "You get it."

    hunt.probe = SimpleNamespace(ask=ask)
    handle = SimpleNamespace(state=state, echo=lambda t: None, sleep=lambda n: None)
    profile = {"skin": False, "loot_container": "sack", "gem_pouch": "pouch"}
    tally = hunt.Tally()
    hunt.dispose(handle, profile, "grendel", tally)
    assert sent.count("get coins") == 2 and tally.coins == 2
    assert "get box" in sent and "put my box in my sack" in sent and tally.boxes == 1
    assert sent.count("get stones") == 1  # by the listing; the wording path skipped it
    assert "put my stones in my pouch" in sent
    assert not any("grendel" in c and c.startswith("get") for c in sent)
    assert not any(c.startswith("drop") for c in sent)


def test_each_entry_is_coins_a_box_or_an_item():
    assert loot.kind("some bronze coins") == "coins"
    assert loot.kind("a bronze coin") == "coins"
    assert loot.kind("a dented iron box") == "box"
    assert loot.kind("a mud-stained iron chest") == "box"
    assert loot.kind("some waermodi stones") == "item"
    assert loot.kind("an ilmenite runestone") == "item"
    assert loot.kind("a war club") == "item"
