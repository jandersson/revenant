"""The settings editor: File → Settings… in the client.

Checkboxes over ~/.revenant/settings.json, plus the game text's font
(family and point size, or the platform default — applied to every
text view the moment the dialog is accepted, #118). The autostart
toggles take effect when the next session starts (a running session
already made its choices); quit-on-close is read live at window close,
and the clocks dock picks its row up within a minute.
"""

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from client.textfont import MAX_SIZE, MIN_SIZE, font_choice


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
        self.autostart_deathwatch = QCheckBox(
            "Depart safely if you die unattended (;deathwatch)"
        )
        self.autostart_deathwatch.setChecked(bool(settings.get("autostart_deathwatch")))
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
        # The game text's font: the platform default, or a family and
        # size of your own. The pickers are always live — touching one
        # unticks the default (greyed-out pickers under a checkbox read
        # as broken, #130); ticking it again is the way back.
        family, size = font_choice(settings)
        self.font_default = QCheckBox("Use the platform default font for game text")
        self.font_default.setChecked(family is None and size is None)
        self.font_family = QFontComboBox()
        self.font_family.setCurrentFont(QFont(family) if family else self.font())
        self.font_size = QSpinBox()
        self.font_size.setRange(MIN_SIZE, MAX_SIZE)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(size or max(MIN_SIZE, self.font().pointSize()))
        font_row = QWidget()
        row_layout = QHBoxLayout(font_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("Game text font:"))
        row_layout.addWidget(self.font_family, 1)
        row_layout.addWidget(self.font_size)
        self.font_family.currentFontChanged.connect(self._font_picked)
        self.font_size.valueChanged.connect(self._font_picked)
        for widget in (
            self.autostart_xp,
            self.autostart_beholder,
            self.autostart_sheet,
            self.autostart_deathwatch,
            self.quit_on_close,
            self.clocks_earth_moon,
            extra_label,
            self.autostart_extra,
            note,
            self.font_default,
            font_row,
        ):
            layout.addWidget(widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _font_picked(self, *_):
        """A picked family or size is a choice: the default no longer
        applies unless it is ticked again afterwards."""
        self.font_default.setChecked(False)

    def values(self):
        use_default = self.font_default.isChecked()
        return {
            "autostart_xp": self.autostart_xp.isChecked(),
            "autostart_beholder": self.autostart_beholder.isChecked(),
            "autostart_sheet": self.autostart_sheet.isChecked(),
            "autostart_deathwatch": self.autostart_deathwatch.isChecked(),
            "autostart_extra": [
                entry.strip()
                for entry in self.autostart_extra.text().split(",")
                if entry.strip()
            ],
            "quit_on_close": self.quit_on_close.isChecked(),
            "clocks_earth_moon": self.clocks_earth_moon.isChecked(),
            "font_family": (
                "" if use_default else self.font_family.currentFont().family()
            ),
            "font_size": 0 if use_default else self.font_size.value(),
        }
