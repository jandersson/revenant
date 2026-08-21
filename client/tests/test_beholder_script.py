"""How ;beholder opens the dashboard — these tests are the manual.

The script reuses a dashboard already answering on the port; otherwise
it spawns one detached, waits for the port, and opens the browser
either way.
"""

import importlib.util
import pathlib
import socket

REPO = pathlib.Path(__file__).parents[2]


def _beholder():
    spec = importlib.util.spec_from_file_location(
        "beholder_script", REPO / "scripts/beholder.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


beholder = _beholder()


class FakeHandle:
    def __init__(self):
        self.args = []
        self.echoes = []
        self.slept = 0

    def echo(self, text):
        self.echoes.append(text)

    def sleep(self, seconds):
        self.slept += 1


def test_dashboard_running_detects_a_listening_port():
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]
    assert beholder.dashboard_running(port=port) is True
    server.close()


def test_dashboard_running_false_on_a_closed_port():
    # Bound but not listening: refused, and cannot be reassigned mid-test.
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    port = blocker.getsockname()[1]
    assert beholder.dashboard_running(port=port) is False
    blocker.close()


def test_reuses_a_dashboard_that_is_already_up(monkeypatch):
    opened = []
    monkeypatch.setattr(beholder, "dashboard_running", lambda *a, **k: True)
    monkeypatch.setattr(beholder.webbrowser, "open", lambda url: opened.append(url))
    spawned = []
    monkeypatch.setattr(beholder, "spawn_dashboard", lambda: spawned.append(1))
    handle = FakeHandle()
    beholder.main(handle)
    assert opened == [beholder.URL]
    assert spawned == []  # never starts a second server
    assert any("already running" in echo for echo in handle.echoes)


def test_spawns_and_waits_for_the_port(monkeypatch):
    answers = iter([False, False, True])  # up on the third poll

    class FakeProcess:
        def poll(self):
            return None

    opened = []
    monkeypatch.setattr(beholder, "dashboard_running", lambda *a, **k: next(answers))
    monkeypatch.setattr(beholder, "spawn_dashboard", lambda: FakeProcess())
    monkeypatch.setattr(beholder.webbrowser, "open", lambda url: opened.append(url))
    handle = FakeHandle()
    beholder.main(handle)
    assert opened == [beholder.URL]
    assert any("dashboard up" in echo for echo in handle.echoes)


def test_reports_a_dashboard_that_dies_on_startup(monkeypatch):
    class DeadProcess:
        returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr(beholder, "dashboard_running", lambda *a, **k: False)
    monkeypatch.setattr(beholder, "spawn_dashboard", lambda: DeadProcess())
    monkeypatch.setattr(
        beholder.webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError)
    )
    handle = FakeHandle()
    beholder.main(handle)
    assert any("exited with code 1" in echo for echo in handle.echoes)


def test_quiet_mode_ensures_the_server_without_a_browser(monkeypatch):
    monkeypatch.setattr(beholder, "dashboard_running", lambda *a, **k: True)
    monkeypatch.setattr(
        beholder.webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError)
    )
    handle = FakeHandle()
    handle.args = ["quiet"]
    beholder.main(handle)
    assert handle.echoes == []  # nothing to say when all is well
