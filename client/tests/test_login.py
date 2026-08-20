import pytest

from client import login

C_RESPONSE = (
    b"C\t16\t16\t0\t0"
    b"\tW_TESTACCT_000\tAlpha"
    b"\tW_TESTACCT_001\tBeta"
    b"\tW_TESTACCT_002\tGamma\n"
)


def _eaccess_returning(response):
    ea = login.EAccessClient()
    ea.client.write = lambda data: None
    ea.client.read_until = lambda expected: response
    return ea


def _eaccess_scripted(responses):
    """An EAccessClient whose socket replays canned responses in order."""
    remaining = list(responses)
    ea = login.EAccessClient()
    ea.connect = lambda: None
    ea.client.write = lambda data: None
    ea.client.read_until = lambda expected: remaining.pop(0)
    ea.client.close = lambda: None
    return ea


def test_get_character_code_handles_multidigit_counts():
    ea = _eaccess_returning(C_RESPONSE)
    assert ea.get_character_code("Beta") == "W_TESTACCT_001"


def test_get_character_code_matches_case_insensitively():
    ea = _eaccess_returning(C_RESPONSE)
    assert ea.get_character_code("gamma") == "W_TESTACCT_002"


def test_get_character_code_unknown_name_raises():
    ea = _eaccess_returning(C_RESPONSE)
    with pytest.raises(login.LoginError, match="Alpha, Beta, Gamma"):
        ea.get_character_code("Nobody")


def test_character_list_returns_every_slot():
    ea = _eaccess_returning(C_RESPONSE)
    assert list(ea.character_list()) == ["Alpha", "Beta", "Gamma"]


def test_save_known_characters_merges_into_login_defaults(monkeypatch, tmp_path):
    defaults = tmp_path / "login.json"
    defaults.write_text('{"account": "TESTACCT", "character": "Alpha"}')
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    login.save_known_characters({"Gamma": "W_1", "Alpha": "W_2", "Beta": "W_3"})
    saved = login.load_login_defaults()
    assert saved["characters"] == ["Alpha", "Beta", "Gamma"]  # sorted names only
    assert saved["account"] == "TESTACCT"  # existing fields untouched


def test_fetch_character_list_returns_roster_and_caches_names(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(tmp_path / "login.json"))
    ea = _eaccess_scripted(
        [
            b"A1B2C3D4" * 4,  # K: password hashkey
            b"A\tTESTACCT\tKEY\tsomekey\tPROBLEM=0\n",  # A: authenticated
            b"G\tDragonRealms\tPRODUCTION\n",  # G: game details
            C_RESPONSE,  # C: the roster
        ]
    )
    roster = login.fetch_character_list("TESTACCT", "hunter2", login_client=ea)
    assert roster == {
        "Alpha": "W_TESTACCT_000",
        "Beta": "W_TESTACCT_001",
        "Gamma": "W_TESTACCT_002",
    }
    assert login.load_login_defaults()["characters"] == ["Alpha", "Beta", "Gamma"]


def test_fetch_character_list_bad_password_raises_and_caches_nothing(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(tmp_path / "login.json"))
    ea = _eaccess_scripted([b"A1B2C3D4" * 4, b"A\tPASSWORD\n"])
    with pytest.raises(login.LoginError, match="Bad Password"):
        login.fetch_character_list("TESTACCT", "wrong", login_client=ea)
    assert login.load_login_defaults() == {}


def test_get_credentials_from_env_and_keyring(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setenv("REVENANT_CHARACTER", "crannach")
    monkeypatch.setattr(
        login.keyring, "get_password", lambda service, username: "hunter2"
    )
    creds = login.get_credentials()
    assert creds["username"] == b"TESTACCT"
    assert creds["password"] == b"hunter2"
    assert creds["character"] == "Crannach"


def test_get_credentials_falls_back_to_saved_names(monkeypatch, tmp_path):
    defaults = tmp_path / "login.json"
    defaults.write_text('{"account": "SAVEDACCT", "character": "savedchar"}')
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    monkeypatch.delenv("REVENANT_ACCOUNT", raising=False)
    monkeypatch.delenv("REVENANT_CHARACTER", raising=False)
    monkeypatch.setattr(
        login.keyring, "get_password", lambda service, username: "hunter2"
    )
    creds = login.get_credentials()
    assert creds["username"] == b"SAVEDACCT"
    assert creds["character"] == "Savedchar"


def test_login_defaults_roundtrip(monkeypatch, tmp_path):
    defaults = tmp_path / "deep" / "login.json"  # parent dir gets created
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    assert login.load_login_defaults() == {}
    login.save_login_defaults("TESTACCT", "Testchar")
    assert login.load_login_defaults() == {
        "account": "TESTACCT",
        "character": "Testchar",
    }


def test_get_credentials_survives_missing_keyring_backend(monkeypatch):
    import keyring.errors

    def no_backend(service, username):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setenv("REVENANT_CHARACTER", "Testchar")
    monkeypatch.setattr(login.keyring, "get_password", no_backend)
    monkeypatch.setattr(login.getpass, "getpass", lambda prompt: "fallback")
    assert login.get_credentials()["password"] == b"fallback"


def test_get_credentials_prompts_when_keychain_empty(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setenv("REVENANT_CHARACTER", "Crannach")
    monkeypatch.setattr(login.keyring, "get_password", lambda service, username: None)
    monkeypatch.setattr(login.getpass, "getpass", lambda prompt: "fromprompt")
    creds = login.get_credentials()
    assert creds["password"] == b"fromprompt"
