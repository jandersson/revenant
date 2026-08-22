import json
import socket
import sys
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


def _fake_dialog(monkeypatch, answers):
    """Stand in for client.gui.login_dialog without importing PyQt6."""
    import sys as _sys
    import types

    calls = []

    def ask_credentials(account="", character="", error=""):
        calls.append((account, character, error))
        return answers.pop(0)

    monkeypatch.setitem(
        _sys.modules,
        "client.gui.login_dialog",
        types.SimpleNamespace(ask_credentials=ask_credentials),
    )
    return calls


def test_gather_login_prefers_keychain(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: "pw")
    assert launch.gather_login("Testchar") == ("TESTACCT", "Testchar", None)


def test_gather_login_prompts_ephemerally_on_a_tty(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: None)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(launch.getpass, "getpass", lambda prompt: "typed-once")
    seen = {}
    monkeypatch.setattr(
        launch, "eaccess_protocol", lambda info: seen.update(info) or "KEY123"
    )
    assert launch.gather_login("Testchar") == ("TESTACCT", "Testchar", "KEY123")
    assert seen["password"] == b"typed-once"


def test_gather_login_retries_on_bad_password(monkeypatch, capsys):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", lambda service, user: None)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: True)
    passwords = iter(["wrong", "right"])
    monkeypatch.setattr(launch.getpass, "getpass", lambda prompt: next(passwords))

    def eaccess(info):
        if info["password"] == b"wrong":
            raise launch.LoginError("Bad Password")
        return "KEY456"

    monkeypatch.setattr(launch, "eaccess_protocol", eaccess)
    assert launch.gather_login("Testchar") == ("TESTACCT", "Testchar", "KEY456")
    assert "Bad Password" in capsys.readouterr().err


def test_gather_login_uses_dialog_without_tty(monkeypatch):
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: False)
    _fake_dialog(monkeypatch, [("TESTACCT", "typed", "Testchar", True)])
    stored = {}
    monkeypatch.setattr(
        launch.keyring,
        "set_password",
        lambda service, user, pw: stored.update({user: pw}),
    )
    monkeypatch.setattr(launch, "eaccess_protocol", lambda info: "KEY789")
    assert launch.gather_login(None) == ("TESTACCT", "Testchar", "KEY789")
    assert stored == {"TESTACCT": "typed"}, "remember-me should hit the keychain"


def test_gather_login_uses_saved_names_with_keychain(monkeypatch, tmp_path):
    # Remember-me saved the names earlier; no env vars, no dialog needed.
    defaults = tmp_path / "login.json"
    defaults.write_text('{"account": "SAVEDACCT", "character": "Savedchar"}')
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    looked_up = {}

    def get_password(service, user):
        looked_up["user"] = user
        return "pw"

    monkeypatch.setattr(launch.keyring, "get_password", get_password)
    assert launch.gather_login(None) == ("SAVEDACCT", "Savedchar", None)
    assert looked_up["user"] == "SAVEDACCT"


def test_gather_login_env_overrides_saved_names(monkeypatch, tmp_path):
    defaults = tmp_path / "login.json"
    defaults.write_text('{"account": "SAVEDACCT", "character": "Savedchar"}')
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    monkeypatch.setenv("REVENANT_ACCOUNT", "ENVACCT")
    looked_up = {}

    def get_password(service, user):
        looked_up["user"] = user
        return "pw"

    monkeypatch.setattr(launch.keyring, "get_password", get_password)
    assert launch.gather_login("Envchar") == ("ENVACCT", "Envchar", None)
    assert looked_up["user"] == "ENVACCT"


def test_gather_login_remember_saves_names(monkeypatch, tmp_path):
    defaults = tmp_path / "login.json"
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: False)
    _fake_dialog(monkeypatch, [("TESTACCT", "typed", "Testchar", True)])
    monkeypatch.setattr(launch.keyring, "set_password", lambda *args: None)
    monkeypatch.setattr(launch, "eaccess_protocol", lambda info: "KEY321")
    assert launch.gather_login(None) == ("TESTACCT", "Testchar", "KEY321")
    assert json.loads(defaults.read_text()) == {
        "account": "TESTACCT",
        "character": "Testchar",
    }


def test_gather_login_survives_missing_keyring_backend(monkeypatch):
    # Headless Linux (CI, servers) has no keyring backend: get_password
    # raises NoKeyringError instead of returning None. That must mean
    # "no saved password", never a crash.
    import keyring.errors

    def no_backend(service, user):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch.keyring, "get_password", no_backend)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(launch.getpass, "getpass", lambda prompt: "typed-once")
    monkeypatch.setattr(launch, "eaccess_protocol", lambda info: "KEY654")
    assert launch.gather_login("Testchar") == ("TESTACCT", "Testchar", "KEY654")


def test_gather_login_dialog_cancel_exits(monkeypatch):
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: False)
    _fake_dialog(monkeypatch, [None])
    with pytest.raises(SystemExit):
        launch.gather_login(None)


def test_wait_for_session_reports_dead_process():
    class DeadProcess:
        returncode = 3

        def poll(self):
            return self.returncode

    placeholder, port = _unserved_port()
    with pytest.raises(SystemExit, match="exited"):
        launch.wait_for_session(DeadProcess(), "127.0.0.1", port, timeout=5)
    placeholder.close()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="macOS-only branding; Windows symlinks need elevation (#38)",
)
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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="macOS-only branding; Windows symlinks need elevation (#38)",
)
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


def test_list_characters_prints_the_roster(monkeypatch, capsys, tmp_path):
    defaults = tmp_path / "login.json"
    defaults.write_text('{"account": "TESTACCT"}')
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    monkeypatch.setattr(launch, "keychain_password", lambda account: "pw")
    monkeypatch.setattr(
        launch,
        "fetch_character_list",
        lambda account, password: {"Alpha": "W_1", "Beta": "W_2"},
    )
    launch.main(["--list-characters"])
    assert capsys.readouterr().out == "Alpha\nBeta\n"


def test_list_characters_without_saved_login_explains(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(tmp_path / "login.json"))
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    with pytest.raises(SystemExit, match="log in once with remember"):
        launch.main(["--list-characters"])


def test_main_attaches_to_running_session(monkeypatch):
    server, port = _listener()
    calls = []
    monkeypatch.setattr(launch, "exec_gui", lambda args: calls.append(args))
    launch.main(["--port", str(port)])
    assert calls == [["--attach", f"127.0.0.1:{port}"]]
    server.close()


def test_launch_choices_lists_sessions_then_offline_characters():
    defaults = {
        "accounts": {
            "otheracct": {"account": "OTHERACCT", "characters": ["Gamma"]},
            "testacct": {"account": "TESTACCT", "characters": ["Alpha", "Beta"]},
        }
    }
    sessions = [{"port": 4242, "character": "Beta", "pid": 1}]
    choices = launch.launch_choices(defaults, sessions)
    assert [choice["label"] for choice in choices] == [
        "Beta — online, attach",
        "Gamma — OTHERACCT",
        "Alpha — TESTACCT",
    ]
    assert choices[0]["kind"] == "attach"
    assert choices[0]["port"] == 4242
    assert choices[2] == {
        "kind": "launch",
        "label": "Alpha — TESTACCT",
        "character": "Alpha",
        "account": "TESTACCT",
    }


def test_launch_choices_single_account_drops_the_account_suffix():
    defaults = {
        "accounts": {"testacct": {"account": "TESTACCT", "characters": ["Alpha"]}}
    }
    assert [choice["label"] for choice in launch.launch_choices(defaults, [])] == [
        "Alpha"
    ]


def test_launch_choices_reads_the_legacy_flat_cache():
    defaults = {"account": "TESTACCT", "characters": ["Alpha", "Beta"]}
    labels = [choice["label"] for choice in launch.launch_choices(defaults, [])]
    assert labels == ["Alpha", "Beta"]


def test_get_free_port_skips_occupied_ports():
    server, port = _listener()
    free = launch.get_free_port("127.0.0.1", start=port, tries=5)
    assert port < free < port + 5
    server.close()


def test_main_with_character_attaches_to_its_own_session(monkeypatch):
    from client import session as session_module

    server, port = _listener()
    session_module.register_session(port, "Beta")
    calls = []
    monkeypatch.setattr(launch, "exec_gui", lambda args: calls.append(args))
    launch.main(["Beta", "--port", str(port)])
    assert calls == [["--attach", f"127.0.0.1:{port}"]]
    server.close()


def test_main_with_character_spawns_beside_a_running_session(monkeypatch):
    # The pre-#58 behavior attached to whatever ran on the port with
    # "character argument ignored" — now the other character gets a
    # session of their own on a free port.
    from client import session as session_module

    server, port = _listener()
    session_module.register_session(port, "Beta")
    calls = {}
    monkeypatch.setattr(
        launch,
        "gather_login",
        lambda character, fresh_account=False, account=None: (
            account or "TESTACCT",
            character,
            "KEY",
        ),
    )
    monkeypatch.setattr(
        launch,
        "start_session",
        lambda host, spawn_port, character, key, account=None: calls.setdefault(
            "spawn", (spawn_port, character, key)
        ),
    )
    monkeypatch.setattr(launch, "exec_gui", lambda args: calls.setdefault("gui", args))
    launch.main(["Alpha", "--port", str(port)])
    spawn_port, character, key = calls["spawn"]
    assert character == "Alpha"
    assert key == "KEY"
    assert spawn_port != port
    assert calls["gui"] == ["--attach", f"127.0.0.1:{spawn_port}"]
    server.close()


def _stub_picker(monkeypatch, answer):
    import sys
    import types

    stub = types.SimpleNamespace(
        ask_character=lambda labels, default, account: answer(labels, default)
    )
    monkeypatch.setitem(sys.modules, "client.gui.login_dialog", stub)


def test_pick_and_go_attaches_to_a_picked_session(monkeypatch):
    from client import session as session_module

    server, port = _listener()
    session_module.register_session(port, "Beta")
    calls = []
    monkeypatch.setattr(launch, "exec_gui", lambda args: calls.append(args))
    _stub_picker(monkeypatch, lambda labels, default: labels[0])
    launch.pick_and_go("127.0.0.1", port)
    assert calls == [["--attach", f"127.0.0.1:{port}"]]
    server.close()


def test_pick_and_go_launches_a_picked_character(monkeypatch, tmp_path):
    defaults = tmp_path / "login.json"
    defaults.write_text(
        '{"accounts": {"testacct": {"account": "TESTACCT", "characters": ["Alpha"]}}}'
    )
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    calls = {}

    def fake_gather(character, fresh_account=False, account=None):
        calls["login"] = (character, account)
        return account, character, "KEY"

    monkeypatch.setattr(launch, "gather_login", fake_gather)
    monkeypatch.setattr(
        launch,
        "start_session",
        lambda host, port, character, key, account=None: calls.setdefault(
            "spawn", port
        ),
    )
    monkeypatch.setattr(launch, "exec_gui", lambda args: calls.setdefault("gui", args))
    _stub_picker(monkeypatch, lambda labels, default: "Alpha")
    launch.pick_and_go("127.0.0.1", 4242)
    assert calls["login"] == ("Alpha", "TESTACCT")
    assert calls["gui"] == ["--attach", f"127.0.0.1:{calls['spawn']}"]


def test_pick_and_go_cancel_means_no_gui(monkeypatch, tmp_path):
    defaults = tmp_path / "login.json"
    defaults.write_text('{"accounts": {"testacct": {"characters": ["Alpha"]}}}')
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    calls = []
    monkeypatch.setattr(launch, "exec_gui", lambda args: calls.append(args))
    _stub_picker(monkeypatch, lambda labels, default: None)
    assert launch.pick_and_go("127.0.0.1", 4242) is None
    assert calls == []


def test_gather_login_fresh_account_ignores_saved_identity(monkeypatch, tmp_path):
    import sys
    import types

    defaults = tmp_path / "login.json"
    defaults.write_text('{"account": "TESTACCT", "character": "Alpha"}')
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setattr(launch, "keychain_password", lambda account: "hunter2")
    # The saved identity would log straight in ...
    assert launch.gather_login("Alpha") == ("TESTACCT", "Alpha", None)
    # ... but fresh_account must fall through to the login dialog instead
    # (stubbed: cancelling it raises SystemExit).
    stub = types.SimpleNamespace(ask_credentials=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "client.gui.login_dialog", stub)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: False, raising=False)
    with pytest.raises(SystemExit):
        launch.gather_login("", fresh_account=True)


def test_gather_login_blank_dialog_password_uses_the_keychain(monkeypatch, tmp_path):
    import sys
    import types

    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(tmp_path / "login.json"))
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    monkeypatch.setattr(launch.sys.stdin, "isatty", lambda: False, raising=False)
    # The dialog answers with a blank password for a remembered account.
    stub = types.SimpleNamespace(
        ask_credentials=lambda *args, **kwargs: ("TESTACCT", "", "Alpha", False)
    )
    monkeypatch.setitem(sys.modules, "client.gui.login_dialog", stub)
    monkeypatch.setattr(launch, "keychain_password", lambda account: "saved-secret")
    seen = {}

    def eaccess(info):
        seen.update(info)
        return "KEY111"

    monkeypatch.setattr(launch, "eaccess_protocol", eaccess)
    assert launch.gather_login("Alpha") == ("TESTACCT", "Alpha", "KEY111")
    assert seen["password"] == b"saved-secret"
