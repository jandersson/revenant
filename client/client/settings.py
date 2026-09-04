"""User settings shared by every revenant process.

Settings live in ~/.revenant/settings.json (REVENANT_SETTINGS overrides
the path) and are read through this Qt-free module by the session and
the GUI alike. Environment variables still win over the file
(REVENANT_NO_XP=1 beats autostart_xp: true), so scripted launches stay
overridable. Unknown keys in the file are preserved on save.
"""

import json
import os
from pathlib import Path

DEFAULTS = {
    "autostart_xp": True,  # log experience history in every session
    "autostart_beholder": True,  # keep the dashboard server up, quietly
    "autostart_sheet": True,  # snapshot the character sheet periodically
    "autostart_deathwatch": True,  # depart safely on unattended death (#90)
    "autostart_extra": [],  # more scripts to start, e.g. ["lnet", "athletics"]
    "quit_on_close": True,  # closing the window sends quit to the game
    "eltime_offset_seconds": 0,  # ;clock's Elanthian calendar correction
    "eltime_moons": {},  # ;clock's moon anchors: {moon: new-moon unix time}
    "clocks_earth_moon": False,  # the for-fun Earth moon row in the clocks dock
    # The game text's font (client/textfont.py): a family name and a
    # point size, "" / 0 for the platform default. Applied live from
    # File → Settings to the main window, stream docks, and input line.
    "font_family": "",
    "font_size": 0,
    # Rooms travel routes around when a clean detour exists — each entry
    # a ;go2-style target (tag, room id, or title substring). Defaults
    # are the cougar grounds that killed a walker (#72); edit the file
    # to extend. ;go2 direct <target> ignores the list for one trip.
    "avoid_rooms": ["cougars", "cougars_vineyard"],
}


def settings_path() -> Path:
    return Path(
        os.environ.get("REVENANT_SETTINGS", "~/.revenant/settings.json")
    ).expanduser()


def load_settings() -> dict:
    """Defaults merged with whatever the file holds."""
    merged = dict(DEFAULTS)
    try:
        with open(settings_path()) as stream:
            stored = json.load(stream)
    except (OSError, ValueError):
        return merged
    if isinstance(stored, dict):
        merged.update(stored)
    return merged


def save_settings(values: dict):
    """Persist settings, keeping any keys this build doesn't know."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(load_settings() | dict(values), indent=1))


def setting(name):
    return load_settings().get(name, DEFAULTS.get(name))
