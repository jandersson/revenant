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


def test_compass_inside_component_is_decoration(xml_data):
    # The room-exits component embeds an empty <compass> alongside the
    # real top-level one; it must neither clobber the exits nor raise
    # compass_updated (captured live 2026-08-13).
    XMLParser(target=xml_data).feed('<r><compass><dir value="n"/></compass></r>')
    xml_data.compass_updated = False
    XMLParser(target=xml_data).feed(
        "<r><component id='room exits'>Obvious paths: "
        "<d>southwest</d>.<compass></compass></component></r>"
    )
    assert xml_data.compass == ["n"]
    assert xml_data.compass_updated is False


# --- the exp window: how skill learning becomes state -------------------


def test_exp_component_parses_rank_percent_and_mindstate(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Athletics'>      Athletics:  346 13% "
        "deliberative</component></r>"
    )
    assert xml_data.experience["Athletics"] == {
        "rank": 346,
        "percent": 13,
        "mindstate": 11,  # deliberative is 11/34
        "rate": "deliberative",
    }
    assert xml_data.exp_updated


def test_exp_component_brief_mode_carries_the_mindstate_number(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Attunement'>Attunement:  520 42% [17/34]</component></r>"
    )
    assert xml_data.experience["Attunement"]["mindstate"] == 17
    assert xml_data.experience["Attunement"]["rate"] == "scrutinizing"


def test_empty_exp_component_clears_the_skill(xml_data):
    # Captured live: the game sends an empty component when a skill
    # leaves the learning queue.
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Shield Usage'>Shield Usage: 100 5% clear</component></r>"
    )
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Shield Usage'></component></r>"
    )
    assert "Shield Usage" not in xml_data.experience


def test_exp_window_extras_are_not_skills(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><component id='exp tdp'>    TDPs:  721</component></r>"
    )
    assert xml_data.experience == {}


def test_nav_tag_carries_the_room_uid(xml_data):
    # Sent on every movement — the exact position fix for ;go2.
    XMLParser(target=xml_data).feed("<r>You stroll east.<nav rm='10081'/></r>")
    assert xml_data.room_uid == 10081


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
        ("", "You see a stunted forest troll.", "")
    ]


def test_route_single_line_stream(xml_data):
    line = '<pushStream id="thoughts"/>You sense: hello there<popStream/>'
    assert xml_data.route(line) == [("thoughts", "You sense: hello there", "")]


def test_route_mixed_line_splits_streams(xml_data):
    line = (
        'Before.<pushStream id="logons"/> * Bob joined the realms. <popStream/>After.'
    )
    assert xml_data.route(line) == [
        ("", "Before.", ""),
        ("logons", " * Bob joined the realms. ", ""),
        ("", "After.", ""),
    ]


def test_route_buffers_multiline_stream(xml_data):
    assert (
        xml_data.route('<pushStream id="percWindow"/>Clear Vision  (29 roisaen)') == []
    )
    assert xml_data.route("<popStream/>") == [
        ("percWindow", "Clear Vision  (29 roisaen)", "")
    ]


def test_route_discards_duplicate_streams(xml_data):
    line = '<pushStream id="talk"/>You say, "hi"<popStream/>'
    assert xml_data.route(line) == []


def test_route_unescapes_entities(xml_data):
    line = "A troll&apos;s club whooshes."
    assert xml_data.route(line) == [("", "A troll's club whooshes.", "")]


# --- styling: how the game's markers become styled segments -------------


def test_bold_text_is_a_styled_run_within_the_line(xml_data):
    line = "You gesture. <pushBold/>A troll's club<popBold/> whooshes."
    assert xml_data.route(line) == [
        ("", "You gesture. ", ""),
        ("", "A troll's club", "bold"),
        ("", " whooshes.", ""),
    ]


def test_speech_preset_styles_the_say_prefix(xml_data):
    # Captured live: the game wraps only "You say" in the speech preset.
    line = "<preset id='speech'>You say</preset>, \"Hello world.\""
    assert xml_data.route(line) == [
        ("", "You say", "speech"),
        ("", ', "Hello world."', ""),
    ]


def test_room_name_style_spans_until_reset(xml_data):
    assert xml_data.route('<style id="roomName" />[Northwall Trail, Grassland]') == [
        ("", "[Northwall Trail, Grassland]", "roomName")
    ]
    # The empty style id on the next line closes the span.
    assert xml_data.route('<style id=""/>Obvious paths: east.') == [
        ("", "Obvious paths: east.", "")
    ]


def test_bold_persists_across_lines_until_popped(xml_data):
    assert xml_data.route("<pushBold/>*** IMPORTANT ***") == [
        ("", "*** IMPORTANT ***", "bold")
    ]
    assert xml_data.route("still shouting") == [("", "still shouting", "bold")]
    assert xml_data.route("<popBold/>calm again") == [("", "calm again", "")]


def test_clear_stream_is_a_control_segment(xml_data):
    # The spell-list pulse: wipe the window, then the fresh list arrives.
    assert xml_data.route('<clearStream id="percWindow"/>') == [
        ("percWindow", "", "clear")
    ]


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


def test_idle_warning_gets_the_alert_style():
    # Captured 2026-08-20 (issue #42): the idle check arrives with no
    # markup at all between two prompts; official frontends supply the
    # emphasis, so the parser stamps our own "alert" style on it.
    xml_data = XMLData()
    assert xml_data.route("YOU HAVE BEEN IDLE TOO LONG. PLEASE RESPOND.") == [
        ("", "YOU HAVE BEEN IDLE TOO LONG. PLEASE RESPOND.", "alert")
    ]
    # Ordinary unstyled text stays plain.
    assert xml_data.route("You feel fully rested.") == [
        ("", "You feel fully rested.", "")
    ]


def test_command_links_get_link_styles():
    xml_data = XMLData()
    segments = xml_data.route("Obvious paths: <d>north</d>, <d>east</d>.")
    assert segments == [
        ("", "Obvious paths: ", ""),
        ("", "north", "link:north"),
        ("", ", ", ""),
        ("", "east", "link:east"),
        ("", ".", ""),
    ]


def test_command_links_prefer_the_cmd_attribute():
    xml_data = XMLData()
    segments = xml_data.route("You see <d cmd='go wooden gate'>a gate</d> here.")
    assert ("", "a gate", "link:go wooden gate") in segments
