"""The hunting bestiary: dr-scripts' hunting zones as ;hunt's grounds
(#340).

hunting_data.py is generated from dr-scripts' data/base-hunting.yaml by
tools/hunting_tables.py: every zone's map rooms, its province, its
creatures with the rank range each suits ("Rat 0-30", from the
Elanthipedia-linked comment above the zone) and each town's zones
weakest first. The map's tags were ;hunt's only way to name a ground,
and they are sparse: Riverhaven's weakest zones, heggarangi frogs
(0-26) and zombie goblins (5-35), carry none, so a circle-1 Barbarian
was sent across the river toward the Crossing's rats, then to grass
eels (25-50) that beat him in a minute (2026-09-26).

ground_rooms() resolves a profile's `hunting_ground`: an exact map tag
first — 293 of the 320 zone names that are also tags list the same
rooms and 27 differ by a room or a few, so a ground that worked keeps
its rooms — then a zone name, then the ;go2 target (a room id, a title)
as before. grounds() lists the zones whose rank range holds a rank,
nearest first by the map's travel time from a room; weapon_rank() is
the rank to ask with: the lowest of the profile's weapon skills, so a
listing never suggests what the weakest weapon cannot handle.
Qt-free, reloadable.
"""

from client.game import hunting_data

ZONES = hunting_data.ZONES
TOWNS = hunting_data.TOWNS
LISTED = 8  # zones a listing shows


def zone(name):
    """(province, rooms, creatures, notes) for a zone name, or None."""
    return ZONES.get(str(name or "").strip().lower())


def zone_range(name):
    """(low, high) over the zone's creatures, either None when unknown;
    None for a zone without a ranked creature."""
    entry = zone(name)
    if not entry or not entry[2]:
        return None
    lows = [low for _, low, _ in entry[2] if low is not None]
    highs = [high for _, _, high in entry[2] if high is not None]
    return (min(lows) if lows else None, max(highs) if highs else None)


def fits(name, rank):
    """True when the rank lies in the zone's range (an unknown end is
    open); False for a zone with no ranked creature."""
    span = zone_range(name)
    if span is None:
        return False
    low, high = span
    return (low is None or low <= rank) and (high is None or rank <= high)


def ground_rooms(db, name):
    """The map rooms of a `hunting_ground`: an exact map tag, else a
    zone name, else whatever ;go2 resolves it to (sorted)."""
    name = str(name or "").strip()
    if not name:
        return []
    tagged = db.rooms_tagged(name)
    if tagged:
        return sorted(tagged)
    entry = zone(name)
    if entry:
        return sorted(room for room in entry[1] if room in db.rooms)
    return sorted(db.resolve(name))


def weapon_rank(profile, experience):
    """The lowest rank among the profile's weapon skills ("noun:Skill"
    turns in `weapons`), from the exp window's {skill: {rank}}; None
    when the profile names no weapon skill the window knows."""
    wanted = set()
    for turn in profile.get("weapons") or []:
        parts = [part.strip() for part in str(turn).split(":")]
        if len(parts) >= 2 and parts[1]:
            wanted.add(parts[1].lower())
    ranks = [
        entry.get("rank", 0)
        for skill, entry in (experience or {}).items()
        if str(skill).lower() in wanted and isinstance(entry, dict)
    ]
    return min(ranks) if ranks else None


def grounds(db, here, rank, limit=LISTED, avoid=()):
    """[(zone, (low, high), creatures, steps)] for the zones whose range
    holds `rank`, nearest first by the map's travel time from `here`,
    the unreachable left out; at most `limit`."""
    found = []
    for name in ZONES:
        if not fits(name, rank):
            continue
        rooms = [room for room in ZONES[name][1] if room in db.rooms]
        if not rooms:
            continue
        if here in rooms:
            found.append((0.0, name, 0))
            continue
        route = db.path(here, rooms, avoid=avoid) if here is not None else None
        if route is None:
            continue
        seconds = 0.0
        previous = here
        for room, _command in route:
            seconds += _seconds(db, previous, room)
            previous = room
        found.append((seconds, name, len(route)))
    found.sort()
    return [
        (name, zone_range(name), ZONES[name][2], steps)
        for _seconds_, name, steps in found[:limit]
    ]


def _seconds(db, room, dest):
    """The map's travel time for one step (0.2 s when it names none)."""
    timeto = (db.rooms.get(room) or {}).get("timeto") or {}
    value = timeto.get(str(dest), timeto.get(dest))
    return value if isinstance(value, (int, float)) else 0.2


def describe(entry):
    """One line for a listed zone: name, range, creatures, steps."""
    name, span, creatures, steps = entry
    low, high = span
    where = "here" if steps == 0 else f"{steps} step(s)"
    who = ", ".join(creature for creature, _, _ in creatures)
    return f"{name} ({low if low is not None else '?'}-{high if high is not None else '?'}: {who}) — {where}"
