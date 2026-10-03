"""The game's STORE containers as ;hunt last set them, per character —
where STOW BOX and STOW GEM put a box or a gem.

STORE is the game's own setting and stays until changed (the operator,
2026-09-26), so ;hunt sends STORE BOXES IN <loot_container> only when
the profile's container differs from the one it last set, and keeps
that one in ~/.revenant/stores/<name>.json ({"boxes": "sack", "gems":
"pouch", "turns": {...}}; REVENANT_STORES_DIR moves the directory).
;boxes reads it too: a box STOWed since the last INV LIST is in the
STORE container, whatever the loot container says now (#432).
"""

import json
import os
from pathlib import Path


def path(character):
    """Where a character's STORE containers are remembered."""
    base = os.environ.get("REVENANT_STORES_DIR") or str(
        Path.home() / ".revenant" / "stores"
    )
    return Path(base) / f"{character or 'unknown'}.json"


def load(character):
    """The remembered STOREs ({} when none or unreadable)."""
    try:
        return json.loads(path(character).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def remember(character, stores):
    target = path(character)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(stores, indent=1), encoding="utf-8")


def boxes_container(character):
    """The container STOW BOX last put boxes in, lower-cased, or ""."""
    return str(load(character).get("boxes") or "").strip().lower()
