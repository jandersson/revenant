"""The session registry: ~/.revenant/sessions.json, one row per running
session, so the launcher's picker can offer the characters online (#58).

A session registers {port, character, pid, attached} when it serves,
keeps the attached-window count current (#158), re-asserts its row every
HEARTBEAT_SECONDS and deregisters on shutdown; the launcher reads the
rows and probes each port, pruning one only when it refuses twice
(#160). Liveness is connectability — pids cannot be probed safely on
Windows. The file is written atomically, a failed read is never
rewritten as empty, and reads and writes within a process take turns.
REVENANT_SESSIONS moves the file (the tests do).
"""

import json
import os
import pathlib
import socket
from threading import Lock
from time import sleep

from client.engine.wire import DEFAULT_HOST

# The session registry: every session records {port, character, pid}
# here so the launcher's picker can offer running characters as attach
# targets beside the roster (#58). Liveness is connectability — a
# crashed session leaves a stale row that running_sessions() prunes
# (pids can't be probed safely on Windows).
SESSIONS_PATH = "~/.revenant/sessions.json"


def sessions_path():
    return pathlib.Path(os.environ.get("REVENANT_SESSIONS", SESSIONS_PATH)).expanduser()


def _load_sessions():
    """The registry's rows: [] when there is no file, None when the file
    could not be read — torn or locked by another process's write, even
    after the retries. None is never "no sessions": a writer that gets
    it skips its write rather than saving what it did not read (#160)."""
    path = sessions_path()
    for attempt in range(_LOAD_TRIES):
        try:
            with open(path) as stream:
                data = json.load(stream)
        except FileNotFoundError:
            return []
        except (OSError, ValueError):  # mid-rewrite: torn, or locked on Windows
            if attempt + 1 < _LOAD_TRIES:
                sleep(_LOAD_RETRY_SECONDS)
                continue
            return None
        return data if isinstance(data, list) else []
    return None


def _write_sessions(entries):
    """Write the rows atomically: a temp file renamed into place, so a
    reader sees the old file or the new one and never a torn one. On
    Windows the rename fails while another process holds the file open;
    it is retried briefly, and the plain write is the last resort."""
    path = sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(entries)
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(text)
        for attempt in range(_REPLACE_TRIES):
            try:
                os.replace(temp, path)
                return
            except OSError:
                if attempt + 1 < _REPLACE_TRIES:
                    sleep(_LOAD_RETRY_SECONDS)
        path.write_text(text)
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


# Registry reads and writes within one process happen from the accept
# loop, every client thread's drop, the heartbeat and the launcher's
# poll, so they take turns (#158). Another process reading mid-write
# (the picker while a session rewrites its attached count) sees a torn
# or locked file: _load_sessions retries, then reports failure (None),
# and no writer turns a failed read into an empty registry (#160).
_REGISTRY_LOCK = Lock()
_LOAD_TRIES = 5
_LOAD_RETRY_SECONDS = 0.04
_REPLACE_TRIES = 5
HEARTBEAT_SECONDS = 30  # a session re-asserts its row this often
# A liveness probe's patience. A live session answers at once (the
# kernel completes the handshake before the accept loop turns), but
# Windows refuses a dead localhost port only after ~2 s of retries
# (measured 2026-09-12: 2.04 s to WinError 10061); with less than that
# a dead row reads as a timeout and is never pruned.
PROBE_TIMEOUT = 3.0
PROBE_RETRY_SECONDS = 0.5  # between the two refused probes that prune a row


def register_session(port, character, pid=None, attached=0):
    """Announce a session: {port, character, pid, attached} — attached
    is the count of front ends on it, kept current by update_attached
    so the launcher's picker can tell a detached session (no window)
    from one already on screen (#158). True when the row was written;
    False when the registry could not be read, in which case nothing is
    written and the session's heartbeat tries again (#160)."""
    with _REGISTRY_LOCK:
        entries = _load_sessions()
        if entries is None:
            return False
        entries = [e for e in entries if e.get("port") != port]
        entries.append(
            {
                "port": port,
                "character": character,
                "pid": pid or os.getpid(),
                "attached": attached,
            }
        )
        _write_sessions(entries)
        return True


def update_attached(port, count, character=None, pid=None):
    """The registry row's attached-window count. With `character` the
    call also heals: a row that is missing — pruned by a busy probe, or
    lost to a bad rewrite — is put back (#160). Without it a missing
    row stays missing (a deregistered session must not return). False
    when the registry could not be read; nothing is written then."""
    with _REGISTRY_LOCK:
        entries = _load_sessions()
        if entries is None:
            return False
        for entry in entries:
            if entry.get("port") == port:
                if entry.get("attached") == count:
                    return True  # nothing to say: no write, no torn window
                entry["attached"] = count
                _write_sessions(entries)
                return True
        if character is None:
            return True
        entries.append(
            {
                "port": port,
                "character": character,
                "pid": pid or os.getpid(),
                "attached": count,
            }
        )
        _write_sessions(entries)
        return True


def deregister_session(port):
    """Drop the row; when the registry cannot be read, drop nothing — a
    stale row is pruned later by a refused probe."""
    with _REGISTRY_LOCK:
        entries = _load_sessions()
        if entries is None:
            return False
        remaining = [e for e in entries if e.get("port") != port]
        if remaining != entries:
            _write_sessions(remaining)
        return True


def character_for_port(port):
    """The character a registered session on `port` plays, or None.

    The GUI asks before it builds its window, so the character's own
    layout can be restored before the first show — the one order Qt
    restores every saved dock state safely (#140)."""
    for entry in _load_sessions() or []:
        try:
            if int(entry.get("port")) == int(port):
                name = entry.get("character")
                return str(name) if name else None
        except (TypeError, ValueError):
            continue
    return None


def _probe(host, port):
    """ "live", "refused" or "unsure" for a registered port. Only a
    refused connection says nothing listens; a timeout says the session
    was busy (replaying a backlog, parsing INFO) and is no reason to
    lose its row (#160)."""
    try:
        with socket.create_connection((host, int(port)), timeout=PROBE_TIMEOUT):
            return "live"
    except ConnectionRefusedError:
        return "refused"
    except (OSError, ValueError, TypeError):
        return "unsure"


def running_sessions(host=DEFAULT_HOST):
    """Registered sessions that actually answer. A row is pruned only
    when its port refuses twice, PROBE_RETRY_SECONDS apart — a crashed
    session leaves a refusing port; a busy one times out and stays."""
    with _REGISTRY_LOCK:
        entries = _load_sessions()
        if not entries:
            return []
        live, doubtful = [], []
        for entry in entries:
            verdict = _probe(host, entry.get("port"))
            if verdict == "refused":
                doubtful.append(entry)
            else:
                live.append(entry)
        if doubtful:
            sleep(PROBE_RETRY_SECONDS)
            for entry in doubtful:
                if _probe(host, entry.get("port")) != "refused":
                    live.append(entry)
            live = [e for e in entries if e in live]  # the file's order
        if live != entries:
            _write_sessions(live)
    return live  # an unsure (busy) session is a running session
