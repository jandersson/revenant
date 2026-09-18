"""File → Reconnect after the session died logs the window's own
character in, on the account that owns it — not the saved login
default (2026-09-19: the Paladin's window reconnected as the account's
other character)."""

from client.engine import launch
from client.engine.session import AttachedEngine

DEFAULTS = {
    "account": "TESTACCT",
    "character": "Uthmor",  # the login screen's last remembered character
    "accounts": {
        "testacct": {"account": "TESTACCT", "characters": ["Uthmor"]},
        "other": {"account": "OTHERACCT", "characters": ["Lanival", "Sable"]},
    },
}


def test_reconnect_logs_the_windows_own_character_in(window, monkeypatch):
    calls = {}
    monkeypatch.setattr(launch, "session_running", lambda host, port: False)
    monkeypatch.setattr(launch, "load_login_defaults", lambda: DEFAULTS)

    def gather(character, fresh_account=False, account=None):
        calls["gather"] = (character, account)
        return account, character, None

    def spawn(host, port, character, key=None, account=None):
        calls["spawn"] = (character, account)
        return "process"

    monkeypatch.setattr(launch, "gather_login", gather)
    monkeypatch.setattr(launch, "spawn_session", spawn)
    monkeypatch.setattr(window, "_finish_reconnect", lambda process, wait: None)
    window.client = AttachedEngine("127.0.0.1", 1)
    window._reader_thread = None

    window.reconnect()

    assert calls["gather"] == ("Lanival", "OTHERACCT")
    assert calls["spawn"] == ("Lanival", "OTHERACCT")
    assert "starting one" in window.status_bar.currentMessage()


def test_a_window_without_a_character_falls_back_and_says_so(window, monkeypatch):
    calls = {}
    monkeypatch.setattr(launch, "session_running", lambda host, port: False)
    monkeypatch.setattr(launch, "load_login_defaults", lambda: DEFAULTS)
    monkeypatch.setattr(
        launch,
        "gather_login",
        lambda character, fresh_account=False, account=None: (
            calls.setdefault("gather", (character, account))
            and ("TESTACCT", "Uthmor", None)
        ),
    )
    monkeypatch.setattr(
        launch, "spawn_session", lambda *args, **kwargs: calls.setdefault("spawn", args)
    )
    monkeypatch.setattr(window, "_finish_reconnect", lambda process, wait: None)
    window.client = AttachedEngine("127.0.0.1", 1)
    window._reader_thread = None
    window._character = None

    window.reconnect()

    assert calls["gather"] == (None, None)
    assert "never learned its character" in window.main_window.toPlainText()
