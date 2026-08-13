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
        engine.read(
            output_callback=lambda text, stream, style: out.append(
                (text, stream, style)
            )
        )
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
    assert ("You see stuff.\n", "", "") in out
    compass_frames = [frame for frame in out if frame[1] == "compass"]
    assert compass_frames == [("n e", "compass", "")]


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
    assert compass_frames == [("n", "compass", ""), ("s out", "compass", "")]


def test_room_exits_component_does_not_double_the_compass_frame():
    # A real arrival sends the exits twice: an empty decorative <compass>
    # inside the room-exits component, then the real one at top level.
    # Exactly one frame may be emitted — go2 paces its walk on them, and
    # a double frame desyncs it one room per step (false "off course").
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b"<component id='room exits'>Obvious paths: "
            b"<d>southwest</d>.<compass></compass></component>\n",
            b'<compass><dir value="sw"/></compass>\n',
        ]
    )
    out = _read_all(engine, 2)
    compass_frames = [frame for frame in out if frame[1] == "compass"]
    assert compass_frames == [("sw", "compass", "")]


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
    assert compass_frames == [("n s", "compass", ""), ("n s", "compass", "")]


def test_a_tag_torn_across_two_reads_never_leaks_fragments():
    # The live bug: a chunk boundary mid-tag rendered "<pr" and
    # 'ompt time="...">>' as visible text. The torn line must be held
    # until complete, then parsed whole.
    engine = Engine()
    engine.connection = FakeConnection(
        [b"All quiet.\n<pr", b'ompt time="1786574358">&gt;</prompt>\n']
    )
    out = _read_all(engine, 2)
    assert ("All quiet.\n", "", "") in out
    assert not any("<pr" in text or "ompt" in text for text, _, _ in out)
    assert engine.xml_data.server_time == 1786574358  # the tag still parsed


def test_a_stream_marker_torn_across_reads_still_routes():
    engine = Engine()
    engine.connection = FakeConnection(
        [b'<pushStream id="thou', b'ghts"/>psst<popStream/>\n']
    )
    out = _read_all(engine, 2)
    assert ("psst\n", "thoughts", "") in out
    assert not any("ghts" in text for text, _, _ in out)


def test_an_incomplete_line_is_held_not_flushed():
    engine = Engine()
    engine.connection = FakeConnection([b"You see half a sent"])
    out = _read_all(engine, 1)
    assert out == []  # nothing emitted until the line completes


def test_exp_change_rewrites_the_whole_exp_stream():
    # The Experience dock is wipe-and-rewrite, like the game's own
    # resident windows: a clear frame, then one line per learning skill.
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b"<component id='exp Athletics'>Athletics:  346 13% "
            b"deliberative</component>\n"
        ]
    )
    out = _read_all(engine, 1)
    exp_frames = [frame for frame in out if frame[1] == "exp"]
    assert exp_frames[0] == ("", "exp", "clear")
    assert exp_frames[1][0].startswith("Athletics")
    assert "346" in exp_frames[1][0] and "deliberative" in exp_frames[1][0]


def test_only_the_last_piece_of_a_line_carries_the_newline():
    # One line, two styled pieces: "You say" (speech) then the words.
    # Front ends just append pieces; the engine owns line endings.
    engine = Engine()
    engine.connection = FakeConnection(
        [b"<preset id='speech'>You say</preset>, \"Hello world.\"\n"]
    )
    out = _read_all(engine, 1)
    assert out == [
        ("You say", "", "speech"),
        (', "Hello world."\n', "", ""),
    ]


def test_clear_stream_control_frame_has_no_newline():
    engine = Engine()
    engine.connection = FakeConnection([b'<clearStream id="percWindow"/>\n'])
    out = _read_all(engine, 1)
    assert ("", "percWindow", "clear") in out
