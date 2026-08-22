"""The Elanthian clock: game-world date, time and moons from real time.

Elanthia's calendar is a fixed function of real time — one game day is
six real hours — so the clocks dock computes it locally and never asks
the game. ``;clock`` (scripts/clock.py) is the ntpdate: it sends TIME,
compares the answer to this formula, and stores the correction in
settings (``eltime_offset_seconds``), plus moon-phase anchors from
OBSERVE MOONS (``eltime_moons``). The constants and their evidence are
recorded in docs/eltime.md.

Unit math (Elanthipedia "Time", validated against a captured TIME on
2026-08-22): 1 roisan = 1 real minute, 1 anlas = 30 real minutes, a day
is 12 anlaen (6 real hours), a month is 40 days (10 real days), a year
is 10 months (100 real days). Years are numbered from the Victory of
Lanival and named on a seven-year cycle; year % 7 indexes the cycle
(year 457 = Golden Panther per the capture, year 341 = Emerald Dolphin
per a character's INFO).

The three moons wax and wane on fixed mean cycles (eight phases each);
their phase anchors come from captured OBSERVE MOONS output, since
Elanthipedia documents the cycle lengths but no calendar alignment.
Earth's moon is here too, for the dock's optional for-fun row.
"""

import re
import time
from dataclasses import dataclass

ROISAN_SECONDS = 60  # 1 roisan = 1 real minute
ANLAS_SECONDS = 30 * ROISAN_SECONDS
DAY_SECONDS = 12 * ANLAS_SECONDS  # 6 real hours
MONTH_DAYS = 40
YEAR_DAYS = 400
YEAR_SECONDS = YEAR_DAYS * DAY_SECONDS  # 100 real days
GAME_HOUR_SECONDS = DAY_SECONDS // 24  # the day also divides into 24 hours
GAME_MINUTE_SECONDS = GAME_HOUR_SECONDS // 60

MONTHS = (
    "Akroeg the Ram",
    "Ka'len the Sea Drake",
    "Lirisa the Archer",
    "Shorka the Cobra",
    "Uthmor the Giant",
    "Arhat the Fire Lion",
    "Moliko the Balance",
    "Skullcleaver the Dwarven Axe",
    "Dolefaren the Brigantine",
    "Nissa the Maiden",
)

# The seven-year name cycle; YEAR_NAMES[year % 7].
YEAR_NAMES = (
    "Silver Unicorn",
    "Bronze Wyvern",
    "Golden Panther",
    "Amber Phoenix",
    "Iron Toad",
    "Emerald Dolphin",
    "Crystal Snow Hare",
)

# The twelve named anlaen of the day, midnight first.
ANLAEN = (
    "Anduwen",
    "Starwatch",
    "Asketi's Hunt",
    "Berengaria's Touch",
    "Hodierna's Blessing",
    "Peri'el's Watch",
    "Dergati's Bane",
    "Firulf's Flame",
    "Tamsine's Toil",
    "Meraud's Cloak",
    "Phelim's Vigil",
    "Revelfae",
)

# The ten four-day weeks of every month.
ANDAEN = (
    "Kertandu",
    "Hodandu",
    "Evandu",
    "Truffandu",
    "Havrandu",
    "Elandu",
    "Chandu",
    "Glythandu",
    "Faeandu",
    "Tamsandu",
)

# The epoch: the real instant of the Victory of Lanival, derived from a
# TIME captured 2026-08-22 12:21:56 UTC — "457 years, 174 days" into
# the Anlas of Meraud's Cloak (the 10th). Anchoring mid-anlas bounds
# the uncalibrated error at ±15 real minutes; ;clock's stored offset
# refines from there.
_CAPTURE_UNIX = 1_787_401_316
_CAPTURE_ELAPSED = (
    457 * YEAR_SECONDS + 174 * DAY_SECONDS + 9 * ANLAS_SECONDS + ANLAS_SECONDS // 2
)
VICTORY_EPOCH = _CAPTURE_UNIX - _CAPTURE_ELAPSED


@dataclass(frozen=True)
class ElanthianTime:
    """One Elanthian instant. Fields are 1-based where the game's own
    phrasing is ("the 5th month"); year counts whole years since the
    Victory of Lanival, exactly as TIME reports it."""

    year: int
    month: int  # 1..10
    day: int  # 1..40, day of the month
    hour: int  # 0..23
    minute: int  # 0..59
    anlas: int  # 1..12
    andu: int  # 1..10, week of the month

    @property
    def year_name(self):
        return YEAR_NAMES[self.year % len(YEAR_NAMES)]

    @property
    def month_name(self):
        return MONTHS[self.month - 1]

    @property
    def anlas_name(self):
        return ANLAEN[self.anlas - 1]

    @property
    def andu_name(self):
        return ANDAEN[self.andu - 1]


def elanthian_now(epoch_s=None, offset=0):
    """The Elanthian date and time at a real Unix instant (now if not
    given), shifted by the calibration offset from settings."""
    if epoch_s is None:
        epoch_s = time.time()
    elapsed = epoch_s + offset - VICTORY_EPOCH
    year, rest = divmod(elapsed, YEAR_SECONDS)
    day_of_year, in_day = divmod(rest, DAY_SECONDS)
    day_of_year = int(day_of_year)
    return ElanthianTime(
        year=int(year),
        month=day_of_year // MONTH_DAYS + 1,
        day=day_of_year % MONTH_DAYS + 1,
        hour=int(in_day // GAME_HOUR_SECONDS),
        minute=int(in_day % GAME_HOUR_SECONDS // GAME_MINUTE_SECONDS),
        anlas=int(in_day // ANLAS_SECONDS) + 1,
        andu=day_of_year % MONTH_DAYS // 4 + 1,
    )


def describe(et: ElanthianTime):
    """The clocks dock's two Elanthian lines: time, then date."""
    return (
        f"{et.hour:02d}:{et.minute:02d}  {et.anlas_name}",
        f"{et.day} {et.month_name} {et.year} ({et.year_name})",
    )


_TIME_ELAPSED = re.compile(
    r"It has been (\d+) years?, (\d+) days? since the Victory of Lanival"
)
_TIME_MONTH = re.compile(
    r"It is the (\d+)\w{2} month of ([A-Za-z'][A-Za-z' ]*?)"
    r" in the year of the ([A-Za-z'][A-Za-z' ]*?)\."
)
_TIME_ANLAS = re.compile(r"the Anlas of ([A-Za-z'][A-Za-z' ]*[A-Za-z])")


def parse_time_output(text):
    """The game's TIME answer as a dict, or None when it isn't one.

    The elapsed line carries the precision (whole days); the anlas line
    refines within the day. TIME never states hour or minute — the
    game's clock is deliberately fuzzy below the anlas.
    """
    elapsed = _TIME_ELAPSED.search(text)
    if not elapsed:
        return None
    month = _TIME_MONTH.search(text)
    anlas = _TIME_ANLAS.search(text)
    anlas_index = None
    if anlas and anlas.group(1) in ANLAEN:
        anlas_index = ANLAEN.index(anlas.group(1)) + 1
    return {
        "years": int(elapsed.group(1)),
        "days": int(elapsed.group(2)),
        "month": int(month.group(1)) if month else None,
        "month_name": month.group(2) if month else None,
        "year_name": month.group(3) if month else None,
        "anlas": anlas_index,
    }


def calibrate(parsed, captured_at):
    """The offset (seconds) that makes the formula agree with a parsed
    TIME captured at a real Unix instant — store it in settings as
    eltime_offset_seconds. Mid-anlas is assumed (±15 real minutes);
    without an anlas line, mid-day (±3 real hours)."""
    if parsed["anlas"] is not None:
        in_day = (parsed["anlas"] - 1) * ANLAS_SECONDS + ANLAS_SECONDS // 2
    else:
        in_day = DAY_SECONDS // 2
    target = parsed["years"] * YEAR_SECONDS + parsed["days"] * DAY_SECONDS + in_day
    return target - (captured_at - VICTORY_EPOCH)


# --- the moons ---------------------------------------------------------

# Mean new-moon-to-new-moon cycles in real seconds (Elanthipedia gives
# per-phase durations in roisaen; eight phases per cycle). The in-game
# orbits wobble slightly around these means, so anchors resync via
# ;clock rather than being eternal truths.
MOON_SYNODIC = {
    "xibar": 8 * 1165 * ROISAN_SECONDS,  # ≈ 6.5 real days
    "yavash": 873_072,  # 40.42 Elanthian days ≈ 10.1 real days
    "katamba": 8 * 1691 * ROISAN_SECONDS,  # ≈ 9.4 real days
}
MOON_NAMES = ("xibar", "yavash", "katamba")

PHASES = (
    "new",
    "waxing crescent",
    "first quarter",
    "waxing gibbous",
    "full",
    "waning gibbous",
    "last quarter",
    "waning crescent",
)
PHASE_EMOJI = (
    "\U0001f311",
    "\U0001f312",
    "\U0001f313",
    "\U0001f314",
    "\U0001f315",
    "\U0001f316",
    "\U0001f317",
    "\U0001f318",
)

# Real Unix instants of a new moon, from captured OBSERVE MOONS output
# (see docs/eltime.md). A capture pins the moon's current phase; the
# anchor places that phase's center at the capture instant. Moons not
# yet captured are None until a ;clock sync sees them above the
# horizon.
DEFAULT_MOON_EPOCHS = {
    # 2026-08-22 12:29:37 UTC: "The black moon Katamba has waned to a
    # narrow crescent of light." — waning crescent, phase 7 of 0..7.
    "katamba": 1_787_401_777 - round(7 / 8 * MOON_SYNODIC["katamba"]),
    "xibar": None,
    "yavash": None,
}


def _phase_index(elapsed, synodic):
    """0..7, with each phase's octant centered on its exact instant
    (full spans the half-cycle mark ± a sixteenth)."""
    fraction = (elapsed % synodic) / synodic
    return round(fraction * 8) % 8


def moon_phase(name, epoch_s=None, new_epoch=None):
    """The moon's phase index (0..7 into PHASES) at a real instant, or
    None while the moon has no anchor yet."""
    if epoch_s is None:
        epoch_s = time.time()
    if new_epoch is None:
        new_epoch = DEFAULT_MOON_EPOCHS[name]
    if new_epoch is None:
        return None
    return _phase_index(epoch_s - new_epoch, MOON_SYNODIC[name])


# OBSERVE MOONS describes each visible moon in prose ("has waned to a
# narrow crescent of light", "Waxing still, half of the blue moon Xibar
# looks down from above"); phase and direction are keyword-classified.
# A moon below the horizon ("nowhere to be seen") tells us nothing.
_PHASE_WORDS = (("full", 4, 4), ("gibbous", 3, 5), ("half", 2, 6), ("crescent", 1, 7))


def parse_observe_output(text):
    """{moon: phase index} for every moon OBSERVE MOONS described
    confidently; an empty dict when none were visible."""
    phases = {}
    for sentence in re.split(r"[.\n]", text):
        lowered = sentence.lower()
        moon = next((m for m in MOON_NAMES if m in lowered), None)
        if moon is None or moon in phases or "nowhere" in lowered:
            continue
        waxing = "wax" in lowered
        waning = "wan" in lowered
        for word, if_waxing, if_waning in _PHASE_WORDS:
            if word not in lowered:
                continue
            if word == "full":
                phases[moon] = 4
            elif waxing != waning:  # direction must be stated, once
                phases[moon] = if_waxing if waxing else if_waning
            break
    return phases


def calibrate_moons(phases, captured_at):
    """New-moon anchors from observed phases — store in settings as
    eltime_moons. The observed phase's center is placed at the capture
    instant (±1/16 cycle, under a real day for every moon)."""
    return {
        moon: captured_at - round(index / 8 * MOON_SYNODIC[moon])
        for moon, index in phases.items()
    }


# --- Earth's moon, optional and just for fun ---------------------------

EARTH_SYNODIC = 2_551_442.9  # 29.530589 days
EARTH_NEW_EPOCH = 947_182_440  # new moon 2000-01-06 18:14 UTC


def earth_moon_phase(epoch_s=None):
    """Phase index (0..7 into PHASES) of Earth's moon right now."""
    if epoch_s is None:
        epoch_s = time.time()
    return _phase_index(epoch_s - EARTH_NEW_EPOCH, EARTH_SYNODIC)
