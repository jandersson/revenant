import xml.etree.ElementTree as ET
import re
import html


class XMLParser:
    def __init__(self):
        self.buffer = ""
        self.active_tags = []
        self.last_tag = None
        self.active_ids = []
        self.last_id = None
        self.bold = False
        self.player_id = None
        self.game = None
        self.name = None
        self.current_stream = ""
        self.current_style = ""
        self.prompt = ""

        # TODO: Rename unesc, its actually just looking for anything thats not a tag. Unescaping is just an addon.
        self.unesc_re = re.compile(r"^[^<]+")
        self.end_re = re.compile(r"^<\/[^<]+>")
        self.end_info_re = re.compile(r"^<\/([^\s>\/]+)")
        self.start_re = re.compile(r"^<[^<]+>")
        self.start_info_re = re.compile(r"^<([^\s>\/]+)")
        self.attr_re = re.compile(r"([A-z][A-z0-9_\-]*)=([\"'])(.*?)\2")

        self._strip_xml_multiline = ""

    def text(self, text_string):
        if self.active_tags and self.active_tags[-1] == "prompt":
            self.prompt = text_string
            print("prompt: ", text_string)
        return text_string

    def parse(self, line: str):
        self.buffer += line
        m = self.unesc_re.match(line)
        if m:
            # print("line: ", line)
            self.buffer = self.unesc_re.sub(self.buffer, "")
            # line = self.unesc_re.sub(self.buffer, "")
            line = html.unescape(line)
            self.text(line)
            if line:
                return line
        m = self.end_re.match(line)
        if m:
            print("end_re match: ", m)
            info_match = self.end_info_re.match(m.group(0))
            if info_match:
                print(info_match)
            return line
        m = self.start_re.match(line)
        if m:
            info = self.start_info_re.match(m.group(0))
            if info:
                element = info.group(1)
                attributes = {}
                for attr in self.attr_re.finditer(line):
                    attributes[attr.group(1)] = attr.group(3)
                self.tag_start(element, attributes)
                self.tag_end(element)
            return line
        return line

    def tag_start(self, name: str, attributes: dict):
        self.active_tags.append(name)
        if "id" in attributes:
            self.active_ids.append(attributes["id"])

        if name == "pushBold":
            self.bold = True
        elif name == "popBold":
            self.bold = False
        elif name == "playerID":
            self.player_id = attributes["id"]
        elif name == "settingsInfo":
            if "instance" in attributes:
                self.game = attributes["instance"]
        elif name == "app":
            self.name = attributes["char"]

    def tag_end(self, name: str):
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
        if len(re.split(r"<pushStream[^>]*\/>", line)) > len(re.split(r"<popStream[^>]*\/>", line)):
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
        line = re.sub(r'<stream id="Spells">.*?<\/stream>', "", line, flags=re.MULTILINE)
        line = re.sub(r"<(compDef|inv|component|right|left|spell|prompt)[^>]*>.*?<\/\1>", "", line, flags=re.MULTILINE)
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
