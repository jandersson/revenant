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
    "autostart_wealth": True,  # BANK ACCOUNT after login and every 3 hours (;wealth)
    "autostart_extra": [],  # more scripts to start, e.g. ["lnet", "athletics"]
    "quit_on_close": True,  # closing the window sends quit to the game
    # The session answers the game's "YOU HAVE BEEN IDLE TOO LONG"
    # warning with one TIME, so a quiet window is not logged out (#153).
    # REVENANT_NO_IDLE_ANSWER=1 turns it off for one launch.
    "answer_idle_warning": True,
    "eltime_offset_seconds": 0,  # ;clock's Elanthian calendar correction
    "eltime_moons": {},  # ;clock's moon anchors: {moon: new-moon unix time}
    "eltime_moon_rises": {},  # ;clock watch's orbit anchors: {moon: rise unix time}
    "clocks_earth_moon": False,  # the for-fun Earth moon row in the clocks dock
    # The map room id after each room name in the story — "[Town
    # Green] (1420)", the id ;go2 takes — resolved by the Map dock
    # (client/ui/roomids.py). Rooms off the map get nothing.
    "show_room_ids": True,
    # Developer mode: the script engine reports a script start that took
    # long to load (helper reloads included). REVENANT_DEV=1 turns it on
    # for one launch.
    "dev_mode": False,
    # revenant-send (client/engine/sendcmd.py, #135): commands beyond the
    # read-only allowlist may be sent into a session from outside.
    # REVENANT_ALLOW_SEND=1 opens the gate for one call.
    "allow_external_send": False,
    "lnet_name": "",  # the last name the standalone chat window logged in as
    # The game text's font (client/ui/textfont.py): a family name and a
    # point size. "" / 0 — what an untouched file holds — means the
    # platform font; the Settings dialog always saves an explicit pair.
    # Applied live to the main window, stream docks, and input line.
    "font_family": "",
    "font_size": 0,
    # Per-view overrides of the pair, keyed by text view (Main, Input,
    # Thoughts, Spells, Arrivals, Deaths, Experience), each naming only
    # what it changes: {"Thoughts": {"size": 8}} (#132).
    "dock_fonts": {},
    # Rooms travel routes around when a clean detour exists — each entry
    # a ;go2-style target (tag, room id, or title substring). Defaults
    # are the cougar grounds that killed a walker (#72); edit the file
    # to extend. ;go2 direct <target> ignores the list for one trip.
    "avoid_rooms": ["cougars", "cougars_vineyard"],
    # Item names (as typed after DROP MY) a script may drop, beyond the
    # built-in foraged junk in client/game/discard.py — nothing else is
    # ever dropped: a dropped item is a lost item.
    "droppable": [],
    # ;athletics' in-town rotation skips the stops dr-scripts flags as
    # justice areas when this is on — for a character the guards want.
    "avoid_justice_climbs": False,
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


def dev_mode() -> bool:
    """Developer mode: the settings toggle, or REVENANT_DEV=1 for one
    launch. Read on demand, so a change in File → Settings applies to
    the running session's next script start."""
    if os.environ.get("REVENANT_DEV") == "1":
        return True
    return bool(setting("dev_mode"))
