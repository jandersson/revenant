import re
import html
from xml.etree.ElementTree import ParseError


class XMLData:
    """A parser target directly translated from lich.rb::XMLParser (aka XMLData)"""

    def __init__(self):
        self.active_tags = []
        self.last_tag = None
        self.active_ids = []
        self.last_id = None
        # Flag indicating if text being processed is bold
        self.bold = False
        # Not sure what this is used for
        self.player_id = None
        self.game = None
        # Character first name
        self.name = None
        self.current_stream = ""
        self.current_style = ""
        self.prompt = ""
        # UNIX timestamp sent with <prompt> tag
        self.server_time = None
        # The prone/sitting/standing indicator
        self.indicator = {}

        # Internal memo pad for stripping multi line tags
        self._strip_xml_multiline = ""

    def data(self, text_string):
        if self.active_tags and self.active_tags[-1] == "prompt":
            self.prompt = text_string

    def start(self, name: str, attributes: dict):
        self.active_tags.append(name)
        if "id" in attributes:
            self.active_ids.append(attributes["id"])

        if name == "pushBold":
            self.bold = True
        elif name == "popBold":
            self.bold = False
        elif name == "playerID":
            self.player_id = attributes["id"]
        elif name == "style":
            self.current_style = attributes["id"]
        elif name == "prompt":
            self.server_time = int(attributes["time"])
        elif name == "settingsInfo":
            if "instance" in attributes:
                self.game = attributes["instance"]
        elif name == "app":
            self.name = attributes["char"]
        elif name == "indicator":
            self.indicator[attributes["id"]] = attributes["visible"]

    def end(self, name: str):
        if self.active_tags:
            self.last_tag = self.active_tags.pop()
        if self.active_ids:
            self.last_id = self.active_ids.pop()

    def strip(self, line: str) -> str:
        if line == "\r\n":
            return line

        if self._strip_xml_multiline:
            self._strip_xml_multiline += line
            line = self._strip_xml_multiline
        if len(re.split(r"<pushStream[^>]*\/>", line)) > len(
            re.split(r"<popStream[^>]*\/>", line)
        ):
            self._strip_xml_multiline = line
            return ""
        # Reset
        self._strip_xml_multiline = ""

        line = re.sub(
            r"<pushStream id=[\"'](?:spellfront|inv|bounty|society|speech|talk)[\"'][^>]*\/>.*?<popStream[^>]*>",
            "",
            line,
            flags=re.MULTILINE,
        )
        line = re.sub(
            r'<stream id="Spells">.*?<\/stream>', "", line, flags=re.MULTILINE
        )
        line = re.sub(
            r"<(compDef|inv|component|right|left|spell|prompt)[^>]*>.*?<\/\1>",
            "",
            line,
            flags=re.MULTILINE,
        )
        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line)
        if not line.strip():
            return ""
        return line

    def reset(self):
        self.current_stream = ""
        self.current_style = ""
        self.active_tags = []
        self.active_ids = []


if __name__ == "__main__":
    import xml.etree.ElementTree as ET

    # from xml.etree.ElementTree import XMLParser

    import pathlib

    test_file = pathlib.Path(__file__).parents[1] / "tests" / "login-sample.log"
    with open(test_file) as infile:
        test_data = infile.readlines()
    xml_data = XMLData()

    parser = ET.XMLParser(target=xml_data, encoding="ASCII")
    for line in test_data:
        try:
            # Need to create a new parser if it ever gets caught in an exception. Not sure how to get it unstuck.
            ET.XMLParser(target=xml_data, encoding="ASCII").feed(line)
        except ParseError as e:
            continue
    print(".")
