import socket
from threading import Thread

import pytest

from client import launch


def _listener():
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]

    def accept_loop():
        try:
            while True:
                conn, _ = server.accept()
                conn.close()
        except OSError:
            pass

    Thread(target=accept_loop, daemon=True).start()
    return server, port


def test_session_running_detects_listener():
    server, port = _listener()
    assert launch.session_running("127.0.0.1", port)
    server.close()


def test_session_running_false_on_closed_port():
    server, port = _listener()
    server.close()
    assert not launch.session_running("127.0.0.1", port)


def test_ensure_credentials_reports_all_problems(monkeypatch, capsys):
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    with pytest.raises(SystemExit):
        launch.ensure_credentials(None)
    err = capsys.readouterr().err
    assert "REVENANT_ACCOUNT" in err
    assert "character" in err


def test_ensure_credentials_checks_keychain(monkeypatch, capsys):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: None)
    with pytest.raises(SystemExit):
        launch.ensure_credentials("Testchar")
    assert "keychain" in capsys.readouterr().err


def test_ensure_credentials_passes_when_complete(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: "pw")
    launch.ensure_credentials("Testchar")


def test_wait_for_session_reports_dead_process():
    class DeadProcess:
        returncode = 3

        def poll(self):
            return self.returncode

    server, port = _listener()
    server.close()
    with pytest.raises(SystemExit, match="exited"):
        launch.wait_for_session(DeadProcess(), "127.0.0.1", port, timeout=5)


def test_main_attaches_to_running_session(monkeypatch):
    from client.gui import client_gui

    server, port = _listener()
    calls = []
    monkeypatch.setattr(client_gui, "main", lambda argv: calls.append(argv))
    launch.main(["--port", str(port)])
    assert calls == [["--attach", f"127.0.0.1:{port}"]]
    server.close()
