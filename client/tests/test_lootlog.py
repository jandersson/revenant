"""Each LOOT's outcome logged per creature, for a ground's box drop rate
(#329). The answers are the captured ones (2026-09-26, the goblins
north of the Crossing; 2026-09-21, the grendels)."""

import sqlite3
from types import SimpleNamespace

from client.game import lootlog

BOX = (
    "You search the scavenger goblin.\nThe goblin was carrying a poorly made iron box!"
)
COINS = (
    "You search the scavenger goblin.\n"
    "The goblin was carrying 9 copper coins (Kronars) and 1 bronze coin (Kronar)!"
)
GEMS = (
    "You search the grendel.\n"
    "The grendel was carrying some waermodi stones, 7 copper coins (Kronars), "
    "and 1 bronze coin (Dokora)!"
)
EMPTY = "You search the large musk hog.\nYou find nothing of interest."


def test_a_box_is_a_box_with_its_noun():
    assert lootlog.parse(BOX) == {
        "creature": "scavenger goblin",
        "outcome": "box",
        "carried": "a poorly made iron box",
        "box": "box",
    }


def test_coins_and_gems_are_treasure():
    coins = lootlog.parse(COINS)
    assert coins["outcome"] == "treasure" and coins["box"] is None
    assert coins["carried"].startswith("9 copper coins")
    assert lootlog.parse(GEMS)["outcome"] == "treasure"


def test_an_empty_creature_is_nothing_and_a_missing_line_is_unknown():
    assert lootlog.parse(EMPTY)["outcome"] == "nothing"
    assert lootlog.parse(EMPTY)["creature"] == "large musk hog"
    # The answer window closed before the carried line arrived.
    assert lootlog.parse("You search the scavenger goblin.")["outcome"] == "unknown"


def test_an_answer_that_is_no_search_is_not_logged():
    assert lootlog.parse("I could not find what you were referring to.") is None
    assert lootlog.parse("") is None


def test_rows_read_back_as_rates_per_creature(tmp_path):
    path = tmp_path / "history.db"
    s = SimpleNamespace(state=SimpleNamespace(name="Lanival", room_uid=1234))
    for answer in (BOX, COINS, COINS, EMPTY, "You search the scavenger goblin."):
        lootlog.log(s, answer, "goblins", path=path)
    with sqlite3.connect(str(path)) as connection:
        rows = lootlog.rates(connection)
        stored = connection.execute(
            "SELECT character_name, room, ground, outcome FROM loot ORDER BY seq"
        ).fetchall()
    assert rows == [  # the unknown one is left out of the rates
        {
            "creature": "scavenger goblin",
            "searched": 3,
            "box": 1,
            "treasure": 2,
            "nothing": 0,
        },
        {
            "creature": "large musk hog",
            "searched": 1,
            "box": 0,
            "treasure": 0,
            "nothing": 1,
        },
    ]
    assert stored[0] == ("Lanival", 1234, "goblins", "box")
    assert stored[-1][3] == "unknown"


def test_a_failed_write_never_raises(tmp_path):
    s = SimpleNamespace(state=SimpleNamespace(name="Lanival", room_uid=None))
    assert lootlog.log(s, BOX, path=tmp_path / "no-such-dir" / "history.db") is None
    assert lootlog.log_hunt(s, path=tmp_path / "no-such-dir" / "history.db") is None


def test_a_hunt_is_a_row_and_yields_read_both_tables_per_ground(tmp_path):
    # #419: boxes per search off the loot rows, boxes an hour off the
    # hunts rows, per ground (any case) and per character.
    path = tmp_path / "history.db"
    me = SimpleNamespace(state=SimpleNamespace(name="Lanival", room_uid=1))
    twin = SimpleNamespace(state=SimpleNamespace(name="Sable", room_uid=1))
    for answer in (BOX, COINS, EMPTY):
        lootlog.log(me, answer, "Goblins", path=path)
    lootlog.log(twin, BOX, "goblins", path=path)
    seq = lootlog.log_hunt(
        me,
        path=path,
        ground="goblins",
        style="boxes",
        minutes=30.0,
        kills=3,
        searched=3,
        boxes=1,
        coins=1,
        boxes_taken=1,
        reason="ground taken",
    )
    assert seq == 1
    with sqlite3.connect(str(path)) as connection:
        row = connection.execute(
            "SELECT character_name, ground, style, minutes, kills, boxes, reason"
            " FROM hunts"
        ).fetchone()
        mine = lootlog.yields(connection, "Lanival")
        everyone = lootlog.yields(connection)
    assert row == ("Lanival", "goblins", "boxes", 30.0, 3, 1, "ground taken")
    assert mine == {
        "goblins": {
            "searched": 3,
            "boxes": 1,
            "hunts": 1,
            "minutes": 30.0,
            "hunt_boxes": 1,
        }
    }
    assert everyone["goblins"]["searched"] == 4  # the twin's search too
    assert lootlog.measured("Lanival", path=path) == mine


def test_no_database_measures_nothing_and_creates_none(tmp_path):
    path = tmp_path / "history.db"
    assert lootlog.measured("Lanival", path=path) == {}
    assert not path.exists()
