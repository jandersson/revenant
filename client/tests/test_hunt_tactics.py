"""The swing's variants: a tactical maneuver every third swing while
Tactics is unlocked (#190), and one HUNT for tracks per empty room while
Perception is (#194). Arena and wordings: hunt_arena.py."""

from hunt_arena import (
    Arena,
    ELBOWED,
    KICKED,
    KILL,
    NOTHING,
    PROFILE,
    PUNCHED,
    RAT_CORPSE,
    ROTATING,
    SKINNED,
    SMITE_CHECK_THREE,
    SMITE_KILL,
    _run,
    _stands,
    hunt,
    kill,
)


# --- tracks ------------------------------------------------------------------


# Captured 2026-09-14 (#194): HUNT's answer, a numbered list, an 8-second
# roundtime; the empty answer is the wiki's.
TRACKED = (
    "You take note of all the tracks in the area, so that you can hunt anything "
    "nearby down.\nTo the east:\n  1)   a rat\nRoundtime: 8 sec."
)


PERCEPTION_OPEN = {"Perception": {"rank": 10, "percent": 0, "mindstate": 3}}


TRACKING = PROFILE | {"perception": True}


def _ticking(monkeypatch, seconds):
    """A clock that advances `seconds` per command sent."""
    now = {"t": 1000.0}
    monkeypatch.setattr(hunt, "clock", lambda: now["t"])
    original_ask = hunt.ask

    def ask(s, command):
        now["t"] += seconds
        return original_ask(s, command)

    monkeypatch.setattr(hunt, "ask", ask)


def test_a_hunt_for_tracks_when_the_room_empties_once_per_timer(travel, monkeypatch):
    # Three kills empty three rooms in turn; the fuse ends the run at
    # the third. With the clock frozen the second emptying is inside
    # the 75-second timer; ticking 30 s a command, a kill is 90 s and
    # every emptying earns a HUNT.
    for seconds, hunts in ((0, 1), (30, 2)):
        _ticking(monkeypatch, seconds)
        arena = Arena(
            {
                "attack": [(KILL, kill)] * 3,
                "hunt": [TRACKED] * 3,
                "skin": [SKINNED] * 3,
                "loot": [NOTHING] * 3,
            },
            experience=PERCEPTION_OPEN,
        )
        arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
        _run(arena, profile=TRACKING | {"max_kills": 3}, travel_first=False)
        assert arena.sent.count("hunt") == hunts, seconds
        first = arena.sent.index("hunt")
        assert arena.sent[first - 1] == "loot"  # after the corpse, before the move
        assert any(f"{hunts} HUNT(s)" in text for text in arena.echoed)


def test_no_hunt_for_tracks_at_lock_or_with_the_flag_off(travel):
    locked = {"Perception": {"rank": 10, "percent": 0, "mindstate": 34}}
    for profile, experience in ((TRACKING, locked), (PROFILE, PERCEPTION_OPEN)):
        arena = Arena(
            {
                "attack": [(KILL, kill)] * 2,
                "hunt": [TRACKED] * 2,
                "skin": [SKINNED] * 2,
                "loot": [NOTHING] * 2,
            },
            experience=experience,
        )
        arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
        _run(arena, profile=profile | {"max_kills": 2}, travel_first=False)
        assert "hunt" not in arena.sent


def test_three_unknown_hunt_answers_turn_tracking_off(travel, monkeypatch):
    _ticking(monkeypatch, 30)
    arena = Arena(
        {
            "attack": [(KILL, kill)] * 5,
            "hunt": ["You can't hunt here."] * 5,
            "skin": [SKINNED] * 5,
            "loot": [NOTHING] * 5,
        },
        experience=PERCEPTION_OPEN,
    )
    arena.arrivals = {6046: {"1": True}, 6047: {"1": True}}
    _run(arena, profile=TRACKING | {"max_kills": 5}, travel_first=False)
    assert arena.sent.count("hunt") == 3
    assert any("tracking off for this run" in text for text in arena.echoed)


# --- tactics -----------------------------------------------------------------


# Captured 2026-09-14 on a striped badger (#190): each maneuver's line,
# then a balance line and a 3-second roundtime; Tactics entered the exp
# window at rank 3 on the first BOB.
BOBBED = (
    "You bob suddenly, lowering yourself into a smaller target.\n"
    "[You're nimbly balanced and in superior position.]\nRoundtime: 3 sec."
)


CIRCLED = (
    "You sidestep a rat suddenly, moving in a short circle around it.\n"
    "[You're nimbly balanced and opponent has slight advantage.]\nRoundtime: 3 sec."
)


WEAVED = (
    "You weave back and forth, trying to distract your opponent.\n"
    "[You're slightly off balance with opponent in better position.]\n"
    "Roundtime: 3 sec."
)


# CIRCLE's second wording, captured 2026-09-20 on a striped badger (#240).
FAKED = (
    "You fake a rat, first moving one way and then another, leaving it off "
    "balance.\n[You're nimbly balanced and in strong position.]\nRoundtime: 3 sec."
)


TACTICAL = PROFILE | {"tactics": ["bob", "circle"]}


TACTICS_OPEN = {"Tactics": {"rank": 3, "percent": 0, "mindstate": 1}}


def test_every_third_swing_is_the_next_maneuver_while_tactics_is_unlocked(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 5 + [(KILL, kill)],
            "bob": [BOBBED] * 3,
            "circle": [CIRCLED] * 3,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"max_kills": 6}, travel_first=False)
    swings = [c for c in arena.sent if c.split()[0] in ("attack", "bob", "circle")]
    assert swings == [
        "attack rat",
        "attack rat",
        "bob rat",
        "attack rat",
        "attack rat",
        "circle rat",
        "attack rat",
        "attack rat",
    ]
    assert any("2 maneuver(s)" in text for text in arena.echoed)


def test_circles_second_wording_is_a_maneuver_done(travel):
    # #240: three "You fake ..." answers in one evening were reported as
    # unrecognized, and three would have turned tactics off for the run.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 5 + [(KILL, kill)],
            "bob": [BOBBED] * 3,
            "circle": [FAKED] * 3,
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"max_kills": 6}, travel_first=False)
    assert arena.sent.count("circle rat") == 1
    assert any("2 maneuver(s)" in text for text in arena.echoed)
    assert not any("unrecognized" in text for text in arena.echoed)
    assert not any("tactics off" in text for text in arena.echoed)


def test_a_maneuver_at_a_corpse_is_the_corpse_answer_not_a_miss(travel):
    # 2026-09-20: a BOB went out at a badger already dead and was reported
    # as unrecognized although the corpse branch disposed of it.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "bob": [RAT_CORPSE],
            "skin": [SKINNED] * 4,
            "loot": [NOTHING] * 4,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"max_kills": 3}, travel_first=False)
    assert "bob rat" in arena.sent
    assert not any("unrecognized" in t for t in arena.echoed)
    assert not any("tactics off" in t for t in arena.echoed)
    assert arena.sent.count("skin rat") == 4  # the corpse the BOB found, disposed


def test_a_maneuver_the_foe_wins_is_still_a_maneuver(travel):
    # Captured 2026-09-21 on the vineyard cougars (#265): seven of these
    # in one run were reported and turned the maneuvers off.
    lost = (
        "You hesitate and change your mind, circle back awkwardly.  The cougar "
        "easily out maneuvers you.\n[You're solidly balanced and opponent has "
        "slight advantage.]\nRoundtime: 4 sec.\n"
    )
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 6 + [(KILL, kill)],
            "bob": [lost, lost],
            "circle": [lost, lost],
            "weave": [lost, lost],
            "skin": [SKINNED] * 7,
            "loot": [NOTHING] * 7,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"max_kills": 7}, travel_first=False)
    assert not any("unrecognized" in text for text in arena.echoed)
    assert not any("tactics off" in text for text in arena.echoed)
    assert any(
        "maneuver(s)" in text and " 0 maneuver" not in text for text in arena.echoed
    )


def test_a_maneuver_from_range_advances_on_the_prey_and_waits_for_melee(travel):
    # Captured 2026-09-20 on a badger closing from pole range: a maneuver
    # does not advance the way ATTACK does, so the loop ADVANCEs itself.
    too_far = "You must be closer to use tactical abilities on your opponent.\n"
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 2 + [(KILL, kill)],
            "bob": [too_far, BOBBED],
            "advance": ["You begin to advance on a rat.\n"],
            "skin": [SKINNED] * 3,
            "loot": [NOTHING] * 3,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"max_kills": 3}, travel_first=False)
    at = arena.sent.index("bob rat")
    assert arena.sent[at : at + 2] == ["bob rat", "advance rat"]
    assert not any("unrecognized" in text for text in arena.echoed)
    assert not any("tactics off" in text for text in arena.echoed)


def test_punch_and_kick_at_range_advance_on_the_prey(travel):
    # Captured 2026-09-20 on a badger closing from pole range (#257):
    # PUNCH quips about a weapon, KICK kicks dirt, neither with a
    # roundtime — three commands went out in a second. Both mean ADVANCE.
    quip = "Actually, using a weapon would probably be a bit more effective.\n"
    dirt = "You kick some dirt on a striped badger in disgust.\n"
    arena = _run(
        Arena(
            {
                "punch": [quip, PUNCHED + "\n", (KILL, kill)],
                "kick": [dirt, KICKED + "\n", KICKED + "\n"],
                "elbow": [ELBOWED + "\n"] * 3,
                "advance": ["You begin to advance on a rat.\n"] * 3,
                "skin": [SKINNED],
                "loot": [NOTHING],
            },
            experience={"Brawling": {"rank": 7, "percent": 0, "mindstate": 5}},
        ),
        profile=ROTATING | {"weapons": ["fists:Brawling"]},
        travel_first=False,
    )
    first = arena.sent.index("punch rat")
    assert arena.sent[first + 1] == "advance rat"
    if "kick rat" in arena.sent:
        assert arena.sent[arena.sent.index("kick rat") + 1] == "advance rat"
    assert not any("unrecognized" in t for t in arena.echoed)


def test_no_maneuver_once_tactics_locks_or_with_none_listed(travel):
    locked = {"Tactics": {"rank": 3, "percent": 0, "mindstate": 34}}
    for profile, experience in ((TACTICAL, locked), (PROFILE, TACTICS_OPEN)):
        arena = Arena(
            {
                "attack": [(KILL, _stands)] * 5 + [(KILL, kill)],
                "bob": [BOBBED] * 3,
                "circle": [CIRCLED] * 3,
                "skin": [SKINNED] * 6,
                "loot": [NOTHING] * 6,
            },
            experience=experience,
        )
        _run(arena, profile=profile | {"max_kills": 6}, travel_first=False)
        assert not any(c.startswith(("bob", "circle")) for c in arena.sent)
        assert not any("maneuver" in text for text in arena.echoed)


def test_a_smite_keeps_its_minute_ahead_of_the_maneuvers(travel, monkeypatch):
    monkeypatch.setattr(hunt, "clock", lambda: 1000.0)  # one smite, never again
    arena = Arena(
        {
            "smite check": [SMITE_CHECK_THREE] * 3,
            "smite": [(SMITE_KILL, _stands)],
            "attack": [(KILL, _stands)] * 3 + [(KILL, kill)],
            "bob": [BOBBED],
            "circle": [CIRCLED],
            "skin": [SKINNED] * 6,
            "loot": [NOTHING] * 6,
        },
        experience=TACTICS_OPEN,
    )
    _run(arena, profile=TACTICAL | {"smite": True, "max_kills": 5}, travel_first=False)
    swings = [
        c
        for c in arena.sent
        if c.split()[0] in ("attack", "smite", "bob", "circle") and c != "smite check"
    ]
    assert swings == [
        "smite rat",
        "attack rat",
        "bob rat",
        "attack rat",
        "attack rat",
        "circle rat",
        "attack rat",
    ]


def test_a_maneuver_from_range_advances_like_an_attack(travel):
    advancing = "You aren't close enough to attack.\nYou begin to advance on a rat."
    arena = Arena(
        {
            "attack": [(KILL, _stands), (KILL, _stands), (KILL, kill)],
            "weave": [advancing],
            "skin": [SKINNED] * 3,
            "loot": [NOTHING] * 3,
        },
        experience=TACTICS_OPEN,
    )
    _run(
        arena,
        profile=PROFILE | {"tactics": ["weave"], "max_kills": 3},
        travel_first=False,
    )
    assert "weave rat" in arena.sent
    assert not any("unrecognized" in text for text in arena.echoed)


def test_a_maneuver_answered_with_nothing_known_three_times_turns_tactics_off(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 11 + [(KILL, kill)],
            "bob": ["You can't do that right now."] * 5,
            "skin": [SKINNED] * 12,
            "loot": [NOTHING] * 12,
        },
        experience=TACTICS_OPEN,
    )
    _run(
        arena,
        profile=PROFILE | {"tactics": ["bob"], "max_kills": 12},
        travel_first=False,
    )
    assert arena.sent.count("bob rat") == 3
    assert sum("unrecognized bob" in text for text in arena.echoed) == 3
    assert any("tactics off for this run" in text for text in arena.echoed)


def test_without_smite_every_swing_is_attack(travel):
    arena = _run(
        Arena({"attack": [(KILL, kill)], "skin": [SKINNED], "loot": [NOTHING]})
    )
    assert not any(c.startswith("smite") for c in arena.sent)


def test_a_room_full_of_creatures_is_hunted_not_left(travel):
    # #178 asked for a crowd threshold; the operator's answer (2026-09-12):
    # a hunt farms, so a full room is fought one at a time, never skipped.
    arena = Arena({"attack": [(KILL, kill)]})
    arena.state.room_creatures = ["a ship's rat"] * 5
    _run(arena)
    assert arena.walks[0] == {6046, 6047}
    assert any(c.startswith("attack") for c in arena.sent)
    assert not any("crowd" in text for text in arena.echoed)


def test_a_maneuver_with_no_foe_left_is_the_room_clearing_not_a_miss(travel):
    # 2026-09-23 at the bobcats: a BOB went out as the last foe fell and
    # the game answered "There is nothing else to face!" — the room is
    # clear, the same as a bare ATTACK's answer, not an unknown answer.
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 11 + [(KILL, kill)],
            "bob": ["There is nothing else to face!"] * 5,
            "skin": [SKINNED] * 12,
            "loot": [NOTHING] * 12,
        },
        experience=TACTICS_OPEN,
    )
    _run(
        arena,
        profile=PROFILE | {"tactics": ["bob"], "max_kills": 12},
        travel_first=False,
    )
    assert "bob rat" in arena.sent
    assert not any("unrecognized bob" in text for text in arena.echoed)
    assert not any("tactics off for this run" in text for text in arena.echoed)
