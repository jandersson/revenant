import pytest
from client.xml_parser import XMLParser
import pathlib


@pytest.fixture
def parser():
    return XMLParser()


@pytest.fixture
def login_strings():
    sample_file = pathlib.Path(__file__).parents[0] / "login-sample.log"
    with open(sample_file) as infile:
        raw_strings = infile.readlines()
    return raw_strings


def test_player_id(parser, login_strings):
    for string in login_strings:
        parser.parse(string)
    assert parser.player_id == "440984"


def test_instance(parser, login_strings):
    for string in login_strings:
        parser.parse(string)
    assert parser.game == "DR"


def test_name(parser, login_strings):
    for string in login_strings:
        parser.parse(string)
    assert parser.name == "Crannach"


def test_server_time(parser, login_strings):
    # Here I have just manually plucked the last prompt time from the log
    for string in login_strings:
        parser.parse(string)
    assert parser.server_time == 1626783177


def test_indicator(parser, login_strings):
    for string in login_strings:
        parser.parse(string)
    assert parser.indicator["IconSTANDING"] == "y"
    assert parser.indicator["IconPOISONED"] == "n"
    assert parser.indicator["IconDISEASED"] == "n"
    assert parser.indicator["IconPRONE"] == "n"
    assert parser.indicator["IconKNEELING"] == "n"
    assert parser.indicator["IconSITTING"] == "n"
    assert parser.indicator["IconSTUNNED"] == "n"
    assert parser.indicator["IconHIDDEN"] == "n"
    assert parser.indicator["IconINVISIBLE"] == "n"
    assert parser.indicator["IconDEAD"] == "n"
    assert parser.indicator["IconWEBBED"] == "n"
    assert parser.indicator["IconJOINED"] == "n"
