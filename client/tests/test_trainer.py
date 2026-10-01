"""client.game.trainer: the loop every skill trainer runs (#407) — the
step until the lock, the hold until the drain, a typed return between
steps, a danger ended with the shared escape, the finish at every end."""

from types import SimpleNamespace

from client.engine.scripting import ScriptStopped
from client.game import flight, trainer

SKILL = "Mechanical Lore"


class Fake:
    """A handle whose mindstates follow a script the steps advance: each
    `sleep` (a pause slice) takes the next value; `commands` are the
    lines typed at the script, read one per command() call."""

    def __init__(self, mindstates=(0,), commands=(), hostiles=None, dead=False):
        self.mindstates = list(mindstates)
        self.commands = list(commands)
        self.dead = dead
        self.echoed, self.sent = [], []
        self.state = SimpleNamespace(
            experience={
                SKILL: {
                    "rank": 10,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                    "rate": "clear",
                }
            },
            hostiles=dict(hostiles or {}),
            room_uid=1,
            room_title="[Field]",
            compass=["north"],
        )

    def set_mindstate(self, value):
        self.state.experience[SKILL]["mindstate"] = value

    def sleep(self, seconds):
        if self.mindstates:
            self.set_mindstate(self.mindstates.pop(0))

    def command(self, timeout=None):
        return self.commands.pop(0) if self.commands else None

    def echo(self, text):
        self.echoed.append(text)

    def put(self, command, cleanup=False):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return None

    def waitrt(self):
        pass


def test_the_step_runs_until_it_returns_a_reason_and_finish_sees_it():
    s = Fake()
    steps = []
    ends = []

    def step(handle):
        steps.append(1)
        return "out of grass" if len(steps) == 3 else None

    why = trainer.train(s, "mech", SKILL, step, finish=lambda h, w: ends.append(w))
    assert why == "out of grass" and len(steps) == 3
    assert s.echoed[-1] == "mech: out of grass — stopping"
    assert ends == ["out of grass"]


def test_a_typed_return_ends_between_steps():
    s = Fake(commands=["return"])
    steps = []
    why = trainer.train(s, "mech", SKILL, lambda h: steps.append(1))
    assert why == "return" and steps == []
    assert s.echoed == ["mech: returning as asked"]


def test_a_death_and_hostiles_end_the_loop_hostiles_with_the_escape(monkeypatch):
    dead = Fake(dead=True)
    assert trainer.train(dead, "mech", SKILL, lambda h: None) == "you are dead"
    assert dead.echoed == ["mech: you are dead — stopping"]
    fled = []
    monkeypatch.setattr(flight, "react", lambda s, prefix, **k: fled.append(prefix))
    beset = Fake(hostiles={"1": "a goblin"})
    assert trainer.train(beset, "mech", SKILL, lambda h: None) == "hostiles in the room"
    assert fled == ["mech"]


def test_a_lock_with_once_ends_done_and_without_it_holds_until_the_drain():
    once = Fake(mindstates=[34])
    assert trainer.train(once, "mech", SKILL, lambda h: None, once=True) == "locked"
    assert once.echoed[-1] == "mech: Mechanical Lore at 34/34 — done"
    # Locked at the start, three polls to drain under 28, one step
    # runs, then the step ends it.
    held = Fake(mindstates=[34, 33, 30, 27])
    steps = []

    def step(handle):
        steps.append(trainer.mindstates(handle, SKILL)[SKILL])
        return "done for the test"

    why = trainer.train(held, "mech", SKILL, step, again="braiding again")
    assert why == "done for the test" and steps == [27]
    assert held.echoed[:2] == [
        "mech: Mechanical Lore mind-locked (34/34) — holding until it drains",
        "mech: drained to 27/34 — braiding again",
    ]


def test_a_return_typed_during_the_hold_ends_it_as_a_return():
    # pause() reads the word, so nothing is left for the loop's own
    # check: the interrupted hold without a danger is the return.
    s = Fake(mindstates=[34, 34], commands=["return"])
    assert trainer.train(s, "mech", SKILL, lambda h: None) == "return"
    assert s.echoed[-1] == "mech: returning as asked"


def test_no_skill_in_exp_ends_before_a_step():
    s = Fake()
    s.state.experience = {}
    steps = []
    why = trainer.train(
        s, "mech", SKILL, lambda h: steps.append(1), ask=lambda h, c: ""
    )
    assert why == "no skill" and steps == []
    assert s.echoed == ["mech: EXP shows no Mechanical Lore — nothing to train"]


def test_finish_runs_on_a_stop_too():
    s = Fake()
    ends = []

    def step(handle):
        raise ScriptStopped()

    try:
        trainer.train(s, "mech", SKILL, step, finish=lambda h, w: ends.append(w))
    except ScriptStopped:
        pass
    assert ends == [None]


def test_several_skills_lock_together_and_drain_on_any_one():
    s = Fake(mindstates=[34])
    s.state.experience["Attunement"] = {
        "rank": 5,
        "percent": 0,
        "mindstate": 34,
        "rate": "clear",
    }
    s.state.experience["Unknown Skill"] = {}  # not listed: ignored
    skills = [SKILL, "Attunement"]
    assert trainer.locked(s, skills)
    s.state.experience["Attunement"]["mindstate"] = 20
    assert not trainer.locked(s, skills)
    assert trainer.drained(s, skills, 27) == ("Attunement", 20)
    assert trainer.drained(s, skills, 10) is None


def test_hold_at_lock_names_every_skill_and_the_one_that_drained():
    s = Fake(mindstates=[34, 34, 34])
    s.state.experience["Attunement"] = {
        "rank": 5,
        "percent": 0,
        "mindstate": 34,
        "rate": "clear",
    }
    ticks = []

    def tick():
        ticks.append(1)
        if len(ticks) == 2:
            s.state.experience["Attunement"]["mindstate"] = 20

    assert trainer.hold_at_lock(
        s, "cast", [SKILL, "Attunement"], again="casting again", tick=tick
    )
    assert s.echoed == [
        "cast: Mechanical Lore, Attunement mind-locked (34/34) — holding until one drains",
        "cast: Attunement drained to 20/34 — casting again",
    ]


def test_hold_at_lock_is_false_when_interrupted():
    s = Fake(mindstates=[34, 34], commands=["return"])
    assert trainer.hold_at_lock(s, "mech", SKILL) is False


def test_a_callable_skill_set_is_read_afresh_every_round():
    # ;cast's watched skills shrink when POWER is dropped for the run: a
    # frozen list would wait on a skill nothing trains any more.
    s = Fake(mindstates=[34])
    s.state.experience["Attunement"] = {
        "rank": 5,
        "percent": 0,
        "mindstate": 10,
        "rate": "clear",
    }
    watched = [SKILL, "Attunement"]
    rounds = []

    def step(handle):
        rounds.append(1)
        if len(rounds) == 1:
            watched.remove("Attunement")  # POWER off: Attunement leaves the set
            return None
        return "spent"

    why = trainer.train(s, "cast", lambda: list(watched), step, once=True)
    # Round one: not locked (Attunement at 10); round two: the set is
    # the one skill at 34 — locked, done.
    assert why == "locked" and len(rounds) == 1


def test_ensure_false_trains_a_skill_the_window_does_not_list():
    s = Fake()
    s.state.experience = {}
    steps = []
    why = trainer.train(
        s, "research", "Warding", lambda h: steps.append(1) or "done", ensure=False
    )
    assert why == "done" and steps == [1]
