import base64
import io
import os
import socket
from threading import Thread
from time import sleep

from client import session
from client.netsock import SocketClient


def test_main_key_stdin_uses_piped_key(monkeypatch):
    connected = {}
    monkeypatch.setattr(
        session, "connect_game", lambda key: connected.setdefault("key", key)
    )
    monkeypatch.setattr(session.SessionServer, "serve", lambda self: None)
    monkeypatch.setattr(session.sys, "stdin", io.StringIO("ONE-SHOT-KEY\n"))
    session.main(["--key-stdin", "--port", "0"])
    assert connected["key"] == "ONE-SHOT-KEY"


class FakeGame:
    """Stands in for the game-side SocketClient."""

    def __init__(self):
        self.pending = []
        self.sent = []
        self.closed = False

    def read_very_eager(self):
        if self.closed:
            raise EOFError("Connection closed by remote end")
        if self.pending:
            return self.pending.pop(0)
        return b""

    def write(self, data):
        self.sent.append(data)


def _start_server(game):
    server = session.SessionServer(game, port=0)
    Thread(target=server.serve, daemon=True).start()
    for _ in range(200):
        if server.listener is not None:
            break
        sleep(0.01)
    return server, server.listener.getsockname()[1]


def _await(condition, timeout=2.0):
    for _ in range(int(timeout / 0.01)):
        if condition():
            return True
        sleep(0.01)
    return False


def test_frame_roundtrip():
    buffer = session.encode_frame("You see a troll.", "") + session.encode_frame(
        "Clear Vision", "percWindow"
    )
    frames, rest = session.decode_frames(buffer + b'{"partial')
    assert frames == [("You see a troll.", ""), ("Clear Vision", "percWindow")]
    assert rest == b'{"partial'


def test_session_relays_text_commands_and_shutdown():
    game = FakeGame()
    server, port = _start_server(game)

    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.settimeout(5)
    assert _await(lambda: server.clients), "client never registered"

    # Game text fans out to the attached client, routed by stream.
    game.pending.append(b'Hello there.\n<pushStream id="thoughts"/>psst<popStream/>\n')
    buffer = b""
    while b"psst" not in buffer:
        buffer += client.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("Hello there.", "") in frames
    assert ("psst", "thoughts") in frames

    # Client commands reach the game connection.
    client.sendall(b"look\n")
    assert _await(lambda: game.sent), "command never reached the game"
    assert game.sent == [b"look\n"]

    # Game EOF: goodbye frame is broadcast, then the session closes us.
    game.closed = True
    buffer = b""
    try:
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            buffer += chunk
    except TimeoutError:
        import threading

        raise AssertionError(
            "no close after EOF; "
            f"server.running={server.running} buffer={buffer!r} "
            f"threads={sorted(t.name for t in threading.enumerate())}"
        )
    frames, _ = session.decode_frames(buffer)
    assert any("SMELL YA LATER" in text for text, _ in frames)
    assert not server.running


def test_semicolon_commands_go_to_scripts_not_game(monkeypatch):
    game = FakeGame()
    server, port = _start_server(game)
    handled = []
    monkeypatch.setattr(server.scripts, "handle_command", handled.append)

    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    assert _await(lambda: server.clients), "client never registered"
    client.sendall(b";list\n")
    assert _await(lambda: handled), "script command never handled"
    assert handled == [";list"]
    assert game.sent == []
    client.close()


def test_reexec_marks_game_fd_inheritable_and_builds_argv(monkeypatch):
    left, right = socket.socketpair()
    game = SocketClient.from_fd(left.detach())
    right.sendall(b"line\nhalf a li")
    game.read_until(b"\n", timeout=5)  # leaves b"half a li" unconsumed
    # Set through monkeypatch so teardown restores the environment.
    monkeypatch.setenv(session.GAME_BUFFER_ENV, "sentinel")
    server = session.SessionServer(game, port=0)  # serve() never called

    calls = {}
    server.reexec(execv=lambda path, argv: calls.update(path=path, argv=argv))

    assert calls["path"] == session.sys.executable
    argv = calls["argv"]
    fd = int(argv[argv.index("--game-fd") + 1])
    assert fd == game.fileno()
    assert os.get_inheritable(fd)
    assert argv[argv.index("--port") + 1] == str(server.port)
    handed_over = base64.b64decode(os.environ[session.GAME_BUFFER_ENV])
    assert handed_over == b"half a li"
    right.close()
    game.close()


def test_reexec_command_is_session_level_not_a_script(monkeypatch):
    game = FakeGame()
    server, port = _start_server(game)
    called = []
    monkeypatch.setattr(server, "reexec", lambda: called.append(True))

    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    assert _await(lambda: server.clients), "client never registered"
    client.sendall(b";reexec\n")
    assert _await(lambda: called), ";reexec never dispatched"
    assert game.sent == []
    client.close()


def test_main_game_fd_adopts_socket_and_reprimes_with_look(monkeypatch):
    left, right = socket.socketpair()
    fd = left.detach()
    monkeypatch.setenv(
        session.GAME_BUFFER_ENV, base64.b64encode(b"carried").decode("ASCII")
    )
    adopted = {}

    def capture_serve(self):
        adopted["game"] = self.game

    monkeypatch.setattr(session.SessionServer, "serve", capture_serve)
    session.main(["--game-fd", str(fd), "--port", "0"])

    assert session.GAME_BUFFER_ENV not in os.environ  # consumed, not leaked
    right.settimeout(5)
    assert right.recv(4096) == b"look\n"  # cold parser reprimed
    right.sendall(b" more")
    game = adopted["game"]
    drained = []

    def all_bytes_arrived():
        drained.append(game.read_very_eager())
        return b"".join(drained) == b"carried more"

    assert _await(all_bytes_arrived), f"got {b''.join(drained)!r}"
    right.close()
    game.close()


def test_attached_engine_reattaches_after_session_restart():
    game = FakeGame()
    server, port = _start_server(game)
    engine = session.AttachedEngine("127.0.0.1", port)
    engine.connect()
    assert _await(lambda: server.clients), "engine never registered"

    # A ;reexec looks like this from the outside: every client dropped,
    # then a fresh session listening on the same port moments later.
    server.shutdown()
    game_after = FakeGame()
    server_after = session.SessionServer(game_after, port=port)
    Thread(target=server_after.serve, daemon=True).start()

    received = []

    def reattached():
        try:
            engine.read(
                output_callback=lambda text, stream: received.append((text, stream))
            )
        except EOFError:
            return False
        return any(text == "reattached" for text, _ in received)

    assert _await(reattached, timeout=15), f"never reattached: {received}"

    game_after.pending.append(b"Back online.\n")

    def frames_flowing():
        engine.read(
            output_callback=lambda text, stream: received.append((text, stream))
        )
        return any("Back online." in text for text, _ in received)

    assert _await(frames_flowing), "no frames after reattach"
    engine.connection.write(b"look\n")
    assert _await(lambda: game_after.sent), "command never reached new session"


def test_attached_engine_reads_frames_and_writes_commands():
    game = FakeGame()
    server, port = _start_server(game)

    engine = session.AttachedEngine("127.0.0.1", port)
    engine.connect()
    assert _await(lambda: server.clients), "engine never registered"

    game.pending.append(b"You see a stunted forest troll.\n")
    received = []

    def pump():
        engine.read(
            output_callback=lambda text, stream: received.append((text, stream))
        )
        return bool(received)

    assert _await(pump), "no frames received"
    assert ("You see a stunted forest troll.", "") in received

    engine.connection.write(b"look\n")
    assert _await(lambda: game.sent), "command never reached the game"
