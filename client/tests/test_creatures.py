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


# --- what a room's creatures can still teach (#322) ---


def test_a_listing_name_finds_its_creature_past_the_article_and_adjectives():
    assert creatures.caps_of("a cougar")[0] == "cougar"
    assert creatures.caps_of("a dour forager goblin")[0] == "forager goblin"
    assert creatures.caps_of("a blood wolf")[0] == "blood wolf"
    assert creatures.caps_of("a rise in the cliff") is None


def test_cougars_have_nothing_left_for_rank_58_and_wolves_do():
    # 2026-09-26: five hunts on the bobcats ground — mostly cougars,
    # MaxCap 49 — left Small Edged 58 and Brawling 57 at 0-3/34.
    ranks = {"Small Edged": 58, "Brawling": 57, "Small Blunt": 13}
    top, past = creatures.outgrown(["a cougar", "a cougar"], ranks)
    assert top == ("cougar", 49)
    assert past == [("Brawling", 57), ("Small Edged", 58)]
    top, past = creatures.outgrown(["a blood wolf"], ranks)
    assert past == []


def test_the_most_generous_creature_in_the_room_decides():
    top, past = creatures.outgrown(["a cougar", "a bobcat"], {"Small Edged": 58})
    assert top == ("bobcat", 65)
    assert past == []


def test_creatures_the_table_does_not_know_say_nothing():
    assert creatures.outgrown(["a glimmering wisp of nothing"], {"Brawling": 57}) == (
        None,
        [],
    )
