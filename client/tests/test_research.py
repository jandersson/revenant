"""How ;research trains a Barbarian's magic skills — these tests are the
manual. MEDITATE RESEARCH <ability> teaches that ability's skill, known
or not, about a minute apart; the loop researches the emptiest of
Augmentation, Warding and Utility, drops a name the game does not know,
holds at mind-lock and ends on a typed return, a danger, or a
non-Barbarian's answer (client/game/research.py, scripts/research.py)."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import research

REPO = pathlib.Path(__file__).parents[2]

# Captured 2026-09-26 on a circle-1 Barbarian; the unknown-name line is
# dr-scripts' combat-trainer.lic's pattern and the non-Barbarian line
# Elanthipedia's, both uncaptured.
BEGUN = (
    "You clear your mind and begin to meditate upon the training you have received.\n"
    "Roundtime: 8 sec.\n"
)
RECALLED = (
    "You recall that Monkey Form is a Basic ability in the Path of the Flame.  "
    "Practicing these movement styles will enhance the Barbarian's balance and "
    "reflex if they possess sufficient augmentation skill.\n"
)
UNKNOWN = "What did you want to research?\n"
NOT_BARBARIAN = "You attempt to meditate, but have trouble concentrating.\n"


def _script():
    spec = importlib.util.spec_from_file_location(
        "research_script", REPO / "scripts/research.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()


# --- the model ---


def test_the_defaults_are_combat_trainers_abilities_for_the_three_skills():
    assert research.DEFAULT_ABILITIES == {
        "Augmentation": "monkey",
        "Warding": "turtle",
        "Utility": "prediction",
    }
    assert research.research_command("Monkey") == "meditate research monkey"


def test_answers_classify_begun_unknown_and_not_a_barbarian():
    assert research.classify(BEGUN) == "begun"
    assert research.classify(BEGUN + RECALLED) == "begun"
    assert research.classify(UNKNOWN) == "unknown"
    assert research.classify(NOT_BARBARIAN) == "not a barbarian"
    assert research.classify("You are too tired to study right now.") is None
    assert research.classify("") is None


def test_no_arguments_research_all_three_skills_a_minute_apart():
    assert research.parse_args([]) == {
        "abilities": dict(research.DEFAULT_ABILITIES),
        "until": 34,
        "gap": 60,
        "once": False,
    }


def test_skill_words_pick_skills_and_skill_equals_ability_picks_the_ability():
    options = research.parse_args(
        ["aug", "Warding=Landslide", "gap=90", "until=30", "once"]
    )
    assert options["abilities"] == {"Augmentation": "monkey", "Warding": "landslide"}
    assert (options["gap"], options["until"], options["once"]) == (90, 30, True)
    assert research.parse_args(["until=50"])["until"] == 34
    assert (
        research.parse_args(["debilitation"])["abilities"] == research.DEFAULT_ABILITIES
    )


def test_the_next_skill_is_the_emptiest_below_the_target():
    assert (
        research.next_skill({"Augmentation": 12, "Warding": 3, "Utility": 7}, 34)
        == "Warding"
    )
    # A skill the window does not list yet is an empty pool.
    assert research.next_skill({"Augmentation": 5, "Utility": None}, 34) == "Utility"
    # With nothing researched yet a tie goes to the first named; one at
    # the target is done.
    assert research.next_skill({"Augmentation": 4, "Warding": 4}, 34) == "Augmentation"
    assert research.next_skill({"Augmentation": 34, "Warding": 30}, 30) is None


def test_a_tie_goes_to_the_skill_researched_longest_ago():
    # The first live run: every pool drained to 0 between researches, and
    # a tie to the first named alternated Augmentation and Warding and
    # never reached Utility.
    empty = {"Augmentation": 0, "Warding": 0, "Utility": 0}
    assert (
        research.next_skill(empty, 34, {"Augmentation": 0, "Warding": 1}) == "Utility"
    )
    assert (
        research.next_skill(empty, 34, {"Augmentation": 3, "Warding": 1, "Utility": 2})
        == "Warding"
    )
    # The emptier pool still goes first, however recently researched.
    assert (
        research.next_skill(
            {"Augmentation": 0, "Warding": 1, "Utility": 1}, 34, {"Augmentation": 5}
        )
        == "Augmentation"
    )


def test_pools_that_drain_between_researches_get_all_three_in_turn():
    fake = Fake({"Augmentation": 0, "Warding": 0, "Utility": 0}, step=0, stop_after=6)
    run(fake)
    assert (
        researches(fake)
        == [
            "meditate research monkey",
            "meditate research turtle",
            "meditate research prediction",
        ]
        * 2
    )


# --- the loop ---


class Fake:
    """A handle whose researched skill gains `step` mindstates per
    research begun; a typed "return" arrives after `stop_after`
    researches. `answers` maps an ability to the game's answer."""

    def __init__(self, start, step=10, stop_after=None, answers=None, drain=()):
        self.step = step
        self.stop_after = stop_after
        self.answers = answers or {}
        self.drain = list(drain)  # mindstates set on each sleep once locked
        self.researched = 0
        self.slept = 0
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.skill_of = {v: k for k, v in research.DEFAULT_ABILITIES.items()}
        self.state = SimpleNamespace(
            name="Uthmor",
            experience={
                skill: {"rank": 2, "percent": 0, "mindstate": value, "rate": "clear"}
                for skill, value in start.items()
            },
            hostiles={},
        )

    def ask(self, s, command, *_):
        self.sent.append(command)
        if command.startswith("meditate research "):
            ability = command.split()[2]
            answer = self.answers.get(ability, BEGUN)
            if research.classify(answer) != "unknown":
                self.researched += 1
                skill = self.skill_of.get(ability)
                entry = self.state.experience.get(skill)
                if entry is not None:
                    entry["mindstate"] = min(34, entry["mindstate"] + self.step)
            return answer
        return ""  # EXP <skill> for a skill the game shows no ranks in

    def command(self, timeout=None):
        if self.stop_after is not None and self.researched >= self.stop_after:
            self.stop_after = None
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.slept += seconds
        if self.drain:
            skill, value = self.drain.pop(0)
            self.state.experience[skill]["mindstate"] = value


def run(fake, args=()):
    script.probe = SimpleNamespace(ask=fake.ask)
    script.clock = lambda: (
        0.0
    )  # every research at the same instant: the whole gap waits
    script.run(fake, script.parse_args(list(args)))
    return "\n".join(fake.echoed)


def researches(fake):
    return [c for c in fake.sent if c.startswith("meditate research ")]


def test_it_researches_the_emptiest_skill_each_round_until_all_lock():
    fake = Fake({"Augmentation": 20, "Warding": 0, "Utility": 10}, step=12)
    out = run(fake, ["once"])
    assert researches(fake)[:3] == [
        "meditate research turtle",  # Warding 0
        "meditate research prediction",  # Utility 10; Warding now 12
        "meditate research turtle",  # Warding 12; Utility 22, Augmentation 20
    ]
    assert (
        "research: Augmentation by monkey, Warding by turtle, Utility by prediction, 60 s apart, until 34/34"
        in out
    )
    assert "Augmentation, Warding, Utility at 34/34 — done" in out
    # The gap is waited between researches, never before the first.
    assert fake.slept == 60 * (len(researches(fake)) - 1)


def test_a_skill_the_game_shows_no_ranks_in_counts_as_empty_and_goes_first():
    fake = Fake({"Augmentation": 5}, stop_after=1)
    fake.skill_of["turtle"] = None  # the window never lists Warding here
    out = run(fake, ["augmentation", "warding"])
    assert "EXP shows no Warding yet — its pool counts as empty" in out
    assert researches(fake) == ["meditate research turtle"]
    assert "stopping as asked" in out


def test_a_name_the_game_does_not_know_drops_its_skill_and_the_rest_go_on():
    fake = Fake(
        {"Augmentation": 30, "Warding": 0},
        answers={"turtle": UNKNOWN},
        stop_after=1,
    )
    out = run(fake, ["augmentation", "warding"])
    assert researches(fake) == ["meditate research turtle", "meditate research monkey"]
    assert (
        "the game knows no ability 'turtle' — Warding is out of the run (warding=<ability> names another)"
        in out
    )

    alone = Fake({"Warding": 0}, answers={"turtle": UNKNOWN})
    out = run(alone, ["warding"])
    assert "nothing left to research — stopping" in out


def test_a_non_barbarian_is_told_and_the_run_ends():
    fake = Fake({"Augmentation": 0}, answers={"monkey": NOT_BARBARIAN})
    out = run(fake, ["augmentation"])
    assert researches(fake) == ["meditate research monkey"]
    assert "only a Barbarian researches this way" in out


def test_an_answer_outside_the_table_is_echoed_for_the_capture_and_the_run_goes_on():
    fake = Fake(
        {"Augmentation": 0},
        answers={"monkey": "You are still recovering from your last session."},
        stop_after=2,
    )
    out = run(fake, ["augmentation"])
    assert (
        "research: monkey answered 'You are still recovering from your last session.'"
        in out
    )
    assert len(researches(fake)) == 2


def test_a_skill_the_window_never_shows_is_read_with_exp_after_its_research():
    # #327: the window pushed nothing for Utility while PREDICTION moved
    # it 0.15 to 0.30 %; the table kept the login seed. EXP UTILITY says
    # it, so the run can see Utility climb and lock.
    fake = Fake({"Augmentation": 34, "Utility": 0}, step=12)
    fake.skill_of["prediction"] = None  # no push for Utility
    readings = iter([5, 17, 34])

    def ask(s, command, *_):
        if command == "exp utility":
            fake.sent.append(command)
            return f"         Utility:      0 30.00% dabbling       ({next(readings)}/34)\n"
        return Fake.ask(fake, s, command)

    fake.ask = ask
    out = run(fake, ["augmentation", "utility", "once"])
    assert researches(fake) == ["meditate research prediction"] * 3
    assert fake.sent.count("exp utility") == 3
    assert fake.state.experience["Utility"]["mindstate"] == 34
    assert out.count("the exp window does not show Utility") == 1
    assert "Augmentation, Utility at 34/34 — done" in out


def test_a_skill_the_window_moves_costs_no_exp():
    fake = Fake({"Augmentation": 0}, step=10, stop_after=2)
    out = run(fake, ["augmentation"])
    assert "exp augmentation" not in fake.sent
    assert "does not show" not in out


def test_a_named_ability_replaces_the_default():
    fake = Fake({"Augmentation": 0}, stop_after=1)
    run(fake, ["augmentation=buffalo"])
    assert researches(fake) == ["meditate research buffalo"]


def test_it_holds_at_the_lock_and_researches_again_once_one_drains(monkeypatch):
    monkeypatch.setattr(script, "LOCK_POLL", 1)
    fake = Fake(
        {"Augmentation": 34, "Warding": 34},
        drain=[("Warding", 31), ("Warding", 27)],
        stop_after=1,
    )
    out = run(fake, ["augmentation", "warding"])
    assert "Augmentation, Warding at 34/34 — holding until one drains" in out
    assert "Warding drained to 27/34 — researching again" in out
    assert researches(fake) == ["meditate research turtle"]
    assert "stopping as asked" in out


def test_danger_ends_the_run_before_any_research(monkeypatch):
    fled = []
    monkeypatch.setattr(script.flight, "react", lambda s, prefix: fled.append(prefix))
    fake = Fake({"Augmentation": 0})
    fake.state.hostiles = {"1": True}
    out = run(fake)
    assert "hostiles in the room — stopping" in out
    assert fled == ["research"]
    assert researches(fake) == []
