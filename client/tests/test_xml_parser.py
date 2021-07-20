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
