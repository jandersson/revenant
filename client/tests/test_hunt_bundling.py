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
            "loot": [NOTHING],
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
    assert after_skin[0] == "loot"  # nothing stowed, nothing bundled by hand
    assert any("1 kill(s), 1 skin(s)" in text for text in arena.echoed)


def test_the_first_skin_starts_the_bundle_and_wears_it(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": [NOT_FOUND],
            "skin": [(PELT_LOOSE, skin_in_hand)],
            "get my bundling rope": [
                "You get a bundling rope from inside your canvas sack."
            ],
            "bundle": [(BUNDLED, hand_empty)],
            "loot": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    first = arena.sent.index("skin rat")
    assert arena.sent[first : first + 7] == [
        "skin rat",
        "sheathe my handaxe in my sack",
        "get my bundling rope from my sack",
        "bundle",
        "wear my bundle",
        "wield my handaxe",
        "loot",
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
            "loot": [NOTHING],
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
                "loot": [NOTHING],
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
            "get my bundling rope": [
                "You get a bundling rope from inside your canvas sack."
            ]
            * 2,
            "bundle": [full, (BUNDLED, hand_empty)],
            "loot": [NOTHING] * 2,
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("get my bundling rope from my sack") == 2
    assert any("would not take that skin" in t for t in arena.echoed)
    assert any("bundle started and worn" in t for t in arena.echoed)
    assert not any("unrecognized" in t for t in arena.echoed)


def test_a_run_bundle_refuses_three_times_stows_its_skins_loose(travel):
    # 2026-10-01: GET MY ROPE took a looted lead rope ("Only bundling
    # ropes can be utilized, not lead ropes", BUNDLE HELP), and BUNDLE
    # answered "full" for every one of 73 skins, each a sheathe, a GET,
    # a BUNDLE and a wield in the fight. Three in a row end the tries.
    full = (
        "Where did you intend to put that?  You don't have any bundles or "
        "they're all full or too tightly packed!  Type BUNDLE HELP for more details."
    )
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 4 + [(KILL, kill)],
            "tap": [NOT_FOUND] * 5,
            "skin": [(PELT_LOOSE, skin_in_hand)] * 5,
            "get my bundling rope": [
                "You get some bundling rope from inside your canvas sack."
            ]
            * 5,
            "bundle": [full] * 5,
            "loot": [NOTHING] * 5,
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING | {"max_kills": 5}, travel_first=False)
    assert arena.sent.count("get my bundling rope from my sack") == 3
    assert "get my rope from my sack" not in arena.sent
    assert sum("refused 3 skins in a row" in t for t in arena.echoed) == 1
    assert arena.sent.count("put my pelt in my sack") == 5


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
                "loot": [NOTHING] * 2,
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
            "get my bundling rope": [MISSING],
            "loot": [NOTHING, NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING | {"max_kills": 2}, travel_first=False)
    assert "get my bundling rope from my sack" in arena.sent
    assert arena.sent.count("get my bundling rope from my sack") == 1
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
            "loot": [NOTHING],
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
            {"attack": [(KILL, effect)], "skin": [SKINNED], "loot": [NOTHING]}
        )
        _run(arena, profile=profile, travel_first=False)
        assert not any(command.startswith("put my handaxe") for command in arena.sent)


def test_a_corpse_that_keeps_answering_ends_the_room_not_the_evening(travel):
    # 2026-09-05: the hostile state still listed the corpse and the loop
    # swung at it five times. Disposed of once, then the room is clear.
    # The hostile state never empties here, so each room is declared
    # clear after CORPSE_SWINGS + 1 swings and the ground is lapped
    # until the pause, where the operator's word ends it.
    arena = Patient({"attack": [RAT_CORPSE] * 100, "loot": [NOTHING] * 100})
    _run(arena, profile=PROFILE | {"skin": False}, travel_first=False)
    assert "loot" in arena.sent
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


# A S'lai scout's pockets, captured 2026-09-28: herbs are no gem, and a
# full pouch answers "There isn't any more room in the pouch for that."
POUCH_FULL_ANSWER = "There isn't any more room in the pouch for that.\n"


def _pocketing(monkeypatch, answers):
    from types import SimpleNamespace

    sent, echoed = [], []

    def ask(s, command, *_):
        sent.append(command)
        for prefix, answer in answers:
            if command.startswith(prefix):
                return answer
        return "You put it away.\n"

    monkeypatch.setattr(hunt, "ask", ask)  # act.ask, imported by name (#407)
    handle = SimpleNamespace(echo=echoed.append)
    profile = {"gem_pouch": "pouch", "loot_container": "sack"}
    return handle, profile, sent, echoed


def test_a_searched_herb_is_stowed_with_the_loot_not_pouched(monkeypatch):
    handle, profile, sent, _ = _pocketing(monkeypatch, [])
    hunt.pocket(handle, profile, "leaves")
    assert sent == ["get leaves", "put my leaves in my sack"]


def test_a_gem_the_full_pouch_refuses_is_stowed_and_said(monkeypatch):
    handle, profile, sent, echoed = _pocketing(
        monkeypatch, [("put my stones in my pouch", POUCH_FULL_ANSWER)]
    )
    hunt.pocket(handle, profile, "stones")
    assert sent == [
        "get stones",
        "put my stones in my pouch",
        "put my stones in my sack",
    ]
    assert any("pouch is full" in line for line in echoed)


def test_a_gem_the_pouch_takes_stays_there(monkeypatch):
    handle, profile, sent, _ = _pocketing(
        monkeypatch,
        [("put my stones in my pouch", "You put your stones in your gem pouch.\n")],
    )
    hunt.pocket(handle, profile, "stones")
    assert sent == ["get stones", "put my stones in my pouch"]


def test_a_searched_item_on_loot_ignore_is_left_where_it_fell():
    # 2026-09-28: "The scout was carrying an embroidery needle!" — the
    # wording path pocketed it though the profile's loot_ignore names it.
    answer = "You search the S'lai scout.\nThe scout was carrying an embroidery needle!"
    assert hunt.named(answer, "needle") == "embroidery needle"
    assert hunt.named("The grendel was carrying some waermodi stones!", "stones") == (
        "waermodi stones"
    )
    assert hunt.loot.ignored(hunt.named(answer, "needle"), ["embroidery needle"])
    assert not hunt.loot.ignored(
        hunt.named("The scout was carrying a sewing needle!", "needle"),
        ["embroidery needle"],
    )


def _almanac_hunt(monkeypatch, retreat, ready=True):
    from types import SimpleNamespace

    studied, sent = [], []
    monkeypatch.setattr(hunt.almanac, "ready", lambda noun: ready and bool(noun))
    monkeypatch.setattr(
        hunt.almanac, "study", lambda s, noun, ask, prefix: studied.append(prefix)
    )

    def ask(s, command, *_):
        sent.append(command)
        return retreat

    monkeypatch.setattr(hunt, "ask", ask)  # act.ask, imported by name (#407)
    monkeypatch.setattr(hunt, "probe", SimpleNamespace(collect=ask))
    state = SimpleNamespace(
        hostiles={"1": "a S'lai scout"},
        stunned=False,
        left_hand=None,
        right_hand={"noun": "mace"},
    )
    return SimpleNamespace(state=state), studied, sent


def test_a_clear_room_runs_the_interludes_with_the_weapon_kept(monkeypatch):
    from types import SimpleNamespace

    s, _, _ = _almanac_hunt(monkeypatch, "")
    ran = []
    monkeypatch.setattr(
        hunt,
        "interlude",
        SimpleNamespace(run_due=lambda s, make_room=True: ran.append(make_room)),
    )
    hunt.study_almanac(s)  # a scout still here: nothing
    s.state.hostiles = {}
    hunt.study_almanac(s)
    assert ran == [False]  # only with a hand already free


def test_mid_fight_the_almanac_is_studied_after_a_retreat_to_pole_range(
    monkeypatch,
):
    # The operator, 2026-09-28: keep the skill moving mid-fight too — retreat
    # to pole range, then study. Captured: "You retreat back to pole range."
    s, studied, sent = _almanac_hunt(monkeypatch, "You retreat back to pole range.\n")
    tally = hunt.Tally()
    assert hunt.study_in_fight(s, {"almanac": "almanac"}, tally) is True
    assert sent == ["retreat"] and studied == ["hunt"]


def test_a_refused_retreat_puts_the_study_off_and_the_fight_goes_on(monkeypatch):
    s, studied, sent = _almanac_hunt(
        monkeypatch, "You are unable to retreat from the S'lai scout!\n"
    )
    tally = hunt.Tally()
    assert hunt.study_in_fight(s, {"almanac": "almanac"}, tally) is False
    assert studied == [] and tally.almanac_retry > 0
    # Within the minute nothing is tried again.
    assert hunt.study_in_fight(s, {"almanac": "almanac"}, tally) is False
    assert sent == ["retreat"]


def test_no_mid_fight_study_stunned_hands_full_or_not_ready(monkeypatch):
    s, studied, sent = _almanac_hunt(monkeypatch, "You retreat back to pole range.\n")
    s.state.stunned = True
    assert not hunt.study_in_fight(s, {"almanac": "almanac"}, hunt.Tally())
    s.state.stunned = False
    s.state.left_hand = {"noun": "leaves"}
    assert not hunt.study_in_fight(s, {"almanac": "almanac"}, hunt.Tally())
    s, studied, sent = _almanac_hunt(monkeypatch, "", ready=False)
    assert not hunt.study_in_fight(s, {"almanac": "almanac"}, hunt.Tally())
    assert sent == [] and studied == []
