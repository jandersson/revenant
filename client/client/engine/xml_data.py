import html
import re

from client.game.rested import parse_rested

# Streams that duplicate text already present in the main window (or that
# nothing renders yet), matching what the old strip() deleted outright.
DISCARD_STREAMS = {"spellfront", "inv", "bounty", "society", "speech", "talk"}

# <pushStream id="thoughts"/> opens a routed block, <popStream/> returns
# to the main stream. The capture group carries the stream id; popStream
# matches contribute None.
_STREAM_MARKER = re.compile(r"<pushStream id=[\"'](\w+)[\"'][^>]*/>|<popStream[^>]*/>")

# One Spells-window line: "Heroic Strength  (10 roisaen)" — the name,
# then the time left in parentheses (captured 2026-09-12). A count of
# roisaen becomes minutes; anything else ("Indefinite") is None.
_SPELL_LINE = re.compile(r"^\s*(.+?)\s+\((.*?)\)\s*$")


# The room's players, from <component id='room players'>: "Also here:
# Sky Knight Kaldean who is darkened by an unnatural shadow, Sand Flower
# Cyranth, Cecil and Penello." (captured 2026-09-12), empty when alone.
# Titles come before the name and " who is ..." after it; the name is
# the last word before that.
_PLAYERS_LEAD = re.compile(r"^\s*Also here:\s*", re.IGNORECASE)


def _players(text):
    """The character names an "Also here:" line names, in order."""
    body = _PLAYERS_LEAD.sub("", text.strip()).rstrip(".")
    if not body:
        return []
    names = []
    for entry in re.split(r",\s*|\s+and\s+", body):
        entry = re.split(r"\s+who\s+(?:is|are|has|have)\b", entry, maxsplit=1)[0]
        words = entry.strip().split()
        if words:
            names.append(words[-1])
    return names


def _active_spells(text):
    """{name: minutes left or None} from the Spells window's lines."""
    spells = {}
    for line in text.splitlines():
        match = _SPELL_LINE.match(line)
        if not match:
            continue
        name, note = match.group(1), match.group(2)
        count = re.match(r"(\d+)\s+roisa", note)
        spells[name] = int(count.group(1)) if count else None
    return spells


# Attention-critical lines the server sends with no markup at all —
# the official frontend supplies their emphasis, so we supply ours as
# the "alert" style (issue #42). Extend only with captured evidence.
_ALERT_LINE = re.compile(r"YOU HAVE BEEN IDLE TOO LONG")
# C0 control characters other than tab / newline / carriage return. The
# game wraps its idle warning in BEL (0x07) — the official frontend's cue
# to beep — and a font has no glyph for it, so a widget shows a box at
# each end (captured 2026-09-04, #131). Stripped from every piece; the
# bell itself becomes a synthetic "bell" segment for the GUI to sound.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BELL = "\x07"

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
# The injuries panel's hurt states: "Injury1" (captured), "Scar2" (the
# pattern's assumption for scars, #163).
_INJURY = re.compile(r"(Injury|Scar)(\d+)$", re.IGNORECASE)

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
    state (prompt, indicators, compass, vitals, room, exp window, hands,
    the prepared spell and the running ones), and route() splits a raw
    line into (stream, text, style) segments.
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
        # Prompts seen so far: a command's answer ends with one, so a
        # script that sent a command waits for the count to move before
        # trusting the roundtime it reads (Handle.waitrt).
        self.prompt_count = 0
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
        # Spells: the one prepared (<spell>Heroic Strength</spell>,
        # "None" between casts) and the ones running, from the Spells
        # window the game rewrites on every pulse — <clearStream
        # id="percWindow"/> then a pushStream of "Name  (N roisaen)"
        # lines (captured 2026-09-12; a roisan is a real minute,
        # client/game/eltime.py). {name: minutes left, or None when the
        # window gives no count}.
        self.prepared_spell = None
        self.active_spells = {}
        self.spells_updated = False  # either changed: the "spells" stream (#175)
        self._spell_text = None
        self._perc_text = None
        # The other players in the room, by name, from the "room
        # players" component the game sends with every room and on
        # every change (#178): a room someone is already hunting or
        # training in is theirs, and a script arriving there moves on.
        self.room_players = []
        self.players_updated = False
        self._players_text = None
        # The room's creatures and NPCs, from the "room objs" component
        # the game sends with every room and on every change: the bolded
        # names in order, articles kept ("a musk hog", "a musk hog",
        # "Forest Warden Hengwild"); unbolded entries are scenery. What
        # dr-scripts' DRRoom.npcs holds and its climb? rule counts (three
        # or more = a crowd, #178). Cleared on a room change like
        # hostiles, until the fresh listing arrives.
        self.room_creatures = []
        self.creatures_updated = False
        self._objs_names = None  # the names read so far, inside room objs
        self._objs_bold = None  # the bold run being read, inside room objs
        # Rested experience, from the footer the exp window pushes on
        # every pulse (<component id='exp rexp'>Rested EXP Stored: 5:42
        # hours  Usable This Cycle: 5:42 hours  Cycle Refreshes: 21
        # hours</component>, 1535 times in one session, #176): {stored,
        # usable, refresh} in minutes (client/game/rested.py), None
        # until the first pulse.
        self.rested = None
        self.rested_updated = False
        self._rested_text = None
        # Vitals percentages from the minivitals dialog's progress bars:
        # {"health": 100, "stamina": 95, ...}; casters also get "mana".
        # The game sends partial updates, so this dict accumulates.
        self.vitals = {}
        self.vitals_updated = False
        self._vitals_dialog = False
        # The injuries panel, <dialogData id="injuries">: one <image> per
        # body part whose name is the part's own id when unhurt and
        # "Injury<N>" / "Scar<N>" when not (captured 2026-09-11, #163):
        # {part: ("wound" | "scar", level)}, hurt parts only. Pushed by
        # the game on every change, so it is current without HEALTH;
        # coarser than HEALTH's wording (client/game/wounds.py).
        self.injuries = {}
        self.injuries_updated = False
        self._injuries_dialog = False
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
        # What each hand holds, from <left exist='...' noun='...'>oak-
        # hafted handaxe</left> and <right>...</right>: None when empty,
        # else {"noun", "exist", "name"}. The game sends one tag per hand
        # as that hand changes (a pair at login); the noun is what GET,
        # STOW and the climb penalty line use (#159 — the felled tree
        # went only once the hands were empty, and nothing tracked them).
        self.left_hand = None
        self.right_hand = None
        self.hands_updated = False
        self._hand = None  # (side, attributes, text) while inside the tag

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
        if self._spell_text is not None:
            self._spell_text += text_string
        if self._perc_text is not None:
            # The engine feeds the window one line at a time with the
            # newline split off, so each piece is a line: give it back,
            # or two spells read as one (#175).
            self._perc_text += text_string
            if not text_string.endswith("\n"):
                self._perc_text += "\n"
        if self._players_text is not None:
            self._players_text += text_string
        if self._objs_bold is not None:
            self._objs_bold.append(text_string)
        if self._rested_text is not None:
            self._rested_text += text_string
        if self._hand is not None:
            self._hand[2].append(text_string)

    def start(self, name: str, attributes: dict):
        self.active_tags.append(name)

        if name in ("left", "right"):
            self._hand = (name, dict(attributes), [])
        elif name == "playerID":
            self.player_id = attributes["id"]
        elif name == "style":
            self.current_style = attributes["id"]
        elif name == "prompt":
            self.server_time = int(attributes["time"])
            self.prompt_count += 1
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
            self.room_creatures = []
        elif name == "roundTime":
            self.roundtime = int(attributes["value"])
        elif name == "castTime":
            self.casttime = int(attributes["value"])
        elif name == "spell":
            self._spell_text = ""
        elif name == "pushStream" and attributes.get("id") == "percWindow":
            self._perc_text = ""
        elif name == "popStream" and self._perc_text is not None:
            spells, self._perc_text = _active_spells(self._perc_text), None
            if spells != self.active_spells:
                self.active_spells = spells
                self.spells_updated = True
        elif name == "clearStream" and attributes.get("id") == "percWindow":
            # The wipe comes alone once the last spell has run out.
            if self.active_spells:
                self.active_spells = {}
                self.spells_updated = True
        elif name == "dialogData":
            self._vitals_dialog = attributes.get("id") == "minivitals"
            self._injuries_dialog = attributes.get("id") == "injuries"
        elif name == "image" and self._injuries_dialog:
            self._note_injury(attributes.get("id", ""), attributes.get("name", ""))
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
            elif ident == "room players":
                self._players_text = ""
            elif ident == "room objs":
                self._objs_names, self._objs_bold = [], None
            elif ident == "exp rexp":
                self._rested_text = ""
        elif name == "pushBold" and self._objs_names is not None:
            self._objs_bold = []
        elif name == "popBold" and self._objs_names is not None:
            creature = "".join(self._objs_bold or []).strip()
            self._objs_bold = None
            if creature:
                self._objs_names.append(creature)
        elif name == "crtrStatus":
            # The first tag since the last swap opens a fresh staged
            # set — the burst is the enumeration (#85), nothing else
            # is. Non-hostile tags join the burst without an entry, so
            # a creature re-announced harmless drops out at the swap.
            if self._staged_hostiles is None:
                self._staged_hostiles = {}
            # A corpse keeps hostile="1" and adds dead="1" (captured
            # 2026-09-05: a hunter that counted it swung at it five
            # times, "The ship's rat is already quite dead."). Dead is
            # not hostile.
            if attributes.get("hostile") == "1" and attributes.get("dead") != "1":
                self._staged_hostiles[attributes.get("exist", "")] = (
                    attributes.get("disengaged") != "1"
                )
        elif name == "streamWindow" and attributes.get("id") == "room":
            subtitle = attributes.get("subtitle", "")
            if subtitle.startswith(" - "):
                self.room_title = subtitle[3:].strip()

    def _note_injury(self, part, name):
        """One <image> of the injuries panel: name == part means clean;
        Injury<N> a fresh wound, Scar<N> a scar (the scar form is the
        pattern's assumption until captured). Skins and bars in the
        same dialog carry other names and are ignored."""
        if not part or part in ("injuredSkin", "healthSkin") or not name:
            return
        match = _INJURY.match(name)
        if match:
            level = int(match.group(2))
            state = ("scar" if match.group(1).lower() == "scar" else "wound", level)
            if self.injuries.get(part) != state:
                self.injuries[part] = state
                self.injuries_updated = True
        elif name == part:
            if self.injuries.pop(part, None) is not None:
                self.injuries_updated = True

    def end(self, name: str):
        if name == "dialogData":
            self._injuries_dialog = False
        if name == "component" and self._players_text is not None:
            players, self._players_text = _players(self._players_text), None
            if players != self.room_players:
                self.room_players = players
                self.players_updated = True
        if name == "component" and self._rested_text is not None:
            rested, self._rested_text = parse_rested(self._rested_text), None
            if rested is not None and rested != self.rested:
                self.rested = rested
                self.rested_updated = True
        if name == "component" and self._objs_names is not None:
            creatures, self._objs_names, self._objs_bold = self._objs_names, None, None
            if creatures != self.room_creatures:
                self.room_creatures = creatures
                self.creatures_updated = True
        if name == "spell" and self._spell_text is not None:
            text, self._spell_text = self._spell_text.strip(), None
            prepared = None if text.lower() in ("", "none") else text
            if prepared != self.prepared_spell:
                self.prepared_spell = prepared
                self.spells_updated = True
        if name in ("left", "right") and self._hand is not None:
            side, attributes, pieces = self._hand
            self._hand = None
            text = "".join(pieces).strip()
            held = (
                None
                if not text or text.lower() == "empty"
                else {
                    "noun": attributes.get("noun") or text.split()[-1],
                    "exist": attributes.get("exist"),
                    "name": text,
                }
            )
            if held != getattr(self, f"{side}_hand"):
                setattr(self, f"{side}_hand", held)
                self.hands_updated = True
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
        if BELL in line:
            segments.append(("bell", "", ""))
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
                    piece = _CONTROL_CHARS.sub("", piece)
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
