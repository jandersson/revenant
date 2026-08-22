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
    "quit_on_close": True,  # closing the window sends quit to the game
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
