"""Aiming at one creature among several of the same noun (#278): the
game's ordinals over the room's listing and its corpse marks."""

from client.game import creatures


def test_the_listing_is_counted_the_way_the_game_names_it():
    assert creatures.ordinals(["a cougar", "a rise", "a cougar", "a cougar"]) == [
        "cougar",
        "rise",
        "second cougar",
        "third cougar",
    ]
    assert creatures.ordinals([]) == []
    assert creatures.noun_of("a striped badger") == "badger"
    assert creatures.phrase("rat", 21) == "21th rat"


def test_aim_reaches_the_first_live_one_past_the_corpses():
    names = ["a cougar", "a rise in the cliff", "a cougar", "a cougar"]
    assert (
        creatures.aim("cougar", names, [True, False, False, False]) == "second cougar"
    )
    assert creatures.aim("cougar", names, [True, False, True, False]) == "third cougar"
    assert creatures.aim("cougar", names, [False, False, False, False]) == "cougar"
    # every one dead: the plain noun, and the game says "already dead"
    assert creatures.aim("cougar", names, [True, False, True, True]) == "cougar"
    # a noun the listing lacks, or no listing: the plain noun
    assert creatures.aim("rat", names, []) == "rat"
    assert creatures.aim("Cougar", [], []) == "cougar"
    assert creatures.aim("", names, []) == ""
