"""How a window remembers its layout per character (#74) — the manual.

Each character's window arrangement lives under its own settings keys;
the unscoped legacy pair is both the pre-#74 fallback and the seed for
characters that have never saved a layout (they inherit the most
recently closed window's arrangement, then diverge).
"""

from client import window_layout


def test_layout_keys_are_scoped_to_the_character():
    assert window_layout.layout_keys("Testchar") == (
        "layout/Testchar/geometry",
        "layout/Testchar/windowState",
    )


def test_no_character_falls_back_to_the_legacy_keys():
    assert window_layout.layout_keys(None) == ("geometry", "windowState")
    assert window_layout.layout_keys("") == ("geometry", "windowState")


def test_a_close_saves_both_the_character_and_the_fallback_layout():
    pairs = window_layout.save_pairs("Testchar", b"geo", b"docks")
    assert pairs == {
        "geometry": b"geo",
        "windowState": b"docks",
        "layout/Testchar/geometry": b"geo",
        "layout/Testchar/windowState": b"docks",
    }


def test_a_close_without_a_character_saves_only_the_legacy_pair():
    assert window_layout.save_pairs(None, b"geo", b"docks") == {
        "geometry": b"geo",
        "windowState": b"docks",
    }
