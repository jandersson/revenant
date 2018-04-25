"""Communicate with LNet, heavily inspired by rcuhljr's Genie LNet Plugin: https://github.com/rcuhljr/genie-lnet-plugin/"""
from typing import NamedTuple
import socket
import ssl


class LnetMessage(NamedTuple):
    contents: str
    to: str
    message_type: str


class Server:
    def __init__(self, host="lnet.lichproject.org", port=7155):
        self.host = host
        self.port = port
        self.connection = None

    def connect(self):
        ssl_context = ssl.create_default_context()
        ssl_context.load_cert_chain(certfile='LnetCert.txt')
        connection = ssl_context.wrap_socket(socket.socket(), server_hostname=self.host)
        connection.connect((self.host, self.port))
        self.connection = connection

    def validate_cert(self): pass

    def run_client(self, user_name): pass




if __name__ == '__main__':
    test_message = LnetMessage(contents='Hello World', to='DrPrime', message_type='public')
    print(test_message)
    test_server = Server()
    _socket = socket.socket()
    ssl_context = ssl.create_default_context()
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.load_default_certs()
    ssl_socket = ssl_context.wrap_socket(_socket, server_hostname='www.verisign.com')
    ssl_socket.connect(('www.verisign.com', 443))
    print(ssl.get_default_verify_paths())
    # test_server.connect()
    # cert = test_server.connection.get_peer_cert()
    # print(cert)

