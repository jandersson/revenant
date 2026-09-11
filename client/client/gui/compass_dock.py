"""The compass rose: clickable exits, lit when the room offers them.

Eight arrows on a ring around OUT, up/down beside, lit amber when the
room's compass frame offers the exit and dimmed to the ring otherwise;
a click sends the direction. The rose lays itself out for whatever
space the dock grants — a fixed-size rose in an elastic wrapper
painted over the neighboring docks whenever the column got crowded.
Split out of client_gui.py, which wraps it in the "Compass" dock.
"""

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QPushButton, QWidget

# Unit-circle offsets for the eight wind directions around a central
# OUT, with up/down stacked beside.
COMPASS_POINTS = {
    "n": (0.0, -1.0),
    "ne": (0.707, -0.707),
    "e": (1.0, 0.0),
    "se": (0.707, 0.707),
    "s": (0.0, 1.0),
    "sw": (-0.707, 0.707),
    "w": (-1.0, 0.0),
    "nw": (-0.707, -0.707),
}
COMPASS_ARROWS = {
    "n": "↑",
    "ne": "↗",
    "e": "→",
    "se": "↘",
    "s": "↓",
    "sw": "↙",
    "w": "←",
    "nw": "↖",
}


class CompassRose(QWidget):
    """The rose widget; `send(direction)` is called on a click."""

    def __init__(self, send):
        super().__init__()
        self.setStyleSheet(
            "QPushButton { background: #d8b465; color: #1c1c24;"
            "  font-weight: bold; border: 1px solid #8a733f; }"
            "QPushButton:disabled { background: #23232b; color: #4a4a55;"
            "  border: 1px solid #33333d; }"
        )
        self.buttons = {}
        for direction in COMPASS_POINTS:
            self._add_button(direction, COMPASS_ARROWS[direction], send)
        self._add_button("out", "out", send)
        self._add_button("up", "up", send)
        self._add_button("down", "dn", send)

    def sizeHint(self):
        return QSize(190, 150)

    def minimumSizeHint(self):
        return QSize(140, 104)

    def resizeEvent(self, event):
        self._layout(self.width(), self.height())
        super().resizeEvent(event)

    def _add_button(self, name, label, send):
        button = QPushButton(label, self)
        button.setEnabled(False)
        button.setToolTip(name)
        button.clicked.connect(lambda checked=False, d=name: send(d))
        self.buttons[name] = button

    def _layout(self, width, height):
        """Fit the rose to the dock's current size: the ring and the
        buttons scale down before anything can spill onto a neighbor."""
        side = max(22, min(36, height * 24 // 100))
        updn = max(18, side * 5 // 6)
        right_column = updn + 8
        ring = max(
            24,
            min((height - side) // 2 - 2, (width - right_column - side) // 2 - 2),
        )
        center_x = (width - right_column) // 2
        center_y = height // 2

        def place(name, x, y, size):
            button = self.buttons[name]
            button.setGeometry(int(x - size / 2), int(y - size / 2), size, size)
            button.setStyleSheet(f"border-radius: {size // 2}px;")

        for direction, (dx, dy) in COMPASS_POINTS.items():
            place(direction, center_x + dx * ring, center_y + dy * ring, side)
        place("out", center_x, center_y, side)
        offset = max(updn, side * 7 // 9)
        place("up", width - updn // 2 - 4, center_y - offset, updn)
        place("down", width - updn // 2 - 4, center_y + offset, updn)

    def set_exits(self, dirs_text: str):
        """A "compass" frame: the exits the room offers, space separated."""
        available = set(dirs_text.split())
        for direction, button in self.buttons.items():
            button.setEnabled(direction in available)
