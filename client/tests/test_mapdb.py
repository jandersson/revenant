from client.mapdb import MapDB, normalize_title, walkable

ROOMS = [
    {"id": 0, "title": ["[Town Square]"], "tags": ["town"], "wayto": {"1": "north"}},
    {
        "id": 1,
        "title": ["[North Road]"],
        # The rooftop edge has real lich logic: untranslatable, unwalkable.
        "wayto": {
            "0": "south",
            "2": "go gate",
            "3": ";e start_script('climb-wall');wait_while{running?('climb-wall')}",
        },
    },
    {"id": 2, "title": ["[Bank]"], "tags": ["bank"], "wayto": {"1": "out"}},
    {"id": 3, "title": ["[[Rooftop]]"], "wayto": {}},
]


def db():
    return MapDB(ROOMS)


def test_normalize_title_strips_any_bracket_depth():
    assert normalize_title("[Town Square]") == "town square"
    assert normalize_title("[[Rooftop]]") == "rooftop"


def test_walkable_accepts_simple_and_translated_edges_only():
    assert walkable("north")
    assert walkable("go gate")
    # Simple fput/move literals now translate and walk (issue #37) ...
    assert walkable(";e fput 'climb wall'")
    # ... but embedded logic stays unwalkable.
    assert not walkable(";e start_script('climb-wall')")
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


def test_path_routes_through_translatable_embedded_edges():
    # The #79 discrepancy, pinned: whole areas hang off simple ;e edges
    # (the live 1429→10171 route crosses eleven, ";e move('s'); waitrt?"
    # style). A graph that drops every ;e edge partitions them away; the
    # walkable rule is translate-or-drop, never drop-all.
    rooms = [
        {"id": 0, "title": ["[Cliff Top]"], "wayto": {"1": ";e move('s'); waitrt?"}},
        {
            "id": 1,
            "title": ["[Cliff Path]"],
            "wayto": {"2": ";e fput('search'); move 'go onyx arch';"},
        },
        {"id": 2, "title": ["[The Strand]"], "wayto": {}},
    ]
    route = MapDB(rooms).path(0, [2])
    assert route == [
        (1, ";e move('s'); waitrt?"),
        (2, ";e fput('search'); move 'go onyx arch';"),
    ]


def test_path_prefers_fast_steps_over_a_slow_shortcut():
    # Routes optimize travel time, not hop count: the map's timeto says
    # the direct swim costs 30s, so two ordinary 0.2s steps win.
    rooms = [
        {
            "id": 0,
            "title": ["[River Bank]"],
            "wayto": {"1": "north", "2": "swim river"},
            "timeto": {"1": 0.2, "2": 30},
        },
        {
            "id": 1,
            "title": ["[Bridge]"],
            "wayto": {"2": "east"},
            "timeto": {"2": 0.2},
        },
        {"id": 2, "title": ["[Far Bank]"], "wayto": {}},
    ]
    assert MapDB(rooms).path(0, [2]) == [(1, "north"), (2, "east")]


def test_unusable_timeto_falls_back_to_the_default_step():
    from client.mapdb import DEFAULT_STEP_SECONDS, edge_seconds

    # Some timeto values are embedded-Ruby conditionals or null — they
    # cost a plain step, they don't poison the route.
    room = {"timeto": {"1": ";e UserVars.premium ? 2 : nil", "2": None, "3": 4}}
    assert edge_seconds(room, "1") == DEFAULT_STEP_SECONDS
    assert edge_seconds(room, "2") == DEFAULT_STEP_SECONDS
    assert edge_seconds(room, "3") == 4.0
    assert edge_seconds(room, "9") == DEFAULT_STEP_SECONDS  # absent entirely


def test_path_detours_around_avoided_rooms_when_it_can():
    # The standing avoid list (cougar grounds, #72) reroutes travel:
    # the fast road crosses room 1, so the slow-but-clean detour wins.
    rooms = [
        {
            "id": 0,
            "title": ["[Trailhead]"],
            "wayto": {"1": "north", "3": "east"},
            "timeto": {"1": 0.2, "3": 0.2},
        },
        {
            "id": 1,
            "title": ["[Cougar Cliffs]"],
            "tags": ["cougars"],
            "wayto": {"2": "north"},
            "timeto": {"2": 0.2},
        },
        {"id": 2, "title": ["[Overlook]"], "wayto": {}},
        {
            "id": 3,
            "title": ["[Long Road]"],
            "wayto": {"4": "north"},
            "timeto": {"4": 30},
        },
        {
            "id": 4,
            "title": ["[Long Road]"],
            "wayto": {"2": "west"},
            "timeto": {"2": 30},
        },
    ]
    db = MapDB(rooms)
    assert [room for room, _ in db.path(0, [2])] == [1, 2]  # fastest, unguarded
    assert [room for room, _ in db.path(0, [2], avoid={1})] == [3, 4, 2]


def test_path_crosses_an_avoided_room_when_there_is_no_way_around():
    # Avoidance is a penalty, not a wall: with no clean detour the
    # route still exists — walker.walk announces the crossing instead.
    rooms = [
        {"id": 0, "title": ["[Gate]"], "wayto": {"1": "north"}},
        {"id": 1, "title": ["[Cougar Cliffs]"], "wayto": {"2": "north"}},
        {"id": 2, "title": ["[Overlook]"], "wayto": {}},
    ]
    assert [room for room, _ in MapDB(rooms).path(0, [2], avoid={1})] == [1, 2]


def test_graph_holds_every_room_but_only_walkable_edges():
    graph = db().graph
    assert set(graph.nodes) == {0, 1, 2, 3}  # isolated rooms included
    assert graph.edges[0, 1]["command"] == "north"
    assert not graph.has_edge(1, 3)  # untranslatable ;e edge dropped


def test_path_empty_when_already_there():
    assert db().path(2, [2]) == []


def test_local_overlay_extends_the_community_map(monkeypatch, tmp_path):
    # Personal survey data (event areas the community map lacks) merges
    # into every load — ;go2 sees local rooms and their uids natively.
    import json

    from client import mapdb

    (tmp_path / "mapdb.json").write_text(
        json.dumps([{"id": 1, "title": ["[Town Square]"], "wayto": {}}])
    )
    (tmp_path / "local.json").write_text(
        json.dumps(
            [{"id": 900001, "uid": [499002], "title": ["[Hidden Vault]"], "wayto": {}}]
        )
    )
    monkeypatch.setenv("REVENANT_MAPDB", str(tmp_path / "mapdb.json"))
    monkeypatch.setenv("REVENANT_MAPDB_LOCAL", str(tmp_path / "local.json"))
    db = mapdb.MapDB.load()
    assert 1 in db.rooms  # community rooms intact
    assert db.room_by_uid(499002) == 900001  # local survey merged


# One Middens room, listed twice — captured 2026-09-04 (#137). The
# community map does this in 39 places; only one twin carries the uid.
MIDDENS = [
    {
        "id": 684,
        "uid": [200008],
        "title": ["[[Middens, Alerin Slade]]"],
        "wayto": {"670": "south", "13100": "south", "685": "northwest"},
    },
    {
        "id": 670,
        "title": ["[[Middens, Gravel Way]]"],
        "wayto": {"669": "east", "671": "south", "684": "north"},
    },
    {
        "id": 13100,
        "uid": [200009],
        "title": ["[[Middens, Gravel Way]]"],
        "wayto": {"669": "east", "671": "south", "684": "north"},
    },
    {
        "id": 669,
        "uid": [200010],
        "title": ["[[Middens, Bumboat Row]]"],
        "wayto": {"668": "east", "670": "west"},
    },
    {
        "id": 671,
        "uid": [200027],
        "title": ["[[Middens, Bumboat Row]]"],
        "wayto": {"672": "west", "670": "north"},
    },
    {"id": 685, "uid": [200007], "title": ["[[Middens, Alerin Slade]]"], "wayto": {}},
    {"id": 668, "uid": [200011], "title": ["[[Middens, Bumboat Row]]"], "wayto": {}},
    {"id": 672, "uid": [200026], "title": ["[[Middens, Bumboat Row]]"], "wayto": {}},
]


def test_two_dead_ends_sharing_a_title_are_not_twins():
    db = MapDB(MIDDENS)
    assert not db.same_place(668, 672)


def test_twins_with_one_title_and_one_set_of_exits_are_the_same_place():
    db = MapDB(MIDDENS)
    assert db.same_place(670, 13100)
    assert db.same_place(13100, 670)
    assert db.same_place(670, 670)


def test_rooms_that_only_share_a_title_are_not_twins():
    # 669 and 671 are both "Bumboat Row" but different rooms.
    db = MapDB(MIDDENS)
    assert not db.same_place(669, 671)
    assert not db.same_place(684, 670)
    assert not db.same_place(670, 424242)  # unknown id


def test_rooms_sharing_a_uid_are_the_same_place_whatever_their_exits():
    db = MapDB(
        [
            {"id": 1, "uid": [5], "title": ["[A]"], "wayto": {"2": "n"}},
            {"id": 2, "uid": [5], "title": ["[A, renamed]"], "wayto": {}},
        ]
    )
    assert db.same_place(1, 2)


def test_a_route_plans_through_the_twin_the_game_will_report():
    # 684 names both twins "south"; the plan must carry the id the
    # arrival uid resolves to, or the walker stops one step short.
    db = MapDB(MIDDENS)
    assert db.path(684, [669]) == [(13100, "south"), (669, "east")]
    assert 670 not in db.graph.successors(684)
