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

import networkx as nx

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


# The travel cost assumed for an edge whose timeto is missing or
# non-numeric (some carry embedded-Ruby conditionals): the community
# db's modal value — an ordinary one-command step.
DEFAULT_STEP_SECONDS = 0.2


def edge_seconds(room, dest) -> float:
    """The travel time the map claims for one wayto edge, in seconds."""
    value = (room.get("timeto") or {}).get(dest)
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return DEFAULT_STEP_SECONDS


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
        self._graph = None
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

    @property
    def graph(self):
        """The walkable map as a networkx DiGraph: nodes are room ids,
        edges carry the movement command and its travel time in seconds
        (the map's timeto). Only walkable edges make the graph — the
        translatable ``;e`` edges included, which matters: whole areas
        (the Segoltha strand among them) hang off simple scripted
        edges, and a graph that drops all ``;e`` partitions them away
        (#79). Built once, on first use."""
        if self._graph is None:
            graph = nx.DiGraph()
            graph.add_nodes_from(self.rooms)
            for room_id, room in self.rooms.items():
                for dest, command in (room.get("wayto") or {}).items():
                    if not str(dest).isdigit():
                        continue
                    dest = int(dest)
                    if dest not in self.rooms or not walkable(command):
                        continue
                    graph.add_edge(
                        room_id,
                        dest,
                        command=command,
                        seconds=edge_seconds(room, str(dest)),
                    )
            self._graph = graph
        return self._graph

    def path(self, start, goals):
        """Fastest walkable path from start to the nearest goal —
        weighted by the map's timeto travel times, so a route optimizes
        minutes, not hop count (a 30s swim loses to three 0.2s steps).

        Returns a list of (room_id, command) steps ([] if already there),
        or None when every route needs an unwalkable (scripted) edge."""
        goals = set(goals)
        if start in goals:
            return []
        if start not in self.rooms:
            raise KeyError(start)
        seconds, routes = nx.single_source_dijkstra(self.graph, start, weight="seconds")
        reachable = [goal for goal in goals if goal in routes]
        if not reachable:
            return None
        nearest = min(reachable, key=lambda goal: (seconds[goal], goal))
        route = routes[nearest]
        return [
            (dest, self.graph.edges[here, dest]["command"])
            for here, dest in zip(route, route[1:])
        ]
