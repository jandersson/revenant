"""The training ramps start a step under DISCERN's estimate, and a
buff's ramp counts the cambrinth charge invoked into the cast against
it (#375). Cecil's evening of 2026-09-28: every run climbed from the
minimum again, and 18 prepared plus the anklet's 12 backfired under an
estimate of 28."""

from types import SimpleNamespace

from client.game import buffs

# Captured 2026-09-28 (Cecil's ;hunt): Heroic Strength and Stun Foe.
HS_DISCERN = (
    "It requires the Augmentation skill to cast effectively.\n"
    "The spell requires at minimum 1 mana streams and you think you can "
    "reinforce it with 27 more, for a total of 28 streams.\nRoundtime: 11 sec.\n"
)
SF_DISCERN = (
    "It requires the Debilitation skill to cast effectively.\n"
    "The spell requires at minimum 1 mana streams and you think you can "
    "reinforce it with 6 more, for a total of 7 streams.\nRoundtime: 9 sec.\n"
)
ANSWERS = {
    "discern heroic strength": HS_DISCERN,
    "discern stun foe": SF_DISCERN,
    "get my anklet": "You get a cambrinth anklet from inside your canvas sack.\n",
    "charge my anklet 12": (
        "You are able to channel all the energy into the anklet.\n"
        "The cambrinth anklet absorbs all of the energy.\n"
    ),
    "invoke my anklet": "You reach for its center and forge a magical link to it.\n",
    "cast": "You gesture.\nThe spell takes effect.\n",
}
PROFILE = {
    "buffs": ["heroic strength"],
    "train_casting": ["Augmentation"],
    "cambrinth": "anklet",
    "cambrinth_mana": 12,
    "cast_gap": 0,
}


class Handle:
    def __init__(self, arcana=5):
        self.sent = []
        self.echoed = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Augmentation": {"rank": 95, "percent": 0, "mindstate": 10},
                "Arcana": {"rank": 81, "percent": 0, "mindstate": arcana},
                "Debilitation": {"rank": 57, "percent": 0, "mindstate": 10},
            },
            vitals={"mana": 100},
            active_spells={"Heroic Strength": 10},
            server_time=None,
            left_hand=None,
            right_hand=None,
        )

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass


def ask(s, command):
    s.sent.append(command)
    if command.startswith("prepare"):
        return "You begin chanting a prayer.\n"
    return ANSWERS.get(command, "")


def _report(what, answer):
    raise AssertionError(f"unrecognized {what}: {answer!r}")


def _prepares(handle):
    return [command for command in handle.sent if command.startswith("prepare")]


def test_a_targeted_ramp_starts_a_step_under_the_estimate():
    handle = Handle()
    state = buffs.BuffState()
    profile = {"buffs": [], "debilitation": "stun foe"}
    buffs.discern_slots(handle, profile, state, ask, "hunt", _report)
    assert state.slot_mana["debilitation"] == 5
    assert state.slot_limit["debilitation"] == 7
    assert "hunt: DISCERN caps stun foe at 7 mana (minimum 1), starting at 5" in (
        handle.echoed
    )


def test_the_invoked_anklet_counts_against_the_estimate(monkeypatch):
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    handle = Handle()
    state = buffs.BuffState()
    buffs.discern_slots(handle, PROFILE, state, ask, "hunt", _report)
    assert state.buff_mana["heroic strength"] == 26  # streams, a step under 28
    handle.sent.clear()
    for _ in range(2):
        buffs.cast_buffs(handle, PROFILE, state, ask, "hunt", _report)
    # 26 streams are 14 prepared and the anklet's 12; then the estimate's 28.
    assert _prepares(handle) == [
        "prepare heroic strength 14",
        "prepare heroic strength 16",
    ]
    assert handle.sent.count("invoke my anklet") == 2
    # Arcana locked: no charge, so the whole 28 is prepared.
    handle.state.experience["Arcana"]["mindstate"] = 34
    handle.sent.clear()
    buffs.cast_buffs(handle, PROFILE, state, ask, "hunt", _report)
    assert _prepares(handle) == ["prepare heroic strength 28"]
    assert "charge my anklet 12" not in handle.sent


def test_a_piece_worn_again_before_the_invoke_comes_off_for_it(monkeypatch):
    # 2026-10-04 15:12 (Cecil's ;hunt): a kill mid-cast, the SKIN found
    # both hands full and wore the anklet back on, and the INVOKE was
    # refused — the cast went without the charge.
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    handle = Handle()
    state = buffs.BuffState()
    buffs.discern_slots(handle, PROFILE, state, ask, "hunt", _report)
    handle.sent.clear()
    invokes = iter(
        [
            "Try though you may, you find it too clumsy to invoke the cambrinth "
            "anklet while wearing it.\n",
            ANSWERS["invoke my anklet"],
        ]
    )

    def worn_once(s, command):
        if command == "invoke my anklet":
            s.sent.append(command)
            return next(invokes)
        return ask(s, command)

    buffs.cast_buffs(handle, PROFILE, state, worn_once, "hunt", _report)
    at = handle.sent.index("remove my anklet")
    assert handle.sent[at - 1 : at + 3] == [
        "invoke my anklet",
        "remove my anklet",
        "invoke my anklet",
        "cast",
    ]


def test_a_collapse_at_the_estimate_holds_a_step_under(monkeypatch):
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    handle = Handle(arcana=34)
    state = buffs.BuffState()
    buffs.discern_slots(handle, PROFILE, state, ask, "hunt", _report)
    state.buff_mana["heroic strength"] = 28
    answers = dict(ANSWERS, cast="You gesture.\nYour spell backfires.\n")

    def backfire(s, command):
        s.sent.append(command)
        if command.startswith("prepare"):
            return "You begin chanting a prayer.\n"
        return answers.get(command, "")

    buffs.cast_buffs(handle, PROFILE, state, backfire, "hunt", _report)
    assert state.buff_mana["heroic strength"] == 26
    assert "heroic strength" in state.buff_cap


# Captured 2026-09-29 (Cecil's box-farm ;hunt, #390): DISCERN HOJ's
# estimate; the skill sentence is Heroic Strength's with Utility.
HOJ_DISCERN = (
    "It requires the Utility skill to cast effectively.\n"
    "The spell requires at minimum 5 mana streams and you think you can "
    "reinforce it with 7 more, for a total of 12 streams.\nRoundtime: 9 sec.\n"
)
HOJ_PROFILE = dict(PROFILE, buffs=["hands of justice"], train_casting=["Utility"])


def _hoj_handle():
    handle = Handle()
    handle.state.experience["Utility"] = {"rank": 40, "percent": 0, "mindstate": 0}
    handle.state.active_spells = {"Hands of Justice": 10}
    return handle


def test_a_charge_that_overfills_a_small_buff_stays_out_of_its_cast(monkeypatch):
    # Hands of Justice: minimum 5, total 12, the anklet's charge 12. The
    # ramp's 10 streams left nothing to prepare, the bare PREPARE and
    # the anklet made 17, and it backfired (2026-09-29).
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    handle = _hoj_handle()
    state = buffs.BuffState()
    answers = dict(ANSWERS, **{"discern hands of justice": HOJ_DISCERN})

    def hoj(s, command):
        s.sent.append(command)
        if command.startswith("prepare"):
            return "You begin chanting a prayer.\n"
        return answers.get(command, "")

    buffs.discern_slots(handle, HOJ_PROFILE, state, hoj, "hunt", _report)
    assert state.buff_mana["hands of justice"] == 10
    handle.sent.clear()
    buffs.cast_buffs(handle, HOJ_PROFILE, state, hoj, "hunt", _report)
    assert _prepares(handle) == ["prepare hands of justice 10"]
    assert "invoke my anklet" not in handle.sent
    assert "charge my anklet 12" not in handle.sent
    assert "hands of justice" not in state.training_spells_off


def test_a_backfire_at_minimum_with_the_charge_keeps_the_buff_training(monkeypatch):
    # With no DISCERN estimate the charge is tried; its backfire at the
    # minimum is the charge's fault, so the buff trains on without it.
    monkeypatch.setattr(buffs, "PREPARE_SECONDS", 0)
    handle = _hoj_handle()
    state = buffs.BuffState()
    answers = dict(
        ANSWERS,
        cast="You gesture.\nYour spell backfires.\n",
        **{
            "discern hands of justice": "It requires the Utility skill to cast effectively.\n"
        },
    )

    def backfire(s, command):
        s.sent.append(command)
        if command.startswith("prepare"):
            return "You begin chanting a prayer.\n"
        return answers.get(command, "")

    buffs.discern_slots(handle, HOJ_PROFILE, state, backfire, "hunt", _report)
    assert "hands of justice" not in state.buff_floor  # no estimate read
    state.buff_mana["hands of justice"] = 10
    handle.sent.clear()
    buffs.cast_buffs(handle, HOJ_PROFILE, state, backfire, "hunt", _report)
    assert "invoke my anklet" in handle.sent
    assert "hands of justice" in state.cambrinth_skip
    assert "hands of justice" not in state.training_spells_off
    assert any("cast without the anklet from here" in e for e in handle.echoed)
    handle.sent.clear()
    buffs.cast_buffs(handle, HOJ_PROFILE, state, ask, "hunt", _report)
    assert "invoke my anklet" not in handle.sent
    assert _prepares(handle) == ["prepare hands of justice 10"]
