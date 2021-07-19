from abc import abstractmethod
import argparse
import logging
import re
from select import select
import sys
from threading import Thread
import xml.etree.ElementTree as ET

from client.client.login import simu_login
from client.client.client_logger import ClientLogger


def is_windows():
    return sys.platform == "win32"


class BaseReactor:
    """Handle basic IO"""

    def __init__(self, connection=None):
        self.connection = connection

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def shutdown(self):
        pass


class GUIReactor(BaseReactor):
    """Handle Input/Output for Graphical User Interface"""

    def __init__(self, connection=None):
        super().__init__(connection)
        self.threads = []

    def start(self):
        self.connect()


class TUIReactor(BaseReactor):
    """Handle Input/Output for Terminal User Interface"""

    def __init__(self, connection=None):
        super().__init__(connection)


# This is a mess. Its really hard to unravel and should be blown up once I get it into a working state.


class Engine(ClientLogger):
    """A basic DR client"""

    def __init__(self, mode=""):
        self._connection = None
        connection = self._connection
        if mode == "gui":
            self.log.debug("Using GUI Reactor")
            self.reactor = GUIReactor()
        elif mode == "tui":
            self.log.debug("Using TUI Reactor")
            self.reactor = TUIReactor()
        else:
            self.log.warning("Using base reactor")
            self.reactor = BaseReactor()

    @property
    def connection(self):
        return self._connection

    @connection.setter
    def connection(self, conn):
        self._connection = conn
        self.reactor.connection = conn

    def connect(self):
        try:
            connection = simu_login()
        except Exception as error:
            self.log.error("Could not establish a connection :(")
            self.log.error(error)
            sys.exit(1)
        self.connection = connection

    def disconnect(self):
        pass

    def reactor(self):
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
        print(f"> {write_data}")
        self.connection.write((write_data + "\n").encode("ASCII"))

    def read(self, output_callback=None):
        read_data = self.connection.read_very_eager().decode("ASCII")
        buff = []

        for line in read_data.split("\n"):

            if line:
                if output_callback:
                    output_callback(line)
                else:
                    buff.append(line)

        if not output_callback:
            sys.stdout.write("\n".join(buff))
            sys.stdout.flush()


def xml_handler(line):
    """Mostly a copy of what lich.rb does"""
    # Handle room xml
    # Just remove it for now
    line = re.sub("<resource picture=.+/>", "", line)
    line = re.sub("<style id=.+/>", "", line)
    if line.startswith("Obvious paths:"):
        line = re.sub("</?d>", "", line)
    if line.startswith("<compass"):
        line = re.sub("<compass>.+</compass>", "", line)
    if line.startswith("<prompt"):
        xml = re.search("<prompt.+</prompt>", line)

        def xml_prompt(_xml, _line):
            if not _xml:
                return _line
            try:
                _line = re.sub("<prompt.+</prompt>", ET.fromstring(xml.group(0)).text, _line)
            except ET.ParseError as error:
                print(f"Parse Error! {error}")
            return _line

        line = xml_prompt(xml, line)
    return line


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="A mud client")
    # TODO: Implement
    argparser.add_argument("--character-file", default=None, help="Login using credentials stored in this file")
    # TODO: Implement
    argparser.add_argument(
        "--test", action="store_true", default=False, help="Use a mock connection instead of connecting to the game"
    )
    args = argparser.parse_args()
    Engine()
