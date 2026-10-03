"""The hunting bestiary (#340): dr-scripts' hunting zones read into
ZONES and TOWNS by tools/hunting_tables.py, a ground resolved as a map
tag, a zone or a ;go2 target, and the zones that suit a rank listed
nearest first (client/game/hunting.py)."""

import importlib.util
import pathlib

from client.game import hunting
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _tables():
    spec = importlib.util.spec_from_file_location(
        "hunting_tables", REPO / "tools/hunting_tables.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tables = _tables()

# The YAML's shapes: the escort zones left out, the town lists, a banner
# per province, the rank comment above a zone, a note, a commented-out
# room, a zone of two creatures, an open-ended range.
YAML = """---
escort_zones:
  grave_worms:
    base: 2317
hunting_areas_by_town:
  Riverhaven:
  # https://elanthipedia.play.net/Heggarangi_frog                          00-26
    - heggarangi_frog_riverhaven
    - grass_eels_riverhaven
hunting_zones:
################################################################################
##########                          ZOLUREN                           ##########
################################################################################
  # https://elanthipedia.play.net/Rat                                       0-30
  # same rats, out ne gate
  black_rats:
  - 14106
  - 14107 # a slow room
################################################################################
##########                          THERENGIA                         ##########
################################################################################
  # https://elanthipedia.play.net/Heggarangi_frog                          00-26
  heggarangi_frog_riverhaven:
  - 488
  # - 13126
  - 487
  # https://elanthipedia.play.net/Grass_eel                                25-50
  # https://elanthipedia.play.net/Wood_Troll_(1)                           36-?
  grass_eels_riverhaven:
  - 591
"""


def test_the_generator_reads_zones_ranges_provinces_and_towns():
    zones, towns = tables.parse(YAML)
    assert set(zones) == {
        "black_rats",
        "heggarangi_frog_riverhaven",
        "grass_eels_riverhaven",
    }
    assert zones["black_rats"] == (
        "Zoluren",
        [14106, 14107],
        [("Rat", 0, 30)],
        ["same rats, out ne gate"],
    )
    assert zones["heggarangi_frog_riverhaven"] == (
        "Therengia",
        [488, 487],
        [("Heggarangi frog", 0, 26)],
        [],  # the commented-out room is no note
    )
    assert zones["grass_eels_riverhaven"][2] == [
        ("Grass eel", 25, 50),
        ("Wood Troll", 36, None),
    ]
    assert towns == {
        "Riverhaven": ["heggarangi_frog_riverhaven", "grass_eels_riverhaven"]
    }


def test_the_generated_table_holds_the_zones_the_hunt_leans_on():
    assert hunting.zone("rats")[1] == (6049, 6048, 6047, 6046, 6050, 6053, 6054)
    assert hunting.zone_range("heggarangi_frog_riverhaven") == (0, 26)
    assert hunting.TOWNS["Riverhaven"][0] == "heggarangi_frog_riverhaven"
    assert len(hunting.ZONES) > 300


MAP = MapDB(
    [
        {
            "id": 7821,
            "uid": [1],
            "title": ["[Barbarian Guild]"],
            "wayto": {"488": "go path", "6046": "go ferry"},
            "timeto": {"488": 5, "6046": 300},
        },
        {
            "id": 488,
            "uid": [488],
            "title": ["[Riverhaven, Pond]"],
            "wayto": {"487": "north"},
        },
        {"id": 487, "uid": [487], "title": ["[Riverhaven, Pond]"], "wayto": {}},
        {
            "id": 6046,
            "uid": [6046],
            "title": ["[Barana's Shipyard]"],
            "tags": ["rats"],
            "wayto": {},
        },
        {
            "id": 591,
            "uid": [591],
            "title": ["[Riverhaven West Wilds, Meadow]"],
            "wayto": {},
        },
    ]
)


def test_a_ground_is_a_map_tag_first_then_a_zone_then_a_go2_target():
    # "rats" is a tag in this map: the tag's rooms, not the zone's seven.
    assert hunting.ground_rooms(MAP, "rats") == [6046]
    # An untagged zone: its rooms the map knows.
    assert hunting.ground_rooms(MAP, "heggarangi_frog_riverhaven") == [487, 488]
    # Neither: ;go2's resolution, a room id here.
    assert hunting.ground_rooms(MAP, "591") == [591]
    assert hunting.ground_rooms(MAP, "") == []


def test_the_zones_that_suit_a_rank_are_listed_nearest_first():
    rows = hunting.grounds(MAP, 7821, 4)
    names = [name for name, _, _, _ in rows]
    assert names[0] == "heggarangi_frog_riverhaven"  # 5 s away
    assert "rats" in names  # the ferry's 300 s, after it
    assert "grass_eels_riverhaven" not in names  # 25-50 does not hold rank 4
    # Nothing measured: the frog's page says it has no boxes (#422).
    assert hunting.describe(rows[0]) == (
        "heggarangi_frog_riverhaven (0-26: Heggarangi frog) — 1 step(s); wiki: no boxes"
    )


def test_the_rank_to_ask_with_is_the_weakest_weapons():
    profile = {"weapons": ["sword:Small Edged:scabbard", "fists:Brawling"]}
    experience = {
        "Small Edged": {"rank": 5},
        "Brawling": {"rank": 4},
        "Large Edged": {"rank": 1},  # not a turn of this profile
    }
    assert hunting.weapon_rank(profile, experience) == 4
    assert hunting.weapon_rank({"weapons": []}, experience) is None
    assert hunting.fits("rats", 30) and not hunting.fits("rats", 31)


# Captured 2026-09-26, the goblins north of the Crossing (test_lootlog.py).
GOBLIN_BOX = (
    "You search the scavenger goblin.\nThe goblin was carrying a poorly made iron box!"
)
GOBLIN_COINS = (
    "You search the scavenger goblin.\n"
    "The goblin was carrying 9 copper coins (Kronars) and 1 bronze coin (Kronar)!"
)
HOG_EMPTY = "You search the large musk hog.\nYou find nothing of interest."


def test_each_search_counts_against_the_creature_it_names():
    # #419: the hunt's end says what each kind of creature carried.
    from client.game import lootlog

    tally = hunting.Tally()
    for answer in (GOBLIN_BOX, GOBLIN_COINS, GOBLIN_COINS, HOG_EMPTY):
        hunting.note_search(tally, lootlog.parse(answer), "goblin")
    # An answer the parser could not read counts against the corpse's noun.
    hunting.note_search(tally, None, "wolf")
    assert hunting.kinds_said(tally.kinds) == (
        "scavenger goblin x3: 1 box(es), 2 with coins; "
        "large musk hog x1: 0 box(es), 0 with coins; "
        "wolf x1: 0 box(es), 0 with coins"
    )
    assert hunting.kinds_total(tally.kinds, "searched") == 5
    assert hunting.kinds_total(tally.kinds, "boxes") == 1


def test_a_zone_line_carries_the_yield_measured_there(monkeypatch):
    from client.game import creatures

    monkeypatch.setattr(creatures, "BOXES", {})  # no wiki fallback here
    monkeypatch.setattr(creatures, "LOCKS", {})
    entry = ("scouts", (36, 49), (("S'lai Scout", 36, 49),), 12)
    plain = "scouts (36-49: S'lai Scout) — 12 step(s)"
    assert hunting.describe(entry) == plain
    assert hunting.describe(entry, {}) == plain
    # Searches alone: the rate per search, no hour yet.
    searches = {"searched": 180, "boxes": 26, "hunts": 0, "minutes": 0.0}
    assert hunting.describe(entry, searches) == (
        plain + "; measured 26 box(es) in 180 search(es), 14%"
    )
    # A logged hunt adds the hour: 3 boxes in 90 minutes.
    hunted = searches | {"hunts": 2, "minutes": 90.0, "hunt_boxes": 3}
    assert hunting.describe(entry, hunted).endswith(
        "14%; 2.0 box(es) an hour over 2 hunt(s)"
    )
    # Opened boxes told to the ground add the copper (#423): 4 boxes
    # held 4,960 copper, 1,240 a box, ~2,480 an hour at 2.0 an hour.
    worth = hunted | {"opened": 4, "coins": 4960}
    assert hunting.describe(entry, worth).endswith(
        "14%; 2.0 box(es) an hour over 2 hunt(s), ~2,480 copper Kronars; "
        "1,240 copper Kronars a box over 4 opened"
    )


def test_where_nothing_is_measured_the_wiki_says_what_it_knows(monkeypatch):
    # #422: the Critter pages' Has Boxes and the Locksmithing page's
    # table, creatures sharing a reading named together; a measured
    # yield always wins over it.
    from client.game import creatures

    monkeypatch.setattr(
        creatures,
        "BOXES",
        {"forager goblin": True, "scavenger goblin": True, "musk hog": False},
    )
    monkeypatch.setattr(
        creatures,
        "LOCKS",
        {"goblin": ("0", "40+", "High"), "wood troll": ("30", "55", "")},
    )
    goblins = (("Forager goblin", 12, 34), ("Scavenger goblin", 18, 36))
    assert hunting.wiki_boxes(goblins) == (
        "wiki: boxes from Forager goblin, Scavenger goblin "
        "(Locksmithing 0-40+, drop high)"
    )
    # Listed in the table alone (no page says), and a mixed zone.
    assert hunting.wiki_boxes((("Wood Troll", 36, 53),)) == (
        "wiki: boxes from Wood Troll (Locksmithing 30-55)"
    )
    mixed = (("Musk Hog", 10, 35), ("Wood Troll", 36, 53), ("Kelpie", 35, 50))
    assert hunting.wiki_boxes(mixed) == (
        "wiki: boxes from Wood Troll (Locksmithing 30-55)"
    )
    assert hunting.wiki_boxes((("Musk Hog", 10, 35),)) == "wiki: no boxes"
    assert hunting.wiki_boxes((("Kelpie", 35, 50),)) == ""  # the wiki is silent
    entry = ("hogs", (10, 35), (("Musk Hog", 10, 35),), 3)
    assert (
        hunting.describe(entry) == "hogs (10-35: Musk Hog) — 3 step(s); wiki: no boxes"
    )
    measured = {"searched": 13, "boxes": 0}
    assert hunting.describe(entry, measured).endswith(
        "; measured 0 box(es) in 13 search(es), 0%"
    )
