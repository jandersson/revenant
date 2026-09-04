"""How a window remembers its layout per character (#74) — the manual.

Each character's window arrangement lives under its own settings keys;
the unscoped legacy pair is both the pre-#74 fallback and the seed for
characters that have never saved a layout (they inherit the most
recently closed window's arrangement, then diverge).
"""

from client import window_layout


def test_layout_keys_are_scoped_to_the_character():
    assert window_layout.layout_keys("Lanival") == (
        "layout/Lanival/geometry",
        "layout/Lanival/windowState",
    )


def test_no_character_falls_back_to_the_legacy_keys():
    assert window_layout.layout_keys(None) == ("geometry", "windowState")
    assert window_layout.layout_keys("") == ("geometry", "windowState")


def test_a_close_saves_both_the_character_and_the_fallback_layout():
    pairs = window_layout.save_pairs("Lanival", b"geo", b"docks")
    assert pairs == {
        "geometry": b"geo",
        "windowState": b"docks",
        "layout/Lanival/geometry": b"geo",
        "layout/Lanival/windowState": b"docks",
    }


def test_a_close_without_a_character_saves_only_the_legacy_pair():
    assert window_layout.save_pairs(None, b"geo", b"docks") == {
        "geometry": b"geo",
        "windowState": b"docks",
    }


class FakeWindow:
    """A QMainWindow's layout surface, recording the order of calls."""

    def __init__(self, visible):
        self.visible = visible
        self.calls = []

    def isVisible(self):
        return self.visible

    def hide(self):
        self.visible = False
        self.calls.append("hide")

    def show(self):
        self.visible = True
        self.calls.append("show")

    def restoreGeometry(self, geometry):
        self.calls.append(("restoreGeometry", geometry))

    def restoreState(self, state):
        self.calls.append(("restoreState", state))


def test_a_shown_window_is_hidden_while_its_layout_lands():
    # Captured 2026-09-04 (#124): dock state restored onto the shown
    # window aborted the process at the next child setVisible.
    window = FakeWindow(visible=True)
    assert window_layout.apply(window, b"geo", b"docks") is True
    assert window.calls == [
        "hide",
        ("restoreGeometry", b"geo"),
        ("restoreState", b"docks"),
        "show",
    ]
    assert window.visible is True


def test_a_hidden_window_is_not_shown_by_the_restore():
    window = FakeWindow(visible=False)
    window_layout.apply(window, b"geo", b"docks")
    assert window.calls == [("restoreGeometry", b"geo"), ("restoreState", b"docks")]
    assert window.visible is False


def test_a_missing_half_of_the_layout_is_skipped():
    window = FakeWindow(visible=True)
    window_layout.apply(window, None, b"docks")
    assert window.calls == ["hide", ("restoreState", b"docks"), "show"]


def test_nothing_saved_means_the_window_is_left_alone():
    window = FakeWindow(visible=True)
    assert window_layout.apply(window, None, None) is False
    assert window.calls == []


def test_startup_restores_the_known_characters_own_layout():
    # Captured 2026-09-04 (#140): one saved state aborted inside Qt when
    # restored onto a shown window, and restored fine before the first
    # show — so a character known up front gets its layout first.
    saved = {
        "geometry": b"legacy-geo",
        "windowState": b"legacy-docks",
        "layout/Lanival/geometry": b"geo",
        "layout/Lanival/windowState": b"docks",
    }
    assert window_layout.startup_layout(saved.get, "Lanival") == (
        b"geo",
        b"docks",
        True,
    )


def test_startup_falls_back_to_the_legacy_pair_for_a_new_character():
    saved = {"geometry": b"legacy-geo", "windowState": b"legacy-docks"}
    assert window_layout.startup_layout(saved.get, "Newbie") == (
        b"legacy-geo",
        b"legacy-docks",
        False,
    )


def test_startup_with_no_character_uses_the_legacy_pair():
    saved = {"geometry": b"legacy-geo", "windowState": b"legacy-docks"}
    assert window_layout.startup_layout(saved.get, None) == (
        b"legacy-geo",
        b"legacy-docks",
        False,
    )


def test_startup_with_half_a_character_layout_still_counts_as_scoped():
    saved = {"windowState": b"legacy-docks", "layout/Lanival/windowState": b"docks"}
    assert window_layout.startup_layout(saved.get, "Lanival") == (None, b"docks", True)
