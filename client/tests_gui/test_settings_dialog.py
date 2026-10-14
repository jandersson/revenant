"""File → Settings' Dropbox sync row, offscreen (#548): it names the
Dropbox folder it found, or says there is none and stays off; ticking
it saves the setting and starts ;dropbox in the running session at once
— nobody should need a terminal or a restart for it."""

import json

from client.game import dropbox
from client.gui.settings_dialog import SettingsDialog


def test_the_dropbox_row_names_the_folder_found_and_carries_the_tick(
    qapp, tmp_path, monkeypatch
):
    found = tmp_path / "Dropbox"
    found.mkdir()
    monkeypatch.setattr(dropbox, "find_dropbox", lambda: found)
    dialog = SettingsDialog({"dropbox_sync": False})
    assert dialog.dropbox_sync.isEnabled() and not dialog.dropbox_sync.isChecked()
    assert dialog.dropbox_folder.text() == f"Dropbox folder: {found}"
    dialog.dropbox_sync.setChecked(True)
    assert dialog.values()["dropbox_sync"] is True


def test_without_dropbox_the_row_says_so_and_stays_off(qapp, monkeypatch):
    monkeypatch.setattr(dropbox, "find_dropbox", lambda: None)
    dialog = SettingsDialog({"dropbox_sync": True})
    assert not dialog.dropbox_sync.isEnabled()
    assert not dialog.dropbox_sync.isChecked()
    assert dialog.dropbox_folder.text() == "Dropbox is not installed on this computer"
    assert dialog.values()["dropbox_sync"] is False


def test_ticking_dropbox_sync_starts_it_now_and_unticking_stops_it(
    window, connection, tmp_path, monkeypatch
):
    found = tmp_path / "Dropbox"
    found.mkdir()
    monkeypatch.setattr(dropbox, "find_dropbox", lambda: found)
    ticked = {"value": True}

    def run(dialog):
        dialog.dropbox_sync.setChecked(ticked["value"])
        return dialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", run)
    window.edit_settings()
    assert connection.written == [b";dropbox\n"]
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert saved["dropbox_sync"] is True
    window.edit_settings()  # accepted unchanged: nothing sent
    assert connection.written == [b";dropbox\n"]
    ticked["value"] = False
    window.edit_settings()
    assert connection.written == [b";dropbox\n", b";stop dropbox\n"]
