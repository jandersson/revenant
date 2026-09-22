import os
import tempfile

import pytest


def pytest_configure(config):
    # Keep test logging out of the real ~/.revenant/logs archive.
    os.environ["REVENANT_LOG_DIR"] = tempfile.mkdtemp(prefix="revenant-test-logs-")
    # And the history database: the walker logs every climb it sends to
    # it on its own now (#159), so a test walk must never land in the
    # operator's ~/.revenant/history.db. Tests that name their own path
    # (test_sheet, test_circle_script) override this per test.
    os.environ["REVENANT_HISTORY_DB"] = os.path.join(
        tempfile.mkdtemp(prefix="revenant-test-history-"), "history.db"
    )
    # And the session registry: a session thread that outlives its test
    # deregisters into whatever the env names by then — never the
    # operator's ~/.revenant/sessions.json (#160).
    os.environ["REVENANT_SESSIONS"] = os.path.join(
        tempfile.mkdtemp(prefix="revenant-test-sessions-"), "sessions.json"
    )


@pytest.fixture(autouse=True)
def _isolated_login_defaults(tmp_path, monkeypatch):
    # Per-test, not per-run: a remember-me test writing the file must not
    # leak saved names into later tests (it did — CI caught it via a
    # NoKeyringError only reachable with names present).
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(tmp_path / "login.json"))
    # Session servers register themselves; tests must never touch the
    # real ~/.revenant/sessions.json.
    monkeypatch.setenv("REVENANT_SESSIONS", str(tmp_path / "sessions.json"))
    # The book reader's read times per character (#255): never the
    # operator's ~/.revenant/scholarship.
    monkeypatch.setenv("REVENANT_SCHOLARSHIP_DIR", str(tmp_path / "scholarship"))


@pytest.fixture
def travel(monkeypatch):
    """;hunt's walk() and locate() over a hunt Arena's own idea of where
    it is (hunt_arena.py, the test_hunt*.py files): a walk lands in the
    first room of the goals and meets whatever the arena put there."""
    import hunt_arena

    def walk(s, db, goals, describe="", avoid=()):
        s.walks.append(set(goals))
        s.room = s.state.room = min(goals)
        if s.room in s.arrivals:
            s.state.hostiles = dict(s.arrivals[s.room])
        return True

    monkeypatch.setattr(hunt_arena.hunt, "walk", walk)
    monkeypatch.setattr(hunt_arena.hunt, "locate", lambda db, state: state.room)
    return walk
