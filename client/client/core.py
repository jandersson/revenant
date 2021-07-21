import argparse
import logging
from select import select
import sys
from threading import Thread
from xml.etree.ElementTree import ParseError, XMLParser

from client.login import simu_login
from client.client_logger import ClientLogger
from client.xml_data import XMLData


def is_windows():
    return sys.platform == "win32"


class Engine(ClientLogger):
    """A basic DR client"""

    def __init__(self, mode=""):
        self._connection = None
        self.xml_data = XMLData()

    @property
    def connection(self):
        return self._connection

    @connection.setter
    def connection(self, conn):
        self._connection = conn

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
        buff = []

        try:
            read_data = self.connection.read_very_eager().decode("ASCII")
        except EOFError as e:
            goodbye = """
            ******************
            *****THE END******
            ******************

            """.split(
                "\n"
            )
            if output_callback:
                output_callback(goodbye)
            else:
                buff.append(goodbye)
            self.log.info("Connection closed")
            raise (e)

        for line in read_data.split("\n"):

            # TODO: This if might be redundant
            if line:
                logging.getLogger("game").info(line)
                try:
                    XMLParser(target=self.xml_data).feed(line)
                except ParseError:
                    pass
                line = self.xml_data.strip(line)
                if not line:
                    continue
                if output_callback:
                    output_callback(line)
                else:
                    buff.append(line)

        if not output_callback:
            sys.stdout.write("\n".join(buff))
            sys.stdout.flush()


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="A mud client")
    # TODO: Implement
    argparser.add_argument(
        "--character-file",
        default=None,
        help="Login using credentials stored in this file",
    )
    # TODO: Implement
    argparser.add_argument(
        "--test",
        action="store_true",
        default=False,
        help="Use a mock connection instead of connecting to the game",
    )
    args = argparser.parse_args()
    Engine()
