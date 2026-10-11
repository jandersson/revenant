"""Astral travel between Grazhir shards — the model behind ;astral (#516).

A Moon Mage at a named shard opens a Moongate into the Astral Plane
through it, follows PERCEIVE to the centre of the microcosm, walks the
ring of pillars to the one the destination shard hangs off, FOCUSes
that shard to enter its conduit, follows PERCEIVE to the conduit's end
and opens a Moongate out (Elanthipedia: Astral Travel, Astral Plane,
Grazhir). The wordings were captured on the first trip, 2026-10-10,
Vellano (Fang Cove) to Besoge (Mer'Kresh): every line on the main
story stream.
"""

import json
import re

# The pillars as a ring joined east-west, the microcosm map's A to H
# (Elanthipedia: Microcosm map): east goes A -> B, and H wraps to A.
# Captured: from the Pillar of Unity (D), `west` reached the Pillar of
# Secrets (C).
RING = (
    "Nightmares",
    "Tradition",
    "Secrets",
    "Unity",
    "Shrew",
    "Heavens",
    "Introspection",
    "Fortune",
)
# Each named shard's pillar and town (Elanthipedia: Astral Plane).
SHARDS = {
    "rolagi": ("Nightmares", "the Crossing"),
    "tabelrem": ("Nightmares", "Muspar'i"),
    "auilusi": ("Tradition", "Aesry"),
    "dor'na'torna": ("Tradition", "the Arid Steppes"),
    "marendin": ("Secrets", "Shard"),
    "besoge": ("Secrets", "Mer'Kresh"),
    "vellano": ("Unity", "Fang Cove"),
    "emalerje": ("Shrew", "Lesser Fist"),
    "aevargwem": ("Shrew", "Asketi's Mount"),
    "asharshpar'i": ("Heavens", "Leth Deriel"),
    "tamigen": ("Heavens", "Raven's Point"),
    "dinegavren": ("Introspection", "Therenborough"),
    "taniendar": ("Introspection", "Riverhaven"),
    "mintais": ("Fortune", "Throne City"),
    "erekinzil": ("Fortune", "Taisgath"),
}
# Each shard's map room (dr-scripts' bescort.lic room_id_to_shard):
# Emalerje was lost with the Crystal Hand Fortress.
SHARD_ROOMS = {
    "asharshpar'i": 9999,
    "rolagi": 607,
    "marendin": 2493,
    "taniendar": 306,
    "mintais": 3002,
    "dinegavren": 3105,
    "tamigen": 4542,
    "erekinzil": 5050,
    "auilusi": 6867,
    "vellano": 8302,
    "dor'na'torna": 3777,
    "tabelrem": 287,
    "besoge": 6991,
    "aevargwem": 51786,
}
# At the 100th circle Moongate opens on Grazhir itself, from any room, no
# FOCUS (Elanthipedia: Moongate; bescort casts it so above circle 99).
# Cast in Ioun's Pawn, 2026-10-11, it took the nearest shard: "You attempt
# to open an astral conduit here, using the energies of the shard
# Taniendar." onto that conduit's end, then the usual way to the centre.
GRAZHIR_CIRCLE = 100

# STUDY <shard> at it (Aevargwem, 2026-10-11): "You recognize the magical
# pattern behind the shard Aevargwem, but will need to study it further
# to learn more." and "...the shard's pattern..." until "You commit the
# pattern of the shard Aevargwem to memory."; a shard already known
# answers "You intently study the shard Aevargwem, reaffirming its
# pattern in your memory."
STUDYING = "pattern"
LEARNED = ("commit the pattern", "reaffirming its pattern")
# RECALL HEAVENS GRAZHIR (2 s roundtime, 2026-10-11): "You know the names
# of:" and one shard a line, "  Aevargwem". ;astral list keeps them on
# record, a learn and an arrival add to it, and the walker plans a crossing
# only to a shard on it: a trip to one unlearned stops at its pillar.
KNOWN_HEAD = "You know the names of:"


def known_shards(answer):
    """The shards RECALL HEAVENS GRAZHIR names, lowered; empty without
    its head line."""
    text = str(answer or "")
    if KNOWN_HEAD not in text:
        return set()
    lines = text.split(KNOWN_HEAD, 1)[1].splitlines()
    return {line.strip().lower() for line in lines if line.strip().lower() in SHARDS}


def learned_path(name):
    from client.game.training import training_dir

    return training_dir() / f"{str(name).lower()}.shards.json"


def learned(name):
    """The shards on record as learned by `name`, lowered."""
    try:
        data = json.loads(learned_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(shard) for shard in data} if isinstance(data, list) else set()


def remember(name, shards, replace=False):
    """Add `shards` to the record (or replace it: RECALL's whole list)."""
    shards = set(shards) | (set() if replace else learned(name))
    path = learned_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(shards)), encoding="utf-8")


# "You also see an obsidian pedestal with the silvery-white shard Vellano
# on it." — Asharshpar'i is "the silvery shard" (the old script's match).
_SHARD_HERE = re.compile(r"the silvery(?:-white)? shard (?P<name>[A-Z][\w']*)")
_CENTRE = re.compile(r"center of the microcosm is to the (?P<dir>\w+)")
_END = re.compile(r"end of the conduit lies (?P<dir>\w+)")
AT_END = "already at the end of the conduit"
_PILLAR = re.compile(r"Astral Plane, Pillar of (?:the )?(?P<name>[\w ]+?)\]")
IN_PLANE = "[Astral Plane,"

# FOCUS on a shard: "You recognize this as the shard Vellano and forge a
# connection to it through the magical pattern." (Roundtime: 20 sec.);
# a shard never learned answers "You do not recognize this shard" (the
# wiki's old script, not met).
CONNECTED = "forge a connection"
UNKNOWN_SHARD = "do not recognize this shard"
PREPARED = "fully prepared to cast"
# FOCUS at the destination's pillar: "You reach out into the seemingly
# infinite strands of Lunar mana and find a conduit anchored by the
# presence of Besoge." then "You move into the chaotic tides of energy."
CONDUIT_FOUND = "find a conduit anchored"
# The plane's verdict every few rooms (Elanthipedia: Astral Travel):
# "You effortlessly maintain your place among the shifting streams of
# mana." captured; the worse two are the wiki's.
STANDINGS = (
    ("effortlessly maintain", "effortless"),
    ("carefully maintain", "careful"),
    ("struggling to maintain", "struggling"),
)
# The Grey Expanse (the old script's wording) and the apparition that
# sends a mage there (Elanthipedia: Pelag ai Aldam).
LOST = ("cannot sense even a single thread of Lunar energy", "endless grey horizon")
# The verdict comes on the plane's own timer, between commands, where an
# ask's clear() would drop it: ;astral flags these lines instead.
PLANE_LINES = tuple(re.escape(n) for n, _ in STANDINGS) + tuple(map(re.escape, LOST))


def shard_here(objs_text):
    """The shard a room's listing names, lowered ("vellano"), or None."""
    match = _SHARD_HERE.search(str(objs_text or ""))
    return match.group("name").lower() if match else None


def pillar_of(title):
    """The pillar a room title names ("Secrets" from "[Astral Plane,
    Pillar of Secrets]"), or None."""
    match = _PILLAR.search(str(title or ""))
    return match.group("name").strip() if match else None


def ring_moves(here, there):
    """The east/west moves from pillar `here` to pillar `there` round the
    ring, the shorter way: ["west"] from Unity to Secrets."""
    start, goal = RING.index(here), RING.index(there)
    east = (goal - start) % len(RING)
    west = (start - goal) % len(RING)
    return ["east"] * east if east <= west else ["west"] * west


def perceived(answer):
    """(the way to the centre, the way to the conduit's end) from a
    PERCEIVE in the plane: either is None when the answer does not say;
    the end is "here" at the conduit's end."""
    text = str(answer or "")
    centre = _CENTRE.search(text)
    end = _END.search(text)
    return (
        centre.group("dir") if centre else None,
        "here" if AT_END in text else (end.group("dir") if end else None),
    )


def standing(answer):
    """The plane's verdict in an answer — "effortless", "careful",
    "struggling" — or None."""
    lowered = str(answer or "").lower()
    for needle, verdict in STANDINGS:
        if needle in lowered:
            return verdict
    return None


def lost(answer):
    """True when the answer says the mage is in the Grey Expanse."""
    lowered = str(answer or "").lower()
    return any(needle in lowered for needle in LOST)
