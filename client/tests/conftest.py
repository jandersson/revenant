import os
import tempfile

import pytest


def pytest_configure(config):
    # Keep test logging out of the real ~/.revenant/logs archive.
    os.environ["REVENANT_LOG_DIR"] = tempfile.mkdtemp(prefix="revenant-test-logs-")
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
