import socket

import pytest

from client.netsock import SocketClient


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
