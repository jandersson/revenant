"""Typing anywhere in the window goes to the input line — the rule, Qt-free.

The game text views are read-only, and a click on one used to take
the keyboard focus with it: the next keystrokes went to a view that
discards them, until the user clicked the input line (#150). The GUI
now hands focus to the input line when a view is clicked without
selecting text, and forwards a printable keystroke that lands on a
view to the input line so the first character is not lost. This
module decides which keystrokes qualify; the GUI's event filter
applies it.
"""


def forwardable(text, control_held=False):
    """Whether a keystroke that landed on a read-only view belongs in the
    input line: printable text without a control chord. Ctrl+C on a view
    copies its selection and stays there; arrows, Page Up/Down and the
    like have no text and keep scrolling the view."""
    if control_held or not text:
        return False
    return text.isprintable()


def click_focuses_input(has_selection):
    """A click that ends without a selection is a "type here" gesture;
    a drag that selected text is a copy in progress and keeps focus."""
    return not has_selection
