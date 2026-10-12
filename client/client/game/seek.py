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
# A town's streets where its wanderers walk, in dr-scripts' order
# (data/base-town.yaml wandering_npcs; its find.lic walks them until the
# room lists the NPC, "find crossing beggar"): ;seek town=<town> laps
# these instead of the loop round the start. An old blind beggar in The
# Crossing is a task's recipient (Ioun, 2026-10-11, #511).
TOWN_ROUTES = {
    "crossing": (
        732,
        741,
        739,
        734,
        733,
        753,
        792,
        791,
        785,
        783,
        779,
        775,
        776,
        777,
        778,
        738,
        737,
        736,
        735,
        784,
        782,
        780,
        774,
        773,
        771,
        770,
        769,
        781,
        810,
        819,
        822,
        7902,
        809,
        808,
        807,
        811,
        812,
        813,
        804,
        805,
        806,
        803,
        802,
        814,
        815,
        800,
        799,
        801,
        817,
        816,
        761,
        797,
        762,
        763,
        798,
        764,
        765,
        766,
        760,
        759,
        758,
        757,
        756,
        748,
        747,
        746,
        729,
        728,
        730,
        731,
        754,
        751,
        750,
        749,
        752,
        793,
        794,
        954,
        796,
        795,
        767,
        768,
        786,
        787,
        788,
        789,
    ),
    "dirge": (
        1307,
        1308,
        1311,
        1315,
        1316,
        1309,
        1310,
        12109,
        1317,
        1318,
        1321,
        1314,
        1313,
        1319,
        1320,
    ),
    "shard": (
        2544,
        2550,
        2556,
        2557,
        2558,
        2559,
        2560,
        2561,
        2562,
        2522,
        19287,
        2517,
        2516,
        2518,
        2520,
        2521,
        2523,
        2524,
        2525,
        2526,
        2527,
        2528,
        2529,
        2536,
        2537,
        2538,
        2611,
        2503,
        2502,
        2501,
        2496,
        2497,
        2498,
        2511,
        2512,
        2513,
        2514,
        2515,
        2499,
        2500,
        2581,
        2596,
        2575,
        2573,
        2570,
        2567,
        2565,
        2566,
        2564,
        2563,
        2582,
        2585,
        2586,
        2589,
        2597,
        2598,
        2599,
        2600,
        2601,
        2612,
        2607,
        2549,
        2548,
        2547,
        2545,
        2621,
        2544,
        2613,
        2608,
        2617,
        2633,
        2632,
        2631,
        2504,
        2505,
        2506,
        2507,
        2508,
        2509,
        2574,
        2540,
        2539,
        2541,
        2543,
        2603,
        2602,
        2583,
        2584,
        2592,
        2593,
        2594,
        2595,
        2567,
        2571,
        2572,
        2569,
        2568,
        2565,
        2566,
        2564,
        2563,
    ),
}


def parse_args(args):
    """{"noun", "rooms", "laps", "from", "town", "area"} from ;seek's arguments: the
    words that are not key=value options make the noun."""
    options = {
        "noun": "",
        "rooms": ROOMS,
        "laps": LAPS,
        "from": "",
        "town": "",
        "area": "",
    }
    words = []
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key in ("rooms", "laps") and value.isdigit():
            options[key] = int(value)
        elif sep and key in ("from", "town", "area") and value:
            options[key] = value
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


def town_route(town, here=None):
    """One lap of the town's wanderers' streets (TOWN_ROUTES), begun at
    `here` when it is on them, as dr-scripts' find does, else at the
    first; () for a town without one. "The Crossing" is "crossing"."""
    name = str(town or "").strip().lower().removeprefix("the ").strip()
    rooms = TOWN_ROUTES.get(name, ())
    if here in rooms:
        index = rooms.index(here)
        return rooms[index:] + rooms[:index]
    return rooms


def area_route(db, area, here=None):
    """One lap of the rooms whose title holds `area`, in map order (a
    road's rooms run in sequence), begun at `here` when it is one of
    them: a recipient named only by where he stands ("Researcher Trelmik
    in Reshalia Trade Road", the barkeep's task, 2026-10-11); () when no
    title holds it. A room no mapped way leads into is left out: three
    of that road's 71 (7144, 12395, 51461) cost a "no walkable path"
    every lap (#528)."""
    from client.game.mapdb import normalize_title

    text = normalize_title(str(area or "")).strip()
    if not text:
        return ()
    rooms = tuple(
        sorted(
            room
            for room, entry in db.rooms.items()
            if any(text in normalize_title(title) for title in entry.get("title") or ())
            and db.graph.in_degree(room)
        )
    )
    if here in rooms:
        index = rooms.index(here)
        return rooms[index:] + rooms[:index]
    return rooms


def loop(db, start, rooms, avoid=()):
    """The visiting order of one lap from `start`: the street chain out
    and back, ending at the start; [] when no street leaves it."""
    path = chain(db, start, rooms, avoid=avoid)
    if len(path) < 2:
        return []
    return circuit(path)
