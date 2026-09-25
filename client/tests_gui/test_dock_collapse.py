"""A dock folds to its title bar and opens again — by its button, a
double-click on the title, or the keyboard on the focused dock — and
the fold survives the layout round trip (#180)."""

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDockWidget

from client.gui import dock_collapse
from client.gui.client_gui import layout_settings
from client.gui.dock_collapse import COLLAPSE_GLYPH, EXPAND_GLYPH, DockTitleBar
from client.ui import window_layout


def test_collapse_hides_the_content_and_expand_brings_it_back(window):
    dock = window.stream_docks["Thoughts"]
    content = dock.widget()
    ceiling = dock.maximumHeight()
    assert not dock_collapse.is_collapsed(dock)
    content_ceiling = content.maximumHeight()
    assert dock_collapse.collapse(dock)
    assert dock_collapse.is_collapsed(dock)
    assert content.maximumHeight() == 0  # squeezed to nothing, not hidden (#201)
    assert not content.isHidden()
    assert dock.maximumHeight() < 80  # the title bar, not the content
    assert not dock_collapse.collapse(dock)  # already folded
    assert dock_collapse.expand(dock)
    assert not dock_collapse.is_collapsed(dock)
    assert content.maximumHeight() == content_ceiling
    assert dock.maximumHeight() == ceiling  # the dock's own ceiling is back
    assert not dock_collapse.expand(dock)


def test_a_folded_dock_leaves_the_dock_columns_width_free(window, qapp):
    # #201: folding a side dock pinned the whole column's width — the
    # separator no longer dragged — because the hidden content took its
    # width limits with it. Folded, the dock's maximum width is still
    # Qt's own and the main window can still resize the dock.
    # A side-column dock: a lone bottom dock spans the window and no
    # resize narrows it, folded or not.
    dock = dock_collapse.dock_of(window.injuries)
    window.resize(1700, 1000)  # room beside the column, which sits at its minimum
    window.show()
    qapp.processEvents()
    assert window.dockWidgetArea(dock) in (
        Qt.DockWidgetArea.LeftDockWidgetArea,
        Qt.DockWidgetArea.RightDockWidgetArea,
    )
    before_min = dock.minimumWidth()
    assert dock_collapse.collapse(dock)
    qapp.processEvents()
    # Folded, the width is not pinned: the maximum stays a layout-sized
    # "no maximum" (Qt reports its layout cap, 524287, not QWIDGETSIZE_MAX).
    assert dock.maximumWidth() > dock.minimumWidth() + 1000
    assert dock.minimumWidth() <= max(
        before_min, dock.titleBarWidget().minimumSizeHint().width()
    )
    target = dock.width() + 120  # wider: what the pinned maximum refused
    window.resizeDocks([dock], [target], Qt.Orientation.Horizontal)
    qapp.processEvents()
    assert dock.width() >= target - 4
    dock_collapse.expand(dock)


def test_a_floating_dock_is_left_alone(window):
    dock = window.stream_docks["Clocks"]
    dock.setFloating(True)
    assert not dock_collapse.collapse(dock)
    assert not dock.widget().isHidden()
    dock.setFloating(False)


def test_every_dock_but_the_command_line_has_the_title_bar_with_its_controls(
    window,
):
    for dock in window.findChildren(QDockWidget):
        bar = dock.titleBarWidget()
        if dock.objectName() == "Input":
            # The command line never folds: Ctrl+Shift+D with the cursor
            # there must not take the input away.
            assert bar is None
            assert not dock_collapse.collapse(dock)
            assert not window.toggle_dock_of(window.input)
            continue
        assert isinstance(bar, DockTitleBar), dock.objectName()
        assert bar.label.text() == dock.windowTitle()
    bar = window.stream_docks["Arrivals"].titleBarWidget()
    assert bar.collapse_button.text() == COLLAPSE_GLYPH
    bar.collapse_button.click()
    assert dock_collapse.is_collapsed(window.stream_docks["Arrivals"])
    assert bar.collapse_button.text() == EXPAND_GLYPH
    bar.collapse_button.click()
    assert not dock_collapse.is_collapsed(window.stream_docks["Arrivals"])
    assert bar.collapse_button.text() == COLLAPSE_GLYPH


def test_a_double_click_on_the_title_toggles(window):
    dock = window.stream_docks["Deaths"]
    bar = dock.titleBarWidget()
    QTest.mouseDClick(bar, Qt.MouseButton.LeftButton)
    assert dock_collapse.is_collapsed(dock)
    QTest.mouseDClick(bar, Qt.MouseButton.LeftButton)
    assert not dock_collapse.is_collapsed(dock)


def test_the_keyboard_action_works_on_the_dock_holding_the_focus(window):
    clocks = window.stream_docks["Clocks"]
    assert window.toggle_dock_of(clocks.widget())
    assert dock_collapse.is_collapsed(clocks)
    assert window.toggle_dock_of(clocks.widget())
    assert not dock_collapse.is_collapsed(clocks)
    assert not window.toggle_dock_of(window.main_window)  # the story: no dock
    assert not window.toggle_dock_of(None)
    assert window.collapse_dock_action.shortcut().toString() == "Ctrl+Shift+D"


def test_the_fold_is_saved_with_the_layout_and_applied_after_a_restore(window, qapp):
    docks = window.findChildren(QDockWidget)
    dock_collapse.collapse(window.stream_docks["Thoughts"])
    dock_collapse.collapse(window.stream_docks["Map"])
    assert dock_collapse.collapsed_names(docks) == ["Map", "Thoughts"]
    # A restore folds exactly the saved set, opening the rest.
    dock_collapse.apply_collapsed(docks, ["Clocks"])
    assert dock_collapse.collapsed_names(docks) == ["Clocks"]
    dock_collapse.collapse(window.stream_docks["Thoughts"])
    window._detaching = True
    window.close()
    qapp.processEvents()
    settings = layout_settings()
    saved = window_layout.collapsed_from(
        settings.value(window_layout.collapsed_key("Lanival"))
    )
    assert saved == ["Clocks", "Thoughts"]
    assert window_layout.collapsed_from(settings.value("collapsed")) == saved


def _tab_group(window, qapp):
    docks = {d.objectName(): d for d in window.findChildren(QDockWidget)}
    thoughts, injuries = docks["Thoughts"], docks["Injuries"]
    window.show()
    for dock in (thoughts, injuries):
        dock.show()
    window.tabifyDockWidget(thoughts, injuries)
    qapp.processEvents()
    return thoughts, injuries


def test_a_tabbed_dock_never_folds(window, qapp):
    # 2026-09-25: a folded tab gave the Thoughts/Injuries group its 23 px
    # ceiling, the group sat at its minimum and its separator would not
    # move. The tab bar already hides a tab.
    thoughts, injuries = _tab_group(window, qapp)
    assert dock_collapse.tabbed(injuries)
    assert not dock_collapse.collapse(injuries)
    assert not dock_collapse.is_collapsed(injuries)


def test_a_folded_dock_tabbed_into_a_group_unfolds_on_the_tab_switch(window, qapp):
    docks = {d.objectName(): d for d in window.findChildren(QDockWidget)}
    injuries = docks["Injuries"]
    window.show()
    injuries.show()
    qapp.processEvents()
    assert dock_collapse.collapse(injuries)  # folded while on its own
    thoughts, injuries = _tab_group(window, qapp)
    window.tabifiedDockWidgetActivated.emit(thoughts)
    assert not dock_collapse.is_collapsed(injuries)
    assert injuries.maximumHeight() > 1000


def test_a_restore_never_folds_a_tabbed_dock(window, qapp):
    thoughts, injuries = _tab_group(window, qapp)
    dock_collapse.apply_collapsed([thoughts, injuries], ["Injuries"])
    assert not dock_collapse.is_collapsed(injuries)
