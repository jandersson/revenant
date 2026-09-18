"""Finding a wandering NPC — the model behind ;seek (#207).

A wandering NPC (Riverhaven's Tall Human Peddler, who sells the copper
zills) has no room on the map, so ;go2 cannot reach him; the way is a
loop of the area's street rooms, walked until a room's listing names
him. The loop is ;attune's power-walking chain (client/game/attune.py:
nearby rooms joined by plain compass moves in both directions, walked
out and back), and the listing is the parser's `room_objs` — the text
of the "room objs" component, "You also see a news stand with a
grinning imp on it, ..., a uniformed representative and a young
alchemist student." (captured 2026-09-18, Riverhaven's Town Square) —
with the room's players beside it. present() names the entry that
holds the noun, whole word, any case: "a tall human peddler" for
"peddler". Model: docs/movement.md.
"""

import re

from client.game.attune import chain, circuit

ROOMS = 8  # rooms beyond the start in the loop, out and back
LAPS = 3  # laps of the loop before giving up
_SPLIT = re.compile(r",\s+|\s+and\s+")
_ALSO_SEE = "you also see"


def parse_args(args):
    """{"noun", "rooms", "laps", "from"} from ;seek's arguments: the
    words that are not key=value options make the noun."""
    options = {"noun": "", "rooms": ROOMS, "laps": LAPS, "from": ""}
    words = []
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key in ("rooms", "laps") and value.isdigit():
            options[key] = int(value)
        elif sep and key == "from" and value:
            options["from"] = value
        else:
            words.append(str(arg))
    options["noun"] = " ".join(words).strip()
    return options


def present(noun, objs_text="", players=()):
    """The room's entry that names `noun`: a player's name from
    `players`, or the item of the listing's "You also see ..." line
    that holds it as a whole word ("a tall human peddler" for
    "peddler"), case ignored; None when nothing does."""
    noun = (noun or "").strip().lower()
    if not noun:
        return None
    pattern = re.compile(rf"\b{re.escape(noun)}\b", re.IGNORECASE)
    for name in players or ():
        if pattern.search(str(name)):
            return str(name)
    text = (objs_text or "").strip()
    if text.lower().startswith(_ALSO_SEE):
        text = text[len(_ALSO_SEE) :]
    for entry in _SPLIT.split(text.strip().rstrip(".")):
        entry = entry.strip()
        if entry and pattern.search(entry):
            return entry
    return None


def loop(db, start, rooms, avoid=()):
    """The visiting order of one lap from `start`: the street chain out
    and back, ending at the start; [] when no street leaves it."""
    path = chain(db, start, rooms, avoid=avoid)
    if len(path) < 2:
        return []
    return circuit(path)
