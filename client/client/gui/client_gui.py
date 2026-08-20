import argparse
import sys
from pathlib import Path
from threading import Thread
from time import sleep

from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QGridLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QTextEdit,
    QWidget,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtCore import QSettings, Qt, pyqtSignal

from client.core import Engine
from client.client_logger import ClientLogger
from client.session import AttachedEngine, DEFAULT_HOST, DEFAULT_PORT

# TODO: Exit the game when the window is closed. Make it optional, leaving room for headless potential.

ICON_PATH = str(Path(__file__).with_name("revenant.svg"))

# Windows groups taskbar buttons by AppUserModelID, defaulting to the exe
# path — which for us is pythonw.exe, shared with every other Python GUI.
# Claiming our own ID (matching the one tools/install_shortcut.ps1 stamps
# on the Start Menu shortcut) merges the running window with the pinned
# icon instead of splitting into two buttons.
APP_USER_MODEL_ID = "revenant.client"


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

    # style id -> (bold, color). The game's own styling markers, rendered
    # the way Stormfront players expect: amber room names, blue speech.
    STYLE_FORMATS = {
        "roomName": (True, "#d8b465"),
        "bold": (True, None),
        "speech": (False, "#8fc7e8"),
        "whisper": (False, "#8fc7e8"),
        "thought": (False, "#b39ddb"),
    }

    # stream id -> dock window title; streams not listed here fall through
    # to the main window.
    STREAM_WINDOWS = {
        "thoughts": "Thoughts",
        "chatter": "Thoughts",
        "percWindow": "Spells",
        "logons": "Arrivals",
        "death": "Arrivals",
        "exp": "Experience",
    }

    # (direction, row, column) in the compass grid
    COMPASS_LAYOUT = [
        ("nw", 0, 0),
        ("n", 0, 1),
        ("ne", 0, 2),
        ("up", 0, 3),
        ("w", 1, 0),
        ("out", 1, 1),
        ("e", 1, 2),
        ("sw", 2, 0),
        ("s", 2, 1),
        ("se", 2, 2),
        ("down", 2, 3),
    ]

    def __init__(self, engine=None):
        super().__init__()
        self.log.debug("Initializing ClientGUI instance")
        self.status_bar = self.statusBar()
        self.input_dock = QDockWidget()
        self.client = engine if engine is not None else Engine()
        self.__init_ui()
        self.game_text.connect(self.dispatch_game_text)
        self.connection_state.connect(self.status_bar.showMessage)
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
        self.__add_input_field()

        reconnect_action = QAction("&Reconnect", self)
        reconnect_action.setShortcut("Ctrl+R")
        reconnect_action.setStatusTip(
            "Start or attach to a game session after a disconnect"
        )
        reconnect_action.triggered.connect(self.reconnect)

        exit_action = QAction(QIcon("exit.png"), "&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit")
        exit_action.triggered.connect(QApplication.instance().quit)

        view_status_bar = QAction("Status Bar", self, checkable=True)
        view_status_bar.setStatusTip("Show the status bar")
        view_status_bar.setChecked(True)
        view_status_bar.triggered.connect(self.toggle_menu)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(reconnect_action)
        file_menu.addAction(exit_action)
        view_menu = menubar.addMenu("View")
        view_menu.addAction(view_status_bar)
        view_menu.addSeparator()
        for dock in self.stream_docks.values():
            view_menu.addAction(dock.toggleViewAction())

        # Window size and dock layout persist between launches.
        settings = QSettings("revenant", "revenant")
        if geometry := settings.value("geometry"):
            self.restoreGeometry(geometry)
        if state := settings.value("windowState"):
            self.restoreState(state)

        self.show()

    def closeEvent(self, event):
        settings = QSettings("revenant", "revenant")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def __add_output_window(self):
        self.main_window = QTextEdit(readOnly=True)
        self.setCentralWidget(self.main_window)

    def __add_stream_docks(self):
        """One dock window per title in STREAM_WINDOWS, stacked on the right."""
        self.stream_docks = {}
        self.stream_windows = {}
        for title in dict.fromkeys(self.STREAM_WINDOWS.values()):
            dock = QDockWidget(title)
            dock.setObjectName(title)  # saveState() needs unique names
            view = QTextEdit(readOnly=True)
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
        """Clickable exits: buttons light up with the room's compass tag."""
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)
        self.compass_buttons = {}
        for direction, row, column in self.COMPASS_LAYOUT:
            button = QPushButton(direction)
            button.setEnabled(False)
            button.setFixedSize(48, 28)
            button.clicked.connect(lambda checked=False, d=direction: self.write(d))
            grid.addWidget(button, row, column)
            self.compass_buttons[direction] = button
        dock = QDockWidget("Compass")
        dock.setObjectName("Compass")
        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        # Registering under stream_docks gives it a View-menu toggle.
        self.stream_docks["Compass"] = dock

    def update_compass(self, dirs_text: str):
        available = set(dirs_text.split())
        for direction, button in self.compass_buttons.items():
            button.setEnabled(direction in available)

    def __add_input_field(self):
        self.input_dock.setObjectName("Input")
        self.input = QLineEdit()
        # Disabled until the game connection is up: Qt's input hook pumps
        # events while login blocks on stdin, so keystrokes meant for the
        # terminal must not reach this field or trigger a send.
        self.input.setEnabled(False)
        # TODO: Fix the bottom dock. BottomDock thingy is incompatible with Qt6
        self.input_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.input_dock.setWidget(self.input)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.input_dock)
        self.input.returnPressed.connect(self.send_input)

    def send_input(self):
        self.write(self.input.text())

    def toggle_menu(self, state):
        if state:
            self.status_bar.show()
        else:
            self.status_bar.hide()

    def dispatch_game_text(self, text: str, stream: str, style: str = ""):
        if stream == "compass":
            self.update_compass(text)
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
        bold, color = self.STYLE_FORMATS.get(style, (False, None))
        if bold:
            text_format.setFontWeight(QFont.Weight.Bold)
        if color:
            text_format.setForeground(QColor(color))
        cursor.insertText(text, text_format)
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
            QApplication.instance().quit()

    def gui_reactor(self):
        def output_loop():
            while True:
                try:
                    self.client.read(output_callback=self.game_text.emit)
                except EOFError:
                    self.connection_state.emit("Disconnected — File → Reconnect")
                    break
                sleep(0.01)

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
                character, key = gather_login(None)
            except SystemExit:
                self.status_bar.showMessage("Reconnect cancelled")
                return
            process = spawn_session(
                self.client.host, self.client.port, character, key=key
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
