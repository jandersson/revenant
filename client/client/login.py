import getpass
import os
import platform
import re
import struct
from time import sleep

import keyring

from client.client_logger import ClientLogger
from client.netsock import SocketClient

GAME_CODE = b"DR"
DR_HOST = "dr.simutronics.net"
DR_PORT = 11024

module_logger = ClientLogger()


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
        self.log.debug(f"a_response: {a_response}")
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

    def get_character_code(self, character_name):
        """Poll server for the character list, return the code for the named one.

        The response is 'C', two slot counts, two zeros, then alternating
        code/name fields, all tab-separated:
        C\t16\t16\t0\t0\t<code>\t<name>\t<code>\t<name>...
        """
        self.client.write(b"C\n")
        c_response = self.client.read_until(b"\n")
        self.log.debug(f"c_response: {c_response}")
        pairs = c_response.decode().strip().split("\t")[5:]
        for code, name in zip(pairs[::2], pairs[1::2]):
            if name.lower() == character_name.lower():
                self.log.debug(f"character_code: {code}")
                return code
        raise LoginError(
            f"No character named {character_name!r} on this account. "
            f"Available: {', '.join(pairs[1::2])}"
        )

    def submit_character_info(self, character_code):
        """Inform server of which character to play, return the server response with connection info"""
        self.client.write(b"L\t" + character_code.encode("ASCII") + b"\t" + b"STORM\n")
        l_response = self.client.read_until(b"\n").decode()
        self.log.debug(f"l_response: {l_response}")
        login_key = re.compile(".+KEY=(.+)\n").match(l_response).group(1)
        self.client.close()
        return login_key

    def encrypt_password(self, password, hashkey):
        """Encrypt the password with the supplied hash from the server"""
        password = list(password)
        hashkey = list(hashkey[:32])
        return b"".join(
            [
                struct.pack("B", ((char - 32) ^ hashkey[i]) + 32)
                for i, char in enumerate(password)
            ]
        )


KEYRING_SERVICE = "revenant"


def get_credentials():
    """Assemble login credentials without a password ever touching disk.

    Account and character come from REVENANT_ACCOUNT / REVENANT_CHARACTER
    (with an interactive prompt as fallback). The password comes from the
    OS keychain, seeded once with:  keyring set revenant <ACCOUNT>
    """
    module_logger.log.debug("Fetching credentials")
    username = os.environ.get("REVENANT_ACCOUNT") or input("Account: ")
    character = os.environ.get("REVENANT_CHARACTER") or input("Character name: ")
    password = keyring.get_password(KEYRING_SERVICE, username)
    if password is None:
        module_logger.log.debug("No keychain entry for %s; prompting", username)
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
        character_code = login_client.get_character_code(login_info["character"])
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
