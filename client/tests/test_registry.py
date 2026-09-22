"""The session registry (client/engine/registry.py): a row per running
session in ~/.revenant/sessions.json, never lost to a torn read, pruned
only when its port refuses twice (#58, #158, #160). The server's side —
registering when it serves, healing its row by heartbeat — is tested
with a live session in test_session.py; the launcher's use in
test_launch.py.
"""

import json

from client.engine import registry


def _registry(monkeypatch, tmp_path, rows):
    path = tmp_path / "sessions.json"
    monkeypatch.setenv("REVENANT_SESSIONS", str(path))
    path.write_text(json.dumps(rows))
    return path


ROWS = [
    {"port": 4242, "character": "Lanival", "pid": 1, "attached": 0},
    {"port": 4243, "character": "Sable", "pid": 2, "attached": 1},
]


def test_a_torn_registry_reads_as_failure_not_as_empty(monkeypatch, tmp_path):
    path = _registry(monkeypatch, tmp_path, ROWS)
    path.write_text('[{"port": 42')  # a rewrite caught halfway
    monkeypatch.setattr(registry, "_LOAD_RETRY_SECONDS", 0.001)
    assert registry._load_sessions() is None
    # ... and no writer turns that into an empty file
    assert registry.update_attached(4242, 1) is False
    assert registry.deregister_session(4242) is False
    assert registry.register_session(4244, "Uthmor") is False
    assert path.read_text() == '[{"port": 42'
    assert registry.character_for_port(4242) is None
    path.unlink()
    assert registry._load_sessions() == []  # no file is genuinely empty


def test_writes_are_atomic_and_leave_no_temp_file(monkeypatch, tmp_path):
    path = _registry(monkeypatch, tmp_path, [])
    registry.register_session(4242, "Lanival", pid=7)
    assert json.loads(path.read_text()) == [
        {"port": 4242, "character": "Lanival", "pid": 7, "attached": 0}
    ]
    assert list(tmp_path.iterdir()) == [path]


def test_update_attached_heals_a_missing_row_only_when_told_who(monkeypatch, tmp_path):
    path = _registry(monkeypatch, tmp_path, ROWS[1:])
    assert registry.update_attached(4242, 1) is True  # no character: stays gone
    assert [r["port"] for r in json.loads(path.read_text())] == [4243]
    assert registry.update_attached(4242, 1, character="Lanival", pid=9) is True
    rows = json.loads(path.read_text())
    assert rows[-1] == {"port": 4242, "character": "Lanival", "pid": 9, "attached": 1}
    # an unchanged count writes nothing (fewer torn-read windows)
    before = path.stat().st_mtime_ns
    registry.update_attached(4243, 1)
    assert path.stat().st_mtime_ns == before


def test_a_busy_session_keeps_its_row_and_a_refusing_one_loses_it(
    monkeypatch, tmp_path
):
    path = _registry(monkeypatch, tmp_path, ROWS)
    verdicts = {4242: TimeoutError(), 4243: ConnectionRefusedError()}
    probes = []

    def connect(address, timeout=None):
        probes.append(address[1])
        raise verdicts[address[1]]

    monkeypatch.setattr(registry.socket, "create_connection", connect)
    monkeypatch.setattr(registry, "PROBE_RETRY_SECONDS", 0.001)
    live = registry.running_sessions()
    assert [r["port"] for r in live] == [4242]  # busy stays, refused goes
    assert probes.count(4243) == 2  # pruned only on the second refusal
    assert [r["port"] for r in json.loads(path.read_text())] == [4242]


def test_a_single_refusal_does_not_prune(monkeypatch, tmp_path):
    path = _registry(monkeypatch, tmp_path, ROWS[:1])
    answers = [ConnectionRefusedError(), None]  # refused once, then answering

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def connect(address, timeout=None):
        answer = answers.pop(0)
        if answer is not None:
            raise answer
        return Conn()

    monkeypatch.setattr(registry.socket, "create_connection", connect)
    monkeypatch.setattr(registry, "PROBE_RETRY_SECONDS", 0.001)
    assert [r["port"] for r in registry.running_sessions()] == [4242]
    assert [r["port"] for r in json.loads(path.read_text())] == [4242]


def test_character_for_port_reads_the_registry(monkeypatch, tmp_path):
    # The GUI asks before building its window, so the character's own
    # layout restores before the first show (#140).
    path = tmp_path / "sessions.json"
    path.write_text(
        json.dumps(
            [
                {"port": 4242, "character": "Lanival", "pid": 1},
                {"port": "4243", "character": "Other", "pid": 2},
                {"port": "bogus", "character": "Nobody"},
            ]
        )
    )
    monkeypatch.setenv("REVENANT_SESSIONS", str(path))
    assert registry.character_for_port(4242) == "Lanival"
    assert registry.character_for_port("4243") == "Other"
    assert registry.character_for_port(5000) is None


def test_character_for_port_is_none_without_a_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SESSIONS", str(tmp_path / "missing.json"))
    assert registry.character_for_port(4242) is None
