"""The wire an outside tool speaks to a running session: JSON frames in,
tagged command lines out, on 127.0.0.1:4242 by default.

A session serves `{"stream", "text", "style"}` frames, one per line
(encode_frame / decode_frames), and reads plain command lines back. A
line led by EXTERNAL_MARK was sent from outside the frontends (#135:
`revenant-send`; the session echoes it to every window with its
origin), one led by STATE_MARK asks for the parser's state and is
answered to that connection alone (#216). request_state, send_and_read
and send_line are the client side of each, used by revenant-send and
the roster sweep; the GUI and the TUI attach through
session.AttachedEngine instead. close_socket is the portable close.
"""

import json
import os
import socket
from time import monotonic

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("REVENANT_SESSION_PORT", "4242"))

# A frontend line that starts with this byte was sent from outside the
# frontends — revenant-send (client/engine/sendcmd.py, #135): "\x1e<origin>\t
# <command>". The session strips the tag, echoes the command to EVERY
# attached window as ">> [<origin>] <command>" and logs it, so a line
# the player did not type never acts invisibly.
EXTERNAL_MARK = b"\x1e"
# A frontend line that starts with this byte asks for the parser's
# state (#216): "\x1d<origin>\t<field,field>" (no fields: all). The
# session answers that connection alone with one "state" frame of
# JSON (client/engine/snapshot.py) — nothing goes to the game, nothing
# is echoed or logged to a window, so an outside reader learns the
# room, the vitals, the exp window or the hands without typing LOOK,
# EXP or INV at the character.
STATE_MARK = b"\x1d"


def request_state(host, port, fields=(), origin="external", timeout=5):
    """The parser's state of a running session as a dict (#216), or
    None when nothing was listening or no answer came in `timeout`
    seconds. `fields` narrows it (see snapshot.FIELDS); the replay a
    new connection gets first is read past."""
    try:
        conn = socket.create_connection((host, int(port)), timeout=timeout)
    except OSError:
        return None
    origin = "".join(ch for ch in origin if ch not in "\t\n\x1d\x1e") or "external"
    line = STATE_MARK + f"{origin}\t{','.join(fields)}\n".encode("UTF-8")
    buffer = b""
    answer = None
    with conn:
        try:
            conn.sendall(line)
        except OSError:
            return None
        deadline = monotonic() + timeout
        while answer is None and (left := deadline - monotonic()) > 0:
            conn.settimeout(min(left, 0.5))
            try:
                chunk = conn.recv(65536)
            except TimeoutError:
                continue
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            decoded, buffer = decode_frames(buffer)
            for text, stream, _ in decoded:
                if stream == "state":
                    try:
                        answer = json.loads(text)
                    except ValueError:
                        answer = None
                    break
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    return answer


def send_and_read(host, port, text, seconds, timeout=5, settle=0.3, until=None):
    """Send one command line and return what the session broadcast in
    the `seconds` after it: [(text, stream, style)] frames, the story
    and the docks alike, from the line's own ">> [origin] ..." echo on.
    None when nothing was listening. This is how a tool reads the
    game's answer without tailing a log: the connection is a frontend
    for those seconds. With `text` None nothing is sent and the
    frames are simply what arrived in the window; with `until` the
    read ends as soon as a story line holds that text (#216: the
    story window a driver used to poll the raw log for).

    The backlog replay comes first, and it can hold an identical echo
    of an earlier send of the same line — so the replay is drained
    (read until `settle` seconds pass with no bytes, two seconds at
    most) before the line goes out, and the first matching echo after
    that is this line's own."""
    try:
        conn = socket.create_connection((host, int(port)), timeout=timeout)
    except OSError:
        return None
    if text is None:
        echo, seen_echo = None, True
    else:
        origin, _, command = text.lstrip("\x1e").partition("\t")
        echo = f">> [{origin}] {' '.join(command.split())}"
        seen_echo = False
    frames, buffer, done = [], b"", False
    with conn:
        # Nothing to drain when nothing is sent: every line counts.
        drain_until = monotonic() + (2.0 if text is not None else 0.0)
        while monotonic() < drain_until:
            conn.settimeout(settle)
            try:
                chunk = conn.recv(65536)
            except TimeoutError:
                break  # quiet: the replay is over
            except OSError:
                break
            if not chunk:
                break
        if text is not None:
            conn.sendall(text.encode("UTF-8").rstrip(b"\n") + b"\n")
        deadline = monotonic() + seconds
        while not done and (left := deadline - monotonic()) > 0:
            conn.settimeout(min(left, 0.5))
            try:
                chunk = conn.recv(65536)
            except TimeoutError:
                continue
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            decoded, buffer = decode_frames(buffer)
            for frame in decoded:
                if not seen_echo:
                    if frame[2] == "sent" and frame[0].strip() == echo:
                        seen_echo = True
                    continue
                frames.append(frame)
                if until and frame[1] == "" and until in frame[0]:
                    done = True
                    break
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    return frames


def send_line(host, port, text, timeout=5):
    """Send one command line to a running session, as a frontend would.

    True when it went out, False when nothing was listening. The
    session forwards any line not starting with ";" straight to the
    game, so this is how a tool logs a character out: closing the
    client only drops the connection, and the game says so at every
    login ("Closing your front end does NOT necessarily drop your
    character from the game! Type QUIT or EXIT!"), leaving the
    character linkdead instead of gone (#114).

    The line goes out, then the socket is half-closed and read until
    the session lets go: attach() replays the backlog to every new
    connection before it reads a byte, and a sender that closed the
    moment it had written made that replay fail against a dead peer —
    the session dropped the connection and never read the command
    (captured 2026-09-11: two sends logged as attached-and-detached
    in the same second, nothing sent to the game, once the backlog
    had grown past a few frames). Half-closing sends the FIN after
    the line, so the session reads the command, then EOF, and drops
    us — which is the EOF this waits for, under the same timeout.
    """
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as conn:
            conn.sendall(text.encode("UTF-8").rstrip(b"\n") + b"\n")
            conn.shutdown(socket.SHUT_WR)
            deadline = monotonic() + timeout
            while monotonic() < deadline:
                try:
                    if not conn.recv(65536):
                        break  # the session read our line and let go
                except TimeoutError:
                    break
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
