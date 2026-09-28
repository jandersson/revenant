"""The model behind ;appraise (client/game/appraisal.py): the rotation
from the inventory or a list, the APPRAISE line, the arguments.
"""

from client.game import appraisal

POSSESSIONS = [
    {"noun": "scimitar", "depth": 0, "worn": False},
    {"noun": "sack", "depth": 0, "worn": True},
    {"noun": "flake", "depth": 1, "worn": False},  # inside the sack
    {"noun": "pouch", "depth": 0, "worn": True},
    {"noun": "sack", "depth": 0, "worn": True},  # a second sack: one noun
    {"noun": "", "depth": 0, "worn": False},
]


def test_the_rotation_is_what_is_worn_or_held_a_pouch_first_each_noun_once():
    assert appraisal.rotation(POSSESSIONS) == ["pouch", "scimitar", "sack"]
    assert appraisal.rotation([]) == []
    assert appraisal.rotation(None) == []


def test_a_list_of_items_replaces_the_inventory():
    assert appraisal.rotation(POSSESSIONS, ["shield", " zills ", "shield"]) == [
        "shield",
        "zills",
    ]


def test_the_appraise_line_is_quick_unless_asked_careful():
    assert appraisal.appraise_command("pouch") == "appraise my pouch quick"
    assert appraisal.appraise_command("shield", careful=True) == (
        "appraise my shield careful"
    )


def test_the_arguments():
    assert appraisal.parse_args([]) == {
        "items": [],
        "careful": False,
        "until": 34,
        "once": False,
        "focus": "",
    }
    assert appraisal.parse_args(
        ["items=pouch,shield", "careful", "until=30", "once", "focus=coffer"]
    ) == {
        "items": ["pouch", "shield"],
        "careful": True,
        "until": 30,
        "once": True,
        "focus": "coffer",
    }
    assert appraisal.parse_args(["focus=inner_fire"])["focus"] == "inner fire"


# APPRAISE FOCUS (#383): the wiki's start and end lines, appraisal.lic's
# answers; none captured yet.
FOCUS_STARTED = (
    "You carefully examine your deobar coffer, focusing beyond any individual "
    "details.  Instead you concentrate your efforts toward honing your knowledge "
    "of locksmithing based on its abstract."
)
FOCUS_BREAKTHROUGH = (
    "Breakthrough!\nYou've pored over the possibilities, weighed out the "
    "consequences, and dismissed a few flawed techniques."
)
FOCUS_EXPLORED = "Your focused insight of locksmithing has been fully explored."


def test_the_focus_answers_classify():
    assert appraisal.focus_outcome(FOCUS_STARTED) == "started"
    assert appraisal.focus_outcome("You are already focusing on a project.") == (
        "running"
    )
    assert appraisal.focus_outcome("You currently feel inspired.") == "boost"
    assert appraisal.focus_outcome("You can't seem to focus on that.") == "refused"
    assert appraisal.focus_outcome(
        "You will lose your progress on your research project if you do that."
    ) == ("research")
    # Captured 2026-09-29 beside a RESEARCH portion: not a focus running.
    assert appraisal.focus_outcome(
        "You are already working on a different research project."
    ) == ("research")
    assert appraisal.focus_outcome("Huh?") is None
    # Captured 2026-09-29 with nothing running.
    assert (
        appraisal.focus_check("You feel ready for any sort of appraisal focus.") is None
    )
    assert appraisal.focus_check("You are currently focusing on ...") == "running"
    assert appraisal.focus_check("You have completed your focus ...") == "boost"
    assert appraisal.focus_check("You are not focusing on anything.") is None


def test_the_focus_lines_are_found_in_any_answer():
    assert appraisal.focus_events(FOCUS_BREAKTHROUGH) == ["breakthrough"]
    assert appraisal.focus_events("junk\n" + FOCUS_EXPLORED) == ["explored"]
    assert appraisal.focus_events("You are certain the pouch is worth ...") == []


def test_a_concept_is_focused_bare_and_an_item_as_yours():
    assert appraisal.focus_command("coffer") == "appraise focus my coffer"
    assert appraisal.focus_command("Offense") == "appraise focus offense"
    assert appraisal.focus_command("inner fire") == "appraise focus inner fire"
    assert appraisal.focus_command("#1234") == "appraise focus #1234"
