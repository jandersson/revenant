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
