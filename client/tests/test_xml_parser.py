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
