import html
import re

# Streams that duplicate text already present in the main window (or that
# nothing renders yet), matching what the old strip() deleted outright.
DISCARD_STREAMS = {"spellfront", "inv", "bounty", "society", "speech", "talk"}

# <pushStream id="thoughts"/> opens a routed block, <popStream/> returns
# to the main stream. The capture group carries the stream id; popStream
# matches contribute None.
_STREAM_MARKER = re.compile(r"<pushStream id=[\"'](\w+)[\"'][^>]*/>|<popStream[^>]*/>")

# Attention-critical lines the server sends with no markup at all —
# the official frontend supplies their emphasis, so we supply ours as
# the "alert" style (issue #42). Extend only with captured evidence.
_ALERT_LINE = re.compile(r"YOU HAVE BEEN IDLE TOO LONG")

# <d>north</d> and <d cmd='go gate'>the gate</d>: command links. The
# link's game command is the cmd attribute when present, else the tag
# body; front ends render style "link:<command>" as clickable.
_LINK = re.compile(r"<d(?:\s+cmd=[\"']([^\"']*)[\"'])?[^>]*>(.*?)</d>", re.S)


def _split_links(piece, style):
    """Split a styled piece around <d> command links: (text, style)
    chunks with links carrying style "link:<command>"."""
    position = 0
    for match in _LINK.finditer(piece):
        if match.start() > position:
            yield piece[position : match.start()], style
        body = match.group(2)
        command = match.group(1) or html.unescape(re.sub(r"<[^>]+>", "", body)).strip()
        yield body, f"link:{command}"
        position = match.end()
    if position < len(piece):
        yield piece[position:], style


# DR's 35 learning rates; the index is the mindstate 0..34 (ported from
# lich's DR_LEARNING_RATES).
LEARNING_RATES = [
    "clear",
    "dabbling",
    "perusing",
    "learning",
    "thoughtful",
    "thinking",
    "considering",
    "pondering",
    "ruminating",
    "concentrating",
    "attentive",
    "deliberative",
    "interested",
    "examining",
    "understanding",
    "absorbing",
    "intrigued",
    "scrutinizing",
    "analyzing",
    "studious",
    "focused",
    "very focused",
    "engaged",
    "very engaged",
    "cogitating",
    "fascinated",
    "captivated",
    "engrossed",
    "riveted",
    "very riveted",
    "rapt",
    "very rapt",
    "enthralled",
    "nearly locked",
    "mind lock",
]

# "Athletics:  346 13% deliberative" or the brief form "... 13% [17/34]"
_EXP_TEXT = re.compile(
    r":\s*(\d+)\s+(\d+)%\s+(?:\[\s*(\d+)/34\]|([a-zA-Z][a-zA-Z ]*?))\s*$"
)

# The exp window's non-skill components (TDPs, favors, rested exp).
_EXP_NOT_SKILLS = {"exp tdp", "exp favor", "exp rexp", "exp mods"}

# The game's inline styling: bold runs, presets (speech, roomDesc, ...)
# and style spans (roomName). Group 1: preset id; group 2: style id.
_STYLE_MARKER = re.compile(
    r"<pushBold\s*/?>|<popBold\s*/?>"
    r"|<preset id=[\"'](\w+)[\"'][^>]*>|</preset>"
    r"|<style id=[\"'](\w*)[\"'][^>]*/?>"
)


class XMLData:
    """The game state parsed from the XML stream — an XMLParser target
    in the shape of lich's XMLData: start()/data()/end() accumulate
    state (prompt, indicators, compass, vitals, room, exp window), and
    route() splits a raw line into (stream, text, style) segments.
    Engine.read drives both; the *_updated flags tell it what changed."""

    def __init__(self):
        # Open tags, innermost last — data() looks at the top of it.
        self.active_tags = []
        self.player_id = None
        # The game instance from <settingsInfo instance=.../> ("DR").
        self.game = None
        # Character first name
        self.name = None
        # The <style id=...> span the parser is inside (roomName ...).
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
        self._compass_in_component = False
        # Epoch seconds (server clock) when roundtime / spellcast time end
        self.roundtime = 0
        self.casttime = 0
        # Vitals percentages from the minivitals dialog's progress bars:
        # {"health": 100, "stamina": 95, ...}; casters also get "mana".
        # The game sends partial updates, so this dict accumulates.
        self.vitals = {}
        self.vitals_updated = False
        self._vitals_dialog = False
        # Hostile creatures in the room, from <crtrStatus hostile='1'>
        # tags: {exist id: engaged}. Each crtrStatus burst replaces the
        # set wholesale (staged, swapped at the closing prompt so a
        # mid-line read never sees a half-set); a room change clears
        # them until a fresh enumeration arrives (#72). 'room objs'
        # pulses must NOT clear anything: they can arrive empty or
        # prose-only mid-engagement with no status tags behind them
        # (the cave-bear capture, 2026-08-22 — #85); a stale hostile
        # self-heals at the next room change.
        self.hostiles = {}
        self._staged_hostiles = None
        # Bracketed room title, e.g. "[The Crossing, Herald Street]"
        self.room_title = None
        # The game's unique room id from <nav rm='...'/>, sent on every
        # movement — the exact position fix (titles collide, uids don't).
        self.room_uid = None
        # The exp window: skill -> {rank, percent, mindstate, rate},
        # updated from <component id='exp Skill'> pulses. An empty
        # component removes the skill (it left the learning queue).
        self.experience = {}
        self.exp_updated = False
        self._exp_skill = None
        self._exp_text = ""

        # Internal memo pad for stripping multi line tags
        self._strip_xml_multiline = ""
        # route()'s own styling state — bold and style spans persist
        # across lines, presets close on the same line.
        self._route_bold = False
        self._route_style = ""
        self._route_preset = ""

    def data(self, text_string):
        if self.active_tags and self.active_tags[-1] == "prompt":
            self.prompt = text_string
        if self.current_style == "roomName" and text_string.strip():
            self.room_title = text_string.strip()
        if self._exp_skill is not None:
            self._exp_text += text_string

    def start(self, name: str, attributes: dict):
        self.active_tags.append(name)

        if name == "playerID":
            self.player_id = attributes["id"]
        elif name == "style":
            self.current_style = attributes["id"]
        elif name == "prompt":
            self.server_time = int(attributes["time"])
            if self._staged_hostiles is not None:
                self.hostiles = self._staged_hostiles
                self._staged_hostiles = None
        elif name == "settingsInfo":
            if "instance" in attributes:
                self.game = attributes["instance"]
        elif name == "app":
            self.name = attributes["char"]
        elif name == "indicator":
            self.indicator[attributes["id"]] = attributes["visible"]
        elif name == "compass":
            self._pending_compass = []
            # The room-exits component embeds a decorative (empty) <compass>;
            # only the top-level one is the room's real exit list, and only
            # that one may signal an arrival (go2 paces its walk on it).
            self._compass_in_component = "component" in self.active_tags[:-1]
        elif name == "dir":
            self._pending_compass.append(attributes["value"])
        elif name == "nav":
            try:
                self.room_uid = int(attributes.get("rm", ""))
            except ValueError:
                pass
            # A new room: creature knowledge resets until the fresh
            # enumeration arrives.
            self.hostiles = {}
            self._staged_hostiles = None
        elif name == "roundTime":
            self.roundtime = int(attributes["value"])
        elif name == "castTime":
            self.casttime = int(attributes["value"])
        elif name == "dialogData":
            self._vitals_dialog = attributes.get("id") == "minivitals"
        elif name == "progressBar" and self._vitals_dialog:
            # Scoped to minivitals: the injuries dialog reuses
            # progressBar ("health2") and must not pollute vitals.
            try:
                self.vitals[attributes["id"]] = int(attributes["value"])
                self.vitals_updated = True
            except (KeyError, ValueError):
                pass
        elif name == "component":
            ident = attributes.get("id", "")
            if ident.startswith("exp ") and ident not in _EXP_NOT_SKILLS:
                self._exp_skill = ident[4:]
                self._exp_text = ""
        elif name == "crtrStatus":
            # The first tag since the last swap opens a fresh staged
            # set — the burst is the enumeration (#85), nothing else
            # is. Non-hostile tags join the burst without an entry, so
            # a creature re-announced harmless drops out at the swap.
            if self._staged_hostiles is None:
                self._staged_hostiles = {}
            if attributes.get("hostile") == "1":
                self._staged_hostiles[attributes.get("exist", "")] = (
                    attributes.get("disengaged") != "1"
                )
        elif name == "streamWindow" and attributes.get("id") == "room":
            subtitle = attributes.get("subtitle", "")
            if subtitle.startswith(" - "):
                self.room_title = subtitle[3:].strip()

    def end(self, name: str):
        if name == "dialogData":
            self._vitals_dialog = False
        if name == "compass" and not self._compass_in_component:
            self.compass = self._pending_compass
            self.compass_updated = True
        if name == "component" and self._exp_skill is not None:
            skill, self._exp_skill = self._exp_skill, None
            text = self._exp_text.strip()
            if not text:
                if self.experience.pop(skill, None) is not None:
                    self.exp_updated = True
            elif match := _EXP_TEXT.search(text):
                rank, percent = int(match.group(1)), int(match.group(2))
                if match.group(3):  # brief mode: [N/34]
                    mindstate = int(match.group(3))
                    rate = LEARNING_RATES[min(mindstate, 34)]
                else:
                    rate = match.group(4).strip()
                    mindstate = (
                        LEARNING_RATES.index(rate) if rate in LEARNING_RATES else 0
                    )
                self.experience[skill] = {
                    "rank": rank,
                    "percent": percent,
                    "mindstate": mindstate,
                    "rate": rate,
                }
                self.exp_updated = True
        if self.active_tags:
            self.active_tags.pop()

    def _effective_style(self):
        return (
            self._route_preset
            or self._route_style
            or ("bold" if self._route_bold else "")
        )

    def _styled_pieces(self, text):
        """Split a segment on style markers into (piece, style) runs."""
        pieces = []
        position = 0
        for match in _STYLE_MARKER.finditer(text):
            if match.start() > position:
                pieces.append((text[position : match.start()], self._effective_style()))
            marker = match.group(0)
            if marker.startswith("<pushBold"):
                self._route_bold = True
            elif marker.startswith("<popBold"):
                self._route_bold = False
            elif marker.startswith("<preset"):
                self._route_preset = match.group(1)
            elif marker.startswith("</preset"):
                self._route_preset = ""
            else:  # <style id="..."/> — empty id closes the span
                self._route_style = match.group(2) or ""
            position = match.end()
        if position < len(text):
            pieces.append((text[position:], self._effective_style()))
        return pieces

    def route(self, line: str) -> list:
        """Split a line of game text into (stream, text, style) segments.

        The main stream is "". pushStream/popStream pairs that span lines
        are buffered until they balance, so a segment always knows its
        stream. Streams in DISCARD_STREAMS are dropped. style is the
        active preset/style/bold ("" for plain text) — or the control
        value "clear" with empty text, meaning the front end should wipe
        that stream's window (<clearStream/>, e.g. the spell list pulse).
        """
        if line == "\r\n":
            return [("", line, "")]

        if self._strip_xml_multiline:
            self._strip_xml_multiline += line
            line = self._strip_xml_multiline
        if len(re.findall(r"<pushStream[^>]*/>", line)) > len(
            re.findall(r"<popStream[^>]*/>", line)
        ):
            self._strip_xml_multiline = line
            return []
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

        segments = []
        # A wipe marker precedes the stream's fresh content: emit the
        # control segment first so front ends clear before appending.
        for stream in re.findall(r"<clearStream id=[\"'](\w+)[\"']", line):
            segments.append((stream, "", "clear"))

        parts = _STREAM_MARKER.split(line)
        texts = parts[0::2]
        # Text before the first marker is main; after a pushStream it is
        # that stream's; after a popStream it is main again.
        streams = [""] + [marker or "" for marker in parts[1::2]]
        for stream, text in zip(streams, texts):
            if stream in DISCARD_STREAMS:
                continue
            for styled_piece, piece_style in self._styled_pieces(text):
                for piece, style in _split_links(styled_piece, piece_style):
                    piece = re.sub(r"<[^>]+>", "", piece)
                    piece = html.unescape(piece)
                    if not piece.strip():
                        continue
                    if not style and _ALERT_LINE.search(piece):
                        # The server sends these attention-critical lines
                        # with no markup at all, trusting the official
                        # frontend to make them loud (captured evidence in
                        # issue #42) — so the styling is ours to add.
                        style = "alert"
                    segments.append((stream, piece, style))
        return segments
