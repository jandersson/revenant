""";break — these tests are the manual. `;break almanac` asks the
running script to study the almanac at its next safe point; with no
script running, ;break studies it itself (#372)."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game import interlude

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "break_script", REPO / "scripts/break.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(interlude, "_PENDING", set())
    ran = []
    monkeypatch.setattr(interlude, "run_due", lambda s, make_room=True: ran.append(s))
    return ran


def handle(args, running=("break", "xp", "deathwatch")):
    echoed = []
    return SimpleNamespace(
        name="break",
        args=list(args),
        echo=echoed.append,
        echoed=echoed,
        running_scripts=lambda: list(running),
    )


def test_a_break_is_left_for_the_running_scripts_next_safe_point(fresh):
    s = handle(["Almanac"], running=("break", "xp", "perform"))
    script.main(s)
    assert interlude.pending() == ["almanac"] and fresh == []
    assert s.echoed == ["break: almanac at the next safe point of ;perform"]


def test_with_only_the_monitors_running_break_does_the_chore_itself(fresh):
    s = handle(["almanac"])
    script.main(s)
    assert fresh == [s]


def test_an_unknown_chore_and_the_bare_listing(fresh):
    s = handle(["nap"])
    script.main(s)
    assert s.echoed == ["break: no chore 'nap' — almanac"] and interlude.pending() == []
    s = handle([])
    script.main(s)
    assert s.echoed == ["break: chores almanac; requested none"]
