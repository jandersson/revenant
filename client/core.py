import argparse
import logging
import re
from select import select
import selectors
import sys
import socket
from threading import Thread
import types
import xml.etree.ElementTree as ET
from telnetlib import Telnet

# from client.login import simu_login


def is_windows():
    return sys.platform == 'win32'


def client_accept_wrapper(sock):
    conn, addr = sock.accept()
    print(f"accept connection from {addr}")
    conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

def client_handler(key, mask):
    sock = key.fileobj
    data = key.data


class Engine:
    """Connection between game and client/s"""

    def __init__(self, connection_url, connection_port):
        self.connection_url = connection_url
        self.connection_port = connection_port
        self.connection = None
        self.selector = selectors.DefaultSelector()
        self.game_connection = Telnet()
        self.loopback_connection = None
        # TODO: Real logging
        logging.basicConfig()
        self.log = logging.getLogger()

    def start_loopback_server(self, port=10001):
        """Sets up a connection for clients"""

        loopback = ('127.0.0.1', port)
        sel = self.selector
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(loopback)
        print(f"waiting for client on {loopback}")
        sock.listen()
        sock.setblocking(False)
        sel.register(sock, selectors.EVENT_READ, data=None)

        try:
            while True:
                events = sel.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        # No client connected, listen for one
                        client_accept_wrapper(key.fileobj)
                    else:
                        client_handler(key, mask)
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, time to shut it down")
        finally:
            sel.close()

    def connect_to_game(self):
        try:
            connection = Telnet(self.connection_url, self.connection_port)
        except Exception as error:
            self.log.error('Could not establish a connection :(')
            self.log.error(error)
            sys.exit(1)
        self.connection = connection

    def disconnect(self): pass

    # def start():
    #     game_connection = self.connection
    #     sel = selectors.DefaultSelector()
        
    #     while True:
    #         events = sel.select(timeout=None)
    #         for key, mask in events:
    #             if key.data is None:


    def start_reactor(self): # Deprecated, use start() instead!
        """A very basic implementation of handling input/output"""
        connection = self.connection
        if is_windows():
            # Windows workaround for select issue
            def read_loop():
                while True:
                    self.read()

            def write_loop():
                while True:
                    self.write()

            Thread(target=read_loop).start()
            Thread(target=write_loop).start()
        else:
            while True:
                # select cannot operate on non socket objects in Windows (sys.stdin)
                fds, _, _ = select([connection.get_socket(), sys.stdin], [], [])
                for fd in fds:
                    if fd == connection.get_socket():
                        self.read()
                    if fd == sys.stdin:
                        self.write()

    def write(self):
        write_data = input()
        print(f'> {write_data}')
        self.connection.write((write_data + '\n').encode('ASCII'))

    def read(self, output_callback=None):
        read_data = self.connection.read_very_eager().decode('ASCII')
        buff = []
        for line in read_data.split('\n'):

            if line:
                if output_callback:
                    output_callback(line)
                else:
                    buff.append(line)

        if not output_callback:
            sys.stdout.write('\n'.join(buff))
            sys.stdout.flush()


def xml_handler(line):
    # Handle room xml
    # Just remove it for now
    line = re.sub('<resource picture=.+/>', '', line)
    line = re.sub('<style id=.+/>', '', line)
    if line.startswith('Obvious paths:'):
        line = re.sub('</?d>', '', line)
    if line.startswith('<compass'):
        line = re.sub('<compass>.+</compass>', '', line)
    if line.startswith('<prompt'):
        xml = re.search('<prompt.+</prompt>', line)

        def xml_prompt(_xml, _line):
            if not _xml:
                return _line
            try:
                _line = re.sub('<prompt.+</prompt>', ET.fromstring(xml.group(0)).text, _line)
            except ET.ParseError as error:
                print(f"Parse Error! {error}")
            return _line
        line = xml_prompt(xml, line)
    return line


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='A mud client')
    # TODO: Implement
    argparser.add_argument('--character-file',
                           default=None,
                           help='Login using credentials stored in this file')
    # TODO: Implement
    argparser.add_argument('--test',
                           action='store_true',
                           default=False,
                           help="Use a mock connection instead of connecting to the game")
    args = argparser.parse_args()
    engine = Engine('aardmud.org', '23')
    engine.start_loopback_server()
    # engine.connect()
    # engine.start_reactor()
