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


def _unserved_port():
    """A socket bound but never listening: connections are refused, and the
    port cannot be grabbed by another process while we hold it (a closed
    ephemeral port can — CI runners reuse them fast)."""
    placeholder = socket.socket()
    placeholder.bind(("127.0.0.1", 0))
    return placeholder, placeholder.getsockname()[1]


def test_session_running_false_on_unserved_port():
    placeholder, port = _unserved_port()
    assert not launch.session_running("127.0.0.1", port)
    placeholder.close()


def test_resolve_credentials_reports_all_problems(monkeypatch, capsys):
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    with pytest.raises(SystemExit):
        launch.resolve_credentials(None)
    err = capsys.readouterr().err
    assert "REVENANT_ACCOUNT" in err
    assert "character" in err


def test_resolve_credentials_prefers_keychain(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: "pw")
    assert launch.resolve_credentials("Testchar") == ("TESTACCT", None)


def test_resolve_credentials_prompts_ephemerally_on_a_tty(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: None)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(launch.getpass, "getpass", lambda prompt: "typed-once")
    assert launch.resolve_credentials("Testchar") == ("TESTACCT", "typed-once")


def test_resolve_credentials_fails_without_keychain_or_tty(monkeypatch, capsys):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: None)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit):
        launch.resolve_credentials("Testchar")
    assert "no keychain password" in capsys.readouterr().err


def test_wait_for_session_reports_dead_process():
    class DeadProcess:
        returncode = 3

        def poll(self):
            return self.returncode

    placeholder, port = _unserved_port()
    with pytest.raises(SystemExit, match="exited"):
        launch.wait_for_session(DeadProcess(), "127.0.0.1", port, timeout=5)
    placeholder.close()


def test_branded_interpreter_creates_symlink(tmp_path):
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    interpreter = bin_dir / "python3"
    interpreter.write_text("")
    branded = launch.branded_interpreter(interpreter)
    assert branded == tmp_path / "venv" / "branded" / "Revenant"
    assert branded.is_symlink()
    assert branded.resolve() == interpreter.resolve()
    # Second call reuses it.
    assert launch.branded_interpreter(interpreter) == branded


def test_branded_interpreter_repairs_stale_symlink(tmp_path):
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    interpreter = bin_dir / "python3"
    interpreter.write_text("")
    (tmp_path / "venv" / "branded").mkdir()
    stale = tmp_path / "venv" / "branded" / "Revenant"
    stale.symlink_to(bin_dir / "elsewhere")
    branded = launch.branded_interpreter(interpreter)
    assert branded.resolve() == interpreter.resolve()


def test_branded_interpreter_refuses_foreign_file(tmp_path):
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    interpreter = bin_dir / "python3"
    interpreter.write_text("")
    (tmp_path / "venv" / "branded").mkdir()
    (tmp_path / "venv" / "branded" / "Revenant").write_text("not a symlink")
    assert launch.branded_interpreter(interpreter) == interpreter


def test_main_attaches_to_running_session(monkeypatch):
    server, port = _listener()
    calls = []
    monkeypatch.setattr(launch, "exec_gui", lambda args: calls.append(args))
    launch.main(["--port", str(port)])
    assert calls == [["--attach", f"127.0.0.1:{port}"]]
    server.close()
