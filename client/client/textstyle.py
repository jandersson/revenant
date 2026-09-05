"""How a frame's style renders, without a toolkit: the rules the
terminal frontend draws by, testable headless.

The session hands frontends (text, stream, style) segments. `style` is
"" for plain text, a game style name (roomName, speech, ...), our own
"alert" and "sent", "clear" (wipe that stream's window), or
"link:<command>" for a clickable command. STYLES maps a name to (bold,
hex color) — the same table the PyQt6 GUI keeps in client_gui.py; keep
them in step. render() turns one segment plus the user's highlight
rules into runs of (text, bold, color, link) a frontend paints in
order; status_line() folds the state frames (character, vitals,
indicators, room, roundtime) into one line for a status bar.
"""

from client.highlights import spans

STYLES = {
    "roomName": (True, "#d8b465"),
    "bold": (True, None),
    "speech": (False, "#8fc7e8"),
    "whisper": (False, "#8fc7e8"),
    "thought": (False, "#b39ddb"),
    "alert": (True, "#e05252"),
    "sent": (False, "#8a8a96"),
}
LINK_COLOR = "#8fc7e8"

# Which state frames the status line shows, and in what order.
STATUS_VITALS = ("health", "stamina", "spirit", "concentration", "mana")
POSTURES = {
    "IconSTANDING": "standing",
    "IconKNEELING": "kneeling",
    "IconSITTING": "sitting",
    "IconPRONE": "prone",
}
BADGES = {
    "IconSTUNNED": "stunned",
    "IconBLEEDING": "bleeding",
    "IconWEBBED": "webbed",
    "IconHIDDEN": "hidden",
    "IconINVISIBLE": "invisible",
    "IconJOINED": "joined",
}


def base_style(style):
    """(bold, color, link) for a segment's style name."""
    if style.startswith("link:"):
        return False, LINK_COLOR, style[5:]
    bold, color = STYLES.get(style, (False, None))
    return bold, color, None


def render(text, style, rules=()):
    """Runs of (text, bold, color, link) for one segment: the base style
    everywhere, a highlight rule's color and boldness over the spans it
    matches (the GUI's rule: a highlight wins the color, the base keeps
    the link)."""
    bold, color, link = base_style(style)
    runs = []
    cursor = 0
    for start, end, rule in spans(text, rules):
        if start > cursor:
            runs.append((text[cursor:start], bold, color, link))
        runs.append(
            (
                text[start:end],
                bool(rule.get("bold", bold)),
                rule.get("color") or color,
                link,
            )
        )
        cursor = end
    if cursor < len(text):
        runs.append((text[cursor:], bold, color, link))
    return runs


class Status:
    """The state a status bar shows, fed one frame at a time."""

    def __init__(self):
        self.character = ""
        self.room = ""
        self.vitals = {}
        self.indicators = set()
        self.connection = "connecting"

    def feed(self, text, stream):
        """True when the frame changed something a status bar shows."""
        if stream == "character":
            self.character = text.strip()
        elif stream == "room":
            _, _, title = text.partition("\t")
            self.room = title.strip()
        elif stream == "vitals":
            parts = text.split()
            for vital, value in zip(parts[::2], parts[1::2]):
                if value.lstrip("-").isdigit():
                    self.vitals[vital] = int(value)
        elif stream == "indicators":
            self.indicators = set(text.split())
        else:
            return False
        return True

    def line(self, roundtime=0):
        """One line: name, room, vitals, posture and badges, roundtime."""
        parts = [self.character or "—"]
        if self.room:
            parts.append(self.room)
        vitals = [
            f"{vital[:2]} {self.vitals[vital]}%"
            for vital in STATUS_VITALS
            if vital in self.vitals
        ]
        if vitals:
            parts.append("  ".join(vitals))
        if "IconDEAD" in self.indicators:
            parts.append("DEAD")
        else:
            posture = next(
                (word for icon, word in POSTURES.items() if icon in self.indicators),
                None,
            )
            badges = [word for icon, word in BADGES.items() if icon in self.indicators]
            if posture:
                parts.append(posture)
            parts.extend(badges)
        if roundtime > 0:
            parts.append(f"RT {roundtime}")
        parts.append(self.connection)
        return " | ".join(parts)
