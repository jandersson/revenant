"""train_casting names several magic skills and each training cast goes
to the one with the emptiest pool, cast with the first buff DISCERN
says uses it (#374). Cecil's evening of 2026-09-28 is the case: one
skill named, Augmentation at 33/34 and Warding and Utility at 0/34."""

import json
from types import SimpleNamespace

from client.game import buffs
from client.game.profile import load_profile, save_profile

# DISCERN's skill sentence, captured 2026-09-28 on Heroic Strength; the
# other spells' lines are that sentence with their wiki skill.
AUG = "It requires the Augmentation skill to cast effectively.\n"
WARD = "It requires the Warding skill to cast effectively.\n"
UTIL = "It requires the Utility skill to cast effectively.\n"
DISCERNS = {
    "heroic strength": AUG,
    "aspirant's aegis": WARD,
    "sentinel's resolve": AUG,
    "courage": WARD,
    "hands of justice": UTIL,
}
PROFILE = {
    "buffs": list(DISCERNS),
    "train_casting": ["Augmentation", "Warding", "Utility"],
    "cast_gap": 0,
}
PREPARED = "You begin chanting a prayer.\n"
CAST = "You gesture.\nThe spell takes effect.\n"


def _exp(augmentation=33, warding=0, utility=0):
    return {
        "Augmentation": {"rank": 95, "percent": 43, "mindstate": augmentation},
        "Warding": {"rank": 35, "percent": 6, "mindstate": warding},
        "Utility": {"rank": 34, "percent": 4, "mindstate": utility},
    }


class Handle:
    def __init__(self, experience):
        self.sent = []
        self.echoed = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience=experience,
            vitals={"mana": 100},
            # Every buff is up, so only the training cast goes out.
            active_spells={spell: 10 for spell in DISCERNS},
            server_time=None,
        )

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass


def ask(s, command):
    s.sent.append(command)
    if command.startswith("discern "):
        return DISCERNS.get(command[len("discern ") :], "")
    if command.startswith("prepare"):
        return PREPARED
    return CAST if command == "cast" else ""


def _report(what, answer):
    raise AssertionError(f"unrecognized {what}: {answer!r}")


def _train(handle, state, profile=PROFILE):
    buffs.discern_slots(handle, profile, state, ask, "hunt", _report)
    handle.sent.clear()
    buffs.cast_buffs(handle, profile, state, ask, "hunt", _report)
    return [command for command in handle.sent if command.startswith("prepare")]


def test_each_training_cast_goes_to_the_emptiest_skill_named(monkeypatch):
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    handle = Handle(_exp(augmentation=33, warding=0, utility=0))
    state = buffs.BuffState()
    # Warding and Utility both empty: the lower rank, Utility, goes first.
    assert _train(handle, state) == ["prepare hands of justice"]
    assert "hunt: cast hands of justice at minimum mana for Utility" in handle.echoed
    handle.state.experience = _exp(augmentation=33, warding=0, utility=3)
    assert _train(handle, state) == ["prepare aspirant's aegis"]
    handle.state.experience = _exp(augmentation=33, warding=34, utility=34)
    assert _train(handle, state) == ["prepare heroic strength"]
    # Each buff keeps its own ramp.
    handle.state.experience = _exp(augmentation=20, warding=20, utility=5)
    assert _train(handle, state) == ["prepare hands of justice 2"]
    handle.state.experience = _exp(augmentation=34, warding=34, utility=34)
    assert _train(handle, state) == []


def test_a_buffs_skill_is_discerned_once_and_remembered_for_the_next_run(
    monkeypatch,
):
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    first = Handle(_exp())
    buffs.discern_slots(first, PROFILE, buffs.BuffState(), ask, "hunt", _report)
    # Every skill unknown: each buff DISCERNed once, in the profile's order.
    assert first.sent == [f"discern {spell}" for spell in DISCERNS]
    stored = json.loads(buffs.spell_skills_path().read_text(encoding="utf-8"))
    assert stored["courage"] == ["Warding"]
    # The next run knows them: only the first buff of each skill is
    # DISCERNed, for its ramp's ceiling; the second of a skill is not.
    second = Handle(_exp())
    buffs.discern_slots(second, PROFILE, buffs.BuffState(), ask, "hunt", _report)
    assert second.sent == [
        "discern heroic strength",
        "discern aspirant's aegis",
        "discern hands of justice",
    ]


def test_a_name_discern_does_not_parse_is_asked_by_its_abbreviation(monkeypatch):
    # Captured 2026-09-29 on Cecil: "discern hands of justice" answered
    # "You have no idea how to cast that spell.", so Hands of Justice
    # never named its skill and Utility had no training cast. PREPARE
    # has retried by ;sheet's abbreviation since #320; DISCERN now too.
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    monkeypatch.setattr(
        buffs, "abbreviation", lambda name, spell: "hoj" if "justice" in spell else None
    )
    unparsed = dict(DISCERNS)
    unparsed["hands of justice"] = "You have no idea how to cast that spell.\n"
    unparsed["hoj"] = UTIL

    def picky(s, command):
        s.sent.append(command)
        if command.startswith("discern "):
            return unparsed.get(command[len("discern ") :], "")
        return ask(s, command)

    handle = Handle(_exp(augmentation=33, warding=34, utility=0))
    state = buffs.BuffState()
    buffs.discern_slots(handle, PROFILE, state, picky, "hunt", _report)
    assert handle.sent[-2:] == ["discern hands of justice", "discern hoj"]
    assert not [e for e in handle.echoed if "nothing trains it" in e]
    assert buffs.skills_of(state, "hands of justice") == ["Utility"]
    # The abbreviation prepares it for the rest of the run.
    assert state.short_names["hands of justice"] == "hoj"


def test_a_skills_next_buff_takes_over_when_the_first_drops_out(monkeypatch):
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    handle = Handle(_exp(augmentation=0, warding=34, utility=34))
    buffs.discern_slots(handle, PROFILE, buffs.BuffState(), ask, "hunt", _report)
    # The next run knows every buff's skill and skips Sentinel's Resolve,
    # Augmentation's second buff, until Heroic Strength drops out.
    state = buffs.BuffState()
    buffs.discern_slots(handle, PROFILE, state, ask, "hunt", _report)
    state.buffs_off.add("heroic strength")  # refused its PREPARE
    assert buffs.training_pick(handle, PROFILE, state) == (
        "Augmentation",
        "sentinel's resolve",
    )
    handle.sent.clear()
    buffs.discern_slots(handle, PROFILE, state, ask, "hunt", _report)
    # Its skill is known; its ceiling now matters.
    assert handle.sent == ["discern sentinel's resolve"]


def test_a_named_skill_no_buff_uses_is_said_once(monkeypatch):
    handle = Handle(_exp())
    state = buffs.BuffState()
    profile = {
        "buffs": ["heroic strength"],
        "train_casting": ["Augmentation", "Warding"],
    }
    buffs.discern_slots(handle, profile, state, ask, "hunt", _report)
    buffs.discern_slots(handle, profile, state, ask, "hunt", _report)
    said = [text for text in handle.echoed if "no buff in the profile uses" in text]
    assert said == ["hunt: no buff in the profile uses Warding — nothing trains it"]
    assert not state.training_off  # Augmentation still trains
    lone = buffs.BuffState()
    buffs.discern_slots(
        handle,
        {"buffs": ["heroic strength"], "train_casting": ["Warding"]},
        lone,
        ask,
        "hunt",
        _report,
    )
    assert lone.training_off


def test_all_trains_every_skill_the_buffs_use(monkeypatch):
    handle = Handle(_exp())
    state = buffs.BuffState()
    profile = dict(PROFILE, train_casting="all")
    buffs.discern_slots(handle, profile, state, ask, "hunt", _report)
    assert buffs.training_buffs(profile, state) == {
        "Augmentation": "heroic strength",
        "Warding": "aspirant's aegis",
        "Utility": "hands of justice",
    }


def test_the_skill_sentence_and_the_profile_spellings():
    captured = (
        "By the time you have mastered this spell, you will be ranked as a "
        "professional in your abilities as a caster.  It requires the "
        "Augmentation skill to cast effectively.  This spell has no prerequisites."
    )
    assert buffs.discerned_skills(captured) == ["Augmentation"]
    assert buffs.discerned_skills(
        "It requires the Augmentation and Utility skills to cast effectively."
    ) == ["Augmentation", "Utility"]
    assert (
        buffs.discerned_skills("You don't think you are able to cast this spell.") == []
    )
    # One skill as a string (a profile from before #374), several, or none.
    assert buffs.training_skills({"train_casting": "Augmentation"}) == ["Augmentation"]
    assert buffs.training_skills({"train_casting": "Augmentation, Warding"}) == [
        "Augmentation",
        "Warding",
    ]
    assert buffs.training_skills({"train_casting": ""}) == []


def test_a_saved_single_skill_profile_loads_as_a_list(tmp_path):
    save_profile("Lanival", {"train_casting": "Augmentation, Warding"})
    assert load_profile("Lanival")["train_casting"] == ["Augmentation", "Warding"]
    path = tmp_path / "profiles" / "lanival.json"
    path.write_text(json.dumps({"train_casting": "Augmentation"}), encoding="utf-8")
    assert load_profile("Lanival")["train_casting"] == ["Augmentation"]
