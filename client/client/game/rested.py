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
beholder shades the 3x windows from (#176).
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
    "less than a minute" → 0."""
    text = text.strip()
    if text.startswith("less than a minute"):
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
