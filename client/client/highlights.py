"""User-configurable text highlights for the frontends (lich-style).

Rules live in ~/.revenant/highlights.json (REVENANT_HIGHLIGHTS
overrides the path): a JSON list of objects like

    {"pattern": "\\\\bGerblanda\\\\b", "color": "#7fe07f", "bold": true}

pattern is a Python regex; only the matched span colors, the way lich
highlight strings behave. The first load writes a starter example.
Invalid entries are skipped rather than fatal, so one typo never takes
the whole list down. The GUI reloads the file via View → Reload
Highlights.
"""

import json
import os
import re
from pathlib import Path

EXAMPLE_RULES = [
    {"pattern": "\\byour name here\\b", "color": "#7fe07f", "bold": True},
    {"pattern": "gleaming|glowing|glittering", "color": "#e0c95e", "bold": False},
]


def highlights_path() -> Path:
    return Path(
        os.environ.get("REVENANT_HIGHLIGHTS", "~/.revenant/highlights.json")
    ).expanduser()


def load_rules(path=None):
    """Compiled highlight rules; writes the starter file when missing."""
    path = path or highlights_path()
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(EXAMPLE_RULES, indent=1))
    try:
        with open(path) as stream:
            raw = json.load(stream)
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    rules = []
    for entry in raw:
        try:
            rules.append(
                {
                    "regex": re.compile(entry["pattern"]),
                    "color": entry.get("color"),
                    "bold": bool(entry.get("bold")),
                }
            )
        except (re.error, KeyError, TypeError):
            continue  # a bad rule is skipped, never fatal
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
