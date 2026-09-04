"""How LNet traffic is archived — the manual (#144).

One append-only file per connection beside the game logs, every element
sent and every chunk received, timestamped; the login element's
password never reaches the file; a Server built without a log
directory logs nothing, which is what the fakes and tests rely on.
"""

import re
from datetime import datetime

from chat.chat import Server, TrafficLog, default_log_dir, redact


class FakeConnection:
    """Records sends; hands out canned chunks on recv."""

    def __init__(self, chunks=()):
        self.sent = []
        self.chunks = list(chunks)

    def send(self, data):
        self.sent.append(data)

    def recv(self, size):
        return self.chunks.pop(0) if self.chunks else b""


def test_default_log_dir_is_the_game_logs_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_LOG_DIR", str(tmp_path / "logs"))
    assert default_log_dir() == tmp_path / "logs"
    monkeypatch.delenv("REVENANT_LOG_DIR")
    assert default_log_dir().name == "logs"
    assert default_log_dir().parent.name == ".revenant"


def test_the_login_password_is_redacted():
    line = '<login name="Lanival" game="DR" password="hunter2" client="1.15" />'
    assert redact(line) == (
        '<login name="Lanival" game="DR" password="<redacted>" client="1.15" />'
    )


def test_sent_and_received_traffic_land_in_the_file_timestamped(tmp_path):
    log = TrafficLog(tmp_path / "lnet.log")
    log.sent(b'<message type="channel">hello</message>\n')
    log.received(
        b'<message type="channel" channel="DRPrime" from="You">hello</message>\n'
    )
    lines = (tmp_path / "lnet.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    stamp = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")
    assert all(stamp.match(line) for line in lines)
    assert lines[0].endswith('>> <message type="channel">hello</message>')
    assert lines[1].endswith(
        '<< <message type="channel" channel="DRPrime" from="You">hello</message>'
    )


def test_a_chunk_with_several_lines_keeps_them_apart(tmp_path):
    log = TrafficLog(tmp_path / "lnet.log")
    log.received(b'<ping />\n<message type="server">hi</message>\n')
    lines = (tmp_path / "lnet.log").read_text(encoding="utf-8").splitlines()
    assert [line.split(" << ", 1)[1] for line in lines] == [
        "<ping />",
        '<message type="server">hi</message>',
    ]


def test_the_log_is_append_only_and_created_on_demand(tmp_path):
    log = TrafficLog(tmp_path / "deep" / "lnet.log")
    log.sent(b"<pong />\n")
    log.sent(b"<pong />\n")
    assert (tmp_path / "deep" / "lnet.log").read_text(encoding="utf-8").count(
        "<pong />"
    ) == 2


def test_the_log_file_is_named_for_the_connections_moment(tmp_path):
    log = TrafficLog.in_directory(tmp_path, when=datetime(2026, 9, 4, 21, 55, 7))
    assert log.path == tmp_path / "lnet-20260904-215507.log"


def test_a_server_with_a_log_dir_logs_the_login_redacted_and_the_replies(tmp_path):
    server = Server(log_dir=tmp_path)
    server.connection = FakeConnection([b'<message type="server">ok</message>\n'])
    # connect() would open the socket; set up the parser and log as it does.
    server._reset_parser()
    server.log = TrafficLog.in_directory(tmp_path)
    server.set_login_info("Lanival", password="hunter2")
    server.login()
    server.receive_messages()
    text = server.log.path.read_text(encoding="utf-8")
    assert "hunter2" not in text
    assert 'name="Lanival"' in text and 'password="<redacted>"' in text
    assert '<< <message type="server">ok</message>' in text
    # What went over the wire is not redacted.
    assert b'password="hunter2"' in server.connection.sent[0]


def test_a_server_without_a_log_dir_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_LOG_DIR", str(tmp_path))
    server = Server()
    server.connection = FakeConnection(
        [b"<ping />\n<message type='server'>x</message>\n"]
    )
    server._reset_parser()
    server.set_login_info("Lanival")
    server.login()
    server.receive_messages()
    assert server.log is None
    assert list(tmp_path.iterdir()) == []
