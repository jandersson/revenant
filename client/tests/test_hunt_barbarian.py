"""A Barbarian's hunt (#328): the self-combo's attacks take the place of
ATTACK while Expertise is unlocked, never on the fists turn; the
profile's abilities go up before the walk; a roar goes out at the prey.
Arena and wordings: hunt_arena.py; the Barbarian answers are
dr-scripts' (client/game/barbarian.py), uncaptured."""

from hunt_arena import (
    GROUND,
    KILL,
    NOTHING,
    PROFILE,
    SKINNED,
    Arena,
    _run,
    _stands,
    hunt,
    kill,
)

from client.game import barbarian

COMBO = "You reveal a weakness in your stance by landing a jab, a feint and a slice."
EXPERTISE_OPEN = {"Expertise": {"rank": 4, "percent": 0, "mindstate": 1}}
ANALYZING = PROFILE | {"analyze": "flame"}


def test_the_combos_attacks_take_the_place_of_attack(travel):
    arena = Arena(
        {
            "analyze flame": [COMBO] * 3,
            "jab": [(KILL, _stands)] * 3,
            "feint": [(KILL, _stands)] * 3,
            "slice": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "attack": [(KILL, kill)] * 3,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
        },
        experience=EXPERTISE_OPEN,
    )
    _run(arena, profile=ANALYZING | {"max_kills": 6}, travel_first=False)
    swings = [
        c
        for c in arena.sent
        if c.split()[0] in ("analyze", "jab", "feint", "slice", "attack")
    ]
    assert swings[:8] == [
        "analyze flame",
        "jab rat",
        "feint rat",
        "slice rat",
        "analyze flame",
        "jab rat",
        "feint rat",
        "slice rat",
    ]
    assert "attack rat" not in swings[:8]
    assert any("self-combo(s)" in text for text in arena.echoed)
    assert not any("unrecognized" in text for text in arena.echoed)


def test_no_combo_once_expertise_locks_or_without_the_profile(travel):
    locked = {"Expertise": {"rank": 4, "percent": 0, "mindstate": 34}}
    for profile, experience in ((ANALYZING, locked), (PROFILE, EXPERTISE_OPEN)):
        arena = Arena(
            {
                "analyze flame": [COMBO] * 3,
                "attack": [(KILL, kill)] * 3,
                "skin": [SKINNED] * 9,
                "loot": [NOTHING] * 9,
            },
            experience=experience,
        )
        _run(arena, profile=profile | {"max_kills": 2}, travel_first=False)
        assert not any(c.startswith("analyze") for c in arena.sent)
        assert "attack rat" in arena.sent


def test_the_fists_turn_swings_its_brawling_not_the_combo(travel):
    arena = Arena(
        {
            "analyze flame": [COMBO] * 3,
            "punch": [(KILL, kill)] * 3,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
        },
        experience=EXPERTISE_OPEN
        | {"Brawling": {"rank": 4, "percent": 0, "mindstate": 1}},
    )
    fists = ANALYZING | {
        "weapons": ["fists:Brawling"],
        "brawling": ["punch"],
        "max_kills": 2,
    }
    _run(arena, profile=fists, travel_first=False)
    assert not any(c.startswith("analyze") for c in arena.sent)
    assert "punch rat" in arena.sent


def test_an_ability_goes_up_before_the_walk_and_a_roar_at_the_prey(travel):
    took = "The " + barbarian.ABILITIES["Avalanche"][2] + "!"
    arena = Arena(
        {
            "berserk avalanche": [took],
            "roar anger": ["You let loose a mighty roar at the rat!"] * 3,
            "attack": [(KILL, _stands), (KILL, kill)],
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
        },
        experience={"Debilitation": {"rank": 1, "percent": 0, "mindstate": 0}},
    )
    _run(
        arena,
        profile=PROFILE | {"abilities": ["Avalanche"], "roar": "anger", "max_kills": 1},
    )
    assert arena.sent.index("berserk avalanche") < arena.sent.index("attack rat")
    assert arena.walks  # the walk came after it
    assert arena.sent.count("berserk avalanche") == 1  # running: not again
    roars = [c for c in arena.sent if c.startswith("roar")]
    assert roars == ["roar anger at rat"]  # once a minute, the clock frozen
    assert GROUND  # the shared ground, unchanged
    assert hunt.barbarian is barbarian
