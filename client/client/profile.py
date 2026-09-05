"""Per-character profiles: the quirks a training script must not hard-code.

A profile is ~/.revenant/profiles/<character>.json — one file per
character, read through this Qt-free module by scripts (;hunt) and
edited from the GUI's File → Character Profile… dialog. It holds what
differs from character to character: the weapon and where it lives,
the stance, whether kills are skinned and with what, whether gems go
in a pouch, the health floor, the hunting ground and the way home.
Unknown keys in the file are preserved on save, so a script can grow
a field before the dialog learns it.

FIELDS is the schema the dialog builds itself from: one row per
setting with its label, kind and help text, in display order. Adding a
profile setting means adding a default and a FIELDS row — the editor
picks it up without a change of its own. REVENANT_PROFILES overrides
the directory (tests point it at a temp dir).
"""

import json
import os
import re
from pathlib import Path

DEFAULTS = {
    # What to fight and where. The ground is a ;go2 target (tag, room
    # id or title substring); every room it resolves to is part of the
    # ground, and the loop moves between them when one runs empty.
    "hunting_ground": "rats",
    "prey": "",  # noun to ATTACK; "" swings at whatever engages you
    "home": "",  # a ;go2 target to walk back to when the hunt ends
    # The weapon: GET <weapon> [FROM <container>] before the first
    # swing. "" fights barehanded (brawling).
    "weapon": "",
    "weapon_container": "",
    # STANCE SET <evasion> <parry> <shield> [<attack>]; "" leaves the
    # stance alone. Defensive-first is the convention (docs/combat.md).
    "stance": "",
    # Skinning: SKIN <corpse> after each kill, with the wielded weapon
    # unless a knife noun is named (the game wants an edged weapon or a
    # belt knife). The skin is stowed into the loot container.
    "skin": False,
    "skin_knife": "",
    "loot_container": "",  # "" stows with the game's STOW default
    # Gems found on a corpse go into this pouch; "" leaves them stowed.
    "gem_pouch": "",
    # Below this health % the loop breaks off and walks home.
    "health_floor": 60,
    # Skills the hunt is for: when every one of them is mind-locked the
    # hunt ends (the exp window's mindstate). [] hunts until stopped.
    "train_skills": [],
    # A fuse: kills per run, 0 = until stopped or locked.
    "max_kills": 0,
}

# (key, label, kind, help) — kind is "bool", "int", "str" or "list".
FIELDS = (
    ("hunting_ground", "Hunting ground (;go2 target)", "str", "rats, 6046, a title"),
    ("prey", "Prey noun to attack", "str", "empty: whatever engages you"),
    ("home", "Walk home to (;go2 target)", "str", "empty: stay where the hunt ends"),
    ("weapon", "Weapon noun", "str", "empty: barehanded"),
    ("weapon_container", "Weapon is kept in", "str", "sack, sheath — empty: in hand"),
    ("stance", "STANCE SET arguments", "str", "e.g. 100 80 0 — empty: leave it"),
    ("skin", "Skin each kill", "bool", ""),
    ("skin_knife", "Skinning knife noun", "str", "empty: the wielded weapon"),
    ("loot_container", "Stow loot and skins in", "str", "empty: the STOW default"),
    ("gem_pouch", "Gem pouch noun", "str", "empty: gems are stowed like loot"),
    ("health_floor", "Break off below health %", "int", "60"),
    ("train_skills", "Stop when these skills lock", "list", "Small Edged, Evasion"),
    ("max_kills", "Kills per run (0 = until stopped)", "int", ""),
)

_KINDS = {key: kind for key, _, kind, _ in FIELDS}
_UNSAFE = re.compile(r"[^a-z0-9_-]")


def profiles_dir() -> Path:
    return Path(
        os.environ.get("REVENANT_PROFILES", "~/.revenant/profiles")
    ).expanduser()


def profile_path(character) -> Path:
    """The file for a character: lowercase, letters and digits only —
    the game's name is a filename here, so nothing else gets through."""
    slug = _UNSAFE.sub("", (character or "").strip().lower()) or "unnamed"
    return profiles_dir() / f"{slug}.json"


def normalize(values: dict) -> dict:
    """Values coerced to their FIELDS kind — the file is hand-editable
    and the dialog hands back strings; neither gets to break a script."""
    clean = {}
    for key, value in values.items():
        kind = _KINDS.get(key)
        if kind == "bool":
            clean[key] = (
                value
                if isinstance(value, bool)
                else str(value).lower() in ("1", "true", "yes", "on")
            )
        elif kind == "int":
            try:
                clean[key] = int(value)
            except (TypeError, ValueError):
                clean[key] = DEFAULTS[key]
        elif kind == "list":
            if isinstance(value, str):
                value = value.split(",")
            clean[key] = [
                str(item).strip() for item in (value or []) if str(item).strip()
            ]
        elif kind == "str":
            clean[key] = str(value or "").strip()
        else:
            clean[key] = value  # a key this build doesn't know: kept as is
    return clean


def load_profile(character) -> dict:
    """Defaults merged with whatever the character's file holds."""
    merged = dict(DEFAULTS)
    try:
        with open(profile_path(character), encoding="utf-8") as stream:
            stored = json.load(stream)
    except (OSError, ValueError):
        return merged
    if isinstance(stored, dict):
        merged.update(normalize(stored))
    return merged


def save_profile(character, values: dict) -> Path:
    """Persist a character's profile, keeping keys this build doesn't know."""
    path = profile_path(character)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(load_profile(character) | normalize(values), indent=1),
        encoding="utf-8",
    )
    return path


def describe(profile: dict) -> list:
    """One line per FIELDS row, for ;hunt profile and the like."""
    lines = []
    for key, label, kind, _ in FIELDS:
        value = profile.get(key, DEFAULTS.get(key))
        if kind == "list":
            value = ", ".join(value) or "(none)"
        elif kind == "bool":
            value = "yes" if value else "no"
        elif value == "":
            value = "(empty)"
        lines.append(f"{label}: {value}")
    return lines
