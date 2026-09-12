"""The game text's font: which family and size the GUI renders in.

Two settings in ~/.revenant/settings.json drive it — `font_family`
(a family name, "" for the platform default) and `font_size` (points,
0 for the platform default). The defaults are what an untouched file
holds; File → Settings always saves an explicit pair, pre-filled with
the font in use. The GUI applies them live to the main window, every stream dock, and the input
line — every view but the status docks: the Experience dock keeps the
fixed-pitch font at its own size (its dashboard is column-aligned, and
the story's size made it unreadable, #173) and the Spells dock the
platform font at its own size (#179); both change only through their
own entry below. This module is the Qt-free half: it turns whatever the file
holds into a clean choice.

A third setting, `dock_fonts`, overrides the pair per text view (#132):
`{"Thoughts": {"size": 8}, "Experience": {"family": "Consolas"}}` —
each entry names only what it changes, the rest follows the default.
view_font() resolves a view's (family, size); TEXT_VIEWS lists the
views the GUI has, in the order the Settings dialog shows them.
"""

MIN_SIZE = 6
MAX_SIZE = 72
# The text views a font can be set for: the story window, the input
# line, and the stream docks by title (client/ui/streamroute.py).
TEXT_VIEWS = ("Main", "Input", "Thoughts", "Spells", "Arrivals", "Deaths", "Experience")
# The docks that hold status text rather than story: the story's
# family and size never reach them, only their own dock_fonts row —
# Experience (a column-aligned dashboard, fixed-pitch, #173) and
# Spells (a few short lines, too large at a 15-point story font, #179).
STATUS_VIEWS = ("Experience", "Spells")


def font_choice(settings: dict) -> tuple[str | None, int | None]:
    """(family, size) to apply, None meaning "keep the platform default".

    Anything unusable — a blank or non-string family, a size that is
    not a whole number or falls outside 6–72 points — resolves to None
    rather than to a Qt fallback font nobody chose.
    """
    return _clean(settings.get("font_family"), settings.get("font_size"))


def _clean(family, size):
    if not isinstance(family, str) or not family.strip():
        family = None
    else:
        family = family.strip()
    if isinstance(size, bool) or not isinstance(size, (int, float)):
        size = None
    elif int(size) != size or not MIN_SIZE <= int(size) <= MAX_SIZE:
        size = None
    else:
        size = int(size)
    return family, size


def view_font(settings: dict, view: str) -> tuple[str | None, int | None]:
    """(family, size) for one text view: the per-view override where
    it names a value, the default pair otherwise, None still meaning
    "keep the platform (or, for Experience, the fixed-pitch) font".
    A status view (STATUS_VIEWS) ignores the default pair altogether.
    An override for a view the GUI has no view for, or with unusable
    values, changes nothing."""
    # A status dock — the Experience dashboard, the Spells list — takes
    # nothing from the story's pair, only its own entry (#173, #179).
    family, size = (None, None) if view in STATUS_VIEWS else font_choice(settings)
    overrides = settings.get("dock_fonts")
    entry = overrides.get(view) if isinstance(overrides, dict) else None
    if isinstance(entry, dict):
        own_family, own_size = _clean(entry.get("family"), entry.get("size"))
        if own_family:
            family = own_family
        if own_size:
            size = own_size
    return family, size


def clean_overrides(overrides) -> dict:
    """The dock_fonts mapping with only usable entries for known views —
    what the Settings dialog saves."""
    cleaned = {}
    if not isinstance(overrides, dict):
        return cleaned
    for view, entry in overrides.items():
        if view not in TEXT_VIEWS or not isinstance(entry, dict):
            continue
        family, size = _clean(entry.get("family"), entry.get("size"))
        kept = {}
        if family:
            kept["family"] = family
        if size:
            kept["size"] = size
        if kept:
            cleaned[view] = kept
    return cleaned
