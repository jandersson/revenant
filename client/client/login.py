import getpass
import json
import os
import platform
import re
import struct
from pathlib import Path
from time import sleep

import keyring
import keyring.errors

from client.client_logger import ClientLogger
from client.netsock import SocketClient

GAME_CODE = b"DR"
DR_HOST = "dr.simutronics.net"
DR_PORT = 11024

module_logger = ClientLogger()

# The eaccess responses carry the operator's identity (account name, real
# name, character codes) and one-shot launch keys. Debug logs get status
# tokens and counts, never the raw responses — stdout may be captured to
# disk by whatever launched us.
_EACCESS_STATUSES = ("KEY", "PASSWORD", "NORECORD", "REJECTED")
_LAUNCH_KEY = re.compile(r"KEY=\S+")


def _response_status(response: str) -> str:
    for token in _EACCESS_STATUSES:
        if token in response:
            return token
    return "UNRECOGNIZED"


class LoginError(Exception):
    def __init__(self, message):
        super().__init__(message)


class EAccessClient(ClientLogger):
    """Handles fetching the login key from Simu"""

    def __init__(self, host="eaccess.play.net", port=7900):
        self.log.debug("Initializing EAccessClient to connect to game")
        self.host = host
        self.port = port
        self.client = SocketClient()

    def connect(self):
        self.client.open(self.host, self.port)

    def submit_login(self, credentials):
        """Inform the server of the user/pass, return what appears to be a login key?"""
        hashed_password = self.encrypt_password(
            credentials["password"], credentials["hashkey"]
        )
        self.client.write(
            b"A\t" + credentials["username"] + b"\t" + hashed_password + b"\n"
        )
        a_response = self.client.read_until(b"\n").decode()
        self.log.debug(f"a_response status: {_response_status(a_response)}")
        if "PASSWORD" in a_response:
            raise LoginError("Bad Password")
        elif "NORECORD" in a_response:
            raise LoginError("Bad Username")
        elif "REJECTED" in a_response:
            raise LoginError("Account suspended? Login Rejected")
        elif "KEY" in a_response:
            key = re.compile(".*\tKEY\t(.+)\t").match(a_response).group(1)
            return key
        else:
            raise LoginError("Something went wrong")

    def get_game_list(self):
        """Poll the server for a list of games (unused at the moment)"""
        self.client.write(rb"\M")
        game_list = self.client.read_until(b"\n")
        self.log.debug(f"game_list: {game_list}")
        return

    def get_hashkey(self):
        """Sends request for key to encrypt password with"""
        self.client.write(b"K\n")
        return self.client.read_until(b"\n")

    def submit_game(self):
        """Tell the server what game you want, server responds with game details"""
        self.client.write(b"G\t" + GAME_CODE + b"\n")
        return self.client.read_until(b"\n")

    def character_list(self):
        """Every character on the account, as an ordered {name: code} dict.

        The response is 'C', two slot counts, two zeros, then alternating
        code/name fields, all tab-separated:
        C\t16\t16\t0\t0\t<code>\t<name>\t<code>\t<name>...
        """
        self.client.write(b"C\n")
        c_response = self.client.read_until(b"\n")
        pairs = c_response.decode().strip().split("\t")[5:]
        self.log.debug(f"c_response: {len(pairs) // 2} characters (redacted)")
        return dict(zip(pairs[1::2], pairs[::2]))

    def get_character_code(self, character_name):
        """The code for the named character, from the account's list."""
        return _code_for(self.character_list(), character_name)

    def submit_character_info(self, character_code):
        """Inform server of which character to play, return the server response with connection info"""
        self.client.write(b"L\t" + character_code.encode("ASCII") + b"\t" + b"STORM\n")
        l_response = self.client.read_until(b"\n").decode()
        self.log.debug(f"l_response: {_LAUNCH_KEY.sub('KEY=<redacted>', l_response)}")
        login_key = re.compile(".+KEY=(.+)\n").match(l_response).group(1)
        self.client.close()
        return login_key

    def encrypt_password(self, password, hashkey):
        """Encrypt the password with the supplied hash from the server.

        Only as many characters as the hashkey covers can be hashed —
        the server validates no more, and official front ends truncate
        the same way. Hashing the full password instead crashed on any
        password over 32 characters (captured live 2026-08-22, #73)."""
        hashkey = list(hashkey[:32])
        password = list(password[: len(hashkey)])
        return b"".join(
            [
                struct.pack("B", ((char - 32) ^ hashkey[i]) + 32)
                for i, char in enumerate(password)
            ]
        )


KEYRING_SERVICE = "revenant"

# Where the login dialog's remember checkbox saves the account and
# character names (the password never joins them — keychain only).
LOGIN_DEFAULTS_PATH = "~/.revenant/login.json"


def login_defaults_path() -> Path:
    return Path(
        os.environ.get("REVENANT_LOGIN_DEFAULTS", LOGIN_DEFAULTS_PATH)
    ).expanduser()


def load_login_defaults() -> dict:
    """The saved account/character names, or {} when nothing is saved."""
    try:
        with open(login_defaults_path()) as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_login_defaults(account: str, character: str):
    """Remember the account and character names for future launches."""
    path = login_defaults_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"account": account, "character": character}))


def _code_for(characters: dict, character_name: str) -> str:
    for name, code in characters.items():
        if name.lower() == character_name.lower():
            return code
    raise LoginError(
        f"No character named {character_name!r} on this account. "
        f"Available: {', '.join(characters)}"
    )


# ask_character's "Other account..." choice: the caller should run the
# full login dialog with a blank account instead of using the saved one.
OTHER_ACCOUNT = object()


def account_roster(defaults: dict, account: str) -> list:
    """The cached character names for an account — the per-account cache
    under "accounts", falling back to the legacy flat "characters" list
    when it belongs to this account. Account names compare lowercased
    (the server treats them case-insensitively)."""
    key = account.lower()
    accounts = defaults.get("accounts")
    if isinstance(accounts, dict) and key in accounts:
        return list(accounts[key].get("characters") or [])
    if key and key == (defaults.get("account") or "").lower():
        return list(defaults.get("characters") or [])
    return []


def save_known_characters(names, account: str):
    """Cache an account's character roster for pickers (names only —
    codes are session-scoped and everything secret stays elsewhere).
    Rosters live per account, so switching accounts never clobbers
    another account's cache."""
    data = load_login_defaults()
    accounts = data.setdefault("accounts", {})
    accounts.setdefault(account.lower(), {})["characters"] = sorted(names)
    path = login_defaults_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def fetch_character_list(username: str, password: str, login_client=None) -> dict:
    """The account's {name: code} roster via a throwaway eaccess
    handshake; caches the names for pickers."""
    login_client = login_client or EAccessClient()
    try:
        login_client.connect()
        hashkey = login_client.get_hashkey()
        login_client.submit_login(
            {
                "username": username.encode("ASCII"),
                "password": password.encode("ASCII"),
                "hashkey": hashkey,
            }
        )
        login_client.submit_game()
        characters = login_client.character_list()
        save_known_characters(characters, username)
        return characters
    finally:
        login_client.client.close()


def keychain_password(account: str):
    """The saved password for the account, or None when the keychain has
    no entry — or no usable backend at all (headless Linux, bare CI)."""
    try:
        return keyring.get_password(KEYRING_SERVICE, account)
    except keyring.errors.KeyringError:
        module_logger.log.debug("No usable keyring backend; treating as unset")
        return None


def get_credentials():
    """Assemble login credentials without a password ever touching disk.

    Account and character come from REVENANT_ACCOUNT / REVENANT_CHARACTER,
    then the names saved by the login dialog's remember checkbox, then an
    interactive prompt. The password comes from the OS keychain, seeded by
    that same checkbox (or once with:  keyring set revenant <ACCOUNT>).
    """
    module_logger.log.debug("Fetching credentials")
    defaults = load_login_defaults()
    username = (
        os.environ.get("REVENANT_ACCOUNT")
        or defaults.get("account")
        or input("Account: ")
    )
    character = (
        os.environ.get("REVENANT_CHARACTER")
        or defaults.get("character")
        or input("Character name: ")
    )
    password = keychain_password(username)
    if password is None:
        module_logger.log.debug("No keychain entry for the account; prompting")
        password = getpass.getpass(f"Password for {username}: ")
    return {
        "username": username.encode("ASCII"),
        "password": password.encode("ASCII"),
        "character": character.capitalize(),
    }


def eaccess_protocol(login_info):
    login_client = EAccessClient()
    try:
        login_client.connect()
        login_info["hashkey"] = login_client.get_hashkey()
        login_client.submit_login(login_info)
        login_client.submit_game()
        characters = login_client.character_list()
        # Roster cache for pickers, keyed by the account logging in.
        save_known_characters(characters, login_info["username"].decode("ASCII"))
        character_code = _code_for(characters, login_info["character"])
        login_key = login_client.submit_character_info(character_code)
        return login_key
    except LoginError as e:
        module_logger.log.error(f"Had some trouble logging in: {e}")
        raise
    except Exception as e:
        module_logger.log.error(f"Had some trouble logging in: {e}")
        raise
    finally:
        login_client.client.close()
    # TODO: Persist key


def simu_login():
    log = module_logger.log
    log.debug("Starting Simu login procedure")
    # TODO: Consider handling game_connection with a context manager, if possible
    creds = get_credentials()
    key = eaccess_protocol(creds)
    return connect_game(key)


def connect_game(key):
    """Open the game connection with a one-shot eaccess launch key."""
    log = module_logger.log
    game_connection = SocketClient(DR_HOST, DR_PORT)
    log.debug("Got a game connection")
    game_connection.read_until(b"</settings>")
    game_connection.write(key.encode("ASCII") + b"\n")
    game_connection.write(
        b"/FE:STORMFRONT /VERSION:1.0.1.26 /P:"
        + platform.system().encode("ASCII")
        + b" /XML\n"
    )
    sleep(0.3)
    game_connection.write(b"<c>\n")
    sleep(0.3)
    game_connection.write(b"<c>\n")
    log.debug("simu_login finished")
    return game_connection
