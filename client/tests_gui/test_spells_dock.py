"""The Spells dock draws the running spells with countdowns from the
"spells" stream, marks the prepared spell, and says when nothing runs
(#175)."""

from client.gui.spells_dock import EMPTY_TEXT, SpellsPanel, countdown, parse_frame

FRAME = "prepared\tHeroic Strength\nHeroic Strength\t10\nManifest Force\t"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_a_frame_parses_to_the_prepared_spell_and_the_rows():
    assert parse_frame(FRAME) == (
        "Heroic Strength",
        [("Heroic Strength", 10), ("Manifest Force", None)],
    )
    assert parse_frame("") == (None, [])
    assert parse_frame("Heroic Strength\t10") == (None, [("Heroic Strength", 10)])


def test_countdowns_read_as_minutes_and_seconds():
    assert countdown(600) == "10:00"
    assert countdown(535) == "8:55"
    assert countdown(-5) == "0:00"


def test_the_panel_counts_down_between_pulses_and_marks_the_prepared(qapp):
    clock = Clock()
    panel = SpellsPanel(clock=clock, ticking=False)
    assert panel.lines() == []
    assert not panel.empty_label.isHidden()
    assert panel.prepared_label.isHidden()
    panel.show_frame(FRAME)
    assert panel.lines() == ["Heroic Strength  10:00", "Manifest Force"]
    assert panel.prepared_label.text() == "prepared: Heroic Strength"
    assert not panel.prepared_label.isHidden()
    assert panel.empty_label.isHidden()
    clock.now += 65
    panel.tick()
    assert panel.lines() == ["Heroic Strength  8:55", "Manifest Force"]
    # The next pulse restarts the count from what the game says.
    panel.show_frame("Heroic Strength\t9")
    assert panel.lines() == ["Heroic Strength  9:00"]
    assert panel.prepared_label.isHidden()
    clock.now += 700
    panel.tick()
    assert panel.lines() == ["Heroic Strength  0:00"]
    panel.show_frame("")
    assert panel.lines() == []
    assert panel.empty_label.text() == EMPTY_TEXT
    assert not panel.empty_label.isHidden()


def test_the_window_routes_the_spells_stream_to_the_dock_and_drops_the_raw_text(
    window,
):
    window.dispatch_game_text("Heroic Strength\t10", "spells", "")
    assert window.spells.lines() == ["Heroic Strength  10:00"]
    assert "Spells" in window.stream_docks
    assert "Heroic Strength" not in window.main_window.toPlainText()
    # The raw Spells window the game pushes is the dock's source, not a
    # text stream any more: neither its lines nor its clear land anywhere.
    window.dispatch_game_text("", "percWindow", "clear")
    window.dispatch_game_text("Heroic Strength  (10 roisaen)\n", "percWindow", "")
    assert "roisaen" not in window.main_window.toPlainText()
    assert window.spells.lines() == ["Heroic Strength  10:00"]
