"""The settings editor: File → Settings… in the client.

Checkboxes over ~/.revenant/settings.json. The autostart toggles take
effect when the next session starts (a running session already made
its choices); quit-on-close is read live at window close, and the
clocks dock picks its row up within a minute.
"""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Revenant — Settings")
        layout = QVBoxLayout(self)
        self.autostart_xp = QCheckBox("Log experience history in every session (;xp)")
        self.autostart_xp.setChecked(bool(settings.get("autostart_xp")))
        self.autostart_beholder = QCheckBox(
            "Keep the dashboard server running (quiet ;beholder)"
        )
        self.autostart_beholder.setChecked(bool(settings.get("autostart_beholder")))
        self.autostart_sheet = QCheckBox(
            "Snapshot the character sheet every few hours (;sheet)"
        )
        self.autostart_sheet.setChecked(bool(settings.get("autostart_sheet")))
        self.quit_on_close = QCheckBox(
            "Quit the game when the window closes (File → Detach skips this)"
        )
        self.quit_on_close.setChecked(bool(settings.get("quit_on_close")))
        self.clocks_earth_moon = QCheckBox(
            "Show Earth's moon in the clocks dock (for fun)"
        )
        self.clocks_earth_moon.setChecked(bool(settings.get("clocks_earth_moon")))
        extra_label = QLabel("Also autostart these scripts (comma-separated):")
        self.autostart_extra = QLineEdit(
            ", ".join(settings.get("autostart_extra") or [])
        )
        self.autostart_extra.setPlaceholderText("lnet, athletics")
        note = QLabel("Autostart changes apply from the next session.")
        note.setStyleSheet("color: #808090;")
        for widget in (
            self.autostart_xp,
            self.autostart_beholder,
            self.autostart_sheet,
            self.quit_on_close,
            self.clocks_earth_moon,
            extra_label,
            self.autostart_extra,
            note,
        ):
            layout.addWidget(widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {
            "autostart_xp": self.autostart_xp.isChecked(),
            "autostart_beholder": self.autostart_beholder.isChecked(),
            "autostart_sheet": self.autostart_sheet.isChecked(),
            "autostart_extra": [
                entry.strip()
                for entry in self.autostart_extra.text().split(",")
                if entry.strip()
            ],
            "quit_on_close": self.quit_on_close.isChecked(),
            "clocks_earth_moon": self.clocks_earth_moon.isChecked(),
        }
