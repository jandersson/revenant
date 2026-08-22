"""The highlights editor: View → Edit Highlights… in the client.

A table of pattern / color / bold rows over ~/.revenant/highlights.json.
Double-click a color cell for the system color picker; Add and Remove
manage rows; OK saves and the client reloads its rules immediately.
Patterns that don't compile still save (the loader skips them at
runtime), so a half-written rule survives the dialog closing — but the
row count reported after saving tells you how many actually loaded.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from client.highlights import pattern_error

DEFAULT_COLOR = "#e0c95e"


class HighlightsDialog(QDialog):
    def __init__(self, entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Highlights")
        self.resize(520, 360)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Pattern (regex)", "Color", "Bold"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 280)
        self.table.setColumnWidth(1, 110)
        self.table.cellDoubleClicked.connect(self._pick_color)
        for entry in entries:
            self._add_row(
                str(entry.get("pattern", "")),
                str(entry.get("color") or DEFAULT_COLOR),
                bool(entry.get("bold")),
            )
        layout.addWidget(self.table)

        row_buttons = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(lambda: self._add_row("", DEFAULT_COLOR, False))
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self._remove_selected)
        row_buttons.addWidget(add_button)
        row_buttons.addWidget(remove_button)
        row_buttons.addStretch(1)
        layout.addLayout(row_buttons)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_row(self, pattern, color, bold):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(pattern))
        color_item = QTableWidgetItem(color)
        color_item.setBackground(QColor(color))
        self.table.setItem(row, 1, color_item)
        bold_item = QTableWidgetItem()
        bold_item.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        bold_item.setCheckState(
            Qt.CheckState.Checked if bold else Qt.CheckState.Unchecked
        )
        self.table.setItem(row, 2, bold_item)

    def _remove_selected(self):
        for index in sorted(
            {item.row() for item in self.table.selectedItems()}, reverse=True
        ):
            self.table.removeRow(index)

    def _pick_color(self, row, column):
        if column != 1:
            return
        current = QColor(self.table.item(row, 1).text() or DEFAULT_COLOR)
        chosen = QColorDialog.getColor(current, self, "Highlight color")
        if chosen.isValid():
            item = self.table.item(row, 1)
            item.setText(chosen.name())
            item.setBackground(chosen)

    def entries(self):
        """The table as raw rule entries (empty patterns dropped)."""
        result = []
        for row in range(self.table.rowCount()):
            pattern = (self.table.item(row, 0).text() or "").strip()
            if not pattern:
                continue
            result.append(
                {
                    "pattern": pattern,
                    "color": (self.table.item(row, 1).text() or "").strip()
                    or DEFAULT_COLOR,
                    "bold": self.table.item(row, 2).checkState()
                    == Qt.CheckState.Checked,
                }
            )
        return result

    def broken_patterns(self):
        return [
            entry["pattern"]
            for entry in self.entries()
            if pattern_error(entry["pattern"])
        ]
