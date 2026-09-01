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


def test_engine_emits_roundtime_paired_with_the_fresh_prompt():
    # Captured 2026-08-22: the game states when roundtime ENDS as
    # server-epoch seconds, and the prompt that follows in the same
    # burst carries the server's "now" — value 1787402555 with prompt
    # 1787402545 is exactly the printed "Roundtime: 10 sec." The frame
    # pairs them ("end\tnow") so frontends count down skew-free.
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b"<roundTime value='1787402555'/>You scan the heavens "
            b"for the three moons:\n"
            b"Roundtime: 10 sec.\n"
            b'<prompt time="1787402545">&gt;</prompt>\n'
        ]
    )
    out = _read_all(engine, 1)
    frames = [frame for frame in out if frame[1] == "roundtime"]
    assert frames == [("1787402555\t1787402545", "roundtime", "")]


def test_roundtime_emits_once_per_value_and_again_on_change():
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b"<roundTime value='1787402555'/>climb\n"
            b'<prompt time="1787402545">&gt;</prompt>\n',
            b"nothing timed here\n",
            b"<roundTime value='1787402600'/>climb again\n"
            b'<prompt time="1787402590">&gt;</prompt>\n',
        ]
    )
    out = _read_all(engine, 3)
    frames = [frame for frame in out if frame[1] == "roundtime"]
    assert frames == [
        ("1787402555\t1787402545", "roundtime", ""),
        ("1787402600\t1787402590", "roundtime", ""),
    ]


def test_roundtime_before_any_prompt_still_emits():
    # No prompt seen yet (session just came up): the local clock
    # stands in for the server's so the counter still runs.
    engine = Engine()
    engine.connection = FakeConnection([b"<roundTime value='99'/>stagger\n"])
    out = _read_all(engine, 1)
    (frame,) = [frame for frame in out if frame[1] == "roundtime"]
    end, now = frame[0].split("\t")
    assert end == "99"
    assert int(now) > 0


def test_engine_emits_full_vitals_state_on_each_partial_update():
    # The game updates minivitals one bar at a time (captured shapes;
    # values tweaked to differ). Every change emits the accumulated
    # whole, so a frontend never holds partial state.
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b"<dialogData id='minivitals'><progressBar id='health'"
            b" value='100' text='health 100%'/></dialogData>\n",
            b"<dialogData id='minivitals'><progressBar id='concentration'"
            b" value='98' text='concentration 98%'/></dialogData>\n",
        ]
    )
    out = _read_all(engine, 2)
    frames = [frame for frame in out if frame[1] == "vitals"]
    assert frames == [
        ("health 100", "vitals", ""),
        ("health 100 concentration 98", "vitals", ""),
    ]


def test_engine_emits_the_character_once_at_login():
    # The game's login tag, scrubbed to synthetic identity:
    # <app char="..." game="DR" title="[DR: ...] Wrayth"/> (captured
    # 2026-08-22). One "character" frame — the title bar's data (#68).
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b'<app char="Testchar" game="DR" title="[DR: Testchar] Wrayth"/>\n',
            b"Later, unrelated text.\n",
        ]
    )
    out = _read_all(engine, 2)
    frames = [frame for frame in out if frame[1] == "character"]
    assert frames == [("Testchar", "character", "")]


def test_casttime_emits_like_roundtime():
    # Synthetic line in the captured roundTime shape — no caster
    # traffic captured yet; <castTime> parsing itself is pinned in
    # test_xml_parser.
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b"<castTime value='1787402560'/>You begin your chant.\n"
            b'<prompt time="1787402545">&gt;</prompt>\n'
        ]
    )
    out = _read_all(engine, 1)
    frames = [frame for frame in out if frame[1] == "casttime"]
    assert frames == [("1787402560\t1787402545", "casttime", "")]


def test_engine_emits_the_indicator_set_on_change():
    # The captured death burst (2026-08-22, #75): prone and dead flip
    # on together as the stun clears. Full state per frame, no re-emit
    # while nothing changes.
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b'<indicator id="IconSTANDING" visible="y"/>'
            b'<indicator id="IconDEAD" visible="n"/>\n',
            b"nothing changes here\n",
            b'<indicator id="IconKNEELING" visible="n"/>'
            b'<indicator id="IconPRONE" visible="y"/>'
            b'<indicator id="IconSITTING" visible="n"/>'
            b'<indicator id="IconSTANDING" visible="n"/>'
            b"<indicator id='IconSTUNNED' visible='n'/>"
            b"<indicator id='IconBLEEDING' visible='n'/>"
            b"<indicator id='IconDEAD' visible='y'/>\n",
        ]
    )
    out = _read_all(engine, 3)
    frames = [frame for frame in out if frame[1] == "indicators"]
    assert frames == [
        ("IconSTANDING", "indicators", ""),
        ("IconDEAD IconPRONE", "indicators", ""),
    ]


def test_engine_emits_the_server_clock_delta_once(monkeypatch):
    # Every prompt states the server's clock (#102); the delta to the
    # local clock emits once and stays quiet while the clocks tick in
    # step — quantization/latency wobble never re-emits.
    local = [1_787_402_500.0]
    monkeypatch.setattr("time.time", lambda: local[0])
    engine = Engine()
    engine.connection = FakeConnection(
        [
            b'<prompt time="1787402545">&gt;</prompt>\n',
            b"",  # idle reads: no data, no fresh prompt ...
            b"",
            b"",
            b'<prompt time="1787402555">&gt;</prompt>\n',
            b'<prompt time="1787402600">&gt;</prompt>\n',
        ]
    )
    out = []

    def read_at(local_now):
        local[0] = local_now
        engine.read(
            output_callback=lambda text, stream, style: out.append(
                (text, stream, style)
            )
        )

    read_at(1_787_402_500.0)  # fresh prompt: delta 45, emitted
    # The live regression: while no prompt arrives, the last one goes
    # stale and the apparent delta decays one second per second. The
    # first rollout emitted that decay as a frame per second, flooding
    # frontends that predate the stream. Idle reads must stay silent.
    read_at(1_787_402_503.0)
    read_at(1_787_402_506.0)
    read_at(1_787_402_509.0)
    read_at(1_787_402_510.4)  # fresh prompt: delta 44.6 — wobble only
    read_at(1_787_402_520.0)  # fresh prompt after the local clock jumped
    frames = [frame for frame in out if frame[1] == "timesync"]
    assert frames == [("45.0", "timesync", ""), ("80.0", "timesync", "")]


def test_room_frame_is_uid_tab_title_with_blanks_for_the_unknown_half():
    # The "room" stream's wire text, shared by Engine.read and the
    # session's attach replay: "uid<TAB>title", "" when neither is known.
    from client.core import room_frame
    from client.xml_data import XMLData

    state = XMLData()
    assert room_frame(state) == ""
    state.room_title = "[The Crossing, Herald Street]"
    assert room_frame(state) == "\t[The Crossing, Herald Street]"
    state.room_uid = 1420
    assert room_frame(state) == "1420\t[The Crossing, Herald Street]"
    state.room_title = None
    assert room_frame(state) == "1420\t"
