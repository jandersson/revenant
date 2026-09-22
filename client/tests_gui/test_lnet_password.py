"""File → LNet Password…, offscreen: the game window asks for the
character's LNet password in a masked field and hands it to the
keychain writer under that name — never a file, never the real
keychain from a test (#290, 2026-09-22)."""

from PyQt6.QtWidgets import QDialog, QLineEdit


def _file_actions(window):
    for menu in window.menuBar().findChildren(
        type(window.menuBar().actions()[0].menu())
    ):
        if menu.title() == "&File":
            return [action.text() for action in menu.actions()]
    return []


def test_the_file_menu_offers_the_lnet_password(window):
    assert "LNet Pass&word…" in _file_actions(window)


def test_the_password_goes_to_the_keychain_under_the_windows_character(
    window, monkeypatch
):
    from client.engine import lnet_login
    from client.gui import chat_window

    stored = []
    monkeypatch.setattr(
        lnet_login,
        "remember",
        lambda name, password: stored.append((name, password)) or True,
    )
    built = {}

    def fake_exec(dialog):
        built["echo"] = dialog.password.echoMode()
        built["remember_hidden"] = dialog.remember.isHidden()
        dialog.password.setText("hunter2")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(chat_window.PasswordDialog, "exec", fake_exec)
    window.store_lnet_password()
    assert stored == [("Lanival", "hunter2")]
    assert built["echo"] == QLineEdit.EchoMode.Password
    assert built["remember_hidden"] is True
    assert "stored for Lanival" in window.status_bar.currentMessage()
    # Cancelled, or left empty: nothing reaches the keychain.
    stored.clear()
    monkeypatch.setattr(
        chat_window.PasswordDialog, "exec", lambda dialog: QDialog.DialogCode.Rejected
    )
    window.store_lnet_password()
    assert stored == []

    def empty(dialog):
        dialog.password.setText("")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(chat_window.PasswordDialog, "exec", empty)
    window.store_lnet_password()
    assert stored == [] and "nothing stored" in window.status_bar.currentMessage()
