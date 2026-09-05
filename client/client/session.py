"""A detachable game session — the lich-shaped middleman.

One process logs in and owns the game socket; any number of front ends
attach and detach over a localhost TCP socket without touching the game
connection. Wire format is one JSON object per line, {"stream", "text"},
matching the (stream, text) segments XMLData.route produces; attached
clients send plain command lines back.

Run a session:   python -m client.session
Attach the GUI:  python -m client.gui.client_gui --attach

Typing `;reexec` in any front end replaces the session process with one
running the code currently on disk, handing the live game socket across —
no logout, no re-login. Front ends drop and reattach on their own.
"""

import argparse
import base64
import json
import os
import pathlib
import socket
import sys
from collections import deque
from threading import Lock, Thread
from time import monotonic, sleep

from client.client_logger import ClientLogger
from client.core import Engine, indicators_frame, room_frame, vitals_frame
from client.login import connect_game, simu_login
from client.netsock import SocketClient
from client.scripting import ScriptManager

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("REVENANT_SESSION_PORT", "4242"))

# Unparsed game bytes ride across a ;reexec in this env var (base64).
GAME_BUFFER_ENV = "REVENANT_GAME_BUFFER"

# Durable parser state rides across a ;reexec in this env var (JSON).
# The game announces indicators only when they change, so a fresh
# process can never re-learn a standing fact like DEAD on its own —
# a mid-death ;reexec left deathwatch armed but blind (#92). The
# character name is the same story: <app char=.../> arrives once, at
# login, and a reattaching title bar went nameless without it (#95).
GAME_STATE_ENV = "REVENANT_GAME_STATE"

# How long a dropped front end keeps retrying the attach — long enough to
# span a session ;reexec, short enough that a dead session is not a hang.
REATTACH_TIMEOUT = 10.0
# What the session says on the script stream just before it ends on
# purpose; a frontend that heard it treats the EOF as expected.
SESSION_ENDING = ("session: logged off", "session: game connection lost")


# The session registry: every session records {port, character, pid}
# here so the launcher's picker can offer running characters as attach
# targets beside the roster (#58). Liveness is connectability — a
# crashed session leaves a stale row that running_sessions() prunes
# (pids can't be probed safely on Windows).
SESSIONS_PATH = "~/.revenant/sessions.json"


def sessions_path():
    return pathlib.Path(os.environ.get("REVENANT_SESSIONS", SESSIONS_PATH)).expanduser()


def _load_sessions():
    try:
        with open(sessions_path()) as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _write_sessions(entries):
    path = sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries))


def register_session(port, character):
    entries = [e for e in _load_sessions() if e.get("port") != port]
    entries.append({"port": port, "character": character, "pid": os.getpid()})
    _write_sessions(entries)


def deregister_session(port):
    _write_sessions([e for e in _load_sessions() if e.get("port") != port])


def character_for_port(port):
    """The character a registered session on `port` plays, or None.

    The GUI asks before it builds its window, so the character's own
    layout can be restored before the first show — the one order Qt
    restores every saved dock state safely (#140)."""
    for entry in _load_sessions():
        try:
            if int(entry.get("port")) == int(port):
                name = entry.get("character")
                return str(name) if name else None
        except (TypeError, ValueError):
            continue
    return None


def running_sessions(host=DEFAULT_HOST):
    """Registered sessions that actually answer, pruning the rest."""
    entries = _load_sessions()
    live = []
    for entry in entries:
        try:
            with socket.create_connection((host, int(entry["port"])), timeout=0.5):
                live.append(entry)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if live != entries:
        _write_sessions(live)
    return live


def send_line(host, port, text, timeout=5):
    """Send one command line to a running session, as a frontend would.

    True when it went out, False when nothing was listening. The
    session forwards any line not starting with ";" straight to the
    game, so this is how a tool logs a character out: closing the
    client only drops the connection, and the game says so at every
    login ("Closing your front end does NOT necessarily drop your
    character from the game! Type QUIT or EXIT!"), leaving the
    character linkdead instead of gone (#114).
    """
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as conn:
            conn.sendall(text.encode("UTF-8").rstrip(b"\n") + b"\n")
        return True
    except OSError:
        return False


def close_socket(conn):
    """shutdown() then close(): on Linux, close() alone neither wakes a
    thread blocked in recv()/accept() on the socket nor sends the peer a
    FIN while one is blocked — shutdown(SHUT_RDWR) does both, portably."""
    try:
        conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        conn.close()
    except OSError:
        pass


def encode_frame(text: str, stream: str, style: str = "") -> bytes:
    return (json.dumps({"stream": stream, "text": text, "style": style}) + "\n").encode(
        "UTF-8"
    )


def decode_frames(buffer: bytes):
    """Split a byte buffer into decoded (text, stream, style) frames and
    the unconsumed tail (a partial line, if any). Frames from older
    sessions carry no style; it decodes as ""."""
    frames = []
    while b"\n" in buffer:
        raw, buffer = buffer.split(b"\n", 1)
        if raw.strip():
            payload = json.loads(raw.decode("UTF-8"))
            frames.append(
                (payload["text"], payload["stream"], payload.get("style", ""))
            )
    return frames, buffer


class SessionServer(ClientLogger):
    """Owns the game connection; relays game text to attached front ends
    and their commands back to the game."""

    def __init__(self, game_connection, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.game = game_connection
        self.host = host
        self.port = port
        self.listener = None
        self.clients = []
        self.clients_lock = Lock()
        # Recent frames, replayed to every newly attached front end so it
        # opens with scrollback instead of a blank window.
        self.backlog = deque(maxlen=500)
        # Serialize writes: script threads, client threads, and the game
        # reader all send on shared sockets.
        self.broadcast_lock = Lock()
        self.game_write_lock = Lock()
        self.running = True
        self.quit_sent = False  # a quit on its way out reclassifies EOF (#43)
        self.engine = Engine()
        self.engine.connection = game_connection

        # Script output is line-oriented; game frames carry their own
        # newlines (mid-line style runs must not be broken apart).
        def as_line(text):
            return text if text.endswith("\n") else text + "\n"

        self.scripts = ScriptManager(
            send=lambda command: self.send_to_game(
                command.encode("ASCII", "replace") + b"\n"
            ),
            emit=lambda text: self.broadcast(as_line(text), "script"),
            emit_stream=lambda text, stream: self.broadcast(as_line(text), stream),
            state=self.engine.xml_data,
        )

    def serve(self):
        self.listener = socket.create_server((self.host, self.port))
        self.bound_port = self.listener.getsockname()[1]
        # Announce this session to the launcher's picker (#58); the
        # character name comes from the spawn env (frontends learn it
        # from the "character" stream instead).
        register_session(
            self.bound_port, os.environ.get("REVENANT_CHARACTER") or "unknown"
        )
        self.log.info(f"Session listening on {self.host}:{self.bound_port}")
        Thread(target=self.game_reader, daemon=True).start()
        try:
            while self.running:
                conn, addr = self.listener.accept()
                self.log.info(f"Front end attached from {addr}")
                if not self.attach(conn):
                    continue
                Thread(target=self.client_reader, args=(conn,), daemon=True).start()
        except OSError:
            pass  # listener closed during shutdown

    def attach(self, conn):
        """Replay the backlog and current room exits, then register the
        client. Under the broadcast lock, so a concurrent frame is either
        in the replay or broadcast after registration — never dropped."""
        with self.broadcast_lock:
            replay = b"".join(self.backlog)
            if self.engine.xml_data.compass:
                replay += encode_frame(
                    " ".join(self.engine.xml_data.compass), "compass"
                )
            # The character name arrives once, at login — long attached
            # sessions have evicted that frame from the backlog, so the
            # title bar gets it stated fresh (#68).
            if self.engine.xml_data.name:
                replay += encode_frame(self.engine.xml_data.name, "character")
            # Same story for the vitals bars: idle vitals stop updating
            # and their frames age out of the backlog (#69).
            if self.engine.xml_data.vitals:
                replay += encode_frame(
                    vitals_frame(self.engine.xml_data.vitals), "vitals"
                )
            # And the status strip (#75): posture rarely changes while
            # idle, so the attach states it fresh.
            if self.engine.xml_data.indicator:
                replay += encode_frame(
                    indicators_frame(self.engine.xml_data.indicator), "indicators"
                )
            # The server-clock delta emits once and rarely again; a
            # late attacher gets it stated fresh so its Elanthian
            # clock anchors to server time immediately (#102).
            if self.engine.timesync_delta is not None:
                replay += encode_frame(f"{self.engine.timesync_delta:.1f}", "timesync")
            # The map dock follows the "room" stream; a room change is
            # rare while idle, so the attach states the position fresh
            # (#56) — same story as the compass above.
            if room := room_frame(self.engine.xml_data):
                replay += encode_frame(room, "room")
            try:
                if replay:
                    conn.sendall(replay)
            except OSError:
                close_socket(conn)
                return False
            with self.clients_lock:
                self.clients.append(conn)
        return True

    def game_reader(self):
        # Engine.read does the parsing/routing; we fan the segments out to
        # attached front ends and running scripts (goodbye included on EOF).
        while True:
            try:
                self.engine.read(output_callback=self.fanout)
            except EOFError:
                # Same EOF, two stories: after a quit it is the expected
                # end of the evening; otherwise the link died under us
                # and the player should know reconnecting is in order.
                if self.quit_sent:
                    self.broadcast("session: logged off; session ending\n", "script")
                else:
                    self.broadcast(
                        "session: game connection lost unexpectedly; session "
                        "ending — File → Reconnect starts a new one\n",
                        "script",
                    )
                self.shutdown()
                return
            except Exception:
                # A reader crash must never be a silent hang for clients.
                self.log.exception("game reader crashed; shutting down")
                self.shutdown()
                return
            sleep(0.01)

    def fanout(self, text: str, stream: str, style: str = ""):
        self.broadcast(text, stream, style)
        if style != "clear":
            self.scripts.feed(text, stream)

    # Moment-bound streams: meaningful only at the instant they fire.
    # Replaying one to a freshly attached frontend would start a stale
    # countdown, so they are never kept in the backlog.
    TRANSIENT_STREAMS = ("roundtime", "casttime", "bell")

    def broadcast(self, text: str, stream: str, style: str = "", exclude=None):
        frame = encode_frame(text, stream, style)
        with self.clients_lock:
            clients = list(self.clients)
        with self.broadcast_lock:
            if stream not in self.TRANSIENT_STREAMS:
                self.backlog.append(frame)
            for conn in clients:
                if conn is exclude:
                    continue
                try:
                    conn.sendall(frame)
                except OSError:
                    self.drop(conn)

    def send_to_game(self, data: bytes):
        if data.strip().lower() == b"quit":
            # Remembered so the coming EOF reads as a clean logoff, not
            # an unexpected drop (issue #43).
            self.quit_sent = True
        with self.game_write_lock:
            self.game.write(data)
        # Traffic-observing scripts (the surveyor) see outbound commands
        # as a synthetic "sent" stream; frontends already echo their own.
        self.scripts.feed(data.decode("ASCII", "replace").strip() + "\n", "sent")

    def client_reader(self, conn):
        buffer = b""
        while True:
            try:
                data = conn.recv(4096)
            except OSError:
                data = b""
            if not data:
                self.drop(conn)
                return
            buffer += data
            while b"\n" in buffer:
                command, buffer = buffer.split(b"\n", 1)
                command = command.strip()
                if not command:
                    continue
                try:
                    if command == b";reexec":
                        self.reexec()
                    elif command.startswith(b";"):
                        self.scripts.handle_command(command.decode("UTF-8", "replace"))
                    else:
                        self.send_to_game(command + b"\n")
                        # Every OTHER frontend sees what this one sent
                        # (dim, shell-style): a probe- or twin-window-
                        # driven command must never act invisibly. The
                        # sender echoes its own locally.
                        self.broadcast(
                            f"> {command.decode('UTF-8', 'replace')}\n",
                            "",
                            "sent",
                            exclude=conn,
                        )
                except Exception as error:
                    # One bad handler must never kill this reader thread:
                    # that leaves the frontend half-dead — receiving
                    # broadcasts while nothing it sends is ever read,
                    # with the status bar still saying Connected (#49).
                    self.log.exception("command failed: %r", command)
                    self.broadcast(
                        f"session: command {command.decode('UTF-8', 'replace')!r} "
                        f"failed: {error!r}\n",
                        "script",
                    )

    def reexec(self, execv=os.execv):
        """Replace this process with one running the code now on disk,
        handing the live game socket across — no logout, no re-login.

        Only the game fd is made inheritable; the listener and client
        sockets close at exec (front ends reattach on their own). Bytes
        already read off the wire but not yet parsed ride along in an
        env var. Parser state (room, compass) starts cold in the new
        process; main() reprimes it with a `look`. The indicators
        cannot be reprimed that way — the game states them only on
        change, and a ghost's look earns just the ghost refusal — so
        they ride across too (#92: deathwatch must see a death that
        predates it)."""
        if sys.platform == "win32":
            # WinSock handles aren't CRT fds and exec has spawn-and-exit
            # semantics — the handoff cannot work as written (#38). Bail
            # before stop_all so a doomed reexec doesn't stop scripts.
            # Detach is the wrong advice here: it leaves this process
            # running, and a relaunch reattaches to it — the old code.
            # Scripts reload from disk on every start, so ;stop + rerun
            # picks up script edits; anything else needs a new session
            # (closing the window quits the game and ends this one, #129).
            self.broadcast(
                "session: ;reexec is not supported on Windows (#129). "
                "Script edits: ;stop <name> then run it again — scripts and "
                "their helper modules reload from disk. Anything else: close "
                "the window (quit) "
                "and relaunch; Detach would reattach to this old session\n",
                "script",
            )
            return
        self.broadcast("session: re-exec'ing with current code ...", "script")
        self.scripts.stop_all()
        fd = self.game.fileno()
        os.set_inheritable(fd, True)
        argv = [
            sys.executable,
            "-m",
            "client.session",
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--game-fd",
            str(fd),
        ]
        self.log.info(f"Re-exec: {' '.join(argv)}")
        os.environ[GAME_STATE_ENV] = json.dumps(
            {
                "indicator": self.engine.xml_data.indicator,
                "name": self.engine.xml_data.name,
            }
        )
        # Snapshot the unparsed buffer as late as possible: the game
        # reader keeps draining the socket until exec replaces us.
        os.environ[GAME_BUFFER_ENV] = base64.b64encode(self.game.buffered).decode(
            "ASCII"
        )
        execv(sys.executable, argv)

    def drop(self, conn):
        with self.clients_lock:
            if conn in self.clients:
                self.clients.remove(conn)
        close_socket(conn)
        self.log.info("Front end detached")

    def shutdown(self):
        if not self.running:
            return
        self.running = False
        if getattr(self, "bound_port", None):
            deregister_session(self.bound_port)
        self.log.info("Game connection closed, shutting down session")
        # Disconnect clients before anything that could block or emit.
        with self.clients_lock:
            clients = list(self.clients)
            self.clients.clear()
        for conn in clients:
            close_socket(conn)
        if self.listener:
            close_socket(self.listener)
        self.scripts.stop_all()


class AttachedEngine(ClientLogger):
    """Engine stand-in that attaches to a running SessionServer instead of
    logging into the game. Presents the surface the GUI uses: connect(),
    connection.write(), read(output_callback), description."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.description = f"Connected (attached to {host}:{port})"
        self._connection = None
        self._buffer = b""
        # Set when the session announced its own end (logoff, lost game
        # link): the EOF that follows is expected, and reattaching to a
        # process that said goodbye would only print noise for ten
        # seconds before failing.
        self._session_ended = False
        # True while _reattach is retrying after a drop: the GUI's
        # Reconnect reads it to say what is happening (#120).
        self.reattaching = False

    @property
    def connection(self):
        return self._connection

    def connect(self):
        try:
            self._connection = SocketClient(self.host, self.port)
        except OSError as error:
            self.log.error(
                f"Could not attach to a session at {self.host}:{self.port} — "
                "is one running? Start it with: python -m client.session"
            )
            self.log.error(error)
            sys.exit(1)

    def read(self, output_callback=None):
        try:
            data = self._connection.read_very_eager()
        except EOFError:
            if self._session_ended:
                if output_callback:
                    output_callback("session ended\n", "script", "")
                self.log.info("Session ended after announcing it")
                raise
            if self._reattach(output_callback):
                return
            if output_callback:
                output_callback(
                    f"session gone — nothing answering on {self.host}:{self.port}; "
                    "File → Reconnect starts a new one\n",
                    "script",
                    "",
                )
            self.log.info("Session connection closed")
            raise
        self._buffer += data
        frames, self._buffer = decode_frames(self._buffer)
        for text, stream, style in frames:
            if stream == "script" and text.startswith(SESSION_ENDING):
                self._session_ended = True
            if output_callback:
                output_callback(text, stream, style)

    def reattach(self):
        """One fresh attach attempt against the session (the reconnect
        path): True when the connection is up again. Unlike connect(),
        failure returns False instead of exiting the process."""
        try:
            self._connection = SocketClient(self.host, self.port)
        except OSError:
            return False
        self._buffer = b""
        return True

    def _reattach(self, output_callback):
        """The session dropped us — usually a ;reexec swapping its code.
        Retry the attach briefly so a code swap doesn't end the front end."""
        if output_callback:
            output_callback(
                f"session dropped — reattaching for up to {REATTACH_TIMEOUT:.0f}s "
                "(a ;reexec looks like this) ...\n",
                "script",
                "",
            )
        self.reattaching = True
        try:
            deadline = monotonic() + REATTACH_TIMEOUT
            while monotonic() < deadline:
                if not self.reattach():
                    sleep(0.25)
                    continue
                self.log.info("Reattached to session")
                if output_callback:
                    output_callback("reattached\n", "script", "")
                return True
            return False
        finally:
            self.reattaching = False


def main(argv=None):
    argparser = argparse.ArgumentParser(
        description="Detachable DragonRealms session: logs in, owns the game "
        "connection, and relays text to attached front ends."
    )
    argparser.add_argument("--host", default=DEFAULT_HOST)
    argparser.add_argument("--port", type=int, default=DEFAULT_PORT)
    argparser.add_argument(
        "--key-stdin",
        action="store_true",
        help="read a one-shot eaccess launch key from stdin instead of "
        "performing the login handshake (the SGE launcher model)",
    )
    argparser.add_argument(
        "--game-fd",
        type=int,
        default=None,
        help="adopt an already-connected game socket by file descriptor "
        "(the ;reexec handoff) instead of logging in",
    )
    args = argparser.parse_args(argv)
    carried_state = {}
    if args.game_fd is not None:
        initial = base64.b64decode(os.environ.pop(GAME_BUFFER_ENV, ""))
        carried_state = _carried_state()
        game_connection = SocketClient.from_fd(args.game_fd, initial=initial)
        # Fresh process, cold parser: a look repopulates room/compass state.
        game_connection.write(b"look\n")
    elif args.key_stdin:
        game_connection = connect_game(sys.stdin.readline().strip())
    else:
        game_connection = simu_login()
    server = SessionServer(game_connection, args.host, args.port)
    # Primed before the autostarts: deathwatch's first poll must already
    # see a death the old process was watching (#92).
    server.engine.xml_data.indicator.update(carried_state.get("indicator") or {})
    # The login <app> tag never repeats, so the name survives the same
    # way — a reattaching title bar stays named (#95). REVENANT_CHARACTER
    # (which rides the process environment through the exec) is the
    # fallback: a name lost before the handoff existed can never ride
    # it, as the first live reexec after shipping #95 demonstrated.
    if args.game_fd is not None and not server.engine.xml_data.name:
        server.engine.xml_data.name = (
            carried_state.get("name") or os.environ.get("REVENANT_CHARACTER") or None
        )
    autostart_scripts(server)
    server.serve()


def _carried_state():
    """The parser state the old process handed across a ;reexec — {}
    when there is none (or it doesn't decode; state is a convenience,
    never worth failing the handoff over)."""
    raw = os.environ.pop(GAME_STATE_ENV, "")
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def autostart_scripts(server):
    """Scripts every session runs from the start: the xp history logger
    (so the experience database fills without anyone remembering to
    ask) and the beholder dashboard server in quiet mode (up and
    waiting, no browser). ;stop opts a session out; the Settings dialog
    (settings.json) turns them off durably, and REVENANT_NO_XP=1 /
    REVENANT_NO_BEHOLDER=1 override everything for a launch."""
    from client.settings import load_settings

    settings = load_settings()
    if not os.environ.get("REVENANT_NO_XP") and settings.get("autostart_xp", True):
        server.scripts.start("xp", [])
    if not os.environ.get("REVENANT_NO_BEHOLDER") and settings.get(
        "autostart_beholder", True
    ):
        server.scripts.start("beholder", ["quiet"])
    if not os.environ.get("REVENANT_NO_SHEET") and settings.get(
        "autostart_sheet", True
    ):
        server.scripts.start("sheet", [])
    if not os.environ.get("REVENANT_NO_DEATHWATCH") and settings.get(
        "autostart_deathwatch", True
    ):
        server.scripts.start("deathwatch", [])
    # User-chosen extras: script names with optional args ("lnet",
    # "athletics ladder"). Unknown names answer with the usual
    # no-script-named message rather than failing the startup.
    for entry in settings.get("autostart_extra", []) or []:
        parts = str(entry).split()
        if parts:
            server.scripts.start(parts[0], parts[1:])


if __name__ == "__main__":
    main()
