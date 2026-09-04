"""Where an LNet password comes from — the manual (#141).

LNET_PASSWORD wins for one run, the keychain is the durable place, the
legacy file is consulted last, and a missing keychain backend is a
quiet None rather than a crash.
"""

import keyring.errors

from client import lnet_login


def test_the_env_var_wins_for_one_run(monkeypatch):
    monkeypatch.setenv("LNET_PASSWORD", "from-env")
    monkeypatch.setattr(
        lnet_login.keyring, "get_password", lambda s, u: "from-keychain"
    )
    assert lnet_login.lnet_password("Lanival") == "from-env"


def test_the_keychain_is_the_durable_place(monkeypatch):
    monkeypatch.delenv("LNET_PASSWORD", raising=False)
    seen = {}

    def get_password(service, username):
        seen["key"] = (service, username)
        return "from-keychain"

    monkeypatch.setattr(lnet_login.keyring, "get_password", get_password)
    assert lnet_login.lnet_password("Lanival") == "from-keychain"
    assert seen["key"] == ("revenant-lnet", "Lanival")


def test_the_legacy_file_is_consulted_last(monkeypatch):
    monkeypatch.delenv("LNET_PASSWORD", raising=False)
    monkeypatch.setattr(lnet_login.keyring, "get_password", lambda s, u: None)
    assert lnet_login.lnet_password("Lanival", legacy_file=lambda: "from-file") == (
        "from-file"
    )
    assert lnet_login.lnet_password("Lanival", legacy_file=lambda: "") is None
    assert lnet_login.lnet_password("Lanival") is None


def test_a_missing_keyring_backend_is_not_an_error(monkeypatch):
    monkeypatch.delenv("LNET_PASSWORD", raising=False)

    def boom(service, username):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setattr(lnet_login.keyring, "get_password", boom)
    assert lnet_login.lnet_password("Lanival") is None


def test_remember_writes_the_keychain_and_reports_when_it_cannot(monkeypatch):
    stored = {}
    monkeypatch.setattr(
        lnet_login.keyring,
        "set_password",
        lambda s, u, p: stored.__setitem__((s, u), p),
    )
    assert lnet_login.remember("Lanival", "hunter2") is True
    assert stored == {("revenant-lnet", "Lanival"): "hunter2"}

    def boom(service, username, password):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setattr(lnet_login.keyring, "set_password", boom)
    assert lnet_login.remember("Lanival", "hunter2") is False


def test_identities_are_the_cached_characters_in_roster_order():
    defaults = {
        "accounts": {
            "one": {"account": "ONE", "characters": ["Lanival", "Otherchar"]},
            "two": {"account": "TWO", "characters": ["Thirdchar", "Lanival"]},
        }
    }
    assert lnet_login.identities(defaults) == ["Lanival", "Otherchar", "Thirdchar"]


def test_allowed_matches_a_roster_name_case_insensitively_or_refuses():
    defaults = {"account": "ONE", "character": "Lanival"}  # the legacy flat cache
    assert lnet_login.allowed("lanival", defaults) == "Lanival"
    assert lnet_login.allowed("Madeupname", defaults) is None


def test_no_roster_means_no_identities():
    assert lnet_login.identities({}) == []
