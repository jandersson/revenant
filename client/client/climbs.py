"""Climbing spots with their Athletics rank bands, keyed to the
community map (#87). ;athletics derives its training ladder from this
table; anything map-aware (the map dock, future planners) may read it.

The community map database is refreshed from upstream and never edited
(client/mapdb.py) — rank knowledge lives here, keyed by that map's
room ids, not written into it. Bands come from Elanthipedia's
"Climbing and Swimming list" (fetched 2026-08-22): low is the rank a
spot starts teaching, high the rank it stops (None = the wiki gives
none); several wiki figures carry "?" marks, kept as given until live
mindstate captures tighten them (the docs/experience.md table method).

Entry kinds:

- "travel"  — a two-room loop over the map's own edges (bottom/top
  room ids); climbs award on the 45-60s timer (docs/experience.md).
- "practice" — one room and an obstacle for `climb practice <x>`,
  award-timer-exempt. The battlements obstacles are assumed
  practice-able like the pear tree until a live run confirms the verb.
- "advice"  — a real spot the community map doesn't cover (or a swim
  the trainer can't loop); shown in ;athletics list only.

Optional per-entry conditions: "weapon" is the wiki table's armed-climb
rank column, encoded only where its rows agree (the column has no
legend on the page — meaning unconfirmed); "notes" carries the wiki's
remark for the spot.

What modifies every climb, spot-independent (Elanthipedia "Athletics",
fetched 2026-08-22): "Lack of encumbrance, armor hindrance, and
injuries also play a role", and "both agility and strength will aid in
climbing"; appraising the obstacle first helps, as do Ranger wilderness
and Thief urban bonuses. ;athletics checks ENCUMBRANCE at auto-mode
start and warns before laps are wasted under load.
"""

CLIMBS = [
    {
        "kind": "travel",
        "low": 0,
        "high": 19,
        "label": "felled tree, Wilderness Deep Forest (west of Crossing)",
        "bottom": 5705,
        "top": 6153,
    },
    {
        "kind": "travel",
        "low": 0,
        "high": 34,
        "label": "moonstone trellis, Jadewater Mansion East Lawn",
        "bottom": 13527,
        "top": 13529,
    },
    {
        "kind": "practice",
        "low": 0,
        "high": 80,
        "label": "pear tree practice, Grassland Road Meadow (timer-exempt)",
        "room": 1455,
        "practice": "pear tree",
    },
    {
        "kind": "travel",
        "low": 5,
        "high": 60,
        "label": "oak tree, Arthe Dale Greensward",
        "bottom": 1068,
        "top": 14134,
        "weapon": 30,  # the wiki's armed-climb column, meaning unconfirmed
    },
    {
        # The wiki caps the apple tree at 34 — the open-ended band it
        # had before was the parked-at-a-stale-rung bug (#87).
        "kind": "travel",
        "low": 10,
        "high": 34,
        "label": "apple tree, Midton Circle",
        "bottom": 19349,
        "top": 7214,
    },
    {
        "kind": "travel",
        "low": 20,
        "high": None,
        "label": "rise, Siergelde Cliffs High Path",
        "bottom": 1429,
        "top": 1430,
    },
    {
        "kind": "travel",
        "low": 30,
        "high": None,
        "label": "mine ladder, Abandoned Mine crevice (beisswurms!)",
        "bottom": 7233,
        "top": 7234,
        "notes": "high skill to drag bodies up",
    },
    {
        # In town atop the NE gate — hostile-free, unlike every
        # wilderness rung. Wiki: 100 to 350?.
        "kind": "practice",
        "low": 100,
        "high": 350,
        "label": "NE gate embrasure, Crossing Battlements (in town)",
        "room": 833,
        "practice": "embrasure",
        "notes": "1 embrasure",
    },
    {
        # Wiki: 150? to 350?; one of three walls.
        "kind": "practice",
        "low": 150,
        "high": 350,
        "label": "W gate wall, Crossing Battlements (in town)",
        "room": 938,
        "practice": "wall",
        "notes": "3 walls",
    },
    {
        # Wiki: 150? to 400; listed after the W gate so the deeper
        # band wins the tie at rank 150+.
        "kind": "practice",
        "low": 150,
        "high": 400,
        "label": "NE gate wall, Crossing Battlements (in town)",
        "room": 833,
        "practice": "wall",
        "notes": "2 walls",
    },
    {
        "kind": "advice",
        "low": 0,
        "high": 80,
        "where": "Crossing sewers (mind the thugs) — swim the channels",
    },
    {
        "kind": "advice",
        "low": 0,
        "high": 110,
        "where": "Goblin Brook (slows after 80) — swim across and back",
    },
    {
        "kind": "advice",
        "low": 75,
        "high": 400,
        "where": "Ilaya Taipa harbor — swim (a trek from Crossing)",
    },
    {
        "kind": "advice",
        "low": 90,
        "high": 400,
        "where": "Geni Oak tree, Geni Wilderness (not in the community map yet)",
    },
    {
        "kind": "advice",
        "low": 175,
        "high": 270,
        "where": "Empath Pole, Crossing Empath Guild (room unverified)",
    },
]


def rungs():
    """The walkable training ladder: travel and practice spots, in
    table order (ties in optimal-rung selection go to later entries)."""
    return [entry for entry in CLIMBS if entry["kind"] in ("travel", "practice")]


def advice():
    """(low, high, where) rows for spots the trainer can't walk."""
    return [
        (entry["low"], entry["high"], entry["where"])
        for entry in CLIMBS
        if entry["kind"] == "advice"
    ]
