"""How ;hunt casts the profile's targeted spell at the prey (#200):
DISCERNed once, TARGETed and PREPAREd under the swing's roundtime, cast
after the last swing or RELEASEd when the prey went down first, and off
for the run when the ranks cannot carry it. Arena and wordings:
hunt_arena.py."""

from types import SimpleNamespace
from client.game import buffs

from hunt_arena import (
    Arena,
    BUFFED,
    CAST,
    DEBIL_OPEN,
    DISCERNED,
    KILL,
    LIFELESS,
    MISSED,
    NOTHING,
    PREPARED,
    PROFILE,
    SF_PREPARED,
    SKINNED,
    STUNNED,
    STUNNING,
    TRAINING,
    _exp,
    _run,
    _stands,
    hunt,
    kill,
    prepares,
)


# --- targeted magic ----------------------------------------------------------


# Footman's Strike (#200): the cast line is the wiki's "You gesture at
# <target> with your <weapon>." until captured; the hit, resist and
# unarmed-failure wordings are still to capture.
STRUCK = "You gesture at a rat with your handaxe."


FS_PREPARED = "You begin chanting a prayer to invoke the Footman's Strike spell."


STRIKING = PROFILE | {"targeted": "footman's strike"}


# TARGET's wordings are the wiki's until captured (#203).
TARGETING = "You begin to weave mana lines into a target pattern around a rat."


# The operator's DISCERN, captured 2026-09-18 (#203): the description,
# the rank the spell wants, the refusal, 13 seconds of roundtime.
DISCERN_REFUSED = (
    "Footman's Strike draws on the caster's melee weapon in hand as a focus for "
    "the spell, which dictates the shape of its manifestation.\n\nThis is a "
    "targeted spell, which must be TARGETed at a specific opponent.  This spell "
    "does slice and impact damage.  It requires a minimum of two mana streams, "
    "and can expand to a maximum of fifty mana streams woven into it.  To begin "
    "to be able to cast this spell, you will need to reach the rank of a "
    "promising novice.  By the time you have mastered this spell, you will be "
    "ranked as a genius in your abilities as a caster.  It requires the Targeted "
    "Magic skill to cast effectively.\n\nYou don't think you are able to cast "
    "this spell.\nRoundtime: 13 sec."
)


TM_OPEN = {"Targeted Magic": {"rank": 1, "percent": 0, "mindstate": 5}}


TM_LOCKED = {"Targeted Magic": {"rank": 1, "percent": 0, "mindstate": 34}}


def test_the_targeted_spell_is_cast_at_the_prey_before_the_swing(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, _stands), (KILL, kill)],
            "prepare": [FS_PREPARED] * 3,
            "cast": [STRUCK] * 3,
            "skin": [SKINNED] * 3,
            "loot": [NOTHING] * 3,
            "discern": [DISCERNED],
            "target": [TARGETING] * 3,
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 3}, travel_first=False)
    # Only in the fight, the weapon drawn: the spell takes it as its focus.
    # Targeted magic: PREPARE, TARGET the prey, the swing while the
    # pattern forms, CAST at the pattern (#203).
    assert arena.sent[:6] == [
        "discern footman's strike",
        "wield my handaxe",
        "stance set 100 80 0",
        "prepare footman's strike",
        "target rat",
        "attack rat",
    ]
    assert arena.sent.index("cast") < arena.sent.index("prepare footman's strike 2")
    assert "cast rat" not in arena.sent
    assert prepares(arena) == [
        "prepare footman's strike",
        "prepare footman's strike 2",
        "prepare footman's strike 4",
    ]
    assert any("for Targeted Magic" in text for text in arena.echoed)


def test_no_targeted_cast_at_lock_under_the_mana_floor_or_with_no_spell(travel):
    for profile, experience, mana in (
        (STRIKING, TM_LOCKED, 100),
        (STRIKING, TM_OPEN, 20),
        (PROFILE, TM_OPEN, 100),
    ):
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "prepare": [FS_PREPARED],
                "cast": [STRUCK],
                "skin": [SKINNED],
                "loot": [NOTHING],
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = mana
        _run(arena, profile=profile | {"max_kills": 1}, travel_first=False)
        assert prepares(arena) == []


def test_each_targeted_slot_is_gated_on_its_own_skill(travel):
    # Debilitation locked, Targeted Magic open: the strike goes out and
    # the stun stays home — and the other way round.
    both = STRIKING | {"debilitation": "stun foe", "max_kills": 1}
    for experience, expected in (
        (DEBIL_OPEN | TM_LOCKED, ["prepare stun foe"]),
        (
            {"Debilitation": {"rank": 1, "percent": 0, "mindstate": 34}} | TM_OPEN,
            ["prepare footman's strike"],
        ),
    ):
        arena = Arena(
            {
                "attack": [(KILL, kill)],
                "prepare": [SF_PREPARED, FS_PREPARED],
                "cast": [STUNNED, STRUCK],
                "skin": [SKINNED],
                "loot": [NOTHING],
            },
            experience=experience,
        )
        arena.state.vitals["mana"] = 100
        _run(arena, profile=both, travel_first=False)
        assert prepares(arena) == expected


def test_a_collapse_at_minimum_mana_turns_the_targeted_spell_off(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [FS_PREPARED] * 2,
            "cast": ["You gesture.\nYour spell barely backfires."] * 2,
            "skin": [SKINNED] * 2,
            "loot": [NOTHING] * 2,
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare footman's strike"]
    assert any("off for this run" in text for text in arena.echoed)


def test_the_buff_debilitation_and_targeted_casts_take_turns(travel):
    # All three due before every swing (cast_gap 0): the buff trains
    # before the weapon is drawn, then stun, strike, buff, stun, strike
    # — never two casts before one swing.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 4 + [(KILL, kill)],
            "prepare": [PREPARED, SF_PREPARED, FS_PREPARED] * 2,
            "cast": [CAST, STUNNED, STRUCK] * 2,
            "skin": [SKINNED] * 5,
            "loot": [NOTHING] * 5,
        },
        experience=_exp(10) | DEBIL_OPEN | TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(
        arena,
        profile=TRAINING
        | {"debilitation": "stun foe", "targeted": "footman's strike", "max_kills": 5},
        travel_first=False,
    )
    assert prepares(arena) == [
        "prepare heroic strength",  # before the weapon is drawn
        "prepare stun foe",  # swing 1
        "prepare footman's strike",  # swing 2
        "prepare heroic strength 2",  # swing 3
        "prepare stun foe 2",  # swing 4
        "prepare footman's strike 2",  # swing 5
    ]


# Captured 2026-09-18 (#202): Footman's Strike, a basic spell, at
# Targeted Magic rank 1.
LACKING = (
    "You gesture at a rat with your handaxe.\nCurrently lacking the skill to "
    "complete the pattern, your spell fails completely."
)


TM_RANK_1 = {"Targeted Magic": {"rank": 1, "percent": 0, "mindstate": 0}}


def test_a_strike_the_ranks_cannot_carry_is_off_for_the_run_with_the_rank_named(
    travel,
):
    # The loop used to take "fails completely" for a cast that landed,
    # step the mana up and prepare it again every rotation.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 3 + [(KILL, kill)],
            "prepare": [FS_PREPARED] * 4,
            "cast": [LACKING] * 4,
            "skin": [SKINNED] * 4,
            "loot": [NOTHING] * 4,
            "discern": [DISCERNED],
        },
        experience=TM_RANK_1,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 4}, travel_first=False)
    assert prepares(arena) == ["prepare footman's strike"]
    assert any(
        "footman's strike fails for lack of Targeted Magic ranks (1) — off for this run"
        in text
        for text in arena.echoed
    )
    assert not any("for Targeted Magic" in text for text in arena.echoed)


def test_discern_saying_no_spares_the_prepare_and_names_the_rank(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [FS_PREPARED] * 2,
            "cast": [LACKING] * 2,
            "skin": [SKINNED] * 2,
            "loot": [NOTHING] * 2,
            "discern": [DISCERN_REFUSED],
        },
        experience=TM_RANK_1,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 2}, travel_first=False)
    assert arena.sent.count("discern footman's strike") == 1
    assert prepares(arena) == []
    assert any(
        "DISCERN says footman's strike needs Targeted Magic 10 (promising novice); "
        "Targeted Magic is 1 — off for this run" in text
        for text in arena.echoed
    )


def test_rank_floor_reads_the_title_discern_names():
    assert buffs.rank_floor(DISCERN_REFUSED) == (10, "promising novice")
    assert buffs.rank_floor("reach the rank of a lowly novice.") == (1, "lowly novice")
    assert buffs.rank_floor("reach the rank of an adept.") == (200, "adept")
    assert buffs.rank_floor("You don't think you are able to cast this spell.") is None


def test_the_swing_goes_out_while_the_training_cast_prepares(travel):
    # cast_gap 0: the buff trains before every swing — PREPARE, the
    # swing, CAST, never a swing on its own while a cast is due (#203).
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "prepare": [PREPARED] * 4,
            "cast": [CAST] * 4,
            "skin": [SKINNED] * 3,
            "loot": [NOTHING] * 3,
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 3}, travel_first=False)
    fight = arena.sent[arena.sent.index("stance set 100 80 0") + 1 :]
    casts = [c for c in fight if c.split()[0] in ("prepare", "attack", "cast")]
    assert casts == [
        "prepare heroic strength 2",
        "attack rat",
        "cast",
        "prepare heroic strength 4",
        "attack rat",
        "cast",
        "prepare heroic strength 6",
        "attack rat",
        "cast",
    ]


def _pattern(seconds):
    """A PREPARE answered with the game's castTime tag: the pattern is
    ready `seconds` of server time after the prepare."""

    def effect(arena):
        arena.state.casttime = arena.state.server_time + seconds

    return effect


def _clocked(arena):
    """The Arena on the server's clock, the way buffs.cast_left reads a
    pattern: every ATTACK is a 4 s swing roundtime gone by."""
    arena.state.server_time = 100
    arena.state.casttime = 0
    original = arena.put

    def put(command):
        original(command)
        if command.startswith("attack"):
            arena.state.server_time += 4

    arena.put = put
    return arena


def _casts(arena):
    fight = arena.sent[arena.sent.index("stance set 100 80 0") + 1 :]
    return [c for c in fight if c.split()[0] in ("prepare", "attack", "cast")]


def test_a_long_pattern_is_swung_into_until_a_roundtime_no_longer_fits(travel):
    # #250: Heroic Strength's pattern formed for 26 s (the castTime tag
    # captured 2026-09-20), one 4 s swing filled it, and the hunt stood
    # the other 22 under the badger. A 14 s pattern here: swings at 100,
    # 104 and 108 (2 s left after the third, no room for a fourth), then
    # the CAST — the kill under the third swing releases nothing, the
    # buff is a self-cast.
    arena = _clocked(
        Arena(
            {
                "attack": [MISSED, MISSED, (KILL, kill)],
                "prepare": [(PREPARED, _pattern(14))],
                "cast": [CAST],
                "skin": [SKINNED],
                "loot": [NOTHING],
            },
            experience=_exp(10),
        )
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 1}, travel_first=False)
    assert _casts(arena) == [
        "prepare heroic strength 2",
        "attack rat",
        "attack rat",
        "attack rat",
        "cast",
    ]
    assert "release" not in arena.sent


def test_the_pattern_is_still_forming_on_the_second_its_timer_names():
    # #263: cast time 119 with the last prompt at 119 is a fraction of a
    # second short of ready — the CAST sent then read the ready line as
    # its answer. One second stays; past the second, nothing.
    state = SimpleNamespace(server_time=119, casttime=119)
    assert buffs.cast_left(SimpleNamespace(state=state)) == 1
    state.server_time = 120
    assert buffs.cast_left(SimpleNamespace(state=state)) == 0
    state.server_time = 100
    assert buffs.cast_left(SimpleNamespace(state=state)) == 20


def test_a_battle_spells_pattern_gets_the_one_swing(travel):
    # Stun Foe forms in 7 s: the first swing's roundtime leaves 3 (and
    # the boundary second, #263), no room for another — the one-swing
    # cadence of #203 stands, and the kill comes on the next iteration's
    # own swing.
    arena = _clocked(
        Arena(
            {
                "attack": [MISSED, (KILL, kill)],
                "prepare": [(SF_PREPARED, _pattern(7))],
                "cast": [STUNNED],
                "skin": [SKINNED],
                "loot": [NOTHING],
                "discern": [DISCERNED],
            },
            experience=DEBIL_OPEN,
        )
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert _casts(arena)[:3] == ["prepare stun foe", "attack rat", "cast rat"]


# Captured 2026-09-20 at 20:28 (#252): the filler CIRCLE killed the
# badger, the parser kept it listed, and the CAST, the next PREPARE and
# its TARGET each answered on the pattern still held.
POINTLESS = "The striped badger is already dead, so that's a bit pointless."


HELD = "You have already fully prepared the Stun Foe spell!"


UNTARGETABLE = "This spell cannot be targeted."


def _casting(arena):
    fight = arena.sent[arena.sent.index("stance set 100 80 0") + 1 :]
    return [
        c
        for c in fight
        if c.split()[0] in ("prepare", "target", "attack", "cast", "release")
    ]


def test_a_solo_kill_under_the_filler_clears_the_room_though_the_parser_lags(travel):
    # The kill line arrives; the dead badger's status frame never does
    # (#244), so the parser's set still lists it. One listed and it just
    # fell: the pattern aimed at it is released, never cast at a corpse.
    arena = Arena(
        {
            "attack": [(KILL, lambda arena: None)],
            "prepare": [SF_PREPARED],
            "cast": [STUNNED],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert "release" in arena.sent
    assert "cast rat" not in arena.sent
    assert any("stun foe released" in text for text in arena.echoed)


def test_a_cast_answered_already_dead_releases_the_held_pattern(travel):
    arena = Arena(
        {
            "attack": [MISSED, (KILL, kill)],
            "prepare": [SF_PREPARED, SF_PREPARED],
            "cast": [POINTLESS],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert _casting(arena)[:4] == [
        "prepare stun foe",
        "attack rat",
        "cast rat",
        "release",
    ]
    assert any("stun foe released" in text for text in arena.echoed)


def test_a_prepare_refused_for_a_held_pattern_releases_it_and_prepares_again(travel):
    arena = Arena(
        {
            "attack": [MISSED, (KILL, kill)],
            "prepare": [HELD, SF_PREPARED],
            "cast": [STUNNED],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert _casting(arena)[:5] == [
        "prepare stun foe",
        "release",
        "prepare stun foe",
        "attack rat",
        "cast rat",
    ]
    assert any("cast stun foe at rat" in text for text in arena.echoed)


def test_a_target_refused_as_untargetable_releases_the_held_pattern(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [FS_PREPARED],
            "target": [UNTARGETABLE],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 1}, travel_first=False)
    assert _casting(arena)[:3] == ["prepare footman's strike", "target rat", "release"]
    assert "cast" not in arena.sent
    assert any(
        "the pattern held was not footman's strike — released" in text
        for text in arena.echoed
    )


GRENDEL_KILL = "A small grendel grunts and collapses."


def test_a_kill_line_with_a_verb_before_the_fall_names_the_creature():
    # #270: the first grendel of the vineyard hunt, 2026-09-21 — "and"
    # was skinned and searched.
    assert hunt.kill_noun(GRENDEL_KILL) == "grendel"
    assert hunt.kill_noun(KILL) == "rat"
    assert hunt.kill_noun(LIFELESS) == "cougar"


def test_with_prey_empty_the_grendel_is_skinned_and_the_stun_pattern_released(travel):
    # prey "" swings at whatever engages (grendels at night on the
    # cougars' ground): the kill noun comes off the kill line, and a
    # Stun Foe whose foe fell under the filler is released, never cast
    # at nothing afterwards (#271).
    arena = Arena(
        {
            "attack": [(GRENDEL_KILL, kill)],
            "prepare": [SF_PREPARED],
            "cast": [STUNNED],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"prey": "", "max_kills": 1}, travel_first=False)
    assert "skin grendel" in arena.sent and "loot" in arena.sent
    assert "release" in arena.sent
    assert "cast" not in arena.sent
    assert any("stun foe released" in text for text in arena.echoed)


def test_a_foe_down_under_the_filler_swing_releases_the_targeted_pattern(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [SF_PREPARED],
            "cast": [STUNNED],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert "release" in arena.sent
    assert "cast rat" not in arena.sent
    assert any("stun foe released" in text for text in arena.echoed)


def test_a_missing_target_releases_the_pattern_before_the_swing(travel):
    arena = Arena(
        {
            "attack": [(KILL, kill)],
            "prepare": [FS_PREPARED],
            "target": ["What were you referring to?"],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 1}, travel_first=False)
    assert arena.sent.index("release") < arena.sent.index("attack rat")
    assert "cast" not in arena.sent


def test_discern_goes_out_once_per_slot_and_not_for_an_empty_one(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "prepare": [SF_PREPARED] * 3,
            "cast": [STUNNED] * 3,
            "skin": [SKINNED] * 3,
            "loot": [NOTHING] * 3,
            "discern": [DISCERNED] * 3,
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 3}, travel_first=False)
    discerns = [c for c in arena.sent if c.startswith("discern")]
    assert discerns == ["discern stun foe"]


# DISCERN's estimate, captured 2026-09-20 on Stun Foe at Debilitation
# 15 and Footman's Strike at Targeted Magic 11: the game's own ceiling,
# which the ramp had climbed past (4 and 6 mana) and backfired five
# times in one evening — nerve wounds that dampen the casting after.
DISCERN_SF = (
    "The spell requires at minimum 1 mana streams and you think you can "
    "reinforce it with 2 more, for a total of 3 streams.\nRoundtime: 13 sec."
)


DISCERN_FS_MIN = (
    "The spell requires at minimum 2 mana streams and you think you can "
    "reinforce it with 0 more, for a total of 2 streams.\nRoundtime: 13 sec."
)


DISCERN_HS = (
    "The spell requires at minimum 1 mana streams and you think you can "
    "reinforce it with 3 more, for a total of 4 streams.\nRoundtime: 13 sec."
)


FS_CAST = (
    "You gesture at a rat with your handaxe.\nA stream of stark white light "
    "jumps from you to a rat, which warps into a spiraling force as it slams "
    "into it!"
)


TM_OPEN = {"Targeted Magic": {"rank": 11, "percent": 0, "mindstate": 5}}


def test_discerns_estimate_caps_the_debilitation_ramp(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 4 + [(KILL, kill)],
            "prepare": [SF_PREPARED] * 5,
            "cast": [STUNNED] * 5,
            "skin": [SKINNED] * 5,
            "loot": [NOTHING] * 5,
            "discern": [DISCERN_SF],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 5}, travel_first=False)
    assert prepares(arena)[:3] == [
        "prepare stun foe",
        "prepare stun foe 2",
        "prepare stun foe 3",
    ]
    assert set(prepares(arena)[3:]) == {"prepare stun foe 3"}  # never 4 again
    assert any("DISCERN caps stun foe at 3 mana (minimum 1)" in t for t in arena.echoed)


def test_an_estimate_at_the_minimum_pins_the_targeted_ramp_there(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "prepare": [FS_PREPARED] * 3,
            "target": [TARGETING] * 3,
            "cast": [FS_CAST] * 3,
            "skin": [SKINNED] * 3,
            "loot": [NOTHING] * 3,
            "discern": [DISCERN_FS_MIN],
        },
        experience=TM_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STRIKING | {"max_kills": 3}, travel_first=False)
    assert prepares(arena) == ["prepare footman's strike"] * 3
    assert any(
        "DISCERN caps footman's strike at 2 mana — the minimum, no ramp" in t
        for t in arena.echoed
    )


def test_the_training_buff_is_discerned_and_its_ramp_capped_too(travel):
    arena = Arena(
        {
            "attack": [(KILL, lambda a: None), (KILL, lambda a: None), (KILL, kill)],
            "prepare": [PREPARED] * 5,
            "cast": [CAST] * 5,
            "skin": [SKINNED] * 3,
            "loot": [NOTHING] * 3,
            "discern": [DISCERN_HS],
        },
        experience=_exp(10),
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=TRAINING | {"max_kills": 3}, travel_first=False)
    assert arena.sent.count("discern heroic strength") == 1
    assert prepares(arena) == [
        "prepare heroic strength",
        "prepare heroic strength 2",
        "prepare heroic strength 4",
        "prepare heroic strength 4",  # the estimate's total, not 6
    ]
    assert any(
        "DISCERN caps heroic strength at 4 mana (minimum 1)" in t for t in arena.echoed
    )
    assert buffs.mana_limit("You think you could weave at most 27 mana streams") is None
    assert (
        buffs.climb(0, None) == 2 and buffs.climb(2, 3) == 3 and buffs.climb(3, 3) == 3
    )
    assert buffs.climb(0, 0) == 0


def test_a_buff_the_ranks_cannot_carry_is_off_for_the_run(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, kill)],
            "prepare": [PREPARED] * 2,
            "cast": [
                "You gesture.\nCurrently lacking the skill to complete the pattern, your spell fails completely."
            ]
            * 2,
            "skin": [SKINNED] * 2,
            "loot": [NOTHING] * 2,
        }
    )
    _run(arena, profile=BUFFED | {"max_kills": 2}, travel_first=False)
    assert prepares(arena) == ["prepare heroic strength"]
    assert any(
        "heroic strength fails for lack of ranks — off for this run" in text
        for text in arena.echoed
    )


# Captured 2026-09-23 at 09:57 at the vineyard: the grendel died between
# the TARGET and the CAST; the pattern went, the spell stayed held.
DISSIPATED = (
    "Your target pattern dissipates because the small grendel is dead, but "
    "the main spell remains intact."
)


def test_a_cast_whose_target_pattern_dissipated_releases_the_held_spell(travel):
    arena = Arena(
        {
            "attack": [MISSED, (KILL, kill)],
            "prepare": [SF_PREPARED, SF_PREPARED],
            "cast": [DISSIPATED],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert _casting(arena)[:4] == [
        "prepare stun foe",
        "attack rat",
        "cast rat",
        "release",
    ]
    assert not any("unrecognized cast answer" in text for text in arena.echoed)


# Captured 2026-09-23 at 15:46: the grendel was dead and searched before
# the CAST, and the targeted spell, its pattern gone, went at the caster.
AT_YOURSELF = "You can't cast that at yourself!"


def test_a_cast_refused_at_yourself_releases_the_held_spell(travel):
    arena = Arena(
        {
            "attack": [MISSED, (KILL, kill)],
            "prepare": [SF_PREPARED, SF_PREPARED],
            "cast": [AT_YOURSELF],
            "skin": [SKINNED],
            "loot": [NOTHING],
            "discern": [DISCERNED],
        },
        experience=DEBIL_OPEN,
    )
    arena.state.vitals["mana"] = 100
    _run(arena, profile=STUNNING | {"max_kills": 1}, travel_first=False)
    assert _casting(arena)[:4] == [
        "prepare stun foe",
        "attack rat",
        "cast rat",
        "release",
    ]
    assert not any("unrecognized cast answer" in text for text in arena.echoed)
