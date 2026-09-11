"""The headless GUI suite: real PyQt6 widgets on Qt's offscreen platform.

client/tests stays Qt-free (fast, import-safe); this directory is
where the window and its docks are exercised for what pure tests
cannot reach — a frame of each stream landing in its widget, the
vitals bar created on first mention, DEAD over the badges, the
Experience view's fixed-pitch font, the dock layout round trip. No
display is needed: QT_QPA_PLATFORM=offscreen is set before PyQt6
loads, and every path the window touches (settings, highlights, the
map, logs, QSettings) is pointed at a temp directory so a test run
never reads or writes the operator's files.
"""

import os
import tempfile

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["REVENANT_LOG_DIR"] = tempfile.mkdtemp(prefix="revenant-gui-test-logs-")

from PyQt6.QtCore import QEvent, QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """The one QApplication a process may have. Widgets are swept after
    every test (below), so nothing is left for it to outlive."""
    app = QApplication.instance() or QApplication(["revenant-tests"])
    yield app
    app.closeAllWindows()
    flush_deletes(app)


@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    """Every file the window reads or writes lives under tmp_path."""
    monkeypatch.setenv("REVENANT_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("REVENANT_HIGHLIGHTS", str(tmp_path / "highlights.json"))
    monkeypatch.setenv("REVENANT_MAPDB", str(tmp_path / "mapdb.json"))
    monkeypatch.setenv("REVENANT_MAPDB_LOCAL", str(tmp_path / "local.json"))
    monkeypatch.setenv("REVENANT_LOGIN_DEFAULTS", str(tmp_path / "login.json"))
    monkeypatch.setenv("REVENANT_SESSIONS", str(tmp_path / "sessions.json"))
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path / "profiles"))
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path / "training"))
    # QSettings("revenant", "revenant") is the window layout store — the
    # registry on Windows, ~/.config on Linux. An ini file here instead.
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "qt")
    )
    return tmp_path


class StubEngine:
    """What ClientGUI needs of an engine: connect(), read() for the
    reader thread, and a connection that records what the window
    writes when a test plugs one in. read() raises EOFError at once:
    that is the only thing that ends reader.pump, and a pump that never
    ends keeps its window alive past the QApplication's death — a
    segfault at interpreter exit on every CI leg, after every test had
    passed."""

    description = "stub engine"

    def __init__(self):
        self.connection = None

    def connect(self):
        pass

    def read(self, output_callback):
        raise EOFError


class Connection:
    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)


def flush_deletes(qapp):
    """Run the queued deleteLater()s now, so nothing Qt-owned outlives
    the test that made it."""
    qapp.processEvents()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


@pytest.fixture(autouse=True)
def sweep_widgets(qapp):
    """Every top-level widget a test leaves behind is closed and deleted
    before the next test: Qt objects destroyed by Python's shutdown GC,
    after the QApplication, are the classic PyQt segfault."""
    yield
    for widget in qapp.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    flush_deletes(qapp)


@pytest.fixture
def window(qapp):
    """A ClientGUI around the stub engine, closed afterwards without
    the game quit (there is no game) — closeEvent still runs, saving
    the layout into the isolated QSettings — once its reader thread
    has ended and before the widget sweep."""
    from client.gui.client_gui import ClientGUI

    gui = ClientGUI(StubEngine(), character="Lanival")
    yield gui
    thread = gui._reader_thread
    if thread is not None:
        thread.join(timeout=5)
        assert not thread.is_alive(), "the stub reader thread must end"
    gui._detaching = True
    gui.close()
    gui.deleteLater()
    flush_deletes(qapp)


@pytest.fixture
def connection(window):
    """A recording connection plugged into the window's engine."""
    window.client.connection = Connection()
    return window.client.connection
