"""Which frontend window a stream frame belongs to — decided without Qt.

A `<clearStream>` names exactly one stream, and only that stream's own
window may be wiped. Streams the frontend gives no window of its own —
`inv` and `experience`, which the game rewrites on every inventory
change, and the game's own `room` stream — have nothing to clear, so the
control is dropped. Falling back to the main window instead blanked the
Story pane on every GET/PUT/STOW (#109).

Text is different: an undocked stream's *content* does belong in the
main window. Only the clear control is stream-exclusive.

This table lives here, Qt-free, because `client/tests` cannot import
PyQt6 (headless CI) — the GUI reads it from this module.
"""

# stream id -> dock title. Several streams may share one dock (thoughts
# and chatter both land in Thoughts). The GUI draws "Spells" as a
# widget dock from the parser's spell state and drops the raw
# percWindow text (#175); the TUI still prints it under that title.
# GROUP's listing arrives as the `group` stream, cleared before every
# rewrite ("Members of your group:" ... "There are 2 members in your
# group.", captured 2026-09-22), and fell into the story until it had
# a dock.
STREAM_WINDOWS = {
    "thoughts": "Thoughts",
    "chatter": "Thoughts",
    "percWindow": "Spells",
    "logons": "Arrivals",
    "death": "Deaths",
    "exp": "Experience",
    "group": "Group",
    "attention": "Attention",  # ;sentinel's new and addressed lines (#276)
}


def window_title(stream):
    """The dock title this stream renders into, or None when it has no
    dock of its own and its text belongs in the main window."""
    return STREAM_WINDOWS.get(stream)


def clears_window(stream):
    """True when a "clear" control for this stream has a window to wipe.

    False means drop it: the frontend renders no window for that stream,
    and the main window is not a stand-in for one (#109).
    """
    return stream in STREAM_WINDOWS
