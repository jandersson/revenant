"""How a HEALTH answer becomes wounds by area and severity — these tests
are the manual (#151).

The fixtures are captured HEALTH answers (2026-08 and 2026-09 sessions,
names scrubbed); the wordings they contain are the ones Elanthipedia's
Damage tables list, generated into client/wounds_data.py.
"""

from client import wounds
from client.wounds import SEVERITIES, describe, level, parse_health

# Captured: a veteran with a fresh neck cut on top of old scars, and a
# bleeding table with one row.
BATTERED = """Your body feels slightly battered.
Your spirit feels full of life.
You have deep cuts across the neck, some tiny scars across the right arm, an occasional twitching in the left arm, a constant twitching in the right leg, severe scarring and chunks of flesh missing from the left leg, a partially paralyzed right hand, a constant twitching in the left hand, a constant twitching in the chest area, severe scarring and ugly gashes about the abdomen, an occasional twitching in the back, a severely swollen and bruised right eye, some severe twitching.

Bleeding
            Area       Rate
-----------------------------------------
            neck       slight
"""

# Captured: the same character once the neck was tended.
TENDED = """Your body feels at full strength.
Your spirit feels full of life.
You have deep cuts across the neck, some tiny scars across the right arm.

Bleeding
            Area       Rate
-----------------------------------------
            neck       clotted(tended)
"""

# Captured: scratches after a scuffle, and a clean bill of health.
SCUFFED = """Your body feels at full strength.
Your spirit feels full of life.
You have some minor abrasions to the head, cuts and bruises about the neck, cuts and bruises about the left arm.
"""
CLEAN = """Your body feels at full strength.
Your spirit feels full of life.
You have no significant injuries.
"""


def test_severity_names_map_to_numbers_in_order():
    assert level("harmful") == 4
    assert level("Useless") == 8
    assert level(3) == 3
    assert SEVERITIES[0] == "none"


def test_the_vitality_and_spirit_lines_are_read():
    health = parse_health(BATTERED)
    assert health.vitality == "slightly battered"
    assert health.spirit == "full of life"


def test_each_wound_lands_on_its_area_kind_and_level():
    health = parse_health(BATTERED)
    assert health.wounds["neck"].external == level("harmful")  # deep cuts across
    assert health.wounds["right arm"].scar == level("negligible")  # tiny scars
    assert health.wounds["left arm"].internal_scar == level(
        "minor"
    )  # occasional twitching
    assert health.wounds["right leg"].internal_scar == level(
        "harmful"
    )  # constant twitching
    assert health.wounds["left leg"].scar == level("severe")  # chunks of flesh missing
    assert health.wounds["right hand"].internal_scar == level(
        "severe"
    )  # partially paralyzed
    assert health.wounds["chest"].internal_scar == level("harmful")
    assert health.wounds["abdomen"].scar == level("damaging")  # ugly gashes
    assert health.wounds["back"].internal_scar == level("minor")
    assert health.wounds["right eye"].internal == level(
        "harmful"
    )  # severely swollen and bruised
    assert health.wounds["skin"].internal == level("harmful")  # some severe twitching
    assert health.unknown == []


def test_the_worst_wound_and_the_floor_query():
    health = parse_health(BATTERED)
    assert health.worst() == ("left leg", "scar", level("severe"))
    assert ("right hand", "internal_scar", 6) in health.at_least("severe")
    assert all(lvl >= 6 for _, _, lvl in health.at_least("severe"))
    assert health.at_least("devastating") == []


def test_a_repeated_wiki_phrase_reads_as_its_lower_level():
    # "a constant twitching in the neck" is listed as harmful and damaging.
    health = parse_health("You have a constant twitching in the neck.")
    assert health.wounds["neck"].internal_scar == level("harmful")


def test_the_bleeding_table_becomes_tend_rows():
    rows = parse_health(BATTERED).bleeders()
    assert rows == [
        {
            "area": "neck",
            "inside": False,
            "rate": "slight",
            "severity": 3,
            "tendable": True,
        }
    ]
    tended = parse_health(TENDED).bleeders()
    assert tended[0]["rate"] == "clotted(tended)"
    assert tended[0]["tendable"] is False


def test_an_internal_bleeder_is_marked_inside():
    health = parse_health("Bleeding\n  Area  Rate\n---\n  inside r. leg   moderate\n")
    assert health.wounds["right leg"].inside_bleeding == "moderate"
    assert health.bleeders()[0]["inside"] is True


def test_light_scuffs_and_a_clean_bill_of_health():
    scuffed = parse_health(SCUFFED)
    assert scuffed.wounds["head"].external == level("insignificant")
    assert scuffed.wounds["neck"].external == level("minor")
    assert scuffed.wounds["left arm"].external == level("minor")
    clean = parse_health(CLEAN)
    assert clean.wounds == {}
    assert clean.worst() is None
    assert clean.bleeders() == []


def test_a_wording_the_tables_lack_is_reported_not_dropped():
    health = parse_health(
        "You have cuts and bruises about the neck, a glowing green nose."
    )
    assert health.wounds["neck"].external == level("minor")
    assert health.unknown == ["glowing green nose"]  # article stripped


def test_describe_reads_like_a_report():
    lines = describe(parse_health(TENDED))
    assert lines == [
        "neck: external harmful, bleeding clotted(tended)",
        "right arm: scar negligible",
    ]


def test_the_generated_table_covers_every_area_kind_and_level():
    areas = {row[0] for row in wounds.ROWS}
    assert areas == {"head", "eye", "neck", "chest", "abdomen", "back", "limb", "skin"}
    assert {row[1] for row in wounds.ROWS} == set(range(1, 9))
    assert {row[2] for row in wounds.ROWS} == set(wounds.KINDS)
