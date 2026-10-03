"""Each stream's frame lands in the widget that shows it — the manual
for dispatch_game_text, on the offscreen window."""

import time


def test_a_compass_frame_lights_the_offered_exits(window):
    window.dispatch_game_text("n e out", "compass", "")
    lit = {
        name for name, button in window.compass.buttons.items() if button.isEnabled()
    }
    assert lit == {"n", "e", "out"}
    window.dispatch_game_text("", "compass", "")
    assert not any(button.isEnabled() for button in window.compass.buttons.values())


def test_vitals_bars_appear_on_first_mention_with_the_games_labels(window):
    strip = window.input_strip
    assert not strip._vitals_row.isVisibleTo(window)
    window.dispatch_game_text("health 80 stamina 95", "vitals", "")
    assert strip.vitals_bars["health"].value() == 80
    assert strip.vitals_bars["stamina"].format().startswith("fatigue")
    assert strip._vitals_row.isVisibleTo(window)
    # A caster's mana bar arrives the moment the stream mentions it.
    window.dispatch_game_text("health 80 stamina 95 mana 40", "vitals", "")
    assert list(strip.vitals_bars) == ["health", "stamina", "mana"]
    assert strip.vitals_bars["mana"].value() == 40


def test_indicators_show_posture_and_badges_and_dead_overrides_them(window):
    strip = window.input_strip
    window.dispatch_game_text("IconKNEELING IconBLEEDING IconHIDDEN", "indicators", "")
    text = strip.status_strip.text()
    assert "kneeling" in text and "bleeding" in text and "hidden" in text
    window.dispatch_game_text("IconSTANDING IconBLEEDING IconDEAD", "indicators", "")
    assert strip.status_strip.text() == '<b style="color:#e05252">DEAD</b>'
    window.dispatch_game_text("IconSTANDING", "indicators", "")
    assert "standing" in strip.status_strip.text()
    assert "DEAD" not in strip.status_strip.text()


def test_a_roundtime_frame_counts_down_beside_the_input(window):
    strip = window.input_strip
    now = int(time.time())
    window.dispatch_game_text(f"{now + 5}\t{now}", "roundtime", "")
    assert strip.rt_label.text() in ("RT 5", "RT 6")
    assert strip.rt_timer.isActive()
    assert not strip.ct_label.isVisibleTo(window)
    window.dispatch_game_text(f"{now + 3}\t{now}", "casttime", "")
    assert strip.ct_label.text().startswith("CT ")
    assert strip.ct_label.isVisibleTo(window)


def test_a_stale_roundtime_frame_does_not_wake_the_ticker(window):
    strip = window.input_strip
    now = int(time.time())
    window.dispatch_game_text(f"{now - 10}\t{now}", "roundtime", "")
    assert strip.rt_label.text() == ""
    assert not strip.rt_timer.isActive()
    window.dispatch_game_text("garbage", "roundtime", "")  # never raises


def test_a_timesync_frame_anchors_the_clocks_to_server_time(window):
    window.dispatch_game_text("12.5", "timesync", "")
    assert window.clocks.server_delta == 12.5
    window.dispatch_game_text("not a number", "timesync", "")
    assert window.clocks.server_delta == 12.5
    window.clocks.refresh()
    assert window.clocks.labels["Elanthia"].text()
    assert window.clocks.labels["Moons"].text()


def test_text_goes_to_its_dock_and_a_clear_wipes_only_that_dock(window):
    window.dispatch_game_text("A troll lumbers in.\n", "", "bold")
    window.dispatch_game_text("psst\n", "thoughts", "")
    assert "troll" in window.main_window.toPlainText()
    assert window.stream_windows["thoughts"].toPlainText().strip() == "psst"
    assert "psst" not in window.main_window.toPlainText()
    window.dispatch_game_text("", "thoughts", "clear")
    assert window.stream_windows["thoughts"].toPlainText() == ""
    # An undocked stream's clear must not blank the story (#109).
    window.dispatch_game_text("", "inv", "clear")
    assert "troll" in window.main_window.toPlainText()


def test_a_said_line_shows_in_the_story_and_in_the_talk_dock(window):
    # The parser routes the talk stream's copy and the main stream's
    # (captured 2026-10-02); the dock is for seeing at a glance that
    # someone spoke, the story keeps the line where it happened.
    yell = 'You hear a female voice yell from the somewhere nearby, "Kailisa!"\n'
    window.dispatch_game_text(yell, "talk", "")
    window.dispatch_game_text(yell, "", "")
    whisper = 'Uthmor whispers, "over here"\n'
    window.dispatch_game_text(whisper, "whispers", "")
    window.dispatch_game_text(whisper, "", "")
    talk = window.stream_docks["Talk"].widget().toPlainText()
    story = window.main_window.toPlainText()
    assert "Kailisa" in talk and "over here" in talk
    assert story.count("Kailisa") == 1 and story.count("over here") == 1


def test_a_docks_right_click_menu_clears_that_dock_alone(window):
    # The operator, 2026-10-04 (#452): a Clear for the Thoughts window.
    from PyQt6.QtCore import QPoint

    window.dispatch_game_text("A troll lumbers in.\n", "", "")
    window.dispatch_game_text("[LNet] Sable: hi\n", "thoughts", "")
    thoughts = window.stream_windows["thoughts"]
    menu = thoughts.context_menu(QPoint(0, 0))
    labels = [action.text() for action in menu.actions() if action.text()]
    assert labels[-1] == "Clear"
    assert any("Copy" in label for label in labels)  # the standard menu stays
    next(action for action in menu.actions() if action.text() == "Clear").trigger()
    menu.deleteLater()
    assert thoughts.toPlainText() == ""
    assert "troll" in window.main_window.toPlainText()  # the story untouched


def test_an_undocked_streams_text_still_reaches_the_story(window):
    window.dispatch_game_text("a backpack\n", "inv", "")
    assert "a backpack" in window.main_window.toPlainText()


def test_a_command_link_renders_as_an_anchor_and_a_click_sends_it(window, connection):
    window.dispatch_game_text("look at the sign", "", "link:look sign")
    cursor = window.main_window.document().find("look at the sign")
    assert cursor.charFormat().anchorHref() == "look sign"
    window._follow_link("look sign")
    assert connection.written == [b"look sign\n"]
    assert "> look sign" in window.main_window.toPlainText()


def test_without_a_connection_a_send_only_reports_it(window):
    window.write("look")
    assert window.status_bar.currentMessage() == "Not connected yet"


def test_the_character_frame_names_the_title_bar(window):
    window.dispatch_game_text("Sable", "character", "")
    assert window.windowTitle() == "Revenant — Sable"


def test_the_room_frame_reaches_the_map_dock(window):
    window.dispatch_game_text("21101\t[Barana's Shipyard, Lumber Storage]", "room", "")
    assert window.map_view._pending == (21101, "[Barana's Shipyard, Lumber Storage]")


def test_every_dock_has_a_view_menu_toggle(window):
    view_menu = next(a for a in window.menuBar().actions() if a.text() == "View")
    titles = {a.text() for a in view_menu.menu().actions()}
    assert {"Compass", "Clocks", "Map", "Experience", "Thoughts"} <= titles


def test_a_hands_frame_shows_what_each_hand_holds(window):
    strip = window.input_strip
    window.dispatch_game_text("oak-hafted handaxe\tsteel scimitar", "hands", "")
    assert strip.hands_label.text() == "L: oak-hafted handaxe  R: steel scimitar"
    window.dispatch_game_text("\tsteel scimitar", "hands", "")
    assert strip.hands_label.text() == "L: —  R: steel scimitar"
    assert "scimitar" not in window.main_window.toPlainText()  # never story text


def test_a_spells_frame_puts_the_prepared_spell_beside_the_hands(window):
    # #326: the Spells dock can be folded away; the bar under the command
    # line is where the eye already is. A cast clears it.
    strip = window.input_strip
    window.dispatch_game_text("prepared\tHeroic Strength\nGauge Flow\t12", "spells", "")
    assert strip.prepared_label.text() == "Prep: Heroic Strength"
    window.dispatch_game_text("Gauge Flow\t12\nHeroic Strength\t9", "spells", "")
    assert strip.prepared_label.text() == ""
    assert "Heroic Strength" not in window.main_window.toPlainText()
