"""How the font settings become a font choice — these tests are the manual.

font_family "" and font_size 0 (the defaults) mean "platform default";
a named family and a size in 6–72 points are applied; garbage in the
file is ignored rather than turned into a surprise font.
"""

from client.settings import DEFAULTS
from client.textfont import MAX_SIZE, MIN_SIZE, font_choice


def test_defaults_keep_the_platform_font():
    assert font_choice(DEFAULTS) == (None, None)


def test_named_family_and_size_are_applied():
    assert font_choice({"font_family": "Consolas", "font_size": 14}) == (
        "Consolas",
        14,
    )


def test_family_whitespace_is_trimmed_and_blank_means_default():
    assert font_choice({"font_family": "  Georgia "})[0] == "Georgia"
    assert font_choice({"font_family": "   "})[0] is None


def test_size_bounds_are_six_to_seventy_two_points():
    assert font_choice({"font_size": MIN_SIZE})[1] == MIN_SIZE
    assert font_choice({"font_size": MAX_SIZE})[1] == MAX_SIZE
    assert font_choice({"font_size": MIN_SIZE - 1})[1] is None
    assert font_choice({"font_size": MAX_SIZE + 1})[1] is None


def test_unusable_values_fall_back_to_default():
    assert font_choice({"font_family": 12, "font_size": "big"}) == (None, None)
    assert font_choice({"font_size": True})[1] is None
    assert font_choice({"font_size": 12.5})[1] is None
    assert font_choice({"font_size": 12.0})[1] == 12  # JSON may round-trip a float


def test_settings_missing_the_keys_entirely():
    assert font_choice({}) == (None, None)


# --- per-view overrides (#132) --------------------------------------------

from client.textfont import TEXT_VIEWS, clean_overrides, view_font  # noqa: E402

BASE = {"font_family": "Georgia", "font_size": 12}


def test_an_override_beats_the_default_for_its_view_only():
    settings = BASE | {"dock_fonts": {"Thoughts": {"size": 8}}}
    assert view_font(settings, "Thoughts") == ("Georgia", 8)
    assert view_font(settings, "Main") == ("Georgia", 12)


def test_an_override_names_only_what_it_changes():
    settings = BASE | {"dock_fonts": {"Experience": {"family": "Consolas"}}}
    assert view_font(settings, "Experience") == ("Consolas", 12)


def test_a_missing_override_leaves_the_default():
    assert view_font(BASE, "Deaths") == ("Georgia", 12)
    assert view_font(BASE | {"dock_fonts": {}}, "Deaths") == ("Georgia", 12)


def test_a_stale_or_unusable_override_is_ignored():
    settings = BASE | {
        "dock_fonts": {
            "Gone Dock": {"size": 30},
            "Spells": {"family": "  ", "size": 500},
            "Arrivals": "not a mapping",
        }
    }
    assert view_font(settings, "Spells") == ("Georgia", 12)
    assert view_font(settings, "Arrivals") == ("Georgia", 12)
    assert view_font(BASE | {"dock_fonts": "junk"}, "Main") == ("Georgia", 12)


def test_defaults_plus_override_keep_platform_none_where_nothing_is_named():
    assert view_font({"dock_fonts": {"Thoughts": {"size": 9}}}, "Thoughts") == (None, 9)
    assert view_font({}, "Thoughts") == (None, None)


def test_clean_overrides_keeps_only_usable_entries_for_known_views():
    assert clean_overrides(
        {
            "Thoughts": {"size": 8, "family": ""},
            "Gone Dock": {"size": 9},
            "Spells": {"size": 0},
            "Main": {"family": "Georgia", "size": 11.0},
        }
    ) == {"Thoughts": {"size": 8}, "Main": {"family": "Georgia", "size": 11}}
    assert clean_overrides(None) == {}


def test_the_views_are_the_story_input_and_the_stream_docks():
    from client.streamroute import STREAM_WINDOWS

    assert set(STREAM_WINDOWS.values()) <= set(TEXT_VIEWS)
    assert TEXT_VIEWS[:2] == ("Main", "Input")
