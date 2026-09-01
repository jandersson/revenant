import argparse
import sys
from datetime import datetime
from math import ceil
from pathlib import Path
from threading import Thread
from time import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtCore import QSettings, QSize, Qt, QTimer, pyqtSignal

from client import crashguard, eltime, reader, window_layout
from client.command_history import CommandHistory
from client.core import Engine
from client.client_logger import ClientLogger
from client.gui.map_dock import MapView
from client.highlights import highlights_path, load_rules, spans
from client.session import AttachedEngine, DEFAULT_HOST, DEFAULT_PORT
from client.settings import load_settings, save_settings, setting, settings_path

ICON_PATH = str(Path(__file__).with_name("revenant.svg"))

# Windows groups taskbar buttons by AppUserModelID, defaulting to the exe
# path — which for us is pythonw.exe, shared with every other Python GUI.
# Claiming our own ID (matching the one tools/install_shortcut.ps1 stamps
# on the Start Menu shortcut) merges the running window with the pinned
# icon instead of splitting into two buttons.
APP_USER_MODEL_ID = "revenant.client"

DASHBOARD_URL = "http://127.0.0.1:8050"

# Qt WebEngine wants importing before the QApplication exists; absence
# is fine (the dashboard falls back to the system browser).
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover — depends on the install
    QWebEngineView = None


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


def claim_taskbar_identity():
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)


class ClientGUI(QMainWindow, ClientLogger):
    # Game text arrives on the reader thread, but Qt widgets may only be
    # touched from the GUI thread — hand it over via a queued signal.
    # Args: text, stream id ("" = main window), style ("" = plain).
    game_text = pyqtSignal(str, str, str)

    # Connection status changes also arrive on worker threads (the reader
    # noticing EOF, the reconnect worker) — same rule, same remedy.
    connection_state = pyqtSignal(str)

    # The map database loads on a worker thread (13MB of JSON must not
    # freeze startup); the loaded db arrives here. Args: db (or None
    # when there is none on disk), the local survey overlay's room ids.
    map_ready = pyqtSignal(object, object)

    # style id -> (bold, color). The game's own styling markers, rendered
    # the way Stormfront players expect: amber room names, blue speech.
    STYLE_FORMATS = {
        "roomName": (True, "#d8b465"),
        "bold": (True, None),
        "speech": (False, "#8fc7e8"),
        "whisper": (False, "#8fc7e8"),
        "thought": (False, "#b39ddb"),
        # Ours, not the game's: markup-less lines that must not be
        # missed (the idle check) — see xml_data._ALERT_LINE.
        "alert": (True, "#e05252"),
        # Sent commands, dim: your own (echoed locally) and everyone
        # else's on this session (broadcast by the session).
        "sent": (False, "#8a8a96"),
    }

    # stream id -> dock window title; streams not listed here fall through
    # to the main window.
    STREAM_WINDOWS = {
        "thoughts": "Thoughts",
        "chatter": "Thoughts",
        "percWindow": "Spells",
        "logons": "Arrivals",
        "death": "Deaths",
        "exp": "Experience",
    }

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

    # Compass rose geometry: unit-circle offsets for the eight wind
    # directions around a central OUT, with up/down stacked beside.
    COMPASS_POINTS = {
        "n": (0.0, -1.0),
        "ne": (0.707, -0.707),
        "e": (1.0, 0.0),
        "se": (0.707, 0.707),
        "s": (0.0, 1.0),
        "sw": (-0.707, 0.707),
        "w": (-1.0, 0.0),
        "nw": (-0.707, -0.707),
    }
    COMPASS_ARROWS = {
        "n": "↑",
        "ne": "↗",
        "e": "→",
        "se": "↘",
        "s": "↓",
        "sw": "↙",
        "w": "←",
        "nw": "↖",
    }

    def __init__(self, engine=None):
        super().__init__()
        self.log.debug("Initializing ClientGUI instance")
        self.status_bar = self.statusBar()
        self.input_dock = QDockWidget()
        self.highlight_rules = load_rules()
        # Who is playing, from the "character" stream — names the title
        # bar and scopes the saved window layout (#74). The layout is
        # applied once, on first identification: a reattach re-states
        # the character and must not stomp a live arrangement.
        self._character = None
        self._layout_applied = False
        # Server-minus-local clock seconds, from the "timesync" stream:
        # the Elanthian clock computes from server time (#102).
        self._server_delta = 0.0
        self.client = engine if engine is not None else Engine()
        self.__init_ui()
        self.game_text.connect(self.dispatch_game_text)
        self.connection_state.connect(self.status_bar.showMessage)
        # An exception escaping any Qt slot would abort the whole
        # process — PyQt spares only apps with their own excepthook
        # (#94). Emitters go through the queued signals above, so the
        # hook is safe from any thread.
        crashguard.install(
            self.log,
            emit_text=lambda text: self.game_text.emit(f"{text}\n", "", "alert"),
            emit_status=self.connection_state.emit,
        )
        self._reader_thread = None
        self.client.connect()
        self.status_bar.showMessage(getattr(self.client, "description", "Connected"))
        self.input.setEnabled(True)
        self.input.setFocus()
        self.gui_reactor()

    def __init_ui(self):
        self.log.debug("Initializing UI")
        self.setWindowTitle("Revenant")
        self.setWindowIcon(QIcon(ICON_PATH))
        # TODO: Update this with some sort of connection string when connected
        self.status_bar.showMessage("Not Connected")

        self.__add_output_window()
        self.__add_stream_docks()
        self.__add_compass_dock()
        self.__add_clocks_dock()
        self.__add_map_dock()
        self.__add_input_field()

        reconnect_action = QAction("&Reconnect", self)
        reconnect_action.setShortcut("Ctrl+R")
        reconnect_action.setStatusTip(
            "Start or attach to a game session after a disconnect"
        )
        reconnect_action.triggered.connect(self.reconnect)

        settings_action = QAction("&Settings…", self)
        settings_action.setStatusTip(
            "Autostart and window-close behavior (~/.revenant/settings.json)"
        )
        settings_action.triggered.connect(self.edit_settings)

        detach_action = QAction("&Detach", self)
        detach_action.setShortcut("Ctrl+D")
        detach_action.setStatusTip(
            "Close this window but stay logged in (reattach with a new launch)"
        )
        detach_action.triggered.connect(self.detach)

        # Exit goes through close() so closeEvent runs: geometry is
        # saved and the game gets its quit.
        exit_action = QAction(QIcon("exit.png"), "&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Quit the game and close the window")
        exit_action.triggered.connect(self.close)

        view_status_bar = QAction("Status Bar", self, checkable=True)
        view_status_bar.setStatusTip("Show the status bar")
        view_status_bar.setChecked(True)
        view_status_bar.triggered.connect(self.toggle_menu)

        history_action = QAction("Experience &History", self)
        history_action.setStatusTip(
            "The beholder dashboard: mindstate and rank over time"
        )
        history_action.triggered.connect(self.show_experience_history)

        beholder_action = QAction("Beholder in Bro&wser", self)
        beholder_action.setStatusTip(
            f"Open the experience dashboard in your browser ({DASHBOARD_URL})"
        )
        beholder_action.triggered.connect(self.open_beholder)

        edit_highlights_action = QAction("Edit High&lights…", self)
        edit_highlights_action.setStatusTip(
            f"Add and edit highlight patterns ({highlights_path()})"
        )
        edit_highlights_action.triggered.connect(self.edit_highlights)

        highlights_action = QAction("Reload Highlights", self)
        highlights_action.setStatusTip(
            f"Re-read your highlight patterns from {highlights_path()}"
        )
        highlights_action.triggered.connect(self.reload_highlights)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(reconnect_action)
        file_menu.addAction(settings_action)
        file_menu.addAction(detach_action)
        file_menu.addAction(exit_action)
        view_menu = menubar.addMenu("View")
        view_menu.addAction(view_status_bar)
        view_menu.addAction(history_action)
        view_menu.addAction(beholder_action)
        view_menu.addAction(edit_highlights_action)
        view_menu.addAction(highlights_action)
        view_menu.addSeparator()
        for dock in self.stream_docks.values():
            view_menu.addAction(dock.toggleViewAction())

        # Window size and dock layout persist between launches. The
        # legacy unscoped pair opens the window before the character is
        # known; the character's own layout takes over the moment the
        # "character" frame names who is playing (#74).
        settings = QSettings("revenant", "revenant")
        if geometry := settings.value("geometry"):
            self.restoreGeometry(geometry)
        if state := settings.value("windowState"):
            self.restoreState(state)

        self.show()

    def _restore_character_layout(self, name):
        """This character's own saved arrangement, if any — without one
        the legacy layout restored at startup simply stays."""
        settings = QSettings("revenant", "revenant")
        geometry_key, state_key = window_layout.layout_keys(name)
        if geometry := settings.value(geometry_key):
            self.restoreGeometry(geometry)
        if state := settings.value(state_key):
            self.restoreState(state)

    def detach(self):
        """File → Detach: close the window, stay logged in. The session
        keeps the game connection; a new launch reattaches to it."""
        self._detaching = True
        self.close()

    def closeEvent(self, event):
        settings = QSettings("revenant", "revenant")
        pairs = window_layout.save_pairs(
            self._character, self.saveGeometry(), self.saveState()
        )
        for key, value in pairs.items():
            settings.setValue(key, value)
        # Closing the window means leaving the game — send quit so the
        # character logs out instead of lingering to a link-death, and
        # the session winds down on the resulting EOF. File → Detach
        # skips this, and Settings can turn it off (quit_on_close).
        if not getattr(self, "_detaching", False) and setting("quit_on_close"):
            connection = getattr(self.client, "connection", None)
            if connection is not None:
                try:
                    connection.write(b"quit\n")
                except OSError:
                    pass  # already disconnected: nothing to quit
        super().closeEvent(event)

    def _make_view(self):
        """A read-only text view whose <d> command links are clickable:
        a click sends the command to the game (QTextBrowser so anchors
        fire without navigating anywhere)."""
        view = QTextBrowser()
        view.setOpenLinks(False)
        view.setOpenExternalLinks(False)
        view.anchorClicked.connect(self._follow_link)
        return view

    def _follow_link(self, url):
        command = url.toString().strip()
        if command:
            self.write(command)

    def __add_output_window(self):
        self.main_window = self._make_view()
        self.setCentralWidget(self.main_window)

    def __add_stream_docks(self):
        """One dock window per title in STREAM_WINDOWS, stacked on the right."""
        self.stream_docks = {}
        self.stream_windows = {}
        for title in dict.fromkeys(self.STREAM_WINDOWS.values()):
            dock = QDockWidget(title)
            dock.setObjectName(title)  # saveState() needs unique names
            view = self._make_view()
            if title == "Experience":
                # The exp dashboard is column-aligned text.
                view.setFont(
                    QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
                )
                # An empty dashboard must not look like a missing one.
                view.setPlaceholderText(
                    "No skills learning right now.\n"
                    "Train something and this fills in live."
                )
            dock.setWidget(view)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            self.stream_docks[title] = dock
        for stream, title in self.STREAM_WINDOWS.items():
            self.stream_windows[stream] = self.stream_docks[title].widget()

    def __add_compass_dock(self):
        """Clickable exits drawn as a compass rose: eight arrows on a
        ring around OUT, up/down beside, lit amber when the room's
        compass tag offers the exit and dimmed to the ring otherwise.

        The rose lays itself out for whatever space the dock grants —
        a fixed-size rose in an elastic wrapper painted over the
        neighboring docks whenever the column got crowded."""
        gui = self

        class Rose(QWidget):
            def sizeHint(self):
                return QSize(190, 150)

            def minimumSizeHint(self):
                return QSize(140, 104)

            def resizeEvent(self, event):
                gui._layout_compass(self.width(), self.height())
                super().resizeEvent(event)

        rose = Rose()
        rose.setStyleSheet(
            "QPushButton { background: #d8b465; color: #1c1c24;"
            "  font-weight: bold; border: 1px solid #8a733f; }"
            "QPushButton:disabled { background: #23232b; color: #4a4a55;"
            "  border: 1px solid #33333d; }"
        )
        self.compass_buttons = {}
        for direction in self.COMPASS_POINTS:
            self._add_compass_button(rose, direction, self.COMPASS_ARROWS[direction])
        self._add_compass_button(rose, "out", "out")
        self._add_compass_button(rose, "up", "up")
        self._add_compass_button(rose, "down", "dn")

        dock = QDockWidget("Compass")
        dock.setObjectName("Compass")
        dock.setWidget(rose)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        # Registering under stream_docks gives it a View-menu toggle.
        self.stream_docks["Compass"] = dock

    def _add_compass_button(self, rose, name, label):
        button = QPushButton(label, rose)
        button.setEnabled(False)
        button.setToolTip(name)
        button.clicked.connect(lambda checked=False, d=name: self.write(d))
        self.compass_buttons[name] = button

    def _layout_compass(self, width, height):
        """Fit the rose to the dock's current size: the ring and the
        buttons scale down before anything can spill onto a neighbor."""
        side = max(22, min(36, height * 24 // 100))
        updn = max(18, side * 5 // 6)
        right_column = updn + 8
        ring = max(
            24,
            min((height - side) // 2 - 2, (width - right_column - side) // 2 - 2),
        )
        center_x = (width - right_column) // 2
        center_y = height // 2

        def place(name, x, y, size):
            button = self.compass_buttons[name]
            button.setGeometry(int(x - size / 2), int(y - size / 2), size, size)
            button.setStyleSheet(f"border-radius: {size // 2}px;")

        for direction, (dx, dy) in self.COMPASS_POINTS.items():
            place(direction, center_x + dx * ring, center_y + dy * ring, side)
        place("out", center_x, center_y, side)
        offset = max(updn, side * 7 // 9)
        place("up", width - updn // 2 - 4, center_y - offset, updn)
        place("down", width - updn // 2 - 4, center_y + offset, updn)

    def update_compass(self, dirs_text: str):
        available = set(dirs_text.split())
        for direction, button in self.compass_buttons.items():
            button.setEnabled(direction in available)

    def __add_map_dock(self):
        """The visual map (#56): the community map drawn around the
        character, following the "room" stream; a click on a room walks
        there via ;go2. The database loads on a worker thread."""
        self.map_view = MapView(send=self.write)
        dock = QDockWidget("Map")
        dock.setObjectName("Map")
        dock.setWidget(self.map_view)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        # Registering under stream_docks gives it a View-menu toggle.
        self.stream_docks["Map"] = dock
        self.map_ready.connect(self.map_view.set_database)
        Thread(target=self._load_map_database, daemon=True).start()

    def _load_map_database(self):
        """Worker: load the community map (plus the survey overlay's ids)
        and hand it to the dock. A missing database is reported, never
        downloaded here — ;go2 update owns fetching the 13MB."""
        from client.mapdb import MapDB, mapdb_path
        from client.maplayout import local_room_ids

        if not mapdb_path().is_file():
            self.map_ready.emit(None, set())
            return
        try:
            db = MapDB.load()
        except (OSError, ValueError):
            self.log.exception("map database failed to load")
            self.map_ready.emit(None, set())
            return
        self.map_ready.emit(db, local_room_ids())

    def __add_clocks_dock(self):
        """What time it is everywhere that matters: Elanthia (computed
        from real time; ;clock calibrates), the three game moons,
        Stockholm and Chicago wall time — plus Earth's moon when the
        for-fun Settings row is on."""
        self._clock_zones = {}
        for city, zone in (
            ("Stockholm", "Europe/Stockholm"),
            ("Chicago", "America/Chicago"),
        ):
            try:
                self._clock_zones[city] = ZoneInfo(zone)
            except ZoneInfoNotFoundError:
                # No tzdata (a stale venv launched without a sync, #67):
                # a dashed row beats a client that dies before showing
                # a window.
                self._clock_zones[city] = None
        wrapper = QWidget()
        grid = QGridLayout(wrapper)
        grid.setContentsMargins(8, 6, 8, 6)
        self.clock_labels = {}
        self._earth_moon_widgets = ()
        rows = ("Elanthia", "Moons", "Stockholm", "Chicago", "Earth's moon")
        for row, name in enumerate(rows):
            place = QLabel(name)
            place.setStyleSheet("color: #808090;")
            value = QLabel("")
            grid.addWidget(place, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, row, 1)
            self.clock_labels[name] = value
            if name == "Earth's moon":
                self._earth_moon_widgets = (place, value)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(len(rows), 1)

        dock = QDockWidget("Clocks")
        dock.setObjectName("Clocks")
        dock.setWidget(wrapper)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.stream_docks["Clocks"] = dock

        self._clocks_ticks = 0
        self._reload_clock_settings()
        self.clocks_timer = QTimer(self)
        self.clocks_timer.timeout.connect(self.update_clocks)
        self.clocks_timer.start(1000)
        self.update_clocks()

    def _reload_clock_settings(self):
        """;clock writes its calibration to settings from the session
        process; re-reading once a minute picks a fresh sync up without
        a restart."""
        values = load_settings()
        self._eltime_offset = values.get("eltime_offset_seconds") or 0
        self._moon_epochs = dict(eltime.DEFAULT_MOON_EPOCHS)
        self._moon_epochs.update(values.get("eltime_moons") or {})
        for widget in self._earth_moon_widgets:
            widget.setVisible(bool(values.get("clocks_earth_moon")))

    def update_clocks(self):
        # Server time, not wall time: the "timesync" delta anchors the
        # Elanthian rows to the game's own clock (#102). Earth rows
        # below deliberately stay on local time.
        now = time() + self._server_delta
        line1, line2 = eltime.describe(eltime.elanthian_now(now, self._eltime_offset))
        self.clock_labels["Elanthia"].setText(f"{line1}\n{line2}")
        bits, tips = [], []
        for name in eltime.MOON_NAMES:
            index = eltime.moon_phase(name, now, self._moon_epochs.get(name))
            title = name.capitalize()
            if index is None:
                bits.append(f"{title} ?")
                tips.append(f"{title}: not observed yet — ;clock under open sky")
            else:
                bits.append(f"{title} {eltime.PHASE_EMOJI[index]}")
                tips.append(f"{title}: {eltime.PHASES[index]}")
        self.clock_labels["Moons"].setText("  ".join(bits))
        self.clock_labels["Moons"].setToolTip("\n".join(tips))
        for city, zone in self._clock_zones.items():
            self.clock_labels[city].setText(
                datetime.now(zone).strftime("%H:%M:%S %a") if zone else "— (no tzdata)"
            )
        index = eltime.earth_moon_phase(now)
        self.clock_labels["Earth's moon"].setText(
            f"{eltime.PHASE_EMOJI[index]} {eltime.PHASES[index]}"
        )
        self._clocks_ticks += 1
        if self._clocks_ticks % 60 == 0:
            self._reload_clock_settings()

    def __add_input_field(self):
        self.input_dock.setObjectName("Input")
        self.input = HistoryLineEdit()
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
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 0, 4, 0)
        row_layout.addWidget(self.status_strip)
        row_layout.addWidget(self.rt_label)
        row_layout.addWidget(self.ct_label)
        row_layout.addWidget(self.input)
        # Vitals bars above the input line — one bar per vital, created
        # as the game first mentions each (casters gain a mana bar the
        # moment it appears in the stream). Hidden until data arrives.
        self.vitals_bars = {}
        self._vitals_row = QWidget()
        self._vitals_layout = QHBoxLayout(self._vitals_row)
        self._vitals_layout.setContentsMargins(4, 2, 4, 0)
        self._vitals_layout.setSpacing(4)
        self._vitals_row.setVisible(False)
        column = QWidget()
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(2)
        column_layout.addWidget(self._vitals_row)
        column_layout.addWidget(row)
        # TODO: Fix the bottom dock. BottomDock thingy is incompatible with Qt6
        self.input_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.input_dock.setWidget(column)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.input_dock)
        self.input.returnPressed.connect(self.send_input)

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

    def update_indicators(self, text: str):
        """An "indicators" frame: the active indicator ids, space
        separated, full state each time."""
        active = set(text.split())
        if "IconDEAD" in active:
            self.status_strip.setText('<b style="color:#e05252">DEAD</b>')
            return
        parts = []
        posture = next(
            (word for icon, word in self.POSTURES.items() if icon in active), None
        )
        if posture:
            parts.append(f'<span style="color:#808090">{posture}</span>')
        for icon, (word, color) in self.INDICATOR_BADGES.items():
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
                bar.setFormat(f"{self.VITAL_LABELS.get(vital, vital)} %p%")
                color = self.VITAL_COLORS.get(vital, "#808090")
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
        if remaining_rt <= 0 and remaining_ct <= 0:
            self.rt_timer.stop()

    def send_input(self):
        text = self.input.text()
        self.write(text)
        self._append(self.main_window, f"> {text}\n", "sent")
        self.input.history.record(text)
        # Leave the text selected: plain Enter repeats it, typing
        # replaces it — the classic frontends' feel.
        self.input.selectAll()

    def reload_highlights(self):
        """View → Reload Highlights: re-read the patterns file so edits
        take effect without a restart."""
        self.highlight_rules = load_rules()
        self.status_bar.showMessage(
            f"{len(self.highlight_rules)} highlight rules loaded "
            f"from {highlights_path()}"
        )

    def edit_settings(self):
        """File → Settings…: toggles over settings.json. Quit-on-close
        applies immediately; autostarts apply to the next session."""
        from client.gui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(load_settings(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        save_settings(dialog.values())
        self.status_bar.showMessage(f"Settings saved to {settings_path()}")

    def edit_highlights(self):
        """View → Edit Highlights…: the table editor over the patterns
        file; saving reloads the rules immediately."""
        from client.highlights import load_entries, save_entries
        from client.gui.highlights_dialog import HighlightsDialog

        dialog = HighlightsDialog(load_entries(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        entries = dialog.entries()
        save_entries(entries)
        self.highlight_rules = load_rules()
        broken = dialog.broken_patterns()
        message = (
            f"{len(self.highlight_rules)} of {len(entries)} highlight rules active"
        )
        if broken:
            message += f" — {len(broken)} pattern(s) don't compile: {', '.join(broken)}"
        self.status_bar.showMessage(message)

    def open_beholder(self):
        """View → Beholder in Browser: the dashboard in a full tab,
        embedded view or not (the session autostarts the server, so
        the page is normally already answering)."""
        import webbrowser

        webbrowser.open(DASHBOARD_URL)
        self.status_bar.showMessage(f"Opened the dashboard ({DASHBOARD_URL})")

    def show_experience_history(self):
        """View → Experience History: the beholder dashboard, embedded.

        The dock is created lazily (WebEngine costs memory only when
        used) and toggled thereafter. Without QtWebEngine installed the
        dashboard opens in the system browser instead. The session
        autostarts the dashboard server, so the page is normally
        already answering on localhost."""
        if QWebEngineView is None:
            import webbrowser

            webbrowser.open(DASHBOARD_URL)
            self.status_bar.showMessage(
                "QtWebEngine not installed — opened the dashboard in your browser"
            )
            return
        dock = getattr(self, "_history_dock", None)
        if dock is None:
            from urllib.parse import quote

            from PyQt6.QtCore import QUrl

            from client.login import load_login_defaults

            # The compact /dock view (issue #59); the full dashboard
            # stays a browser away via ;beholder. Character comes from
            # the saved login default, the server falling back to the
            # latest-logged character without one.
            character = load_login_defaults().get("character") or ""
            url = DASHBOARD_URL + "/dock"
            if character:
                url += f"?character={quote(character)}"
            view = QWebEngineView()
            view.load(QUrl(url))
            dock = QDockWidget("Experience History")
            dock.setObjectName("ExperienceHistory")
            dock.setWidget(view)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            self._history_dock = dock
        else:
            dock.widget().reload()  # a fresh look picks up new characters
        dock.show()
        dock.raise_()

    def toggle_menu(self, state):
        if state:
            self.status_bar.show()
        else:
            self.status_bar.hide()

    def dispatch_game_text(self, text: str, stream: str, style: str = ""):
        if stream == "compass":
            self.update_compass(text)
            return
        if stream in ("roundtime", "casttime"):
            self.update_timer(stream, text)
            return
        if stream == "character":
            name = text.strip()
            self.setWindowTitle(f"Revenant — {name}" if name else "Revenant")
            self._character = name or self._character
            if name and not self._layout_applied:
                self._layout_applied = True
                self._restore_character_layout(name)
            return
        if stream == "timesync":
            try:
                self._server_delta = float(text.strip())
            except ValueError:
                pass  # a malformed delta never breaks the dispatch
            return
        if stream == "vitals":
            self.update_vitals(text)
            return
        if stream == "indicators":
            self.update_indicators(text)
            return
        if stream == "room":
            # uid\ttitle per room change — the map dock follows it.
            uid_text, _, title = text.partition("\t")
            uid = int(uid_text) if uid_text.strip().isdigit() else None
            self.map_view.update_room(uid, title.strip())
            return
        view = self.stream_windows.get(stream, self.main_window)
        if style == "clear":
            # The game rewrites resident windows wholesale (spell list
            # pulses): wipe before the fresh content lands.
            view.clear()
            return
        self._append(view, text, style)

    def write_to_main_window(self, text: str):
        if not text.endswith("\n"):
            text = text + "\n"
        self._append(self.main_window, text)

    def _append(self, view, text: str, style: str = ""):
        # Frames carry their own newlines: a line may arrive as several
        # styled pieces, and only the last one ends with "\n".
        scrollbar = view.verticalScrollBar()
        # Follow the text only when the user is already at the bottom;
        # scrolled-up reading must not be yanked back down.
        follow = scrollbar.value() >= scrollbar.maximum() - 4
        cursor = QTextCursor(view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        text_format = QTextCharFormat()
        if style.startswith("link:"):
            # A <d> command link: clicking sends the command (issue #54).
            text_format.setAnchor(True)
            text_format.setAnchorHref(style[5:])
            text_format.setForeground(QColor("#6db3f2"))
            text_format.setFontUnderline(True)
            cursor.insertText(text, text_format)
            if follow:
                scrollbar.setValue(scrollbar.maximum())
            return
        bold, color = self.STYLE_FORMATS.get(style, (False, None))
        if bold:
            text_format.setFontWeight(QFont.Weight.Bold)
        if color:
            text_format.setForeground(QColor(color))
        # User highlights color just the matched spans, lich-style,
        # over whatever base style the piece arrived with.
        position = 0
        for start, end, rule in spans(text, self.highlight_rules):
            if start > position:
                cursor.insertText(text[position:start], text_format)
            highlight_format = QTextCharFormat(text_format)
            if rule["bold"]:
                highlight_format.setFontWeight(QFont.Weight.Bold)
            if rule["color"]:
                highlight_format.setForeground(QColor(rule["color"]))
            cursor.insertText(text[start:end], highlight_format)
            position = end
        cursor.insertText(text[position:], text_format)
        if follow:
            scrollbar.setValue(scrollbar.maximum())

    def write(self, write_data: str):
        if self.client.connection is None:
            self.status_bar.showMessage("Not connected yet")
            return
        write_data = write_data + "\n"
        try:
            self.client.connection.write(write_data.encode("ASCII"))
        except OSError:
            # Session mid-;reexec: the old connection is gone and the
            # reader thread is busy reattaching. An exception escaping a
            # Qt slot would take the whole GUI down.
            self.status_bar.showMessage("Connection lost — reattaching, try again")
            return
        self.write_to_main_window(f">{write_data}")
        self.input.clear()

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        exit_action = context_menu.addAction("Quit")
        action = context_menu.exec(self.mapToGlobal(event.pos()))

        if action == exit_action:
            self.close()  # through closeEvent: quit the game, save layout

    def gui_reactor(self):
        def output_loop():
            # reader.pump surfaces EOF and crashes in the status bar —
            # a dead reader must never leave the window claiming
            # Connected (#96). Ending the thread re-arms File →
            # Reconnect (reconnect() checks is_alive).
            reader.pump(
                lambda: self.client.read(output_callback=self.game_text.emit),
                self.connection_state.emit,
                self.log,
            )

        self._reader_thread = Thread(target=output_loop, daemon=True)
        self._reader_thread.start()

    def reconnect(self):
        """File → Reconnect: bring a dead frontend back into the game.

        Attaches to a session if one is listening; otherwise gathers login
        (keychain first, dialog if needed — GUI thread, so the dialog may
        show) and spawns a fresh session, then reattaches from a worker
        thread so the wait never freezes the window."""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self.status_bar.showMessage("Still connected")
            return
        if not isinstance(self.client, AttachedEngine):
            # Direct mode has no session to respawn; log in again.
            self.status_bar.showMessage("Reconnecting (direct login) ...")
            Thread(target=self._reconnect_direct, daemon=True).start()
            return
        from client.launch import (
            gather_login,
            session_running,
            spawn_session,
            wait_for_session,
        )

        process = None
        if not session_running(self.client.host, self.client.port):
            try:
                # Three values since the multi-account rework — the old
                # two-value unpack crashed the whole GUI on click.
                account, character, key = gather_login(None)
            except SystemExit:
                self.status_bar.showMessage("Reconnect cancelled")
                return
            process = spawn_session(
                self.client.host,
                self.client.port,
                character,
                key=key,
                account=account,
            )
        self.status_bar.showMessage("Reconnecting ...")
        Thread(
            target=self._finish_reconnect,
            args=(process, wait_for_session),
            daemon=True,
        ).start()

    def _finish_reconnect(self, process, wait_for_session):
        try:
            if process is not None:
                wait_for_session(process, self.client.host, self.client.port)
        except SystemExit as error:
            self.connection_state.emit(str(error))
            return
        if not self.client.reattach():
            self.connection_state.emit("Reconnect failed — no session came up")
            return
        self.connection_state.emit(self.client.description)
        self.gui_reactor()

    def _reconnect_direct(self):
        try:
            self.client.connect()
        except SystemExit:
            self.connection_state.emit("Reconnect failed — login did not complete")
            return
        self.connection_state.emit(getattr(self.client, "description", "Connected"))
        self.gui_reactor()


def main(argv=None):
    argparser = argparse.ArgumentParser(description="Revenant PyQt6 front end")
    argparser.add_argument(
        "--attach",
        nargs="?",
        const=f"{DEFAULT_HOST}:{DEFAULT_PORT}",
        default=None,
        metavar="HOST:PORT",
        help="attach to a running client.session instead of logging in directly",
    )
    args = argparser.parse_args(argv)
    claim_taskbar_identity()  # before any window exists
    app = QApplication(sys.argv[:1])
    # On macOS this also sets the Dock icon for the running app.
    app.setWindowIcon(QIcon(ICON_PATH))
    if args.attach:
        host, _, port = args.attach.rpartition(":")
        engine = AttachedEngine(host or DEFAULT_HOST, int(port))
    else:
        engine = Engine()
    client_app = ClientGUI(engine)  # noqa: F841 -- must outlive app.exec()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
