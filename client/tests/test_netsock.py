import socket

import pytest

from client.engine import netsock
from client.engine.netsock import SocketClient


def _tcp_pair():
    """A connected TCP pair on the loopback (a socketpair is AF_UNIX on
    POSIX, where TCP options do not apply)."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    left = socket.create_connection(listener.getsockname())
    right, _ = listener.accept()
    listener.close()
    return left, right


def test_keepalive_is_on_for_every_way_a_game_socket_is_made():
    # #221: a dead link with no FIN was found only on the next write, 52
    # minutes on. Every constructor turns TCP keepalive on; the option
    # is readable back, the timings are the OS's to keep.
    left, right = _tcp_pair()
    adopted = SocketClient.from_fd(left.detach())
    assert adopted.sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
    other, peer = _tcp_pair()
    wrapped = SocketClient.from_socket(other)
    assert wrapped.sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
    assert netsock.keepalive(peer) is True
    # The silence clock: recent at birth, reset by a byte.
    assert adopted.silent_for() < 5
    adopted.last_received -= 1000
    assert adopted.silent_for() > 900
    right.sendall(b"pulse\n")
    adopted.read_until(b"\n", timeout=5)
    assert adopted.silent_for() < 5
    for sock in (right, peer):
        sock.close()
    adopted.close()
    wrapped.close()


def test_from_fd_adopts_socket_and_seeds_buffer():
    left, right = socket.socketpair()
    client = SocketClient.from_fd(left.detach(), initial=b"seeded ")

    client.write(b"ping")
    right.settimeout(5)
    assert right.recv(4096) == b"ping"

    right.sendall(b"fresh")
    right.close()
    assert client.read_very_eager() == b"seeded fresh"
    with pytest.raises(EOFError):
        client.read_very_eager()
    client.close()


def test_buffered_exposes_unconsumed_bytes():
    left, right = socket.socketpair()
    client = SocketClient.from_fd(left.detach())
    right.sendall(b"line one\nhalf a li")
    client.read_until(b"\n", timeout=5)
    assert client.buffered == b"half a li"
    right.close()
    client.close()
