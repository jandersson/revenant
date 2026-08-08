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


def test_get_credentials_prompts_when_keychain_empty(monkeypatch):
    monkeypatch.setenv("REVENANT_ACCOUNT", "TESTACCT")
    monkeypatch.setenv("REVENANT_CHARACTER", "Crannach")
    monkeypatch.setattr(login.keyring, "get_password", lambda service, username: None)
    monkeypatch.setattr(login.getpass, "getpass", lambda prompt: "fromprompt")
    creds = login.get_credentials()
    assert creds["password"] == b"fromprompt"
