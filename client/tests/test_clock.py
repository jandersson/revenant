"""How ;clock syncs the Elanthian clock and moons — the manual.

The script sends TIME and OBSERVE MOONS, calibrates through
client/eltime.py, and stores the results in settings for the GUI's
clocks dock. Fixtures are the captured answers from test_eltime.
"""

import importlib.util
import json
import pathlib

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
