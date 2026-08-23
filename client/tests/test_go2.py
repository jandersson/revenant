"""How ;go2 knows where you are — these tests are the manual.

Position comes from the game's own <nav rm> uid whenever the community
map knows it; the title+exits guess is only a fallback, because titles
collide (a road repeats the same title for many segments — the live bug
this pins down: three rooms named "[The Crossing, Eylhaar Bane Road]").
"""

import importlib.util
import pathlib
import types

from client.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _go2():
    spec = importlib.util.spec_from_file_location("go2_script", REPO / "scripts/go2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


go2 = _go2()

# Two road segments with the same title; only the uid tells them apart.
ROAD = MapDB(
    [
        {
            "id": 804,
            "uid": [10080],
            "title": ["[The Crossing, Eylhaar Bane Road]"],
            "wayto": {"805": "east"},
        },
        {
            "id": 805,
            "uid": [10081],
            "title": ["[The Crossing, Eylhaar Bane Road]"],
            "wayto": {"804": "west"},
        },
    ]
)


def _state(**fields):
    defaults = {"room_uid": None, "room_title": None, "compass": []}
    return types.SimpleNamespace(**{**defaults, **fields})


def test_position_comes_from_the_games_nav_uid():
    state = _state(room_uid=10081, room_title="[The Crossing, Eylhaar Bane Road]")
    assert go2.locate(ROAD, state) == 805


def test_uid_beats_the_title_guess_on_identically_titled_rooms():
    # The title+exits guess alone cannot tell segment 804 from 805.
    state = _state(
        room_uid=10080,
        room_title="[The Crossing, Eylhaar Bane Road]",
        compass=["w"],  # exits would (wrongly) suggest 805
    )
    assert go2.locate(ROAD, state) == 804


def test_unmapped_uid_falls_back_to_the_title_guess():
    state = _state(room_uid=999999, room_title="[The Crossing, Eylhaar Bane Road]")
    assert go2.locate(ROAD, state) in (804, 805)


def test_unknown_position_is_none_not_a_guess():
    assert go2.locate(ROAD, _state()) is None
    assert go2.locate(ROAD, None) is None


def test_mapdb_indexes_uids():
    assert ROAD.room_by_uid(10080) == 804
    assert ROAD.room_by_uid(424242) is None


def test_go2_direct_skips_the_avoid_list_for_one_trip(monkeypatch, tmp_path):
    # ";go2 direct <target>" ignores settings' avoid_rooms; bare
    # ";go2 direct" still answers with position and usage, proving the
    # word is consumed as a flag, not mistaken for a target.
    import json

    (tmp_path / "mapdb.json").write_text(
        json.dumps([{"id": 5, "uid": [301], "title": ["[Town Square]"], "wayto": {}}])
    )
    monkeypatch.setenv("REVENANT_MAPDB", str(tmp_path / "mapdb.json"))
    monkeypatch.setenv("REVENANT_MAPDB_LOCAL", str(tmp_path / "no-local.json"))
    monkeypatch.setenv("REVENANT_SETTINGS", str(tmp_path / "settings.json"))
    handle = types.SimpleNamespace(
        args=["direct"],
        state=_state(room_uid=301, room_title="[Town Square]"),
        echoes=[],
    )
    handle.echo = handle.echoes.append
    go2.main(handle)
    assert any("you are in room 5" in echo for echo in handle.echoes)
    assert any("usage:" in echo for echo in handle.echoes)
