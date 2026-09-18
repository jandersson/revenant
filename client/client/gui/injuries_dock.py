"""The Injuries dock: the game's injuries panel as a body of badges.

One label per body part in a rough body layout, dim when the part is
clean, amber for a fresh wound and purple for a scar with the panel's
level beside the name — driven by the "injuries" stream ("head wound
1 chest scar 2", "" for clean), which the engine emits whenever the
game pushes its <dialogData id="injuries"> (#163) and the session
states on every attach, clean or not, so a window that attaches after
the wounds healed shows none (#213). Coarser than HEALTH
(docs/wounds.md): the panel says which parts and roughly how much,
right now, without asking — and the panel omits light hits, so the
dock can look clean while the health bar says hurt.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget

# Panel part id -> (label, row, column) in the body layout.
PARTS = {
    "head": ("head", 0, 1),
    "leftEye": ("l.eye", 1, 0),
    "neck": ("neck", 1, 1),
    "rightEye": ("r.eye", 1, 2),
    "leftArm": ("l.arm", 2, 0),
    "chest": ("chest", 2, 1),
    "rightArm": ("r.arm", 2, 2),
    "leftHand": ("l.hand", 3, 0),
    "abdomen": ("abdomen", 3, 1),
    "rightHand": ("r.hand", 3, 2),
    "back": ("back", 4, 1),
    "leftLeg": ("l.leg", 5, 0),
    "nsys": ("nerves", 5, 1),
    "rightLeg": ("r.leg", 5, 2),
    "leftFoot": ("l.foot", 6, 0),
    "rightFoot": ("r.foot", 6, 2),
}

CLEAN_STYLE = "color: #4a4a55; padding: 2px 6px;"
WOUND_STYLE = (
    "background: #d8b465; color: #1c1c24; font-weight: bold;"
    " border-radius: 3px; padding: 2px 6px;"
)
SCAR_STYLE = (
    "background: #b39ddb; color: #1c1c24; font-weight: bold;"
    " border-radius: 3px; padding: 2px 6px;"
)


def parse_frame(text):
    """{part: (kind, level)} from an "injuries" frame; {} when clean."""
    words = text.split()
    hurt = {}
    for part, kind, level in zip(words[::3], words[1::3], words[2::3]):
        try:
            hurt[part] = (kind, int(level))
        except ValueError:
            continue
    return hurt


class InjuriesPanel(QWidget):
    def __init__(self):
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(3)
        self.labels = {}
        for part, (label, row, column) in PARTS.items():
            badge = QLabel(label)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(badge, row, column)
            self.labels[part] = badge
        grid.setRowStretch(len({r for _, r, _ in PARTS.values()}), 1)
        self.hurt = {}
        self.show_frame("")

    def show_frame(self, text):
        """An "injuries" frame: every part restyled, hurt or clean."""
        self.hurt = parse_frame(text)
        for part, badge in self.labels.items():
            label = PARTS[part][0]
            state = self.hurt.get(part)
            if state is None:
                badge.setText(label)
                badge.setStyleSheet(CLEAN_STYLE)
                badge.setToolTip(f"{label}: clean")
            else:
                kind, level = state
                badge.setText(f"{label} {level}")
                badge.setStyleSheet(SCAR_STYLE if kind == "scar" else WOUND_STYLE)
                badge.setToolTip(f"{label}: {kind} {level}")
