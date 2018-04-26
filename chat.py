"""Communicate with LNet, heavily inspired by rcuhljr's Genie LNet Plugin: https://github.com/rcuhljr/genie-lnet-plugin/"""
import socket
import re
import xml.etree.ElementTree as ET
from typing import NamedTuple
from OpenSSL import crypto, SSL


class LnetMessage(NamedTuple):
    contents: str
    to: str
    message_type: str


class Server:
    def __init__(self, host="lnet.lichproject.org", port=7155):
        self.host = host
        self.port = port
        self.connection = None
        self.login_info = None

    def connect(self):
        store = crypto.X509Store()
        with open('LnetCert.txt', 'rt') as f:
            cert_raw = f.read()
            cert_cleaned = re.sub(r'[^\x00-\x7f]', r'', cert_raw).encode('utf-8')
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_cleaned)
            store.add_cert(cert=cert)
        ssl_context = SSL.Context(SSL.SSLv23_METHOD)
        connection = SSL.Connection(ssl_context, socket.socket())
        connection.connect((self.host, self.port))
        self.connection = connection

    def set_login_info(self, username, game='DR'):
        login_xml = ET.Element('login', {
            'name': username,
            'game': game,
            'client': '1.5',
            'lich': 'custom',
        })
        self.login_info = ET.tostring(login_xml)

    def validate_cert(self): pass

    def run_client(self, user_name): pass




if __name__ == '__main__':
    test_server = Server()

    test_server.set_login_info('Wabbajack')
    # login_str = ET.dump(test_server.login_info)
    # print(test_server.login_info)
    test_server.connect()
    test_server.connection.send(test_server.login_info)
    while True:
        try:
            print(test_server.connection.recv(1024))
        except SSL.Error:
            print("The connection is dead")
            break
    test_server.connection.shutdown()
    test_server.connection.close()
