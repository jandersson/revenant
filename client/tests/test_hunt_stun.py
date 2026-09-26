""";hunt and a stun (#336): a swing waits the stun out, and one answered
"You are still stunned." did not happen — the maneuver keeps its turn,
a self-combo's attack its place, nothing counts as a miss. Captured
2026-09-26 on a circle-1 Barbarian among grass eels. Arena:
hunt_arena.py."""

from types import SimpleNamespace

from hunt_arena import (
    MISSED,
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

STILL = "You are still stunned."
TACTICS_OPEN = {"Tactics": {"rank": 3, "percent": 0, "mindstate": 1}}
# Captured 2026-09-14 (test_hunt_tactics.py's).
BOBBED = (
    "You bob suddenly, lowering yourself into a smaller target.\n"
    "[You're nimbly balanced and in superior position.]\nRoundtime: 3 sec."
)


def test_a_refused_attack_is_sent_again_and_not_a_miss(travel):
    arena = Arena(
        {
            "attack": [STILL, STILL, (KILL, kill)],
            "skin": [SKINNED],
            "loot": [NOTHING],
        }
    )
    _run(arena, profile=PROFILE | {"max_kills": 1}, travel_first=False)
    assert arena.sent.count("attack rat") == 3
    assert not any("unrecognized" in text for text in arena.echoed)
    assert any("rat down (1)" in text for text in arena.echoed)


def test_a_refused_maneuver_keeps_its_turn_and_is_no_tactics_miss(travel):
    arena = Arena(
        {
            "attack": [(KILL, _stands)] * 4 + [(KILL, kill)],
            "bob": [STILL, STILL, STILL, BOBBED],
            "skin": [SKINNED] * 9,
            "loot": [NOTHING] * 9,
        },
        experience=TACTICS_OPEN,
    )
    profile = PROFILE | {"tactics": ["bob", "circle"], "max_kills": 5}
    _run(arena, profile=profile, travel_first=False)
    swings = [c for c in arena.sent if c.split()[0] in ("attack", "bob", "circle")]
    # Three refusals were three MISS answers before #336 and turned tactics
    # off; now BOB is sent again until it goes out, and CIRCLE stays next.
    assert swings[:6] == [
        "attack rat",
        "attack rat",
        "bob rat",
        "bob rat",
        "bob rat",
        "bob rat",
    ]
    assert not any("tactics off" in text for text in arena.echoed)
    assert not any("unrecognized bob" in text for text in arena.echoed)


def test_a_refused_combo_attack_keeps_its_place(travel):
    combo = "Increased inner fire may be achieved by landing a draw and a feint."
    arena = Arena(
        {
            "analyze flame": [combo] * 2,
            "draw": [STILL, MISSED],
            "feint": [(KILL, kill)],
            "skin": [SKINNED],
            "loot": [NOTHING],
        },
        experience={"Expertise": {"rank": 4, "percent": 0, "mindstate": 1}},
    )
    _run(
        arena,
        profile=PROFILE | {"analyze": "flame", "max_kills": 1},
        travel_first=False,
    )
    swings = [c for c in arena.sent if c.split()[0] in ("analyze", "draw", "feint")]
    assert swings == ["analyze flame", "draw rat", "draw rat", "feint rat"]


class Stunned:
    """A status that reads stunned for its first `reads` looks."""

    def __init__(self, reads):
        self.reads = reads

    @property
    def stunned(self):
        self.reads -= 1
        return self.reads >= 0


def test_a_swing_waits_while_the_status_says_stunned():
    slept = []
    s = SimpleNamespace(status=Stunned(3), dead=False, sleep=slept.append)
    hunt.wait_out_stun(s)
    assert slept == [hunt.STUN_POLL] * 3
    # Never past STUN_WAIT, and none for a handle without the status.
    slept.clear()
    s = SimpleNamespace(status=Stunned(10**6), dead=False, sleep=slept.append)
    hunt.wait_out_stun(s)
    assert sum(slept) == hunt.STUN_WAIT
    hunt.wait_out_stun(SimpleNamespace(dead=False, sleep=slept.append))


def test_a_stunned_analyze_is_no_miss():
    barb = barbarian.BarbState()
    handle = SimpleNamespace(
        state=SimpleNamespace(experience={}),
        waitrt=lambda: None,
        echo=lambda text: None,
    )
    seen = []
    for _ in range(4):
        barbarian.next_combo_attack(
            handle,
            {"analyze": "flame"},
            barb,
            lambda s, command: STILL,
            "hunt",
            lambda what, answer: seen.append(answer),
        )
    assert not barb.analyze_off and seen == []
