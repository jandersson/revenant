"""The graphical login screen: account, password, character, remember-me.

Shown by the launcher when it needs credentials and has no terminal to
prompt in (a Revenant.app launch). The password is used once for the
login handshake; "remember" stores it in the OS keychain and the
account/character names in ~/.revenant/login.json, so the next launch
logs straight in without showing this screen. "Fetch characters" pulls
the account's roster from the server so the character is picked from a
list instead of typed — handy on a machine with no cached names yet.
"""

from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from client.login import LoginError, fetch_character_list, load_login_defaults

ICON_PATH = str(Path(__file__).with_name("revenant.svg"))


class LoginDialog(QDialog):
    def __init__(self, account="", character="", error=""):
        super().__init__()
        self.setWindowTitle("Revenant — Log In")
        self.setWindowIcon(QIcon(ICON_PATH))
        form = QFormLayout(self)
        self.status = QLabel(error)
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #c05050;")
        self.status.setVisible(bool(error))
        form.addRow(self.status)
        self.account = QLineEdit(account)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        # Known characters (cached from earlier logins) as a dropdown;
        # still editable for names the cache hasn't seen.
        self.character = QComboBox()
        self.character.setEditable(True)
        self.character.addItems(load_login_defaults().get("characters", []))
        self.character.setCurrentText(character)
        self.fetch = QPushButton("Fetch characters")
        self.fetch.setToolTip(
            "Look up the account's characters so you can pick from a list"
        )
        self.fetch.clicked.connect(self.fetch_characters)
        character_row = QHBoxLayout()
        character_row.addWidget(self.character, stretch=1)
        character_row.addWidget(self.fetch)
        self.remember = QCheckBox("Remember me (password goes to the system keychain)")
        form.addRow("Account", self.account)
        form.addRow("Password", self.password)
        form.addRow("Character", character_row)
        form.addRow(self.remember)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        (self.password if account else self.account).setFocus()

    def show_status(self, message, error=True):
        self.status.setStyleSheet("color: #c05050;" if error else "color: #508050;")
        self.status.setText(message)
        self.status.setVisible(bool(message))

    def fetch_characters(self):
        """Pull the roster with the entered account/password and load it
        into the dropdown. Synchronous: the handshake is sub-second and
        this is a modal dialog, so no thread juggling."""
        account = self.account.text().strip()
        password = self.password.text()
        if not account or not password:
            self.show_status("Enter account and password first, then fetch.")
            return
        self.fetch.setEnabled(False)
        QApplication.processEvents()
        try:
            names = sorted(fetch_character_list(account, password))
        except LoginError as error:
            self.show_status(str(error))
            return
        except OSError as error:
            self.show_status(f"Could not reach the login server: {error}")
            return
        finally:
            self.fetch.setEnabled(True)
        chosen = self.character.currentText().strip()
        self.character.clear()
        self.character.addItems(names)
        if chosen and chosen in names:
            self.character.setCurrentText(chosen)
        self.show_status(f"{len(names)} characters on {account}.", error=False)


def ask_character(roster, default=""):
    """A dropdown of the account's characters (the launcher's --pick
    mode); returns the chosen name, or None when the user cancelled."""
    from PyQt6.QtWidgets import QInputDialog

    app = QApplication.instance() or QApplication([])  # noqa: F841
    current = roster.index(default) if default in roster else 0
    name, accepted = QInputDialog.getItem(
        None, "Revenant", "Play as:", roster, current, False
    )
    return name if accepted else None


def ask_credentials(account="", character="", error=""):
    """Show the login screen; return (account, password, character,
    remember) or None if the user cancelled."""
    app = QApplication.instance() or QApplication([])  # noqa: F841
    dialog = LoginDialog(account, character, error)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return (
        dialog.account.text().strip(),
        dialog.password.text(),
        dialog.character.currentText().strip(),
        dialog.remember.isChecked(),
    )
