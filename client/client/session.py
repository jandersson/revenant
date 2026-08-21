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
import socket
import sys
from collections import deque
from threading import Lock, Thread
from time import monotonic, sleep

from client.client_logger import ClientLogger
from client.core import Engine
from client.login import connect_game, simu_login
from client.netsock import SocketClient
from client.scripting import ScriptManager

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("REVENANT_SESSION_PORT", "4242"))

# Unparsed game bytes ride across a ;reexec in this env var (base64).
GAME_BUFFER_ENV = "REVENANT_GAME_BUFFER"

# How long a dropped front end keeps retrying the attach — long enough to
# span a session ;reexec, short enough that a dead session is not a hang.
REATTACH_TIMEOUT = 10.0


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
        self.log.info(f"Session listening on {self.host}:{self.port}")
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
                    self.broadcast("session: logged off — good night\n", "script")
                else:
                    self.broadcast(
                        "session: game connection lost unexpectedly — "
                        "File → Reconnect when ready\n",
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

    def broadcast(self, text: str, stream: str, style: str = ""):
        frame = encode_frame(text, stream, style)
        with self.clients_lock:
            clients = list(self.clients)
        with self.broadcast_lock:
            self.backlog.append(frame)
            for conn in clients:
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
        process; main() reprimes it with a `look`."""
        if sys.platform == "win32":
            # WinSock handles aren't CRT fds and exec has spawn-and-exit
            # semantics — the handoff cannot work as written (#38). Bail
            # before stop_all so a doomed reexec doesn't stop scripts.
            self.broadcast(
                "session: ;reexec is not supported on Windows — "
                "File → Detach and relaunch to pick up new code\n",
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
            if self._reattach(output_callback):
                return
            if output_callback:
                output_callback(
                    "\n****************************************************\n"
                    '* I CANT BELIEVE "SMELL YA LATER" REPLACED "GOODBYE" *\n'
                    "****************************************************\n",
                    "",
                    "",
                )
            self.log.info("Session connection closed")
            raise
        self._buffer += data
        frames, self._buffer = decode_frames(self._buffer)
        for text, stream, style in frames:
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
            output_callback("session dropped — reattaching ...\n", "script", "")
        deadline = monotonic() + REATTACH_TIMEOUT
        while monotonic() < deadline:
            try:
                self._connection = SocketClient(self.host, self.port)
            except OSError:
                sleep(0.25)
                continue
            self._buffer = b""
            self.log.info("Reattached to session")
            if output_callback:
                output_callback("reattached\n", "script", "")
            return True
        return False


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
    if args.game_fd is not None:
        initial = base64.b64decode(os.environ.pop(GAME_BUFFER_ENV, ""))
        game_connection = SocketClient.from_fd(args.game_fd, initial=initial)
        # Fresh process, cold parser: a look repopulates room/compass state.
        game_connection.write(b"look\n")
    elif args.key_stdin:
        game_connection = connect_game(sys.stdin.readline().strip())
    else:
        game_connection = simu_login()
    server = SessionServer(game_connection, args.host, args.port)
    autostart_scripts(server)
    server.serve()


def autostart_scripts(server):
    """Scripts every session runs from the start: the xp history logger
    (so the experience database fills without anyone remembering to
    ask) and the beholder dashboard server in quiet mode (up and
    waiting, no browser). ;stop opts a session out; REVENANT_NO_XP=1 /
    REVENANT_NO_BEHOLDER=1 disable them entirely."""
    if not os.environ.get("REVENANT_NO_XP"):
        server.scripts.start("xp", [])
    if not os.environ.get("REVENANT_NO_BEHOLDER"):
        server.scripts.start("beholder", ["quiet"])


if __name__ == "__main__":
    main()
