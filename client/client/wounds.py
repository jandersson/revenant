"""HEALTH, parsed: wounds by body area, severity and kind, plus bleeders.

parse_health(text) turns the game's HEALTH answer into a Health: the
vitality and spirit lines, one Wound per body area with its external,
scar, internal and internal-scar severities (1-8: insignificant,
negligible, minor, harmful, damaging, severe, devastating, useless),
the bleeding table's rate per area, and whatever fragment matched no
known wording (`unknown`, for reporting). Scripts compare severities
by number — Health.worst(), Health.at_least("harmful") — instead of
reading only the health percentage (#151); ;tend takes its bleeders
from here, ;hunt its wound floor.

The wordings are Elanthipedia's Damage tables, generated into
client/wounds_data.py by tools/wound_tables.py; the bleed rates follow
the same page and Lich's healing data. A phrase the wiki lists at two
severities ("a constant twitching in the neck" is harmful and
damaging) is read as the lower one. Captured HEALTH answers pin the
parser in client/tests/test_wounds.py.
"""

import re
from dataclasses import dataclass, field

from client.wounds_data import ROWS

SEVERITIES = (
    "none",
    "insignificant",
    "negligible",
    "minor",
    "harmful",
    "damaging",
    "severe",
    "devastating",
    "useless",
)
KINDS = ("external", "scar", "internal", "internal_scar")

# Bleed rate -> (severity for triage, a bandage can help), the health
# command's wordings; "(tended)" and clotted variants need no tending.
RATES = {
    "slight": (3, True),
    "light": (4, True),
    "moderate": (5, True),
    "bad": (6, True),
    "very bad": (7, True),
    "heavy": (8, True),
    "very heavy": (9, True),
    "severe": (10, True),
    "very severe": (11, True),
    "extremely severe": (12, True),
    "profuse": (13, True),
    "gushing": (14, True),
    "massive stream": (15, True),
    "uncontrollable": (16, True),
    "unbelievable": (17, True),
    "beyond measure": (18, True),
    "death awaits": (19, True),
}

BLEED_ROW = re.compile(
    r"^\s*(?P<inside>inside\s+)?"
    r"(?P<area>(?:l\.|r\.|left|right)?\s?"
    r"(?:head|eye|neck|chest|abdomen|back|arm|hand|leg|tail|skin))"
    r"\s{2,}(?P<rate>[a-z( )]+?)\s*$",
    re.IGNORECASE,
)
_VITALITY = re.compile(r"Your body feels (?P<how>[^.]+)\.")
_SPIRIT = re.compile(r"Your spirit feels (?P<how>[^.]+)\.")
_WOUNDS = re.compile(r"You have (?P<list>.+?)\.\s*$", re.MULTILINE)
NO_INJURIES = "no significant injuries"


def level(name):
    """A severity name ("harmful") as its number; numbers pass through."""
    if isinstance(name, int):
        return name
    return SEVERITIES.index(str(name).strip().lower())


def _pattern(phrase):
    escaped = re.escape(phrase)
    escaped = escaped.replace(re.escape("[right/left]"), r"(?P<side>right|left)")
    escaped = escaped.replace(re.escape("[left/right]"), r"(?P<side>left|right)")
    escaped = escaped.replace(
        re.escape("[hand/arm/leg/tail]"), r"(?P<limb>hand|arm|leg|tail)"
    )
    return re.compile(escaped, re.IGNORECASE)


def _compile():
    """(regex, area, kind, level) for every wording, longest phrase
    first so a longer wording claims its span before a shorter one
    contained in it; a repeated phrase keeps its lowest level."""
    seen = {}
    for area, lvl, kind, phrase in ROWS:
        key = (area, kind, phrase)
        seen[key] = min(lvl, seen.get(key, lvl))
    rows = sorted(seen.items(), key=lambda item: -len(item[0][2]))
    return [(_pattern(phrase), area, kind, lvl) for (area, kind, phrase), lvl in rows]


_PATTERNS = _compile()


@dataclass
class Wound:
    area: str
    external: int = 0
    scar: int = 0
    internal: int = 0
    internal_scar: int = 0
    bleeding: str | None = None  # the table's rate word, "clotted(tended)" included
    inside_bleeding: str | None = None

    def worst(self):
        """(kind, level) of the worst of the four, or None when unhurt."""
        levels = [(getattr(self, kind), kind) for kind in KINDS]
        top, kind = max(levels)
        return (kind, top) if top else None


@dataclass
class Health:
    vitality: str | None = None
    spirit: str | None = None
    wounds: dict = field(default_factory=dict)
    unknown: list = field(default_factory=list)
    # The bleeding table's rows in the game's order: (area, inside, rate).
    bleeding: list = field(default_factory=list)

    def wound(self, area):
        return self.wounds.setdefault(area, Wound(area))

    def worst(self):
        """(area, kind, level) of the worst wound, or None when unhurt."""
        top = None
        for wound in self.wounds.values():
            hit = wound.worst()
            if hit and (top is None or hit[1] > top[2]):
                top = (wound.area, hit[0], hit[1])
        return top

    def at_least(self, severity):
        """Every (area, kind, level) at this severity or worse."""
        floor = level(severity)
        found = []
        for wound in self.wounds.values():
            for kind in KINDS:
                lvl = getattr(wound, kind)
                if lvl >= floor:
                    found.append((wound.area, kind, lvl))
        return found

    def bleeders(self):
        """The bleeding table as ;tend's rows: [{area, inside, rate,
        severity, tendable}], tended and clotted rows at severity 0."""
        rows = []
        for area, inside, rate in self.bleeding:
            if rate.endswith("(tended)") or rate.startswith("clotted"):
                severity, tendable = 0, False
            elif rate in RATES:
                severity, tendable = RATES[rate]
            else:
                continue
            rows.append(
                {
                    "area": area,
                    "inside": inside,
                    "rate": rate,
                    "severity": severity,
                    "tendable": tendable,
                }
            )
        return rows


def expand_area(area):
    """The bleeding table abbreviates sides; commands want them spelled out."""
    return area.replace("l.", "left").replace("r.", "right").strip()


def _area_of(match, area):
    if area == "limb":
        return f"{match.group('side')} {match.group('limb')}".lower()
    if area == "eye":
        return f"{match.group('side')} eye".lower()
    return area


def parse_wound_list(text, health):
    """The "You have ..." list into health.wounds; leftovers to unknown."""
    taken = []
    for pattern, area, kind, lvl in _PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if any(start < span[1] and span[0] < end for start, end in taken):
                continue
            taken.append(span)
            wound = health.wound(_area_of(match, area))
            setattr(wound, kind, max(getattr(wound, kind), lvl))
    remainder = text
    for start, end in sorted(taken, reverse=True):
        remainder = remainder[:start] + "|" + remainder[end:]
    for fragment in re.split(r"[|,]| and ", remainder):
        fragment = fragment.strip(" .")
        # HEALTH prefixes articles the wiki leaves off ("some minor
        # abrasions", "an occasional twitching"): not a wound of their own.
        words = fragment.split()
        while words and words[0].lower() in ("a", "an", "some", "and"):
            words = words[1:]
        fragment = " ".join(words)
        if not fragment:
            continue
        health.unknown.append(fragment)


def parse_health(text_or_lines):
    """A HEALTH answer (a string, or the collected lines) as a Health."""
    if not isinstance(text_or_lines, str):
        text_or_lines = "\n".join(text_or_lines)
    text = text_or_lines
    health = Health()
    if match := _VITALITY.search(text):
        health.vitality = match.group("how")
    if match := _SPIRIT.search(text):
        health.spirit = match.group("how")
    for match in _WOUNDS.finditer(text):
        listed = match.group("list")
        if NO_INJURIES in listed:
            continue
        parse_wound_list(listed, health)
    for line in text.splitlines():
        row = BLEED_ROW.match(line)
        if not row:
            continue
        area = expand_area(row.group("area"))
        wound = health.wound(area)
        rate = row.group("rate").strip().lower()
        inside = bool(row.group("inside"))
        health.bleeding.append((area, inside, rate))
        if inside:
            wound.inside_bleeding = rate
        else:
            wound.bleeding = rate
    return health


def describe(health):
    """One line per wounded area, worst kind first — for echoes."""
    lines = []
    for area, wound in sorted(health.wounds.items()):
        parts = [
            f"{kind.replace('_', ' ')} {SEVERITIES[getattr(wound, kind)]}"
            for kind in KINDS
            if getattr(wound, kind)
        ]
        if wound.bleeding:
            parts.append(f"bleeding {wound.bleeding}")
        if wound.inside_bleeding:
            parts.append(f"bleeding inside {wound.inside_bleeding}")
        if parts:
            lines.append(f"{area}: {', '.join(parts)}")
    return lines
