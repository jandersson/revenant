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


def test_the_arguments():
    assert remedies.parse_args([]) == {
        "salve": "head",
        "until": 34,
        "once": False,
        "count": 0,
        "work": False,
        "level": "easy",
    }
    assert remedies.parse_args(["chest", "count=2", "until=30", "once"]) == {
        "salve": "chest",
        "until": 30,
        "once": True,
        "count": 2,
        "work": False,
        "level": "easy",
    }
    assert remedies.parse_args(["work", "hard", "count=3"]) == {
        "salve": "head",
        "until": 34,
        "once": False,
        "count": 3,
        "work": True,
        "level": "hard",
    }
    assert remedies.parse_args(["salve=bogus"])["salve"] == "head"
