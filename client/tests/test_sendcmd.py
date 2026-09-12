"""How revenant-send gets one command into a session — these tests are
the manual (#135).

Read-only commands pass with the gate shut; anything else needs the
setting or REVENANT_ALLOW_SEND=1; --dry-run sends nothing; no listener
is a message, never a traceback; the line arrives tagged with its
origin so the session can echo it as not-the-player. The fake session
here is a thread on an ephemeral port — never a live game.
"""

import socket
from threading import Thread

import pytest

from client.engine import sendcmd
from client.engine.sendcmd import Result, allowlisted, resolve_port, send

SHUT = {"allow_external_send": False}
OPEN = {"allow_external_send": True}
NO_ENV = {}


@pytest.fixture
def listener():
    """A one-shot fake session: accepts one connection, keeps the line."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(5)
    got = []

    def serve():
        try:
            conn, _ = server.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(5)
            buffer = b""
            while b"\n" not in buffer:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
            got.append(buffer)

    thread = Thread(target=serve, daemon=True)
    thread.start()
    yield server.getsockname()[1], got, thread
    server.close()


@pytest.fixture
def answering():
    """A fake session that replays a backlog, echoes the line it got as
    the session does, answers with two story lines and a dock frame,
    then waits for the sender to hang up."""
    import json

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(5)
    got = []

    def frame(text, stream="", style=""):
        return (
            json.dumps({"text": text, "stream": stream, "style": style}) + "\n"
        ).encode()

    def serve():
        try:
            conn, _ = server.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(5)
            conn.sendall(frame("an old line from the backlog\n"))
            buffer = b""
            while b"\n" not in buffer:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                buffer += chunk
            got.append(buffer)
            origin, _, command = (
                buffer.decode().lstrip("\x1e").rstrip("\n").partition("\t")
            )
            conn.sendall(frame(f">> [{origin}] {command}\n", "", "sent"))
            conn.sendall(
                frame("You have 347 TDPs.\n") + frame("bar", "vitals") + frame(">\n")
            )
            try:
                while conn.recv(4096):
                    pass
            except OSError:
                pass

    thread = Thread(target=serve, daemon=True)
    thread.start()
    yield server.getsockname()[1], got, thread
    server.close()


def test_answer_returns_the_story_lines_after_the_echo_and_not_the_replay(answering):
    port, got, thread = answering
    result = send(
        "tdp", port=port, origin="claude", settings=SHUT, environ=NO_ENV, answer=1.5
    )
    thread.join(5)
    assert result.sent
    assert got == [b"\x1eclaude\ttdp\n"]
    assert (
        result.answer == "You have 347 TDPs.\n>\n"
    )  # the dock frame and the replay are not story


def test_the_console_script_prints_the_answer(monkeypatch, capsys, answering):
    port, got, thread = answering
    monkeypatch.setenv("REVENANT_ALLOW_SEND", "0")
    code = sendcmd.main(
        ["--port", str(port), "--origin", "claude", "--answer", "1.5", "tdp"]
    )
    thread.join(5)
    out = capsys.readouterr().out
    assert code == 0
    assert "sent 'tdp'" in out and "You have 347 TDPs." in out


def test_read_only_commands_are_allowlisted_and_the_rest_are_gated():
    assert allowlisted("exp all")
    assert allowlisted("INFO")
    assert allowlisted(";sheet inv")
    assert allowlisted(";stop hunt")
    assert allowlisted("tdp project agility 12")
    assert allowlisted("Stamina")
    assert allowlisted("encumbrance")
    assert not allowlisted("train")
    assert not allowlisted("vault pay 1 5000")  # VAULT reads and pays alike: gated
    assert not allowlisted("bank withdraw 1 all")
    assert not allowlisted("attack rat")
    assert not allowlisted("drop sack")
    assert not allowlisted(";hunt")
    assert not allowlisted("")


def test_the_line_arrives_verbatim_tagged_with_its_origin(listener):
    port, got, thread = listener
    result = send("exp all", port=port, settings=SHUT, environ=NO_ENV)
    thread.join(5)
    assert result.sent is True
    assert got == [b"\x1eexternal\texp all\n"]
    assert "allowlisted" in result.message


def test_a_gated_command_is_refused_with_the_gate_shut(listener):
    port, got, thread = listener
    result = send("attack rat", port=port, settings=SHUT, environ=NO_ENV)
    assert result.sent is False
    assert result.message.startswith("refused: 'attack rat'")
    assert "REVENANT_ALLOW_SEND=1" in result.message
    assert got == []


def test_the_setting_or_the_env_override_opens_the_gate(listener):
    port, got, thread = listener
    assert send("attack rat", port=port, settings=OPEN, environ=NO_ENV).sent is True
    thread.join(5)
    assert got == [b"\x1eexternal\tattack rat\n"]
    assert sendcmd.gate_open(SHUT, {"REVENANT_ALLOW_SEND": "1"}) is True
    assert sendcmd.gate_open(SHUT, {"REVENANT_ALLOW_SEND": "0"}) is False


def test_a_dry_run_sends_nothing_and_says_what_it_would_do(listener):
    port, got, thread = listener
    result = send("exp all", port=port, dry_run=True, settings=SHUT, environ=NO_ENV)
    assert result.sent is False
    assert result.ok is True
    assert (
        result.message
        == f"dry run: would send 'exp all' to 127.0.0.1:{port} (allowlisted (read-only))"
    )
    assert got == []


def test_a_dry_run_still_reports_a_refusal(listener):
    port, got, thread = listener
    result = send("attack rat", port=port, dry_run=True, settings=SHUT, environ=NO_ENV)
    assert result.ok is False
    assert result.message.startswith("refused")


def test_nothing_listening_is_a_message_not_a_traceback():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))  # bound, never listening: a port nobody answers on
    port = probe.getsockname()[1]
    try:
        result = send("exp all", port=port, settings=SHUT, environ=NO_ENV)
    finally:
        probe.close()
    assert result.sent is False
    assert result.message == f"nothing is listening on 127.0.0.1:{port}"


def test_the_origin_cannot_smuggle_a_second_line(listener):
    port, got, thread = listener
    send("exp all", port=port, origin="bot\tquit\n", settings=SHUT, environ=NO_ENV)
    thread.join(5)
    assert got == [b"\x1ebotquit\texp all\n"]


def test_the_character_picks_the_session_and_one_session_needs_no_name():
    sessions = [
        {"port": 4242, "character": "Lanival"},
        {"port": 4243, "character": "Sable"},
    ]
    assert resolve_port("sable", sessions)[0] == 4243
    port, why = resolve_port(None, sessions)
    assert port is None and "name one with --character" in why
    port, why = resolve_port("Uthmor", sessions)
    assert port is None and "no session is playing 'Uthmor'" in why
    assert resolve_port(None, sessions[:1])[0] == 4242
    assert resolve_port(None, [])[0] is None


def test_empty_input_sends_nothing():
    assert send("   ", port=1, settings=OPEN, environ=NO_ENV) == Result(
        False, "nothing to send", "127.0.0.1", 1, ""
    )


def test_the_console_script_exits_nonzero_on_a_refusal(monkeypatch, capsys, listener):
    port, got, thread = listener
    monkeypatch.setattr(sendcmd, "load_settings", lambda: SHUT)
    monkeypatch.delenv("REVENANT_ALLOW_SEND", raising=False)
    assert sendcmd.main(["--port", str(port), "attack", "rat"]) == 1
    assert "refused" in capsys.readouterr().out
    assert sendcmd.main(["--port", str(port), "--dry-run", "exp", "all"]) == 0
    assert got == []
