import base64
import io
import json
import os
import socket
import sys
import types
from threading import Thread
from time import sleep

import pytest

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
    assert frames == [
        ("You see a troll.", "", ""),
        ("Clear Vision", "percWindow", ""),
    ]
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
    assert ("Hello there.\n", "", "") in frames
    assert ("psst\n", "thoughts", "") in frames

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
    assert any("connection closed by the game" in text for text, _, _ in frames)
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


def test_sessions_register_for_the_launcher_and_prune_stale_rows(monkeypatch):
    # The launcher's picker reads ~/.revenant/sessions.json (#58):
    # serving registers {port, character, pid}; a shutdown removes the
    # row; a crash leaves one that running_sessions() prunes because
    # nothing answers on its port.
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    game = FakeGame()
    server, port = _start_server(game)
    assert _await(lambda: session.running_sessions()), "session never registered"
    (entry,) = session.running_sessions()
    assert (entry["port"], entry["character"]) == (port, "Lanival")

    # A bound-but-not-listening socket: the stale row's port refuses.
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    session.register_session(holder.getsockname()[1], "Ghost")
    assert [e["character"] for e in session.running_sessions()] == ["Lanival"]
    holder.close()

    game.closed = True  # the game EOF shuts the session down
    assert _await(lambda: not session.running_sessions()), "never deregistered"


def test_new_front_end_receives_recent_backlog_on_attach():
    # Attaching to a running session shows what already happened —
    # scrollback and compass state — not a blank window.
    game = FakeGame()
    server, port = _start_server(game)
    game.pending.append(
        b'<compass><dir value="n"/><dir value="e"/></compass>'
        b"An eerie howl rises in the distance.\n"
    )
    assert _await(lambda: server.backlog), "backlog never filled"

    late_client = socket.create_connection(("127.0.0.1", port), timeout=5)
    late_client.settimeout(5)
    buffer = b""
    while b"compass" not in buffer:
        buffer += late_client.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("An eerie howl rises in the distance.\n", "", "") in frames
    assert ("n e", "compass", "") in frames  # compass replayed for the dock
    late_client.close()


def test_late_attach_learns_the_character_despite_an_evicted_backlog():
    # The <app> login tag fires once; after hours of play its frame is
    # long gone from the 500-frame backlog. attach() states the name
    # fresh, like it does the compass, so the title bar fills in (#68).
    game = FakeGame()
    server, port = _start_server(game)
    game.pending.append(
        b'<app char="Lanival" game="DR" title="[DR: Lanival] Wrayth"/>\n'
    )
    assert _await(lambda: server.engine.xml_data.name == "Lanival"), (
        "app tag never parsed"
    )
    server.backlog.clear()  # simulate the eviction

    late = socket.create_connection(("127.0.0.1", port), timeout=5)
    late.settimeout(5)
    buffer = b""
    while b"character" not in buffer:
        buffer += late.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("Lanival", "character", "") in frames
    late.close()


def test_late_attach_learns_the_vitals_despite_an_evicted_backlog():
    # Idle vitals stop updating; their frames age out of the backlog.
    # attach() replays the current set so the bars fill in (#69).
    game = FakeGame()
    server, port = _start_server(game)
    game.pending.append(
        b"<dialogData id='minivitals'><progressBar id='health'"
        b" value='100' text='health 100%'/></dialogData>\n"
    )
    assert _await(lambda: server.engine.xml_data.vitals), "vitals never parsed"
    server.backlog.clear()  # simulate the eviction

    late = socket.create_connection(("127.0.0.1", port), timeout=5)
    late.settimeout(5)
    buffer = b""
    while b"vitals" not in buffer:
        buffer += late.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("health 100", "vitals", "") in frames
    late.close()


def test_late_attach_learns_the_room():
    # The map dock follows the "room" stream; standing still, the room
    # frame ages out of the backlog. attach() states the position fresh
    # (#56), like the compass and vitals.
    game = FakeGame()
    server, port = _start_server(game)
    game.pending.append(
        b'<style id="roomName"/>[Northwall Trail, Grassland] <style id=""/>'
        b"<nav rm='10081'/>\n"
    )
    assert _await(lambda: server.engine.xml_data.room_uid == 10081), (
        "nav uid never parsed"
    )
    server.backlog.clear()  # simulate the eviction

    late = socket.create_connection(("127.0.0.1", port), timeout=5)
    late.settimeout(5)
    buffer = b""
    while b'"room"' not in buffer:
        buffer += late.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("10081\t[Northwall Trail, Grassland]", "room", "") in frames
    late.close()


def test_transient_streams_broadcast_live_but_never_replay():
    # A roundtime frame is meaningful only at its instant: live
    # frontends get it, but one attaching later must not have it
    # replayed and start a stale countdown (#63).
    game = FakeGame()
    server, port = _start_server(game)

    live = socket.create_connection(("127.0.0.1", port), timeout=5)
    assert _await(lambda: server.clients), "client never registered"
    game.pending.append(
        b"<roundTime value='1787402555'/>You scan the heavens "
        b"for the three moons:\n"
        b'<prompt time="1787402545">&gt;</prompt>\n'
    )
    live.settimeout(5)
    buffer = b""
    while b"roundtime" not in buffer:
        buffer += live.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("1787402555\t1787402545", "roundtime", "") in frames
    # The game text made the backlog; the roundtime frame never does.
    assert any(b"heavens" in frame for frame in server.backlog)
    assert not any(b"roundtime" in frame for frame in server.backlog)
    live.close()


def test_script_emit_stream_reaches_attached_clients():
    game = FakeGame()
    server, port = _start_server(game)
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.settimeout(5)
    assert _await(lambda: server.clients), "client never registered"

    # The ;lnet mirror path: a script emits onto the thoughts stream.
    server.scripts.emit_stream("[LNet General] Someone: hi", "thoughts")
    buffer = b""
    while b"Someone" not in buffer:
        buffer += client.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("[LNet General] Someone: hi\n", "thoughts", "") in frames
    client.close()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=";reexec is POSIX-only and gated off on Windows (#38)",
)
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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=";reexec is POSIX-only and gated off on Windows (#38)",
)
def test_reexec_hands_the_indicators_across(monkeypatch):
    # The game states an indicator only when it changes, so a fresh
    # process can never re-learn DEAD on its own: a mid-death ;reexec
    # left deathwatch armed but blind (#92). The indicator dict rides
    # the exec in an env var.
    left, right = socket.socketpair()
    game = SocketClient.from_fd(left.detach())
    # Set through monkeypatch so teardown restores the environment.
    monkeypatch.setenv(session.GAME_STATE_ENV, "sentinel")
    monkeypatch.setenv(session.GAME_BUFFER_ENV, "sentinel")
    server = session.SessionServer(game, port=0)  # serve() never called
    server.engine.xml_data.indicator.update({"IconDEAD": "y", "IconPRONE": "y"})
    server.engine.xml_data.name = "Lanival"  # <app> never repeats (#95)

    server.reexec(execv=lambda path, argv: None)

    handed_over = json.loads(os.environ[session.GAME_STATE_ENV])
    assert handed_over["indicator"] == {"IconDEAD": "y", "IconPRONE": "y"}
    assert handed_over["name"] == "Lanival"
    right.close()
    game.close()


def test_main_game_fd_primes_the_indicators_from_the_handoff(monkeypatch):
    left, right = socket.socketpair()
    fd = left.detach()
    monkeypatch.setenv(
        session.GAME_STATE_ENV,
        json.dumps({"indicator": {"IconDEAD": "y"}, "name": "Lanival"}),
    )
    adopted = {}
    monkeypatch.setattr(
        session.SessionServer, "serve", lambda self: adopted.update(server=self)
    )
    # The autostarts are where the primed state matters (deathwatch's
    # first poll), but they are exercised in their own tests.
    monkeypatch.setattr(session, "autostart_scripts", lambda server: None)
    session.main(["--game-fd", str(fd), "--port", "0"])

    assert session.GAME_STATE_ENV not in os.environ  # consumed, not leaked
    xml_data = adopted["server"].engine.xml_data
    assert xml_data.indicator["IconDEAD"] == "y"
    assert xml_data.name == "Lanival"  # the title bar stays named (#95)
    right.close()
    adopted["server"].game.close()


def test_main_game_fd_names_the_character_from_the_environment(monkeypatch):
    # A name lost before the #95 handoff existed can never ride it —
    # the first live reexec after shipping proved it. REVENANT_CHARACTER
    # rides the exec's environment and fills the gap.
    left, right = socket.socketpair()
    fd = left.detach()
    monkeypatch.setenv(session.GAME_STATE_ENV, json.dumps({"indicator": {}}))
    monkeypatch.setenv("REVENANT_CHARACTER", "Lanival")
    adopted = {}
    monkeypatch.setattr(
        session.SessionServer, "serve", lambda self: adopted.update(server=self)
    )
    monkeypatch.setattr(session, "autostart_scripts", lambda server: None)
    session.main(["--game-fd", str(fd), "--port", "0"])

    assert adopted["server"].engine.xml_data.name == "Lanival"
    right.close()
    adopted["server"].game.close()


def test_carried_state_swallows_a_corrupt_handoff(monkeypatch):
    monkeypatch.setenv(session.GAME_STATE_ENV, "not json {")
    assert session._carried_state() == {}
    monkeypatch.setenv(session.GAME_STATE_ENV, '["a list, not a dict"]')
    assert session._carried_state() == {}
    assert session.GAME_STATE_ENV not in os.environ


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
    # Autostarts are not under test, and the sheet script would write
    # its INFO probe into the adopted socket this test is asserting on.
    monkeypatch.setattr(session, "autostart_scripts", lambda server: None)
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
                output_callback=lambda text, stream, style: received.append(
                    (text, stream)
                )
            )
        except EOFError:
            return False
        return any(text == "reattached\n" for text, _ in received)

    assert _await(reattached, timeout=15), f"never reattached: {received}"

    game_after.pending.append(b"Back online.\n")

    def frames_flowing():
        engine.read(
            output_callback=lambda text, stream, style: received.append((text, stream))
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
            output_callback=lambda text, stream, style: received.append((text, stream))
        )
        return bool(received)

    assert _await(pump), "no frames received"
    assert ("You see a stunted forest troll.\n", "") in received

    engine.connection.write(b"look\n")
    assert _await(lambda: game.sent), "command never reached the game"


def test_reattach_connects_when_a_session_is_listening():
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]
    engine = session.AttachedEngine("127.0.0.1", port)
    assert engine.reattach() is True
    conn, _ = server.accept()  # a fresh connection actually arrived
    session.close_socket(conn)
    server.close()
    session.close_socket(engine.connection.get_socket())


def test_reattach_returns_false_without_a_session():
    # Hold the port bound but not listening: connects are refused, and the
    # port cannot be reassigned mid-test (hermeticity per CLAUDE.md).
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    port = blocker.getsockname()[1]
    engine = session.AttachedEngine("127.0.0.1", port)
    assert engine.reattach() is False
    assert engine.connection is None
    blocker.close()


def _autostart_with(monkeypatch, settings=None, **env):
    monkeypatch.delenv("REVENANT_NO_XP", raising=False)
    monkeypatch.delenv("REVENANT_NO_BEHOLDER", raising=False)
    monkeypatch.delenv("REVENANT_NO_SHEET", raising=False)
    monkeypatch.delenv("REVENANT_NO_DEATHWATCH", raising=False)
    import json
    import tempfile
    from pathlib import Path

    directory = Path(tempfile.mkdtemp())
    (directory / "settings.json").write_text(json.dumps(settings or {}))
    monkeypatch.setenv("REVENANT_SETTINGS", str(directory / "settings.json"))
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    started = []
    server = types.SimpleNamespace(
        scripts=types.SimpleNamespace(
            start=lambda name, args: started.append((name, args))
        )
    )
    session.autostart_scripts(server)
    return started


def test_sessions_autostart_xp_and_the_quiet_dashboard(monkeypatch):
    assert _autostart_with(monkeypatch) == [
        ("xp", []),
        ("beholder", ["quiet"]),
        ("sheet", []),
        ("deathwatch", []),
    ]


def test_env_flags_disable_each_autostart(monkeypatch):
    assert _autostart_with(
        monkeypatch,
        REVENANT_NO_XP="1",
        REVENANT_NO_SHEET="1",
        REVENANT_NO_DEATHWATCH="1",
    ) == [("beholder", ["quiet"])]
    assert _autostart_with(
        monkeypatch,
        REVENANT_NO_BEHOLDER="1",
        REVENANT_NO_SHEET="1",
        REVENANT_NO_DEATHWATCH="1",
    ) == [("xp", [])]
    assert _autostart_with(
        monkeypatch,
        REVENANT_NO_XP="1",
        REVENANT_NO_BEHOLDER="1",
        REVENANT_NO_DEATHWATCH="1",
    ) == [("sheet", [])]
    assert _autostart_with(
        monkeypatch,
        REVENANT_NO_XP="1",
        REVENANT_NO_BEHOLDER="1",
        REVENANT_NO_SHEET="1",
    ) == [("deathwatch", [])]
    assert (
        _autostart_with(
            monkeypatch,
            REVENANT_NO_XP="1",
            REVENANT_NO_BEHOLDER="1",
            REVENANT_NO_SHEET="1",
            REVENANT_NO_DEATHWATCH="1",
        )
        == []
    )


def test_a_crashing_command_does_not_kill_client_reader(monkeypatch):
    game = FakeGame()
    server, port = _start_server(game)

    def explode():
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "reexec", explode)
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.settimeout(5)
    assert _await(lambda: server.clients), "client never registered"

    client.sendall(b";reexec\n")  # handler raises
    client.sendall(b"look\n")  # the reader must still be alive for this
    assert _await(lambda: game.sent), "reader died: command never reached game"
    assert game.sent == [b"look\n"]

    # The failure was reported to the frontend, not swallowed.
    buffer = b""
    while b"failed" not in buffer:
        buffer += client.recv(4096)
    client.close()


def test_reexec_is_gated_off_on_windows(monkeypatch):
    monkeypatch.setattr(session.sys, "platform", "win32")
    server = session.SessionServer(FakeGame(), port=0)  # serve() never called
    stopped = []
    monkeypatch.setattr(server.scripts, "stop_all", lambda: stopped.append(True))
    broadcasts = []
    monkeypatch.setattr(
        server, "broadcast", lambda text, stream="", style="": broadcasts.append(text)
    )
    server.reexec(execv=lambda path, argv: (_ for _ in ()).throw(AssertionError))
    assert stopped == []  # a doomed reexec must not stop running scripts
    note = next(text for text in broadcasts if "not supported on Windows" in text)
    # Detach keeps this process alive, and a relaunch reattaches to it —
    # the note must steer to what actually loads new code.
    assert ";stop <name>" in note and "close the window" in note
    assert "helper modules reload" in note  # #138: the walker fix needs no relaunch
    assert "Detach and relaunch" not in note


def test_eof_without_quit_reads_as_an_unexpected_drop():
    game = FakeGame()
    server, port = _start_server(game)
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.settimeout(5)
    assert _await(lambda: server.clients), "client never registered"

    game.closed = True  # the server dropped us; nobody sent quit
    buffer = b""
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        buffer += chunk
    frames, _ = session.decode_frames(buffer)
    assert any("lost unexpectedly" in text for text, _, _ in frames)
    assert not any("logged off" in text for text, _, _ in frames)


def test_eof_after_quit_reads_as_a_clean_logoff():
    game = FakeGame()
    server, port = _start_server(game)
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.settimeout(5)
    assert _await(lambda: server.clients), "client never registered"

    client.sendall(b"quit\n")
    assert _await(lambda: game.sent), "quit never reached the game"
    game.closed = True  # the logoff closes the connection
    buffer = b""
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        buffer += chunk
    frames, _ = session.decode_frames(buffer)
    assert any("logged off" in text for text, _, _ in frames)
    assert not any("lost unexpectedly" in text for text, _, _ in frames)


def test_settings_file_disables_autostarts_durably(monkeypatch):
    off = {"autostart_sheet": False, "autostart_deathwatch": False}
    assert _autostart_with(monkeypatch, settings={"autostart_xp": False, **off}) == [
        ("beholder", ["quiet"])
    ]
    assert _autostart_with(
        monkeypatch, settings={"autostart_beholder": False, **off}
    ) == [("xp", [])]
    assert _autostart_with(
        monkeypatch,
        settings={
            "autostart_xp": False,
            "autostart_beholder": False,
            "autostart_sheet": False,
        },
    ) == [("deathwatch", [])]
    # Env vars still beat the file for a single launch.
    assert (
        _autostart_with(
            monkeypatch,
            settings={"autostart_xp": True, "autostart_beholder": True},
            REVENANT_NO_XP="1",
            REVENANT_NO_BEHOLDER="1",
            REVENANT_NO_SHEET="1",
            REVENANT_NO_DEATHWATCH="1",
        )
        == []
    )


def test_autostart_extra_starts_user_chosen_scripts(monkeypatch):
    started = _autostart_with(
        monkeypatch,
        settings={"autostart_extra": ["lnet", "athletics ladder", "", 42]},
    )
    assert ("lnet", []) in started
    assert ("athletics", ["ladder"]) in started
    # Blank entries vanish; junk becomes a name the manager will answer
    # with its usual no-script-named message rather than crash startup.
    assert ("42", []) in started


def test_late_attach_learns_the_indicators(monkeypatch):
    # Posture rarely changes while idle; attach states the strip fresh
    # (#75), like the compass and vitals.
    game = FakeGame()
    server, port = _start_server(game)
    game.pending.append(
        b'<indicator id="IconSTANDING" visible="y"/>'
        b"<indicator id='IconBLEEDING' visible='y'/>\n"
    )
    assert _await(lambda: server.engine.xml_data.indicator), "never parsed"
    server.backlog.clear()

    late = socket.create_connection(("127.0.0.1", port), timeout=5)
    late.settimeout(5)
    buffer = b""
    while b"indicators" not in buffer:
        buffer += late.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("IconBLEEDING IconSTANDING", "indicators", "") in frames
    late.close()


def test_sent_commands_reach_the_other_frontends():
    # A command from one frontend (a probe, a twin window) is echoed
    # to every other frontend, dim — driven characters must never act
    # invisibly. The sender echoes its own locally instead.
    game = FakeGame()
    server, port = _start_server(game)
    driver = socket.create_connection(("127.0.0.1", port), timeout=5)
    watcher = socket.create_connection(("127.0.0.1", port), timeout=5)
    watcher.settimeout(5)
    assert _await(lambda: len(server.clients) == 2), "clients never registered"

    driver.settimeout(1)
    driver.sendall(b"look\n")
    buffer = b""
    while b"sent" not in buffer:
        buffer += watcher.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("> look\n", "", "sent") in frames
    # The origin connection gets no echo back (it echoes locally).
    try:
        data = driver.recv(4096)
    except TimeoutError:
        data = b""
    assert b"> look" not in data
    driver.close()
    watcher.close()


def test_attach_states_the_server_clock_delta_fresh():
    # The timesync frame emits once per session and ages out of the
    # backlog; a late attacher gets it stated fresh so its Elanthian
    # clock anchors to server time immediately (#102).
    game = FakeGame()
    server, port = _start_server(game)
    server.engine.timesync_delta = 42.0

    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.settimeout(5)
    buffer = b""
    while b"timesync" not in buffer:
        buffer += client.recv(4096)
    frames, _ = session.decode_frames(buffer)
    assert ("42.0", "timesync", "") in frames
    client.close()


# --- send_line: logging a character out, not just dropping it (#114) ---


def test_send_line_delivers_one_terminated_line():
    # A tool logs a character out by writing to the session the way a
    # frontend would; the session forwards any non-";" line to the game.
    received = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve():
        conn, _ = listener.accept()
        with conn:
            received.append(conn.recv(4096))

    thread = Thread(target=serve, daemon=True)
    thread.start()
    assert session.send_line("127.0.0.1", port, "quit") is True
    thread.join(timeout=5)
    listener.close()
    assert received == [b"quit\n"]


def test_send_line_does_not_double_the_newline():
    received = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve():
        conn, _ = listener.accept()
        with conn:
            received.append(conn.recv(4096))

    thread = Thread(target=serve, daemon=True)
    thread.start()
    assert session.send_line("127.0.0.1", port, "quit\n") is True
    thread.join(timeout=5)
    listener.close()
    assert received == [b"quit\n"]


def test_send_line_reports_failure_when_nothing_listens():
    # A session that already died must not raise — the sweep's kill is
    # the backstop, and a broken character may never answer at all.
    held = socket.socket()  # bound, never listening: the port stays shut
    held.bind(("127.0.0.1", 0))
    port = held.getsockname()[1]
    assert session.send_line("127.0.0.1", port, "quit", timeout=1) is False
    held.close()


def test_a_bell_is_never_replayed_to_a_late_attacher():
    # A bell is moment-bound like a roundtime: sounding an hour-old idle
    # warning at whoever attaches next would be a lie (#131).
    game = FakeGame()
    server, port = _start_server(game)
    game.pending.append(b"\x07YOU HAVE BEEN IDLE TOO LONG. PLEASE RESPOND.\x07\n")
    assert _await(lambda: server.backlog), "backlog never filled"
    frames, _ = session.decode_frames(b"".join(server.backlog))
    streams = [stream for _, stream, _ in frames]
    assert "" in streams  # the warning text itself is scrollback
    assert "bell" not in streams


def test_character_for_port_reads_the_registry(monkeypatch, tmp_path):
    # The GUI asks before building its window, so the character's own
    # layout restores before the first show (#140).
    registry = tmp_path / "sessions.json"
    registry.write_text(
        json.dumps(
            [
                {"port": 4242, "character": "Lanival", "pid": 1},
                {"port": "4243", "character": "Other", "pid": 2},
                {"port": "bogus", "character": "Nobody"},
            ]
        )
    )
    monkeypatch.setenv("REVENANT_SESSIONS", str(registry))
    assert session.character_for_port(4242) == "Lanival"
    assert session.character_for_port("4243") == "Other"
    assert session.character_for_port(5000) is None


def test_character_for_port_is_none_without_a_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SESSIONS", str(tmp_path / "missing.json"))
    assert session.character_for_port(4242) is None


# --- what a frontend says when the session ends ---


class _FramesThenEOF:
    """A session connection that serves canned frames, then hangs up."""

    def __init__(self, frames):
        self.chunks = [
            session.encode_frame(text, stream, style) for text, stream, style in frames
        ]

    def read_very_eager(self):
        if self.chunks:
            return self.chunks.pop(0)
        raise EOFError


def _attached_with(frames, monkeypatch):
    engine = session.AttachedEngine("127.0.0.1", 1)
    engine._connection = _FramesThenEOF(frames)
    monkeypatch.setattr(engine, "reattach", lambda: False)
    monkeypatch.setattr(session, "REATTACH_TIMEOUT", 0.0)
    return engine


def _drain(engine):
    out = []
    try:
        while True:
            engine.read(output_callback=lambda text, stream, style: out.append(text))
    except EOFError:
        pass
    return out


def test_an_announced_logoff_ends_plainly_without_a_reattach(monkeypatch):
    # After quit the session says it is logging off; the EOF that follows
    # is the expected end, not a drop to chase for ten seconds.
    out = _drain(
        _attached_with(
            [("session: logged off; session ending\n", "script", "")], monkeypatch
        )
    )
    assert out[-1] == "session ended\n"
    assert not any("reattaching" in text for text in out)
    assert not any("*" in text for text in out)  # no banners


def test_an_unannounced_drop_reattaches_then_says_the_session_is_gone(monkeypatch):
    out = _drain(_attached_with([("All quiet.\n", "", "")], monkeypatch))
    assert any(text.startswith("session dropped — reattaching") for text in out)
    assert any(
        text.startswith("session gone — nothing answering on 127.0.0.1:1")
        for text in out
    )
