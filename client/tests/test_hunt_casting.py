"""How ;hunt casts: the profile's buffs kept up, the training cast on the
mana ramp with the cambrinth, and the debilitation cast at the prey —
one cast per swing at most, never idling for a pattern. Arena and
wordings: hunt_arena.py; the targeted attack spell is test_hunt_targeted.py."""

from client.game import buffs

from hunt_arena import (
    Arena,
    BUFFED,
    BUNDLING,
    CAST,
    DEBIL_OPEN,
    DISCERNED,
    KILL,
    NOTHING,
    PELT_LOOSE,
    PREPARED,
    PROFILE,
    SF_PREPARED,
    SKINNED,
    STUNNED,
    STUNNING,
    TRAINING,
    _exp,
    _hands,
    _run,
    _stands,
    hunt,
    kill,
    prepares,
)


# --- buffs -------------------------------------------------------------------


def test_with_a_walk_the_buffs_are_cast_before_it_not_among_the_prey(monkeypatch):
    # The operator, 2026-09-20: four casts on arrival were a minute
    # standing in the badgers' room. The walk itself is recorded in
    # `sent` here so the order shows; the Spells window then lists the
    # buff and the second pass casts nothing.
    def walk(s, db, goals, describe="", avoid=()):
        s.sent.append("<walk>")
        s.room = s.state.room = min(goals)
        s.state.active_spells = {"Heroic Strength": 9}
        return True

    monkeypatch.setattr(hunt, "walk", walk)
    monkeypatch.setattr(hunt, "locate", lambda db, state: state.room)
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [PREPARED],
            "cast": [CAST],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    arena.state.active_spells = {}
    _run(arena, profile=BUFFED | {"max_kills": 1})
    assert arena.sent[:4] == [
        "prepare heroic strength",
        "cast",
        "<walk>",
        "get my handaxe from my sack",
    ]
    assert arena.sent.count("cast") == 1


def test_buffs_are_cast_before_the_weapon_is_drawn(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [PREPARED],
            "cast": [CAST],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena, profile=BUFFED | {"max_kills": 1}, travel_first=False)
    assert arena.sent[:4] == [
        "prepare heroic strength",
        "cast",
        "get my handaxe from my sack",
        "stance set 100 80 0",
    ]
    assert arena.sent.count("cast") == 1  # no Spells window: the timer holds it
    assert "hunt: cast heroic strength" in arena.echoed


def test_a_buff_the_spells_window_lists_is_not_recast_until_it_runs_out(travel):
    def running(arena):
        arena.state.active_spells = {"Heroic Strength": 10}

    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED, PREPARED],
            "cast": [(CAST, running), (CAST, running)],
            "skin": [SKINNED, SKINNED],
            "search": [NOTHING, NOTHING],
        }
    )
    arena.state.active_spells = {}
    _run(arena, profile=BUFFED | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("cast") == 1

    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED, PREPARED],
            "cast": [CAST, CAST],
            "skin": [SKINNED, SKINNED],
            "search": [NOTHING, NOTHING],
        }
    )
    arena.state.active_spells = {}  # never lists it: at the start, then before each swing
    _run(arena, profile=BUFFED | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("cast") == 3


def test_a_buff_that_will_not_prepare_is_dropped_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": ["You don't know that spell."],
            "skin": [SKINNED],
            "search": [NOTHING],
        }
    )
    _run(arena, profile=BUFFED | {"max_kills": 1}, travel_first=False)
    assert "cast" not in arena.sent
    assert arena.sent.count("prepare heroic strength") == 1
    assert any("cannot prepare heroic strength" in text for text in arena.echoed)


# --- training casts ----------------------------------------------------------


STRAINED = (
    "You have to strain to harness the energy for this spell, and you aren't "
    "sure you can get enough to cast it.\n" + PREPARED
)


def test_training_casts_ramp_the_mana_between_swings(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED] * 5,
            "cast": [CAST] * 5,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 3}, travel_first=False)
    # One before the weapon, then one before each of the three swings:
    # the minimum first, then two more mana each time.
    assert prepares(arena) == [
        "prepare heroic strength",
        "prepare heroic strength 2",
        "prepare heroic strength 4",
        "prepare heroic strength 6",
    ]
    assert any("at minimum mana for Augmentation" in text for text in arena.echoed)


def test_the_strain_warning_caps_the_mana_one_step_under(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED, STRAINED, PREPARED, PREPARED],
            "cast": [CAST] * 4,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 3}, travel_first=False)
    assert prepares(arena) == [
        "prepare heroic strength",
        "prepare heroic strength 2",
        "prepare heroic strength",
        "prepare heroic strength",
    ]
    assert any("was too much (strained)" in text for text in arena.echoed)


def test_a_backfire_at_minimum_mana_ends_the_training_casts(travel):
    # Captured 2026-09-12: 5 mana "barely backfires" on a circle-1
    # Paladin. Below the minimum there is nowhere to go, so training
    # casts stop; the buff itself is still tried when it runs out.
    backfire = "You gesture.\nYour spell barely backfires."
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED] * 3,
            "cast": [backfire] * 3,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare heroic strength"] * 2
    assert any("training casts off" in text for text in arena.echoed)


# Captured 2026-09-14 on a round cambrinth flake (1 mana).
GOT_FLAKE = "You get a round cambrinth flake from inside your canvas sack."


CHARGED = (
    "You harness a small amount of energy and attempt to channel it into your "
    "cambrinth flake.\nYou are able to channel all the energy into the flake.\n"
    "The cambrinth flake absorbs all of the energy.\nRoundtime: 2 sec."
)


FLAKE_FULL = (
    "You are able to channel all the energy into the flake.\nThe cambrinth flake "
    "is already holding as much power as you could possibly charge it with.\n"
    "Your harnessed energy dissipates uselessly.\nRoundtime: 4 sec."
)


NOT_CHANNELLED = (
    "You harness a small amount of energy and attempt to channel it into your "
    "cambrinth armband.\nYou fail to channel any of the energy into the armband."
)


INVOKED = (
    "The cambrinth flake pulses with Holy energy.  You reach for its center and "
    "forge a magical link to it, readying all of its mana for your use.\n"
    "Roundtime: 1 sec."
)


SNAP_CAST = (
    "You gesture.\nYour cambrinth flake emits a loud *snap* as it discharges all "
    "its power to aid your spell.\nYour soul and body intertwine tighter, the "
    "bond renewed by the spell."
)


CAMBRINTH = TRAINING | {"cambrinth": "flake", "cambrinth_mana": 1}


def test_a_cambrinth_piece_is_charged_and_invoked_into_the_training_cast(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "get my flake": [GOT_FLAKE] * 3,
            "charge my flake": [CHARGED, FLAKE_FULL, FLAKE_FULL],
            "prepare": [PREPARED] * 4,
            "invoke my flake": [INVOKED] * 3,
            "cast": [CAST, SNAP_CAST, SNAP_CAST, SNAP_CAST],
            "stow my flake": ["You put your flake in your canvas sack."] * 3,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10) | {"Arcana": {"rank": 1, "percent": 36, "mindstate": 3}},
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=CAMBRINTH | {"max_kills": 2}, travel_first=False)
    first = arena.sent.index("get my flake")
    assert arena.sent[first : first + 6] == [
        "get my flake",
        "charge my flake 1",
        "prepare heroic strength",
        "invoke my flake",
        "cast",
        "stow my flake",
    ]
    # One training cast at the start and one before each of two swings;
    # the later ones found the flake still full, invoked all the same.
    assert arena.sent.count("charge my flake 1") == 3
    assert arena.sent.count("invoke my flake") == 3
    assert any("charged the flake with 1 mana for Arcana" in t for t in arena.echoed)
    assert any("(+flake)" in t for t in arena.echoed)


def test_a_piece_that_outranks_arcana_is_off_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "get my armband": [
                "You get a braided cambrinth armband from inside your sack."
            ],
            "charge my armband": [NOT_CHANNELLED],
            "prepare": [PREPARED] * 4,
            "cast": [CAST] * 4,
            "stow my armband": ["You put your armband in your canvas sack."],
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(
        arena,
        profile=CAMBRINTH
        | {"cambrinth": "armband", "cambrinth_mana": 3, "max_kills": 2},
        travel_first=False,
    )
    assert arena.sent.count("charge my armband 3") == 1
    assert "invoke my armband" not in arena.sent
    assert "stow my armband" in arena.sent
    assert any("outranks Arcana" in t for t in arena.echoed)
    assert len(prepares(arena)) >= 2  # the training casts go on without it


def test_cambrinth_alone_drives_the_training_cadence_until_arcana_locks(travel):
    profile = BUFFED | {"train_casting": "", "cambrinth": "flake", "cambrinth_mana": 1}
    for arcana, charges in ((3, 2), (34, 0)):  # the start, then before the swing
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "get my flake": [GOT_FLAKE] * 2,
                "charge my flake": [CHARGED, FLAKE_FULL],
                "prepare": [PREPARED] * 3,
                "invoke my flake": [INVOKED] * 2,
                "cast": [SNAP_CAST] * 3,
                "stow my flake": ["You put your flake in your canvas sack."] * 2,
                "skin": [SKINNED],
                "search": [NOTHING],
            },
            experience={"Arcana": {"rank": 1, "percent": 0, "mindstate": arcana}},
        )
        arena.state.vitals["mana"] = 100
        _run(arena, profile=profile | {"max_kills": 1}, travel_first=False)
        assert arena.sent.count("charge my flake 1") == charges, arcana


def test_the_profile_cast_gap_paces_the_training_casts(travel, monkeypatch):
    # #189: at a 20-second gap the first badger fight was seven swings
    # to the badger's 42, a cambrinth cycle being eight commands. The
    # profile's cast_gap (60 s by default) spaces the casts; 0 casts
    # before every swing.
    now = {"t": 1000.0}
    monkeypatch.setattr(buffs, "monotonic", lambda: now["t"])
    original_ask = hunt.ask

    def ask(s, command):
        now["t"] += 7  # every command costs a swing's worth of time
        return original_ask(s, command)

    monkeypatch.setattr(hunt, "ask", ask)
    casts = {}
    for gap in (0, 60):
        arena = Arena(
            {
                "attack": [(KILL, lambda a: None)] * 5 + [(KILL, kill)],
                "prepare": [PREPARED] * 9,
                "cast": [CAST] * 9,
                "skin": [SKINNED] * 6,
                "search": [NOTHING] * 6,
            },
            experience=_exp(10),
        )
        arena.state.vitals["mana"] = 100
        _run(
            arena,
            profile=TRAINING | {"cast_gap": gap, "max_kills": 6},
            travel_first=False,
        )
        casts[gap] = arena.sent.count("cast")
    assert casts[0] == 7  # before the weapon is drawn, then before every swing
    assert 1 < casts[60] < 4  # a kill is three commands, so one cast in three


def test_no_training_cast_at_lock_or_under_the_mana_floor(travel):
    for experience, mana in ((_exp(34), 100), (_exp(10), 20)):
        arena = Arena(
            {
                "attack": [(KILL, lambda a: None), (KILL, kill)],
                "prepare": [PREPARED] * 3,
                "cast": [CAST] * 3,
                "skin": [SKINNED] * 2,
                "search": [NOTHING] * 2,
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = mana
        _run(arena, profile=TRAINING | {"max_kills": 2}, travel_first=False)
        # The buff itself is still cast once (no Spells window: the timer holds it).
        assert prepares(arena) == ["prepare heroic strength"]


def test_a_bundle_worn_from_the_last_run_is_left_where_it_is(travel):
    # Captured 2026-09-12: the second bundled run began with a GET from
    # the sack that missed the bundle still on his shoulder; TAP says
    # "that you are wearing", and nothing needs fetching.
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "tap": ["You tap a lumpy bundle that you are wearing."],
            "skin": [PELT_LOOSE],
            "search": [NOTHING],
        }
    )
    _hands(arena)
    _run(arena, profile=BUNDLING, travel_first=False)
    assert arena.sent[:2] == ["tap my bundle", "get my handaxe from my sack"]
    assert "wear my bundle" not in arena.sent
    after_skin = arena.sent[arena.sent.index("skin rat") + 1 :]
    assert after_skin[0] == "search rat"
    assert "hunt: bundle worn — skins go straight into it" in arena.echoed


# --- debilitation ------------------------------------------------------------


def test_the_debilitation_spell_is_cast_at_the_prey_before_the_swing(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, _stands), (KILL, kill)],
            "prepare": [SF_PREPARED] * 3,
            "cast": [STUNNED] * 3,
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 3}, travel_first=False)
    # DISCERN first, before the weapon is drawn (#202); the cast in the fight.
    # PREPARE, the swing while the pattern forms (its kill skinned and
    # searched, the pattern holding), CAST (#203).
    assert arena.sent[:5] == [
        "discern stun foe",
        "get my handaxe from my sack",
        "stance set 100 80 0",
        "prepare stun foe",
        "attack rat",
    ]
    assert arena.sent.index("cast rat") < arena.sent.index("prepare stun foe 2")
    # The mana climbs a step per cast that took, like the training casts.
    assert prepares(arena) == [
        "prepare stun foe",
        "prepare stun foe 2",
        "prepare stun foe 4",
    ]
    assert any("for Debilitation" in text for text in arena.echoed)


def test_no_debilitation_cast_at_lock_under_the_mana_floor_or_with_no_spell(travel):
    locked = {"Debilitation": {"rank": 1, "percent": 0, "mindstate": 34}}
    for profile, experience, mana in (
        (STUNNING, locked, 100),
        (STUNNING, DEBIL_OPEN, 20),
        (PROFILE, DEBIL_OPEN, 100),
    ):
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "prepare": [SF_PREPARED],
                "cast": [STUNNED],
                "skin": [SKINNED],
                "search": [NOTHING],
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = mana
        _run(arena, profile=profile | {"max_kills": 1}, travel_first=False)
        assert prepares(arena) == []


def test_a_collapse_at_minimum_mana_turns_the_debilitation_spell_off(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [SF_PREPARED] * 2,
            "cast": ["You gesture.\nYour spell barely backfires."] * 2,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare stun foe"]
    assert any("off for this run" in text for text in arena.echoed)


def test_the_debilitation_and_training_casts_take_turns(travel):
    # Both due before every swing (cast_gap 0): the buff trains first,
    # the stun takes the next swing, and so on — never two casts before
    # one swing.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "prepare": [PREPARED, SF_PREPARED, PREPARED, SF_PREPARED],
            "cast": [CAST, STUNNED, CAST, STUNNED],
            "skin": [SKINNED] * 3,
            "search": [NOTHING] * 3,
        },
        experience=_exp(10) | DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(
        arena,
        profile=TRAINING | {"debilitation": "stun foe", "max_kills": 3},
        travel_first=False,
    )
    assert prepares(arena) == [
        "prepare heroic strength",  # before the weapon is drawn
        "prepare stun foe",  # swing 1: the buff went last, the stun's turn
        "prepare heroic strength 2",  # swing 2
        "prepare stun foe 2",  # swing 3
    ]


# --- the injuries panel as the wound floor's pre-check (#163) ----------------


def test_a_clean_injuries_panel_skips_health_and_a_lit_one_asks(travel):
    # The game pushes the panel on every change, so an empty one means
    # nothing is hurt and HEALTH need not be asked after the kill.
    arena = Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "search": [NOTHING]})
    arena.state.injuries = {}
    _run(arena, profile=PROFILE | {"wound_floor": "harmful"}, travel_first=False)
    assert "health" not in arena.sent

    lit = Arena(
        {
            "attack": [(KILL, kill)],
            "skin": [SKINNED],
            "search": [NOTHING],
            "health": [
                "Your body feels at full strength.\nYou have no significant injuries."
            ],
        }
    )
    lit.state.injuries = {"head": ("wound", 1)}
    _run(lit, profile=PROFILE | {"wound_floor": "harmful"}, travel_first=False)
    assert "health" in lit.sent


def test_a_worn_cambrinth_piece_is_removed_for_the_charge_and_worn_again(travel):
    # The anklet (2026-09-20): worn between casts, since a worn piece
    # refuses a charge, so the cycle is REMOVE, CHARGE, PREPARE, INVOKE,
    # CAST, WEAR instead of GET ... STOW.
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "remove my anklet": [
                "You remove a simple cambrinth anklet from your ankle.\n"
            ]
            * 3,
            "charge my anklet": [CHARGED.replace("flake", "anklet")] * 3,
            "prepare": [PREPARED] * 4,
            "invoke my anklet": [INVOKED.replace("flake", "anklet")] * 3,
            "cast": [CAST, SNAP_CAST, SNAP_CAST, SNAP_CAST],
            "wear my anklet": ["You attach a simple cambrinth anklet to your ankle.\n"]
            * 3,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10) | {"Arcana": {"rank": 17, "percent": 0, "mindstate": 3}},
    )
    arena.state.vitals["mana"] = 100
    worn = TRAINING | {
        "cambrinth": "anklet",
        "cambrinth_mana": 12,
        "cambrinth_worn": True,
    }
    _run(arena, profile=worn | {"max_kills": 2}, travel_first=False)
    first = arena.sent.index("remove my anklet")
    assert arena.sent[first : first + 6] == [
        "remove my anklet",
        "charge my anklet 12",
        "prepare heroic strength",
        "invoke my anklet",
        "cast",
        "wear my anklet",
    ]
    assert "get my anklet" not in arena.sent and "stow my anklet" not in arena.sent


def test_a_worn_piece_found_in_the_sack_is_got_instead_and_worn_back(travel):
    # 2026-09-20 in the badgers' room, after a death and a raising: the
    # anklet was in the sack, REMOVE answered "Remove what?", the charge
    # went out anyway and the game said "You'll have to hold it, set it
    # on the ground, or put it on something first."
    unheld = (
        "You'll have to hold it, set it on the ground, or put it on something first.\n"
    )
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, kill)],
            "remove my anklet": [
                "Remove what?\n",
                "You remove a simple cambrinth anklet from your ankle.\n",
            ]
            + ["You remove a simple cambrinth anklet from your ankle.\n"] * 4,
            "get my anklet": [
                "You get a simple cambrinth anklet from inside your canvas sack.\n"
            ]
            * 4,
            "charge my anklet": [
                CHARGED.replace("flake", "anklet"),
                unheld,
                CHARGED.replace("flake", "anklet"),
            ]
            + [CHARGED.replace("flake", "anklet")] * 4,
            "prepare": [PREPARED] * 8,
            "invoke my anklet": [INVOKED.replace("flake", "anklet")] * 6,
            "cast": [CAST] + [SNAP_CAST] * 6,
            "wear my anklet": ["You attach a simple cambrinth anklet to your ankle.\n"]
            * 6,
            "skin": [SKINNED] * 2,
            "search": [NOTHING] * 2,
        },
        experience=_exp(10) | {"Arcana": {"rank": 17, "percent": 0, "mindstate": 3}},
    )
    arena.state.vitals["mana"] = 100
    worn = TRAINING | {
        "cambrinth": "anklet",
        "cambrinth_mana": 12,
        "cambrinth_worn": True,
    }
    _run(arena, profile=worn | {"max_kills": 2}, travel_first=False)
    first = arena.sent.index("remove my anklet")
    # Not worn: GET it, charge, cast, WEAR it — on the ankle from now on.
    assert arena.sent[first : first + 7] == [
        "remove my anklet",
        "get my anklet",
        "charge my anklet 12",
        "prepare heroic strength",
        "invoke my anklet",
        "cast",
        "wear my anklet",
    ]
    # The next cycle's charge finds nothing in hand: once more from the
    # container, then the charge again.
    second = arena.sent.index("remove my anklet", first + 1)
    assert arena.sent[second : second + 5] == [
        "remove my anklet",
        "charge my anklet 12",
        "get my anklet",
        "charge my anklet 12",
        "prepare heroic strength 2",  # the training ramp's second step
    ]
    assert not [text for text in arena.echoed if "unrecognized" in text]
    assert not [text for text in arena.echoed if "cambrinth off" in text]
