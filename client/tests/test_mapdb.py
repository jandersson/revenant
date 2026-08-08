from client.mapdb import MapDB, normalize_title, walkable

ROOMS = [
    {"id": 0, "title": ["[Town Square]"], "tags": ["town"], "wayto": {"1": "north"}},
    {
        "id": 1,
        "title": ["[North Road]"],
        "wayto": {"0": "south", "2": "go gate", "3": ";e fput 'climb wall'"},
    },
    {"id": 2, "title": ["[Bank]"], "tags": ["bank"], "wayto": {"1": "out"}},
    {"id": 3, "title": ["[[Rooftop]]"], "wayto": {}},
]


def db():
    return MapDB(ROOMS)


def test_normalize_title_strips_any_bracket_depth():
    assert normalize_title("[Town Square]") == "town square"
    assert normalize_title("[[Rooftop]]") == "rooftop"


def test_walkable_rejects_embedded_ruby():
    assert walkable("north")
    assert walkable("go gate")
    assert not walkable(";e fput 'climb wall'")
    assert not walkable(None)


def test_resolve_by_id_tag_and_title():
    mapdb = db()
    assert mapdb.resolve("2") == [2]
    assert mapdb.resolve("bank") == [2]
    assert mapdb.resolve("north ro") == [1]


def test_path_finds_shortest_walkable_route():
    assert db().path(0, [2]) == [(1, "north"), (2, "go gate")]


def test_path_none_when_only_scripted_edges_reach_goal():
    assert db().path(0, [3]) is None


def test_path_empty_when_already_there():
    assert db().path(2, [2]) == []
