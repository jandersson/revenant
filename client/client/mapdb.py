"""The community DragonRealms map database, consumed as data.

Rooms come from the elanthia-online mapdb-backup-dr repository (the lich
map database). The JSON is cached under ~/.revenant/mapdb (override the
file with REVENANT_MAPDB) and refreshed on demand — never vendored here.

Schema notes (as observed in the real data): a list of rooms with id,
title (list of bracketed strings), wayto (dest-id -> movement command),
tags, paths. Movement commands starting with ";e" are embedded Ruby for
lich; simple fput/move sequences translate to plain game commands
(translate_embedded), the rest are unwalkable.
"""

import json
import os
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

MAPDB_URL = (
    "https://raw.githubusercontent.com/elanthia-online/"
    "mapdb-backup-dr/main/map_files/mapdb.json"
)


def mapdb_path() -> Path:
    return Path(
        os.environ.get("REVENANT_MAPDB", "~/.revenant/mapdb/mapdb.json")
    ).expanduser()


def local_mapdb_path() -> Path:
    """Personal room data the community map lacks (event areas, private
    zones) — same room schema, merged into every load. Never leaves the
    machine."""
    return Path(
        os.environ.get("REVENANT_MAPDB_LOCAL", "~/.revenant/mapdb/local.json")
    ).expanduser()


def download(url=MAPDB_URL, destination=None) -> Path:
    destination = destination or mapdb_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:
        data = response.read()
    json.loads(data)  # refuse to cache anything that isn't JSON
    destination.write_bytes(data)
    return destination


def normalize_title(title: str) -> str:
    return title.strip().strip("[]").strip().lower()


# One statement of a simple embedded-Ruby edge: fput/move with a string
# literal (lich style, parens optional), or a bare waitrt?.
_SIMPLE_STATEMENT = re.compile(
    r"^(?:(?:fput|move)\s*\(?\s*(['\"])(?P<literal>.*?)\1\s*\)?|waitrt\??)$"
)


@lru_cache(maxsize=4096)
def translate_embedded(command):
    """Game commands for a simple embedded-Ruby edge, or None.

    The community map writes scripted edges for lich (;e fput 'go
    gate'; waitrt?; move 'climb wall'). Sequences of fput/move string
    literals translate directly to game commands — 754 of the map's
    1087 scripted edges at last count. waitrt? drops out because the
    walker waits out roundtime around every command anyway. Anything
    with logic (start_script, UserVars, waits, conditionals) stays
    untranslatable."""
    if not isinstance(command, str) or not command.startswith(";e"):
        return None
    commands = []
    for statement in command[2:].split(";"):
        statement = statement.strip()
        if not statement:
            continue
        match = _SIMPLE_STATEMENT.match(statement)
        if not match:
            return None
        if match.group("literal") is not None:
            commands.append(match.group("literal"))
    return commands or None


def walkable(command) -> bool:
    if not isinstance(command, str):
        return False
    if command.startswith(";e"):
        return translate_embedded(command) is not None
    return True


class MapDB:
    def __init__(self, rooms):
        self.rooms = {int(room["id"]): room for room in rooms}
        self._by_title = {}
        self._by_uid = {}
        for room in rooms:
            for title in room.get("title") or []:
                self._by_title.setdefault(normalize_title(title), []).append(
                    int(room["id"])
                )
            for uid in room.get("uid") or []:
                self._by_uid[int(uid)] = int(room["id"])

    @classmethod
    def load(cls, path=None):
        path = path or mapdb_path()
        if not path.is_file():
            download(destination=path)
        with open(path) as stream:
            rooms = json.load(stream)
        local = local_mapdb_path()
        if local.is_file():
            with open(local) as stream:
                rooms = rooms + json.load(stream)
        return cls(rooms)

    def rooms_titled(self, title):
        return list(self._by_title.get(normalize_title(title), []))

    def room_by_uid(self, uid):
        """The map room id for a game <nav rm> uid, or None — exact,
        unlike titles, which collide (roads repeat the same title)."""
        return self._by_uid.get(uid)

    def rooms_tagged(self, tag):
        tag = tag.lower()
        return [
            room_id
            for room_id, room in self.rooms.items()
            if any(t.lower() == tag for t in room.get("tags") or [])
        ]

    def resolve(self, query):
        """Room ids matching a query: exact id, tag, or title substring."""
        if query.isdigit() and int(query) in self.rooms:
            return [int(query)]
        tagged = self.rooms_tagged(query)
        if tagged:
            return tagged
        needle = query.lower()
        return [
            room_id
            for room_id, room in self.rooms.items()
            if any(
                needle in normalize_title(title) for title in room.get("title") or []
            )
        ]

    def path(self, start, goals):
        """Breadth-first shortest path from start to the nearest goal.

        Returns a list of (room_id, command) steps ([] if already there),
        or None when every route needs an unwalkable (scripted) edge."""
        goals = set(goals)
        if start in goals:
            return []
        seen = {start}
        frontier = [(start, [])]
        while frontier:
            next_frontier = []
            for room_id, steps in frontier:
                for dest, command in (self.rooms[room_id].get("wayto") or {}).items():
                    if not str(dest).isdigit():
                        continue
                    dest = int(dest)
                    if dest in seen or dest not in self.rooms or not walkable(command):
                        continue
                    route = steps + [(dest, command)]
                    if dest in goals:
                        return route
                    seen.add(dest)
                    next_frontier.append((dest, route))
            frontier = next_frontier
        return None
