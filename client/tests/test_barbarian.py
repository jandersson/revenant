"""A Barbarian's pieces of the hunt (client/game/barbarian.py, #328):
ANALYZE self-combos for Expertise, abilities kept up, a roar at the
prey. The ANALYZE answers are dr-scripts' combat-trainer.lic's, the
ability lines its data/base-spells.yaml's, none captured yet."""

from types import SimpleNamespace

import pytest

from client.game import barbarian

# The shape combat-trainer reads: "by landing an? (.*)\.$".
COMBO = "You reveal a weakness in your stance by landing a jab, a feint and a slice."
COMBO_OXFORD = (
    "Analyzing, you see you can gain an edge by landing a draw, a thrust, and a chop."
)


class Handle:
    def __init__(self, answers=None, experience=None, spells=None):
        self.answers = dict(answers or {})
        self.sent, self.echoed, self.flags = [], [], {}
        self.raised = set()
        self.state = SimpleNamespace(
            experience=experience or {}, active_spells=spells or {}
        )

    def ask(self, s, command):
        self.sent.append(command)
        queue = self.answers.get(command, "")
        if isinstance(queue, list):
            return queue.pop(0) if queue else ""
        return queue

    def waitrt(self):
        pass

    def echo(self, text):
        self.echoed.append(text)

    def flag(self, name, *patterns):
        self.flags[name] = patterns

    def flagged(self, name, clear=True):
        if name in self.raised:
            self.raised.discard(name)
            return True
        return False


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(barbarian, "clock", lambda: now["t"])
    return now


def reports():
    seen = []
    return seen, lambda what, answer: seen.append((what, answer))


# --- ANALYZE ---


def test_a_combo_answer_names_its_attacks_as_verbs():
    assert barbarian.combo_attacks(COMBO) == ["jab", "feint", "slice"]
    assert barbarian.combo_attacks(COMBO_OXFORD) == ["draw", "thrust", "chop"]
    assert barbarian.combo_attacks("You fail to find any holes.") == []


def test_analyze_starts_a_combo_and_the_swings_are_its_attacks():
    handle = Handle({"analyze flame": COMBO})
    barb = barbarian.BarbState()
    seen, report = reports()
    profile = {"analyze": "flame"}
    swings = [
        barbarian.next_combo_attack(handle, profile, barb, handle.ask, "hunt", report)
        for _ in range(3)
    ]
    assert swings == ["jab", "feint", "slice"]
    assert handle.sent == ["analyze flame"]  # once for the whole combo
    assert barb.combos == 1 and not seen
    # The combo done, the next swing asks again.
    barbarian.next_combo_attack(handle, profile, barb, handle.ask, "hunt", report)
    assert handle.sent == ["analyze flame"] * 2


def test_no_combo_without_the_profile_or_with_expertise_locked():
    barb = barbarian.BarbState()
    _, report = reports()
    handle = Handle({"analyze flame": COMBO})
    assert (
        barbarian.next_combo_attack(
            handle, {"analyze": ""}, barb, handle.ask, "hunt", report
        )
        is None
    )
    locked = Handle(
        {"analyze flame": COMBO}, experience={"Expertise": {"mindstate": 34}}
    )
    assert (
        barbarian.next_combo_attack(
            locked, {"analyze": "flame"}, barb, locked.ask, "hunt", report
        )
        is None
    )
    assert handle.sent == [] and locked.sent == []


def test_known_refusals_swing_attack_and_three_unknown_answers_turn_it_off():
    barb = barbarian.BarbState()
    seen, report = reports()
    handle = Handle(
        {
            "analyze flame": [
                "Analyze what?",
                "You must be closer.",
                "Huh?",
                "Huh?",
                "Huh?",
            ]
        }
    )
    profile = {"analyze": "flame"}
    for _ in range(5):
        assert (
            barbarian.next_combo_attack(
                handle, profile, barb, handle.ask, "hunt", report
            )
            is None
        )
    assert barb.analyze_off
    assert len(seen) == 3
    assert "answered nothing known 3 times — off for this run" in handle.echoed[-1]


def test_a_combo_on_its_cooldown_waits_before_asking_again(frozen):
    barb = barbarian.BarbState()
    _, report = reports()
    handle = Handle({"analyze accuracy": ["You cannot repeat that yet.", COMBO]})
    profile = {"analyze": "accuracy"}
    assert (
        barbarian.next_combo_attack(handle, profile, barb, handle.ask, "hunt", report)
        is None
    )
    assert (
        barbarian.next_combo_attack(handle, profile, barb, handle.ask, "hunt", report)
        is None
    )
    assert handle.sent == ["analyze accuracy"]
    frozen["t"] += barbarian.COMBO_COOLDOWN
    assert (
        barbarian.next_combo_attack(handle, profile, barb, handle.ask, "hunt", report)
        == "jab"
    )


# --- abilities ---


AVALANCHE_TOOK = "The rage of the avalanche replenishes your energy!"


def test_the_table_is_dr_scripts_thirty_seven_abilities():
    assert len(barbarian.ABILITIES) == 37
    assert barbarian.ability("berserk avalanche") == (
        "Avalanche",
        barbarian.ABILITIES["Avalanche"],
    )
    assert barbarian.ability("buffalo")[1][1] == "form buffalo"
    assert barbarian.ability("fireball")[1] is None


def test_an_ability_not_running_is_started_and_watched_for_its_end():
    handle = Handle({"berserk avalanche": AVALANCHE_TOOK})
    barb = barbarian.BarbState()
    seen, report = reports()
    profile = {"abilities": ["Avalanche"]}
    assert barbarian.keep_abilities(
        handle, profile, barb, handle.ask, "hunt", report
    ) == ["Avalanche"]
    assert "barb-Avalanche" in handle.flags
    # Running: no second start.
    assert (
        barbarian.keep_abilities(handle, profile, barb, handle.ask, "hunt", report)
        == []
    )
    # Its ended line came: started again.
    handle.raised.add("barb-Avalanche")
    assert barbarian.keep_abilities(
        handle, profile, barb, handle.ask, "hunt", report
    ) == ["Avalanche"]
    assert handle.sent == ["berserk avalanche"] * 2 and not seen


def test_the_spells_window_listing_it_is_running_too():
    handle = Handle({"berserk avalanche": AVALANCHE_TOOK}, spells={"Avalanche": 8})
    barb = barbarian.BarbState()
    _, report = reports()
    assert (
        barbarian.keep_abilities(
            handle, {"abilities": ["avalanche"]}, barb, handle.ask, "hunt", report
        )
        == []
    )
    assert handle.sent == []


def test_untrained_is_off_for_the_run_and_low_fire_waits(frozen):
    handle = Handle(
        {
            "berserk avalanche": "You have not been trained in that berserk.",
            "form buffalo": [
                "Your inner fire lacks the strength for that.",
                "Lurching forward, " + barbarian.ABILITIES["Buffalo"][2],
            ],
        }
    )
    barb = barbarian.BarbState()
    _, report = reports()
    profile = {"abilities": ["Avalanche", "Buffalo"]}
    assert (
        barbarian.keep_abilities(handle, profile, barb, handle.ask, "hunt", report)
        == []
    )
    assert "Avalanche is not trained — off for this run" in handle.echoed[-1]
    assert (
        barbarian.keep_abilities(handle, profile, barb, handle.ask, "hunt", report)
        == []
    )
    assert handle.sent == ["berserk avalanche", "form buffalo"]  # both waiting
    frozen["t"] += barbarian.IF_WAIT
    assert barbarian.keep_abilities(
        handle, profile, barb, handle.ask, "hunt", report
    ) == ["Buffalo"]


def test_a_meditation_sits_for_it_and_never_goes_out_in_the_fight():
    handle = Handle(
        {
            "meditate tenacity": [
                "You must be sitting to do that.",
                "You begin to meditate on tenacity.",
            ]
        }
    )
    barb = barbarian.BarbState()
    _, report = reports()
    profile = {"abilities": ["Tenacity"]}
    assert (
        barbarian.keep_abilities(
            handle, profile, barb, handle.ask, "hunt", report, fight=True
        )
        == []
    )
    assert handle.sent == []
    assert barbarian.keep_abilities(
        handle, profile, barb, handle.ask, "hunt", report
    ) == ["Tenacity"]
    assert handle.sent == ["meditate tenacity", "sit", "meditate tenacity", "stand"]


def test_a_name_outside_the_table_is_said_once_and_skipped():
    handle = Handle()
    barb = barbarian.BarbState()
    _, report = reports()
    for _ in range(2):
        barbarian.keep_abilities(
            handle, {"abilities": ["Fireball"]}, barb, handle.ask, "hunt", report
        )
    assert handle.sent == []
    assert (
        len(handle.echoed) == 1
        and "no Barbarian ability 'Fireball'" in handle.echoed[0]
    )


# --- roars ---


def test_a_roar_goes_out_once_a_gap_while_debilitation_is_unlocked(frozen):
    handle = Handle({"roar anger at rat": "You let loose a mighty roar!"})
    barb = barbarian.BarbState()
    seen, report = reports()
    profile = {"roar": "anger"}
    assert barbarian.roar(
        handle, profile, barb, handle.ask, "hunt", report, target="rat"
    )
    assert not barbarian.roar(
        handle, profile, barb, handle.ask, "hunt", report, target="rat"
    )
    frozen["t"] += barbarian.ROAR_GAP
    assert barbarian.roar(
        handle, profile, barb, handle.ask, "hunt", report, target="rat"
    )
    assert handle.sent == ["roar anger at rat"] * 2
    assert len(seen) == 1  # the first answer, for the fixtures
    locked = Handle(experience={"Debilitation": {"mindstate": 34}})
    assert not barbarian.roar(
        locked, profile, barbarian.BarbState(), locked.ask, "hunt", report
    )


def test_an_untrained_roar_is_off_for_the_run(frozen):
    handle = Handle({"roar anger": "You have not been trained in that roar."})
    barb = barbarian.BarbState()
    _, report = reports()
    barbarian.roar(handle, {"roar": "anger"}, barb, handle.ask, "hunt", report)
    frozen["t"] += barbarian.ROAR_GAP
    assert not barbarian.roar(
        handle, {"roar": "anger"}, barb, handle.ask, "hunt", report
    )
    assert barb.roar_off
