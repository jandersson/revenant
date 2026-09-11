"""The room-id annotation pairs a shown title with a resolved room in
either arrival order, once per room-name line — the manual."""

from client.ui.roomids import RoomIdTracker, room_id_suffix

GREEN = "[The Crossing, Town Green]"
STREET = "[The Crossing, Herald Street]"


def test_the_suffix_is_the_map_id_in_parentheses():
    assert room_id_suffix(1420) == " (1420)"


def test_title_first_then_frame_annotates_on_the_frame():
    tracker = RoomIdTracker()
    assert tracker.title_shown(GREEN + "\n") is None
    assert tracker.room_resolved(1, GREEN) == 1


def test_frame_first_then_title_annotates_on_the_title():
    # The <nav> uid can land a line before the room name.
    tracker = RoomIdTracker()
    assert tracker.room_resolved(1, GREEN) is None
    assert tracker.title_shown(GREEN) == 1


def test_each_room_name_line_is_annotated_once():
    tracker = RoomIdTracker()
    tracker.title_shown(GREEN)
    assert tracker.room_resolved(1, GREEN) == 1
    assert tracker.room_resolved(1, GREEN) is None  # a repeated frame
    assert tracker.title_shown(GREEN) == 1  # LOOK again: a new line, same room


def test_an_off_map_room_annotates_nothing():
    tracker = RoomIdTracker()
    tracker.title_shown(GREEN)
    assert tracker.room_resolved(None, GREEN) is None
    tracker.room_resolved(None, STREET)
    assert tracker.title_shown(STREET) is None


def test_a_frame_for_another_title_leaves_the_shown_line_alone():
    # A stale frame must not stamp the wrong id on a fresh title.
    tracker = RoomIdTracker()
    tracker.title_shown(STREET)
    assert tracker.room_resolved(1, GREEN) is None
    assert tracker.room_resolved(2, STREET) == 2


def test_blank_titles_are_ignored():
    tracker = RoomIdTracker()
    assert tracker.title_shown("   \n") is None
    assert tracker.room_resolved(1, GREEN) is None
