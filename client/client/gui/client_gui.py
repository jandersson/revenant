"""The PyQt6 window: menus, docks, dispatch, rendering, reconnect.

The docks' widgets live beside this module — compass_dock.py (the
rose), clocks_dock.py (the clocks panel), input_strip.py (the command
line with its vitals bars, status strip and timers), map_dock.py (the
map) and text_views.py (the story and stream views, fonts); this file
builds the window around them, restores the saved layout, routes each
frame of game text to the widget or dock it belongs to, appends styled
text, and owns the connection (reader thread, reconnect, detach, quit).
"""

import argparse
import os
import sys
from pathlib import Path
from threading import Thread

from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QMenu,
    QTextBrowser,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtCore import QEvent, QSettings, Qt, pyqtSignal

from client.ui import crashguard, window_layout

from client.engine import reader
from client.engine.core import Engine
from client.client_logger import ClientLogger
from client.gui.clocks_dock import ClocksPanel
from client.gui import dock_collapse
from client.gui.compass_dock import CompassRose
from client.gui.injuries_dock import InjuriesPanel
from client.gui.spells_dock import SpellsPanel
from client.gui import jumplist
from client.gui.input_strip import InputStrip
from client.gui.jumplist import APP_USER_MODEL_ID
from client.gui.map_dock import MapView
from client.gui.text_views import GameTextView, font_for, style_experience_view
from client.ui.highlights import highlights_path, load_rules, spans
from client.ui.inputfocus import click_focuses_input, forwardable
from client.ui.roomids import RoomIdTracker, room_id_suffix
from client.engine.registry import character_for_port
from client.engine.session import AttachedEngine
from client.engine.wire import DEFAULT_HOST, DEFAULT_PORT
from client.settings import load_settings, save_settings, setting, settings_path
from client.ui.streamroute import STREAM_WINDOWS as STREAM_WINDOW_TITLES, clears_window


def layout_settings():
    """The window-layout store: QSettings("revenant", "revenant") — the
    registry on Windows, ~/.config on Linux — or the ini file
    REVENANT_QSETTINGS names. The tests set the latter: on Windows the
    two-argument constructor ignores QSettings.setDefaultFormat and
    setPath, so the GUI suite's synthetic "Lanival" layouts had been
    landing in the real registry on every run (found 2026-09-13 under
    #180, when a test's folded docks came back folded in a fresh
    window)."""
    path = os.environ.get("REVENANT_QSETTINGS")
    if path:
        return QSettings(path, QSettings.Format.IniFormat)
    return QSettings("revenant", "revenant")


ICON_PATH = str(Path(__file__).with_name("revenant.svg"))

# Windows groups taskbar buttons by AppUserModelID (jumplist.py has the
# story); claiming ours merges the running window with the pinned icon.

DASHBOARD_URL = "http://127.0.0.1:8050"

# Qt WebEngine wants importing before the QApplication exists; absence
# is fine (the dashboard falls back to the system browser).
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover — depends on the install
    QWebEngineView = None


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
    # client/ui/textstyle.py keeps the TUI's copy in step.
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

    # stream id -> dock window title; a stream not listed here has no dock
    # of its own, and its text falls through to the main window. The table
    # lives in client.ui.streamroute, Qt-free, so tests can exercise the
    # routing rules headless (#109).
    STREAM_WINDOWS = STREAM_WINDOW_TITLES

    def __init__(self, engine=None, character=None):
        super().__init__()
        self.log.debug("Initializing ClientGUI instance")
        self.status_bar = self.statusBar()
        self.highlight_rules = load_rules()
        # Who is playing — known up front when the launcher or the
        # session registry says so (`character`), otherwise from the
        # "character" stream — names the title bar and scopes the saved
        # window layout (#74). Known up front, the layout is restored
        # before the first show, the only order Qt has restored every
        # saved dock state safely (#140); learned later, it is applied
        # once, on first identification: a reattach re-states the
        # character and must not stomp a live arrangement.
        self._character = character or None
        self._layout_applied = False
        # The map room id after each room title (client/ui/roomids.py):
        # a cursor parked at the end of the last title line, filled in
        # when the Map dock has resolved the room, if Settings say so.
        self._room_ids = RoomIdTracker()
        self._title_cursor = None
        self._show_room_ids = bool(setting("show_room_ids"))
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

    # -- building the window ------------------------------------------------

    def __init_ui(self):
        self.log.debug("Initializing UI")
        self.setWindowTitle("Revenant")
        self.setWindowIcon(QIcon(ICON_PATH))
        # TODO: Update this with some sort of connection string when connected
        self.status_bar.showMessage("Not Connected")

        # Dock creation order and object names are what a saved layout
        # restores onto (#140): keep both stable.
        self.stream_docks = {}
        self.__add_output_window()
        self.__add_stream_docks()
        self.__add_compass_dock()
        self.__add_clocks_dock()
        self.__add_map_dock()
        self.__add_injuries_dock()
        self.__add_spells_dock()
        self.__add_input_field()
        self._apply_text_font()
        self.__add_menus()

        # Window size and dock layout persist between launches. The
        # character's own layout when the character is known up front,
        # the legacy unscoped pair otherwise — restored before the
        # first show (#140). A character learned later, from the
        # "character" frame, gets the hide-restore-show path (#74).
        settings = layout_settings()
        geometry, state, scoped = window_layout.startup_layout(
            settings.value, self._character
        )
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        dock_collapse.apply_collapsed(
            self.findChildren(QDockWidget),
            window_layout.startup_collapsed(settings.value, self._character, scoped),
        )
        if scoped:
            self._layout_applied = True
            self.setWindowTitle(f"Revenant — {self._character}")

        self.show()

    def _dock(self, title, widget, object_name=None):
        """A dock on the right, registered under stream_docks so the
        View menu gets its toggle; the object name is what saveState()
        keys the layout by, so it never changes."""
        dock = QDockWidget(title)
        dock.setObjectName(object_name or title)
        dock.setWidget(widget)
        dock_collapse.install(dock)  # the title bar with the fold button (#180)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.stream_docks[title] = dock
        return dock

    def _make_view(self):
        return GameTextView(self._follow_link, self)

    def __add_output_window(self):
        self.main_window = self._make_view()
        self.setCentralWidget(self.main_window)
        # The platform font, kept so "use the default" in Settings can
        # restore it after a custom font was applied.
        self._default_text_font = QFont(self.main_window.font())

    # Stream titles a widget dock draws instead of a text view: the
    # Spells dock renders the parser's spell state, not the raw window
    # (#175); the TUI still prints the raw lines under that title.
    WIDGET_DOCKS = ("Spells",)

    def __add_stream_docks(self):
        """One dock window per title in STREAM_WINDOWS, stacked on the
        right — except the titles a widget dock takes (WIDGET_DOCKS)."""
        self.stream_windows = {}
        for title in dict.fromkeys(self.STREAM_WINDOWS.values()):
            if title in self.WIDGET_DOCKS:
                continue
            view = self._make_view()
            if title == "Experience":
                style_experience_view(view)
            self._dock(title, view)
        for stream, title in self.STREAM_WINDOWS.items():
            if title not in self.WIDGET_DOCKS:
                self.stream_windows[stream] = self.stream_docks[title].widget()

    def __add_compass_dock(self):
        self.compass = CompassRose(send=self.write)
        self._dock("Compass", self.compass)

    def __add_clocks_dock(self):
        self.clocks = ClocksPanel()
        self._dock("Clocks", self.clocks)

    def __add_injuries_dock(self):
        """The game's injuries panel as badges (#163): fed by the
        "injuries" stream, which states the hurt parts on every change."""
        self.injuries = InjuriesPanel()
        self._dock("Injuries", self.injuries)

    def __add_spells_dock(self):
        """The running spells with countdowns and the prepared one
        (#175): fed by the "spells" stream. Keeps the "Spells" object
        name the raw text dock had, so saved layouts keep its place."""
        self.spells = SpellsPanel()
        self._dock("Spells", self.spells)

    def __add_map_dock(self):
        """The visual map (#56): the community map drawn around the
        character, following the "room" stream; a click on a room walks
        there via ;go2. The database loads on a worker thread. On the
        right with the other docks: alone on the left it got whatever
        width the story window left over, a strip (#146)."""
        self.map_view = MapView(send=self.write)
        self._dock("Map", self.map_view)
        self.map_ready.connect(self.map_view.set_database)
        # After the dock has the database (the slot above runs first),
        # a title shown while it was still loading gets its id.
        self.map_ready.connect(self._map_loaded)
        Thread(target=self._load_map_database, daemon=True).start()

    def _map_loaded(self, db, local_ids):
        self._annotate_title(
            self._room_ids.room_resolved(
                self.map_view.room_id, self.map_view.room_title
            )
        )

    def _load_map_database(self):
        """Worker: load the community map (plus the survey overlay's ids)
        and hand it to the dock. A missing database is reported, never
        downloaded here — ;go2 update owns fetching the 13MB."""
        from client.game.mapdb import MapDB, mapdb_path
        from client.ui.maplayout import local_room_ids

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

    def __add_input_field(self):
        self.input_strip = InputStrip()
        self.input = self.input_strip.input
        self.input_dock = QDockWidget()
        self.input_dock.setObjectName("Input")
        # TODO: Fix the bottom dock. BottomDock thingy is incompatible with Qt6
        self.input_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.input_dock.setWidget(self.input_strip)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.input_dock)
        self.input.returnPressed.connect(self.send_input)

    def __add_menus(self):
        reconnect_action = QAction("&Reconnect", self)
        reconnect_action.setShortcut("Ctrl+R")
        reconnect_action.setStatusTip(
            "Start or attach to a game session after a disconnect"
        )
        reconnect_action.triggered.connect(self.reconnect)

        settings_action = QAction("&Settings…", self)
        settings_action.setStatusTip(
            "Font, autostarts and window-close behavior (~/.revenant/settings.json)"
        )
        settings_action.triggered.connect(self.edit_settings)

        profile_action = QAction("Character &Profile…", self)
        profile_action.setStatusTip(
            "What ;hunt does for this character (~/.revenant/profiles/<name>.json)"
        )
        profile_action.triggered.connect(self.edit_profile)

        lnet_action = QAction("LNet Pass&word…", self)
        lnet_action.setStatusTip(
            "Store this character's LNet password in the OS keychain, for ;lnet"
        )
        lnet_action.triggered.connect(self.store_lnet_password)

        plan_action = QAction("Training Pla&n…", self)
        plan_action.setStatusTip(
            "What ;train runs for this character (~/.revenant/training/<name>.json)"
        )
        plan_action.triggered.connect(self.edit_plan)

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
        file_menu.addAction(profile_action)
        file_menu.addAction(plan_action)
        file_menu.addAction(lnet_action)
        file_menu.addAction(detach_action)
        file_menu.addAction(exit_action)
        # Fold the dock holding the keyboard focus to its title bar, or
        # open it again (#180); the title bar's button and a double-click
        # on the title do the same with the mouse.
        self.collapse_dock_action = QAction("Collapse/Expand &Dock", self)
        self.collapse_dock_action.setShortcut("Ctrl+Shift+D")
        self.collapse_dock_action.setStatusTip(
            "Fold the focused dock to its title bar, or expand it again"
        )
        self.collapse_dock_action.triggered.connect(self.toggle_focused_dock)

        view_menu = menubar.addMenu("View")
        view_menu.addAction(view_status_bar)
        view_menu.addAction(history_action)
        view_menu.addAction(beholder_action)
        view_menu.addAction(edit_highlights_action)
        view_menu.addAction(highlights_action)
        view_menu.addSeparator()
        view_menu.addAction(self.collapse_dock_action)
        for dock in self.stream_docks.values():
            view_menu.addAction(dock.toggleViewAction())

    def _apply_text_font(self):
        """Settings' font on the main window, every stream dock, and the
        input line (#118), each view resolved on its own (#132)."""
        settings = load_settings()
        for title, dock in self.stream_docks.items():
            if title in STREAM_WINDOW_TITLES.values():
                dock.widget().setFont(
                    font_for(settings, title, self._default_text_font)
                )
        self.main_window.setFont(font_for(settings, "Main", self._default_text_font))
        self.input.setFont(font_for(settings, "Input", self._default_text_font))

    # -- layout, focus, closing ------------------------------------------------

    def _restore_character_layout(self, name):
        """This character's own saved arrangement, if any — without one
        the legacy layout restored at startup simply stays. Applied
        with the window hidden: dock state restored onto the shown
        window crashed the process at the next setVisible (#124)."""
        settings = layout_settings()
        geometry_key, state_key = window_layout.layout_keys(name)
        if window_layout.apply(
            self, settings.value(geometry_key), settings.value(state_key)
        ):
            dock_collapse.apply_collapsed(
                self.findChildren(QDockWidget),
                window_layout.collapsed_from(
                    settings.value(window_layout.collapsed_key(name))
                ),
            )

    def toggle_dock_of(self, widget):
        """Fold or open the dock holding `widget`; False when no dock
        holds it (the story, the menu bar, nothing focused)."""
        dock = dock_collapse.dock_of(widget)
        return dock is not None and dock_collapse.toggle(dock)

    def toggle_focused_dock(self):
        """View → Collapse/Expand Dock (Ctrl+Shift+D)."""
        return self.toggle_dock_of(QApplication.focusWidget())

    def detach(self):
        """File → Detach: close the window, stay logged in. The session
        keeps the game connection; a new launch reattaches to it."""
        self._detaching = True
        self.close()

    def closeEvent(self, event):
        settings = layout_settings()
        pairs = window_layout.save_pairs(
            self._character,
            self.saveGeometry(),
            self.saveState(),
            dock_collapse.collapsed_names(self.findChildren(QDockWidget)),
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

    def eventFilter(self, obj, event):
        """A click on a game text view without selecting text focuses
        the input line; a printable keystroke that lands on a view is
        typed into the input line instead of being discarded (#150).
        Selections, control chords and scrolling keys stay with the
        view (client/ui/inputfocus.py holds the rule)."""
        if isinstance(obj, QTextBrowser):
            kind = event.type()
            if kind == QEvent.Type.MouseButtonRelease:
                if click_focuses_input(obj.textCursor().hasSelection()):
                    self.input.setFocus()
            elif kind == QEvent.Type.KeyPress:
                chord = (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
                if forwardable(event.text(), bool(event.modifiers() & chord)):
                    self.input.setFocus()
                    self.input.insert(event.text())
                    return True
        return super().eventFilter(obj, event)

    def _follow_link(self, command):
        if command:
            self.write(command)

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        exit_action = context_menu.addAction("Quit")
        action = context_menu.exec(self.mapToGlobal(event.pos()))

        if action == exit_action:
            self.close()  # through closeEvent: quit the game, save layout

    def toggle_menu(self, state):
        if state:
            self.status_bar.show()
        else:
            self.status_bar.hide()

    # -- the menus' actions ---------------------------------------------------

    def reload_highlights(self):
        """View → Reload Highlights: re-read the patterns file so edits
        take effect without a restart."""
        self.highlight_rules = load_rules()
        self.status_bar.showMessage(
            f"{len(self.highlight_rules)} highlight rules loaded "
            f"from {highlights_path()}"
        )

    def edit_settings(self):
        """File → Settings…: toggles and the font over settings.json.
        Quit-on-close and the font apply immediately; autostarts apply
        to the next session."""
        from client.gui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(load_settings(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        save_settings(dialog.values())
        self._apply_text_font()
        self.clocks.reload_settings()
        self._show_room_ids = bool(setting("show_room_ids"))
        self.status_bar.showMessage(f"Settings saved to {settings_path()}")

    def store_lnet_password(self):
        """File → LNet Password…: the password ;lnet logs this window's
        character in with, asked in a masked field and kept in the OS
        keychain (service revenant-lnet, one entry per name) — the
        game-window way in, beside revenant-chat's ask-and-remember
        (the operator, 2026-09-22, #290). Never a file, never echoed."""
        from client.engine import lnet_login
        from client.gui.chat_window import PasswordDialog

        character = self._character or ""
        if not character:
            self.status_bar.showMessage("No character in this window yet")
            return
        dialog = PasswordDialog(
            character,
            "",
            self,
            intro=(
                f"The LNet password for {character}, used by ;lnet.\n"
                "It goes into the OS keychain and nowhere else."
            ),
        )
        dialog.remember.setChecked(True)
        dialog.remember.hide()  # storing it is the point here
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        password = dialog.password.text()
        if not password:
            self.status_bar.showMessage("No password entered — nothing stored")
            return
        if lnet_login.remember(character, password):
            self.status_bar.showMessage(
                f"LNet password stored for {character} — ;lnet to log in"
            )
        else:
            self.status_bar.showMessage(
                "No usable OS keychain — the password was not stored"
            )

    def edit_profile(self):
        """File → Character Profile…: the ;hunt settings for the
        character this window plays, over profiles/<name>.json; the
        next ;hunt start reads them."""
        from client.gui.profile_dialog import ProfileDialog
        from client.game.profile import load_profile, save_profile

        character = self._character or ""
        dialog = ProfileDialog(character, load_profile(character), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        path = save_profile(character, dialog.values())
        self.status_bar.showMessage(f"Profile saved to {path}")

    def edit_plan(self):
        """File → Training Plan…: the ;train plan for the character this
        window plays, over training/<name>.json — the starter plan
        (;train init's) when there is none yet; the next ;train start
        reads it."""
        from client.gui.plan_dialog import PlanDialog
        from client.game.training import load_plan, plan_path, save_plan, starter_plan

        character = self._character or ""
        plan = (
            load_plan(character)
            if plan_path(character).is_file()
            else starter_plan(character)
        )
        dialog = PlanDialog(character, plan, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        path = save_plan(character, dialog.values())
        self.status_bar.showMessage(f"Training plan saved to {path}")

    def edit_highlights(self):
        """View → Edit Highlights…: the table editor over the patterns
        file; saving reloads the rules immediately."""
        from client.ui.highlights import load_entries, save_entries
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

            from client.engine.login import load_login_defaults

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

    # -- game text in, commands out ------------------------------------------

    def dispatch_game_text(self, text: str, stream: str, style: str = ""):
        if stream == "attached":
            return  # the end of the replay, for outside readers (#287)
        if stream == "percWindow":
            # The raw Spells window: the parser reads it and the Spells
            # dock draws the result from the "spells" stream (#175), so
            # neither its lines nor its clear land anywhere here.
            return
        if style == "clear":
            # A clear names one stream, so it is answered before the
            # synthetic-stream branches below: the game has its own
            # "room" stream whose clear would otherwise reach the map
            # dock as an empty room frame. Streams with no window of
            # their own (inv, experience) have nothing to wipe — the
            # main window is not a stand-in, or every GET/PUT would
            # blank the story (#109).
            if clears_window(stream):
                self.stream_windows[stream].clear()
            return
        if stream == "bell":
            # The game rang its bell (the idle warning): sound it, as
            # the official frontend does (#131). Nothing to display.
            QApplication.beep()
            return
        if stream == "compass":
            self.compass.set_exits(text)
            return
        if stream in ("roundtime", "casttime"):
            self.input_strip.update_timer(stream, text)
            return
        if stream == "shutdown":
            self.input_strip.update_shutdown(text)
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
                self.clocks.server_delta = float(text.strip())
            except ValueError:
                pass  # a malformed delta never breaks the dispatch
            return
        if stream == "vitals":
            self.input_strip.update_vitals(text)
            return
        if stream == "indicators":
            self.input_strip.update_indicators(text)
            return
        if stream == "injuries":
            self.injuries.show_frame(text)
            return
        if stream == "spells":
            self.spells.show_frame(text)
            return
        if stream == "room":
            # uid\ttitle per room change — the map dock follows it.
            uid_text, _, title = text.partition("\t")
            uid = int(uid_text) if uid_text.strip().isdigit() else None
            self.map_view.update_room(uid, title.strip())
            self._annotate_title(
                self._room_ids.room_resolved(self.map_view.room_id, title.strip())
            )
            return
        # An undocked stream's text still belongs in the main window;
        # only the clear control above is stream-exclusive.
        self._append(self.stream_windows.get(stream, self.main_window), text, style)

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
        if view is self.main_window and style == "roomName":
            # Park a cursor before the title's newline; the map id lands
            # there once the room is resolved (or now, if it already is).
            anchor = QTextCursor(view.document())
            anchor.setPosition(cursor.position() - (1 if text.endswith("\n") else 0))
            self._title_cursor = anchor
            self._annotate_title(self._room_ids.title_shown(text))

    def _annotate_title(self, room_id):
        """Append " (1420)" to the last room title, once, when Settings
        show room ids and the tracker handed an id back."""
        if room_id is None or not self._show_room_ids or self._title_cursor is None:
            return
        view = self.main_window
        scrollbar = view.verticalScrollBar()
        follow = scrollbar.value() >= scrollbar.maximum() - 4
        dim = QTextCharFormat()
        dim.setForeground(QColor(self.STYLE_FORMATS["sent"][1]))
        self._title_cursor.insertText(room_id_suffix(room_id), dim)
        self._title_cursor = None
        if follow:
            scrollbar.setValue(scrollbar.maximum())

    def send_input(self):
        text = self.input.text()
        self.write(text)
        self.input.history.record(text)
        # Leave the text selected: plain Enter repeats it, typing
        # replaces it — the classic frontends' feel.
        self.input.selectAll()

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
        # One echo per command, here, whatever sent it — typed, a link
        # click, a compass button. Typed commands used to echo a second
        # time in send_input (#143).
        self._append(self.main_window, f"> {write_data}", "sent")
        self.input.clear()

    # -- the connection --------------------------------------------------------

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
            # The reader is up: the session is fine, or it dropped and
            # the reader is reattaching by itself. Say which in the
            # story, not only the status bar — a click that only changed
            # the status bar read as "does nothing" (#120).
            if getattr(self.client, "reattaching", False):
                self._say(
                    "reconnect: the session dropped and the window is "
                    "reattaching now — give it ten seconds"
                )
            elif isinstance(self.client, AttachedEngine):
                self._say(
                    f"reconnect: already connected to the session on "
                    f"{self.client.host}:{self.client.port} — nothing to do"
                )
            else:
                self._say("reconnect: already connected to the game — nothing to do")
            return
        if not isinstance(self.client, AttachedEngine):
            # Direct mode has no session to respawn; log in again.
            self._say("reconnect: logging in again (direct mode) ...")
            Thread(target=self._reconnect_direct, daemon=True).start()
            return
        from client.engine.launch import (
            account_for_character,
            gather_login,
            load_login_defaults,
            session_running,
            spawn_session,
            wait_for_session,
        )

        process = None
        if not session_running(self.client.host, self.client.port):
            # This window's character, on the account that owns it —
            # gather_login(None) took the saved login default and logged
            # the account's other character in (2026-09-19).
            character = self._character or None
            account = (
                account_for_character(load_login_defaults(), character)
                if character
                else None
            )
            if not character:
                self._say(
                    "reconnect: this window never learned its character — "
                    "logging in the saved default"
                )
            try:
                # Three values since the multi-account rework — the old
                # two-value unpack crashed the whole GUI on click.
                account, character, key = gather_login(character, account=account)
            except SystemExit:
                self._say("reconnect: cancelled")
                return
            process = spawn_session(
                self.client.host,
                self.client.port,
                character,
                key=key,
                account=account,
            )
        self._say(
            "reconnect: attaching to the session ..."
            if process is None
            else "reconnect: no session was listening — starting one and attaching ..."
        )
        Thread(
            target=self._finish_reconnect,
            args=(process, wait_for_session),
            daemon=True,
        ).start()

    def _say(self, text):
        """A line in the story window and the status bar both: what the
        reconnect is doing, where it cannot be missed (#120)."""
        self._append(self.main_window, f"{text}\n", "sent")
        self.status_bar.showMessage(text)

    def _finish_reconnect(self, process, wait_for_session):
        try:
            if process is not None:
                wait_for_session(process, self.client.host, self.client.port)
        except SystemExit as error:
            self.game_text.emit(f"reconnect failed: {error}\n", "", "alert")
            self.connection_state.emit(str(error))
            return
        if not self.client.reattach():
            self.game_text.emit(
                "reconnect failed: no session came up on "
                f"{self.client.host}:{self.client.port}\n",
                "",
                "alert",
            )
            self.connection_state.emit("Reconnect failed — no session came up")
            return
        self.game_text.emit("reconnect: attached\n", "", "sent")
        self.connection_state.emit(self.client.description)
        self.gui_reactor()

    def _reconnect_direct(self):
        try:
            self.client.connect()
        except SystemExit:
            self.game_text.emit(
                "reconnect failed: login did not complete\n", "", "alert"
            )
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
        help="attach to a running client.engine.session instead of logging in directly",
    )
    args = argparser.parse_args(argv)
    claim_taskbar_identity()  # before any window exists
    app = QApplication(sys.argv[:1])
    jumplist.install()  # the button's "launch another character" tasks (#226)
    # On macOS this also sets the Dock icon for the running app.
    app.setWindowIcon(QIcon(ICON_PATH))
    if args.attach:
        host, _, port = args.attach.rpartition(":")
        engine = AttachedEngine(host or DEFAULT_HOST, int(port))
    else:
        engine = Engine()
    if args.attach:
        character = character_for_port(port)
    else:
        character = os.environ.get("REVENANT_CHARACTER")
    # noqa: F841 -- must outlive app.exec()
    client_app = ClientGUI(engine, character=character)  # noqa: F841
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
