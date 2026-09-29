"""Rested experience (REXP): the EXP footer parsed, and whether it is
burning between two readings.

The game states the bank in one line — "Rested EXP Stored: 5:42 hours
Usable This Cycle: 5:42 hours  Cycle Refreshes: 21 hours" — at the
foot of EXP ALL and, on every exp pulse, as `<component id='exp
rexp'>`. Times are H:MM hours, bare hours, bare minutes, or "less than
a minute" (captured 2026-09-04/05, #106). `parse_rested` reads it into
minutes; the parser keeps the latest as `XMLData.rested`, `;sheet`
stores it every three hours, `;xp` logs it per change and flags every
mindstate row it takes while the bank burns.

Burning is the usable figure falling between two readings: each skill
group that pulses with experience in it deducts twenty seconds, so a
training minute shows as a drop of one to three minutes, while an idle
bank holds still or grows (docs/experience.md, Elanthipedia
"Experience"). That is `burning(previous, current)`, the boolean
beholder shades the 3x windows from (#176). The footer does not tick
every minute, so `Burn` keeps the flag up for STICKY_MINUTES after the
last fall: a spending stretch reads burning throughout (#346).

On some accounts the window's component arrives empty on every pulse
(`<component id='exp rexp'></component>`, 250 times in one evening,
2026-09-28) and the footer shows only at the foot of an EXP answer
(;sheet's EXP ALL at login and every three hours, any EXP typed), so
the parser takes it from the story too and says which source it has
(`XMLData.rested_window`). Between such readings `available()` says
what is certain: the bank spends at most one minute a minute (twenty
seconds a pulse for each of the ten skill groups; Elanthipedia,
Experience: Rested Experience System), so a reading with more usable
minutes than minutes since it was taken still has some left. `Minute`
gives ;xp its per-minute flag from whichever source the session has.
"""

import re

_RESTED = re.compile(
    r"Rested EXP Stored:\s*(?P<stored>.+?)\s+Usable This Cycle:\s*(?P<usable>.+?)"
    r"\s+Cycle Refreshes:\s*(?P<refresh>.+?)\s*$",
    re.MULTILINE,
)
_DURATION = re.compile(r"(?:(\d+):(\d+)\s*hours?|(\d+)\s*hours?|(\d+)\s*minutes?)")
KEYS = ("stored", "usable", "refresh")


def parse_duration(text):
    """Minutes from the footer's wording, or None for anything unread:
    "5:42 hours" → 342, "6 hours" → 360, "38 minutes" → 38,
    "less than a minute" → 0, "none" → 0 (a cycle spent: "Usable This
    Cycle: none", captured 2026-09-13 and read as unknown until
    2026-09-29 — 1909 rows of history.db hold it as NULL)."""
    text = text.strip()
    if text.startswith(("less than a minute", "none")):
        return 0
    match = _DURATION.match(text)
    if not match:
        return None
    hours_mm, minutes_of, hours, minutes = match.groups()
    if hours_mm is not None:
        return int(hours_mm) * 60 + int(minutes_of)
    if hours is not None:
        return int(hours) * 60
    return int(minutes)


def parse_rested(text):
    """{"stored", "usable", "refresh"} in minutes from the footer line
    (EXP ALL's or the exp window's), or None when the line is absent."""
    match = _RESTED.search(text)
    if not match:
        return None
    return {key: parse_duration(match.group(key)) for key in KEYS}


def burning(previous, current):
    """Whether the bank burnt between two readings: True when the usable
    minutes fell, False when they held or grew, None without two
    readable readings (the first minute of a session, a footer never
    seen)."""
    if not previous or not current:
        return None
    before, after = previous.get("usable"), current.get("usable")
    if before is None or after is None:
        return None
    return after < before


# How long the bank still counts as burning after Usable last fell.
# The footer's falls come 1-3 minutes apart in training, every 5 on a
# slower character and every 10 in a steady trickle (history.db's rested
# rows, 2026-09-28: 1480 of Cecil's falls, 38 of his 61 ten-minute gaps
# between two more), so a flag per fall flickered — Westan's 21:29 read 1
# between two minutes of 0 — and no drain run read 3x throughout (#346).
STICKY_MINUTES = 11


class Burn:
    """Whether the bank burns, one reading a minute: True from a fall of
    the usable figure until STICKY_MINUTES pass without another, False
    otherwise and whenever nothing usable is left, None until two
    readable readings (the first minute, a footer never seen)."""

    def __init__(self):
        self.previous = None
        self.quiet = None  # minutes since the last fall; None: none seen

    def step(self, reading):
        fell = burning(self.previous, reading)
        if reading:
            self.previous = reading
        if fell is None:
            return None
        if fell:
            self.quiet = 0
        elif self.quiet is not None:
            self.quiet += 1
        if reading.get("usable") == 0 or self.quiet is None:
            return False
        return self.quiet < STICKY_MINUTES


# Minutes without draining before the bank starts to refill (2:1; the
# wiki's Rested Experience System).
REFILL_MINUTES = 5


def available(reading, age):
    """Whether rested experience is certainly left `age` minutes after
    `reading`. What can be spent is the lesser of the bank and the
    cycle's usable figure — "Usable This Cycle" can exceed what is
    banked (Elanthipedia, Experience), and Cecil read 0 stored with 360
    usable. True while that exceeds the age (the bank spends at most a
    minute a minute); False when the cycle was spent and has not
    refreshed since, or the bank was empty under REFILL_MINUTES ago (it
    refills after five minutes without draining); None otherwise — it
    may have run out or refilled, the cycle may have refreshed, or no
    reading."""
    if not reading or age is None:
        return None
    stored, usable = reading.get("stored"), reading.get("usable")
    refresh = reading.get("refresh")
    if usable is None or (refresh is not None and age >= refresh):
        return None
    if usable == 0:
        return False
    left = usable if stored is None else min(stored, usable)
    if left == 0:
        return False if age < REFILL_MINUTES else None
    return True if left > age else None


class Minute:
    """;xp's flag for one minute, from whichever footer the session has:
    the window's, read on every pulse (`Burn`), or else the last EXP
    answer's (`available()`, burning only while some pool drains).
    `count` is the parser's tally of footers read, so a repeat of the
    same footer still dates the reading; None for a parser without it,
    where a changed reading does."""

    def __init__(self):
        self.burn = Burn()
        self.key = None
        self.read_at = None

    def step(self, reading, now, window=True, draining=True, count=None):
        """The flag for this minute (1/0 as a bool, or None): `now` is a
        clock in minutes, `window` whether the reading comes from the
        exp window's component, `draining` whether any pool holds
        experience."""
        key = (
            count
            if count is not None
            else (tuple(sorted(reading.items())) if reading else None)
        )
        if reading and key != self.key:
            self.key, self.read_at = key, now
        flag = self.burn.step(reading) if window else None
        if flag is None and reading and self.read_at is not None:
            flag = available(reading, now - self.read_at)
            if flag and not draining:
                flag = False  # nothing drains, so nothing burns
        return flag


def hhmm(minutes):
    """ "5:42" from 342 minutes; "-" for an unread figure."""
    if minutes is None:
        return "-"
    return f"{minutes // 60}:{minutes % 60:02d}"


def describe(rested):
    """The footer as one line for a window: "Rested EXP  stored 5:42
    usable 5:42  refreshes in 21:00"."""
    return (
        f"Rested EXP  stored {hhmm(rested.get('stored'))}"
        f"  usable {hhmm(rested.get('usable'))}"
        f"  refreshes in {hhmm(rested.get('refresh'))}"
    )
