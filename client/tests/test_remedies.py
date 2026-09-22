"""The model behind ;remedies (client/game/remedies.py): the salves, their
herbs and pages, CRUSH's answers classified, the arguments. Wordings
captured 2026-09-22 at the Crossing Alchemy Society."""

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
NO_INSTRUCTIONS = (
    "You cannot figure out how to do that.  Perhaps finding suitable ingredients "
    "and studying some instructions would help.\n"
)
RAW = (
    "You poorly crush the jadice flower into some jadice powder.\nRoundtime: 10 sec.\n"
)


def test_the_chapter_three_salves_and_their_herbs():
    assert remedies.herb_for("head") == "nemoih" and remedies.page_for("head") == 4
    assert remedies.herb_for("neck") == "georin" and remedies.page_for("neck") == 1
    assert remedies.HERB_SALVE["plovik"] == "chest"
    assert remedies.CHAPTER == 3


def test_crush_answers_are_classified_failures_first():
    assert classify(NEED_WATER.lower(), remedies.CRUSH_OUTCOMES) == "need water"
    assert classify(CRUSHED.lower(), remedies.CRUSH_OUTCOMES) == "crushed"
    assert (
        classify(NO_INSTRUCTIONS.lower(), remedies.CRUSH_OUTCOMES) == "no instructions"
    )
    assert classify("crush what?", remedies.CRUSH_OUTCOMES) == "missing"
    assert classify(
        "you need a free hand to pick that up.", remedies.CRUSH_OUTCOMES
    ) == ("free hand")
    assert (
        classify(
            "the jadice powder is as crushed as it is going to get.",
            remedies.CRUSH_OUTCOMES,
        )
        == "as crushed"
    )
    assert classify(RAW.lower(), remedies.CRUSH_OUTCOMES) == "crushed"


def test_the_crush_line_names_the_herb_first_and_the_salve_after():
    assert remedies.crush_command("nemoih", False) == (
        "crush my nemoih in my mortar with my pestle"
    )
    assert remedies.crush_command("nemoih", True) == (
        "crush my salve in my mortar with my pestle"
    )


def test_the_arguments():
    assert remedies.parse_args([]) == {
        "salve": "head",
        "until": 34,
        "once": False,
        "count": 0,
    }
    assert remedies.parse_args(["chest", "count=2", "until=30", "once"]) == {
        "salve": "chest",
        "until": 30,
        "once": True,
        "count": 2,
    }
    assert remedies.parse_args(["salve=eye"])["salve"] == "eye"
    assert remedies.parse_args(["salve=bogus"])["salve"] == "head"
