import logging

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


def test_save_known_characters_caches_per_account(monkeypatch, tmp_path):
    defaults = tmp_path / "login.json"
    defaults.write_text(
        '{"account": "TESTACCT", "character": "Alpha",'
        ' "accounts": {"otheracct": {"characters": ["Zed"]}}}'
    )
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(defaults))
    login.save_known_characters(
        {"Gamma": "W_1", "Alpha": "W_2", "Beta": "W_3"}, "TESTACCT"
    )
    saved = login.load_login_defaults()
    # sorted names only, keyed by lowercased account
    assert saved["accounts"]["testacct"]["characters"] == ["Alpha", "Beta", "Gamma"]
    assert saved["accounts"]["otheracct"]["characters"] == ["Zed"]  # untouched
    assert saved["account"] == "TESTACCT"  # existing fields untouched


def test_account_roster_prefers_per_account_cache():
    defaults = {
        "account": "TESTACCT",
        "characters": ["Legacy"],
        "accounts": {"testacct": {"characters": ["Alpha", "Beta"]}},
    }
    assert login.account_roster(defaults, "TESTACCT") == ["Alpha", "Beta"]


def test_account_roster_falls_back_to_the_legacy_flat_list():
    defaults = {"account": "TESTACCT", "characters": ["Alpha", "Beta"]}
    assert login.account_roster(defaults, "testacct") == ["Alpha", "Beta"]
    assert login.account_roster(defaults, "OTHERACCT") == []
    assert login.account_roster({}, "") == []


def _recapture(caplog):
    """Undo ClientLogger's per-instance dictConfig (filed as a defect):
    it replaces root's handlers (ejecting caplog's) and, via the default
    disable_existing_loggers, disables loggers earlier tests created."""
    root = logging.getLogger()
    if caplog.handler not in root.handlers:
        root.addHandler(caplog.handler)
    logging.getLogger("client.login.EAccessClient").disabled = False


def test_submit_login_logs_status_never_account_name_or_key(caplog):
    ea = _eaccess_returning(b"A\tTESTACCT\tKEY\tsecretkey123\tTest Person\n")
    _recapture(caplog)
    with caplog.at_level(logging.DEBUG):
        key = ea.submit_login(
            {
                "username": b"TESTACCT",
                "password": b"hunter2",
                "hashkey": b"12345678" * 4,
            }
        )
    assert key == "secretkey123"
    for leaked in ("TESTACCT", "secretkey123", "Test Person"):
        assert leaked not in caplog.text
    assert "KEY" in caplog.text  # the status token still aids debugging


def test_character_list_logs_a_count_never_codes_or_names(caplog):
    ea = _eaccess_returning(C_RESPONSE)
    _recapture(caplog)
    with caplog.at_level(logging.DEBUG):
        roster = ea.character_list()
    assert list(roster) == ["Alpha", "Beta", "Gamma"]
    for leaked in ("W_TESTACCT_000", "Alpha"):
        assert leaked not in caplog.text
    assert "3 characters" in caplog.text


def test_submit_character_info_redacts_the_launch_key(caplog):
    ea = _eaccess_returning(
        b"L\tOK\tGAMEHOST=dr.simutronics.net\tGAMEPORT=11024\tKEY=sekrit123\n"
    )
    ea.client.close = lambda: None
    _recapture(caplog)
    with caplog.at_level(logging.DEBUG):
        key = ea.submit_character_info("W_TESTACCT_000")
    assert key == "sekrit123"
    assert "sekrit123" not in caplog.text
    assert "KEY=<redacted>" in caplog.text  # host/port stay visible for debugging


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
    saved = login.load_login_defaults()
    assert login.account_roster(saved, "TESTACCT") == ["Alpha", "Beta", "Gamma"]


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


def test_encrypt_password_xors_against_the_hashkey():
    ea = login.EAccessClient()
    hashed = ea.encrypt_password(b"secret", b"\x01" * 32)
    assert hashed == bytes(((char - 32) ^ 1) + 32 for char in b"secret")


def test_a_password_longer_than_the_hashkey_hashes_its_prefix():
    # Captured live 2026-08-22 (#73): a freshly reset password longer
    # than the 32-byte hashkey crashed login with IndexError. The
    # server only validates the hashed prefix, so truncate like the
    # official front ends do.
    ea = login.EAccessClient()
    long_password = b"correct-horse-battery-staple-and-then-some"
    hashed = ea.encrypt_password(long_password, b"\x02" * 32)
    assert len(hashed) == 32
    assert hashed == ea.encrypt_password(long_password[:32], b"\x02" * 32)


def test_account_for_character_searches_every_cached_roster():
    defaults = {
        "account": "TESTACCT",
        "character": "Alpha",
        "accounts": {
            "otheracct": {"account": "OTHERACCT", "characters": ["Gamma"]},
        },
    }
    # Case-insensitive, typed-case account back out.
    assert login.account_for_character(defaults, "gamma") == "OTHERACCT"
    # The legacy flat default still answers for its character.
    assert login.account_for_character(defaults, "Alpha") == "TESTACCT"
    assert login.account_for_character(defaults, "Nobody") is None


def test_save_known_characters_keeps_the_typed_account_case(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(tmp_path / "login.json"))
    login.save_known_characters({"Alpha": "c1", "Beta": "c2"}, "TESTACCT")
    defaults = login.load_login_defaults()
    assert defaults["accounts"]["testacct"]["account"] == "TESTACCT"
    assert login.account_for_character(defaults, "beta") == "TESTACCT"
