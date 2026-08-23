"""How ;deathwatch protects an unattended death — these tests are the manual.

Watch the DEAD indicator; on death, parse the announced decay window,
hold a rescue grace inside it (answering the idle check), then walk
the depart ladder best-variant-first, judging every attempt by the
indicator actually clearing. The wordings come from a captured death
(2026-08-22, docs/death.md).
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

REPO = pathlib.Path(__file__).parents[2]


def _deathwatch():
    spec = importlib.util.spec_from_file_location(
        "deathwatch_script", REPO / "scripts/deathwatch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deathwatch = _deathwatch()

DECAY_LINE = "Your body will decay beyond its ability to hold your soul in 21 minutes."
GHOST_LINE = (
    "You are a ghost!  You must wait until someone resurrects you, or you decay."
)


class LoopDone(Exception):
    """Raised by the fake handle to end the forever-loops."""


class FakeHandle:
    """The script surface: an indicator dict, a line queue, a sleep
    budget ending the run the way ;stop would."""

    def __init__(self, args=(), sleeps=30, dead=False):
        self.args = list(args)
        self.calls = []
        self.echoes = []
        self.lines = []
        self._sleeps = sleeps
        self.state = SimpleNamespace(indicator={"IconDEAD": "y" if dead else "n"})

    def put(self, command):
        self.calls.append(("put", command))

    def get(self, timeout=None):
        return self.lines.pop(0) if self.lines else None

    def echo(self, text):
        self.echoes.append(text)

    def sleep(self, seconds):
        self.calls.append(("sleep", seconds))
        self._sleeps -= 1
        if self._sleeps <= 0:
            raise LoopDone()


class DepartAtGraveHandle(FakeHandle):
    """DEPART FULL and ITEMS are refused (too few favors — the state
    stays dead); DEPART GRAVE takes."""

    def put(self, command):
        super().put(command)
        if command == "depart grave":
            self.state.indicator = {"IconDEAD": "n"}


def test_grace_argument_and_default():
    assert deathwatch.grace_minutes_from(["5"]) == 5.0
    assert deathwatch.grace_minutes_from([]) == 10.0
    assert deathwatch.grace_minutes_from(["soon"]) == 10.0


def test_decay_window_parsed_from_the_captured_line(monkeypatch):
    monkeypatch.setattr(deathwatch, "DECAY_SCAN_SECONDS", 0.05)
    handle = FakeHandle(dead=True)
    handle.lines = [GHOST_LINE, DECAY_LINE]
    assert deathwatch.scan_decay_minutes(handle) == 21


def test_depart_ladder_steps_down_until_the_indicator_clears(monkeypatch):
    monkeypatch.setattr(deathwatch, "DEPART_WAIT", 4)
    handle = DepartAtGraveHandle(dead=True, sleeps=40)
    assert deathwatch.depart(handle) is True
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert puts == ["depart full", "depart items", "depart grave"]
    assert any("departed (depart grave)" in echo for echo in handle.echoes)


def test_zero_grace_departs_immediately(monkeypatch):
    monkeypatch.setattr(deathwatch, "DECAY_SCAN_SECONDS", 0.05)
    monkeypatch.setattr(deathwatch, "DEPART_WAIT", 2)
    handle = DepartAtGraveHandle(dead=True, sleeps=40)
    handle.lines = [DECAY_LINE]
    deathwatch.handle_death(handle, grace_minutes=0)
    assert any("21 minute decay window" in echo for echo in handle.echoes)
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert "depart full" in puts


class RescuedHandle(FakeHandle):
    """A resurrection lands after two polls of the grace wait."""

    def sleep(self, seconds):
        super().sleep(seconds)
        self._polls = getattr(self, "_polls", 0) + 1
        if self._polls >= 2:
            self.state.indicator = {"IconDEAD": "n"}


def test_a_rescue_during_the_grace_stands_the_watch_down(monkeypatch):
    monkeypatch.setattr(deathwatch, "DECAY_SCAN_SECONDS", 0.05)
    handle = RescuedHandle(dead=True, sleeps=30)
    deathwatch.handle_death(handle, grace_minutes=10)
    assert any("standing down" in echo for echo in handle.echoes)
    assert not any("depart" in call[1] for call in handle.calls if call[0] == "put")


def test_the_grace_wait_answers_the_idle_check(monkeypatch):
    # The captured death ended in an idle disconnect; the ghost refusal
    # a LOOK earns still counts as activity (docs/death.md).
    monkeypatch.setattr(deathwatch, "KEEPALIVE_SECONDS", 0)
    handle = FakeHandle(dead=True, sleeps=5)
    with pytest.raises(LoopDone):
        deathwatch.wait_for_rescue(handle, grace_seconds=300)
    assert ("put", "look") in handle.calls


def test_a_death_that_predates_the_watch_starts_the_countdown(monkeypatch):
    # The captured blindness (#92): a ;reexec restarted deathwatch while
    # the character was already a ghost, and the fresh watch idled. Dead
    # at startup must count as a freshly observed death.
    monkeypatch.setattr(deathwatch, "DECAY_SCAN_SECONDS", 0.05)
    monkeypatch.setattr(deathwatch, "DEPART_WAIT", 2)
    handle = DepartAtGraveHandle(args=["0"], dead=True, sleeps=40)
    with pytest.raises(LoopDone):
        deathwatch.main(handle)
    puts = [call[1] for call in handle.calls if call[0] == "put"]
    assert "depart full" in puts
    assert any("you are DEAD" in echo for echo in handle.echoes)


def test_watching_costs_nothing_while_alive():
    handle = FakeHandle(sleeps=5)
    with pytest.raises(LoopDone):
        deathwatch.main(handle)
    assert not [call for call in handle.calls if call[0] == "put"]
    assert any("watching" in echo for echo in handle.echoes)
