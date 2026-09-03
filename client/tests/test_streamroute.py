"""How a stream frame picks its window, and which streams a clear may wipe.

The rule these pin down (#109): a `<clearStream>` names one stream, and
only that stream's own dock may be cleared. A stream the frontend gives
no dock — `inv`, which the game rewrites on every GET/PUT/STOW — must not
fall back to the main window, or handling any item erases the story.
"""

import pytest

from client.streamroute import STREAM_WINDOWS, clears_window, window_title


class TestWindowTitle:
    """Where a stream's text is rendered."""

    @pytest.mark.parametrize(
        "stream, title",
        [
            ("thoughts", "Thoughts"),
            ("chatter", "Thoughts"),  # both LNet streams share one dock
            ("percWindow", "Spells"),
            ("logons", "Arrivals"),
            ("death", "Deaths"),
            ("exp", "Experience"),
        ],
    )
    def test_docked_streams_name_their_dock(self, stream, title):
        assert window_title(stream) == title

    @pytest.mark.parametrize("stream", ["inv", "experience", "room", "main", ""])
    def test_undocked_streams_have_no_dock(self, stream):
        # None means "no dock of its own" — the caller puts the text in
        # the main window, which is right for text.
        assert window_title(stream) is None


class TestClearsWindow:
    """Which streams a clear control may act on."""

    @pytest.mark.parametrize("stream", sorted(STREAM_WINDOWS))
    def test_a_docked_stream_clears_its_own_dock(self, stream):
        assert clears_window(stream) is True

    def test_the_engines_own_exp_clear_still_works(self):
        # core.py emits ("", "exp", "clear") to wipe the Experience dock
        # before rewriting it; that must keep working.
        assert clears_window("exp") is True

    @pytest.mark.parametrize(
        "stream",
        [
            "inv",  # <clearStream id='inv'/> on every GET/PUT/STOW
            "experience",  # the game's own experience window
            "room",  # collides with the engine's synthetic room frame
        ],
    )
    def test_an_undocked_stream_clears_nothing(self, stream):
        # The regression: these used to resolve to the main window and
        # blank the story pane.
        assert clears_window(stream) is False

    def test_the_main_window_is_never_a_clear_target(self):
        # No stream id may be answered by wiping the main window.
        assert clears_window("main") is False
        assert clears_window("") is False
