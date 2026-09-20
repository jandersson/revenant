"""How ;train runs a plan — these tests are the manual.

Each task's script is started and watched until its skills reach the
target (the stop word first, then the kill), a command task cycles in
place, a time budget ends a task, and once every task is trained the
loop walks to the safe room, rests until the skills drain, rotates
the safe room, and goes again. Death stops everything, child included.
"""

import importlib.util
import json
import pathlib
from types import SimpleNamespace

import pytest

from client.game.mapdb import MapDB
from client.game.training import DEFAULTS, normalize

REPO = pathlib.Path(__file__).parents[2]


def _train():
    spec = importlib.util.spec_from_file_location(
        "train_script", REPO / "scripts/train.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


train = _train()
train.EXIT_WAIT = 0

MAP = MapDB(
    [
        {"id": 1, "uid": [1], "title": ["[Town Green]"], "tags": ["home"], "wayto": {}},
        {"id": 2, "uid": [2], "title": ["[The Bank]"], "tags": ["bank"], "wayto": {}},
    ]
)


STOP_TAKES = 5  # fake seconds a told child needs to finish and exit


class StopRequested(Exception):
    """The fake's ;stop: raised once the sleep budget is spent."""


class Fake:
    """A Script-handle stand-in with a clock and a timeline: each sleep
    advances the clock by the seconds slept and applies the next
    scripted exp window, so a test writes the mindstates it wants seen
    poll by poll. Child scripts are names in a set."""

    def __init__(self, timeline=(), args=(), exits=None, obeys_stop=True, sleeps=200):
        self.args = list(args)
        self.obeys_stop = obeys_stop  # a told child exits STOP_TAKES later
        self.sleeps = sleeps  # the ;stop after this many sleeps
        self.sent = []
        self.echoed = []
        self.started = []  # (name, args)
        self.told = []
        self.killed = []
        self.commands = []
        self.walks = []
        self.now = 0.0
        self.dead = False
        self.children = set()
        self.exits = exits or {}  # child name -> the fake clock time it exits
        self._timeline = list(timeline)
        self.state = SimpleNamespace(
            name="Lanival", experience={}, hostiles={}, compass=["north"]
        )
        self._advance()

    def _advance(self):
        """The next timeline step; a dry timeline holds its last state."""
        if not self._timeline:
            return
        step = self._timeline.pop(0)
        if callable(step):
            step(self)
        else:
            self.state.experience = {
                skill: {"rank": 1, "percent": 0, "mindstate": state}
                for skill, state in step.items()
            }

    # -- the handle API ------------------------------------------------

    def put(self, command):
        self.sent.append(command)
        answers = getattr(self, "answers", {}).get(command)
        self.pending = (
            [line + "\n" for line in answers.pop(0).splitlines()] if answers else []
        )

    def get(self, timeout=None, streams=("",)):
        pending = getattr(self, "pending", [])
        return pending.pop(0) if pending else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        if self.sleeps <= 0:
            raise StopRequested()
        self.sleeps -= 1
        self.now += seconds
        for name, when in list(self.exits.items()):
            if self.now >= when:
                self.children.discard(name)
        self._advance()

    def command(self, timeout=None):
        return self.commands.pop(0) if self.commands else None

    def run(self, name, args=()):
        if name in self.children:
            return False
        self.started.append((name, list(args)))
        self.children.add(name)
        return True

    def is_running(self, name):
        return name in self.children

    def tell(self, name, line):
        self.told.append((name, line))
        if self.obeys_stop and name in self.children:
            self.exits[name] = self.now + STOP_TAKES
        return name in self.children

    def kill(self, name):
        self.killed.append(name)
        self.children.discard(name)

    def crashed(self, name):
        return getattr(self, "crashes", {}).get(name)


@pytest.fixture(autouse=True)
def clock(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path / "training"))
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path / "profiles"))
    holder = {}

    def now():
        return holder["fake"].now

    monkeypatch.setattr(train, "clock", now)
    return holder


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    return True


def plan(**overrides):
    values = dict(DEFAULTS)
    values["poll"] = 10
    values["tasks"] = [
        {"name": "climbs", "script": "athletics", "skills": ["Athletics"]},
        {
            "name": "rats",
            "script": "hunt",
            "skills": ["Small Edged"],
            "return_word": "return",
            "return_grace": 30,
        },
    ]
    values.update(overrides)
    return normalize(values)


def run(clock, fake, current, cycles=1, db=MAP):
    clock["fake"] = fake
    try:
        train.run(fake, current, cycles, db=db, walk=walk)
    except StopRequested:
        pass
    return fake


def test_each_task_script_runs_until_its_skills_reach_the_target(clock):
    fake = run(
        clock,
        Fake(
            [
                {"Athletics": 5},
                {"Athletics": 20},
                {"Athletics": 30},  # climbs at target
                {"Athletics": 30, "Small Edged": 12},
                {"Athletics": 30, "Small Edged": 31},  # rats at target
                {"Athletics": 9, "Small Edged": 9},  # drained
            ]
        ),
        plan(),
    )
    assert fake.started == [("athletics", []), ("hunt", [])]
    assert fake.killed[0] == "athletics"
    assert fake.told == [("hunt", "return")]
    assert any("climbs at target — Athletics 30/30" in text for text in fake.echoed)
    assert any("rested" in text for text in fake.echoed)
    assert fake.echoed[-1] == "train: 1 cycle(s) done"


def test_the_return_word_gets_the_grace_then_the_kill(clock):
    fake = Fake([{"Small Edged": 5}, {"Small Edged": 31}], obeys_stop=False)
    run(clock, fake, plan(tasks=[plan()["tasks"][1]], rest_until=34))
    assert fake.told == [("hunt", "return")]
    assert fake.now >= 10 + 30  # a poll, then the grace waited out
    assert fake.killed == ["hunt"]


def test_a_script_that_obeys_its_return_word_is_never_killed(clock):
    fake = Fake([{"Small Edged": 5}, {"Small Edged": 31}])
    run(clock, fake, plan(tasks=[plan()["tasks"][1]], rest_until=34))
    assert fake.told == [("hunt", "return")]
    assert fake.killed == []
    assert any("rats at target" in text for text in fake.echoed)


def test_a_script_that_exits_on_its_own_ends_the_task_for_the_cycle(clock):
    fake = Fake(
        [{"Small Edged": 3}, {"Small Edged": 4}, {"Small Edged": 5}], exits={"hunt": 10}
    )
    run(clock, fake, plan(tasks=[plan()["tasks"][1]], rest_until=34))
    assert fake.started == [("hunt", [])]  # not restarted
    assert fake.killed == []
    assert any("its script ended on its own" in text for text in fake.echoed)


def test_a_task_already_at_target_is_skipped(clock):
    fake = run(
        clock,
        Fake(
            [{"Athletics": 32, "Small Edged": 2}]
            + [{"Athletics": 32, "Small Edged": 30}] * 7  # through hunt's stop
            + [{"Athletics": 5, "Small Edged": 5}]
        ),
        plan(),
    )
    assert fake.started == [("hunt", [])]


def test_a_command_task_cycles_its_commands_between_setup_and_teardown(clock):
    music = {
        "name": "music",
        "commands": ["play my flute", "hum"],
        "pace": 8,
        "skills": ["Performance"],
        "setup": ["get my flute"],
        "teardown": ["stow my flute"],
    }
    fake = run(
        clock,
        Fake([{"Performance": 0}, {"Performance": 10}, {"Performance": 30}, {}]),
        plan(tasks=[music]),
    )
    assert fake.sent[:4] == ["get my flute", "play my flute", "hum", "stow my flute"]
    assert fake.started == []


def test_the_time_budget_ends_a_task_that_never_reaches_the_target(clock):
    fake = Fake([{"Athletics": 5}] * 40 + [{}])
    run(clock, fake, plan(task_minutes=1, tasks=[plan()["tasks"][0]]))
    assert fake.killed == ["athletics"]
    assert any("time budget spent" in text for text in fake.echoed)
    assert 60 <= fake.now < 60 + 2 * 10  # a poll past the minute, no more


def test_a_skill_less_task_runs_its_budget_once_per_cycle(clock):
    fake = Fake([{}] * 12)
    run(clock, fake, plan(task_minutes=1, tasks=[{"name": "hum", "commands": ["hum"]}]))
    assert fake.sent.count("hum") >= 5
    assert any("hum time budget spent" in text for text in fake.echoed)


def test_after_training_the_loop_walks_to_the_safe_room_and_rests(clock):
    fake = run(
        clock,
        Fake(
            [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20}, {"Athletics": 10}]
        ),
        plan(safe_rooms=["home"], rest_commands=["sit"]),
    )
    assert fake.walks == [{1}]
    assert fake.sent == ["sit"]
    assert fake.echoed[-2:] == [
        "train: rested — the pool has drained",
        "train: 1 cycle(s) done",
    ]


def test_safe_rooms_rotate_cycle_by_cycle(clock):
    trained = {"Athletics": 30, "Small Edged": 30}
    drained = {"Athletics": 0, "Small Edged": 0}
    fake = run(
        clock,
        Fake([trained, drained, trained, drained]),
        plan(safe_rooms=["home", "bank"]),
        cycles=2,
    )
    # Each cycle: trained already, so straight to the safe room; the
    # second cycle's climbs runs once its skills drained (spent resets).
    assert fake.walks == [{1}, {2}]


def test_the_rest_cap_ends_a_rest_that_will_not_drain(clock):
    fake = Fake([{"Athletics": 30, "Small Edged": 30}] * 20)
    run(clock, fake, plan(rest_minutes=1))
    assert any("1 minutes of rest — moving on" in text for text in fake.echoed)


def test_hostiles_at_the_safe_room_send_the_rest_to_the_next_one(clock):
    def ambush(fake):
        fake.state.hostiles = {"1": True}

    def clear(fake):
        fake.state.hostiles = {}

    trained = {"Athletics": 30, "Small Edged": 30}
    fake = Fake([trained, ambush, clear, {"Athletics": 0, "Small Edged": 0}])
    run(clock, fake, plan(safe_rooms=["home", "bank"], rest_commands=["sit"]))
    assert fake.walks == [{1}, {2}]
    assert fake.sent == ["sit", "retreat", "retreat", "north", "sit"]


def test_with_one_safe_room_hostiles_send_the_rest_next_door(clock):
    # #182 (2026-09-12): the loop stood among rats "resting" for twenty
    # minutes, the attacked skills locked, the rest never draining.
    def ambush(fake):
        fake.state.hostiles = {"1": True}

    def clear(fake):
        fake.state.hostiles = {}

    trained = {"Athletics": 30, "Small Edged": 30}
    fake = Fake([trained, ambush, clear, {"Athletics": 0, "Small Edged": 0}])
    run(clock, fake, plan(safe_rooms=["home"], rest_commands=["sit"]))
    assert fake.walks == [{1}]  # no walk back: rest where the burst landed
    assert fake.sent == ["sit", "retreat", "retreat", "north", "sit"]
    assert any("leaving the room to rest next door" in text for text in fake.echoed)
    assert not any("intervene" in text for text in fake.echoed)


def test_a_rest_hostiles_keep_finding_is_given_up_for_the_cycle(clock):
    def ambush(fake):
        fake.state.hostiles = {"1": True}

    trained = {"Athletics": 30, "Small Edged": 30}
    fake = Fake([trained, ambush] + [ambush] * 20)
    run(clock, fake, plan(safe_rooms=[]))
    assert fake.sent.count("retreat") == 2 * train.LEAVE_ATTEMPTS
    assert any("giving it up for this cycle" in text for text in fake.echoed)


def test_death_stops_the_loop_and_kills_the_task_script(clock):
    def die(fake):
        fake.dead = True

    fake = Fake([{"Athletics": 5}, die, {"Athletics": 5}])
    run(clock, fake, plan())
    assert fake.killed == ["athletics"]
    assert fake.echoed[-1] == "train: you are dead — stopping; deathwatch has it"


def test_train_skip_ends_the_current_task_and_rest_rests_now(clock):
    fake = Fake([{"Athletics": 5}] * 6 + [{}])
    fake.commands = ["skip"]
    run(clock, fake, plan(tasks=[plan()["tasks"][0]]))
    assert fake.killed == ["athletics"]
    assert any("climbs skipped" in text for text in fake.echoed)

    fake = Fake([{"Athletics": 5}] * 6 + [{}])
    fake.commands = ["rest"]
    run(clock, fake, plan())
    assert fake.started == [("athletics", [])]  # rats never ran
    assert any("resting on request" in text for text in fake.echoed)


def test_train_status_answers_while_running(clock):
    fake = Fake([{"Athletics": 5}, {"Athletics": 30}, {}])
    fake.commands = ["status", "dance"]
    run(clock, fake, plan(tasks=[plan()["tasks"][0]]))
    assert "  Athletics: 5/34" in fake.echoed
    assert any(
        "I understand ;train skip / rest / status" in text for text in fake.echoed
    )


def test_a_script_gone_within_seconds_is_a_failed_start(clock):
    # #182: ;attune started in a rat room and ended at once on its own
    # hostiles rule; the loop called the task trained and went to rest.
    fake = Fake([{"Athletics": 5}] * 10, exits={"athletics": 1})
    run(clock, fake, plan(tasks=[plan()["tasks"][0]], poll=1))
    assert any("a failed start" in text for text in fake.echoed)
    assert any("no task trained this cycle" in text for text in fake.echoed)
    assert fake.walks == []  # and no rest


def test_a_cycle_with_one_trained_task_still_rests(clock):
    fake = Fake(
        [{"Athletics": 5, "Small Edged": 3}] * 3
        + [{"Athletics": 5, "Small Edged": 30}],
        exits={"athletics": 1},
    )
    run(clock, fake, plan(poll=1, safe_rooms=["home"], rest_until=34))
    assert any("a failed start" in text for text in fake.echoed)
    assert fake.walks == [{1}]  # rats trained, so the cycle rests


def test_a_script_that_crashed_is_a_failed_task_with_its_error(clock):
    # #181: ;hunt died with a traceback and the loop read it as "ended
    # on its own"; the handle remembers the crash now.
    fake = Fake([{"Small Edged": 3}] * 10, exits={"hunt": 20})
    fake.crashes = {"hunt": "ValueError('too many values to unpack') (walker.py:225)"}
    run(clock, fake, plan(tasks=[plan()["tasks"][1]]))
    assert any(
        ";hunt crashed — ValueError('too many values to unpack')" in text
        for text in fake.echoed
    )
    assert any("no task trained this cycle" in text for text in fake.echoed)
    assert fake.walks == []


def test_a_script_that_cannot_start_is_skipped(clock):
    fake = Fake([{"Athletics": 5}, {}])
    fake.children.add("athletics")  # the user's own ;athletics is running
    run(clock, fake, plan(tasks=[plan()["tasks"][0]], rest_until=34))
    assert any("could not start ;athletics" in text for text in fake.echoed)
    assert fake.killed == []


# -- ;train's words -------------------------------------------------------


def test_train_init_writes_the_starter_and_refuses_to_overwrite(clock, tmp_path):
    fake = Fake(args=["init"])
    clock["fake"] = fake
    train.main(fake)
    path = tmp_path / "training" / "lanival.json"
    assert path.is_file()
    written = json.loads(path.read_text())
    assert [task["script"] for task in written["tasks"]] == [
        "athletics",
        "hunt",
        "skins",
        "bank",
        "forage",
    ]
    train.main(Fake(args=["init"]))
    fake = Fake(args=["init"])
    train.main(fake)
    assert any("exists" in text for text in fake.echoed)
    path.write_text("{}")
    train.main(Fake(args=["init", "force"]))
    assert json.loads(path.read_text())["tasks"]


def test_train_plan_prints_the_plan_and_a_broken_one_refuses_to_run(clock, tmp_path):
    (tmp_path / "training").mkdir()
    (tmp_path / "training" / "lanival.json").write_text(
        json.dumps({"tasks": [{"name": "neither"}]})
    )
    fake = Fake(args=["plan"])
    train.main(fake)
    assert any("neither: no skills" in text for text in fake.echoed)
    fake = Fake(args=[])
    train.main(fake)
    assert any("names no script and no commands" in text for text in fake.echoed)
    assert fake.started == []


def test_train_without_a_plan_points_at_init(clock):
    fake = Fake(args=[])
    train.main(fake)
    assert any(";train init writes a starter" in text for text in fake.echoed)


# --- the soul deeds in the rests (#227) ------------------------------------
def test_a_rest_runs_the_due_soul_deed_and_walks_back(clock, monkeypatch, tmp_path):
    from client.game import soul

    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path / "soul"))
    import time

    now = time.time()  # soul's timers run on the wall clock, not the fake's
    # The tithe never done, the soul read steady white just now (below
    # pristine: the deeds run).
    soul.save_timers("Lanival", soul.mark_state({"badge": now, "pray": now}, 5, now))
    fake = Fake(
        [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20}, {"Athletics": 10}],
        exits={"soul": 15},
    )
    run(clock, fake, plan(safe_rooms=["home"], rest_commands=["sit"], soul="on"))
    # The tithe (never done) is the one deed due; the badge and the
    # prayer were just done and their timers have not cleared.
    assert fake.started == [("soul", ["tithe"])]
    assert fake.walks == [{1}, {1}]  # the rest's room, then back after the tithe
    assert fake.sent == ["sit", "sit"]
    assert any("soul deed — ;soul tithe" in text for text in fake.echoed)


def test_a_fresh_pristine_reading_skips_the_deeds_and_none_asks_for_one(
    clock, monkeypatch, tmp_path
):
    # The operator, 2026-09-20: at pristine no soul action in ;train;
    # with no reading the reading comes first (#231).
    from client.game import soul

    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path / "soul"))
    import time

    now = time.time()
    soul.save_timers("Lanival", soul.mark_state({}, 7, now))  # the tithe never done
    fake = Fake(
        [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20}, {"Athletics": 10}],
        exits={"soul": 15},
    )
    run(clock, fake, plan(soul="on"))
    assert fake.started == []
    soul.save_timers("Lanival", {"badge": now, "pray": now})  # no reading at all
    fake = Fake(
        [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20}, {"Athletics": 10}],
        exits={"soul": 15},
    )
    run(clock, fake, plan(soul="on"))
    assert fake.started[0] == ("soul", ["read"])
    assert any("soul reading — ;soul read" in text for text in fake.echoed)


def test_train_takes_a_running_soul_keep_over(clock):
    fake = Fake([{"Athletics": 30, "Small Edged": 30}, {"Athletics": 10}])
    fake.children.add("soul")
    run(clock, fake, plan(soul="on"))
    assert fake.killed[0] == "soul"
    assert any("taking over ;soul" in text for text in fake.echoed)


def test_a_plan_with_soul_off_never_touches_it(clock, monkeypatch, tmp_path):
    from client.game import soul

    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path / "soul"))
    soul.save_timers("Lanival", {})
    fake = Fake([{"Athletics": 30, "Small Edged": 30}, {"Athletics": 10}])
    fake.children.add("soul")
    run(clock, fake, plan())
    assert fake.started == [] and fake.killed == []


# --- TDPs spent in the rests (#230) -------------------------------------------
INFO_TEXT = (
    "Name: Lanival Redeemer   Race: Dwarf   Guild: Paladin\n"
    "     Strength :  10              Reflex :   8\n"
    "      Agility :   8            Charisma :  10\n"
    "   Discipline :  12              Wisdom :  10\n"
    " Intelligence :  10             Stamina :  12\n"
    "         TDPs : 347\n"
)


def _tdp_fake(rounds=4):
    fake = Fake(
        [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20}, {"Athletics": 10}],
        exits={"tdp": 15},
    )
    fake.answers = {"info": [INFO_TEXT] * rounds}
    return fake


def test_a_rest_buys_the_plans_next_stat_point_through_tdp(clock, monkeypatch):
    monkeypatch.setattr(train, "INFO_SECONDS", 0.01)
    monkeypatch.setattr(train, "INFO_TAIL", 0.01)
    fake = _tdp_fake()
    run(clock, fake, plan(tdp=["stamina 30"]))
    # Stamina 12 at 36 TDPs a point, 347 on hand: three points a rest at most.
    assert fake.started[:3] == [("tdp", ["train", "stamina", "+1"])] * 3
    assert fake.sent.count("info") == 3
    assert any("Stamina 12 → 13" in text for text in fake.echoed)


def test_auto_buys_the_guilds_tier_and_the_reserve_holds_points_back(
    clock, monkeypatch
):
    monkeypatch.setattr(train, "INFO_SECONDS", 0.01)
    monkeypatch.setattr(train, "INFO_TAIL", 0.01)
    fake = _tdp_fake()
    run(clock, fake, plan(tdp=["auto"]))
    assert fake.started[0] == (
        "tdp",
        ["train", "strength", "+1"],
    )  # the Paladin's first tier
    held = _tdp_fake()
    run(clock, held, plan(tdp=["auto"], tdp_reserve=340))
    assert held.started == []  # 347 - 340 covers no 30-TDP point


def test_no_tdp_plan_asks_no_info(clock):
    fake = _tdp_fake()
    run(clock, fake, plan())
    assert "info" not in fake.sent
