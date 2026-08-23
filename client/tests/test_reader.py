"""How the frontend's reader loop ends — these tests are the manual.

EOF is the clean end (the session dropped us): reconnect guidance in
the status bar. Any other crash is logged in full and announced the
same way (#96) — before this, a ValueError killed the thread via the
default threading excepthook (a stderr print nobody sees) and the
window sat half-dead, still claiming Connected.
"""

from client import reader


class FakeLog:
    def __init__(self):
        self.exceptions = []

    def exception(self, message):
        self.exceptions.append(message)


def test_eof_announces_reconnect_and_ends_the_loop():
    reads, statuses = [], []

    def read():
        reads.append(True)
        if len(reads) == 3:
            raise EOFError()

    reader.pump(read, statuses.append, FakeLog(), delay=0)
    assert len(reads) == 3  # pumped until the connection ended
    assert statuses == ["Disconnected — File → Reconnect"]


def test_a_crash_is_logged_and_announced_not_silent():
    log, statuses = FakeLog(), []

    def read():
        raise ValueError("corrupt frame")  # e.g. decode_frames choking

    reader.pump(read, statuses.append, log, delay=0)  # must not raise
    assert log.exceptions == ["reader thread crashed"]
    assert statuses and "File → Reconnect" in statuses[0]
    assert "crashed" in statuses[0]
