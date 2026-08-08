import socket
from threading import Thread
from time import sleep

from client import session


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
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        buffer += chunk
    frames, _ = session.decode_frames(buffer)
    assert any("THE END" in text for text, _ in frames)
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
