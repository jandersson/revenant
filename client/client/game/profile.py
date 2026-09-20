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
    # Skins go on a bundling rope: a worn lumpy bundle takes each skin
    # straight from SKIN (BUNDLE help's auto-bundling), the rope is free
    # at any tannery (ASK <tanner> FOR ROPE) and lives in the loot
    # container, and the bundle sells as one item (;skins).
    "bundle": False,
    # Self-cast buffs kept up through the hunt: PREPARE <spell>, CAST
    # before the first swing, and again whenever the Spells window no
    # longer lists it (Heroic Strength, Manifest Force, ...).
    "buffs": [],
    # A magic skill to train by recasting the first buff between swings
    # while it sits below mind-lock and mana holds: "Augmentation" for
    # a Paladin's Heroic Strength. The mana fed grows by steps until
    # the game warns of strain, then holds one step under. "" casts
    # buffs only when they run out.
    "train_casting": "",
    # A cambrinth piece held for Arcana: its noun ("flake"), charged with
    # cambrinth_mana before every training cast and INVOKEd into it. The
    # piece must not outrank the skill (a 1- or 5-mana piece at 0 ranks,
    # Herilo's Artifacts; 2026-09-14). "" charges nothing.
    "cambrinth": "",
    # The piece is worn between casts (an anklet, an armband): the
    # cycle REMOVEs it for the charge and WEARs it back, since a worn
    # piece refuses a charge ("too clumsy ... while wearing it").
    "cambrinth_worn": False,
    "cambrinth_mana": 1,
    # Seconds between training casts. A cast cycle with a cambrinth
    # piece is eight commands, and at 20 s the first badger fight was
    # seven swings to the badger's 42 in four minutes (2026-09-14,
    # #189); one a minute trains both skills and leaves the fight to
    # the weapon.
    "cast_gap": 60,
    # A targeted spell cast at the prey between swings to train
    # Debilitation ("Stun Foe" for a Paladin): one per cast_gap, the
    # mana ramping like the training casts, taking turns with them so
    # a swing never carries two casts (#192). "" casts none.
    "debilitation": "",
    # An attack spell cast at the prey between swings to train Targeted
    # Magic ("Footman's Strike" for a Paladin, cast through the melee
    # weapon in hand): the same cast gap, mana ramp and turn-taking as
    # the debilitation spell (#200). "" casts none.
    "targeted": "",
    # Below this health % the loop breaks off and walks home.
    "health_floor": 60,
    # A wound this bad or worse (any area, any kind — HEALTH, parsed by
    # client/game/wounds.py) breaks the loop off too: insignificant,
    # negligible, minor, harmful, damaging, severe, devastating,
    # useless. "" never asks HEALTH.
    "wound_floor": "",
    # Skills the hunt is for: when every one of them is mind-locked the
    # hunt ends (the exp window's mindstate). [] hunts until stopped.
    "train_skills": [],
    # A fuse: kills per run, 0 = until stopped or locked.
    "max_kills": 0,
    # Paladins: one swing a minute is SMITE instead of ATTACK, which is
    # what trains Conviction (free smites regenerate one a minute and
    # the experience comes at most once per minute, #183).
    "smite": False,
    # Tactical maneuvers in rotation ("bob", "circle", "weave"): every
    # third swing is the next one while Tactics sits below mind-lock,
    # which is what trains Tactics (Elanthipedia: Tactics skill, #190).
    # [] is off.
    "tactics": [],
    # The weapons the hunt cycles through, one per kill, each with the
    # skill it trains — "noun:Skill[:container]", the container where
    # it is kept between turns ("handaxe:Small Edged:sack"), or
    # "fists:Brawling" for the brawling attacks with nothing in hand (a
    # parry stick and knuckles are worn and work worn). A weapon whose
    # skill is mind-locked sits out until it drains; all locked ends
    # the hunt (the operator, 2026-09-20: no argument per weapon type,
    # #238). [] hunts with `weapon` alone.
    "weapons": [],
    # The brawling attacks in rotation for the fists turn ("punch",
    # "kick", "elbow" — Elanthipedia: Brawling skill; punch wants a
    # free hand, elbow and kick none), which is what trains Brawling.
    # [] means the fists turn has nothing to swing and is skipped.
    "brawling": [],
    # HUNT for tracks when a room of the ground empties, at most once
    # per 75 seconds while Perception sits below lock — HUNT teaches
    # Perception on that timer (Elanthipedia: Hunt command, #194).
    "perception": False,
    # Where ;attune walks before building its street loop — a ;go2
    # target (room id, tag, title); "" loops from wherever it stands.
    "attune_start": "",
    # The instrument ;perform plays for Performance, worn or held
    # ("zills"); "" means ;perform needs instrument=<noun> (#208).
    "instrument": "",
    # The cloth ;perform cleans the instrument with when the game says
    # its dirt weighs on the song ("rag"); "" plays it dirty (#233).
    "instrument_cloth": "",
    # The library ;scholarship books reads in — a ;go2 target (the
    # Paladins' Guild library is 11716); "" reads where it stands (#210).
    "library": "",
}

# (key, label, kind, help) — kind is "bool", "int", "str" or "list".
FIELDS = (
    ("hunting_ground", "Hunting ground (;go2 target)", "str", "rats, 6046, a title"),
    ("prey", "Prey noun to attack", "str", "empty: whatever engages you"),
    (
        "home",
        "Walk home to (;go2 target)",
        "str",
        "empty: a break-off leaves you just off the ground",
    ),
    ("weapon", "Weapon noun", "str", "empty: barehanded"),
    ("weapon_container", "Weapon is kept in", "str", "sack, sheath — empty: in hand"),
    ("stance", "STANCE SET arguments", "str", "e.g. 100 80 0 — empty: leave it"),
    ("skin", "Skin each kill", "bool", ""),
    ("skin_knife", "Skinning knife noun", "str", "empty: the wielded weapon"),
    ("loot_container", "Stow loot and skins in", "str", "empty: the STOW default"),
    ("gem_pouch", "Gem pouch noun", "str", "empty: gems are stowed like loot"),
    (
        "bundle",
        "Bundle skins on a bundling rope",
        "bool",
        "worn; ASK a tanner FOR ROPE",
    ),
    ("buffs", "Buff spells to keep up", "list", "Heroic Strength, Manifest Force"),
    (
        "train_casting",
        "Recast the first buff to train",
        "str",
        "Augmentation — empty: cast only when it runs out",
    ),
    ("cambrinth", "Cambrinth piece to charge for Arcana", "str", "flake — empty: none"),
    ("cambrinth_mana", "Mana per cambrinth charge", "int", "1: the piece's capacity"),
    (
        "cambrinth_worn",
        "The cambrinth piece is worn (REMOVE, charge, WEAR)",
        "bool",
        "",
    ),
    ("cast_gap", "Seconds between training casts", "int", "60"),
    (
        "debilitation",
        "Spell cast at the prey (Debilitation)",
        "str",
        "Stun Foe — empty: none",
    ),
    (
        "targeted",
        "Attack spell cast at the prey (Targeted Magic)",
        "str",
        "Footman's Strike — empty: none",
    ),
    ("health_floor", "Break off below health %", "int", "60"),
    (
        "wound_floor",
        "Break off at a wound this bad",
        "str",
        "harmful, severe — empty: off",
    ),
    ("train_skills", "Stop when these skills lock", "list", "Small Edged, Evasion"),
    ("max_kills", "Kills per run (0 = until stopped)", "int", ""),
    ("smite", "SMITE one swing a minute (Paladin: Conviction)", "bool", ""),
    (
        "tactics",
        "Maneuvers every third swing (Tactics)",
        "list",
        "bob, circle — empty: off",
    ),
    ("perception", "HUNT for tracks when a room empties (Perception)", "bool", ""),
    (
        "weapons",
        "Weapons cycled per kill (noun:Skill[:container])",
        "list",
        "handaxe:Small Edged:sack, fists:Brawling — empty: the weapon alone",
    ),
    (
        "brawling",
        "Brawling attacks for the fists turn (Brawling)",
        "list",
        "punch, kick, elbow — empty: the fists turn is skipped",
    ),
    ("attune_start", ";attune walks to (;go2 target)", "str", "empty: from here"),
    (
        "instrument",
        "Instrument ;perform plays (Performance)",
        "str",
        "zills — empty: none",
    ),
    (
        "instrument_cloth",
        "Cloth ;perform cleans the instrument with",
        "str",
        "rag — empty: a dirty instrument plays on",
    ),
    (
        "library",
        "Library ;scholarship reads in (;go2 target)",
        "str",
        "11716 — empty: here",
    ),
)

_KINDS = {key: kind for key, _, kind, _ in FIELDS}
_UNSAFE = re.compile(r"[^a-z0-9_-]")


def profiles_dir() -> Path:
    return Path(
        os.environ.get("REVENANT_PROFILES", "~/.revenant/profiles")
    ).expanduser()


def slug(character) -> str:
    """A character name as a filename: lowercase, letters and digits
    only — the game's name is a filename here, so nothing else gets
    through. Shared with the training plans (client/game/training.py)."""
    return _UNSAFE.sub("", (character or "").strip().lower()) or "unnamed"


def profile_path(character) -> Path:
    """The profile file for a character."""
    return profiles_dir() / f"{slug(character)}.json"


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
