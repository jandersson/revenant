"""Interludes — these tests are the manual. A chore due (the profile's
almanac on its timer, or a typed `;break almanac`) runs at the next
safe point of whatever script reaches one; with both hands full the
left hand's item is stowed for it and got back after
(client/game/interlude.py, #372)."""

from types import SimpleNamespace

import pytest

from client.game import almanac, interlude, loop
from client.game.profile import save_profile

STUDIED = (
    "You set about studying your diamond-hide almanac intently.  You believe "
    "you've learned something significant about Bow!\nRoundtime: 10 seconds\n"
)
GLEANED = (
    "You've gleaned all the insight you can from the diamond-hide almanac, for "
    "now.\n[Please try again in 9 roisaen.]\n"
)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(almanac, "clock", lambda: now["t"])
    monkeypatch.setattr(almanac, "_NEXT", {})
    monkeypatch.setattr(almanac, "_OFF", set())
    monkeypatch.setattr(interlude, "_PENDING", set())
    monkeypatch.setattr(interlude, "_DEFERRED", {})
    monkeypatch.setattr(interlude, "clock", lambda: now["t"])
    monkeypatch.setattr(interlude, "_PROFILE", {})
    return now


class Game:
    """The game's side: answers by command prefix, the hands kept."""

    def __init__(self, s, answers=None):
        self.s = s
        self.sent = []
        self.answers = {"study": STUDIED} | (answers or {})

    def __call__(self, s, command):
        self.sent.append(command)
        state = s.state
        verb, _, noun = command.partition(" my ")
        for prefix, text in self.answers.items():
            if command.startswith(prefix):
                return text
        if verb in ("stow", "put"):
            noun = noun.split(" in ")[0]
            for side in ("left_hand", "right_hand"):
                if (getattr(state, side) or {}).get("noun") == noun:
                    setattr(state, side, None)
            return f"You put your {noun} in your backpack.\n"
        if verb == "get":
            side = "left_hand" if state.left_hand is None else "right_hand"
            setattr(state, side, {"noun": noun})
            return f"You get a {noun} from inside your backpack.\n"
        return ""


def handle(monkeypatch, script="perform", left=None, right=None, answers=None):
    echoed, put = [], []
    s = SimpleNamespace(
        name=script,
        state=SimpleNamespace(
            name="Lanival", left_hand=left, right_hand=right, hostiles={}, stunned=False
        ),
        dead=False,
        echo=echoed.append,
        echoed=echoed,
        put=lambda command, cleanup=False: put.append(command),
        waitrt=lambda: None,
        command=lambda timeout=None: None,
    )
    game = Game(s, answers)
    monkeypatch.setattr(interlude, "ask", game)
    return s, game


def with_almanac():
    save_profile("Lanival", {"almanac": "almanac"})


def test_nothing_is_due_without_an_almanac_in_the_profile(monkeypatch):
    s, game = handle(monkeypatch)
    interlude.run_due(s)
    assert game.sent == []


def test_due_names_the_chores_without_sending(monkeypatch):
    # #417: a climb practice asks first, so STOP CLIMB goes out only for
    # a chore that will run; never for ;favors, never past the timer.
    with_almanac()
    s, game = handle(monkeypatch, right={"noun": "lute"})
    assert interlude.due(s) == ["almanac"]
    assert game.sent == []
    interlude.run_due(s)
    assert interlude.due(s) == []  # the timer
    favors, _ = handle(monkeypatch, "favors")
    assert interlude.due(favors) == []


def test_a_due_almanac_is_studied_with_a_free_hand_and_named_under_the_script(
    monkeypatch,
):
    with_almanac()
    s, game = handle(monkeypatch, right={"noun": "lute"})
    interlude.run_due(s)
    assert game.sent == ["get my almanac", "study my almanac", "stow my almanac"]
    assert s.echoed == ["interlude: almanac studied — Bow"]
    interlude.run_due(s)  # the timer: ten minutes before the next
    assert len(game.sent) == 3


def test_full_hands_make_room_the_left_item_stowed_and_got_back(monkeypatch):
    # ;remedies after a crush: the remedy stays in the stowed mortar.
    with_almanac()
    s, game = handle(
        monkeypatch, "remedies", left={"noun": "mortar"}, right={"noun": "pestle"}
    )
    interlude.run_due(s)
    assert game.sent == [
        "stow my mortar",
        "get my almanac",
        "study my almanac",
        "stow my almanac",
        "get my mortar",
    ]
    assert s.state.left_hand == {"noun": "mortar"}
    assert s.state.right_hand == {"noun": "pestle"}


def test_boxes_and_perform_wait_for_a_free_hand_and_favors_never(monkeypatch):
    with_almanac()
    for script in ("boxes", "perform"):
        s, game = handle(
            monkeypatch, script, left={"noun": "box"}, right={"noun": "lockpick"}
        )
        interlude.run_due(s)
        assert game.sent == []
    s, game = handle(monkeypatch, "favors")
    interlude.run_due(s)
    assert game.sent == []
    s, game = handle(
        monkeypatch, "hunt", left={"noun": "shield"}, right={"noun": "mace"}
    )
    interlude.run_due(s, make_room=False)  # ;hunt's clear room keeps both
    assert game.sent == []


def test_never_with_a_hostile_a_stun_or_a_dead_character(monkeypatch):
    with_almanac()
    for trouble in (
        {"hostiles": {"1": "a goblin"}},
        {"stunned": True},
    ):
        s, game = handle(monkeypatch)
        vars(s.state).update(trouble)
        interlude.run_due(s)
        assert game.sent == []
    s, game = handle(monkeypatch)
    s.dead = True
    interlude.run_due(s)
    assert game.sent == []


def test_a_stow_refused_leaves_the_hands_and_the_chore_waits(monkeypatch):
    # Since #416 a no-room refusal asks STORE DEFAULT for a fallback
    # container; an answer naming none leaves the mortar in hand.
    monkeypatch.setattr(interlude.hands, "_DEFAULTS", {})
    with_almanac()
    s, game = handle(
        monkeypatch,
        "remedies",
        left={"noun": "mortar"},
        right={"noun": "pestle"},
        answers={"stow my mortar": "There isn't any more room in the backpack.\n"},
    )
    interlude.run_due(s)
    assert game.sent == ["stow my mortar", "store default"]
    assert "the chore waits" in s.echoed[0]


WEALTH_OF_GEMS = (
    "You've already got a wealth of gems in there!  You'd better tie it up "
    "before putting more gems inside.\n"
)  # a full gem pouch, captured 2026-10-03 (#436)


def test_a_full_gem_pouch_sends_the_gem_to_the_default_container(monkeypatch):
    # 20:19 on 2026-10-03: the pouch's answer read as stowed, the gem
    # stayed in hand, and the almanac was tried at every safe point.
    monkeypatch.setattr(interlude.hands, "_DEFAULTS", {})
    with_almanac()
    s, game = handle(
        monkeypatch,
        "athletics",
        left={"noun": "chrysoprase"},
        right={"noun": "rope"},
        answers={
            "stow my chrysoprase": WEALTH_OF_GEMS,
            "store default": "         Default:  a rugged backpack\n",
        },
    )
    interlude.run_due(s)
    assert game.sent == [
        "stow my chrysoprase",
        "store default",
        "put my chrysoprase in my backpack",
        "get my almanac",
        "study my almanac",
        "stow my almanac",
    ]
    assert "the chrysoprase went in the backpack" in s.echoed[0]
    # A gem is never put back in the hand (#484): it was held only
    # because the pouch refused it, and holding it cost the badge deed.
    assert "the chrysoprase stays stowed" in s.echoed[-1]


def test_a_chore_that_cannot_act_waits_five_minutes_not_every_safe_point(
    monkeypatch, fresh
):
    # The shape of #436: a STOW the game answered without freeing the
    # hand, the almanac silent for want of one, and the next safe point
    # three seconds on doing it all again.
    with_almanac()
    s, game = handle(
        monkeypatch,
        "athletics",
        left={"noun": "chrysoprase"},
        right={"noun": "rope"},
        answers={"stow my chrysoprase": "You fiddle with the chrysoprase.\n"},
    )
    interlude.run_due(s)
    assert game.sent == ["stow my chrysoprase"]  # a gem is not got back (#484)
    fresh["t"] += 3
    assert interlude.due(s) == []  # no STOP CLIMB for it either (#417)
    interlude.run_due(s)
    assert len(game.sent) == 1
    fresh["t"] += interlude.DEFER_SECONDS
    assert interlude.due(s) == ["almanac"]
    # A STOW refused outright waits the same.
    refused, game = handle(
        monkeypatch,
        "remedies",
        left={"noun": "mortar"},
        right={"noun": "pestle"},
        answers={"stow my mortar": "You can't do that right now.\n"},
    )
    interlude._DEFERRED.clear()
    interlude.run_due(refused)
    assert interlude.due(refused) == []


def test_an_item_that_does_not_come_back_is_said(monkeypatch):
    with_almanac()
    s, game = handle(
        monkeypatch,
        "remedies",
        left={"noun": "mortar"},
        right={"noun": "pestle"},
        answers={"get my mortar": "What were you referring to?\n"},
    )
    interlude.run_due(s)
    assert game.sent[-1] == "get my mortar"
    assert "the mortar did not come back" in s.echoed[-1]


def test_a_break_forces_the_almanac_past_the_local_timer_once(monkeypatch, fresh):
    with_almanac()
    almanac._NEXT["almanac"] = fresh["t"] + 300  # studied by hand, say
    s, game = handle(monkeypatch)
    interlude.run_due(s)
    assert game.sent == []
    assert interlude.post("almanac") and interlude.pending() == ["almanac"]
    assert not interlude.post("nap")
    game.answers["study"] = GLEANED  # the game's countdown decides
    interlude.run_due(s)
    assert "study my almanac" in game.sent and interlude.pending() == []
    # "9 roisaen" is rounded down: ten minutes, and the slack.
    assert almanac._NEXT["almanac"] == fresh["t"] + 600 + 20


def test_the_countdown_is_read_rounded_up_and_about_a_roisan_is_a_minute():
    # Captured 2026-09-28: "9 roisaen" with 9:48 left, and 13 s early
    # the next try's "about a roisan".
    assert almanac.answer(GLEANED) == ("waiting", None, 600)
    about = (
        "You've gleaned all the insight you can from the diamond-hide almanac, "
        "for now.\n[Please try again in about a roisan.]\n"
    )
    assert almanac.answer(about) == ("waiting", None, 60)


def test_a_parent_waiting_on_its_child_leaves_the_chore_to_the_child(monkeypatch):
    # 2026-09-28: ;remedies studied while its ;forage foraged, and read
    # ;forage's "...wait 4 seconds." as the STUDY's answer.
    with_almanac()
    s, game = handle(monkeypatch, "remedies")
    s.younger_scripts = lambda: ["forage"]
    interlude.run_due(s)
    assert game.sent == []
    s.younger_scripts = lambda: ["xp", "sheet"]  # monitors act on nothing
    interlude.run_due(s)
    assert "study my almanac" in game.sent


def test_a_break_waits_out_a_hostile_and_is_honored_after(monkeypatch):
    with_almanac()
    s, game = handle(monkeypatch)
    s.state.hostiles = {"1": "a goblin"}
    interlude.post("almanac")
    interlude.run_due(s)
    assert game.sent == [] and interlude.pending() == ["almanac"]
    s.state.hostiles = {}
    interlude.run_due(s)
    assert "study my almanac" in game.sent and interlude.pending() == []


def test_every_safe_point_runs_the_interludes(monkeypatch):
    # loop.wants_stop — called by every trainer between steps, and by
    # pause() once a second.
    with_almanac()
    s, game = handle(monkeypatch, "athletics")
    assert loop.wants_stop(s) is False
    assert "study my almanac" in game.sent


def test_the_item_stowed_for_a_chore_comes_back_by_its_id(monkeypatch):
    # 2026-10-07: GET MY JADE after the almanac took another jade out of
    # the tote; the hand tag's id names the one that went (#484).
    with_almanac()
    s, game = handle(
        monkeypatch,
        "remedies",
        left={"noun": "mortar", "exist": "77"},
        right={"noun": "pestle", "exist": "78"},
    )
    interlude.run_due(s)
    assert game.sent[0] == "stow my mortar"
    assert game.sent[-1] == "get #77"
