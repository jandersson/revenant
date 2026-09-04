"""A standalone LNet chat window:  revenant-chat [name]

Log into LNet as one of your own characters, with or without a game
session, and chat from a window of its own (#141). Only names from the
cached account rosters are offered or accepted: LNet names are
character names, and an invented one risks the account. Plain typing goes to your default
channel; the ;lnet commands work with or without the leading ";":
chat on <channel> <msg>, chat to <name> <msg>, reply <msg>, who [name],
stats, channels [all], tune/untune <channel>.

Identity: a roster name on the command line, else a picker over the
roster, preselecting the last name used (settings lnet_name). The password comes from the OS
keychain (client/lnet_login.py); a rejected login asks once, with a
"remember" checkbox that writes the keychain entry — never a file.

One worker thread owns the socket, the way ;lnet does: it drains the
command queue, then receives with a short timeout, so sends and
receives never race on the SSL socket. Rendered lines reach the
transcript through a queued signal.
"""

import argparse
import queue
import ssl
import sys
from pathlib import Path
from threading import Thread

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

# chat/ is a workspace member at the repo root that is not installed as a
# package (the session imports it from the repo root cwd); the console
# script can start anywhere, so the root goes on the path here.
_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from chat.chat import LoginRejected, Server, get_password  # noqa: E402
from chat.commands import input_to_command, obey  # noqa: E402
from client import lnet_login  # noqa: E402
from client.login import load_login_defaults  # noqa: E402
from client.settings import save_settings, setting  # noqa: E402

ICON_PATH = str(Path(__file__).with_name("gweth.svg"))
RECV_TIMEOUT = 0.25  # seconds between command-queue checks


class PasswordDialog(QDialog):
    """Asked once after LNet rejects a login: the name's password and
    whether to keep it in the keychain."""

    def __init__(self, name, reason, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"LNet password for {name}")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"LNet rejected the login for {name}:\n{reason}"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("password")
        layout.addWidget(self.password)
        self.remember = QCheckBox("Remember in the OS keychain")
        self.remember.setChecked(True)
        layout.addWidget(self.remember)
        note = QLabel("Forgotten? Reset it at https://lnet.lichproject.org")
        note.setStyleSheet("color: #808090;")
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ChatWindow(QMainWindow):
    line_received = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    login_rejected = pyqtSignal(str)
    connection_lost = pyqtSignal(str)

    def __init__(self, name, password):
        super().__init__()
        self.name = name
        self.password = password
        self.last_priv = None
        self._commands = queue.Queue()
        self._worker = None
        self._stopping = False
        self.setWindowTitle(f"Revenant Chat — {name}")
        self.setWindowIcon(QIcon(ICON_PATH))
        self._build_ui()
        self.line_received.connect(self._append)
        self.status_changed.connect(self.statusBar().showMessage)
        self.login_rejected.connect(self._ask_password)
        self.connection_lost.connect(self._lost)
        self.start()

    # -- UI ---------------------------------------------------------------

    def _build_ui(self):
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(4, 4, 4, 4)
        self.transcript = QTextBrowser()
        self.transcript.setOpenLinks(False)
        layout.addWidget(self.transcript, 1)
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "message to your default channel — or ;chat to <name> …, ;who, ;channels"
        )
        self.input.returnPressed.connect(self._send)
        layout.addWidget(self.input)
        self.setCentralWidget(column)
        reconnect = QAction("&Reconnect", self)
        reconnect.setShortcut("Ctrl+R")
        reconnect.triggered.connect(self.start)
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        menu = self.menuBar().addMenu("&Chat")
        menu.addAction(reconnect)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.resize(640, 480)
        self.input.setFocus()

    def _append(self, text):
        self.transcript.append(text)

    def _lost(self, reason):
        self._append(f"* connection lost: {reason} (Ctrl+R to reconnect)")
        self.statusBar().showMessage("Disconnected")

    # -- the worker: one thread owns the socket ----------------------------

    def start(self):
        """Connect (or reconnect) and start the worker; a running worker
        is left alone."""
        if self._worker is not None and self._worker.is_alive():
            self.statusBar().showMessage("Already connected")
            return
        self._stopping = False
        self.server = Server()
        self.server.set_login_info(self.name, password=self.password)
        self._worker = Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self):
        try:
            self.server.connect()
            self.server.login()
            self.server.connection.settimeout(RECV_TIMEOUT)
            self.status_changed.emit(f"Logging in as {self.name} …")
            while not self._stopping:
                self._drain_commands()
                try:
                    messages = self.server.receive_messages()
                except TimeoutError:
                    continue
                for message in messages:
                    if isinstance(message, bytes):
                        continue  # unrecognized protocol element
                    if message.message_type == "greeting":
                        self.status_changed.emit(f"Connected as {self.name}")
                    if message.message_type == "private" and message.sender:
                        self.last_priv = message.sender
                    self.line_received.emit(str(message))
        except LoginRejected as rejection:
            self.login_rejected.emit(str(rejection))
        except (ssl.SSLError, ConnectionError, OSError) as error:
            if not self._stopping:
                self.connection_lost.emit(str(error))
        finally:
            try:
                self.server.connection.close()
            except Exception:
                pass

    def _drain_commands(self):
        while True:
            try:
                line = self._commands.get_nowait()
            except queue.Empty:
                return
            self.last_priv = obey(
                self.line_received.emit, self.server, line, self.last_priv
            )

    # -- input -------------------------------------------------------------

    def _send(self):
        command = input_to_command(self.input.text())
        self.input.clear()
        if command is None:
            return
        if self._worker is None or not self._worker.is_alive():
            self._append("* not connected (Ctrl+R to reconnect)")
            return
        self._commands.put(command)

    # -- login rejected: ask once, remember on request --------------------

    def _ask_password(self, reason):
        dialog = PasswordDialog(self.name, reason, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.password.text():
            self._append(f"* login rejected: {reason}")
            self.statusBar().showMessage("Login rejected")
            return
        self.password = dialog.password.text()
        if dialog.remember.isChecked() and not lnet_login.remember(
            self.name, self.password
        ):
            self._append("* no OS keychain available — the password holds for this run")
        self.start()

    def closeEvent(self, event):
        self._stopping = True
        try:
            self.server.connection.close()
        except Exception:
            pass
        super().closeEvent(event)


def choose_name(names, parent=None):
    """One of your characters, from the roster; None when cancelled or
    when no roster is cached yet."""
    if not names:
        return None
    remembered = setting("lnet_name") or ""
    current = names.index(remembered) if remembered in names else 0
    name, ok = QInputDialog.getItem(
        parent, "Revenant Chat", "Log into LNet as:", names, current, False
    )
    return name if ok and name else None


def main(argv=None):
    parser = argparse.ArgumentParser(description="A standalone LNet chat window")
    parser.add_argument("name", nargs="?", help="which of your characters to log in as")
    args = parser.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setWindowIcon(QIcon(ICON_PATH))
    defaults = load_login_defaults()
    names = lnet_login.identities(defaults)
    if not names:
        print(
            "revenant-chat: no characters cached yet - log into the game once "
            "with remember ticked, then retry",
            file=sys.stderr,
        )
        return 2
    if args.name:
        name = lnet_login.allowed(args.name, defaults)
        if not name:
            print(
                f"revenant-chat: {args.name!r} is not one of your characters "
                f"(cached: {', '.join(names)}) - LNet names are character names",
                file=sys.stderr,
            )
            return 2
    else:
        name = choose_name(names)
    if not name:
        return 0
    save_settings({"lnet_name": name})
    password = lnet_login.lnet_password(name, legacy_file=get_password)
    window = ChatWindow(name, password)
    window.show()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
