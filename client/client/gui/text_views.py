"""The game text views and their fonts.

A read-only view whose <d> command links are clickable (a click sends
the command), the Experience dock's fixed-pitch dashboard treatment,
and the per-view font resolution over Settings (client/ui/textfont.py).
Split out of client_gui.py, which builds one view for the story and
one per stream dock and appends the styled text.
"""

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QTextBrowser

from client.ui.textfont import view_font


class GameTextView(QTextBrowser):
    """`on_link(command)` gets a clicked <d> link's command; the window
    installs itself as the event filter so a click or a keystroke on
    the view hands focus (and the key) to the input line (#150)."""

    def __init__(self, on_link, event_filter):
        super().__init__()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(lambda url: on_link(url.toString().strip()))
        self.installEventFilter(event_filter)


def fixed_pitch_font():
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def style_experience_view(view):
    """The exp dashboard is column-aligned text, and an empty one must
    not look like a missing one."""
    view.setFont(fixed_pitch_font())
    view.setPlaceholderText(
        "No skills learning right now.\nTrain something and this fills in live."
    )


def font_for(settings, view, default_font):
    """Settings' font for one view (#118), resolved through
    textfont.view_font so a dock_fonts override wins for that view
    (#132). The Experience dock starts from the fixed-pitch font and
    every other view from the platform default the window kept; a
    family named in Settings, global or per-view, replaces either."""
    family, size = view_font(settings, view)
    font = fixed_pitch_font() if view == "Experience" else QFont(default_font)
    if family:
        font.setFamily(family)
    if size:
        font.setPointSize(size)
    return font
