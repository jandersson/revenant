"""The settings editor: File → Settings… in the client.

Checkboxes over ~/.revenant/settings.json, plus the game text's font
(family and point size, applied to every text view the moment the
dialog is accepted, #118) and, under it, one row per text view to
override that pair for the view alone — tick the view, pick its font
(#132); an unticked row follows the default. The pickers open on the font the window
is using — the platform's until you choose one — and always save an
explicit choice; a "use the default" checkbox that locked the pickers
read as broken (#130), and a reset button would only exist to be
hit by accident. The autostart
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

from client.textfont import MAX_SIZE, MIN_SIZE, TEXT_VIEWS, font_choice, view_font


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
        self.answer_idle_warning = QCheckBox(
            "Answer the game's idle warning with TIME so a quiet window stays in"
        )
        self.answer_idle_warning.setChecked(bool(settings.get("answer_idle_warning")))
        self.clocks_earth_moon = QCheckBox(
            "Show Earth's moon in the clocks dock (for fun)"
        )
        self.clocks_earth_moon.setChecked(bool(settings.get("clocks_earth_moon")))
        self.dev_mode = QCheckBox(
            "Developer mode: report script starts that are slow to load"
        )
        self.dev_mode.setChecked(bool(settings.get("dev_mode")))
        self.allow_external_send = QCheckBox(
            "Allow external tools to send any command (revenant-send); "
            "read-only commands always pass"
        )
        self.allow_external_send.setChecked(bool(settings.get("allow_external_send")))
        extra_label = QLabel("Also autostart these scripts (comma-separated):")
        self.autostart_extra = QLineEdit(
            ", ".join(settings.get("autostart_extra") or [])
        )
        self.autostart_extra.setPlaceholderText("lnet, athletics")
        note = QLabel("Autostart changes apply from the next session.")
        note.setStyleSheet("color: #808090;")
        # The game text's font, pre-filled with what the window uses now:
        # the saved choice, or the platform font while nothing is saved.
        family, size = font_choice(settings)
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
        # Per-view overrides (#132): a ticked row keeps its own pair.
        overrides = settings.get("dock_fonts") or {}
        self.view_rows = {}
        view_rows = []
        for view in TEXT_VIEWS:
            entry = overrides.get(view) if isinstance(overrides, dict) else None
            tick = QCheckBox(view)
            tick.setChecked(isinstance(entry, dict) and bool(entry))
            own_family, own_size = view_font(settings, view)
            family_box = QFontComboBox()
            family_box.setCurrentFont(QFont(own_family) if own_family else self.font())
            size_box = QSpinBox()
            size_box.setRange(MIN_SIZE, MAX_SIZE)
            size_box.setSuffix(" pt")
            size_box.setValue(own_size or max(MIN_SIZE, self.font().pointSize()))
            for box in (family_box, size_box):
                box.setEnabled(tick.isChecked())
                tick.toggled.connect(box.setEnabled)
            row = QWidget()
            row_box = QHBoxLayout(row)
            row_box.setContentsMargins(24, 0, 0, 0)
            row_box.addWidget(tick)
            row_box.addWidget(family_box, 1)
            row_box.addWidget(size_box)
            self.view_rows[view] = (tick, family_box, size_box)
            view_rows.append(row)
        views_label = QLabel("Per-view fonts (ticked views keep their own):")
        for widget in (
            self.autostart_xp,
            self.autostart_beholder,
            self.autostart_sheet,
            self.autostart_deathwatch,
            self.quit_on_close,
            self.answer_idle_warning,
            self.clocks_earth_moon,
            self.dev_mode,
            self.allow_external_send,
            extra_label,
            self.autostart_extra,
            note,
            font_row,
            views_label,
            *view_rows,
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
            "autostart_deathwatch": self.autostart_deathwatch.isChecked(),
            "autostart_extra": [
                entry.strip()
                for entry in self.autostart_extra.text().split(",")
                if entry.strip()
            ],
            "quit_on_close": self.quit_on_close.isChecked(),
            "answer_idle_warning": self.answer_idle_warning.isChecked(),
            "clocks_earth_moon": self.clocks_earth_moon.isChecked(),
            "dev_mode": self.dev_mode.isChecked(),
            "allow_external_send": self.allow_external_send.isChecked(),
            "font_family": self.font_family.currentFont().family(),
            "font_size": self.font_size.value(),
            "dock_fonts": {
                view: {
                    "family": family_box.currentFont().family(),
                    "size": size_box.value(),
                }
                for view, (tick, family_box, size_box) in self.view_rows.items()
                if tick.isChecked()
            },
        }
