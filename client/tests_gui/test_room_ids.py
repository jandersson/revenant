"""The map room id lands after the room title in the story, in either
arrival order, only while Settings ask for it."""

from client.game.mapdb import MapDB

GREEN = "[The Crossing, Town Green]"
STREET = "[The Crossing, Herald Street]"
MAP = MapDB(
    [
        {"id": 1420, "uid": [21], "title": [GREEN], "tags": [], "wayto": {}},
        {"id": 1421, "uid": [22], "title": [STREET], "tags": [], "wayto": {}},
    ]
)


def load_map(window):
    # The loader thread's delivery, through the same signal: the dock
    # takes the database, then the window fills a waiting title in.
    window.map_ready.emit(MAP, set())


def story(window):
    return window.main_window.toPlainText()


def test_title_then_room_frame_gets_the_map_id(window):
    load_map(window)
    window.dispatch_game_text(GREEN + "\n", "", "roomName")
    window.dispatch_game_text("Grass everywhere.\n", "", "")
    window.dispatch_game_text(f"21\t{GREEN}", "room", "")
    assert f"{GREEN} (1420)\nGrass everywhere." in story(window)


def test_room_frame_then_title_gets_the_map_id(window):
    # The <nav> uid can land a line before the room name.
    load_map(window)
    window.dispatch_game_text(f"22\t{STREET}", "room", "")
    window.dispatch_game_text(STREET + "\n", "", "roomName")
    assert f"{STREET} (1421)\n" in story(window)


def test_the_id_is_dim_not_amber(window):
    load_map(window)
    window.dispatch_game_text(GREEN + "\n", "", "roomName")
    window.dispatch_game_text(f"21\t{GREEN}", "room", "")
    cursor = window.main_window.document().find("(1420)")
    assert cursor.charFormat().foreground().color().name() == "#8a8a96"


def test_an_off_map_room_and_a_missing_database_add_nothing(window):
    window.dispatch_game_text(GREEN + "\n", "", "roomName")
    window.dispatch_game_text(f"21\t{GREEN}", "room", "")
    assert "(" not in story(window)  # no database yet
    load_map(window)  # the database arriving fills the waiting title in
    assert f"{GREEN} (1420)" in story(window)
    window.dispatch_game_text("[Nowhere]\n", "", "roomName")
    window.dispatch_game_text("99\t[Nowhere]", "room", "")
    assert "[Nowhere]\n" in story(window)
    assert "(99)" not in story(window)


def test_the_setting_turns_it_off(window):
    load_map(window)
    window._show_room_ids = False
    window.dispatch_game_text(GREEN + "\n", "", "roomName")
    window.dispatch_game_text(f"21\t{GREEN}", "room", "")
    assert "(1420)" not in story(window)
