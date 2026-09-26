"""The loop idioms the trainer scripts share (client/game/loop.py): the
typed "return", the danger check, and the pause that ends on either.
"""

from types import SimpleNamespace

from client.game import loop


class Handle:
    def __init__(self, typed=(), dead=False, hostiles=None):
        self.typed = list(typed)
        self.dead = dead
        self.state = SimpleNamespace(hostiles=hostiles or {})
        self.slept = []

    def command(self, timeout=None):
        return self.typed.pop(0) if self.typed else None

    def sleep(self, seconds):
        self.slept.append(seconds)


def test_return_typed_at_the_script_is_the_graceful_end_other_words_are_not():
    assert loop.wants_stop(Handle(["status", "Return"])) is True
    assert loop.wants_stop(Handle(["status", "faster"])) is False
    assert loop.wants_stop(Handle()) is False


def test_danger_is_death_or_hostiles_and_nothing_else():
    assert loop.danger(Handle(dead=True)) == "you are dead"
    assert loop.danger(Handle(hostiles={"123": True})) == "hostiles in the room"
    assert loop.danger(Handle()) is None


def test_a_pause_sleeps_in_one_second_slices_and_passes_whole():
    handle = Handle()
    assert loop.pause(handle, 2.5) is True
    assert handle.slept == [1, 1, 0.5]


def test_a_pause_ends_at_once_on_a_typed_return_or_a_danger():
    typed = Handle(["return"])
    assert loop.pause(typed, 30) is False
    assert typed.slept == [1]  # one slice, then the word was seen

    class Ambushed(Handle):
        def sleep(self, seconds):
            super().sleep(seconds)
            if len(self.slept) == 2:
                self.state.hostiles = {"7": True}

    ambushed = Ambushed()
    assert loop.pause(ambushed, 30) is False
    assert ambushed.slept == [1, 1]


def test_the_mindstate_is_the_exp_windows_or_none():
    handle = Handle()
    handle.state.experience = {"Appraisal": {"rank": 8, "percent": 0, "mindstate": 3}}
    assert loop.mindstate(handle, "Appraisal") == 3
    assert loop.mindstate(handle, "Scholarship") is None
    assert loop.mindstate(Handle(), "Appraisal") is None


def test_a_skill_the_window_lacks_is_asked_of_exp_and_seeded_whole():
    handle = Handle()
    handle.state.experience = {}
    asked = []

    def ask(s, command):
        asked.append(command)
        return "appraisal:   8 11% dabbling  (1/34)\n"  # lower-cased by an ask()

    assert loop.ensure_mindstate(handle, "Appraisal", ask) == 1
    assert asked == ["exp appraisal"]
    # a whole entry, the parser's shape — a seed without a rate took the
    # session down (#239)
    assert handle.state.experience["Appraisal"] == {
        "rank": 8,
        "percent": 0,
        "mindstate": 1,
        "rate": "dabbling",
    }
    assert loop.ensure_mindstate(handle, "Scholarship", lambda s, c: "") is None


def test_read_exp_asks_whatever_the_window_holds_and_writes_the_whole_entry():
    # #327: the window never pushes a Barbarian's Utility, so the table
    # kept its login seed while MEDITATE RESEARCH moved it.
    handle = Handle()
    handle.state.experience = {
        "Utility": {"rank": 0, "percent": 15, "mindstate": 0, "rate": "clear"}
    }
    asked = []

    def ask(s, command):
        asked.append(command)
        return "         Utility:      0 30.00% dabbling       (1/34)\n"

    assert loop.exp_entry(handle, "utility")["percent"] == 15
    assert loop.read_exp(handle, "Utility", ask) == 1
    assert asked == ["exp utility"]
    assert handle.state.experience == {
        "Utility": {"rank": 0, "percent": 30, "mindstate": 1, "rate": "dabbling"}
    }
    # A copy, not the table's own dict; nothing shown, nothing written.
    loop.exp_entry(handle, "Utility")["percent"] = 99
    assert handle.state.experience["Utility"]["percent"] == 30
    assert loop.read_exp(handle, "Warding", lambda s, c: "") is None
    assert "Warding" not in handle.state.experience


def test_a_skill_is_found_and_seeded_under_the_windows_spelling():
    # #295: ;listen asked "exp parry ability" and seeded "parry ability"
    # beside the window's "Parry Ability"; the window's pushes updated
    # its own key and the seed sat at 11 while the class taught to 25.
    handle = Handle()
    handle.state.experience = {"Parry Ability": {"rank": 45, "mindstate": 22}}
    assert loop.mindstate(handle, "parry ability") == 22
    assert loop.ensure_mindstate(handle, "parry ability", lambda s, c: "") == 22
    assert list(handle.state.experience) == ["Parry Ability"]  # no seed

    fresh = Handle()
    fresh.state.experience = {}
    loop.ensure_mindstate(
        fresh,
        "parry ability",
        lambda s, c: "Parry Ability:   45 63% dabbling  (11/34)\n",
    )
    assert list(fresh.state.experience) == ["Parry Ability"]
    lowered = Handle()
    lowered.state.experience = {}
    loop.ensure_mindstate(
        lowered,
        "parry ability",
        lambda s, c: "parry ability:   45 63% dabbling  (11/34)\n",
    )
    assert list(lowered.state.experience) == ["Parry Ability"]

    # A session from before the fix holds both: the window's wins.
    stale = Handle()
    stale.state.experience = {
        "parry ability": {"rank": 45, "mindstate": 11},
        "Parry Ability": {"rank": 46, "mindstate": 25},
    }
    assert loop.mindstate(stale, "parry ability") == 25
    assert loop.mindstate(stale, "Parry Ability") == 25


def test_a_lowercase_seed_alone_is_no_entry():
    # 10:29 on 2026-09-23: the window had dropped "Parry Ability" and the
    # pre-#295 seed was all that was left; it counts for nothing, so a
    # script asks EXP and seeds afresh under the window's spelling.
    stale = Handle()
    stale.state.experience = {"parry ability": {"rank": 45, "mindstate": 11}}
    assert loop.mindstate(stale, "parry ability") is None
    loop.ensure_mindstate(
        stale, "parry ability", lambda s, c: "Parry Ability:   47 10% clear  (0/34)\n"
    )
    assert stale.state.experience["Parry Ability"]["mindstate"] == 0
    assert loop.mindstate(stale, "Parry Ability") == 0
