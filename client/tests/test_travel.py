"""client.game.travel: the one way a script walks (#407) — a ;go2
target resolved, settings.json's avoid_rooms always routed around, the
walker injected for a test, nothing in the map said."""

import json
from types import SimpleNamespace

from client.game import travel
from client.game.mapdb import MapDB

MAP = MapDB(
    [
        {"id": 1, "uid": [1], "title": ["[Town Square]"], "wayto": {"2": "north"}},
        {
            "id": 2,
            "uid": [2],
            "title": ["[Provincial Bank, Teller]"],
            "tags": ["bank"],
            "wayto": {"1": "south", "3": "east"},
        },
        {
            "id": 3,
            "uid": [3],
            "title": ["[Cougar Vineyard]"],
            "tags": ["cougars"],
            "wayto": {"2": "west"},
        },
    ]
)


def _walker(walks):
    def walk(s, db, goals, describe="", avoid=(), max_steps=None):
        walks.append((set(goals), describe, set(avoid), max_steps))
        return True

    return walk


def _handle():
    return SimpleNamespace(echoed=[], state=SimpleNamespace(room_uid=1))


def test_goals_of_takes_an_id_a_tag_a_title_or_ids_outright():
    assert travel.goals_of(MAP, 2) == {2}
    assert travel.goals_of(MAP, "2") == {2}
    assert travel.goals_of(MAP, "bank") == {2}
    assert travel.goals_of(MAP, "town square") == {1}
    assert travel.goals_of(MAP, [1, "3"]) == {1, 3}
    assert travel.goals_of(MAP, 99) == set()
    assert travel.goals_of(MAP, "") == set()
    assert travel.goals_of(MAP, "nowhere like this") == set()


def test_go_walks_to_the_target_around_the_settings_avoid_rooms(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"avoid_rooms": ["cougars"]}))
    monkeypatch.setenv("REVENANT_SETTINGS", str(settings))
    walks = []
    s = _handle()
    s.echo = s.echoed.append
    assert travel.go(s, "bank", "the teller", db=MAP, walk=_walker(walks))
    assert walks == [({2}, "the teller", {3}, None)]


def test_go_says_when_nothing_matches_and_walks_nowhere():
    walks = []
    s = _handle()
    s.echo = s.echoed.append
    assert travel.go(s, "nowhere", "the shop", db=MAP, walk=_walker(walks)) is False
    assert s.echoed == ["nothing in the map matches the shop"]
    assert walks == []


def test_go_passes_an_explicit_avoid_and_a_step_limit_through():
    walks = []
    s = _handle()
    s.echo = s.echoed.append
    travel.go(s, {1, 2}, db=MAP, walk=_walker(walks), avoid=(), max_steps=50)
    assert walks == [({1, 2}, "{1, 2}", set(), 50)]


def test_here_is_the_walkers_locate():
    assert travel.here(_handle(), db=MAP) == 1
    assert travel.here(SimpleNamespace(state=None), db=MAP) is None


def test_avoided_resolves_the_settings_entries_against_the_map(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"avoid_rooms": ["cougars", "town square", "99"]}))
    monkeypatch.setenv("REVENANT_SETTINGS", str(settings))
    assert travel.avoided(MAP) == {1, 3}
