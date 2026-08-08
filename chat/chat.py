"""Communicate with LNet, originally inspired by rcuhljr's Genie LNet Plugin:
https://github.com/rcuhljr/genie-lnet-plugin/

Protocol notes are derived from lnet.lic 1.15 (the reference client shipped
with Lich 5). Login is a single XML element; names can be password-protected
on the server, in which case the password travels as an attribute on that
element. Passwords are registered/changed after login with a
<data type='newpassword'> element and reset at https://lnet.lichproject.org.
"""

import base64
import os
import socket
import ssl
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple

LNET_HOST = "lnet.lichproject.org"
LNET_PORT = 7155
CERT_FILE = Path(__file__).parent / "LnetCert.txt"
PASSWORD_FILE = Path(__file__).parent / "lnet_password.txt"
# lnet.lic accepts either of these CNs instead of doing hostname verification
ALLOWED_CERT_CNS = {"lichproject.org", "LichNet"}
CLIENT_VERSION = "1.15"


class LnetMessage(NamedTuple):
    contents: str
    to: str
    message_type: str
    sender: str

    def __str__(self):
        if self.message_type == "greeting":
            return self.contents
        elif self.message_type == "channel":
            return f"[{self.to}]-{self.sender}:{self.contents}"
        elif self.message_type == "private":
            return f"[PrivateTo]-{self.sender}:{self.contents}"
        else:
            return self.contents


class LoginRejected(Exception):
    """The server refused our login (missing or incorrect password)."""


def _ruby_marshal_str(text):
    """Serialize a str the way Ruby's Marshal.dump serializes a UTF-8 String.

    The LNet server Marshal.loads the payload of <data> elements, so a pure
    Python client has to speak just enough of the format for a single string:
    version 4.8, an ivar-wrapped string ('I' '"'), then the :E => true
    encoding ivar marking it UTF-8.
    """
    raw = text.encode("utf-8")

    def marshal_long(n):
        if n == 0:
            return b"\x00"
        if n < 123:
            return bytes([n + 5])
        payload = b""
        while n > 0:
            payload += bytes([n & 0xFF])
            n >>= 8
        return bytes([len(payload)]) + payload

    return b'\x04\x08I"' + marshal_long(len(raw)) + raw + b"\x06:\x06ET"


def _ruby_pack_m(data):
    """Base64 like Ruby's Array#pack('m').strip: 60-char lines."""
    encoded = base64.b64encode(data).decode("ascii")
    return "\n".join(encoded[i : i + 60] for i in range(0, len(encoded), 60))


class Server:
    def __init__(self, host=LNET_HOST, port=LNET_PORT, debug=False):
        self.host = host
        self.port = port
        self.connection = None
        self.login_info = None
        self.is_debugging = debug
        self._parser = None
        self._depth = 0

    def connect(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(CERT_FILE))
        # The server cert's CN is not the hostname; verify the chain against
        # the pinned CA and then check the CN, the same way lnet.lic does.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED
        sock = socket.create_connection((self.host, self.port), timeout=15)
        connection = context.wrap_socket(sock, server_hostname=self.host)
        common_names = [
            value
            for rdn in connection.getpeercert()["subject"]
            for (key, value) in rdn
            if key == "commonName"
        ]
        if not any(cn in ALLOWED_CERT_CNS for cn in common_names):
            connection.close()
            raise ssl.SSLCertVerificationError(
                f"server certificate CN {common_names} is not one of {ALLOWED_CERT_CNS}"
            )
        self.connection = connection
        self._reset_parser()

    def _reset_parser(self):
        # The server writes a stream of sibling XML documents (elements can
        # span lines and lines can hold several elements), so parse them as
        # children of a synthetic never-closed root.
        self._parser = ET.XMLPullParser(events=("start", "end"))
        self._parser.feed(b"<r>")
        self._depth = 0

    def set_login_info(self, username, game="DR", password=None):
        attributes = {
            "name": username,
            "game": game,
            "client": CLIENT_VERSION,
            "lich": "custom",
        }
        if password:
            attributes["password"] = password
        self.login_info = ET.tostring(ET.Element("login", attributes))

    def login(self):
        self.send_message(self.login_info)

    def register_password(self, password):
        """Set the server-side password for the logged-in name.

        Pass the literal string "nil" to remove password protection.
        """
        element = ET.Element("data", {"type": "newpassword"})
        element.text = _ruby_pack_m(_ruby_marshal_str(password))
        self.send_message(ET.tostring(element))

    def send_pong(self):
        pong = ET.tostring(ET.Element("pong"))
        if self.is_debugging:
            print(f"Sending pong: {pong}")
        self.send_message(pong)

    def send_message(self, message):
        if type(message) is str:
            message = message.encode("utf-8")
        if not message.endswith(b"\n"):
            message = message + b"\n"
        self.connection.send(message)

    def receive_messages(self):
        """Block until at least one complete element arrives, return messages.

        Pings are answered internally and not returned.
        """
        messages = []
        while not messages:
            chunk = self.connection.recv(4096)
            if not chunk:
                raise ConnectionError("server closed the connection")
            if self.is_debugging:
                print(f"Received: {chunk}")
            try:
                self._parser.feed(chunk)
                for event, element in self._parser.read_events():
                    if event == "start":
                        self._depth += 1
                        continue
                    self._depth -= 1
                    if self._depth != 1:
                        continue
                    handled = self._message_handler(element)
                    if handled is not None:
                        messages.append(handled)
            except ET.ParseError as error:
                # expat can't recover once poisoned; start a fresh stream and
                # drop whatever fragment was in flight
                if self.is_debugging:
                    print(f"Dropping unparseable fragment: {error}")
                self._reset_parser()
        return messages

    def _message_handler(self, message_xml):
        if message_xml.tag == "message":
            message = LnetMessage(
                contents=message_xml.text,
                to=message_xml.get("channel"),
                message_type=message_xml.get("type"),
                sender=message_xml.get("from"),
            )
            if (
                message.message_type == "server"
                and message.contents
                and (
                    "password required" in message.contents
                    or "incorrect password" in message.contents
                )
            ):
                raise LoginRejected(message.contents)
            return message
        if message_xml.tag == "ping":
            if self.is_debugging:
                print("Ping!")
            self.send_pong()
            return None
        if message_xml.tag == "greeting":
            return LnetMessage(
                contents=message_xml.text,
                to="greeting",
                message_type=message_xml.tag,
                sender="lnet",
            )
        # We're not sure what this is, return the element itself
        return ET.tostring(message_xml)


def get_password():
    """LNET_PASSWORD env var, else the git-ignored chat/lnet_password.txt."""
    password = os.environ.get("LNET_PASSWORD")
    if not password and PASSWORD_FILE.exists():
        password = PASSWORD_FILE.read_text().strip()
    return password or None


def run_client():
    name = os.environ.get("LNET_NAME", "Wabbajack")
    lnet = Server(debug=bool(os.environ.get("LNET_DEBUG")))
    lnet.set_login_info(name, password=get_password())
    lnet.connect()
    lnet.login()
    while True:
        try:
            for message in lnet.receive_messages():
                print(message)
        except LoginRejected as rejection:
            print(f"Login rejected: {rejection}")
            print(
                "Set LNET_PASSWORD (or chat/lnet_password.txt) to this name's "
                "password, or reset it at https://lnet.lichproject.org"
            )
            break
        except (ssl.SSLError, ConnectionError):
            print("Connection Lost")
            break
        except KeyboardInterrupt:
            print("User Interrupt, shutting down")
            break
    lnet.connection.close()


if __name__ == "__main__":
    run_client()
