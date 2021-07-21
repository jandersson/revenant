"""Communicate with LNet, heavily inspired by rcuhljr's Genie LNet Plugin: https://github.com/rcuhljr/genie-lnet-plugin/
"""
import socket
import re
import xml.etree.ElementTree as ET
from typing import NamedTuple
from OpenSSL import crypto, SSL


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


class Server:
    def __init__(self, host="lnet.lichproject.org", port=7155, debug=False):
        self.host = host
        self.port = port
        self.connection = None
        self.login_info = None
        self.is_debugging = debug

    def connect(self):
        store = crypto.X509Store()
        with open("LnetCert.txt", "rt") as f:
            cert_raw = f.read()
            # Remove invisible characters that cause an exception when trying to load the certificate
            cert_cleaned = re.sub(r"[^\x00-\x7f]", r"", cert_raw).encode("utf-8")
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_cleaned)
            store.add_cert(cert=cert)
        ssl_context = SSL.Context(SSL.SSLv23_METHOD)
        connection = SSL.Connection(ssl_context, socket.socket())
        connection.connect((self.host, self.port))
        self.connection = connection

    def set_login_info(self, username, game="DR"):
        login_xml = ET.Element(
            "login",
            {
                "name": username,
                "game": game,
                "client": "1.5",
                "lich": "custom",
            },
        )
        self.login_info = ET.tostring(login_xml)

    def send_pong(self):
        pong = ET.tostring(ET.Element("pong")) + b"\n"
        if self.is_debugging:
            print(f"Sending pong: {pong}")
        self.send_message(pong)

    def send_message(self, message):
        if type(message) is str:
            message = message.encode("utf-8")
        if type(message) is bytes:
            if not message.endswith(b"\n"):
                message = message + b"\n"
        self.connection.send(message)

    def receive_message(self):
        message = self.connection.recv(2048)
        return self._message_handler(message)

    def _message_handler(self, message):
        if self.is_debugging:
            print(f"Message Received: {message}")

        message_xml = ET.fromstring(message)
        if message_xml.tag == "message":
            lnet_message = LnetMessage(
                contents=message_xml.text,
                to=message_xml.get("channel"),
                message_type=message_xml.get("type"),
                sender=message_xml.get("from"),
            )
            return lnet_message
        if message_xml.tag == "ping":
            if self.is_debugging:
                print("Ping!")
            self.send_pong()
            return
        if message_xml.tag == "greeting":
            lnet_message = LnetMessage(
                contents=message_xml.text,
                to="greeting",
                message_type=message_xml.tag,
                sender="lnet",
            )
            return lnet_message
        # We're not sure what this is, return encoded message
        return message

    def run_client(self, user_name):
        pass


def run_server():
    lnet = Server(debug=True)
    lnet.set_login_info("Wabbajack")

    lnet.connect()
    lnet.connection.send(lnet.login_info)
    while True:
        try:
            message = lnet.receive_message()
            print(message)
        except SSL.Error:
            print("Connection Lost")
            break
        except KeyboardInterrupt:
            print("User Interrupt, shutting down")
            break
    lnet.connection.shutdown()
    lnet.connection.close()


if __name__ == "__main__":
    run_server()
