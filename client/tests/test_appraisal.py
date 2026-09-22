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
    }
    assert appraisal.parse_args(
        ["items=pouch,shield", "careful", "until=30", "once"]
    ) == {
        "items": ["pouch", "shield"],
        "careful": True,
        "until": 30,
        "once": True,
    }
