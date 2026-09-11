"""What heals a wound: healing herbs by body area and kind, and where to buy them.

The table comes from Elanthipedia's Healing herbs page (herbs_data.py
is generated from it by tools/herb_tables.py, never hand-edited). It
speaks the wiki's vocabulary — body parts "all", "limb", "torso",
"skinnerve", location "internal"/"external", type "wounds"/"scars" —
and this module maps that onto the HEALTH wound model in
client/game/wounds.py (areas head, eye, neck, chest, abdomen, back,
limb, skin; kinds external, scar, internal, internal_scar), so a
parsed wound can be answered with the herbs that treat it and the
shops that stock them. Model and captured evidence: docs/healing.md.

Bleeding is not here: TEND stops it (;tend, docs/wounds.md). Neither
are Empaths, who heal by touch and are players, not data.
"""

from client.game.herbs_data import HERBS, SHOPS

# The wiki's body parts against HEALTH's areas: which areas a herb for
# that part treats. "torso" covers the three trunk areas; "face" is
# reported as the head by HEALTH; "skinnerve" is the skin/nerves area.
PART_AREAS = {
    "all": {"head", "eye", "neck", "chest", "abdomen", "back", "limb", "skin"},
    "head": {"head"},
    "face": {"head"},
    "eye": {"eye"},
    "neck": {"neck"},
    "chest": {"chest"},
    "abdomen": {"abdomen"},
    "back": {"back"},
    "torso": {"chest", "abdomen", "back"},
    "limb": {"limb"},
    "skinnerve": {"skin"},
}

# HEALTH's four wound kinds against the wiki's (location, type).
KIND_MATCH = {
    "external": ("external", "wounds"),
    "scar": ("external", "scars"),
    "internal": ("internal", "wounds"),
    "internal_scar": ("internal", "scars"),
}

# Dokt's Healer's Kitchen at Knife Clan (map room 6218, tags dokt and
# npchealer — the former NPC healer, retired to baking; captured
# 2026-09-11): remedy-infused cookies, one per herb, "ideal for your
# external wounds". Cookie noun -> herb, as the counter lists them.
KITCHEN_ROOM = 6218
KITCHEN_COOKIES = {
    "jadice": "jadice flower",
    "hulnik": "hulnik grass",
    "nilos": "nilos grass",
    "plovik": "plovik leaves",
}


def herb(name):
    """The herb's row as a dict, or None. Names match ignoring case and
    the wiki's "leaves"/"leaf" wobble is not smoothed — use the table's."""
    wanted = name.strip().lower()
    for row in HERBS:
        if row[0] == wanted:
            return _as_dict(row)
    return None


def _as_dict(row):
    name, ranks, season, time, conditions, terrain, part, location, kind = row
    return {
        "name": name,
        "ranks": ranks,
        "season": season,
        "time": time,
        "conditions": conditions,
        "terrain": terrain,
        "part": part,
        "location": location,
        "kind": kind,
    }


def treats(row, area, kind):
    """True when a herb row treats a wound of that HEALTH area and kind."""
    location, wound_type = KIND_MATCH[kind]
    if row["kind"] != wound_type:
        return False
    if location not in row["location"].split("/"):
        return False
    return area in PART_AREAS.get(row["part"], set())


def remedies(area, kind):
    """The herbs that treat a wound of that area (head, eye, neck,
    chest, abdomen, back, limb, skin) and kind (external, scar,
    internal, internal_scar), specific-part herbs before the cure-alls."""
    rows = [_as_dict(row) for row in HERBS]
    fitting = [row for row in rows if treats(row, area, kind)]
    return [row["name"] for row in fitting if row["part"] != "all"] + [
        row["name"] for row in fitting if row["part"] == "all"
    ]


def sources(name):
    """Where the wiki's shop table says a herb product is sold — the
    products of that herb (flower, salve, potion ...), each with its
    stores. [] for one no shop stocks."""
    stem = name.strip().lower().split()[0]
    return [
        (product, list(stores))
        for product, stores in SHOPS
        if product.split()[0] == stem and stores
    ]


def sources_in(name, place):
    """The stores in one town (a substring of the store's name, e.g.
    "Crossing") for a herb's products."""
    return [
        (product, [store for store in stores if place.lower() in store.lower()])
        for product, stores in sources(name)
        if any(place.lower() in store.lower() for store in stores)
    ]
