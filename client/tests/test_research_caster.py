"""How ;research trains a caster's magic skills — these tests are the
manual. With Gauge Flow up, RESEARCH <project> <seconds> runs a portion
in the game; the portions add up to the project, and its breakthrough
locks the project's skill. The loop casts Gauge Flow at DISCERN's mana
when it is down, finishes a project in progress first, picks the
emptiest skill's project next, and ends on a typed return, a danger,
or an answer its tables lack (client/game/research.py,
scripts/research.py). The start, the portion's end, the idle status
and DISCERN's estimate were captured on a Moon Mage (2026-09-29); the
lost portion is Elanthipedia's and dr-scripts' crossing-training.lic's
until captured."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import buffs, research

REPO = pathlib.Path(__file__).parents[2]

# Captured 2026-09-29, RESEARCH AUGMENTATION 300 under a 98-mana Gauge
# Flow; the pulses between ("Noting that your research is progressing
# nicely, you continue to focus on it.") end nothing.
STARTED = (
    "You confidently begin to bend the mana streams around and through you, "
    "testing the limits of your ability to weave augmentation spells into the "
    "flesh.\n"
)
PORTION = (
    "You make definite progress in your project about Augmentation Patterns "
    "Research and decide to take a break.  However, there is still more to learn "
    "before you arrive at a breakthrough.\n"
)
# The next portion's start, when less than its seconds are left.
SHORTENED = (
    "You realize that your project about Augmentation Patterns Research only "
    "requires 182 more seconds of research, so you adjust your plans accordingly.\n"
)
BREAKTHROUGH = (
    "Breakthrough!  The mana streams dance in front of your magical senses and, at "
    "least in their present configuration, you understand the nature of their warp "
    "and weave.\n"
)
LOST = "Distracted by your spellcasting, you forget what you were researching.\n"
IDLE = "You're not researching anything!\n"  # captured 2026-09-29
DISCERN = (  # captured 2026-09-29: the spell's own cap
    "The spell requires at minimum 5 mana streams and you think you can reinforce "
    "it with 95 more, for a total of 100 streams.\n"
)
ENDS = {"portion": PORTION, "breakthrough": BREAKTHROUGH, "lost": LOST}


def _script():
    spec = importlib.util.spec_from_file_location(
        "research_caster_script", REPO / "scripts/research.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()


# --- the model ---


def test_the_start_answers_classify():
    assert research.start_outcome(STARTED) == "started"
    assert research.start_outcome("You start to research harness symbiosis.") == (
        "started"
    )
    assert research.start_outcome("You are already busy at research.") == "busy"
    assert research.start_outcome("You cannot begin a new project now.") == "blocked"
    assert research.start_outcome("You do not know how to research that.") == (
        "unknown"
    )
    assert research.start_outcome("Usage: RESEARCH <project> <seconds>") == "unknown"
    assert research.start_outcome("What?") is None


def test_a_portion_ends_in_progress_a_breakthrough_or_a_loss():
    assert research.portion_end(PORTION) == "portion"
    assert research.portion_end(BREAKTHROUGH) == "breakthrough"
    assert research.portion_end(LOST) == "lost"
    assert research.portion_end("You continue to flex the mana streams.") is None
    pulse = (
        "Noting that your research is progressing nicely, you continue to focus on it."
    )
    assert research.portion_end(pulse) is None


def test_a_shortened_portion_is_a_start_not_an_end():
    # The last portion of a project says how much is left, then starts.
    assert research.start_outcome(SHORTENED + STARTED) == "started"
    assert research.portion_end(SHORTENED) is None


def test_research_status_names_the_project_in_progress():
    assert research.research_status(IDLE) == (None, None)
    # Captured 2026-09-29, mid-portion.
    assert research.research_status(
        "You believe that you're 36% complete with a portion of research about "
        "Mana Stream Theory.  You estimate that you will complete it a few "
        "minutes from now."
    ) == ("stream", 36)
    assert research.research_status(
        "You have completed 40% of a project about Mana Stream Theory."
    ) == ("stream", 40)
    assert research.research_status(
        "You have completed 12% of a project about Warding Patterns Research.\n"
        "You estimate that you will complete it a few minutes from now."
    ) == ("warding", 12)
    assert research.research_status(
        "You have completed 5% of a project about Harness Symbiosis."
    ) == ("other", 5)
    assert research.research_status("") == (None, None)


def test_caster_words_name_projects_by_shorthand_or_skill():
    assert research.parse_caster_args([]) == {
        "projects": ["stream", "augmentation", "utility", "warding"],
        "until": 34,
        "portion": 300,
        "once": False,
    }
    options = research.parse_caster_args(
        ["attunement", "arcana", "aug", "portion=500", "until=30", "once"]
    )
    assert options["projects"] == ["stream", "fundamental", "augmentation"]
    assert options["portion"] == 300  # a portion's most
    assert options["until"] == 30 and options["once"]
    assert research.parse_caster_args(["portion=10"])["portion"] == 30  # its least


def test_only_a_casters_own_words_pick_the_caster_mode_by_themselves():
    assert research.wants_caster(["stream"])
    assert research.wants_caster(["fundamental", "once"])
    assert not research.wants_caster(["augmentation", "warding"])
    assert not research.wants_caster(["warding=buffalo"])


def test_gauge_flow_is_cast_a_step_under_discerns_estimate_never_past_its_cap():
    assert research.gauge_mana((5, 60), 2) == 58
    assert research.gauge_mana((5, 150), 2) == 100  # the spell's cast cap
    assert research.gauge_mana((5, 6), 2) == 0  # no room: the minimum
    assert research.gauge_mana(None, 2) == 0


# --- the loop ---


class Fake:
    """A caster in the game: RESEARCH starts a portion that ends
    `portion` seconds on with the next of `ends` ("portion",
    "breakthrough", "lost"); a breakthrough puts the project's skill at
    34. Gauge Flow casts ok (or the scripted `casts` outcomes). A typed
    "return" arrives once the clock passes `stop_at`."""

    def __init__(
        self,
        start,
        ends=(),
        status=IDLE,
        casts=(),
        stop_at=None,
        answers=None,
        active=None,
    ):
        self.now = 1000.0
        self.ends = list(ends)
        self.status = status
        self.casts = list(casts)
        self.cast_mana = []
        self.stop_at = stop_at
        self.answers = answers or {}
        self.due = None  # (when, line) of the running portion's end
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Sable",
            experience={
                skill: {"rank": 900, "percent": 0, "mindstate": value, "rate": "x"}
                for skill, value in start.items()
            },
            hostiles={},
            active_spells=dict(active or {}),
        )

    def ask(self, s, command, *_):
        self.sent.append(command)
        if command == "research status":
            return self.status
        if command == "discern gauge flow":
            return DISCERN
        if command.startswith("research "):
            _, project, seconds = command.split()
            answer = self.answers.get(project, STARTED)
            if research.start_outcome(answer) in ("started", "busy") and self.ends:
                end = self.ends.pop(0)
                if end == "breakthrough":
                    skill = research.PROJECTS[project]
                    self._after = (skill, 34)
                self.due = (self.now + int(seconds), ENDS[end])
            return answer
        return ""

    _after = None

    def cast_once(self, s, spell, mana, state, ask, report):
        assert spell == "Gauge Flow"
        self.sent.append(f"cast gauge flow {mana}")
        self.cast_mana.append(mana)
        outcome = self.casts.pop(0) if self.casts else "ok"
        if outcome == "ok":
            self.state.active_spells["Gauge Flow"] = 60
        return outcome

    def get(self, timeout=None, streams=("",)):
        if self.due and self.now >= self.due[0]:
            line, self.due = self.due[1], None
            if self._after:
                skill, value = self._after
                self.state.experience[skill]["mindstate"] = value
                self._after = None
            return line
        self.now += timeout or 1
        return None

    def command(self, timeout=None):
        if self.stop_at is not None and self.now >= self.stop_at:
            self.stop_at = None
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.now += seconds


def run(fake, args=()):
    script.probe = SimpleNamespace(ask=fake.ask, STORY_STREAMS=("", "combat"))
    script.buffs = SimpleNamespace(
        cast_once=fake.cast_once,
        mana_limit=buffs.mana_limit,
        MANA_STEP=buffs.MANA_STEP,
        BuffState=buffs.BuffState,
    )
    script.clock = lambda: fake.now
    script.run_caster(fake, research.parse_caster_args(list(args)))
    return "\n".join(fake.echoed)


def portions(fake):
    return [c for c in fake.sent if c.startswith("research ") and "status" not in c]


def test_it_casts_gauge_flow_then_researches_the_emptiest_project_to_its_breakthrough():
    fake = Fake(
        {"Attunement": 2, "Augmentation": 20},
        ends=["portion", "breakthrough", "breakthrough"],
    )
    out = run(fake, ["stream", "augmentation", "once"])
    assert fake.sent[:3] == [
        "research status",
        "discern gauge flow",
        "cast gauge flow 98",
    ]
    assert portions(fake) == [
        "research stream 300",
        "research stream 300",
        "research augmentation 300",
    ]
    assert "STREAM for Attunement (2/34)" in out
    assert "research: STREAM portion done — more to learn" in out
    assert "breakthrough — STREAM done, Attunement 34/34" in out
    assert "Attunement, Augmentation at 34/34 — done" in out
    assert fake.cast_mana == [98]  # still up for the second project


def test_gauge_flow_under_twenty_minutes_is_recast_before_the_portion():
    fake = Fake({"Attunement": 0}, ends=["breakthrough"], active={"Gauge Flow": 12})
    out = run(fake, ["stream", "once"])
    assert fake.cast_mana == [98]
    assert "Gauge Flow cast at 98 mana (12 min left)" in out


def test_gauge_flow_with_time_left_is_not_recast():
    fake = Fake({"Attunement": 0}, ends=["breakthrough"], active={"Gauge Flow": 45})
    run(fake, ["stream", "once"])
    assert fake.cast_mana == []
    assert "discern gauge flow" not in fake.sent


def test_a_gauge_flow_that_fails_at_discerns_mana_is_tried_at_the_minimum():
    fake = Fake({"Attunement": 0}, ends=["breakthrough"], casts=["collapsed", "ok"])
    out = run(fake, ["stream", "once"])
    assert fake.cast_mana == [98, 0]
    assert "Gauge Flow failed at 98 mana — the minimum from here" in out
    assert portions(fake) == ["research stream 300"]


def test_a_gauge_flow_that_will_not_cast_ends_the_run_before_any_research():
    fake = Fake({"Attunement": 0}, casts=["refused"])
    out = run(fake, ["stream"])
    assert "Gauge Flow did not cast (refused) — research needs it; stopping" in out
    assert portions(fake) == []


def test_a_project_in_progress_is_finished_first():
    fake = Fake(
        {"Attunement": 0, "Warding": 20},
        ends=["breakthrough", "breakthrough"],
        status="You have completed 60% of a project about Warding Patterns Research.\n",
    )
    out = run(fake, ["stream", "once"])
    assert "finishing the WARDING project in progress (60%)" in out
    assert portions(fake) == ["research warding 300", "research stream 300"]


def test_a_project_the_script_does_not_run_is_left_alone():
    fake = Fake(
        {"Attunement": 0},
        status="You have completed 5% of a project about Harness Symbiosis.\n",
    )
    out = run(fake, ["stream"])
    assert "a project this script does not run" in out
    assert "RESEARCH CANCEL" in out
    assert portions(fake) == [] and fake.cast_mana == []


def test_a_lost_portion_is_started_again():
    fake = Fake({"Attunement": 0}, ends=["lost", "breakthrough"])
    out = run(fake, ["stream", "once"])
    assert "the portion was lost" in out
    assert portions(fake) == ["research stream 300"] * 2


def test_a_project_the_game_does_not_know_leaves_the_run():
    fake = Fake(
        {"Attunement": 0, "Warding": 10},
        ends=["breakthrough"],
        answers={"stream": "You do not know how to research that.\n"},
    )
    out = run(fake, ["stream", "warding", "once"])
    assert "RESEARCH STREAM answered 'You do not know how to research that.'" in out
    assert portions(fake) == ["research stream 300", "research warding 300"]


def test_an_answer_outside_the_table_is_echoed_and_the_run_ends():
    fake = Fake({"Attunement": 0}, answers={"stream": "The streams ignore you.\n"})
    out = run(fake, ["stream"])
    assert "RESEARCH STREAM answered 'The streams ignore you.' — stopping" in out


def test_a_return_early_in_a_portion_ends_at_once_and_leaves_it_running():
    fake = Fake({"Attunement": 0}, ends=["portion"], stop_at=1100)
    out = run(fake, ["stream"])
    assert "ending — the portion runs on in the game for about" in out
    assert "(a cast, PLAY, STUDY or fight loses it)" in out
    assert portions(fake) == ["research stream 300"]


def test_a_return_late_in_a_portion_finishes_it_first():
    # the portion starts about 1000 and ends 300 s on; the return at 1250
    fake = Fake({"Attunement": 0}, ends=["portion", "portion"], stop_at=1250)
    out = run(fake, ["stream"])
    assert "research: STREAM portion done — more to learn" in out
    assert out.endswith("research: stopping as asked")
    assert portions(fake) == ["research stream 300"]


def test_a_project_whose_skill_is_full_waits_for_the_drain(monkeypatch):
    monkeypatch.setattr(script, "LOCK_POLL", 1)
    fake = Fake(
        {"Attunement": 34, "Warding": 34},
        status="You have completed 60% of a project about Warding Patterns Research.\n",
    )
    out = run(fake, ["stream", "once"])
    assert "Warding at 34/34 — done" in out
    assert portions(fake) == []


def test_danger_ends_the_run_before_any_research(monkeypatch):
    fled = []
    monkeypatch.setattr(script.flight, "react", lambda s, prefix: fled.append(prefix))
    fake = Fake({"Attunement": 0})
    fake.state.hostiles = {"1": True}
    out = run(fake, ["stream"])
    assert "hostiles in the room — stopping" in out
    assert fled == ["research"]
    assert portions(fake) == []


def test_the_guild_picks_the_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(script, "run", lambda s, o: calls.append(("barbarian", o)))
    monkeypatch.setattr(script, "run_caster", lambda s, o: calls.append(("caster", o)))
    handle = SimpleNamespace(args=[], state=SimpleNamespace(name="Sable"))
    for guild, mode in (("Moon Mage", "caster"), ("Barbarian", "barbarian")):
        monkeypatch.setattr(script, "snapshot_guild", lambda name, g=guild: g)
        script.main(handle)
        assert calls[-1][0] == mode
    # A caster's own word needs no guild at all.
    monkeypatch.setattr(script, "snapshot_guild", lambda name: None)
    monkeypatch.setattr(script, "ask", lambda s, c: calls.append(c) or "")
    handle.args = ["stream"]
    script.main(handle)
    assert calls[-1][0] == "caster" and "info" not in calls
    # No snapshot: INFO says (read-only); nothing parseable is a Barbarian's run.
    handle.args = []
    script.main(handle)
    assert "info" in calls and calls[-1][0] == "barbarian"
