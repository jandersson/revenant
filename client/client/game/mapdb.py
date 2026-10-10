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

MapDB.load() parses the 13 MB file once a process and hands every
caller the same map until the file or the local overlay changes on
disk (#407): ;remedies re-read it for every room of a building on
every lap, and each script start parsed its own copy. An edge an
instance records is in it already and keeps the instance.
"""

import json
import os
import re
import threading
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
# The Riverhaven–Throne City barge (#506) is bescort's haven_throne route,
# written in the `if` form on both docks (Salt Yard, Barge Dock 452 ↔
# Stone Docks, Covered Shore 3084); walker.ride_barge boards by name.
# The sea mammoths (#515) are bescort's mammoth route: Fang Cove, Dock
# 8301 ↔ Ratha's Shore Walk, Rocky Path 11130 and Acenamacra Pier 2239;
# with a Premium character's meeting portal into Fang Cove they are the
# way from the Crossing to Ratha (walker.ride_mammoth).
RIDES = {
    "faldesu": "ferry",
    "ferry": "ferry",
    "gondola": "gondola",
    "haven_throne": "barge",
    "mammoth": "mammoth",
}
IF_FORM_RIDES = frozenset({"gondola", "ferry", "haven_throne"})
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
# Fang Cove's EXIT portal returns a character to the town portal they
# came in by: the map gates each of its 13 `go portal` edges on the town
# lich remembers in UserVars.premiumPortal (#289).
_ATOM_PORTAL = re.compile(r"^UserVars\.premiumPortal\s*==\s*'(?P<town>[^']+)'$")
# The 13 town meeting portals into Fang Cove open to a Premium account:
# lich asks the login's subscription or the player's UserVars.premium;
# here the profile's `premium` says so (the usher's "nods at you and
# waves you through the portal", Cecil, 2026-10-04).
_ATOM_PREMIUM = re.compile(
    r"^Account\.subscription\s*==\s*'PREMIUM'\s*\|\|\s*UserVars\.premium"
    r"\s*\|\|\s*\['DRF',\s*'DRX'\]\.include\?\(XMLData\.game\)$"
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
    `circle` the least circle; `portal` the town a Fang Cove exit
    returns to; `premium` a Premium account (a meeting portal); `needs`
    names a condition the walker cannot judge, and such a gate never
    opens."""

    seconds: float = DEFAULT_STEP_SECONDS
    skill: str | None = None
    ranks: int = 0
    guild: str | None = None
    circle: int = 0
    needs: str = ""
    portal: str = ""
    premium: bool = False

    def met(self, ranks=None, guild=None, circle=None, premium=False) -> bool:
        """True when this character passes: `ranks` is {skill: rank}
        (the exp window's), `guild` and `circle` None when unknown —
        and unknown never passes a gate that asks for them. A `portal`
        gate always passes: the game lands the character in the town
        they entered Fang Cove from, and a walk that lands elsewhere
        than planned plans again from there (#232, #289). A `premium`
        gate passes for a Premium account only."""
        if self.needs:
            return False
        if self.premium and not premium:
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
        if self.portal:
            parts.append(f"entered Fang Cove from {self.portal}")
        if self.premium:
            parts.append("Premium (the profile's premium)")
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
        elif portal := _ATOM_PORTAL.match(atom):
            fields["portal"] = portal.group("town")
        elif _ATOM_PREMIUM.match(atom):
            fields["premium"] = True
        else:
            return Gate(
                seconds=seconds, needs=f"a condition the walker cannot judge ({atom})"
            )
    return Gate(**fields)


# One statement of a simple embedded-Ruby edge: fput/move with a string
# literal (lich style, parens optional), a bare waitrt?, or a waitfor
# with a literal — the Crossing temple's stairs into the Eyes of the
# Thirteen are `fput 'go stair'; waitfor 'Obvious paths:'` (2026-09-20),
# and the walker waits for the room's arrival on its own.
_SIMPLE_STATEMENT = re.compile(
    r"^(?:(?:fput|move)\s*\(?\s*(['\"])(?P<literal>.*?)\1\s*\)?"
    r"|waitrt\??"
    r"|waitfor\s*\(?\s*(['\"]).*?\3\s*\)?)$"
)
# Lich's note of the town a Fang Cove portal was entered from (#289):
# bookkeeping for its own go2, nothing sent to the game.
_BOOKKEEPING = re.compile(r"^UserVars\.premiumPortal\s*=\s*(?:nil|'[^']*'|\"[^\"]*\")$")
_ENTRY_TOWN = re.compile(r"UserVars\.premiumPortal\s*=\s*'(?P<town>[^']+)'")


def portal_town_of(command):
    """The town a meeting-portal edge enters Fang Cove from ("Crossing"),
    as lich notes it; None for any other edge. The game keeps that town:
    the EXIT portal returns you there, a mammoth ride later included
    (2026-10-10, #515)."""
    match = _ENTRY_TOWN.search(command) if isinstance(command, str) else None
    return match.group("town") if match else None


@lru_cache(maxsize=4096)
def translate_embedded(command):
    """Game commands for a simple embedded-Ruby edge, or None.

    The community map writes scripted edges for lich (;e fput 'go
    gate'; waitrt?; move 'climb wall'). Sequences of fput/move string
    literals translate directly to game commands — 754 of the map's
    1087 scripted edges at last count. waitrt? drops out because the
    walker waits out roundtime around every command anyway, and a
    waitfor with a literal AFTER the last command likewise: the walker
    waits for the arrival itself (the temple stairs' "waitfor 'Obvious
    paths:'"). A waitfor before a command is a real wait (a ferry
    arriving) the walker does not do, so that edge stays untranslated.
    Anything
    with logic (start_script, UserVars, waits, conditionals) stays
    untranslatable, bar lich's note of the Fang Cove portal town
    (`UserVars.premiumPortal = ...`), which sends nothing (#289)."""
    if not isinstance(command, str) or not command.startswith(";e"):
        return None
    commands = []
    waited = False  # a waitfor seen since the last command
    for statement in command[2:].split(";"):
        statement = statement.strip()
        if not statement or _BOOKKEEPING.match(statement):
            continue
        match = _SIMPLE_STATEMENT.match(statement)
        if not match:
            return None
        if match.group("literal") is not None:
            if waited:
                # A waitfor BEFORE a command is a real wait — the ferry
                # arriving — that the walker does not do: untranslatable.
                return None
            commands.append(match.group("literal"))
        elif statement.startswith("waitfor"):
            waited = True
    return commands or None


# Verbs an edge sends after its move, in the room it lands in: the
# poplar over the Northwall Trail's river leaves you lying (`fput 'go
# poplar'; waitrt?; fput 'stand'`), the heavy barricade ends with a
# LOOK, the iron arch closes and locks the door behind you.
AFTER_MOVE_VERBS = frozenset({"stand", "look", "close", "lock"})


def split_move(commands):
    """(before, move, after) for a translated edge's commands: `after`
    are the trailing commands sent in the room the move lands in
    (AFTER_MOVE_VERBS), `move` the last one before them — the command
    the walker waits on for arrival. A STAND taken for the move waited
    for a room that never came and stopped ;athletics at the poplar
    (2026-09-27)."""
    end = len(commands)
    while end > 1 and commands[end - 1].split()[0].lower() in AFTER_MOVE_VERBS:
        end -= 1
    return commands[: end - 1], commands[end - 1], commands[end:]


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


_LOADED = {}  # (map path, overlay path) -> ((map stamp, overlay stamp), MapDB)
_LOAD_LOCK = threading.Lock()


def _stamp(path):
    """(mtime in ns, size) of a file, None when there is none: what a
    cached load compares to know the file changed under it."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _restamp(db, overlay):
    """After `db` wrote the overlay itself (record_edge): the cache's
    stamp follows, so the next load keeps this instance — the edge is
    in it — instead of parsing the map again."""
    with _LOAD_LOCK:
        for key, (stamps, cached) in list(_LOADED.items()):
            if cached is db and key[1] == str(overlay):
                _LOADED[key] = ((stamps[0], _stamp(overlay)), cached)


class MapDB:
    def __init__(self, rooms):
        self.rooms = {int(room["id"]): room for room in rooms}
        self._graph = None
        # One map is shared by every script of the session (#407): the
        # graph is built, and an edge recorded, under this lock.
        self._lock = threading.RLock()
        self._by_title = {}
        self._by_uid = {}
        for room in rooms:
            for title in room.get("title") or []:
                ids = self._by_title.setdefault(normalize_title(title), [])
                if int(room["id"]) not in ids:  # a local copy of a room (#229)
                    ids.append(int(room["id"]))
            for uid in room.get("uid") or []:
                self._by_uid[int(uid)] = int(room["id"])

    @classmethod
    def load(cls, path=None):
        """The map at `path` (mapdb_path() by default) with the local
        overlay merged in — parsed once: the same instance comes back
        until either file changes on disk (a ;go2 update, a ;survey
        in another process), judged by mtime and size (#407). A map
        file that is not there is downloaded first."""
        path = path or mapdb_path()
        local = local_mapdb_path()
        with _LOAD_LOCK:
            if not path.is_file():
                download(destination=path)
            key = (str(path), str(local))
            stamps = (_stamp(path), _stamp(local))
            cached = _LOADED.get(key)
            if cached is not None and cached[0] == stamps:
                return cached[1]
            with open(path) as stream:
                rooms = json.load(stream)
            if local.is_file():
                with open(local) as stream:
                    rooms = rooms + json.load(stream)
            db = cls(rooms)
            _LOADED[key] = (stamps, db)
            return db

    def record_edge(self, room_id, dest, command, path=None):
        """Remember a way the game showed and the map lacks or has wrong
        — the compass exit out of a room the map lists without exits
        (#229), the room an edge landed in when the map said another
        (#232) — in this map at once and in the local overlay
        (`local_mapdb_path()`) as a full copy of the room with the edge
        added (and the map's own entry under the same command dropped),
        which a later load's merge takes over the community room (the
        last copy of an id wins). The overlay's path."""
        path = path or local_mapdb_path()
        with self._lock:
            room = self.rooms[room_id]
            # One command leads one way: an entry the community map had
            # under the same command (Glaysker Lane's `go shop` said the
            # Shrine of Ushnish, #232) is the one this edge corrects.
            wayto = {
                other: known
                for other, known in (room.get("wayto") or {}).items()
                if known != command
            }
            wayto[str(dest)] = command
            room["wayto"] = wayto
            timeto = room.get("timeto")
            if isinstance(timeto, dict):
                room["timeto"] = {k: v for k, v in timeto.items() if k in wayto}
            self._graph = None
            overlay = []
            if path.is_file():
                with open(path) as stream:
                    overlay = json.load(stream)
            overlay = [
                entry for entry in overlay if int(entry.get("id", -1)) != room_id
            ]
            overlay.append(room)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(overlay, indent=1))
        _restamp(self, path)
        return path

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
            with self._lock:
                if self._graph is None:
                    self._graph = self._build_graph()
        return self._graph

    def _build_graph(self):
        """The walkable DiGraph, built once per map (the `graph` property).
        Twins (#137) are resolved as there, gates (#214) priced as there."""
        graph = nx.DiGraph()
        graph.add_nodes_from(self.rooms)
        for room_id, room in self.rooms.items():
            edges = [
                (int(dest), command)
                for dest, command in (room.get("wayto") or {}).items()
                if str(dest).isdigit() and int(dest) in self.rooms and walkable(command)
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
        return graph

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
        premium=False,
        portal_town=None,
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
        unknown guild or circle passes no gate that asks for one;
        `premium` opens the meeting portals into Fang Cove, and
        `portal_town` (the town they were entered from, when known)
        names the one exit portal that leads anywhere new.
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
        inside = {}  # a Fang Cove exit portal's room -> the walk starts beside it
        if avoid or closed or gates:

            def weight(here, dest, data):
                if (here, dest) in closed:
                    return None  # not an edge, for this walk
                gate = data.get("gate")
                if (
                    gates
                    and gate is not None
                    and not gate.met(ranks, guild, circle, premium)
                ):
                    return None  # the map prices it nil for this character
                if gates and gate is not None and gate.portal:
                    # Fang Cove's exit returns you to the town you came in
                    # by: a walk from outside that portals in and out again
                    # lands where it began (#515), so only a walk that
                    # starts in Fang Cove takes one, and only the exit to
                    # that town when it is known.
                    if here not in inside:
                        inside[here] = start in self._fang_cove(here)
                    if not inside[here]:
                        return None
                    if portal_town and gate.portal != portal_town:
                        return None
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

    def _fang_cove(self, portal_room):
        """The rooms walkable from Fang Cove's exit-portal room without a
        gated edge or a ride: Fang Cove itself, whose other ways out are
        the meeting portals and the mammoths."""
        graph = self.graph

        def inner(here, dest):
            data = graph.edges[here, dest]
            return data.get("gate") is None and not ride_of(data["command"])

        view = nx.subgraph_view(graph, filter_edge=inner)
        return nx.descendants(view, portal_room) | {portal_room}

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
