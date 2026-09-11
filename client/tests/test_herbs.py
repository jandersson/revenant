"""What heals a wound — the herb table answers a HEALTH area and kind.

The wiki's vocabulary (all, torso, skinnerve; internal/external;
wounds/scars) is mapped onto wounds.py's areas and kinds; the shop
table says where a herb is sold; Knife Clan's cookies name four herbs.
"""

from client.game import herbs
from client.game.herbs_data import HERBS, SHOPS
from client.game.wounds import KINDS


def test_the_generated_table_has_the_wikis_shape():
    assert len(HERBS) >= 30
    for row in HERBS:
        assert len(row) == 9
        name, ranks, season, time, conditions, terrain, part, location, kind = row
        assert name == name.lower() and name
        assert ranks is None or isinstance(ranks, int)
        assert part in herbs.PART_AREAS or part == ""
        assert kind in ("wounds", "scars", "")
        assert location in ("internal", "external", "internal/external", "")
    assert all(product and isinstance(stores, tuple) for product, stores in SHOPS)


def test_every_health_kind_has_a_wiki_match():
    assert set(herbs.KIND_MATCH) == set(KINDS)


def test_remedies_name_the_specific_herb_before_the_cure_alls():
    limb = herbs.remedies("limb", "external")
    assert limb[0] == "jadice flower"
    assert "marram grass" in limb  # an "all" herb, listed after
    assert herbs.remedies("head", "external")[0] == "nemoih root"
    assert "belradi moss" in herbs.remedies("chest", "internal_scar")
    assert "cebi root" in herbs.remedies("skin", "scar")


def test_torso_and_face_herbs_reach_the_health_areas_they_cover():
    torso = [row[0] for row in HERBS if row[6] == "torso"]
    face = [row[0] for row in HERBS if row[6] == "face"]
    assert torso and face  # the wiki uses both words
    for name in torso:
        row = herbs.herb(name)
        for area in ("chest", "abdomen", "back"):
            assert herbs.treats(row, area, _kind_of(row))
    for name in face:
        assert herbs.treats(herbs.herb(name), "head", _kind_of(herbs.herb(name)))


def _kind_of(row):
    location = row["location"].split("/")[0]
    return {
        ("external", "wounds"): "external",
        ("external", "scars"): "scar",
        ("internal", "wounds"): "internal",
        ("internal", "scars"): "internal_scar",
    }[(location, row["kind"])]


def test_an_unknown_area_or_a_blank_row_treats_nothing():
    assert herbs.remedies("tail", "external") == []
    blanks = [row for row in HERBS if not row[6]]
    assert blanks  # the wiki lists a few flowers that heal nothing alone
    for row in blanks:
        for kind in KINDS:
            assert not herbs.treats(herbs.herb(row[0]), "limb", kind)


def test_the_kitchen_cookies_are_the_four_external_wound_herbs():
    covered = {}
    for cookie, name in herbs.KITCHEN_COOKIES.items():
        row = herbs.herb(name)
        assert row["location"] == "external" and row["kind"] == "wounds", cookie
        covered[cookie] = row["part"]
    assert covered == {
        "jadice": "limb",
        "hulnik": "back",
        "nilos": "abdomen",
        "plovik": "chest",
    }
    # Nothing on that counter reaches the head: the abrasions from a
    # fall are not a cookie's job.
    assert not any(
        herbs.treats(herbs.herb(name), "head", "external")
        for name in herbs.KITCHEN_COOKIES.values()
    )
    assert herbs.KITCHEN_ROOM == 6218


def test_sources_come_from_the_shop_table():
    assert herbs.sources_in("hulnik grass", "Crossing") == [
        ("hulnik grass", ["Mauriga's Botanicals (Crossing)"])
    ]
    crossing = herbs.sources_in("jadice flower", "Crossing")
    assert ("jadice flower", ["Alchemy Society (Crossing) (Crossing)"]) in crossing
    assert herbs.sources("aloe leaves") == []  # the wiki lists no shop
    assert herbs.herb("Jadice Flower")["ranks"] == 20
    assert herbs.herb("no such herb") is None
