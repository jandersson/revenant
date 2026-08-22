"""The climbing knowledge base — rank bands keyed to the community map.

client/climbs.py is the one table ;athletics builds its ladder from
(#87): travel loops carry two map room ids, practice spots one room
and an obstacle, advice rows a description only. Bands come from
Elanthipedia's "Climbing and Swimming list" (fetched 2026-08-22);
"?"-flagged wiki figures are encoded as given until live captures
tighten them.
"""

from client import climbs


def test_every_entry_carries_its_kinds_required_fields():
    for entry in climbs.CLIMBS:
        assert entry["kind"] in ("travel", "practice", "advice")
        assert isinstance(entry["low"], int)
        assert entry["high"] is None or entry["high"] > entry["low"]
        # Optional condition fields keep their shapes when present.
        assert isinstance(entry.get("weapon", 0), int)
        assert isinstance(entry.get("notes", ""), str)
        if entry["kind"] == "travel":
            assert isinstance(entry["bottom"], int)
            assert isinstance(entry["top"], int)
        elif entry["kind"] == "practice":
            assert isinstance(entry["room"], int)
            assert entry["practice"]
        else:
            assert entry["where"]


def test_rungs_are_the_walkable_kinds_and_advice_the_rest():
    assert all(entry["kind"] != "advice" for entry in climbs.rungs())
    assert len(climbs.rungs()) + len(climbs.advice()) == len(climbs.CLIMBS)


def test_the_wiki_caps_are_encoded_not_open_ended():
    # The apple tree's open-ended band was the parked-at-a-stale-rung
    # bug (#87): the wiki caps it at 34.
    apple = next(e for e in climbs.CLIMBS if e["label"].startswith("apple tree"))
    assert apple["high"] == 34


def test_rank_144_lands_on_an_in_town_rung():
    # The live gap that parked rank 144 at the rank-30 mine (#87): the
    # NE gate embrasure (100-350) covers it, inside Crossing's walls.
    embrasure = next(
        e for e in climbs.rungs() if e["label"].startswith("NE gate embrasure")
    )
    assert embrasure["low"] <= 144 < embrasure["high"]
    assert embrasure["room"] == 833  # [Crossing, Northeast Gate Battlements]
