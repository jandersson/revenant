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

from PyQt6.QtCore import Qt
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
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from client.login import (
    OTHER_ACCOUNT,
    LoginError,
    account_roster,
    fetch_character_list,
    load_login_defaults,
)

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
        self.password.setPlaceholderText("blank = use the saved password")
        # Known characters (cached from earlier logins) as a dropdown;
        # still editable for names the cache hasn't seen. Strictly the
        # shown account's roster: a blank account (the picker's "Other
        # account...") starts with a blank list, not the saved account's.
        self.character = QComboBox()
        self.character.setEditable(True)
        self.character.addItems(account_roster(load_login_defaults(), account))
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


class CharacterPicker(QDialog):
    """The launcher's character select: every character visible at once
    in a list — no dropdown to burrow into — with double-click (or
    Enter) to play, and the alternate paths as plain buttons."""

    def __init__(self, roster, default="", account=""):
        super().__init__()
        self.setWindowTitle("Revenant")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.other_account = False
        layout = QVBoxLayout(self)
        # Nobody is logged in yet: the heading states whose saved roster
        # this is, and the switch button offers to use a different one.
        if account:
            layout.addWidget(QLabel(f"Account: {account}"))
        layout.addWidget(QLabel("Play as:"))
        self.list = QListWidget()
        self.list.addItems(roster)
        matches = self.list.findItems(default, Qt.MatchFlag.MatchExactly)
        self.list.setCurrentItem(matches[0] if matches else self.list.item(0))
        self.list.itemDoubleClicked.connect(lambda item: self.accept())
        # Show the whole roster without scrolling, up to a sane cap.
        row = max(self.list.sizeHintForRow(0), 1)
        self.list.setMinimumHeight(min(row * (self.list.count() + 1), 420))
        layout.addWidget(self.list)
        buttons = QDialogButtonBox()
        play = buttons.addButton("Play", QDialogButtonBox.ButtonRole.AcceptRole)
        play.setDefault(True)
        # Always offered: the picker's entries can span accounts, and a
        # brand-new account has to be reachable from here (#58).
        switch = buttons.addButton(
            "Other account…", QDialogButtonBox.ButtonRole.ActionRole
        )
        switch.clicked.connect(self._choose_other_account)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.list.setFocus()

    def _choose_other_account(self):
        self.other_account = True
        self.accept()


def ask_character(roster, default="", account=""):
    """The character-select screen (the launcher's --pick mode); returns
    the chosen name, OTHER_ACCOUNT when the user wants to log in with a
    different account, or None when the user cancelled."""
    app = QApplication.instance() or QApplication([])  # noqa: F841
    dialog = CharacterPicker(roster, default, account)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    if dialog.other_account:
        return OTHER_ACCOUNT
    item = dialog.list.currentItem()
    return item.text() if item else None


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
