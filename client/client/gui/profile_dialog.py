"""The character profile editor: File → Character Profile… in the client.

One row per entry of client.profile.FIELDS, built from that schema, so
a new profile setting appears here the moment it gets a default and a
row — checkboxes for yes/no, spinners for numbers, text for the rest
(lists as comma-separated text). Saves to
~/.revenant/profiles/<character>.json; ;hunt reads the file at each
start, so a change reaches the next run without a restart.
"""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from client.profile import FIELDS


class ProfileDialog(QDialog):
    def __init__(self, character, profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Revenant — Character Profile: {character or 'unnamed'}")
        layout = QVBoxLayout(self)
        intro = QLabel(
            "What ;hunt does for this character. Empty means the game's default."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.widgets = {}
        for key, label, kind, help_text in FIELDS:
            value = profile.get(key)
            if kind == "bool":
                widget = QCheckBox()
                widget.setChecked(bool(value))
            elif kind == "int":
                widget = QSpinBox()
                widget.setRange(0, 100000)
                widget.setValue(int(value or 0))
            else:
                text = ", ".join(value) if kind == "list" else str(value or "")
                widget = QLineEdit(text)
                if help_text:
                    widget.setPlaceholderText(help_text)
            if help_text and kind in ("bool", "int"):
                widget.setToolTip(help_text)
            form.addRow(f"{label}:", widget)
            self.widgets[key] = (kind, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        """The form as profile values; client.profile.normalize coerces
        the text fields when they are saved."""
        values = {}
        for key, (kind, widget) in self.widgets.items():
            if kind == "bool":
                values[key] = widget.isChecked()
            elif kind == "int":
                values[key] = widget.value()
            else:
                values[key] = widget.text()
        return values
