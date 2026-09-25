"""Collapse a dock to its title bar and expand it again (#180).

Ten docks crowd the window, and hiding one through the View menu
loses its place in the layout. A collapsed dock keeps its place and
its title bar and gives up its space: the content widget is hidden
(the content squeezed to zero height, not hidden — hidden, it took
its width limits with it and the dock column could no longer be
resized, #201) and the dock's height pinned to the title bar's;
expanding lifts the
pin, shows the content and asks the main window for the height the
dock had. Three ways to do it — the ▾ button on the title bar, a
double-click on the title, or the View menu's Collapse/Expand Dock
action (Ctrl+Shift+D) on the dock holding the keyboard focus. The
title bar is our own widget (a QDockWidget's default one has no room
for a button), so it carries the float and close buttons too. A
floating dock is left alone: collapsing is for docks in the layout,
and only docks given this title bar fold at all — the Input dock (the
command line) keeps Qt's own and never folds, so Ctrl+Shift+D with
the cursor in the command line does nothing.

A dock that shares a tab group never folds: Qt gives the group the
lowest ceiling among its tabs, so one folded tab pinned the whole
group at its minimum and the separator under it would not move
(Thoughts with Injuries and Spells, 2026-09-25). The tab bar already
hides a tab; `collapse` refuses one, a folded dock tabbed into a group
unfolds when its group's tab is switched (`unfold_group`, wired to the
main window's tabifiedDockWidgetActivated), and a restore never folds
a tabbed dock again.

The collapsed set rides the layout round trip: `collapsed_names`
lists the docks to save beside the window state, `apply_collapsed`
folds them again after a restore (client/ui/window_layout.py keys).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QToolButton,
    QWidget,
)

COLLAPSED = "collapsed"  # the dock's dynamic property
EXPANDED_HEIGHT = "expanded_height"  # remembered across a collapse
EXPANDED_MAX = "expanded_max_height"  # the dock's own ceiling, restored
CONTENT_MAX = "content_max_height"  # the content's own ceiling and floor,
CONTENT_MIN = "content_min_height"  # restored on expand (#201)
QWIDGETSIZE_MAX = 16777215  # Qt's "no maximum"
COLLAPSE_GLYPH, EXPAND_GLYPH = "▾", "▸"  # ▾ ▸
FLOAT_GLYPH, CLOSE_GLYPH = "❐", "✕"  # ❐ ✕


class DockTitleBar(QWidget):
    """A dock's title bar: the title, then collapse, float and close."""

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 2, 2)
        row.setSpacing(2)
        self.label = QLabel(dock.windowTitle())
        row.addWidget(self.label, 1)
        self.collapse_button = self._button(
            COLLAPSE_GLYPH, "Collapse to the title bar (or double-click the title)"
        )
        self.collapse_button.clicked.connect(lambda: toggle(self.dock))
        self.float_button = self._button(FLOAT_GLYPH, "Float / dock")
        self.float_button.clicked.connect(
            lambda: self.dock.setFloating(not self.dock.isFloating())
        )
        self.close_button = self._button(
            CLOSE_GLYPH, "Close (View menu shows it again)"
        )
        self.close_button.clicked.connect(self.dock.close)
        for button in (self.collapse_button, self.float_button, self.close_button):
            row.addWidget(button)
        dock.windowTitleChanged.connect(self.label.setText)

    def _button(self, glyph, tip):
        button = QToolButton(self)
        button.setText(glyph)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def mouseDoubleClickEvent(self, event):
        toggle(self.dock)

    def show_collapsed(self, collapsed):
        self.collapse_button.setText(EXPAND_GLYPH if collapsed else COLLAPSE_GLYPH)
        self.collapse_button.setToolTip(
            "Expand (or double-click the title)"
            if collapsed
            else "Collapse to the title bar (or double-click the title)"
        )


def install(dock):
    """Give a dock the title bar with the controls; returns it."""
    bar = DockTitleBar(dock)
    dock.setTitleBarWidget(bar)
    return bar


def is_collapsed(dock):
    return bool(dock.property(COLLAPSED))


def foldable(dock):
    """Only a dock with our title bar folds; the Input dock keeps Qt's."""
    return isinstance(dock.titleBarWidget(), DockTitleBar)


def tabbed(dock):
    """True when the dock shares a tab group with another open dock."""
    main = dock.parentWidget()
    if not isinstance(main, QMainWindow):
        return False
    return any(not other.isHidden() for other in main.tabifiedDockWidgets(dock))


def collapse(dock):
    """Fold the dock to its title bar; False when it already is, floats,
    shares a tab group (a folded tab caps the whole group), or is not
    foldable."""
    if is_collapsed(dock) or dock.isFloating() or not foldable(dock) or tabbed(dock):
        return False
    bar = dock.titleBarWidget()
    dock.setProperty(EXPANDED_HEIGHT, dock.height())
    dock.setProperty(EXPANDED_MAX, dock.maximumHeight())
    content = dock.widget()
    if content is not None:
        # Squeezed to nothing, not hidden: a QDockWidget takes its
        # minimum and maximum width from its layout, and with the
        # content hidden both come from the title bar alone, which
        # pinned the whole dock column's width until the dock was
        # expanded again (#201). At zero height the content still
        # lends the dock its width limits and paints nothing.
        dock.setProperty(CONTENT_MAX, content.maximumHeight())
        dock.setProperty(CONTENT_MIN, content.minimumHeight())
        content.setMinimumHeight(0)
        content.setMaximumHeight(0)
    dock.setMaximumHeight(bar.sizeHint().height() + 4)
    dock.setProperty(COLLAPSED, True)
    bar.show_collapsed(True)
    return True


def expand(dock):
    """Open a collapsed dock back to the height it had; False when it
    is not collapsed."""
    if not is_collapsed(dock):
        return False
    ceiling = dock.property(EXPANDED_MAX)
    dock.setMaximumHeight(int(ceiling) if ceiling else QWIDGETSIZE_MAX)
    content = dock.widget()
    if content is not None:
        floor, ceiling = dock.property(CONTENT_MIN), dock.property(CONTENT_MAX)
        content.setMinimumHeight(int(floor) if floor else 0)
        content.setMaximumHeight(int(ceiling) if ceiling else QWIDGETSIZE_MAX)
    dock.setProperty(COLLAPSED, False)
    bar = dock.titleBarWidget()
    if isinstance(bar, DockTitleBar):
        bar.show_collapsed(False)
    height = dock.property(EXPANDED_HEIGHT)
    main = dock.parentWidget()
    if isinstance(main, QMainWindow) and height:
        main.resizeDocks([dock], [int(height)], Qt.Orientation.Vertical)
    return True


def unfold_group(dock):
    """Expand the dock and every folded dock tabbed with it — a fold
    from before the dock joined the group would cap the group's
    height. Wired to QMainWindow.tabifiedDockWidgetActivated."""
    main = dock.parentWidget()
    group = [dock]
    if isinstance(main, QMainWindow):
        group += main.tabifiedDockWidgets(dock)
    for member in group:
        expand(member)


def toggle(dock):
    return expand(dock) if is_collapsed(dock) else collapse(dock)


def dock_of(widget):
    """The QDockWidget holding a widget, or None (the story, the menu)."""
    while widget is not None:
        if isinstance(widget, QDockWidget):
            return widget
        widget = widget.parentWidget()
    return None


def collapsed_names(docks):
    """The object names of the collapsed docks, sorted — what the
    layout saves."""
    return sorted(dock.objectName() for dock in docks if is_collapsed(dock))


def apply_collapsed(docks, names):
    """Fold the named docks after a layout restore; unnamed ones are
    expanded, so a stale fold does not outlive its saved state. A
    tabbed dock stays open whatever the saved set says."""
    wanted = set(names)
    for dock in docks:
        if dock.objectName() in wanted and not tabbed(dock):
            collapse(dock)
        else:
            expand(dock)
