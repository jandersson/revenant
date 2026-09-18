"""The community DragonRealms map database, consumed as data.

Rooms come from the elanthia-online mapdb-backup-dr repository (the lich
map database). The JSON is cached under ~/.revenant/mapdb (override the
file with REVENANT_MAPDB) and refreshed on demand — never vendored here.

Schema notes (as observed in the real data): a list of rooms with id,
title (list of bracketed strings), wayto (dest-id -> movement command),
tags, paths. Movement commands starting with ";e" are embedded Ruby for
lich; simple fput/move sequences translate to plain game commands
(translate_embedded), a bescort route the walker knows how to ride is
a ride edge (ride_of: the Faldesu ferry, #205), the rest are unwalkable.
A timeto that is Ruby is a gate (gate_of, #214): the map prices an
edge at nil — no edge — unless the character has the ranks, guild or
circle the expression names, and the router honors that against the
exp window's ranks instead of pricing every such edge at a free step.
"""

import json
import os
import re
import urllib.request
from dataclasses import dataclass
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
# A bescort route the walker rides itself (#205): the map writes the
# crossing as start_script('bescort', ['faldesu', ...]) for lich, and
# the walker boards the Faldesu ferry between North Road, Ferry and
# Riverhaven, Ferry Dock on its own (walker.ride_ferry). Any other
# bescort route stays unwalkable. For the ferry only an edge that IS
# the call rides: the Marsh's Stone Road ↔ Riverhaven's Stone Bridge
# edges name the same route inside an `if Script.exists?('bescort')`
# with a swim as the else, and there is no dock there to wait at
# (2026-09-18). The Obsidian Pass gondola (#211) is written in that
# `if` form with GO GONDOLA as the else, so that route rides from it
# too; the way under the gondola wants 550 ranks of Athletics.
# Alfren's Ferry over the Segoltha (The Crossing, Alfren's Ferry 957 ↔
# Southern Trade Route, Segoltha South Bank 1904) is bescort's 'ferry'
# route, written in the `if` form too; it is the way south to Leth
# Deriel and Shard — the map's other way, the Riverbank tunnel, goes
# through a silverfish ground to a panel the game could not find
# (2026-09-18).
RIDES = {"faldesu": "ferry", "ferry": "ferry", "gondola": "gondola"}
IF_FORM_RIDES = frozenset({"gondola", "ferry"})
RIDE_SECONDS = 300.0  # the wait and the crossing: a land route wins where one exists
_BESCORT_CALL = (
    r"start_script\s*\(\s*'bescort'\s*,\s*\[\s*'(?P<route>[a-z0-9_]+)'"
    r"(?:\s*,\s*'(?P<arg>[a-z0-9_]+)')?"
)
_BESCORT = re.compile(r"^;e\s*" + _BESCORT_CALL)
_BESCORT_IF = re.compile(
    r"^;e\s*if\s+Script\.exists\?\(\s*'bescort'\s*\)\s*;?\s*(?:then\s*)?"
    + _BESCORT_CALL
)

# What entering an avoided room costs on top of its real travel time:
# an hour dominates any honest route, so a route only crosses an
# avoided room when no clean way around exists at all.
AVOID_PENALTY_SECONDS = 3600.0


def edge_seconds(room, dest) -> float:
    """The travel time the map claims for one wayto edge, in seconds.
    A Ruby timeto is a gate (gate_of), priced by the gate itself."""
    value = (room.get("timeto") or {}).get(dest)
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    gate = gate_of(value)
    if gate is not None:
        return gate.seconds
    return DEFAULT_STEP_SECONDS


# --- Skill gates in timeto (#214) --------------------------------------------
# The community map writes some travel times as Ruby for lich to
# evaluate at routing time — `;e unless DRSkill.getmodrank('Athletics')
# >= 540 then nil else 0.2 end` on the Obsidian Pass branch — and nil
# means no edge: that is how Lich's go2 keeps a circle-5 Paladin off a
# 540-rank climb. Pricing every such edge at a plain step routed the
# walker into that climb (2026-09-18, turned back twice before #211
# closed the edge). The known shapes, from a survey of the 98 string
# timeto values (2026-09-19): `unless COND then nil else S end`, `if
# COND then S else nil end`, `if COND then nil else S end`, `(COND) ?
# S : nil` (an optional `rescue nil` after it) and `COND ? nil : S`,
# with COND `&&`-joined atoms: a skill's modified rank against a
# minimum, the guild, the circle, `Script.exists?('bescort')` (true —
# the walker is its own bescort where it rides, and elsewhere the
# wayto is unwalkable anyway), `invisible?` (false: the walker walks
# seen) and `XMLData.game == 'DRF'` (false: this is DragonRealms
# Prime). Anything else — premium portals, a Thieves' Guild password,
# citizenship, a known spell — is a condition the walker cannot judge,
# and that closes the edge: a gate is a reason to be careful, not
# optimistic.
_GATE_FORMS = (
    # (pattern, the branch that is a number is taken when COND holds?)
    (
        re.compile(
            r"^unless\s+(?P<cond>.+?)\s+then\s+nil\s+else\s+(?P<seconds>[\d.]+)\s+end$"
        ),
        True,
    ),
    (
        re.compile(
            r"^if\s+(?P<cond>.+?)\s+then\s+(?P<seconds>[\d.]+)\s+else\s+nil\s+end$"
        ),
        True,
    ),
    (
        re.compile(
            r"^if\s+(?P<cond>.+?)\s+then\s+nil\s+else\s+(?P<seconds>[\d.]+)\s+end$"
        ),
        False,
    ),
    (
        re.compile(
            r"^(?P<cond>.+?)\s*\?\s*(?P<seconds>[\d.]+)\s*:\s*nil(?:\s+rescue\s+nil)?$"
        ),
        True,
    ),
    (
        re.compile(
            r"^(?P<cond>.+?)\s*\?\s*nil\s*:\s*(?P<seconds>[\d.]+)(?:\s+rescue\s+nil)?$"
        ),
        False,
    ),
)
_ATOM_SKILL = re.compile(
    r"^DRSkill\.getmodrank\(\s*'(?P<skill>[A-Za-z ]+)'\s*\)\s*(?P<op>>=|>)\s*(?P<ranks>\d+)$"
)
_ATOM_GUILD = re.compile(r"^DRStats\.guild\s*==\s*'(?P<guild>[A-Za-z ]+)'$")
_ATOM_CIRCLE = re.compile(
    r"^(?:Scripting::)?DRStats\.circle\s*(?P<op>>=|>)\s*(?P<circle>\d+)$"
)
# Atoms whose truth is fixed for this client.
_STATIC_ATOMS = {
    "Script.exists?('bescort')": True,
    "invisible?": False,
    "XMLData.game == 'DRF'": False,
}


@dataclass(frozen=True)
class Gate:
    """What a Ruby timeto asks of the character before the edge exists.

    `seconds` is the edge's price once open. `skill`/`ranks` is the
    modified rank the skill must reach (0 ranks for a skill the exp
    window does not list), `guild` the guild the character must be in,
    `circle` the least circle; `needs` names a condition the walker
    cannot judge, and such a gate never opens."""

    seconds: float = DEFAULT_STEP_SECONDS
    skill: str | None = None
    ranks: int = 0
    guild: str | None = None
    circle: int = 0
    needs: str = ""

    def met(self, ranks=None, guild=None, circle=None) -> bool:
        """True when this character passes: `ranks` is {skill: rank}
        (the exp window's), `guild` and `circle` None when unknown —
        and unknown never passes a gate that asks for them."""
        if self.needs:
            return False
        if self.skill and (ranks or {}).get(self.skill, 0) < self.ranks:
            return False
        if self.guild and guild != self.guild:
            return False
        if self.circle and (circle is None or circle < self.circle):
            return False
        return True

    def describe(self) -> str:
        """The ask in words: "Athletics 540", "Thief circle 6", or the
        condition the walker cannot judge."""
        if self.needs:
            return self.needs
        parts = []
        if self.guild:
            parts.append(self.guild)
        if self.circle:
            parts.append(f"circle {self.circle}")
        if self.skill:
            parts.append(f"{self.skill} {self.ranks}")
        return " ".join(parts) or "open"


def _split_atoms(cond):
    cond = cond.strip()
    while cond.startswith("(") and cond.endswith(")"):
        cond = cond[1:-1].strip()
    return [atom.strip() for atom in cond.split("&&")]


@lru_cache(maxsize=4096)
def gate_of(timeto):
    """The Gate a Ruby timeto expresses, or None for a plain (numeric,
    missing) travel time (#214). An expression outside the known
    shapes is a closed gate that says so in `needs`."""
    if not isinstance(timeto, str):
        return None
    expr = timeto.strip()
    if expr.startswith(";e"):
        expr = expr[2:].strip()
    if not expr:
        return None
    for pattern, open_when_true in _GATE_FORMS:
        match = pattern.match(expr)
        if match:
            break
    else:
        return Gate(needs=f"a condition the walker cannot judge ({expr})")
    seconds = float(match.group("seconds")) or DEFAULT_STEP_SECONDS
    fields = {"seconds": seconds}
    for atom in _split_atoms(match.group("cond")):
        if atom in _STATIC_ATOMS:
            if _STATIC_ATOMS[atom] != open_when_true:
                return Gate(seconds=seconds, needs=f"never here ({atom})")
            continue
        if not open_when_true:
            # A dynamic requirement under negation ("open unless the
            # character has ...") is nothing the map writes; refuse
            # to guess at it.
            return Gate(
                seconds=seconds, needs=f"a condition the walker cannot judge ({expr})"
            )
        if skill := _ATOM_SKILL.match(atom):
            ranks = int(skill.group("ranks")) + (skill.group("op") == ">")
            fields.update(skill=skill.group("skill"), ranks=ranks)
        elif guild := _ATOM_GUILD.match(atom):
            fields["guild"] = guild.group("guild")
        elif circle := _ATOM_CIRCLE.match(atom):
            fields["circle"] = int(circle.group("circle")) + (circle.group("op") == ">")
        else:
            return Gate(
                seconds=seconds, needs=f"a condition the walker cannot judge ({atom})"
            )
    return Gate(**fields)


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


def _ride_match(command):
    if not isinstance(command, str) or not command.startswith(";e"):
        return None
    match = _BESCORT.search(command)
    if match and match.group("route") in RIDES:
        return match
    match = _BESCORT_IF.search(command)
    if match and match.group("route") in IF_FORM_RIDES:
        return match
    return None


def ride_of(command):
    """The bescort route a scripted edge names when the walker rides it
    ("faldesu", "gondola"), else None (#205, #211)."""
    match = _ride_match(command)
    return match.group("route") if match else None


def ride_args(command):
    """The route's argument on a ride edge — the ferry's bank ("haven",
    "crossing"), the gondola's direction ("north", "south") — or ""."""
    match = _ride_match(command)
    return (match.group("arg") or "") if match else ""


def walkable(command) -> bool:
    if not isinstance(command, str):
        return False
    if command.startswith(";e"):
        return translate_embedded(command) is not None or ride_of(command) is not None
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

    def same_place(self, a, b):
        """True when two map ids describe one physical room.

        The community map holds twins — captured 2026-09-04 (#137):
        670 and 13100 are one Middens room, same title, same three
        exits, only 13100 carrying the game's uid — so a walk planned
        through one twin arrives, by uid, in the other. Twins share a
        uid, or share a title and an identical set of exits."""
        if a == b:
            return True
        room_a, room_b = self.rooms.get(a), self.rooms.get(b)
        if room_a is None or room_b is None:
            return False
        uids_a = {int(uid) for uid in room_a.get("uid") or []}
        uids_b = {int(uid) for uid in room_b.get("uid") or []}
        if uids_a & uids_b:
            return True
        titles_a = {normalize_title(t) for t in room_a.get("title") or []}
        titles_b = {normalize_title(t) for t in room_b.get("title") or []}
        exits_a = room_a.get("wayto") or {}
        # No exits is no evidence: two dead ends sharing a title are
        # just two dead ends.
        return (
            bool(titles_a & titles_b)
            and bool(exits_a)
            and exits_a == (room_b.get("wayto") or {})
        )

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
                edges = [
                    (int(dest), command)
                    for dest, command in (room.get("wayto") or {}).items()
                    if str(dest).isdigit()
                    and int(dest) in self.rooms
                    and walkable(command)
                ]
                for dest, command in edges:
                    # A room that names both twins of one place (684
                    # → 670 and 13100, both "south") plans through the
                    # one the game will report: the uid-bearing twin
                    # (#137). The uid-less edge stays out of the graph.
                    if not self.rooms[dest].get("uid") and any(
                        other != dest
                        and other_command == command
                        and self.rooms[other].get("uid")
                        and self.same_place(dest, other)
                        for other, other_command in edges
                    ):
                        continue
                    graph.add_edge(
                        room_id,
                        dest,
                        command=command,
                        seconds=RIDE_SECONDS
                        if ride_of(command)
                        else edge_seconds(room, str(dest)),
                        # The gate a Ruby timeto puts on the edge
                        # (#214), judged per walk against the character.
                        gate=gate_of((room.get("timeto") or {}).get(str(dest))),
                    )
            self._graph = graph
        return self._graph

    def path(
        self,
        start,
        goals,
        avoid=(),
        closed=(),
        ranks=None,
        guild=None,
        circle=None,
        gates=True,
    ):
        """Fastest walkable path from start to the nearest goal —
        weighted by the map's timeto travel times, so a route optimizes
        minutes, not hop count (a 30s swim loses to three 0.2s steps).

        Rooms in `avoid` are detoured around whenever a clean route
        exists; when none does, the route crosses them anyway (the
        caller can warn — walker.walk does). Edges in `closed` — (room,
        dest) pairs the game refused this run, "not experienced enough
        to go there" (#209) — are never taken. Nor is a gated edge
        (#214) the character does not pass: `ranks` is the exp window's
        {skill: rank}, `guild` and `circle` the character's when known
        — a skill the window does not list counts as rank 0, and an
        unknown guild or circle passes no gate that asks for one.
        `gates=False` prices gated edges as if every gate were open —
        for a caller that wants to say which gate shut the only way.

        Returns a list of (room_id, command) steps ([] if already there),
        or None when every route needs an unwalkable (scripted) edge."""
        goals = set(goals)
        if start in goals:
            return []
        if start not in self.rooms:
            raise KeyError(start)
        avoid = frozenset(avoid)
        closed = frozenset(closed)
        weight = "seconds"
        if avoid or closed or gates:

            def weight(here, dest, data):
                if (here, dest) in closed:
                    return None  # not an edge, for this walk
                gate = data.get("gate")
                if gates and gate is not None and not gate.met(ranks, guild, circle):
                    return None  # the map prices it nil for this character
                penalty = AVOID_PENALTY_SECONDS if dest in avoid else 0.0
                return data["seconds"] + penalty

        seconds, routes = nx.single_source_dijkstra(self.graph, start, weight=weight)
        reachable = [goal for goal in goals if goal in routes]
        if not reachable:
            return None
        nearest = min(reachable, key=lambda goal: (seconds[goal], goal))
        route = routes[nearest]
        return [
            (dest, self.graph.edges[here, dest]["command"])
            for here, dest in zip(route, route[1:])
        ]

    def route_gates(self, start, route):
        """(here, dest, Gate) for every gated edge of a route (a list
        of (dest, command) steps from `start`) — the walker's report
        when the only way is gated (#214)."""
        here = start
        found = []
        for dest, _ in route:
            gate = self.graph.edges[here, dest].get("gate")
            if gate is not None:
                found.append((here, dest, gate))
            here = dest
        return found
