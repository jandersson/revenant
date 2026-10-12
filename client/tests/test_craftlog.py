"""The crafting dataset: ANALYZE's answer read into a quality and a
difficulty, one history.db row per finished item."""

import sqlite3

from client.game import craftlog

# ANALYZE MY CREAM, a blister cream made at Alchemy 392 (captured 2026-10-12).
ANALYZED = (
    "You analyze every minute detail of the blister cream and smile knowingly to yourself.\n"
    "This appears to be a type of basic wound remedy that is of exceptional quality.\n"
    "The cream is an extremely easy piece to make.\n"
    "It was made by someone with abilities close to your own skill.\n"
    "When finished the cream has a potential for low potency and somewhat good efficacy."
    "  It may also be very insoluble and moderately toxic.\n"
    "You find it impossible to identify who crafted this item.\n"
    "Roundtime: 4 sec.\n"
)


def test_analyze_gives_the_quality_its_rank_and_the_difficulty():
    assert craftlog.read(ANALYZED) == ("exceptional", 10, "extremely easy")
    assert craftlog.read("...that is of about average quality.")[:2] == (
        "about average",
        5,
    )
    assert craftlog.read("What were you referring to?") == ("", None, "")


def test_a_finished_item_is_one_row(tmp_path):
    path = tmp_path / "history.db"
    quality = craftlog.log(
        "Lanival", "remedies", "blister cream", ANALYZED, "Alchemy", 392, 66, path=path
    )
    assert quality == "exceptional"
    row = (
        sqlite3.connect(path)
        .execute(
            "SELECT character_name, item, quality, quality_rank, skill_rank,"
            " skill_percent, difficulty FROM crafts"
        )
        .fetchone()
    )
    assert row == (
        "Lanival",
        "blister cream",
        "exceptional",
        10,
        392,
        66,
        "extremely easy",
    )
