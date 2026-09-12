"""The dock layout survives a round trip — what #124, #140 and #146
guarded by hand: stable object names, a hidden dock restored hidden,
the character's own layout applied to the hidden window."""

from PyQt6.QtWidgets import QDockWidget

from client.gui.client_gui import layout_settings
from client.ui import window_layout

DOCK_NAMES = {
    "Thoughts",
    "Spells",
    "Arrivals",
    "Deaths",
    "Experience",
    "Compass",
    "Clocks",
    "Map",
    "Input",
}


def dock_names(window):
    return {dock.objectName() for dock in window.findChildren(QDockWidget)}


def test_dock_object_names_are_the_ones_saved_layouts_key_on(window):
    # A rename here silently orphans every saved arrangement.
    assert DOCK_NAMES <= dock_names(window)


def test_a_hidden_dock_comes_back_hidden_from_a_saved_state(window):
    clocks = window.stream_docks["Clocks"]
    clocks.hide()
    state = window.saveState()
    clocks.show()
    assert window.restoreState(state)
    assert clocks.isHidden()


def test_the_characters_layout_is_applied_with_the_window_hidden(window):
    compass = window.stream_docks["Compass"]
    compass.hide()
    geometry, state = window.saveGeometry(), window.saveState()
    compass.show()
    assert window_layout.apply(window, geometry, state)
    assert compass.isHidden()
    assert window.isVisible()  # shown again afterwards


def test_closing_saves_the_characters_own_layout(window, qapp):
    window.stream_docks["Map"].hide()
    window._detaching = True
    window.close()
    qapp.processEvents()
    settings = layout_settings()
    geometry_key, state_key = window_layout.layout_keys("Lanival")
    assert settings.value(geometry_key) is not None
    assert settings.value(state_key) is not None
