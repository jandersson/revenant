"""The Spells dock: the running spells with their time left, counting down.

The game rewrites its Spells window on every pulse — `<clearStream
id="percWindow"/>` then "Heroic Strength  (10 roisaen)" lines — and the
parser keeps it as `active_spells` ({name: minutes left, or None when
the window gives no count}) beside `prepared_spell` from the `<spell>`
tag. The engine emits the "spells" stream on every change of either:
"prepared<TAB>name" first while a spell is prepared, then one
"name<TAB>minutes" line per running spell (minutes "" for no count),
"" when nothing runs or is prepared (#175). This dock draws one row per
spell and ticks the count down by the second between pulses (a roisan
is a real minute, client/game/eltime.py), the prepared spell above them
in its own colour, and "No spells running" when the list is empty. The
raw window text itself is no longer shown anywhere: this is its view.
"""

import math
from time import monotonic

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

TICK_MS = 1000
EMPTY_TEXT = "No spells running"
SPELL_STYLE = "padding: 2px 6px;"
PREPARED_STYLE = "color: #d8b465; font-weight: bold; padding: 2px 6px;"
EMPTY_STYLE = "color: #4a4a55; padding: 2px 6px;"


def parse_frame(text):
    """(prepared spell or None, [(name, minutes or None), ...]) from a
    "spells" frame; (None, []) when nothing runs."""
    prepared = None
    spells = []
    for line in text.splitlines():
        name, _, count = line.partition("\t")
        if not name:
            continue
        if name == "prepared" and prepared is None:
            prepared = count.strip() or None
            continue
        try:
            minutes = int(count) if count.strip() else None
        except ValueError:
            minutes = None
        spells.append((name, minutes))
    return prepared, spells


def countdown(seconds):
    """ "9:40" from seconds left, never below "0:00"; a fraction rounds
    up, so a fresh ten-minute count reads 10:00 for its first second."""
    seconds = max(0, math.ceil(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class SpellsPanel(QWidget):
    """One label per running spell, the prepared spell on top, a timer
    ticking the counts down between pulses. `clock` is injectable for
    tests; `ticking=False` leaves the timer off (tests call tick())."""

    def __init__(self, clock=monotonic, ticking=True):
        super().__init__()
        self._clock = clock
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(2)
        self.prepared = None
        self.spells = []  # [(name, seconds left at frame time, or None)]
        self.frame_at = clock()
        self.rows = []
        self.prepared_label = QLabel()
        self.prepared_label.setStyleSheet(PREPARED_STYLE)
        self.empty_label = QLabel(EMPTY_TEXT)
        self.empty_label.setStyleSheet(EMPTY_STYLE)
        self._layout.addWidget(self.prepared_label)
        self._layout.addWidget(self.empty_label)
        self._layout.addStretch(1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        if ticking:
            self.timer.start(TICK_MS)
        self.show_frame("")

    def show_frame(self, text):
        """A "spells" frame: the rows rebuilt, the counts restarted from
        now."""
        self.prepared, spells = parse_frame(text)
        self.frame_at = self._clock()
        self.spells = [
            (name, None if minutes is None else minutes * 60)
            for name, minutes in spells
        ]
        for row in self.rows:
            self._layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        for index, (name, _) in enumerate(self.spells):
            label = QLabel(name)
            label.setStyleSheet(SPELL_STYLE)
            self._layout.insertWidget(1 + index, label)
            self.rows.append(label)
        self.prepared_label.setText(
            f"prepared: {self.prepared}" if self.prepared else ""
        )
        self.prepared_label.setHidden(not self.prepared)
        self.empty_label.setHidden(bool(self.spells))
        self.tick()

    def tick(self):
        """Every row's text from the seconds left since the frame."""
        elapsed = self._clock() - self.frame_at
        for label, (name, seconds) in zip(self.rows, self.spells):
            if seconds is None:
                label.setText(name)
            else:
                label.setText(f"{name}  {countdown(seconds - elapsed)}")

    def lines(self):
        """The rows as text, top to bottom."""
        return [label.text() for label in self.rows]
