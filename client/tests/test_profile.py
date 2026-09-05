"""How character profiles load, save and coerce — these tests are the manual.

One JSON file per character under ~/.revenant/profiles/ (REVENANT_PROFILES
overrides), defaults merged over the file, unknown keys preserved, and
every value coerced to the kind FIELDS declares, since both the dialog
and a text editor hand back strings.
"""

import json

import pytest

from client.profile import (
    DEFAULTS,
    FIELDS,
    describe,
    load_profile,
    normalize,
    profile_path,
    save_profile,
)


@pytest.fixture(autouse=True)
def _profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    return tmp_path


def test_every_default_has_a_dialog_row_and_vice_versa():
    assert {key for key, _, _, _ in FIELDS} == set(DEFAULTS)


def test_the_file_is_named_after_the_character_sanitized(tmp_path):
    assert profile_path("Lanival") == tmp_path / "lanival.json"
    assert profile_path("../Sable's") == tmp_path / "sables.json"
    assert profile_path("") == tmp_path / "unnamed.json"


def test_missing_file_yields_defaults():
    assert load_profile("Lanival") == DEFAULTS


def test_save_then_load_round_trips_and_keeps_unknown_keys(tmp_path):
    path = tmp_path / "lanival.json"
    path.write_text(json.dumps({"future_knob": 42}))
    save_profile("Lanival", {"weapon": "handaxe", "skin": True, "health_floor": 70})
    stored = json.loads(path.read_text())
    assert stored["future_knob"] == 42
    profile = load_profile("Lanival")
    assert profile["weapon"] == "handaxe"
    assert profile["skin"] is True
    assert profile["health_floor"] == 70
    assert profile["future_knob"] == 42


def test_dialog_strings_are_coerced_to_their_kinds():
    clean = normalize(
        {
            "skin": "true",
            "health_floor": "55",
            "train_skills": "Small Edged, Evasion,",
            "weapon": "  handaxe ",
            "max_kills": "not a number",
        }
    )
    assert clean == {
        "skin": True,
        "health_floor": 55,
        "train_skills": ["Small Edged", "Evasion"],
        "weapon": "handaxe",
        "max_kills": DEFAULTS["max_kills"],
    }


def test_garbage_file_yields_defaults(tmp_path):
    (tmp_path / "lanival.json").write_text("{not json")
    assert load_profile("Lanival") == DEFAULTS


def test_describe_reads_like_the_dialog():
    lines = describe(
        load_profile("Lanival") | {"skin": True, "train_skills": ["Evasion"]}
    )
    assert "Skin each kill: yes" in lines
    assert "Stop when these skills lock: Evasion" in lines
    assert "Weapon noun: (empty)" in lines
