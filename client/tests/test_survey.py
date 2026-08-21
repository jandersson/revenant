"""How ;survey records unmapped rooms — these tests are the manual.

Rooms the community map doesn't know get appended to the local overlay
with uid-derived ids; the room you came from is linked with the exact
command sent, shadow-copying a community source room into the overlay
when needed (the overlay loads last, so its copy wins).
"""

import importlib.util
import pathlib

from client.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _survey():
    spec = importlib.util.spec_from_file_location(
        "survey_script", REPO / "scripts/survey.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


survey = _survey()

TOWN = MapDB(
    [
        {"id": 7, "uid": [700], "title": ["[Town Gate]"], "wayto": {"8": "north"}},
        {"id": 8, "uid": [800], "title": ["[Road]"], "wayto": {"7": "south"}},
    ]
)


def test_record_room_is_idempotent_per_uid():
    overlay = []
    first = survey.record_room(overlay, 555, "[Hidden Glade]")
    again = survey.record_room(overlay, 555, "[Hidden Glade]")
    assert first is again
    assert overlay == [
        {
            "id": survey.LOCAL_ID_BASE + 555,
            "uid": [555],
            "title": ["[Hidden Glade]"],
            "wayto": {},
        }
    ]


def test_record_edge_shadow_copies_a_community_source():
    overlay = []
    survey.record_room(overlay, 555, "[Hidden Glade]")
    assert survey.record_edge(overlay, TOWN, 700, "go hidden path", 555)
    shadow = survey.overlay_room(overlay, 700)
    # The copy keeps the community edges and gains the surveyed one.
    assert shadow["id"] == 7
    assert shadow["wayto"] == {
        "8": "north",
        str(survey.LOCAL_ID_BASE + 555): "go hidden path",
    }
    # The community room itself is untouched.
    assert TOWN.rooms[7]["wayto"] == {"8": "north"}


def test_record_edge_links_between_two_surveyed_rooms():
    overlay = []
    survey.record_room(overlay, 555, "[Hidden Glade]")
    survey.record_room(overlay, 556, "[Deeper Glade]")
    assert survey.record_edge(overlay, TOWN, 555, "go tunnel", 556)
    glade = survey.overlay_room(overlay, 555)
    assert glade["wayto"] == {str(survey.LOCAL_ID_BASE + 556): "go tunnel"}


def test_record_edge_refuses_unknown_sources_and_empty_commands():
    overlay = []
    survey.record_room(overlay, 555, "[Hidden Glade]")
    assert not survey.record_edge(overlay, TOWN, 12345, "go x", 555)
    assert not survey.record_edge(overlay, TOWN, 700, None, 555)


def test_overlay_roundtrips_through_disk_and_mapdb(tmp_path):
    overlay = []
    survey.record_room(overlay, 555, "[Hidden Glade]")
    survey.record_edge(overlay, TOWN, 700, "go hidden path", 555)
    path = tmp_path / "local.json"
    survey.save_overlay(path, overlay)
    assert survey.load_overlay(path) == overlay

    # Merged the way MapDB.load does it: community rooms + overlay, the
    # overlay's shadow copy winning by id — the new room is walkable.
    community = [
        {"id": 7, "uid": [700], "title": ["[Town Gate]"], "wayto": {"8": "north"}},
        {"id": 8, "uid": [800], "title": ["[Road]"], "wayto": {"7": "south"}},
    ]
    merged = MapDB(community + survey.load_overlay(path))
    assert merged.path(7, [survey.LOCAL_ID_BASE + 555]) == [
        (survey.LOCAL_ID_BASE + 555, "go hidden path")
    ]
