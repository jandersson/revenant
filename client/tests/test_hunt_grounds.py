""";hunt's ground from the bestiary (#340): a `hunting_ground` naming a
hunting zone walks to the zone's rooms, a map tag keeps its own, and
`;hunt grounds` lists the zones that suit the weakest weapon's rank.
Arena: hunt_arena.py."""

from types import SimpleNamespace

from hunt_arena import GROUND, KILL, NOTHING, PROFILE, SKINNED, Arena, _run, hunt, kill

from client.game import hunting

YARD_ZONE = {
    "yard_rats": ("Zoluren", (6048, 6047), (("Rat", 0, 30),), ()),
    "far_trolls": ("Zoluren", (1,), (("Cave troll", 200, 300),), ()),
}


def test_a_zone_name_walks_to_the_zones_rooms(travel, monkeypatch):
    monkeypatch.setattr(hunting, "ZONES", YARD_ZONE)
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]},
    )
    _run(arena, profile=PROFILE | {"hunting_ground": "yard_rats", "max_kills": 1})
    assert arena.walks[0] == {6047, 6048}


def test_a_map_tag_keeps_its_rooms_over_a_zone_of_the_same_name(travel, monkeypatch):
    monkeypatch.setattr(
        hunting, "ZONES", {"rats": ("Zoluren", (6048,), (("Rat", 0, 30),), ())}
    )
    arena = Arena(
        {"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]},
    )
    _run(arena, profile=PROFILE | {"hunting_ground": "rats", "max_kills": 1})
    assert arena.walks[0] == {6046, 6047}  # the tag's rooms, as before


class Echoes:
    def __init__(self, experience):
        self.echoed = []
        self.state = SimpleNamespace(
            experience=experience, room=6046, name="Lanival", room_uid=1
        )

    def echo(self, text):
        self.echoed.append(text)


def test_grounds_lists_the_zones_the_weakest_weapon_suits(monkeypatch, tmp_path):
    # Nothing measured: the arena hunts above logged to the shared test db.
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setattr(hunting, "ZONES", YARD_ZONE)
    monkeypatch.setattr(hunt, "locate", lambda db, state: state.room)
    s = Echoes({"Small Edged": {"rank": 12}, "Brawling": {"rank": 4}})
    profile = PROFILE | {
        "weapons": ["handaxe:Small Edged:sack", "fists:Brawling"],
        "hunting_ground": "yard_rats",
    }
    hunt.show_grounds(s, profile, GROUND, [])
    assert s.echoed[0] == "hunt: hunting zones for rank 4, nearest first:"
    # Nothing measured, so the wiki's word: the rat's page says no boxes (#422).
    assert s.echoed[1] == (
        "  yard_rats (0-30: Rat) — 1 step(s); wiki: no boxes  (your ground)"
    )
    assert not any("far_trolls" in line for line in s.echoed)
    # A rank given; and none to go by.
    s = Echoes({})
    hunt.show_grounds(s, PROFILE, GROUND, ["250"])
    assert s.echoed == ["hunt: no hunting zone reachable from here suits rank 250"]
    s = Echoes({})
    hunt.show_grounds(s, PROFILE, GROUND, [])
    assert s.echoed == ["hunt: no weapon skill to go by — ;hunt grounds <rank>"]


def test_grounds_says_the_box_rate_measured_on_a_zone(monkeypatch, tmp_path):
    # #419: the character's own searches and hunts on the zone, beside
    # the bestiary's band; another character's are not theirs.
    from client.game import lootlog

    path = tmp_path / "history.db"
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(path))
    monkeypatch.setattr(hunting, "ZONES", YARD_ZONE)
    monkeypatch.setattr(hunt, "locate", lambda db, state: state.room)
    s = Echoes({})
    box = "You search the rat.\nThe rat was carrying a poorly made iron box!"
    for answer in (box, NOTHING, NOTHING, NOTHING):
        lootlog.log(s, answer, "yard_rats")
    sable = SimpleNamespace(state=SimpleNamespace(name="Sable", room_uid=1))
    lootlog.log(sable, box, "yard_rats")
    lootlog.log_hunt(s, ground="yard_rats", minutes=30.0, kills=4, boxes=1)
    hunt.show_grounds(s, PROFILE, GROUND, ["10"])
    assert s.echoed[1] == (
        "  yard_rats (0-30: Rat) — 1 step(s); measured 1 box(es) in 4 search(es), "
        "25%; 2.0 box(es) an hour over 1 hunt(s)"
    )
    # #423: a box opened and told to the zone adds the copper it held.
    from client.game import boxlog

    later = "2999-01-01T00:00:00+00:00"  # after every search above
    boxlog.log_opened(s, run_started=later, noun="box", coins=450)
    s.echoed.clear()
    hunt.show_grounds(s, PROFILE, GROUND, ["10"])
    assert s.echoed[1].endswith(
        "2.0 box(es) an hour over 1 hunt(s), ~900 copper; 450 copper a box over 1 opened"
    )
