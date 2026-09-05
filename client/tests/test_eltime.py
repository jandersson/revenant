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

# Captured 2026-09-03 21:20 local, a Moon Mage's OBSERVE MOONS — the
# first capture holding a quarter moon. DR words the half-lit phases as
# ordinals ("third quarter"), never as "half", and states no wax/wan
# direction alongside them: the ordinal is the direction (#110).
OBSERVE_TEXT_3 = """Katamba is a waxing crescent moon and is not visible.  Although you cannot see it, you can sense it should rise in about 5 anlaen.
You are certain that Katamba is thirty-two degrees below the western horizon.
Xibar is a waxing gibbous moon and is not visible.  Although you cannot see it, you can sense it should rise in about 2 anlaen.
You are certain that Xibar is eighty degrees below the eastern horizon.
Yavash is a third quarter moon soaring high near the zenith.
You're certain that Yavash is seventy-six degrees above the eastern horizon.
"""
OBSERVE_UNIX_3 = 1_788_463_232


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
        "phase": "dusk",
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


def test_parse_observe_output_reads_all_three_moons_with_a_quarter():
    # The regression (#110): "third quarter" used to be dropped, so a
    # calibration silently anchored two moons instead of three.
    assert eltime.parse_observe_output(OBSERVE_TEXT_3) == {
        "katamba": 1,
        "xibar": 3,
        "yavash": 6,
    }


def test_parse_observe_reads_the_quarter_ordinals_without_a_direction():
    # The ordinal names the direction; the sentence states no wax/wan,
    # and must not need to.
    assert eltime.parse_observe_output("Yavash is a third quarter moon.") == {
        "yavash": 6
    }
    assert eltime.parse_observe_output("Yavash is a last quarter moon.") == {
        "yavash": 6
    }
    assert eltime.parse_observe_output("Xibar is a first quarter moon.") == {"xibar": 2}


def test_the_third_capture_matches_what_the_model_predicts():
    # Every moon the capture describes, against the uncalibrated
    # defaults: the observation agreeing with the model is the reason
    # to trust DEFAULT_MOON_EPOCHS. "third quarter" is index 6, which
    # PHASES names "last quarter" — the same phase, the other name.
    for moon, index in eltime.parse_observe_output(OBSERVE_TEXT_3).items():
        assert eltime.moon_phase(moon, OBSERVE_UNIX_3) == index
    assert eltime.PHASES[6] == "last quarter"


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


# Captured 2026-08-23, Elanthian evening — the #64 Xibar hunt's prize:
# a phase wording with no shape word at all. The old classifier
# silently skipped both moons ("no moons visible to sync") while
# staring at them.
OBSERVE_TEXT_WANING = """You scan the heavens for the three moons:
Katamba is nowhere to be seen.
The blue moon Xibar, beginning to wane, travels slowly through the sky.
The red moon Yavash, beginning to wane, travels slowly through the sky.
"""


def test_beginning_to_wane_classifies_as_waning_gibbous():
    phases = eltime.parse_observe_output(OBSERVE_TEXT_WANING)
    assert phases == {"xibar": 5, "yavash": 5}


def test_beginning_to_wax_is_the_anticipated_symmetric():
    text = OBSERVE_TEXT_WANING.replace("beginning to wane", "beginning to wax")
    assert eltime.parse_observe_output(text) == {"xibar": 1, "yavash": 1}


OBSERVE_UNIX_WANING = 1_787_510_358  # server clock at the capture


def test_default_moon_epochs_match_the_live_synced_anchors():
    # The 2026-08-23 observation anchored Xibar for the first time and
    # refreshed Yavash; the baked defaults are exactly what ;clock
    # stored live that evening (#64).
    assert eltime.DEFAULT_MOON_EPOCHS["xibar"] == OBSERVE_UNIX_WANING - round(
        5 / 8 * eltime.MOON_SYNODIC["xibar"]
    )
    assert eltime.DEFAULT_MOON_EPOCHS["xibar"] == 1_787_160_858
    assert eltime.DEFAULT_MOON_EPOCHS["yavash"] == 1_786_964_688
    # A fresh install shows all three moons, no "?" rows left.
    for moon in eltime.MOON_NAMES:
        assert eltime.moon_phase(moon, OBSERVE_UNIX_WANING) is not None
    assert eltime.moon_phase("xibar", OBSERVE_UNIX_WANING) == 5


# --- TIME's day-phase word cross-checks the computed hour (#103) ---

# Every phase word captured so far, at the Elanthian hour it was captured
# (2026-08-22 and 2026-09-03 sessions, offset-calibrated); the bands in
# DAY_PHASES were drawn from these and widened by an hour each side.
CAPTURED_PHASES = [
    ("dawn", 6.3),
    ("early morning", 7.0),
    ("early morning", 8.6),
    ("mid-morning", 9.0),
    ("mid-morning", 10.6),
    ("late morning", 11.0),
    ("late morning", 12.6),
    ("midday", 13.0),
    ("midday", 14.3),
    ("early afternoon", 14.6),
    ("early afternoon", 16.3),
    ("mid-afternoon", 16.6),
    ("mid-afternoon", 18.3),
    ("late afternoon", 18.6),
    ("dusk", 18.9),
    ("dusk", 20.3),
    ("sunset", 20.6),
    ("sunset", 21.3),
    ("early evening", 21.6),
    ("late evening", 0.3),
    ("night", 1.0),
]


def test_parse_time_output_reads_the_day_phase_word():
    assert eltime.parse_time_output(TIME_TEXT)["phase"] == "dusk"


def test_every_captured_phase_agrees_with_its_hour():
    for phase, hour in CAPTURED_PHASES:
        assert eltime.phase_agrees(phase, hour) is True, (phase, hour)


def test_a_two_game_hour_drift_is_caught():
    # The #101 bug moved the clock ~29 real minutes, two game hours.
    assert eltime.phase_agrees("midday", 10.5) is False
    assert eltime.phase_agrees("dusk", 23.0) is False
    assert eltime.phase_agrees("dawn", 9.0) is False


def test_unknown_or_missing_phase_words_never_block():
    assert eltime.phase_agrees("the witching hour", 3.0) is None
    assert eltime.phase_agrees(None, 3.0) is None
    assert eltime.phase_agrees("", 3.0) is None


def test_the_bands_that_wrap_midnight():
    assert eltime.phase_agrees("night", 23.5) is True
    assert eltime.phase_agrees("night", 5.9) is True
    assert eltime.phase_agrees("night", 12.0) is False
    assert eltime.phase_agrees("late evening", 1.5) is True


# --- boundary events (#104) and orbits (#105) ------------------------------

from client.eltime import (  # noqa: E402
    DEFAULT_MOON_RISES,
    MOON_ORBIT,
    describe_moon_position,
    drift_seconds,
    moon_event,
    moon_position,
    rise_from_set,
    sun_boundary,
)

# Captured sun lines and the calibrated hour each arrived at
# (2026-08-19 .. 2026-09-04); the boundary hours are their means.
CAPTURED_SUN = [
    ("The sun rises in a crisp, clear blue sky, heralding another fine day.", 4.92),
    ("The sun rises in a crisp, clear blue sky, heralding another fine day.", 4.93),
    (
        "The sun climbs higher into the clear sky, bringing with it a pure, clear light.",
        8.87,
    ),
    (
        "Thin streamers of cloud float in a mostly clear sky as the sun rises high above them.",
        8.85,
    ),
    (
        "The sun nears the far horizon as the clear blue sky deepens into a rich indigo.",
        18.78,
    ),
    (
        "Long streamers of clouds turn shades of salmon and umber as the sun nears the horizon.",
        18.80,
    ),
    (
        "The sun sinks below the horizon, turning the clear sky a thousand shades of blue.",
        20.45,
    ),
    (
        "The sun sinks below the horizon, turning the clear sky a thousand shades of blue.",
        20.52,
    ),
]


def test_every_captured_sun_line_is_a_boundary_within_two_minutes():
    for line, hour in CAPTURED_SUN:
        boundary = sun_boundary(line)
        assert boundary is not None, line
        assert abs(drift_seconds(hour, boundary[1])) <= 120, (line, hour)


def test_room_prose_mentioning_the_sun_is_no_boundary():
    assert sun_boundary("The heat from the sun grows rather intense.") is None
    assert sun_boundary("Blackened rocks stretch to the horizon.") is None
    assert sun_boundary("") is None


def test_fractional_hour_matches_the_minute_clock_with_seconds_kept():
    from client.eltime import fractional_hour

    now = 1788554905
    et = eltime.elanthian_now(now, 0)
    assert int(fractional_hour(now, 0)) == et.hour
    assert abs(fractional_hour(now, 0) - (et.hour + et.minute / 60)) < 1 / 60
    assert fractional_hour(now + 900, 0) - fractional_hour(now, 0) in (1.0, -23.0)


def test_drift_is_signed_in_real_seconds_and_wraps_midnight():
    assert drift_seconds(5.0, 4.92) == 72  # computed clock 0.08h fast: 72s
    assert drift_seconds(4.80, 4.92) == -108
    assert drift_seconds(0.1, 23.9) == 180
    assert drift_seconds(23.9, 0.1) == -180


def test_moon_rise_and_set_lines_are_recognized():
    assert moon_event("Katamba slowly rises above the horizon.") == ("katamba", "rise")
    assert moon_event("Xibar sets, slowly dropping below the horizon.") == (
        "xibar",
        "set",
    )
    assert moon_event("Yavash slowly rises above the horizon.") == ("yavash", "rise")
    assert moon_event("The moon Xibar looks lovely tonight.") is None


def test_the_wiki_orbits_agree_with_the_captured_events():
    # Katamba rose at 1788556276 and again at 1788577396 (2026-09-03/04):
    # one orbit, 21120s against the wiki's 21090s — under a minute out.
    assert abs((1788577396 - 1788556276) - MOON_ORBIT["katamba"]["period"]) < 60
    # Katamba set at 1788545836 and rose at 1788556276: the time below
    # the horizon, against period - up.
    below = MOON_ORBIT["katamba"]["period"] - MOON_ORBIT["katamba"]["up"]
    assert abs((1788556276 - 1788545836) - below) <= 60
    # Yavash rose at 1787402244 and set at 1787412924 (2026-08-20): up.
    assert abs((1787412924 - 1787402244) - MOON_ORBIT["yavash"]["up"]) < 60
    # Xibar set on 2026-08-19 (1787269164) and rose on 2026-09-03
    # (1788551296): 61 orbits plus the time below the horizon.
    orbit = MOON_ORBIT["xibar"]
    predicted = 61 * orbit["period"] + (orbit["period"] - orbit["up"])
    assert abs((1788551296 - 1787269164) - predicted) < 120


def test_moon_position_follows_the_anchor_through_the_orbit():
    rise = DEFAULT_MOON_RISES["katamba"]
    up = MOON_ORBIT["katamba"]["up"]
    period = MOON_ORBIT["katamba"]["period"]
    assert moon_position("katamba", rise + 60, rise) == (True, up - 60)
    assert moon_position("katamba", rise + up + 60, rise) == (False, period - up - 60)
    assert moon_position("katamba", rise + period + 60, rise) == (True, up - 60)
    assert moon_position("katamba", rise, None) is not None  # the default anchor
    assert moon_position("xibar", rise, rise_epoch=None) is not None


def test_a_set_line_implies_the_rise_before_it():
    assert rise_from_set("xibar", 1000000) == 1000000 - MOON_ORBIT["xibar"]["up"]


def test_the_position_reads_as_a_sentence():
    rise = 1_000_000
    assert describe_moon_position("xibar", rise + 60, rise) == "up, sets in 2h54m"
    down_at = rise + MOON_ORBIT["xibar"]["up"] + 60
    assert describe_moon_position("xibar", down_at, rise) == "down, rises in 2h52m"
    assert describe_moon_position("xibar", rise, rise_epoch=None) != "no rise seen yet"
