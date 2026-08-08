import re
import html
from xml.etree.ElementTree import ParseError

# Streams that duplicate text already present in the main window (or that
# nothing renders yet), matching what the old strip() deleted outright.
DISCARD_STREAMS = {"spellfront", "inv", "bounty", "society", "speech", "talk"}

# <pushStream id="thoughts"/> opens a routed block, <popStream/> returns
# to the main stream. The capture group carries the stream id; popStream
# matches contribute None.
_STREAM_MARKER = re.compile(r"<pushStream id=[\"'](\w+)[\"'][^>]*/>|<popStream[^>]*/>")


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
        # Obvious exits from the <compass> tag, e.g. ["n", "sw", "up"]
        self.compass = []
        self.compass_updated = False
        self._pending_compass = []
        # Epoch seconds (server clock) when roundtime / spellcast time end
        self.roundtime = 0
        self.casttime = 0

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
        elif name == "compass":
            self._pending_compass = []
        elif name == "dir":
            self._pending_compass.append(attributes["value"])
        elif name == "roundTime":
            self.roundtime = int(attributes["value"])
        elif name == "castTime":
            self.casttime = int(attributes["value"])

    def end(self, name: str):
        if name == "compass":
            self.compass = self._pending_compass
            self.compass_updated = True
        if self.active_tags:
            self.last_tag = self.active_tags.pop()
        if self.active_ids:
            self.last_id = self.active_ids.pop()

    def route(self, line: str) -> list:
        """Split a line of game text into (stream, text) segments.

        The main stream is "". pushStream/popStream pairs that span lines
        are buffered until they balance, so a segment always knows its
        stream. Streams in DISCARD_STREAMS are dropped.
        """
        if line == "\r\n":
            return [("", line)]

        if self._strip_xml_multiline:
            self._strip_xml_multiline += line
            line = self._strip_xml_multiline
        if len(re.split(r"<pushStream[^>]*\/>", line)) > len(
            re.split(r"<popStream[^>]*\/>", line)
        ):
            self._strip_xml_multiline = line
            return []
        # Reset
        self._strip_xml_multiline = ""

        line = re.sub(
            r'<stream id="Spells">.*?<\/stream>', "", line, flags=re.MULTILINE
        )
        line = re.sub(
            r"<(compDef|inv|component|right|left|spell|prompt)[^>]*>.*?<\/\1>",
            "",
            line,
            flags=re.MULTILINE,
        )

        parts = _STREAM_MARKER.split(line)
        texts = parts[0::2]
        # Text before the first marker is main; after a pushStream it is
        # that stream's; after a popStream it is main again.
        streams = [""] + [marker or "" for marker in parts[1::2]]
        segments = []
        for stream, text in zip(streams, texts):
            text = re.sub(r"<[^>]+>", "", text)
            text = html.unescape(text)
            if not text.strip() or stream in DISCARD_STREAMS:
                continue
            segments.append((stream, text))
        return segments

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
        except ParseError:
            continue
    print(".")
