import pytest
from xml.etree.ElementTree import ParseError, XMLParser
from client.xml_data import XMLData
import pathlib


@pytest.fixture
def xml_data():
    return XMLData()


@pytest.fixture
def login_strings():
    """About 5 minutes worth of strings in a list from first logging in to the game"""
    sample_file = pathlib.Path(__file__).parents[0] / "login-sample.log"
    with open(sample_file) as infile:
        raw_strings = infile.readlines()
    return raw_strings


def _feed(xml_data, login_strings):
    """Feed captured lines into a fresh XMLParser, matching core.py's
    root-wrapping so multiple top-level self-closing tags on one line
    (e.g. a burst of <indicator/>s) are all processed."""
    for string in login_strings:
        try:
            XMLParser(target=xml_data).feed(f"<r>{string}</r>")
        except ParseError:
            continue


def test_player_id(xml_data, login_strings):
    _feed(xml_data, login_strings)
    assert xml_data.player_id == "440984"


def test_instance(xml_data, login_strings):
    _feed(xml_data, login_strings)
    assert xml_data.game == "DR"


def test_name(xml_data, login_strings):
    _feed(xml_data, login_strings)
    assert xml_data.name == "Crannach"


def test_server_time(xml_data, login_strings):
    _feed(xml_data, login_strings)
    # Last <prompt time=.../> in the captured session. Was 1626783177
    # before the root-wrap fix, because lines containing multiple prompts
    # silently dropped all but the first.
    assert xml_data.server_time == 1626783184


def test_compass_directions(xml_data):
    XMLParser(target=xml_data).feed(
        '<r><compass><dir value="n"/><dir value="sw"/><dir value="up"/></compass></r>'
    )
    assert xml_data.compass == ["n", "sw", "up"]


def test_compass_replaced_on_next_room(xml_data):
    XMLParser(target=xml_data).feed('<r><compass><dir value="n"/></compass></r>')
    XMLParser(target=xml_data).feed('<r><compass><dir value="e"/></compass></r>')
    assert xml_data.compass == ["e"]


def test_room_title_from_stream_window(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><streamWindow id='room' title='Room' "
        'subtitle=" - [The Crossing, Herald Street]"/></r>'
    )
    assert xml_data.room_title == "[The Crossing, Herald Street]"


def test_room_title_from_room_name_style(xml_data):
    XMLParser(target=xml_data).feed(
        '<r><style id="roomName"/>[Ilithi, Sana\'ati Dyaus] <style id=""/></r>'
    )
    assert xml_data.room_title == "[Ilithi, Sana'ati Dyaus]"


def test_roundtime_and_casttime(xml_data):
    XMLParser(target=xml_data).feed('<r><roundTime value="1723456789"/></r>')
    XMLParser(target=xml_data).feed('<r><castTime value="1723456792"/></r>')
    assert xml_data.roundtime == 1723456789
    assert xml_data.casttime == 1723456792


def test_route_plain_text_goes_to_main(xml_data):
    assert xml_data.route("You see a stunted forest troll.") == [
        ("", "You see a stunted forest troll.")
    ]


def test_route_single_line_stream(xml_data):
    line = '<pushStream id="thoughts"/>You sense: hello there<popStream/>'
    assert xml_data.route(line) == [("thoughts", "You sense: hello there")]


def test_route_mixed_line_splits_streams(xml_data):
    line = (
        'Before.<pushStream id="logons"/> * Bob joined the realms. <popStream/>After.'
    )
    assert xml_data.route(line) == [
        ("", "Before."),
        ("logons", " * Bob joined the realms. "),
        ("", "After."),
    ]


def test_route_buffers_multiline_stream(xml_data):
    assert (
        xml_data.route('<pushStream id="percWindow"/>Clear Vision  (29 roisaen)') == []
    )
    assert xml_data.route("<popStream/>") == [
        ("percWindow", "Clear Vision  (29 roisaen)")
    ]


def test_route_discards_duplicate_streams(xml_data):
    line = '<pushStream id="talk"/>You say, "hi"<popStream/>'
    assert xml_data.route(line) == []


def test_route_strips_tags_and_unescapes(xml_data):
    line = "You gesture. <pushBold/>A troll&apos;s club<popBold/> whooshes."
    assert xml_data.route(line) == [("", "You gesture. A troll's club whooshes.")]


def test_indicator(xml_data, login_strings):
    _feed(xml_data, login_strings)
    # IconPOISONED / IconDISEASED are not present in login-sample.log, so
    # they are not asserted here (the original test expected them, which
    # is why it was marked skip).
    assert xml_data.indicator["IconSTANDING"] == "y"
    assert xml_data.indicator["IconPRONE"] == "n"
    assert xml_data.indicator["IconKNEELING"] == "n"
    assert xml_data.indicator["IconSITTING"] == "n"
    assert xml_data.indicator["IconSTUNNED"] == "n"
    assert xml_data.indicator["IconHIDDEN"] == "n"
    assert xml_data.indicator["IconINVISIBLE"] == "n"
    assert xml_data.indicator["IconDEAD"] == "n"
    assert xml_data.indicator["IconWEBBED"] == "n"
    assert xml_data.indicator["IconJOINED"] == "n"
    assert xml_data.indicator["IconBLEEDING"] == "n"
