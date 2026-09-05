import logging
import sys
import time
from xml.etree.ElementTree import ParseError, XMLParser

from client.login import simu_login
from client.client_logger import ClientLogger
from client.xml_data import XMLData


def indicators_frame(indicator: dict) -> str:
    """The "indicators" stream's wire text: the active indicator ids,
    sorted ("IconBLEEDING IconSTANDING"); "" when none. Full state
    every time — absence means off. Shared with session.attach()."""
    return " ".join(
        sorted(name for name, visible in indicator.items() if visible == "y")
    )


def vitals_frame(vitals: dict) -> str:
    """The "vitals" stream's wire text: "health 100 stamina 95 ...",
    in the order the game first sent the bars. Shared with
    session.attach()'s replay to late attachers."""
    return " ".join(f"{vital} {value}" for vital, value in vitals.items())


def room_frame(xml_data) -> str:
    """The "room" stream's wire text: "uid<TAB>title", either half ""
    when unknown; "" when neither is known. One frame per room change
    from the engine, and stated fresh to late attachers by
    session.attach() (#56) — the map dock and the surveyor follow it."""
    uid, title = xml_data.room_uid, xml_data.room_title
    if uid is None and title is None:
        return ""
    return f"{uid if uid is not None else ''}\t{title or ''}"


class Engine(ClientLogger):
    """Parses the game stream into (text, stream, style) segments and
    synthetic state frames. Owns a connection (a SocketClient, logged in
    by connect()); read() drains it once and hands every segment to the
    output callback — the session fans those out to front ends."""

    def __init__(self):
        self._connection = None
        self.xml_data = XMLData()
        self.description = "Connected (direct)"
        # Tail of the last read that didn't end in a newline: a TCP chunk
        # can end mid-line — even mid-tag — and parsing the fragment leaks
        # broken XML into the output. Held here until its line completes.
        self._partial_line = ""
        # Last emitted room frame, for the synthetic "room" stream.
        self._last_room_frame = ""
        # Last emitted roundtime/casttime ends, for their synthetic streams.
        self._last_timer_ends = {"roundtime": 0, "casttime": 0}
        # Last emitted character name, for the synthetic "character" stream.
        self._last_character = None
        # Last emitted active-indicator set, for the "indicators"
        # stream. Starts as "" (not None) so a fresh engine doesn't
        # emit an empty frame before any indicator ever parses.
        self._last_indicators = ""
        # Last emitted server-minus-local clock delta ("timesync"
        # stream, #102); public so session.attach() can state it
        # fresh to late attachers. The delta is only meaningful at
        # the instant a fresh prompt arrives — computing it against a
        # stale prompt makes it decay one second per second, and the
        # first live rollout emitted that decay as a frame-per-second
        # flood. _last_server_time gates on prompt freshness.
        self.timesync_delta = None
        self._last_server_time = 0

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

    def read(self, output_callback=None):
        buff = []

        try:
            read_data = self.connection.read_very_eager().decode("ASCII")
        except EOFError as e:
            # No story line of its own: the session (or, in direct mode,
            # the reader's status bar) says what the close meant — one
            # event was three lines once (#152).
            self.log.info("Connection closed")
            raise (e)

        lines = (self._partial_line + read_data).split("\n")
        # The last piece is "" when the chunk ended cleanly; otherwise it
        # is an incomplete line, kept back for the next chunk.
        self._partial_line = lines.pop()

        for line in lines:
            # A blank line ("\n\n" in the chunk) has nothing to parse or route.
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
                # "uid\ttitle" frame per room change. The surveyor and
                # the GUI's map dock (#56) follow it.
                room = room_frame(self.xml_data)
                if room and room != self._last_room_frame:
                    self._last_room_frame = room
                    if output_callback:
                        output_callback(room, "room", "")
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

        # Vitals ("health 100 stamina 95 ..."): the game updates its
        # minivitals bars piecemeal; every change emits the full
        # accumulated set so frontends always hold complete state.
        if self.xml_data.vitals_updated:
            self.xml_data.vitals_updated = False
            if output_callback:
                output_callback(vitals_frame(self.xml_data.vitals), "vitals", "")

        # Indicators (posture, stunned, bleeding, dead, ...): the GUI's
        # status strip (#75). Full active set on any change.
        active = indicators_frame(self.xml_data.indicator)
        if active != self._last_indicators:
            self._last_indicators = active
            if output_callback:
                output_callback(active, "indicators", "")

        # The server states its own clock on every <prompt>; the
        # "timesync" frame carries server-minus-local seconds so
        # frontends compute server time between prompts (the Elanthian
        # clock anchors to it — local clock drift stops mattering,
        # #102). Measured ONLY at the instant a fresh prompt arrives:
        # against a stale prompt the delta just decays one second per
        # second (the first rollout emitted that decay as a frame per
        # second, flooding old frontends). Re-emitted when it moves
        # more than two seconds — beyond whole-second quantization
        # plus network jitter — so it fires effectively once per
        # session on a sane machine.
        if self.xml_data.server_time and self.xml_data.server_time != (
            self._last_server_time
        ):
            self._last_server_time = self.xml_data.server_time
            delta = self.xml_data.server_time - time.time()
            if self.timesync_delta is None or abs(delta - self.timesync_delta) > 2.0:
                self.timesync_delta = delta
                if output_callback:
                    output_callback(f"{delta:.1f}", "timesync", "")

        if not output_callback:
            sys.stdout.write("".join(buff))
            sys.stdout.flush()
