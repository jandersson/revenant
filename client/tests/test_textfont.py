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
