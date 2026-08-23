"""How the Elanthian clock computes, parses, and calibrates — the manual.

Fixtures are captured game traffic (2026-08-22, no identity in them):
a TIME answer and an OBSERVE MOONS answer. The formula tests assert
that the computed calendar reproduces the captures — the
fixtures-pin-assumptions rule for calendar lore.
"""

from datetime import datetime, timezone

from client import eltime

# Captured 2026-08-22 12:21:56 UTC.
TIME_TEXT = """It has been 457 years, 174 days since the Victory of Lanival the Redeemer.
It is the 5th month of Uthmor the Giant in the year of the Golden Panther.
It is currently summer and it is dusk.
You're fairly certain it's past the Anlas of Meraud's Cloak.
"""
TIME_UNIX = 1_787_401_316

# Captured 2026-08-22 12:29:37 UTC, outdoors in the Crossing.
OBSERVE_TEXT = """You scan the heavens for the three moons:
The black moon Katamba has waned to a narrow crescent of light.
It is quite near and glowing rather insistently.
Xibar is nowhere to be seen.
Yavash is nowhere to be seen.
Roundtime: 10 sec.
"""
OBSERVE_UNIX = 1_787_401_777

# Captured 2026-08-22 12:42:26 UTC — Yavash had just risen, full.
OBSERVE_TEXT_2 = """Yavash slowly rises above the horizon.
You scan the heavens for the three moons:
The black moon Katamba has waned to a narrow crescent of light.
Xibar is nowhere to be seen.
The moon Yavash forms a perfect circle in the heavens.
"""
OBSERVE_UNIX_2 = 1_787_402_546


def test_the_capture_instant_is_what_the_comment_says():
    stamp = datetime(2026, 8, 22, 12, 21, 56, tzinfo=timezone.utc)
    assert int(stamp.timestamp()) == TIME_UNIX


def test_parse_time_output_reads_the_captured_answer():
    parsed = eltime.parse_time_output(TIME_TEXT)
    assert parsed == {
        "years": 457,
        "days": 174,
        "month": 5,
        "month_name": "Uthmor the Giant",
        "year_name": "Golden Panther",
        "anlas": 10,  # Meraud's Cloak
        "anlas_roisaen": None,  # "past the Anlas of X" states no count
    }


def test_parse_time_output_rejects_other_text():
    assert eltime.parse_time_output("Obvious paths: north.") is None


# Captured 2026-08-23, Elanthian mid-afternoon: the phrasing with a
# roisaen count. The live bug (#101): the old parser read this as
# being inside Meraud's Cloak and calibrated the dock ~29 real
# minutes fast; the count actually says the anlas has NOT started.
TIME_TEXT_BEFORE = """It has been 457 years, 179 days since the Victory of Lanival the Redeemer.
It is the 5th month of Uthmor the Giant in the year of the Golden Panther.
It is currently summer and it is mid-afternoon.
You're fairly certain it's 14 roisaen before the Anlas of Meraud's Cloak.
"""


def test_a_roisaen_count_before_the_anlas_is_parsed_signed():
    parsed = eltime.parse_time_output(TIME_TEXT_BEFORE)
    assert parsed["anlas"] == 10  # the NAMED anlas, not yet begun
    assert parsed["anlas_roisaen"] == -14


def test_calibrate_uses_the_roisaen_count_to_the_minute():
    # 14 roisaen before Meraud's Cloak (starts 16200s into the day):
    # 16200 - 14*60 = 15360s — Elanthian 17:04, mid-afternoon, exactly
    # as the capture says. Mid-anlas anchoring would have said 17100s.
    parsed = eltime.parse_time_output(TIME_TEXT_BEFORE)
    captured_at = 1_787_500_000  # any instant; the target is absolute
    target = 457 * eltime.YEAR_SECONDS + 179 * eltime.DAY_SECONDS + 15_360
    assert eltime.calibrate(parsed, captured_at) == target - (
        captured_at - eltime.VICTORY_EPOCH
    )
    at_target = eltime.elanthian_now(captured_at, eltime.calibrate(parsed, captured_at))
    assert (at_target.hour, at_target.minute) == (17, 4)
    assert at_target.anlas_name == "Tamsine's Toil"  # the 9th, still


def test_a_roisaen_count_past_the_anlas_is_positive():
    # The symmetric wording, anticipated but not yet captured (#101).
    text = TIME_TEXT_BEFORE.replace(
        "14 roisaen before the Anlas", "3 roisaen past the Anlas"
    )
    parsed = eltime.parse_time_output(text)
    assert parsed["anlas_roisaen"] == 3


def test_before_the_first_anlas_rolls_into_the_previous_day():
    # Pure arithmetic on our side: 5 roisaen before Anduwen (in_day
    # -300) lands at 23:40 of the previous day.
    text = TIME_TEXT_BEFORE.replace(
        "14 roisaen before the Anlas of Meraud's Cloak",
        "5 roisaen before the Anlas of Anduwen",
    )
    parsed = eltime.parse_time_output(text)
    captured_at = 1_787_500_000
    rolled = eltime.elanthian_now(captured_at, eltime.calibrate(parsed, captured_at))
    assert (rolled.hour, rolled.minute) == (23, 40)


def test_formula_agrees_with_the_captured_time():
    et = eltime.elanthian_now(TIME_UNIX)
    assert et.year == 457
    assert et.year_name == "Golden Panther"
    assert et.month == 5
    assert et.month_name == "Uthmor the Giant"
    assert et.day == 15  # 174 elapsed days -> the 175th, day 15 of the month
    assert et.anlas == 10
    assert et.anlas_name == "Meraud's Cloak"
    assert et.andu == 4
    assert et.andu_name == "Truffandu"


def test_year_names_follow_the_seven_year_cycle():
    # Anchors: TIME (457 = Golden Panther) and a character's INFO
    # ("in the year of the Emerald Dolphin, 341 years after the
    # victory of Lanival the Redeemer").
    assert eltime.YEAR_NAMES[457 % 7] == "Golden Panther"
    assert eltime.YEAR_NAMES[341 % 7] == "Emerald Dolphin"
    assert eltime.YEAR_NAMES[0] == "Silver Unicorn"


def test_the_epoch_starts_the_calendar():
    et = eltime.elanthian_now(eltime.VICTORY_EPOCH)
    assert (et.year, et.month, et.day) == (0, 1, 1)
    assert et.month_name == "Akroeg the Ram"
    assert (et.hour, et.minute) == (0, 0)
    assert et.anlas_name == "Anduwen"
    assert et.andu_name == "Kertandu"


def test_days_months_and_years_roll_over():
    last_moment = eltime.elanthian_now(eltime.VICTORY_EPOCH + eltime.DAY_SECONDS - 1)
    assert (last_moment.day, last_moment.anlas, last_moment.hour) == (1, 12, 23)
    next_day = eltime.elanthian_now(eltime.VICTORY_EPOCH + eltime.DAY_SECONDS)
    assert (next_day.day, next_day.anlas) == (2, 1)
    next_month = eltime.elanthian_now(
        eltime.VICTORY_EPOCH + eltime.MONTH_DAYS * eltime.DAY_SECONDS
    )
    assert (next_month.month, next_month.day) == (2, 1)
    next_year = eltime.elanthian_now(eltime.VICTORY_EPOCH + eltime.YEAR_SECONDS)
    assert (next_year.year, next_year.month, next_year.day) == (1, 1, 1)
    assert next_year.year_name == "Bronze Wyvern"


def test_offset_shifts_the_clock():
    plain = eltime.elanthian_now(eltime.VICTORY_EPOCH)
    shifted = eltime.elanthian_now(eltime.VICTORY_EPOCH, offset=eltime.ANLAS_SECONDS)
    assert plain.anlas == 1
    assert shifted.anlas == 2


def test_calibrate_is_zero_at_the_anchor_capture():
    parsed = eltime.parse_time_output(TIME_TEXT)
    assert eltime.calibrate(parsed, TIME_UNIX) == 0
    # Ten real minutes later the same answer means we run ten fast.
    assert eltime.calibrate(parsed, TIME_UNIX + 600) == -600


def test_calibrate_without_an_anlas_assumes_midday():
    parsed = eltime.parse_time_output(TIME_TEXT)
    parsed["anlas"] = None
    expected = (
        457 * eltime.YEAR_SECONDS + 174 * eltime.DAY_SECONDS + eltime.DAY_SECONDS // 2
    )
    assert eltime.calibrate(parsed, TIME_UNIX) == expected - (
        TIME_UNIX - eltime.VICTORY_EPOCH
    )


def test_describe_renders_the_dock_lines():
    time_line, date_line = eltime.describe(eltime.elanthian_now(TIME_UNIX))
    assert time_line == "19:00  Meraud's Cloak"
    assert date_line == "15 Uthmor the Giant 457 (Golden Panther)"


# --- the moons ---------------------------------------------------------


def test_parse_observe_output_from_the_capture():
    # Only Katamba was above the horizon; a narrowing crescent of
    # light is a waning crescent, the last of the eight phases.
    assert eltime.parse_observe_output(OBSERVE_TEXT) == {"katamba": 7}


def test_parse_observe_output_wiki_waxing_half():
    # Elanthipedia's OBSERVE example — a waxing half is the first
    # quarter.
    text = (
        "Waxing still, half of the blue moon Xibar looks down from"
        " above.  It is quite near and glowing rather insistently."
    )
    assert eltime.parse_observe_output(text) == {"xibar": 2}


def test_parse_observe_classifies_synthetic_directions():
    # Synthetic sentences exercising the keyword classifier, not
    # claims about server wording.
    assert eltime.parse_observe_output("Yavash is full tonight.") == {"yavash": 4}
    assert eltime.parse_observe_output("Xibar is a waxing gibbous orb.") == {"xibar": 3}
    assert eltime.parse_observe_output("Katamba wanes, gibbous still.") == {
        "katamba": 5
    }
    # No stated direction: no confident phase.
    assert eltime.parse_observe_output("A crescent Yavash hangs there.") == {}


def test_parse_observe_output_second_capture_reads_a_full_moon():
    # "forms a perfect circle" is the game's full-moon wording.
    assert eltime.parse_observe_output(OBSERVE_TEXT_2) == {
        "katamba": 7,
        "yavash": 4,
    }


def test_moon_phase_reproduces_the_capture_through_its_anchor():
    assert eltime.moon_phase("katamba", OBSERVE_UNIX) == 7
    assert eltime.moon_phase("katamba", eltime.DEFAULT_MOON_EPOCHS["katamba"]) == 0
    assert eltime.moon_phase("yavash", OBSERVE_UNIX_2) == 4


def test_moon_phase_without_an_anchor_is_unknown(monkeypatch):
    monkeypatch.setitem(eltime.DEFAULT_MOON_EPOCHS, "xibar", None)
    assert eltime.moon_phase("xibar", OBSERVE_UNIX) is None


def test_calibrate_moons_roundtrips():
    anchors = eltime.calibrate_moons({"yavash": 4}, OBSERVE_UNIX)
    assert eltime.moon_phase("yavash", OBSERVE_UNIX, anchors["yavash"]) == 4
    # Half a synodic cycle later the full moon has become new.
    later = OBSERVE_UNIX + eltime.MOON_SYNODIC["yavash"] // 2
    assert eltime.moon_phase("yavash", later, anchors["yavash"]) == 0


def test_earth_moon_matches_the_almanac():
    # New moon 2000-01-06 18:14 UTC anchors the cycle; the Sturgeon
    # Moon of 2026-08-28 04:18 UTC lands on "full".
    anchor = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    assert int(anchor.timestamp()) == eltime.EARTH_NEW_EPOCH
    sturgeon = datetime(2026, 8, 28, 4, 18, tzinfo=timezone.utc)
    assert eltime.PHASES[eltime.earth_moon_phase(sturgeon.timestamp())] == "full"
    assert eltime.earth_moon_phase(eltime.EARTH_NEW_EPOCH) == 0
