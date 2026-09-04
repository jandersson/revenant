"""The game text's font: which family and size the GUI renders in.

Two settings in ~/.revenant/settings.json drive it — `font_family`
(a family name, "" for the platform default) and `font_size` (points,
0 for the platform default). The defaults are what an untouched file
holds; File → Settings always saves an explicit pair, pre-filled with
the font in use. The GUI applies them live to the main window, every stream dock, and the input
line; the Experience dock keeps its fixed-pitch family (its dashboard
is column-aligned) and only follows the size. This module is the
Qt-free half: it turns whatever the file holds into a clean choice.
"""

MIN_SIZE = 6
MAX_SIZE = 72


def font_choice(settings: dict) -> tuple[str | None, int | None]:
    """(family, size) to apply, None meaning "keep the platform default".

    Anything unusable — a blank or non-string family, a size that is
    not a whole number or falls outside 6–72 points — resolves to None
    rather than to a Qt fallback font nobody chose.
    """
    family = settings.get("font_family")
    if not isinstance(family, str) or not family.strip():
        family = None
    else:
        family = family.strip()
    size = settings.get("font_size")
    if isinstance(size, bool) or not isinstance(size, (int, float)):
        size = None
    elif int(size) != size or not MIN_SIZE <= int(size) <= MAX_SIZE:
        size = None
    else:
        size = int(size)
    return family, size
