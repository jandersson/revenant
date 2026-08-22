import argparse
import logging
import time
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
        # Tail of the last read that didn't end in a newline: a TCP chunk
        # can end mid-line — even mid-tag — and parsing the fragment leaks
        # broken XML into the output. Held here until its line completes.
        self._partial_line = ""
        # Last emitted room identity, for the synthetic "room" stream.
        self._last_room_identity = (None, None)
        # Last emitted roundtime/casttime ends, for their synthetic streams.
        self._last_timer_ends = {"roundtime": 0, "casttime": 0}
        # Last emitted character name, for the synthetic "character" stream.
        self._last_character = None

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

        lines = (self._partial_line + read_data).split("\n")
        # The last piece is "" when the chunk ended cleanly; otherwise it
        # is an incomplete line, kept back for the next chunk.
        self._partial_line = lines.pop()

        for line in lines:
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
                # Room identity as a synthetic "room" stream: one
                # "uid\ttitle" frame per room change. Machine-facing —
                # the surveyor and future mappers consume it; the GUI
                # ignores it (issue #22's structured-events slice).
                identity = (
                    getattr(self.xml_data, "room_uid", None),
                    getattr(self.xml_data, "room_title", None),
                )
                if identity != self._last_room_identity and any(identity):
                    self._last_room_identity = identity
                    if output_callback:
                        uid, title = identity
                        output_callback(f"{uid or ''}\t{title or ''}", "room", "")
                # Every room sends a <compass>; emit the exits as a synthetic
                # "compass" stream. One frame per room — front ends drive
                # their widget from it, and scripts treat it as the
                # room-arrival signal (identical-exit rooms included).
                if self.xml_data.compass_updated:
                    self.xml_data.compass_updated = False
                    if output_callback:
                        output_callback(" ".join(self.xml_data.compass), "compass", "")
                # The exp window: on any change, rewrite the whole "exp"
                # stream (wipe + one line per learning skill), the same
                # pattern the game itself uses for resident windows.
                if self.xml_data.exp_updated:
                    self.xml_data.exp_updated = False
                    if output_callback:
                        output_callback("", "exp", "clear")
                        for skill in sorted(self.xml_data.experience):
                            entry = self.xml_data.experience[skill]
                            output_callback(
                                f"{skill:<18} {entry['rank']:>5} "
                                f"{entry['percent']:>3}%  {entry['rate']}\n",
                                "exp",
                                "",
                            )

        # Roundtime / casttime as synthetic streams: the game states the
        # END as server-epoch seconds ("end<TAB>server now" per frame);
        # frontends count down from end - now, skew-free. Emitted after
        # the whole burst parses, not per line — the fresh <prompt>
        # follows the <roundTime> tag in the same burst, and pairing
        # with the pre-command prompt would inflate an idle player's
        # first roundtime by the idle time.
        for timer in ("roundtime", "casttime"):
            end = getattr(self.xml_data, timer)
            if end != self._last_timer_ends[timer]:
                self._last_timer_ends[timer] = end
                if output_callback:
                    now = self.xml_data.server_time or int(time.time())
                    output_callback(f"{end}\t{now}", timer, "")

        # Who is logged in, from the game's <app char="..."/> login tag:
        # one synthetic "character" frame when it (first) parses. The
        # session also replays it to late attachers — see attach().
        if self.xml_data.name and self.xml_data.name != self._last_character:
            self._last_character = self.xml_data.name
            if output_callback:
                output_callback(self.xml_data.name, "character", "")

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
