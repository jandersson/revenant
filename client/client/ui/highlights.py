"""User-configurable text highlights for the frontends (lich-style).

Rules live in ~/.revenant/highlights.json (REVENANT_HIGHLIGHTS
overrides the path): a JSON list of objects like

    {"pattern": "\\\\bGerblanda\\\\b", "color": "#7fe07f", "bold": true}

pattern is a Python regex; only the matched span colors, the way lich
highlight strings behave. The first load writes a starter example.
Invalid entries are skipped rather than fatal, so one typo never takes
the whole list down. The GUI reloads the file via View → Reload
Highlights.

A few defaults ship in code (DEFAULT_RULES, 2026-09-13 — the operator
asked for a soft highlight on the balance line and whatever else the
logs say earns one): the combat balance line, the roundtime line and
the spell-ready lines, each in a soft colour because they come every
swing. Each has a name; a file entry {"disable": "balance"} turns one
off, a file rule with the same name replaces it, and a file rule
matching the same text wins the span (file rules come first).
"""

import json
import os
import re
from pathlib import Path

EXAMPLE_RULES = [
    {"pattern": "\\byour name here\\b", "color": "#7fe07f", "bold": True},
    {"pattern": "gleaming|glowing|glittering", "color": "#e0c95e", "bold": False},
]

# Shipped defaults, from tonight's logs (2026-09-13: the balance line
# 4,000 times, the roundtime line 800, the spell-ready lines 140):
# soft colours from the story's palette, never bold.
DEFAULT_RULES = [
    {
        # "[You're solidly balanced and in strong position.]" — the
        # balance and position after every exchange.
        "name": "balance",
        "pattern": r"\[You're [^\]]*\]",
        "color": "#8fa3c4",
        "bold": False,
    },
    {
        # "[Roundtime 6 sec.]" after a swing, "Roundtime: 2 sec." after
        # a skin or a move.
        "name": "roundtime",
        "pattern": r"\[Roundtime \d+ sec\.\]|\bRoundtime: \d+ sec\.",
        "color": "#b8a070",
        "bold": False,
    },
    {
        # The spell is ready to cast; the mana streams are back.
        "name": "ready",
        "pattern": (
            r"You feel fully (?:prepared to cast your spell"
            r"|attuned to the mana streams again)\."
        ),
        "color": "#8fc7e8",
        "bold": False,
    },
]


def highlights_path() -> Path:
    return Path(
        os.environ.get("REVENANT_HIGHLIGHTS", "~/.revenant/highlights.json")
    ).expanduser()


def _compile(entry):
    return {
        "name": entry.get("name"),
        "regex": re.compile(entry["pattern"]),
        "color": entry.get("color"),
        "bold": bool(entry.get("bold")),
    }


def load_rules(path=None, defaults=DEFAULT_RULES):
    """Compiled highlight rules: the file's, then the shipped defaults
    the file has not disabled or replaced by name. Writes the starter
    file when missing; an unreadable file leaves the defaults."""
    path = path or highlights_path()
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(EXAMPLE_RULES, indent=1))
    try:
        with open(path) as stream:
            raw = json.load(stream)
    except (OSError, ValueError):
        raw = []
    if not isinstance(raw, list):
        raw = []
    rules = []
    taken = set()  # default names the file disabled or replaced
    for entry in raw:
        if isinstance(entry, dict) and "disable" in entry:
            taken.add(entry["disable"])
            continue
        try:
            rule = _compile(entry)
        except (re.error, KeyError, TypeError, AttributeError):
            continue  # a bad rule is skipped, never fatal
        rules.append(rule)
        if rule["name"]:
            taken.add(rule["name"])
    for entry in defaults:
        if entry["name"] not in taken:
            rules.append(_compile(entry))
    return rules


def load_entries(path=None):
    """The raw rule entries as saved (for the editor dialog) — every
    dict in the file, valid or not, so a broken pattern can be fixed
    in place instead of silently vanishing."""
    path = path or highlights_path()
    try:
        with open(path) as stream:
            raw = json.load(stream)
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def save_entries(entries, path=None):
    """Write rule entries back (the editor dialog's save)."""
    path = path or highlights_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(entries), indent=1))


def pattern_error(pattern):
    """The regex compile error for a pattern, or None when it is fine."""
    try:
        re.compile(pattern)
    except re.error as error:
        return str(error)
    return None


def spans(text, rules):
    """Non-overlapping (start, end, rule) highlight spans for a piece of
    text, earliest match winning overlaps (longer match breaking ties)."""
    found = []
    for rule in rules:
        for match in rule["regex"].finditer(text):
            if match.start() < match.end():
                found.append((match.start(), match.end(), rule))
    found.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    result = []
    cursor = 0
    for start, end, rule in found:
        if start >= cursor:
            result.append((start, end, rule))
            cursor = end
    return result
