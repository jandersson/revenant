"""The graphical login screen: account, password, character, remember-me.

Shown by the launcher when it needs credentials and has no terminal to
prompt in (a Revenant.app launch). The password is used once for the
login handshake; "remember" stores it in the OS keychain and the
account/character names in ~/.revenant/login.json, so the next launch
logs straight in without showing this screen.
"""

from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

ICON_PATH = str(Path(__file__).with_name("revenant.svg"))


class LoginDialog(QDialog):
    def __init__(self, account="", character="", error=""):
        super().__init__()
        self.setWindowTitle("Revenant — Log In")
        self.setWindowIcon(QIcon(ICON_PATH))
        form = QFormLayout(self)
        if error:
            message = QLabel(error)
            message.setWordWrap(True)
            message.setStyleSheet("color: #c05050;")
            form.addRow(message)
        self.account = QLineEdit(account)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.character = QLineEdit(character)
        self.remember = QCheckBox("Remember me (password goes to the system keychain)")
        form.addRow("Account", self.account)
        form.addRow("Password", self.password)
        form.addRow("Character", self.character)
        form.addRow(self.remember)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        (self.password if account else self.account).setFocus()


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
        dialog.character.text().strip(),
        dialog.remember.isChecked(),
    )
