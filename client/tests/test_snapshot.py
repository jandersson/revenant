"""The state snapshot an outside reader gets from the session (#216):
every field from the parser, plain JSON types, a narrowing list, and
a name it does not know said back."""

import json

from client.engine.snapshot import FIELDS, snapshot
from client.engine.xml_data import XMLData


def _state():
    data = XMLData()
    data.name = "Lanival"
    data.room_title = "[Town Square]"
    data.room_uid = 1
    data.compass = ["n", "s"]
    data.vitals = {"health": 64, "mana": 100}
    data.experience = {
        "Athletics": {"rank": 37, "percent": 4, "mindstate": 2, "rate": "clear"}
    }
    data.left_hand = {"noun": "handaxe", "exist": "1", "name": "an oak-hafted handaxe"}
    data.injuries = {"chest": ("wound", 1)}
    data.active_spells = {"Heroic Strength": 10}
    data.room_players = ["Sable"]
    data.room_creatures = ["a badger", "a badger"]
    data.room_objs = "a striped badger and a rock"
    return data


def test_the_snapshot_holds_every_field_as_plain_json():
    full = snapshot(_state())
    assert set(full) == set(FIELDS)
    assert full["name"] == "Lanival"
    assert full["room"] == {"title": "[Town Square]", "uid": 1, "compass": ["n", "s"]}
    assert full["vitals"] == {"health": 64, "mana": 100}
    assert full["experience"]["Athletics"]["rank"] == 37
    assert full["hands"]["left"]["noun"] == "handaxe" and full["hands"]["right"] is None
    assert full["injuries"] == {"chest": ["wound", 1]}
    assert full["spells"] == {"prepared": None, "active": {"Heroic Strength": 10}}
    assert full["room_players"] == ["Sable"]
    assert full["room_creatures"] == ["a badger", "a badger"]
    assert full["status"]["hands_empty"] is False
    assert full["dead"] is False and full["status"]["dead"] is False
    assert "Town Square" in full["status"]["summary"]
    json.dumps(full)  # nothing but plain types


def test_fields_narrow_the_answer_and_an_unknown_name_is_said_back():
    narrow = snapshot(_state(), ["room", "vitals", "moon"])
    assert set(narrow) == {"room", "vitals", "unknown"}
    assert narrow["unknown"] == ["moon"]
    assert snapshot(_state(), ["", " vitals "]) == {
        "vitals": {"health": 64, "mana": 100}
    }


def test_a_fresh_parser_snapshots_to_empties_not_errors():
    fresh = snapshot(XMLData())
    assert fresh["room"] == {"title": None, "uid": None, "compass": []}
    assert fresh["hands"] == {"left": None, "right": None}
    assert fresh["experience"] == {} and fresh["injuries"] == {}
    json.dumps(fresh)
