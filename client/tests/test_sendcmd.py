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
            # the replay: an old line, and an identical echo of an earlier
            # send of the same command, which must not count as the answer
            conn.sendall(
                frame("an old line from the backlog\n")
                + frame(">> [claude] tdp\n", "", "sent")
                + frame("You have 999 TDPs.\n")
            )
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
                frame("You have 347 TDPs.\n")
                + frame("bar", "vitals")
                + frame("[soul] no arch near\n", "script")
                + frame(">\n")
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
    # The story and the scripts' echoes; the dock frame is not an answer.
    assert (
        result.answer == "You have 347 TDPs.\n[soul] no arch near\n>\n"
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
    assert allowlisted("bank account")
    assert allowlisted("BANK  Account")
    assert not allowlisted("bank debt")  # sends a runner to pay: gated
    assert not allowlisted("bank")
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


# --- the read-only forms (#216) --------------------------------------------
@pytest.fixture
def stateful():
    """A fake session that answers a state request with one "state"
    frame, after a replay line, and keeps the request it got."""
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
            conn.sendall(
                frame(
                    json.dumps({"room": {"title": "[Town Square]"}, "vitals": {}}),
                    "state",
                )
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


@pytest.fixture
def talker():
    """A fake session whose replay already holds the line a wait is
    for, then the "attached" mark, then two live story lines a second
    apart — without waiting for any line from the client."""
    import json
    from time import sleep

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(5)

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
            try:
                # The replay (#287: it held the previous order's pay
                # line, and the wait ended on it), then the mark.
                conn.sendall(
                    frame("Earlier, her breath came in ragged pants.\n")
                    + frame("", "attached")
                    + frame("The girl runs past.\n")
                )
                sleep(1.0)
                conn.sendall(frame("The girl's breath comes in ragged pants.\n"))
                while conn.recv(4096):
                    pass
            except OSError:
                pass

    thread = Thread(target=serve, daemon=True)
    thread.start()
    yield server.getsockname()[1], thread
    server.close()


def test_state_asks_with_the_mark_and_returns_the_sessions_answer(stateful):
    port, got, thread = stateful
    result = sendcmd.query_state(port=port, fields=["room", "vitals"], origin="claude")
    thread.join(5)
    assert result.sent and result.state == {
        "room": {"title": "[Town Square]"},
        "vitals": {},
    }
    assert got == [b"\x1dclaude\troom,vitals\n"]


def test_the_console_script_prints_the_state_as_json(monkeypatch, capsys, stateful):
    port, got, thread = stateful
    code = sendcmd.main(["--port", str(port), "--origin", "claude", "--state"])
    thread.join(5)
    out = capsys.readouterr().out
    assert code == 0
    assert '"title": "[Town Square]"' in out
    assert got == [b"\x1dclaude\t\n"]  # no fields: all of them


def test_state_needs_no_gate_and_says_when_nothing_listens(monkeypatch, capsys):
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    port = holder.getsockname()[1]  # bound, not listening: refused
    code = sendcmd.main(["--port", str(port), "--state", "room"])
    assert code == 1 and "no state answer" in capsys.readouterr().out
    holder.close()


def test_wait_for_ends_on_the_line_and_says_so(answering):
    port, got, thread = answering
    result = send(
        "tdp",
        port=port,
        origin="claude",
        settings=SHUT,
        environ=NO_ENV,
        wait_for="347 TDPs",
        timeout=5,
    )
    thread.join(5)
    assert result.sent and result.found is True and result.ok
    assert "came" in result.message
    assert result.answer == "You have 347 TDPs.\n"  # nothing past the line


def test_wait_for_times_out_with_exit_status_one(monkeypatch, capsys, answering):
    port, got, thread = answering
    code = sendcmd.main(
        [
            "--port",
            str(port),
            "--origin",
            "claude",
            "--wait-for",
            "never",
            "--timeout",
            "1",
            "tdp",
        ]
    )
    thread.join(5)
    out = capsys.readouterr().out
    assert code == 1 and "did not come" in out and "You have 347 TDPs." in out


def test_wait_for_alone_sends_nothing_and_returns_on_the_line(talker):
    port, thread = talker
    result = sendcmd.wait("ragged pants", port=port, timeout=5)
    thread.join(5)
    assert result.found is True
    assert result.answer.endswith("The girl's breath comes in ragged pants.\n")
    assert "The girl runs past." in result.answer
    # The replayed line held the text too and did not end the wait.
    assert "Earlier" not in result.answer


def test_the_console_script_needs_a_command_or_a_read_only_form(capsys):
    with pytest.raises(SystemExit):
        sendcmd.main(["--port", "1"])
