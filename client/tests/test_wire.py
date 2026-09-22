"""The wire between a session and an outside tool (client/engine/wire.py):
one JSON object per line, decoded back to (text, stream, style) with the
unconsumed tail kept. send_line, send_and_read and request_state need a
live session and are tested in test_session.py and test_sendcmd.py.
"""

from client.engine import wire


def test_frame_roundtrip():
    buffer = wire.encode_frame("You see a troll.", "") + wire.encode_frame(
        "Clear Vision", "percWindow"
    )
    frames, rest = wire.decode_frames(buffer + b'{"partial')
    assert frames == [
        ("You see a troll.", "", ""),
        ("Clear Vision", "percWindow", ""),
    ]
    assert rest == b'{"partial'
