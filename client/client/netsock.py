"""A minimal socket client covering the slice of telnetlib's API this project used.

telnetlib was removed from the standard library in Python 3.13. Neither the
eaccess handshake nor the game stream uses actual telnet negotiation (no IAC
sequences), so a plain buffered TCP socket is a faithful replacement.
"""

import socket
from select import select


class SocketClient:
    def __init__(self, host=None, port=0, timeout=None):
        self.sock = None
        self._buffer = b""
        self._eof = False
        if host is not None:
            self.open(host, port, timeout)

    def open(self, host, port, timeout=None):
        self.sock = socket.create_connection((host, port), timeout)

    def write(self, buffer):
        self.sock.sendall(buffer)

    def read_until(self, expected, timeout=None):
        """Read until the expected byte sequence appears, returning everything
        up to and including it. Raises EOFError if the connection closes first."""
        while expected not in self._buffer:
            data = self.sock.recv(4096)
            if not data:
                self._eof = True
                raise EOFError("Connection closed by remote end")
            self._buffer += data
        end = self._buffer.index(expected) + len(expected)
        result, self._buffer = self._buffer[:end], self._buffer[end:]
        return result

    def read_very_eager(self):
        """Drain whatever is available without blocking. Returns b'' when
        nothing is pending; raises EOFError once the connection has closed."""
        if self._eof and not self._buffer:
            raise EOFError("Connection closed by remote end")
        while select([self.sock], [], [], 0)[0]:
            data = self.sock.recv(4096)
            if not data:
                self._eof = True
                break
            self._buffer += data
        if self._eof and not self._buffer:
            raise EOFError("Connection closed by remote end")
        result, self._buffer = self._buffer, b""
        return result

    def get_socket(self):
        return self.sock

    def fileno(self):
        return self.sock.fileno()

    def close(self):
        if self.sock is not None:
            self.sock.close()
