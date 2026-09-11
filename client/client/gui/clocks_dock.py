"""The clocks panel: what time it is everywhere that matters.

Elanthia (computed from server time by client/eltime.py; ;clock
calibrates through settings), the three game moons with their phase
and whether they are up, Stockholm and Chicago wall time, and Earth's
moon when the for-fun Settings row is on. Ticks once a second and
re-reads the calibration once a minute, so a ;clock run in the
session process reaches the window without a restart. Split out of
client_gui.py, which wraps it in the "Clocks" dock and feeds it the
"timesync" delta.
"""

from datetime import datetime
from time import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

from client import eltime
from client.settings import load_settings

CITIES = (("Stockholm", "Europe/Stockholm"), ("Chicago", "America/Chicago"))
ROWS = ("Elanthia", "Moons", "Stockholm", "Chicago", "Earth's moon")
SETTINGS_REREAD_TICKS = 60


class ClocksPanel(QWidget):
    def __init__(self):
        super().__init__()
        # Server-minus-local clock seconds, from the "timesync" stream:
        # the Elanthian rows compute from server time (#102).
        self.server_delta = 0.0
        self._zones = {}
        for city, zone in CITIES:
            try:
                self._zones[city] = ZoneInfo(zone)
            except ZoneInfoNotFoundError:
                # No tzdata (a stale venv launched without a sync, #67):
                # a dashed row beats a client that dies before showing
                # a window.
                self._zones[city] = None
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        self.labels = {}
        self._earth_moon_widgets = ()
        for row, name in enumerate(ROWS):
            place = QLabel(name)
            place.setStyleSheet("color: #808090;")
            value = QLabel("")
            grid.addWidget(place, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, row, 1)
            self.labels[name] = value
            if name == "Earth's moon":
                self._earth_moon_widgets = (place, value)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(len(ROWS), 1)

        self._ticks = 0
        self.reload_settings()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def reload_settings(self):
        """;clock writes its calibration to settings from the session
        process; re-reading once a minute picks a fresh sync up without
        a restart. File → Settings calls it on save too."""
        values = load_settings()
        self._eltime_offset = values.get("eltime_offset_seconds") or 0
        self._moon_epochs = dict(eltime.DEFAULT_MOON_EPOCHS)
        self._moon_epochs.update(values.get("eltime_moons") or {})
        self._moon_rises = dict(eltime.DEFAULT_MOON_RISES)
        self._moon_rises.update(values.get("eltime_moon_rises") or {})
        for widget in self._earth_moon_widgets:
            widget.setVisible(bool(values.get("clocks_earth_moon")))

    def refresh(self):
        # Server time, not wall time: the "timesync" delta anchors the
        # Elanthian rows to the game's own clock (#102). Earth rows
        # below deliberately stay on local time.
        now = time() + self.server_delta
        line1, line2 = eltime.describe(eltime.elanthian_now(now, self._eltime_offset))
        self.labels["Elanthia"].setText(f"{line1}\n{line2}")
        bits, tips = [], []
        for name in eltime.MOON_NAMES:
            index = eltime.moon_phase(name, now, self._moon_epochs.get(name))
            title = name.capitalize()
            if index is None:
                bits.append(f"{title} ?")
                tips.append(f"{title}: not observed yet — ;clock under open sky")
            else:
                position = eltime.moon_position(name, now, self._moon_rises.get(name))
                # Up or down beside the phase (#105): ↑ above the horizon.
                mark = "" if position is None else (" ↑" if position[0] else " ↓")
                bits.append(f"{title} {eltime.PHASE_EMOJI[index]}{mark}")
                tips.append(f"{title}: {eltime.PHASES[index]}")
        self.labels["Moons"].setText("  ".join(bits))
        self.labels["Moons"].setToolTip("\n".join(tips))
        for city, zone in self._zones.items():
            self.labels[city].setText(
                datetime.now(zone).strftime("%H:%M:%S %a") if zone else "— (no tzdata)"
            )
        index = eltime.earth_moon_phase(now)
        self.labels["Earth's moon"].setText(
            f"{eltime.PHASE_EMOJI[index]} {eltime.PHASES[index]}"
        )
        self._ticks += 1
        if self._ticks % SETTINGS_REREAD_TICKS == 0:
            self.reload_settings()
