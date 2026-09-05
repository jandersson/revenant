"""How ;clock syncs the Elanthian clock and moons — the manual.

The script sends TIME and OBSERVE MOONS, calibrates through
client/eltime.py, and stores the results in settings for the GUI's
clocks dock. Fixtures are the captured answers from test_eltime.
"""

import importlib.util
import json
import pathlib
import types

from client import eltime
from test_eltime import OBSERVE_TEXT, TIME_TEXT, TIME_UNIX

REPO = pathlib.Path(__file__).parents[2]


def _clock():
    spec = importlib.util.spec_from_file_location(
        "clock_script", REPO / "scripts/clock.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


clock = _clock()


class FakeHandle:
    """The script-engine surface ;clock uses, with canned answers."""

    def __init__(self, responses):
        self.responses = responses
        self.pending = []
        self.echoed = []
        self.args = ("once",)
        self.state = None

    def put(self, command):
        self.pending = list(self.responses.get(command, []))

    def get(self, timeout=None):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def sleep(self, seconds):
        raise AssertionError(";clock once must exit, not sleep")


def run_once(monkeypatch, tmp_path, responses):
    monkeypatch.setenv("REVENANT_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setattr(clock, "COLLECT_SECONDS", 0.05)
    # Pin the wall clock to the capture instant so calibration is exact.
    monkeypatch.setattr(clock.time, "time", lambda: TIME_UNIX)
    handle = FakeHandle(responses)
    clock.main(handle)
    try:
        stored = json.loads((tmp_path / "settings.json").read_text())
    except OSError:
        stored = {}
    return handle, stored


def test_clock_once_syncs_calendar_and_moons(monkeypatch, tmp_path):
    handle, stored = run_once(
        monkeypatch,
        tmp_path,
        {
            "time": TIME_TEXT.splitlines(),
            "observe moons": OBSERVE_TEXT.splitlines(),
        },
    )
    # The TIME fixture is the formula's own anchor: zero drift.
    assert stored["eltime_offset_seconds"] == 0
    assert stored["eltime_moons"]["katamba"] == TIME_UNIX - round(
        7 / 8 * eltime.MOON_SYNODIC["katamba"]
    )
    assert any("offset +0s" in line for line in handle.echoed)
    assert any("katamba waning crescent" in line for line in handle.echoed)


def test_clock_skips_moons_indoors(monkeypatch, tmp_path):
    handle, stored = run_once(
        monkeypatch,
        tmp_path,
        {
            "time": TIME_TEXT.splitlines(),
            "observe moons": ["That's a bit hard to do while inside."],
        },
    )
    # The calendar offset saved (which writes the file), but no moon
    # anchor was recorded.
    assert stored.get("eltime_moons", {}) == {}
    assert any("indoors" in line for line in handle.echoed)


def test_clock_reports_when_nothing_answers(monkeypatch, tmp_path):
    handle, stored = run_once(monkeypatch, tmp_path, {})
    assert "eltime_offset_seconds" not in stored
    assert any("is the game answering?" in line for line in handle.echoed)
    assert any("no moons visible" in line for line in handle.echoed)


def test_calibration_prefers_the_server_clock(monkeypatch, tmp_path):
    # The prompt that arrives with the TIME answer stamps it with the
    # server's clock (#102): calibration binds to that, so a local
    # clock lying by an hour changes nothing.
    import types

    monkeypatch.setenv("REVENANT_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setattr(clock, "COLLECT_SECONDS", 0.05)
    monkeypatch.setattr(clock.time, "time", lambda: TIME_UNIX + 3600)  # liar
    handle = FakeHandle({"time": TIME_TEXT.splitlines()})
    handle.state = types.SimpleNamespace(server_time=TIME_UNIX)
    clock.main(handle)
    stored = json.loads((tmp_path / "settings.json").read_text())
    assert stored["eltime_offset_seconds"] == 0  # the anchor capture: zero drift


# --- ;clock watch: passive calibration and orbit anchors (#104, #105) ------


class _Listener:
    def __init__(self, server_time):
        self.state = types.SimpleNamespace(server_time=server_time)
        self.echoed = []

    def echo(self, text):
        self.echoed.append(text)


def _settings_file(monkeypatch, tmp_path, values):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(values))
    monkeypatch.setenv("REVENANT_SETTINGS", str(path))
    return path


def test_a_sun_line_within_tolerance_confirms_the_offset(monkeypatch, tmp_path):
    # 2026-09-04 04:56 Elanthian sunrise capture: the stored offset put
    # the computed clock 4 minutes 56 -> boundary 4.92 = 4:55: 60s out.
    path = _settings_file(monkeypatch, tmp_path, {"eltime_offset_seconds": 0})
    now = 1788554905
    drift = eltime.drift_seconds(eltime.fractional_hour(now, 0), 4.92)
    listener = _Listener(now)
    # Shift the stored offset so the line lands exactly on the boundary.
    path.write_text(json.dumps({"eltime_offset_seconds": -drift}))
    note = clock.hear_boundary(
        listener,
        "The sun rises in a crisp, clear blue sky, heralding another fine day.",
    )
    assert note.startswith("clock: sunrise confirms the calibration")
    assert json.loads(path.read_text())["eltime_offset_seconds"] == -drift


def test_a_sun_line_far_out_corrects_the_offset(monkeypatch, tmp_path):
    path = _settings_file(monkeypatch, tmp_path, {"eltime_offset_seconds": 0})
    now = 1788554905
    drift = eltime.drift_seconds(eltime.fractional_hour(now, 0), 4.92)
    # Push the clock 10 game minutes (600 real seconds) fast.
    path.write_text(json.dumps({"eltime_offset_seconds": -drift + 600}))
    note = clock.hear_boundary(
        _Listener(now), "The sun rises in a crisp, clear blue sky."
    )
    assert "says the clock ran +600s" in note
    assert json.loads(path.read_text())["eltime_offset_seconds"] == -drift


def test_a_moon_rise_pins_the_orbit_and_a_set_implies_the_rise(monkeypatch, tmp_path):
    path = _settings_file(monkeypatch, tmp_path, {})
    now = 1788577396
    note = clock.hear_boundary(
        _Listener(now), "Katamba slowly rises above the horizon."
    )
    assert note.startswith("clock: Katamba rise pinned — up, sets in 2h56m")
    assert json.loads(path.read_text())["eltime_moon_rises"]["katamba"] == now
    note = clock.hear_boundary(
        _Listener(now + 100), "Xibar sets, slowly dropping below the horizon."
    )
    assert note.startswith("clock: Xibar set pinned — down, rises in 2h53m")
    stored = json.loads(path.read_text())["eltime_moon_rises"]
    assert stored["xibar"] == now + 100 - eltime.MOON_ORBIT["xibar"]["up"]
    assert stored["katamba"] == now  # the other anchor survives


def test_ordinary_lines_are_ignored(monkeypatch, tmp_path):
    _settings_file(monkeypatch, tmp_path, {})
    listener = _Listener(1788577396)
    assert clock.hear_boundary(listener, "A ship's rat scurries about.") is None
    assert listener.echoed == []
