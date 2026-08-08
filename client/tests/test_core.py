from client.core import Engine


class FakeConnection:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def read_very_eager(self):
        if self.chunks:
            return self.chunks.pop(0)
        return b""


def _read_all(engine, reads):
    out = []
    for _ in range(reads):
        engine.read(output_callback=lambda text, stream: out.append((text, stream)))
    return out


def test_engine_emits_compass_stream_once_per_room():
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b'<compass><dir value="n"/><dir value="e"/></compass>You see stuff.\n',
            b"Nothing new here.\n",
        ]
    )
    out = _read_all(engine, 2)
    assert ("You see stuff.", "") in out
    compass_frames = [frame for frame in out if frame[1] == "compass"]
    assert compass_frames == [("n e", "compass")]


def test_engine_emits_compass_again_on_change():
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b'<compass><dir value="n"/></compass>Room one.\n',
            b'<compass><dir value="s"/><dir value="out"/></compass>Room two.\n',
        ]
    )
    out = _read_all(engine, 2)
    compass_frames = [frame for frame in out if frame[1] == "compass"]
    assert compass_frames == [("n", "compass"), ("s out", "compass")]


def test_engine_emits_compass_for_identical_adjacent_rooms():
    # Corridor case: consecutive rooms with the same exits still emit one
    # frame each — scripts rely on it as the room-arrival signal.
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b'<compass><dir value="n"/><dir value="s"/></compass>Corridor.\n',
            b'<compass><dir value="n"/><dir value="s"/></compass>More corridor.\n',
        ]
    )
    out = _read_all(engine, 2)
    compass_frames = [frame for frame in out if frame[1] == "compass"]
    assert compass_frames == [("n s", "compass"), ("n s", "compass")]
