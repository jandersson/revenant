"""The readable state view: flags by name, posture as a word, hands as
nouns, timers as seconds left, and the one-line summary — all derived
on access from the parser's raw fields."""

from types import SimpleNamespace

from client.game.status import status


def state(**overrides):
    base = dict(
        indicator={"IconSTANDING": "y", "IconBLEEDING": "y", "IconDEAD": "n"},
        vitals={"health": 92, "stamina": 100, "concentration": 88},
        left_hand={"noun": "greaves", "exist": "1", "name": "some light plate greaves"},
        right_hand=None,
        room_title="[Provincial Bank, Teller]",
        room_uid=19104,
        hostiles={},
        roundtime=1789228600,
        casttime=0,
        server_time=1789228595,
        experience={"Attunement": {"rank": 2, "percent": 16, "mindstate": 6}},
        injuries={"head": ("wound", 1)},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_flags_and_posture_read_off_the_indicators():
    view = status(state())
    assert view.standing and view.posture == "standing" and not view.prone
    assert view.bleeding and not view.stunned and not view.dead
    assert view.badges == ["bleeding"]
    assert view.can_act
    view = status(
        state(indicator={"IconPRONE": "y", "IconSTUNNED": "y", "IconWEBBED": "y"})
    )
    assert view.posture == "prone" and view.prone
    assert view.badges == ["stunned", "webbed"]
    assert not view.can_act


def test_dead_leads_the_badges_and_stops_action():
    view = status(
        state(indicator={"IconDEAD": "y", "IconPRONE": "y", "IconBLEEDING": "y"})
    )
    assert view.dead and view.badges == ["dead", "bleeding"]
    assert not view.can_act


def test_hands_vitals_room_and_mindstates():
    view = status(state())
    assert view.left_hand == "greaves" and view.right_hand is None
    assert not view.hands_empty
    assert view.health == 92 and view.vitals["concentration"] == 88
    assert view.room == "[Provincial Bank, Teller]" and view.room_uid == 19104
    assert view.mindstate("Attunement") == 6 and view.mindstates == {"Attunement": 6}
    assert view.mindstate("Athletics") is None
    assert view.injuries == {"head": ("wound", 1)}


def test_timers_count_down_by_the_game_clock():
    view = status(state())
    assert view.roundtime == 5 and view.casttime == 0
    assert status(state(server_time=1789228601)).roundtime == 0
    assert status(state(server_time=None)).roundtime == 0  # the clock not heard yet


def test_the_view_is_live_not_a_snapshot():
    st = state()
    view = status(st)
    assert view.posture == "standing"
    st.indicator = {"IconKNEELING": "y"}
    assert view.posture == "kneeling"


def test_the_summary_is_one_line_in_the_strip_s_order():
    view = status(state(hostiles={"a rat": 2}))
    assert view.summary() == (
        "[Provincial Bank, Teller] | standing bleeding | he 92%  st 100%  co 88% | "
        "L greaves R - | hostiles: a rat | RT 5"
    )
    assert (
        status(state(indicator={"IconDEAD": "y"}, hostiles={}))
        .summary()
        .startswith("[Provincial Bank, Teller] | DEAD |")
    )
    assert status(SimpleNamespace()).summary() == "L - R -"
