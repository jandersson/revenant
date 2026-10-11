"""A Moon Mage's moonbeam and the Teleport back to it (#522): the moons
read off PERCEIVE MOONS, the beam focused on the moon with the most time
left, the beam's record kept for the way home — ;moonbeam's model.

Captured by hand on a circle-200 Moon Mage, 2026-10-10 (#522). PERCEIVE
MOONS (9 s roundtime) says each moon: up, "Xibar is a new moon, high in
the eastern sky." and "You're certain that Xibar is seventy-two degrees
above the eastern horizon."; down, "Yavash is a full moon and is not
visible.  Although you cannot see it, you can sense it should rise in
about 4 anlaen." A moon is up 174–178 minutes across its 180 degrees, so
one in the east has 180 less its degrees to go, one in the west its
degrees. Focus Moonbeam (`cast xibar`, outdoors): "A beam of clear
silvery-blue light descends from the heavens as you focus a moonbeam from
Xibar into the area."; it lasts 45–210 minutes by its mana, and never past
its moon's setting (Elanthipedia: Focus Moonbeam). Distant Gaze shows the
beam's room: "You concentrate on your Xibar moonbeam, overlaying an oddly
flat image from its location upon your normal vision...". Teleport (`cast
xibar`): "Elanthia seems to fall away from under your feet as the entire
world disappears in a brilliant blue flash.", then "You are stunned!".
Teleport on a moon that is down disintegrates the caster (past circle 100
it sets them in an Astral Plane conduit), and to a beam that has lapsed is
"usually fatal" (Elanthipedia: Teleport) — so the moon and the beam are
both checked first, as dr-scripts' gate.lic checks the moon.
"""

import json
import re

MOONS = ("katamba", "xibar", "yavash")
UP_MINUTES = 176  # a moon crosses its 180 degrees above the horizon in 174-178
TELEPORT_MARGIN = 4  # minutes of the moon's time a teleport wants (gate.lic's 4)
FOCUS_MARGIN = 8  # minutes a moon needs left to be worth a beam (gate.lic's 8)

FOCUSED = "you focus a moonbeam from"
GAZED = "You concentrate on your"
TELEPORTED = "Elanthia seems to fall away from under your feet"

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}  # fmt: skip
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip

_MOON = r"(?P<moon>Katamba|Xibar|Yavash)"
_DEGREES = re.compile(
    rf"{_MOON} is (?P<deg>[a-z0-9 -]+?) degrees? above the "
    r"(?P<side>eastern|western) horizon",
    re.I,
)
_DOWN = re.compile(rf"{_MOON} is (?:an? )?[\w ]*?moon and is not visible", re.I)
_UP = re.compile(rf"{_MOON} is (?:an? )?[\w ]*?moon, [^.]*\bsky\b", re.I)


def number(words):
    """An integer from the game's words ("seventy-two", "nine", "72"), or
    None."""
    text = str(words or "").strip().lower()
    if text.isdigit():
        return int(text)
    total = 0
    for part in re.split(r"[\s-]+", text):
        if part in _ONES:
            total += _ONES[part]
        elif part in _TENS:
            total += _TENS[part]
        elif part:
            return None
    return total if text else None


def parse_moons(text):
    """{moon: {"up": bool, "degrees": int or None, "side": "east"/"west"
    or None}} for each moon PERCEIVE MOONS named; a moon it did not name
    is left out."""
    moons = {}
    lines = str(text or "").splitlines()
    for index, line in enumerate(lines):
        if match := _DOWN.search(line):
            moons[match.group("moon").lower()] = {
                "up": False,
                "degrees": None,
                "side": None,
            }
            continue
        if match := _UP.search(line):
            moons.setdefault(
                match.group("moon").lower(), {"up": True, "degrees": None, "side": None}
            )
        if match := _DEGREES.search(line):
            moons[match.group("moon").lower()] = {
                "up": True,
                "degrees": number(match.group("deg")),
                "side": match.group("side").lower()[:4],
            }
    return moons


def minutes_left(entry):
    """Minutes until the moon sets, from its degrees and side; None when
    the reading has no degrees, 0 when it is down."""
    if not entry or not entry.get("up"):
        return 0
    degrees, side = entry.get("degrees"), entry.get("side")
    if degrees is None or side not in ("east", "west"):
        return None
    arc = 180 - degrees if side == "east" else degrees
    return round(max(arc, 0) * UP_MINUTES / 180)


def best_moon(moons):
    """The moon up with the most minutes left (FOCUS_MARGIN at least), or
    None: a beam lasts no longer than its moon is up."""
    timed = [
        (minutes_left(entry), moon)
        for moon, entry in moons.items()
        if entry.get("up") and minutes_left(entry) is not None
    ]
    timed = [(minutes, moon) for minutes, moon in timed if minutes >= FOCUS_MARGIN]
    return max(timed)[1] if timed else None


def says(moon, entry):
    """The moon in words: "Xibar up, sets in about 106 minutes", "Yavash
    down"."""
    name = moon.title()
    if not entry or not entry.get("up"):
        return f"{name} down"
    minutes = minutes_left(entry)
    if minutes is None:
        return f"{name} up"
    return f"{name} up, sets in about {minutes} minutes"


# --- the beam's record --------------------------------------------------------


def record_path(name):
    from client.game.training import training_dir

    return training_dir() / f"{str(name).lower()}.moonbeam.json"


def record(name, beam):
    """The beam focused: its moon, room (map id and title), mana and the
    wall time it went up."""
    path = record_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(beam)), encoding="utf-8")


def load(name):
    try:
        data = json.loads(record_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def usable(beam, now):
    """True while a recorded beam may still stand with TELEPORT_MARGIN to
    spare: before its moon's setting as read at the focus (`ends`), or
    within a moon's whole time up of the focus for a record without
    one. The walker plans a Teleport on it; ;moonbeam teleport checks the
    moon and the beam before it casts."""
    if not beam or not beam.get("room"):
        return False
    ends = beam.get("ends") or beam.get("at", 0) + UP_MINUTES * 60
    return now < ends - TELEPORT_MARGIN * 60


def clear(name):
    try:
        record_path(name).unlink()
    except OSError:
        pass
