"""The Injuries dock paints the panel's hurt parts and clears them."""

from client.gui.injuries_dock import PARTS, InjuriesPanel, parse_frame


def test_a_frame_parses_to_parts():
    assert parse_frame("head wound 1 back scar 2") == {
        "head": ("wound", 1),
        "back": ("scar", 2),
    }
    assert parse_frame("") == {}
    assert parse_frame("head wound x") == {}


def test_the_panel_has_every_part_and_starts_clean(qapp):
    panel = InjuriesPanel()
    assert set(panel.labels) == set(PARTS)
    assert panel.hurt == {}
    assert panel.labels["head"].text() == "head"
    assert "#4a4a55" in panel.labels["head"].styleSheet()


def test_hurt_parts_light_up_and_clear_again(qapp):
    panel = InjuriesPanel()
    panel.show_frame("head wound 1 back scar 2")
    assert panel.labels["head"].text() == "head 1"
    assert "#d8b465" in panel.labels["head"].styleSheet()
    assert panel.labels["back"].text() == "back 2"
    assert "#b39ddb" in panel.labels["back"].styleSheet()
    assert panel.labels["chest"].text() == "chest"
    panel.show_frame("")
    assert panel.labels["head"].text() == "head"
    assert "#4a4a55" in panel.labels["head"].styleSheet()


def test_the_window_routes_the_injuries_stream_to_the_dock(window):
    window.dispatch_game_text("rightArm wound 1", "injuries", "")
    assert window.injuries.hurt == {"rightArm": ("wound", 1)}
    assert window.injuries.labels["rightArm"].text() == "r.arm 1"
    assert "Injuries" in window.stream_docks
    assert "rightArm" not in window.main_window.toPlainText()
