"""How shared settings load and save — these tests are the manual.

settings.json merges over defaults; unknown keys survive saves; env
vars beat the file (covered with the autostart tests in test_session).
"""

import json

from client.settings import DEFAULTS, load_settings, save_settings, setting


def test_missing_file_yields_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SETTINGS", str(tmp_path / "settings.json"))
    assert load_settings() == DEFAULTS
    assert setting("quit_on_close") is True


def test_file_values_merge_over_defaults(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"quit_on_close": False}))
    monkeypatch.setenv("REVENANT_SETTINGS", str(path))
    assert setting("quit_on_close") is False
    assert setting("autostart_xp") is True  # untouched default


def test_save_preserves_unknown_keys(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"future_knob": 42}))
    monkeypatch.setenv("REVENANT_SETTINGS", str(path))
    save_settings({"autostart_xp": False})
    stored = json.loads(path.read_text())
    assert stored["future_knob"] == 42
    assert stored["autostart_xp"] is False


def test_garbage_file_yields_defaults(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    monkeypatch.setenv("REVENANT_SETTINGS", str(path))
    assert load_settings() == DEFAULTS


def test_font_defaults_to_the_platform_font():
    assert DEFAULTS["font_family"] == ""
    assert DEFAULTS["font_size"] == 0
