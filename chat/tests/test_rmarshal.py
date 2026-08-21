"""How the Marshal reader decodes LNet replies — these tests are the manual.

Ground truth comes two ways: round-tripping chat.py's own Marshal
string writer, and handcrafted Marshal 4.8 byte vectors for the shapes
the writer doesn't produce (arrays, hashes, integers, symbol links).
"""

import base64
import xml.etree.ElementTree as ET

import pytest

from chat.chat import _ruby_marshal_str, format_data_payload, render_data
from chat.rmarshal import MarshalError, loads


def test_round_trips_the_writers_own_strings():
    assert loads(_ruby_marshal_str("hello")) == "hello"
    assert loads(_ruby_marshal_str("åäö räksmörgås")) == "åäö räksmörgås"


def test_scalars():
    assert loads(b"\x04\x080") is None
    assert loads(b"\x04\x08T") is True
    assert loads(b"\x04\x08F") is False
    assert loads(b"\x04\x08i\x00") == 0
    assert loads(b"\x04\x08i\x7f") == 122  # small positive: byte - 5
    assert loads(b"\x04\x08i\xfa") == -1  # small negative: byte + 5
    assert loads(b"\x04\x08i\x02\xc8\x00") == 200  # 2-byte little-endian


def test_array_of_ivar_strings_with_symbol_links():
    # ["hi", "yo"] the way Ruby dumps it: the second :E is a symlink.
    data = b'\x04\x08[\x07I"\x07hi\x06:\x06ETI"\x07yo\x06;\x00T'
    assert loads(data) == ["hi", "yo"]


def test_hash_with_symbol_keys():
    # {:users => 3}
    data = b"\x04\x08{\x06:\x0ausersi\x08"
    assert loads(data) == {"users": 3}


def test_unsupported_tags_fail_loudly():
    with pytest.raises(MarshalError, match="unsupported"):
        loads(b"\x04\x08u\x06")  # user-defined class
    with pytest.raises(MarshalError, match="header"):
        loads(b"\x03\x07T")
    with pytest.raises(MarshalError, match="truncated"):
        loads(b'\x04\x08"\x10short')


def test_render_data_formats_a_who_reply():
    payload = b'\x04\x08[\x07I"\x0aAlvin\x06:\x06ETI"\x0bTestch\x06;\x00T'
    element = ET.Element("data", {"type": "who"})
    element.text = base64.b64encode(payload).decode("ascii")
    rendered = render_data(element)
    assert rendered.startswith("[LNet who]")
    assert "Alvin, Testch" in rendered


def test_render_data_falls_back_on_garbage():
    element = ET.Element("data", {"type": "who"})
    element.text = base64.b64encode(b"\x04\x08u\x06whatever").decode("ascii")
    assert render_data(element) is None


def test_format_handles_dicts_and_scalars():
    assert format_data_payload("server stats", {"users": 3, "uptime": "9d"}) == (
        "[LNet server stats]\nusers: 3\nuptime: 9d"
    )
    assert format_data_payload("channels", []) == "[LNet channels]\n(none)"
