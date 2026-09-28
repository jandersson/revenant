"""Power walking — the model behind ;attune.

Perceiving mana (POWER, PERCEIVE, CONCENTRATE) trains Attunement, but
a room pays out once per sixty seconds (Elanthipedia: Attunement
skill, Perceive command), so most guilds walk: perceive, step to the
next room, perceive again — "power walking". Moon Mages sense lunar
mana, which is the same everywhere, so they perceive in place, and
with PERCEIVE MANA: their POWER reads the moons instead ("Yavash and
Xibar are dominant, while Katamba's influence is moderate. / Psychic
Projection and Perception spells are favored.") and teaches nothing,
while PERCEIVE MANA answers one line per book ("You reach out with
your senses and see brilliant streams of cold, white Lunar mana
available for the Enlightened Geometry book.", 8 s of roundtime) and
paid again about a minute later (captured 2026-09-28 on a Moon Mage,
#384; Elanthipedia's Attunement skill page: every 61 seconds, each
book perceived separately gains nothing more). Captured
2026-09-12 on a circle-1 Paladin: "You reach out with your weak
senses and see glowing streams of golden Holy mana radiating through
the area." with 8-9 s of roundtime; the room's first POWER took
Attunement from 4/34 to 6/34, a second POWER in the same room within
the minute gave nothing. This module builds the loop — a chain of
nearby rooms joined by plain compass moves in both directions, walked
out and back so every room comes round again after the minute — and
keeps the per-room timer. Model: docs/training.md.
"""

from client.game.mapdb import walkable

PERCEIVE_TIMER = 60  # seconds before a room pays Attunement again
COMPASS = (
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
)
PERCEIVED = "You reach out with your"  # the first words of every mana perceive
LUNAR_PERCEIVE = "perceive mana"  # a Moon Mage's perceive: all four books at once
MOON_READING = ("influence is", "spells are favored")  # a Moon Mage's POWER


def reads_moons(answer):
    """True when POWER answered with the moons — a Moon Mage, who
    trains Attunement with PERCEIVE MANA instead."""
    return any(marker in (answer or "") for marker in MOON_READING)


def plain_neighbors(db, room_id, avoid=()):
    """[(neighbor id, command)] for the rooms a plain compass move
    reaches from `room_id` and a plain compass move returns from —
    streets, not shop doors ("go forge") or climbs — avoiding `avoid`."""
    room = db.rooms.get(room_id) or {}
    found = []
    for dest, command in (room.get("wayto") or {}).items():
        try:
            dest_id = int(dest)
        except (TypeError, ValueError):
            continue
        if dest_id in avoid or dest_id not in db.rooms or not walkable(command):
            continue
        if command not in COMPASS:
            continue
        back = (db.rooms[dest_id].get("wayto") or {}).get(str(room_id))
        if back in COMPASS:
            found.append((dest_id, command))
    return found


def chain(db, start, length, avoid=()):
    """[start, r1, ..., rN] — a simple path of `length` rooms beyond the
    start along plain two-way compass moves, the first the search
    finds; shorter when the streets run out. `avoid` rooms are never
    entered."""
    best = [start]

    def extend(path):
        nonlocal best
        if len(path) - 1 >= length:
            return True
        for dest, _ in plain_neighbors(db, path[-1], avoid):
            if dest in path:
                continue
            path.append(dest)
            if len(path) > len(best):
                best = list(path)
            if extend(path):
                return True
            path.pop()
        return False

    extend([start])
    return best


def circuit(rooms):
    """The visiting order that walks a chain out and back, forever:
    [s, a, b, c] → [a, b, c, b, a, s]. A single room → [s]."""
    if len(rooms) < 2:
        return list(rooms)
    return rooms[1:] + rooms[-2::-1]


def wait_for(room, last_seen, now, timer=PERCEIVE_TIMER):
    """Seconds still to wait before `room` pays again; 0 when it does."""
    seen = last_seen.get(room)
    if seen is None:
        return 0
    return max(0.0, timer - (now - seen))
