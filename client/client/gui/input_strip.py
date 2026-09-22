"""The strip around the input line: vitals bars, status badges, timers.

The command line with shell-style history, the roundtime and casttime
countdowns beside it, the status strip (posture, stunned, bleeding,
hidden, a red DEAD) that the scrolling text buries (#75), and the
vitals bars above — one per vital, created as the game first mentions
each. Split out of client_gui.py, which docks it at the bottom and
feeds it the "roundtime"/"casttime", "indicators" and "vitals" frames.
"""

from math import ceil
from time import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from client.ui.command_history import CommandHistory

# The status strip's badge colors: alarming states loud, sneaky
# states purple, posture plain. IconDEAD overrides everything.
INDICATOR_BADGES = {
    "IconSTUNNED": ("stunned", "#d8b465"),
    "IconBLEEDING": ("bleeding", "#e05252"),
    "IconWEBBED": ("webbed", "#8fc7e8"),
    "IconHIDDEN": ("hidden", "#b39ddb"),
    "IconINVISIBLE": ("invisible", "#b39ddb"),
    "IconJOINED": ("joined", "#808090"),
}
POSTURES = {
    "IconSTANDING": "standing",
    "IconKNEELING": "kneeling",
    "IconSITTING": "sitting",
    "IconPRONE": "prone",
}

# Vitals bar colors, roughly the classic frontends' scheme; ids the
# game hasn't taught us yet fall back to grey. The game calls the
# stamina bar "fatigue" on screen — so do we.
VITAL_COLORS = {
    "health": "#c0504d",
    "mana": "#4f81bd",
    "stamina": "#d8b465",
    "spirit": "#c8c8d4",
    "concentration": "#b39ddb",
}
VITAL_LABELS = {"stamina": "fatigue"}


class HistoryLineEdit(QLineEdit):
    """The command line with shell-style history: Up/Down browse what
    was typed, the unsent draft survives the browse (#76)."""

    def __init__(self):
        super().__init__()
        self.history = CommandHistory()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            shown = self.history.previous(self.text())
            if shown is not None:
                self.setText(shown)
            return
        if event.key() == Qt.Key.Key_Down:
            shown = self.history.next()
            if shown is not None:
                self.setText(shown)
            return
        super().keyPressEvent(event)


class OutlinedBar(QProgressBar):
    """A vitals bar whose label stays readable over any fill: the
    glyphs get a black outline behind a light face. Plain bar text
    washed out where chunk and text were both light — the spirit
    bar's near-white chunk was the reported case."""

    def __init__(self):
        super().__init__()
        self.setTextVisible(False)  # the label is painted here instead

    def paintEvent(self, event):
        super().paintEvent(event)  # groove and chunk, no text
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        text = self.text()
        metrics = QFontMetricsF(self.font())
        x = (self.width() - metrics.horizontalAdvance(text)) / 2
        y = (self.height() + metrics.ascent() - metrics.descent()) / 2
        path = QPainterPath()
        path.addText(x, y, self.font(), text)
        painter.strokePath(path, QPen(QColor(0, 0, 0), 3))
        painter.fillPath(path, QColor("#f0f0f2"))


# The command line has to read as the place to type at a glance,
# among the docks and the story (the operator, 2026-09-13): a prompt
# glyph in the roundtime amber before it, a rounded border that turns
# amber and thick while it has the focus, room around the text, a
# placeholder saying what it is, and its own dark slate ground with
# light text (the story's palette: amber, blue, purple on dark), so it
# reads as the console whatever the platform theme.
PROMPT_GLYPH = ">"
PROMPT_STYLE = "color: #d8b465; font-weight: bold; padding-left: 4px;"
INPUT_STYLE = (
    "QLineEdit { background: #23232e; color: #f0f0f2;"
    " selection-background-color: #d8b465; selection-color: #1c1c24;"
    " placeholder-text-color: #8a8a96;"
    " border: 1px solid #8a8a96; border-radius: 4px; padding: 4px 8px; }"
    " QLineEdit:focus { border: 2px solid #d8b465; padding: 3px 7px; }"
    " QLineEdit:disabled { color: #8a8a96; border: 1px dashed #8a8a96; }"
)
PLACEHOLDER = "command — Enter sends, Up/Down browse history"


class InputStrip(QWidget):
    """The vitals row over the input row; `input` is the line edit,
    `prompt` the glyph before it."""

    def __init__(self):
        super().__init__()
        self.input = HistoryLineEdit()
        self.input.setStyleSheet(INPUT_STYLE)
        self.input.setPlaceholderText(PLACEHOLDER)
        self.input.setClearButtonEnabled(True)
        self.prompt = QLabel(PROMPT_GLYPH)
        self.prompt.setStyleSheet(PROMPT_STYLE)
        # Disabled until the game connection is up: Qt's input hook pumps
        # events while login blocks on stdin, so keystrokes meant for the
        # terminal must not reach this field or trigger a send.
        self.input.setEnabled(False)
        # Roundtime/casttime countdowns sit beside the input line — the
        # classic frontends' RT bar, reduced to a number. The RT label
        # keeps its width when idle so the input field never shifts;
        # the casttime label appears on a caster's first cast.
        self.rt_label = QLabel("")
        self.rt_label.setFixedWidth(52)
        self.rt_label.setStyleSheet("color: #d8b465; font-weight: bold;")
        self.ct_label = QLabel("")
        self.ct_label.setFixedWidth(52)
        self.ct_label.setStyleSheet("color: #8fc7e8; font-weight: bold;")
        self.ct_label.setVisible(False)
        self._timer_ends = {"roundtime": 0.0, "casttime": 0.0}  # local clock
        self.rt_timer = QTimer(self)
        self.rt_timer.setInterval(200)
        self.rt_timer.timeout.connect(self._tick_timers)
        # The status strip: posture plus lit badges (stunned, bleeding,
        # hidden, ...), DEAD in alert red over everything — the state
        # the scrolling text buries (#75).
        self.status_strip = QLabel("")
        self.status_strip.setMinimumWidth(70)
        # The maintenance countdown (#277): "shutdown in N min" in the
        # alert red, ticking with the roundtime timer.
        self.shutdown_label = QLabel("")
        self.shutdown_label.setStyleSheet("color: #e05252; font-weight: bold;")
        self._shutdown_end = 0.0  # local clock
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 0, 4, 0)
        row_layout.addWidget(self.status_strip)
        row_layout.addWidget(self.shutdown_label)
        row_layout.addWidget(self.rt_label)
        row_layout.addWidget(self.ct_label)
        row_layout.addWidget(self.prompt)
        row_layout.addWidget(self.input, 1)
        # Vitals bars above the input line — one bar per vital, created
        # as the game first mentions each (casters gain a mana bar the
        # moment it appears in the stream). Hidden until data arrives.
        self.vitals_bars = {}
        self._vitals_row = QWidget()
        self._vitals_layout = QHBoxLayout(self._vitals_row)
        self._vitals_layout.setContentsMargins(4, 2, 4, 0)
        self._vitals_layout.setSpacing(4)
        self._vitals_row.setVisible(False)
        column_layout = QVBoxLayout(self)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(2)
        column_layout.addWidget(self._vitals_row)
        column_layout.addWidget(row)

    def update_timer(self, stream: str, text: str):
        """A roundtime/casttime frame: "end<TAB>server now" in server
        epoch seconds. The difference is the duration, anchored to the
        local clock at receipt — server-vs-local skew cancels out."""
        try:
            end, server_now = (int(part) for part in text.split("\t"))
        except ValueError:
            return
        self._timer_ends[stream] = time() + max(0, end - server_now)
        self._tick_timers()
        # Only a countdown still in the future needs the ticker — a
        # stale frame (reattach backlog has none, but belt and braces)
        # must not wake it.
        if max(self._timer_ends.values()) > time() and not self.rt_timer.isActive():
            self.rt_timer.start()

    def update_shutdown(self, text: str):
        """A "shutdown" frame (#277): "end<TAB>server now" in server epoch
        seconds, like a roundtime frame; the label counts the minutes
        down until the game goes."""
        try:
            end, server_now = (int(part) for part in text.split("\t"))
        except ValueError:
            return
        self._shutdown_end = time() + max(0, end - server_now)
        self._tick_timers()
        if not self.rt_timer.isActive():
            self.rt_timer.start()

    def shutdown_text(self, now=None):
        """The countdown's wording, "" when none is announced."""
        if not self._shutdown_end:
            return ""
        left = self._shutdown_end - (time() if now is None else now)
        if left <= 0:
            return "shutdown now"
        return f"shutdown in {ceil(left / 60)} min"

    def update_indicators(self, text: str):
        """An "indicators" frame: the active indicator ids, space
        separated, full state each time."""
        active = set(text.split())
        if "IconDEAD" in active:
            self.status_strip.setText('<b style="color:#e05252">DEAD</b>')
            return
        parts = []
        posture = next(
            (word for icon, word in POSTURES.items() if icon in active), None
        )
        if posture:
            parts.append(f'<span style="color:#808090">{posture}</span>')
        for icon, (word, color) in INDICATOR_BADGES.items():
            if icon in active:
                parts.append(f'<b style="color:{color}">{word}</b>')
        self.status_strip.setText("&nbsp;".join(parts))

    def update_vitals(self, text: str):
        """A "vitals" frame: "health 100 stamina 95 ..." — the full
        current set every time (the engine accumulates the game's
        partial updates)."""
        parts = text.split()
        for vital, value in zip(parts[::2], parts[1::2]):
            try:
                value = int(value)
            except ValueError:
                continue
            bar = self.vitals_bars.get(vital)
            if bar is None:
                bar = OutlinedBar()
                bar.setRange(0, 100)
                bar.setFixedHeight(16)
                bar.setFormat(f"{VITAL_LABELS.get(vital, vital)} %p%")
                color = VITAL_COLORS.get(vital, "#808090")
                bar.setStyleSheet(
                    "QProgressBar { border: 1px solid #33333d;"
                    " text-align: center; }"
                    f"QProgressBar::chunk {{ background: {color}; }}"
                )
                self._vitals_layout.addWidget(bar)
                self.vitals_bars[vital] = bar
            bar.setValue(value)
        if self.vitals_bars:
            self._vitals_row.setVisible(True)

    def _tick_timers(self):
        now = time()
        remaining_rt = ceil(self._timer_ends["roundtime"] - now)
        remaining_ct = ceil(self._timer_ends["casttime"] - now)
        self.rt_label.setText(f"RT {remaining_rt}" if remaining_rt > 0 else "")
        if remaining_ct > 0:
            self.ct_label.setVisible(True)
            self.ct_label.setText(f"CT {remaining_ct}")
        else:
            self.ct_label.setText("")
        self.shutdown_label.setText(self.shutdown_text(now))
        if remaining_rt <= 0 and remaining_ct <= 0 and self._shutdown_end <= now:
            self.rt_timer.stop()
