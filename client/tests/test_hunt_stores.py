"""STORE and STOW GEM / STOW BOX in ;hunt (the operator, 2026-09-26) —
these tests are the manual. The loot kinds' containers are set with
STORE only when they change, remembered per character; a gem or box on
the ground goes in with one STOW, the old GET path when STOW answers
otherwise."""

from types import SimpleNamespace

import hunt_arena
from hunt_arena import KILL, NOTHING, PROFILE, Arena, _run, kill

hunt = hunt_arena.hunt

STORED_BOXES = "You will now store boxes in your canvas sack.\n"  # captured 2026-09-26
STORED_GEMS = "You will now store gems in your gem pouch.\n"


class Asker:
    def __init__(self, answers):
        self.answers = answers
        self.sent, self.echoed = [], []
        self.state = SimpleNamespace(name="Lanival")

    def echo(self, text):
        self.echoed.append(text)


def _ask(asker):
    def ask(s, command):
        asker.sent.append(command)
        for prefix, answer in asker.answers.items():
            if command.startswith(prefix):
                return answer
        return ""

    return ask


def test_store_is_sent_once_and_not_again_until_the_container_changes(monkeypatch):
    asker = Asker({"store boxes": STORED_BOXES, "store gems": STORED_GEMS})
    monkeypatch.setattr(hunt, "ask", _ask(asker))
    profile = {"loot_container": "sack", "gem_pouch": "pouch"}
    assert hunt.set_stores(asker, dict(profile)) == ["box", "gem"]
    assert asker.sent == ["store boxes in sack", "store gems in pouch"]
    asker.sent.clear()
    assert hunt.set_stores(asker, dict(profile)) == ["box", "gem"]
    assert asker.sent == []  # the game keeps STORE: nothing to send
    hunt.set_stores(asker, profile | {"loot_container": "backpack"})
    assert asker.sent == ["store boxes in backpack"]


def test_a_store_the_game_refuses_is_said_and_that_kind_goes_by_hand(monkeypatch):
    asker = Asker(
        {
            "store boxes": "You can only store things in containers that you are wearing.\n"
        }
    )
    monkeypatch.setattr(hunt, "ask", _ask(asker))
    assert hunt.set_stores(asker, {"loot_container": "sack"}) == []
    assert any("boxes picked up by hand" in e for e in asker.echoed)
    asker.sent.clear()
    hunt.set_stores(asker, {"loot_container": "sack"})
    assert asker.sent == ["store boxes in sack"]  # not remembered: tried again


def test_a_two_word_container_is_named_bare_as_store_takes_it(monkeypatch):
    # #415 (2026-10-02): STORE takes its container as one or two words —
    # "store herbs in my herb bag" answered "I could not find that
    # container." while "store herbs in herb bag" set it. No MY, so a
    # two-word profile container still fits.
    asker = Asker({"store gems": STORED_GEMS})
    monkeypatch.setattr(hunt, "ask", _ask(asker))
    assert hunt.set_stores(asker, {"gem_pouch": "gem pouch"}) == ["gem"]
    assert asker.sent == ["store gems in gem pouch"]


def test_a_box_on_the_ground_goes_in_with_stow_box(monkeypatch):
    found = iter([["a small wooden coffer"], ["a small wooden coffer"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena(
        {
            "attack": [(KILL, _no_kill), (KILL, kill), (KILL, kill)],
            "loot": [NOTHING] * 3,
            # Captured 2026-09-26 at the goblins, the first STOW BOX.
            "stow box": [
                "You pick up a mud-stained steel crate.\n"
                "You put your crate in your canvas sack.\n"
            ]
            * 3,
        }
    )
    farm = PROFILE | {"skin": False, "box_limit": 2, "until": "boxes"}
    _run(arena, profile=farm, travel_first=False)
    assert arena.sent.count("stow box") == 2
    assert "get coffer" not in arena.sent
    assert any("2 box(es) in the sack — the farm is done" in e for e in arena.echoed)


def test_a_full_sack_ends_the_farm_with_the_box_in_hand(monkeypatch):
    # 2026-09-26 at the goblins: STOW BOX picked the chest up and the
    # sack refused it; the hunt said it stayed on the ground, tried GET
    # CHEST and the pouch for it, farmed on — the box count never grew —
    # and for the next box sheathed the broadsword to free a hand, the
    # chest and a casket in hand among three goblins.
    found = iter([["a reinforced oaken chest"], ["a driftwood casket"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    searched = (
        "You search the scavenger goblin.\n"
        "The goblin was carrying a reinforced oaken chest!\n"
    )
    arena = Arena(
        {
            "attack": [(KILL, kill), (KILL, kill)],
            "loot": [searched, NOTHING],
            "stow box": [
                "You pick up a reinforced oaken chest.\n"
                "There isn't any more room in the sack for that.\n"
            ],
        }
    )
    farm = PROFILE | {"skin": False, "box_limit": 8, "until": "boxes"}
    _run(arena, profile=farm, travel_first=False)
    assert arena.sent.count("stow box") == 1
    assert not any(
        c.startswith(("get chest", "get casket", "put my chest")) for c in arena.sent
    )
    assert not any(c.startswith("sheathe") for c in arena.sent)
    assert any("the sack is full — the chest is in hand" in e for e in arena.echoed)
    assert any(
        "the sack is full after 0 box(es) this run — the farm is done" in e
        for e in arena.echoed
    )
    assert arena.sent.count("loot") == 1  # the farm ended on the refusal


def test_a_gem_a_full_pouch_refuses_goes_with_the_loot(monkeypatch):
    # 2026-10-03 (#436): STOW GEM at a full pouch picked the gem up and
    # kept it in hand, and "You pick up" read as stowed — two gems sat in
    # Cecil's hands into ;athletics. Now the pouch is full and the gem
    # goes into the loot container.
    found = iter([["a tiny green diopside"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    full = (
        "You've already got a wealth of gems in there!  You'd better tie it up "
        "before putting more gems inside.\n"
    )
    arena = Arena(
        {
            "attack": [(KILL, kill), (KILL, _no_kill)],
            "loot": [NOTHING] * 2,
            "stow gem": ["You pick up a tiny green diopside.\n" + full],
            "put my diopside in my pouch": [full],
            "put my diopside in my sack": [
                "You put your diopside in your canvas sack.\n"
            ],
        }
    )
    _run(
        arena,
        profile=PROFILE | {"skin": False, "gem_pouch": "pouch"},
        travel_first=False,
    )
    assert "stow gem" in arena.sent
    assert "put my diopside in my sack" in arena.sent
    assert any(
        "the pouch is full — the diopside goes with the loot (#283)" in e
        for e in arena.echoed
    )


def _no_kill(arena):
    """The first swing's line, the rat still up (test_hunt's _stands)."""


def test_a_lone_coin_is_picked_up_as_a_coin_not_as_coins(monkeypatch):
    # 2026-09-26: a goblin dropped "8 copper coins (Kronars) and 1 bronze
    # coin (Dokora)"; GET COINS twice took the coppers and answered "What
    # were you referring to?" for the bronze, which stayed on the ground.
    found = iter([["some copper coins", "a bronze coin"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "loot": [NOTHING],
            "get coins": ["You pick up 8 copper Kronars.\n"],
            "get coin": ["You pick up 1 bronze Dokora.\n"],
        }
    )
    _run(arena, profile=PROFILE | {"skin": False, "max_kills": 1}, travel_first=False)
    gets = [c for c in arena.sent if c.startswith("get coin")]
    assert gets == ["get coins", "get coin"]


def test_a_box_farm_fights_on_when_its_weapon_skill_locks(monkeypatch):
    # 2026-09-26: the boxes style's mace mind-locked Small Blunt five kills
    # in and the farm ended "every weapon skill mind-locked" with its box
    # limit far off.
    found = iter([["a small wooden coffer"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "loot": [NOTHING],
            "stow box": [
                "You pick up a mud-stained steel crate.\n"
                "You put your crate in your canvas sack.\n"
            ],
        },
        experience={"Small Blunt": {"rank": 13, "percent": 0, "mindstate": 34}},
    )
    farm = PROFILE | {
        "skin": False,
        "box_limit": 1,
        "until": "boxes",
        "weapons": ["mace:Small Blunt:backpack"],
    }
    _run(arena, profile=farm, travel_first=False)
    assert not any("mind-locked" in e for e in arena.echoed)
    assert any("1 box(es) in the sack — the farm is done" in e for e in arena.echoed)


# #423: a box picked up is a box_drops row — its item id beside the
# creature the search named — for ;boxes to tell its contents to.
SCOUT_SEARCH = (
    "You search the S'lai scout.\nThe scout was carrying a salt-stained copper box!\n"
)
COPPER_BOX = {"noun": "box", "exist": "139883771", "name": "copper box"}


def _drops(monkeypatch, tmp_path, answers):
    import sqlite3

    db = tmp_path / "history.db"
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(db))
    found = iter([["a salt-stained copper box"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena({"attack": [(KILL, kill)], "loot": [SCOUT_SEARCH], **answers})
    farm = PROFILE | {"skin": False, "box_limit": 1, "until": "boxes"}
    _run(arena, profile=farm, travel_first=False)
    with sqlite3.connect(str(db)) as connection:
        return connection.execute(
            "SELECT box_id, noun, description, creature, ground, loot_seq"
            " FROM box_drops"
        ).fetchall()


def _beaten(db, creature, boxes, opened=0):
    """history.db with `boxes` boxes of `creature` worked by ;boxes: each
    put back too hard, the last `opened` of them opened instead."""
    import sqlite3

    from client.game import boxlog

    with sqlite3.connect(str(db)) as connection:
        boxlog.ensure_schema(connection)
        for index in range(boxes):
            box_id = f"{abs(hash(creature)) % 100000}{index}"  # unique per creature
            boxlog.record_drop(
                connection,
                character_name="Lanival",
                box_id=box_id,
                noun="trunk",
                description="a cracked pine trunk",
                creature=creature,
                ground="young_ogres",
            )
            done = index >= boxes - opened
            boxlog.record_attempt(
                connection,
                character_name="Lanival",
                box_id=box_id,
                noun="trunk",
                verb="open" if done else "disarm",
                reading=None if done else 12,
                outcome="open" if done else "too hard",
                lockpick="ordinary",
                rank=53,
            )


def test_a_creatures_boxes_the_data_says_are_past_you_are_left(monkeypatch, tmp_path):
    # #495 (2026-10-09): thirteen ogre boxes in the tote, every one put
    # back "for a better locksmith" at Locksmithing 53 — the hunt kept
    # bringing them home.
    db = tmp_path / "history.db"
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(db))
    _beaten(db, "s'lai scout", 3)
    found = iter([["a salt-stained copper box"], ["a salt-stained copper box"], []])
    monkeypatch.setattr(
        hunt.loot, "new_items", lambda before, after, creatures=(): next(found, [])
    )
    arena = Arena(
        {"attack": [(KILL, kill)] * 2, "loot": [SCOUT_SEARCH] * 2},
        experience={"Locksmithing": {"rank": 53, "percent": 0, "mindstate": 0}},
    )
    _run(arena, profile=PROFILE | {"skin": False, "max_kills": 2}, travel_first=False)
    assert "stow box" not in arena.sent and "get box" not in arena.sent
    said = [t for t in arena.echoed if "boxes are past you at Locksmithing 53" in t]
    assert len(said) == 1  # once a run, two searches
    assert "the box stays (the last three went back unopened)" in said[0]


def test_a_box_farm_takes_the_boxes_whatever_the_data_says(monkeypatch, tmp_path):
    db = tmp_path / "history.db"
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(db))
    _beaten(db, "s'lai scout", 3)
    rows = _drops(
        monkeypatch, tmp_path, {"stow box": ["You put your box in your sack.\n"]}
    )
    assert len(rows) == 4  # the three seeded, and the farm's pickup


def test_one_opened_among_the_last_three_is_no_verdict(tmp_path):
    import sqlite3

    from client.game import boxlog

    db = tmp_path / "history.db"
    _beaten(db, "young ogre", 3, opened=1)
    with sqlite3.connect(str(db)) as connection:
        assert not boxlog.beyond(connection, "Lanival", "young ogre")
        assert len(boxlog.verdicts(connection, "Lanival", "young ogre")) == 3
    _beaten(db, "rat", 2)
    assert not boxlog.past("Lanival", "rat", path=db)  # two boxes: too few
    _beaten(db, "wood troll", 3)
    assert boxlog.past("Lanival", "Wood Troll", path=db)  # case ignored
    assert not boxlog.past("Lanival", "", path=db)
    assert not boxlog.past("Lanival", "rat", path=tmp_path / "none.db")


def test_a_stowed_box_is_logged_with_the_id_its_hand_tag_showed(monkeypatch, tmp_path):
    # Captured 2026-10-02: STOW BOX showed the box in the left hand and
    # emptied it on the same line; the parser's last_held keeps it.
    def flashed(arena):
        arena.state.hand_events = getattr(arena.state, "hand_events", 0) + 1
        arena.state.last_held = {
            "left": dict(COPPER_BOX, seq=arena.state.hand_events),
            "right": None,
        }

    stowed = (
        "You pick up a salt-stained copper box.\n"
        "You put your box in your canvas sack.\n",
        flashed,
    )
    rows = _drops(monkeypatch, tmp_path, {"stow box": [stowed]})
    assert rows == [
        (
            "139883771",
            "box",
            "a salt-stained copper box",
            "s'lai scout",
            PROFILE["hunting_ground"],
            1,
        )
    ]


def test_a_box_picked_up_by_hand_is_logged_with_the_id_it_held(monkeypatch, tmp_path):
    # The GET path (STOW BOX answered nothing known): the box's tag is
    # read while it is in hand, before the PUT — in a session whose
    # parser keeps no last_held as well.
    def in_hand(arena):
        arena.state.right_hand = dict(COPPER_BOX)

    rows = _drops(
        monkeypatch,
        tmp_path,
        {
            "stow box": ["You glance around.\n"],
            "get box": [("You pick up a salt-stained copper box.\n", in_hand)],
            "put my box": ["You put your box in your canvas sack.\n"],
        },
    )
    assert [row[0] for row in rows] == ["139883771"]
