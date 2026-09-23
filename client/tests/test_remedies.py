"""The model behind ;remedies (client/game/remedies.py): the recipes and
their pages, CRUSH's answers classified, the master's order and the
logbook read, the arguments. Wordings captured 2026-09-22 at the
Crossing Alchemy Society."""

from client.game import remedies
from client.game.probe import classify

CRUSHED = (
    "With short strokes you crush some unfinished nemoih salve with your pestle.  "
    "The pestle slips and falls upon the dirty floor!  You hastily pick it back up.\n"
    "Roundtime: 19 sec.\n"
)
NEED_WATER = (
    CRUSHED + "You need another splash of water to continue crafting some unfinished "
    "nemoih salve.  You believe you can just pour or put it inside the mortar and "
    "continue crushing the unfinished remedy inside.\n"
)
NEED_HERB = (
    "With short strokes you crush some unfinished blister cream with your pestle.  "
    "Only once do you slip and poke a finger into the mixture.\nRoundtime: 16 sec.\n"
    "You need another prepared herb to continue crafting some unfinished blister "
    "cream.  You believe you can just pour or put it inside the mortar and continue "
    "crushing the unfinished remedy inside.\n"
)
NEED_CATALYST = (
    CRUSHED + "You need another catalyst material to continue crafting some "
    "unfinished nemoih salve.  You believe you can just pour or put it inside the "
    "mortar and continue crushing the unfinished remedy inside.\n"
)
FINISHED = (
    "With short strokes you crush some unfinished blister cream with your pestle.  "
    "Only once do you slip and poke a finger into the mixture.\nRoundtime: 16 sec.\n"
    "Applying the final touches, you complete working on some blister cream.\n"
)
NO_INSTRUCTIONS = (
    "You cannot figure out how to do that.  Perhaps finding suitable ingredients "
    "and studying some instructions would help.\n"
)
ORDER = (
    'Lanshado shuffles through some notes and says, "Alright, this is an order for '
    "some blister cream. I need 2 stacks (5 uses each) finely-crafted, made from any "
    "material and due in 65 roisaen.  Please complete the items, bundle them with "
    'your logbook and then give me the logbook to complete this order.  Good luck!"\n'
    "You seem to recall this item being somewhere in chapter 2 of the instruction "
    "book.\n"
)
LOGBOOK_OPEN = (
    "You open your logbook and sort through its contents.\n"
    "This logbook is tracking a work order requiring you to craft some blister cream "
    "from any material.  You must bundle and deliver 1 more within the next 33 "
    "roisaen.\n"
)
LOGBOOK_DONE = (
    "This logbook is tracking a work order requiring you to craft some blister cream."
    "  This work order appears to be complete.  Now give it to a crafting trainer "
    "within the next 22 roisaen to receive payment.\n"
)
LOGBOOK_NONE = "This logbook is not currently tracking any work orders.\n"
PAID = (
    "You hand Lanshado your logbook and bundled items, and are given 1146 Kronars "
    "in return.\nLanshado steadies himself and shuffles away.\n"
)


def test_the_recipes_are_the_books_pages():
    assert remedies.recipe("some blister cream") == (2, 1, "flowers", "nemoih", "cream")
    assert remedies.recipe("head salve") == (3, 4, "nemoih", None, "salve")
    assert remedies.recipe("a stomach tonic") is None
    assert remedies.herb_for("head") == "nemoih" and remedies.page_for("head") == 4
    assert remedies.herb_for("neck") == "georin" and remedies.page_for("neck") == 1
    assert remedies.HERB_SALVE["plovik"] == "chest"
    assert set(remedies.SALVES) == {"neck", "abdominal", "chest", "head", "back", "eye"}


def test_crush_answers_are_classified_failures_first():
    outcomes = remedies.CRUSH_OUTCOMES
    assert classify(NEED_WATER.lower(), outcomes) == "need water"
    assert classify(NEED_HERB.lower(), outcomes) == "need herb"
    assert classify(NEED_CATALYST.lower(), outcomes) == "need catalyst"
    assert classify(FINISHED.lower(), outcomes) == "finished"
    assert classify(CRUSHED.lower(), outcomes) == "crushed"
    assert classify(NO_INSTRUCTIONS.lower(), outcomes) == "no instructions"
    assert classify("crush what?", outcomes) == "missing"
    assert classify("you need a free hand to pick that up.", outcomes) == "free hand"
    assert classify("interesting thought really... but no.", outcomes) == "done already"
    assert (
        classify("the jadice powder is as crushed as it is going to get.", outcomes)
        == "as crushed"
    )


def test_the_crush_line_names_the_herb_first_and_the_remedy_after():
    assert remedies.crush_command("nemoih", False) == (
        "crush my nemoih in my mortar with my pestle"
    )
    assert remedies.crush_command("flowers", True, "cream") == (
        "crush my cream in my mortar with my pestle"
    )


def test_the_masters_order_and_the_logbook_are_read():
    assert remedies.parse_order(ORDER) == {
        "item": "blister cream",
        "count": 2,
        "quality": "finely-crafted",
        "due": 65,
    }
    assert remedies.parse_order("To whom are you speaking?") is None
    assert remedies.parse_logbook(LOGBOOK_OPEN) == ("open", 1, 33)
    assert remedies.parse_logbook(LOGBOOK_DONE) == ("done", 0, 22)
    assert remedies.parse_logbook(LOGBOOK_NONE) == ("none", 0, None)
    assert remedies.payment(PAID) == 1146
    assert remedies.payment("Lanshado shrugs.") is None
    assert remedies.logbook_item(LOGBOOK_OPEN) == "blister cream"
    assert remedies.logbook_item(LOGBOOK_NONE) is None


# The Supplies' answers to ORDER 13, captured 2026-09-22.
QUOTE = (
    'The attendant says, "You can purchase (25 pieces) dried red flowers for 343 '
    "Kronars.  Just order it again and we'll see it done!\"\n"
)
BOUGHT = (
    "The attendant takes some coins from you and hands you (25 pieces) dried red "
    "flowers.\n"
)


def test_a_crushs_roundtime_is_read_off_its_answer():
    assert remedies.roundtime_of(CRUSHED) == 19
    assert remedies.roundtime_of(NEED_HERB) == 16
    assert remedies.roundtime_of("Swoth runs south.\n") == 0


def test_a_rank_line_is_a_crush_and_a_bystanders_line_is_noise():
    # Captured 2026-09-22 in the Tool Shop, each alone in a crush's
    # answer window: the rank line is a crush that taught; a player
    # passing through is nothing said to the character.
    rank = "You've gained a new rank in your practice as an alchemist.\n"
    assert classify(rank.lower(), remedies.CRUSH_OUTCOMES) == "crushed"
    assert not remedies.is_noise(rank)
    assert remedies.is_noise("Swoth runs south.\n")
    assert remedies.is_noise("Khaelyn gets some blue flowers from her carryall.\n")
    assert not remedies.is_noise("")
    assert not remedies.is_noise(
        "Swoth runs south.\nYou need another splash of water.\n"
    )


def test_the_shops_quote_and_the_shortages_are_read():
    assert remedies.quote(QUOTE) == ("(25 pieces) dried red flowers", 343)
    assert remedies.quote(BOUGHT) is None
    assert any(word in BOUGHT for word in remedies.BOUGHT)
    cream = remedies.recipe("blister cream")
    assert remedies.sellable(cream)
    assert not remedies.sellable(remedies.recipe("back salve"))  # hulnik: no shelf
    assert remedies.shortage("dried flowers", cream, "nugget") == (
        "flowers",
        1,
        remedies.SUPPLIES,
        remedies.CATALOG,
    )
    assert remedies.shortage("dried nemoih", cream, "nugget")[:2] == ("nemoih", 0)
    assert remedies.shortage("water", cream, "nugget")[:2] == ("water", 0)
    assert remedies.shortage("nugget", cream, "nugget") == (
        "nugget",
        1,
        remedies.CATALYST_SHOP,
        remedies.CATALYST_CATALOG,
    )
    assert remedies.shortage("stopped", cream, "nugget") is None
    assert remedies.shortage("nugget", cream, "") is None  # no catalyst named


def test_the_arguments():
    assert remedies.parse_args([]) == {
        "salve": "head",
        "until": 34,
        "once": False,
        "count": 0,
        "work": False,
        "level": "easy",
        "ledger": False,
    }
    assert remedies.parse_args(["chest", "count=2", "until=30", "once"]) == {
        "salve": "chest",
        "until": 30,
        "once": True,
        "count": 2,
        "work": False,
        "level": "easy",
        "ledger": False,
    }
    assert remedies.parse_args(["work", "hard", "count=3"]) == {
        "salve": "head",
        "until": 34,
        "once": False,
        "count": 3,
        "work": True,
        "level": "hard",
        "ledger": False,
    }
    assert remedies.parse_args(["ledger"])["ledger"] is True
    assert remedies.parse_args(["salve=bogus"])["salve"] == "head"


def test_the_remedy_the_mortar_already_holds_is_read_off_the_refusal():
    # Captured 2026-09-23: a nemoih salve left unfinished by a run that
    # ended on a missing catalyst, refusing the next order's flowers.
    from client.game.remedies import MORTAR_BUSY, remedy_in_mortar

    line = (
        "You realize the red flowers is not required to continue crafting the "
        "nemoih salve, so you stop.\n"
    )
    assert any(word in line for word in MORTAR_BUSY)
    assert remedy_in_mortar(line) == ("head salve", (3, 4, "nemoih", None, "salve"))
    cream = "You realize the dried nemoih is not required to continue crafting some blister cream, so you stop."
    assert remedy_in_mortar(cream) == (
        "blister cream",
        (2, 1, "flowers", "nemoih", "cream"),
    )
    assert remedy_in_mortar("You put your flowers in your iron mortar.") is None
    assert (
        remedy_in_mortar("... continue crafting the mystery goo, so you stop.") is None
    )
    # LOOK IN MY MORTAR, what every craft reads first (captured 2026-09-23).
    from client.game.remedies import unfinished_in_mortar

    look = "In the iron mortar you see some unfinished nemoih salve.\n"
    assert unfinished_in_mortar(look) == ("head salve", (3, 4, "nemoih", None, "salve"))
    cream = "In the iron mortar you see some unfinished blister cream."
    assert unfinished_in_mortar(cream) == (
        "blister cream",
        (2, 1, "flowers", "nemoih", "cream"),
    )
    assert unfinished_in_mortar("There is nothing in there.") is None
    assert (
        unfinished_in_mortar("In the iron mortar you see some unfinished goo.") is None
    )


def test_the_buildings_rooms_share_the_title_before_the_comma():
    from client.game.remedies import building_rooms

    rooms = {
        "8859": {"title": ["[[Crossing Alchemy Society, Entrance]]"]},
        "8860": {"title": ["[[Crossing Alchemy Society, Tool Shop]]"]},
        "8863": {"title": ["[[Crossing Alchemy Society, Office]]"]},
        "909": {"title": ["[[Crossing, Alchemy Street]]"]},
        "9140": {"title": ["[[Fang Cove Alchemy Society, Tool Store]]"]},
        "1": {"title": []},
    }
    assert building_rooms(rooms, "8860") == ["8859", "8860", "8863"]
    assert building_rooms(rooms, 8860) == ["8859", "8860", "8863"]
    assert building_rooms(rooms, "9140") == ["9140"]
    assert building_rooms(rooms, "1") == []
    assert building_rooms(rooms, "none") == []
