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
        self.description = "Connected (direct)"

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
            goodbye = "\n******************\n* SMELL YA LATER *\n******************\n"
            if output_callback:
                output_callback(goodbye, "", "")
            else:
                buff.append(goodbye)
            self.log.info("Connection closed")
            raise (e)

        for line in read_data.split("\n"):
            # TODO: This if might be redundant
            if line:
                logging.getLogger("game").info(line)
                try:
                    # Wrap in a synthetic root so multiple top-level
                    # self-closing tags on one line (e.g. successive
                    # <indicator .../> elements) all get walked. Without
                    # this, expat raises ParseError after the first tag
                    # and everything else on the line is silently lost.
                    XMLParser(target=self.xml_data).feed(f"<r>{line}</r>")
                except ParseError:
                    pass
                segments = self.xml_data.route(line)
                # One line can hold several styled pieces; the last piece
                # per stream carries the newline so front ends never have
                # to guess where lines end. Control frames carry none.
                final_piece = {}
                for index, (stream, text, style) in enumerate(segments):
                    if style != "clear":
                        final_piece[stream] = index
                for index, (stream, text, style) in enumerate(segments):
                    if index == final_piece.get(stream):
                        text += "\n"
                    if output_callback:
                        output_callback(text, stream, style)
                    elif style != "clear":
                        buff.append(text if not stream else f"[{stream}] {text}")
                # Every room sends a <compass>; emit the exits as a synthetic
                # "compass" stream. One frame per room — front ends drive
                # their widget from it, and scripts treat it as the
                # room-arrival signal (identical-exit rooms included).
                if self.xml_data.compass_updated:
                    self.xml_data.compass_updated = False
                    if output_callback:
                        output_callback(" ".join(self.xml_data.compass), "compass", "")

        if not output_callback:
            sys.stdout.write("".join(buff))
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
