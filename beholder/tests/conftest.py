"""Every beholder test reads its own settings file: Dropbox sync turned
on in the operator's real one (#548) would have the dashboard read a
merged history instead of the test's database."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.delenv("REVENANT_DROPBOX_DIR", raising=False)
