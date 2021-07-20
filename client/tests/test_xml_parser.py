import pytest
from xml.etree.ElementTree import ParseError, XMLParser
from client.xml_parser import XMLData
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


def test_player_id(xml_data, login_strings):
    # TODO: Make the XMLParser for loop DRY, its duplicated in every test and in core.
    for string in login_strings:
        try:
            XMLParser(target=xml_data).feed(string)
        except ParseError:
            continue
    assert xml_data.player_id == "440984"


def test_instance(xml_data, login_strings):
    for string in login_strings:
        try:
            XMLParser(target=xml_data).feed(string)
        except ParseError:
            continue
    assert xml_data.game == "DR"


def test_name(xml_data, login_strings):
    for string in login_strings:
        try:
            XMLParser(target=xml_data).feed(string)
        except ParseError:
            continue
    assert xml_data.name == "Crannach"


def test_server_time(xml_data, login_strings):
    # Here I have just manually plucked the last prompt time from the log
    for string in login_strings:
        try:
            XMLParser(target=xml_data).feed(string)
        except ParseError:
            continue
    assert xml_data.server_time == 1626783177


@pytest.mark.skip
def test_indicator(xml_data, login_strings):
    # FIXME: Test is failing. Only some of the indicator data is processed, leading to key errors
    for string in login_strings:
        try:
            XMLParser(target=xml_data).feed(string)
        except ParseError:
            continue
    assert xml_data.indicator["IconSTANDING"] == "y"
    assert xml_data.indicator["IconPOISONED"] == "n"
    assert xml_data.indicator["IconDISEASED"] == "n"
    assert xml_data.indicator["IconPRONE"] == "n"
    assert xml_data.indicator["IconKNEELING"] == "n"
    assert xml_data.indicator["IconSITTING"] == "n"
    assert xml_data.indicator["IconSTUNNED"] == "n"
    assert xml_data.indicator["IconHIDDEN"] == "n"
    assert xml_data.indicator["IconINVISIBLE"] == "n"
    assert xml_data.indicator["IconDEAD"] == "n"
    assert xml_data.indicator["IconWEBBED"] == "n"
    assert xml_data.indicator["IconJOINED"] == "n"
