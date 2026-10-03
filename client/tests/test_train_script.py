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
    values["top_up"] = "off"  # whole rests; the top-up has its own tests
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


def test_a_rest_opens_with_the_drain_models_guess(clock, monkeypatch):
    # Athletics at 30 and 20 buckets above the floor of 10, tertiary for
    # a Paladin at rank 72: 20 / 0.65 pulses of 200 s, about 103 min (#300).
    def trained(fake):
        fake.state.experience = {
            "Athletics": {"rank": 72, "percent": 0, "mindstate": 30},
            "Small Edged": {"rank": 41, "percent": 0, "mindstate": 30},
        }

    monkeypatch.setattr(train, "drain_inputs", lambda name: ("Paladin", 15))
    fake = run(clock, Fake([trained, {"Athletics": 10}]), plan(safe_rooms=["home"]))
    assert (
        "train: the drain model expects about 103 min — Athletics drains last"
        in fake.echoed
    )


def test_a_rest_without_a_known_guild_says_no_guess(clock, monkeypatch):
    monkeypatch.setattr(train, "drain_inputs", lambda name: (None, None))
    fake = run(
        clock, Fake([{"Athletics": 30, "Small Edged": 30}, {"Athletics": 10}]), plan()
    )
    assert not any("drain model" in text for text in fake.echoed)


def test_guild_and_wisdom_come_from_the_latest_sheet_snapshot(monkeypatch, tmp_path):
    import sqlite3

    path = tmp_path / "history.db"
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(path))
    assert train.drain_inputs("Lanival") == (None, None)  # no tables yet
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE character (character_name, logged_at, guild)")
    connection.execute("CREATE TABLE stats (character_name, logged_at, stat, value)")
    connection.executemany(
        "INSERT INTO character VALUES (?, ?, ?)",
        [
            ("Lanival", "2026-09-01T00:00:00", "Commoner"),
            ("Lanival", "2026-09-20T00:00:00", "Paladin"),
            ("Sable", "2026-09-21T00:00:00", "Moon Mage"),
        ],
    )
    connection.executemany(
        "INSERT INTO stats VALUES (?, ?, ?, ?)",
        [
            ("Lanival", "2026-09-01T00:00:00", "Wisdom", 10),
            ("Lanival", "2026-09-20T00:00:00", "Wisdom", 15),
            ("Lanival", "2026-09-20T00:00:00", "Strength", 20),
        ],
    )
    connection.commit()
    connection.close()
    assert train.drain_inputs("Lanival") == ("Paladin", 15)


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
    # each leave is the shared escape's full burst loop now (#285):
    # two retreats per burst, flight.ATTEMPTS bursts per attempt
    from client.game import flight

    assert fake.sent.count("retreat") == 2 * flight.ATTEMPTS * train.LEAVE_ATTEMPTS
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


def test_train_task_names_one_task_of_the_plan():
    # ;train task <name> runs that task once, no rest (2026-09-22).
    p = plan()
    assert train.task_named(p, "Climbs")["name"] == "climbs"
    assert train.task_named(p, "nosuch") is None
    assert train.following_task(p, train.task_named(p, "climbs"))["name"] == "rats"
    assert train.following_task(p, p["tasks"][-1]) is None


def test_train_status_answers_while_running(clock):
    fake = Fake([{"Athletics": 5}, {"Athletics": 30}, {}])
    fake.commands = ["status", "dance"]
    run(clock, fake, plan(tasks=[plan()["tasks"][0]]))
    assert "  Athletics: 5/34" in fake.echoed
    assert any(
        "I understand ;train skip / rest / return / status" in text
        for text in fake.echoed
    )


def test_train_return_hands_the_task_its_return_word_and_ends_the_run(clock):
    # #338 (2026-09-26): ;train return was not understood, and ending a
    # run took ;hunt return, then ;stop train once home, by hand.
    rats = plan()["tasks"][1]
    fake = Fake([{"Small Edged": 5}] * 20)
    fake.commands = ["return"]
    run(clock, fake, plan(tasks=[rats, plan()["tasks"][0]]), cycles=0)
    assert fake.told == [("hunt", "return")]
    assert fake.killed == []  # it finished within the grace
    assert fake.started == [("hunt", [])]  # no next task
    assert fake.walks == []  # and no rest
    assert any("rats returned on request" in text for text in fake.echoed)
    assert fake.echoed[-1] == "train: returned on request — the run ends here"


def test_train_return_during_the_rest_ends_the_run_without_a_next_cycle(clock):
    def typed(fake):
        fake.commands.append("return")

    fake = Fake([{"Athletics": 5}, {"Athletics": 30}, typed] + [{"Athletics": 30}] * 5)
    run(clock, fake, plan(tasks=[plan()["tasks"][0]]), cycles=0)
    assert fake.started == [("athletics", [])]  # one cycle, none after
    assert fake.echoed[-1] == (
        "train: returned on request — the rest and the run end here"
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
        "hunt",  # it sells its skins and banks as it ends
        "repair",
        "bank",
        "tdp",
        "forage",
    ]
    # The operator, 2026-10-03: "i have no idea what any of the things
    # do" — init says where each setting is explained.
    assert any("File > Training Plan..." in text for text in fake.echoed)
    train.main(Fake(args=["init"]))
    fake = Fake(args=["init"])
    train.main(fake)
    assert any("exists" in text for text in fake.echoed)
    path.write_text("{}")
    train.main(Fake(args=["init", "force"]))
    assert json.loads(path.read_text())["tasks"]


def test_train_init_writes_no_hunt_for_an_empath(clock, tmp_path, monkeypatch):
    monkeypatch.setattr(train, "drain_inputs", lambda name: ("Empath", None))
    fake = Fake(args=["init"])
    clock["fake"] = fake
    train.main(fake)
    written = json.loads((tmp_path / "training" / "lanival.json").read_text())
    assert "hunt" not in [task["script"] for task in written["tasks"]]
    assert any("empathic shock" in text for text in fake.echoed)


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
    assert any("names no script, commands or helper" in text for text in fake.echoed)
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


def test_an_announced_shutdown_winds_the_task_down_and_ends_the_run(clock):
    # #277: the parser's shutdown_at within the plan's shutdown_minutes
    # gets the hunt its return word, and ;train stops instead of resting.
    def announce(fake):
        fake.state.experience = {
            "Athletics": {"rank": 1, "percent": 0, "mindstate": 30},
            "Small Edged": {"rank": 1, "percent": 0, "mindstate": 12},
        }
        fake.state.server_time = 1000
        fake.state.shutdown_at = 1000 + 120  # two minutes: under the three

    fake = run(
        clock,
        Fake(
            [
                {"Athletics": 30},
                {"Athletics": 30, "Small Edged": 5},
                announce,
                {"Athletics": 30, "Small Edged": 12},
            ]
        ),
        plan(),
    )
    assert fake.started == [("hunt", [])]
    assert fake.told == [("hunt", "return")]
    assert any("wound down for the game's shutdown" in text for text in fake.echoed)
    assert fake.echoed[-1].startswith("train: the game is shutting down")
    assert not any("resting until" in text for text in fake.echoed)


def test_a_rest_short_of_a_point_asks_info_once_and_says_so_once(clock, monkeypatch):
    # #282: 247 INFOs in an afternoon for 5 points against a 45-point
    # cost. One INFO prices the point; the polls after read the exp
    # window's count and stay quiet.
    monkeypatch.setattr(train, "INFO_SECONDS", 0.01)
    monkeypatch.setattr(train, "INFO_TAIL", 0.01)
    fake = Fake(
        [{"Athletics": 30, "Small Edged": 30}]
        + [{"Athletics": 20}] * 8
        + [{"Athletics": 10}],
        exits={"tdp": 15},
    )
    fake.answers = {"info": [INFO_TEXT.replace("347", "5")] * 12}
    fake.state.tdps = 5
    run(clock, fake, plan(tdp=["auto"]))
    assert fake.sent.count("info") == 1
    assert fake.started == []
    said = [text for text in fake.echoed if "no stat this rest" in text]
    assert said == [
        "train: 5 TDPs, the next point (Strength 10 → 11) costs 30 — no stat this rest"
    ]


def test_the_windows_count_rising_past_the_cost_prices_again_and_buys(
    clock, monkeypatch
):
    monkeypatch.setattr(train, "INFO_SECONDS", 0.01)
    monkeypatch.setattr(train, "INFO_TAIL", 0.01)

    def richer(fake):
        fake.state.experience = {
            "Athletics": {"rank": 1, "percent": 0, "mindstate": 20}
        }
        fake.state.tdps = 40  # the window says a point is affordable now

    fake = Fake(
        [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20}, {"Athletics": 20}]
        + [richer]
        + [{"Athletics": 20}] * 3
        + [{"Athletics": 10}],
        exits={"tdp": 15},
    )
    fake.answers = {
        "info": [INFO_TEXT.replace("347", "5")] * 2
        + [INFO_TEXT.replace("347", "40")] * 4
    }
    fake.state.tdps = 5
    run(clock, fake, plan(tdp=["auto"]))
    assert fake.started[:1] == [("tdp", ["train", "strength", "+1"])]
    assert fake.sent.count("info") >= 2


def test_a_task_whose_script_ended_among_hostiles_gets_away_first(clock):
    # #285: the invasion of 2026-09-22 — the trainer stopped on hostiles
    # and left the character among them; ;train flees before the next task.
    def ambushed(fake):
        fake.state.experience = {
            "Small Edged": {"rank": 1, "percent": 0, "mindstate": 3}
        }
        fake.state.hostiles = {"92557788": True}
        fake.state.compass = ["nw"]

    fake = Fake(
        [{"Small Edged": 3}, ambushed, {"Small Edged": 3}, {"Small Edged": 3}],
        exits={"hunt": 20},
    )
    original_put = fake.put

    def put(command):
        original_put(command)
        if command == "nw":
            fake.state.hostiles = {}

    fake.put = put
    run(clock, fake, plan(tasks=[plan()["tasks"][1]], poll=10))
    assert any("ended among hostiles — getting away" in text for text in fake.echoed)
    assert fake.sent[:3] == ["retreat", "retreat", "nw"]
    assert any("ended among hostiles — got away" in text for text in fake.echoed)


HEAL = {
    "name": "heal",
    "helper": "Riphik",
    "helper_script": "empath",
    "helper_args": ["cecil"],
    "helper_room": "7890",
    "when": "wounded",
}


class HelperWorld:
    """The helper's session as ;train sees it: the scripts it runs, poll
    by poll (the last repeating), and every line sent to it."""

    def __init__(self, polls):
        self.polls = list(polls)
        self.sent = []

    def __call__(self, s, db=None):
        return self  # stands in for the HelperIO class

    def scripts_of(self, port):
        return self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]

    def send(self, port, line):
        self.sent.append(line.split("\t", 1)[-1])

    def sleep(self, seconds):
        pass


def test_a_helper_task_lasts_while_the_helpers_script_runs(clock, monkeypatch):
    # The operator, 2026-09-27: Riphik called in to heal Cecil the way
    # Fallanor is called in to teach. No script or commands of the
    # student's own: the task lasts while ;empath runs, then Riphik's
    # session logs out, with no ;empath return to start it again.
    from client.game import helper

    world = HelperWorld([["empath"], ["empath"], []])
    monkeypatch.setattr(train, "HelperIO", world)
    monkeypatch.setattr(
        train,
        "start_helper",
        lambda s, task, db, walk: helper.Helper("Riphik", 4260, True),
    )
    fake = Fake()
    fake.state.injuries = {"chest": ("wound", 2)}
    clock["fake"] = fake
    task = normalize({"tasks": [HEAL]})["tasks"][0]
    reason = train.run_task(fake, plan(poll=10), task, db=MAP, walk=walk)
    assert reason == "helper done"
    assert world.sent == [";logout"]
    assert any("heal its helper's script ended" in text for text in fake.echoed)


def test_a_task_only_when_wounded_is_skipped_while_the_panel_is_clean(
    clock, monkeypatch
):
    called = []
    monkeypatch.setattr(
        train, "start_helper", lambda *args: called.append(args) or None
    )
    fake = Fake()
    fake.state.injuries = {}
    clock["fake"] = fake
    task = normalize({"tasks": [HEAL]})["tasks"][0]
    assert train.run_task(fake, plan(), task, db=MAP, walk=walk) == "unneeded"
    assert called == []
    assert "train: heal — not wounded, skipped" in fake.echoed


# --- the vela'tohr plant in the rests (#443) --------------------------------
# The wiki's patient line (Elanthipedia: Embrace of the Vela'tohr).
PLANT_TOUCHED = (
    "You reach out to touch an ethereal vela'tohr plant and it extends a green "
    "branch, soft leaves curling against your flesh with a cool tingle.  You feel "
    "an empathic connection forming between you and the vela'tohr plant."
)
RESTED = [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20}, {"Athletics": 10}]


def test_a_wounded_rest_touches_the_plant_and_stays_beside_it(clock):
    # Riphik's plant in the Paladins' Guild Chambers (2026-10-03), the
    # operator: "make cecil touch the plant when he rests".
    fake = Fake(RESTED)
    fake.state.injuries = {"chest": ("wound", 2)}
    fake.state.room_objs = "You also see an ethereal vela'tohr plant and a waste bin."
    fake.answers = {"touch plant": [PLANT_TOUCHED]}
    run(clock, fake, plan(safe_rooms=["home"], plant_room="bank"))
    assert fake.walks[:2] == [{1}, {2}]  # the rest's room, then the plant's
    assert fake.sent.count("touch plant") == 1
    assert any("resting beside it while it heals" in text for text in fake.echoed)


def test_no_plant_in_its_room_walks_back_and_rests_as_usual(clock):
    fake = Fake(RESTED)
    fake.state.injuries = {"chest": ("wound", 2)}
    fake.state.room_objs = "You also see a waste bin."  # Riphik logged out
    run(clock, fake, plan(safe_rooms=["home"], plant_room="bank"))
    assert fake.walks[:3] == [{1}, {2}, {1}]
    assert "touch plant" not in fake.sent
    assert "train: no vela'tohr plant at bank — resting as usual" in fake.echoed


def test_an_unhurt_rest_never_goes_to_the_plant(clock):
    fake = Fake(RESTED)
    fake.state.injuries = {}
    fake.state.room_objs = "You also see an ethereal vela'tohr plant."
    run(clock, fake, plan(safe_rooms=["home"], plant_room="bank"))
    assert fake.walks == [{1}]
    assert "touch plant" not in fake.sent


def test_a_helper_alone_is_a_valid_task():
    # 2026-09-27: the heal task (Riphik's ;empath) was refused as naming
    # "no script and no commands" before it ever ran.
    from client.game.training import validate

    assert validate(normalize(DEFAULTS | {"tasks": [HEAL]})) == []
    assert validate(normalize(DEFAULTS | {"tasks": [{"name": "neither"}]})) == [
        "task neither: names no script, commands or helper"
    ]


def test_a_helper_told_to_stay_is_not_logged_out(clock, monkeypatch):
    # The operator, 2026-09-27: keep Riphik logged in between heals.
    from client.game import helper

    world = HelperWorld([["empath"], []])
    monkeypatch.setattr(train, "HelperIO", world)
    monkeypatch.setattr(
        train,
        "start_helper",
        lambda s, task, db, walk: helper.Helper("Riphik", 4260, True),
    )
    fake = Fake()
    fake.state.injuries = {"chest": ("wound", 2)}
    clock["fake"] = fake
    task = normalize({"tasks": [HEAL | {"helper_after": "stay"}]})["tasks"][0]
    assert train.run_task(fake, plan(poll=10), task, db=MAP, walk=walk) == "helper done"
    assert world.sent == []
    assert "train: Riphik stays logged in" in fake.echoed


def test_a_task_whose_skills_drain_first_trains_again_during_the_rest(clock):
    # The operator, 2026-09-27: Cecil's rest waited ~107 minutes on
    # Attunement and Outdoorsmanship while eight skills sat empty. A task
    # whose own skills have all drained trains again, then the rest goes on.
    fake = run(
        clock,
        Fake(
            [
                {"Athletics": 30, "Small Edged": 30},  # both at target: rest
                {"Athletics": 5, "Small Edged": 25},  # climbs drained first
                {"Athletics": 30, "Small Edged": 20},  # climbs trained again
                {"Athletics": 8, "Small Edged": 8},  # the whole pool drained
            ]
        ),
        plan(top_up="on", safe_rooms=["home"]),
    )
    assert fake.started == [("athletics", [])]
    assert "train: drained — climbs before the rest goes on" in fake.echoed
    assert "train: back to the rest" in fake.echoed
    assert fake.walks == [{1}, {1}]  # to the rest, and back to it after
    assert fake.echoed[-2:] == [
        "train: rested — the pool has drained",
        "train: 1 cycle(s) done",
    ]


def test_the_drained_task_brings_the_when_tasks_before_it():
    from client.game.training import top_up_tasks

    tasks = [
        {"name": "climbs", "script": "athletics", "skills": ["Athletics"]},
        HEAL,
        {"name": "hunt", "script": "hunt", "skills": ["Small Edged", "Brawling"]},
        {"name": "skins", "script": "skins", "skills": []},
    ]
    current = normalize(DEFAULTS | {"tasks": tasks, "top_up": "on"})

    def exp(**states):
        return {
            skill.replace("_", " "): {"rank": 1, "percent": 0, "mindstate": state}
            for skill, state in states.items()
        }

    ready = top_up_tasks(current, exp(Athletics=20, Small_Edged=3, Brawling=0))
    assert [task["name"] for task in ready] == ["heal", "hunt"]
    # One skill still above rest_until keeps the task resting.
    assert top_up_tasks(current, exp(Athletics=20, Small_Edged=3, Brawling=12)) == []
    # A task at its target is not topped up; off turns it all off.
    assert top_up_tasks(current, exp(Athletics=31, Small_Edged=31, Brawling=31)) == []
    off = normalize(DEFAULTS | {"tasks": tasks, "top_up": "off"})
    assert top_up_tasks(off, exp(Athletics=0, Small_Edged=0, Brawling=0)) == []


def test_a_task_tops_up_once_a_rest_even_if_its_skill_never_moves(clock):
    # 2026-09-27: ;boxes with no box to open left Locksmithing at 0/34,
    # "drained" at every look, and the rest ran it again every poll.
    fake = run(
        clock,
        Fake(
            [
                {"Athletics": 30, "Small Edged": 30},
                {"Athletics": 0, "Small Edged": 25},  # climbs drained
                {"Athletics": 0, "Small Edged": 20},  # and it earned nothing
                {"Athletics": 0, "Small Edged": 15},
                {"Athletics": 0, "Small Edged": 8},  # the whole pool drained
            ],
            exits={"athletics": 0},  # it ends at once each time
        ),
        plan(top_up="on"),
    )
    assert fake.started.count(("athletics", [])) == 1
    assert fake.echoed[-2:] == [
        "train: rested — the pool has drained",
        "train: 1 cycle(s) done",
    ]


def test_a_staying_healer_is_not_waited_on_once_the_student_is_clean(
    clock, monkeypatch
):
    # 2026-09-27: Riphik healed Cecil in ninety seconds, then himself for
    # eight minutes while Cecil stood by. With helper_after "stay" the
    # task ends when the panel is clean; ;empath runs on, never told
    # return.
    from client.game import helper

    world = HelperWorld([["empath"]])  # still healing himself

    def heal(s):
        s.state.injuries = {}  # Riphik has taken everything

    monkeypatch.setattr(train, "HelperIO", world)
    monkeypatch.setattr(
        train,
        "start_helper",
        lambda s, task, db, walk: helper.Helper("Riphik", 4260, True),
    )
    fake = Fake([lambda s: None, heal])  # hurt at the start, clean a poll on
    fake.state.injuries = {"chest": ("wound", 2)}
    clock["fake"] = fake
    task = normalize({"tasks": [HEAL | {"helper_after": "stay"}]})["tasks"][0]
    assert train.run_task(fake, plan(poll=10), task, db=MAP, walk=walk) == "healed"
    assert world.sent == []  # no ;empath return, no ;logout


def test_a_healer_told_after_logs_out_once_his_own_heal_is_done(clock, monkeypatch):
    # The operator, 2026-09-28: Riphik logged out once Cecil is healed
    # and Riphik has healed himself. The task ends when Cecil is clean,
    # as with "stay"; Riphik lingers until ;empath ends, then ;logout.
    from client.game import helper

    world = HelperWorld([["empath"]])  # still healing himself

    def heal(s):
        s.state.injuries = {}

    monkeypatch.setattr(train, "HelperIO", world)
    monkeypatch.setattr(train, "LINGERING", {})
    monkeypatch.setattr(
        train,
        "start_helper",
        lambda s, task, db, walk: helper.Helper("Riphik", 4260, True),
    )
    fake = Fake([lambda s: None, heal])
    fake.state.injuries = {"chest": ("wound", 2)}
    clock["fake"] = fake
    task = normalize({"tasks": [HEAL | {"helper_after": "after"}]})["tasks"][0]
    assert train.run_task(fake, plan(poll=10), task, db=MAP, walk=walk) == "healed"
    assert world.sent == []  # no ;empath return, not yet out
    assert "train: Riphik logs out once ;empath is done" in fake.echoed
    assert "riphik" in train.LINGERING

    world.polls = [["empath"]]
    train.settle_helpers(fake)
    assert world.sent == []  # still healing himself
    world.polls = [[]]
    train.settle_helpers(fake)
    assert world.sent == [";logout"]  # his ;empath has ended: out
    assert train.LINGERING == {}


def test_a_lingering_healer_wanted_again_is_not_logged_out(monkeypatch):
    from client.game import helper

    monkeypatch.setattr(
        train, "LINGERING", {"riphik": (helper.Helper("Riphik", 4260, True), "empath")}
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        train, "HelperIO", lambda s, db=None: SimpleNamespace(own_port=lambda: None)
    )
    monkeypatch.setattr(train.helper, "ensure", lambda *args, **kwargs: None)
    fake = Fake()
    task = normalize({"tasks": [HEAL | {"helper_after": "after"}]})["tasks"][0]
    train.start_helper(fake, task, None, None)
    assert train.LINGERING == {}


FAVORS = {"name": "favors", "script": "favors", "when": "favors<10", "skills": []}


def test_the_favors_task_runs_below_the_cap_and_is_skipped_at_it(clock):
    # The operator, 2026-09-28: ;train earns favors up to a cap of 10 with
    # ;favors — never LTB points. The exp window's count decides.
    task = normalize({"tasks": [FAVORS]})["tasks"][0]
    fake = Fake()
    fake.state.favors = 10
    clock["fake"] = fake
    assert train.run_task(fake, plan(), task, db=MAP, walk=walk) == "unneeded"
    assert "train: favors — favors 10 (cap 10), skipped" in fake.echoed
    assert fake.started == []
    fake = Fake()
    fake.state.favors = 5
    clock["fake"] = fake
    train.run_task(fake, plan(), task, db=MAP, walk=walk)
    assert fake.started == [("favors", [])]


def test_a_favors_task_waits_for_the_count_to_be_read(clock):
    task = normalize({"tasks": [FAVORS]})["tasks"][0]
    fake = Fake()
    fake.state.favors = None
    clock["fake"] = fake
    assert train.run_task(fake, plan(), task, db=MAP, walk=walk) == "unneeded"
    assert "train: favors — favors not read yet (cap 10), skipped" in fake.echoed


def test_a_when_the_loop_does_not_know_is_a_plan_problem():
    from client.game.training import favors_cap, validate

    assert favors_cap("favors<10") == 10 and favors_cap("favors < 3") == 3
    assert favors_cap("wounded") is None
    good = normalize(DEFAULTS | {"tasks": [FAVORS]})
    assert validate(good) == []
    bad = normalize(DEFAULTS | {"tasks": [FAVORS | {"when": "raining"}]})
    assert validate(bad) == ["task favors: when 'raining' is not wounded or favors<N"]


def test_train_studies_the_profiles_almanac_between_tasks(clock, monkeypatch):
    # The operator, 2026-09-28: the almanac, every ten minutes it allows.
    studied = []
    monkeypatch.setattr(
        train,
        "interlude",
        SimpleNamespace(run_due=lambda s, make_room=True: studied.append(make_room)),
    )
    fake = Fake()
    clock["fake"] = fake
    train.study_almanac(fake, plan())
    assert studied == [True]  # the interludes, a hand made if need be
    fake.state.hostiles = {"1": "a goblin"}
    train.study_almanac(fake, plan())
    assert len(studied) == 1  # never with a hostile about


def test_a_hunt_told_to_return_gets_minutes_to_sell_and_bank(monkeypatch):
    # Every hunt ends with ;skins bank (the operator, 2026-09-28): a plan's
    # hunt task with the old two-minute grace is not killed mid-sale.
    now = [0.0]
    monkeypatch.setattr(train, "clock", lambda: now[0])

    class Handle:
        def __init__(self, busy_until):
            self.busy_until = busy_until
            self.killed = []

        def is_running(self, name):
            return name not in self.killed and now[0] < self.busy_until

        def tell(self, name, word):
            pass

        def echo(self, text):
            pass

        def sleep(self, seconds):
            now[0] += seconds

        def kill(self, name):
            self.killed.append(name)

    hunting = Handle(busy_until=400)
    train.stop_script(
        hunting, {"script": "hunt", "return_word": "return", "return_grace": 120}
    )
    assert hunting.killed == [] and now[0] >= 400
    now[0] = 0.0
    foraging = Handle(busy_until=400)
    train.stop_script(
        foraging, {"script": "forage", "return_word": "return", "return_grace": 120}
    )
    assert foraging.killed == ["forage"]


# --- the rest's cap, the almanac's refills and the logout rest (#412) ---------


def test_an_uncapped_rest_ends_at_the_default_cap(clock):
    # #412 (2026-10-02): a rest online burns the rested bank for nothing
    # new, and one left uncapped ran from 06:15 to 12:49. rest_minutes 0
    # is an hour now.
    fake = Fake([{"Athletics": 30, "Small Edged": 30}] * 3, sleeps=100)
    run(clock, fake, plan(rest_minutes=0, poll=60))
    assert (
        "train: resting until every trained skill is at 10/34 or below (at most 60 min)"
        in fake.echoed
    )
    assert "train: 60 minutes of rest — moving on" in fake.echoed


def test_a_skill_the_almanac_refills_during_the_rest_is_not_waited_for(
    clock, monkeypatch
):
    # #412: the almanac studied Attunement three times during a rest, each
    # time before it had drained, and the rest waited on it for hours
    # while every other trained skill sat empty.
    monkeypatch.setattr(train.almanac, "STUDIED", [])

    def studied(fake):
        train.almanac.STUDIED.append("Athletics")
        fake.state.experience = {
            "Athletics": {"rank": 1, "percent": 0, "mindstate": 32},
            "Small Edged": {"rank": 1, "percent": 0, "mindstate": 15},
        }

    fake = run(
        clock,
        Fake(
            [
                {"Athletics": 30, "Small Edged": 30},
                {"Athletics": 20, "Small Edged": 20},
                studied,
                {"Athletics": 32, "Small Edged": 8},
            ]
        ),
        plan(safe_rooms=["home"]),
    )
    assert (
        "train: the almanac refilled Athletics — the rest will not wait for it"
        in fake.echoed
    )
    assert fake.echoed[-2:] == [
        "train: rested — the pool has drained",
        "train: 1 cycle(s) done",
    ]


def test_a_study_from_before_the_rest_is_still_waited_for(clock, monkeypatch):
    monkeypatch.setattr(train.almanac, "STUDIED", ["Athletics"])
    fake = Fake(
        [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 32, "Small Edged": 8}],
        sleeps=100,
    )
    run(clock, fake, plan(poll=60))
    assert not any("refilled" in text for text in fake.echoed)
    assert "train: 60 minutes of rest — moving on" in fake.echoed


def test_a_logout_rest_logs_out_once_the_top_ups_are_done(clock):
    # #412, the operator (2026-10-02): the rest itself is the loss — the
    # rested bank refills only offline, and the pools drain either way.
    # Each task gets its top-up, then QUIT; ;train resumes at the next login.
    fake = run(
        clock,
        Fake(
            [
                {"Athletics": 30, "Small Edged": 30},  # both at target: rest
                {"Athletics": 5, "Small Edged": 25},  # climbs drained: its top-up
                {"Athletics": 30, "Small Edged": 20},  # climbs trained again
                {"Athletics": 28, "Small Edged": 5},  # rats drained: its top-up
                {"Athletics": 25, "Small Edged": 30},  # rats trained again
            ]
        ),
        plan(rest_mode="logout", top_up="on", safe_rooms=["home"]),
    )
    assert fake.started == [("athletics", []), ("hunt", [])]
    assert fake.walks == [{1}, {1}, {1}]  # the rest, and back to it after each top-up
    assert fake.sent[-1] == "quit"
    assert fake.echoed[-1] == (
        "train: the top-ups are done — logging out for the rest (QUIT); "
        "start me again at the next login"
    )


def test_a_logout_rest_with_no_top_ups_logs_out_at_once(clock):
    fake = run(
        clock,
        Fake(
            [{"Athletics": 30, "Small Edged": 30}, {"Athletics": 20, "Small Edged": 20}]
        ),
        plan(rest_mode="logout", safe_rooms=["home"], rest_commands=["sit"]),
    )
    assert fake.walks == [{1}]
    assert fake.sent == ["sit", "quit"]
    assert any("logging out once the top-ups are done" in text for text in fake.echoed)


def test_a_logout_rest_at_the_cap_logs_out_rather_than_training_on(clock):
    fake = Fake([{"Athletics": 30, "Small Edged": 30}] * 3, sleeps=100)
    run(clock, fake, plan(rest_mode="logout", top_up="on", poll=60))
    assert fake.sent[-1] == "quit"
    assert (
        "train: 60 minutes of rest — logging out for the rest (QUIT); "
        "start me again at the next login"
    ) in fake.echoed


def test_a_logout_rest_leaves_hostiles_before_it_logs_out(clock):
    def rats(fake):
        fake.state.hostiles = {"1": "a rat"}
        fake.state.experience = {
            "Athletics": {"rank": 1, "percent": 0, "mindstate": 30},
            "Small Edged": {"rank": 1, "percent": 0, "mindstate": 30},
        }

    def gone(fake):
        fake.state.hostiles = {}

    fake = run(
        clock, Fake([rats, gone]), plan(rest_mode="logout", safe_rooms=["home", "bank"])
    )
    assert "train: hostiles at the safe room — moving to the next one" in fake.echoed
    assert fake.walks == [{1}, {2}]
    assert fake.sent[-1] == "quit"
