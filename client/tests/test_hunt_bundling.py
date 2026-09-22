"""How ;hunt bundles its skins (#174): a bundle worn before the first
swing, the first skin of a run starting one, every later skin into it,
and the run falling back to loose skins when the rope is missing or the
bundle is full. Arena and wordings: hunt_arena.py."""

from hunt_arena import (
    Arena,
    BUNDLING,
    GROUND,
    KILL,
    NOTHING,
    PELT_LOOSE,
    PROFILE,
    Patient,
    RAT_CORPSE,
    RAT_KILL,
    SKINNED,
    TAIL_REMOVED,
    _hands,
    _run,
    _stands,
    hunt,
    kill,
)


# --- bundling (#174) ---------------------------------------------------------


# Captured 2026-09-12 at Falken's Tannery; the hand tags, not a wording,
# say whether a skin went into the worn bundle.
BUNDLED = "You bundle up your rat pelt with your bundling rope."


GOT_BUNDLE = "You get a lumpy bundle from inside your canvas sack."


MISSING = "What were you referring to?"


NOT_FOUND = "I could not find what you were referring to."  # TAP, captured 2026-09-12


def skin_in_hand(arena):
    arena.state.left_hand = {"noun": "pelt", "exist": "1", "name": "rat pelt"}


def hand_empty(arena):
    arena.state.left_hand = None


def test_a_bundle_kept_in_the_sack_is_worn_before_the_weapon_is_drawn(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": ["You tap a lumpy bundle inside your canvas sack."],
            "get my bundle": [GOT_BUNDLE],
            "skin": [
                PELT_LOOSE
            ],  # the skin goes into the worn bundle: hand stays empty
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    assert arena.sent[:4] == [
        "tap my bundle",
        "get my bundle from my sack",
        "wear my bundle",
        "wield my handaxe",
    ]
    after_skin = arena.sent[arena.sent.index("skin rat") + 1 :]
    assert after_skin[0] == "search rat"  # nothing stowed, nothing bundled by hand
    assert any("1 kill(s), 1 skin(s)" in text for text in arena.echoed)


def test_the_first_skin_starts_the_bundle_and_wears_it(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": [NOT_FOUND],
            "skin": [(PELT_LOOSE, skin_in_hand)],
            "get my rope": ["You get a bundling rope from inside your canvas sack."],
            "bundle": [(BUNDLED, hand_empty)],
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    first = arena.sent.index("skin rat")
    assert arena.sent[first : first + 7] == [
        "skin rat",
        "sheathe my handaxe in my sack",
        "get my rope from my sack",
        "bundle",
        "wear my bundle",
        "wield my handaxe",
        "search rat",
    ]
    assert any("bundle started and worn" in text for text in arena.echoed)


def test_a_full_bundle_is_known_and_the_skin_is_stowed_loose(travel):
    # Captured 2026-09-20 on the fourth badger skin of a run (#254): the
    # worn bundle takes no more, BUNDLE says so, the skin stays in hand.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": ["You tap a lumpy bundle that you are wearing."],
            "skin": [(PELT_LOOSE, skin_in_hand)],
            "bundle": [
                "Where did you intend to put that?  You don't have any bundles or "
                "they're all full or too tightly packed!  Type BUNDLE HELP for "
                "more details."
            ],
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    assert "bundle" in arena.sent
    assert any("took no more" in text for text in arena.echoed)
    assert not any("unrecognized bundle" in text for text in arena.echoed)


def test_a_weapon_not_in_its_container_is_drawn_from_wherever_it_is(travel):
    # #259: the scimitar sat in the sack while the profile named the
    # scabbard, and a GET at the scabbard swung the turn bare-handed.
    # WIELD searches the inventory itself (captured 2026-09-22).
    arena = _run(
        Arena(
            {
                "wield my handaxe": [
                    "You draw out your oak-hafted handaxe from the canvas sack, "
                    "gripping it firmly in your right hand."
                ],
                "attack": [(KILL, kill)],
                "skin": [SKINNED],
                "search": [NOTHING],
            }
        ),
        travel_first=False,
    )
    assert arena.sent[0] == "wield my handaxe"
    assert not any("no handaxe to draw" in t for t in arena.echoed)
    gone = _run(
        Arena({"wield my handaxe": [MISSING], "attack": [(KILL, kill)]}),
        travel_first=False,
    )
    assert any("no handaxe to draw" in t for t in gone.echoed)


def test_a_skin_the_bundle_will_not_take_leaves_the_next_one_to_start_it(travel):
    # #260: a curved claw as the first skin — "You don't have any
    # bundles or they're all full or too tightly packed!" — was reported
    # and turned bundling off for the run.
    full = (
        "Where did you intend to put that?  You don't have any bundles or "
        "they're all full or too tightly packed!  Type BUNDLE HELP for more details."
    )
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "tap": [NOT_FOUND] * 2,
            "skin": [(PELT_LOOSE, skin_in_hand)] * 2,
            "get my rope": ["You get a bundling rope from inside your canvas sack."]
            * 2,
            "bundle": [full, (BUNDLED, hand_empty)],
            "search": [NOTHING] * 2,
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("get my rope from my sack") == 2
    assert any("would not take that skin" in t for t in arena.echoed)
    assert any("bundle started and worn" in t for t in arena.echoed)
    assert not any("unrecognized" in t for t in arena.echoed)


def test_a_skin_no_container_will_take_stays_in_hand_and_ends_skinning(travel):
    # #262: "There isn't any more room in the sack for that." — four
    # times on 2026-09-21, the answer unread, a pelt in each hand.
    no_room = "There isn't any more room in the sack for that."
    arena = _run(
        Arena(
            {
                "attack": [(KILL, _stands), (KILL, kill)],
                "skin": [SKINNED] * 2,
                "put my pelt in my sack": [no_room],
                "stow my pelt": [no_room],
                "search": [NOTHING] * 2,
            }
        ),
        profile=PROFILE | {"max_kills": 2},
        travel_first=False,
    )
    assert arena.sent.count("skin rat") == 1
    assert "stow my pelt" in arena.sent
    assert any("no room for the pelt" in t for t in arena.echoed)
    assert not any(c.startswith("drop") for c in arena.sent)


def test_without_a_rope_the_skin_is_stowed_and_the_run_says_so_once(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda arena: None), (KILL, kill)],
            "tap": [NOT_FOUND],
            "skin": [(PELT_LOOSE, skin_in_hand), (PELT_LOOSE, skin_in_hand)],
            "get my rope": [MISSING],
            "search": [NOTHING, NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING | {"max_kills": 2}, travel_first=False)
    assert "get my rope from my sack" in arena.sent
    assert arena.sent.count("get my rope from my sack") == 1
    assert arena.sent.count("put my pelt in my sack") == 2
    assert sum("no bundling rope" in text for text in arena.echoed) == 1


def test_an_attack_from_range_waits_for_melee_before_the_next(travel):
    # Captured 2026-09-12: ATTACK beyond melee advances first, and a
    # second ATTACK meanwhile only answers "already advancing".
    advancing = (
        "You aren't close enough to attack.\nYou begin to advance on a ship's rat."
    )
    arena = Arena(
        {
            "attack": [advancing, (KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena, profile=PROFILE | {"max_kills": 1}, travel_first=False)
    assert arena.sent.count("attack rat") == 2
    assert not any("unrecognized" in text for text in arena.echoed)


def test_the_weapon_stays_in_hand_at_every_end(travel):
    # A stowed weapon parries nothing: the stop word among three live
    # rats stowed the handaxe and left him taking bites (2026-09-12).
    # Home or not, hostiles or not, the hunt ends with it in hand.
    for profile, hostiles_left in (
        (PROFILE | {"home": "", "max_kills": 1}, True),
        (PROFILE | {"max_kills": 1}, False),
    ):
        effect = (lambda arena: None) if hostiles_left else kill
        arena = Arena(
            {"attack": [(KILL, effect)], "skin": [SKINNED], "search": [NOTHING]}
        )
        _run(arena, profile=profile, travel_first=False)
        assert not any(command.startswith("put my handaxe") for command in arena.sent)


def test_a_corpse_that_keeps_answering_ends_the_room_not_the_evening(travel):
    # 2026-09-05: the hostile state still listed the corpse and the loop
    # swung at it five times. Disposed of once, then the room is clear.
    # The hostile state never empties here, so each room is declared
    # clear after CORPSE_SWINGS + 1 swings and the ground is lapped
    # until the pause, where the operator's word ends it.
    arena = Patient({"attack": [RAT_CORPSE] * 100, "search": [NOTHING] * 100})
    _run(arena, profile=PROFILE | {"skin": False}, travel_first=False)
    assert "search rat" in arena.sent
    rooms_visited = hunt.EMPTY_LAPS * len(GROUND.rooms_tagged("rats")) + 1
    assert arena.sent.count("attack rat") <= (hunt.CORPSE_SWINGS + 1) * rooms_visited
    assert any("only a corpse answers" in text for text in arena.echoed)
    assert any("ground empty" in text for text in arena.echoed)


def test_kill_and_item_nouns_are_read_from_the_game_lines():
    assert hunt.kill_noun("The cougar falls to the ground and lies still.") == "cougar"
    assert hunt.kill_noun("The cougar slowly tips over and falls down.") is None
    assert hunt.kill_noun(RAT_KILL) == "rat"
    assert hunt._DEAD_NOUN.search(RAT_CORPSE).group(2) == "rat"
    assert hunt.kill_noun("A large rat goes still.") == "rat"
    assert hunt.kill_noun("You miss.") is None
    assert hunt.items_in("You skin the rat, obtaining a rat pelt.") == ["pelt"]
    assert hunt.items_in(PELT_LOOSE) == ["pelt"]
    assert hunt.items_in(TAIL_REMOVED) == ["tail"]
    assert hunt.items_in("You find a small ruby. You find some coins.") == [
        "ruby",
        "coins",
    ]
    # The corpse's pockets, captured on the vineyard grendels (#292): the
    # gem is the item, the coins after it are not (GET COINS is #291).
    for line, item in (
        (
            "The grendel was carrying some waermodi stones, 7 copper coins "
            "(Kronars), and 1 bronze coin (Dokora)!",
            "stones",
        ),
        (
            "The grendel was carrying an ilmenite runestone, 9 copper coins "
            "(Kronars), and 1 bronze coin (Dokora)!",
            "runestone",
        ),
        (
            "The grendel was carrying a shining calavarite runestone, 4 copper "
            "coins (Lirums), and 2 bronze coins (Dokoras)!",
            "runestone",
        ),
    ):
        assert hunt.items_in("You search the small grendel.\n" + line) == [item], line
