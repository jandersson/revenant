"""Which keystrokes on a read-only game view belong in the input line —
these tests are the manual (#150).

A click on the story window without selecting text focuses the input
line; a printable key typed onto a view is forwarded there. Control
chords (Ctrl+C copies the view's selection) and textless keys (arrows,
Page Up/Down scroll the view) stay with the view.
"""

from client.inputfocus import click_focuses_input, forwardable


def test_printable_keys_typed_onto_a_view_go_to_the_input_line():
    assert forwardable("l") is True
    assert forwardable(" ") is True
    assert forwardable(";") is True


def test_control_chords_stay_with_the_view():
    assert forwardable("\x03", control_held=True) is False  # Ctrl+C: copy
    assert forwardable("c", control_held=True) is False


def test_textless_and_control_characters_keep_scrolling_the_view():
    assert forwardable("") is False  # arrows, Page Up/Down, Home, End
    assert forwardable("\x1b") is False  # Escape
    assert forwardable("\r") is False  # Enter on a view sends nothing


def test_a_plain_click_focuses_the_input_but_a_text_selection_does_not():
    assert click_focuses_input(has_selection=False) is True
    assert click_focuses_input(has_selection=True) is False
