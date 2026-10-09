"""How ;appraise trains — these tests are the manual. It APPRAISEs the
items on you in rotation, quick, drops what the game cannot find, holds
at mind-lock and ends on a typed return, a danger or an empty rotation
(#275)."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.engine.scripting import ScriptStopped
from client.game import trainer

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "appraise_script", REPO / "scripts/appraise.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

MISSING = "What were you referring to?\n"
# The success wording is uncaptured (2026-09-22); the wiki's certainty line.
CERTAIN = "You are certain that the scimitar weighs exactly 52 stones.\n"

POSSESSIONS = [
    {"noun": "scimitar", "depth": 0},
    {"noun": "sack", "depth": 0},
    {"noun": "pouch", "depth": 0},
]


class Fake:
    """A handle whose Appraisal mindstate advances one step per APPRAISE
    answered; a typed "return" arrives after `stop_after` appraisals."""

    def __init__(self, mindstates, stop_after=None, missing=(), possessions=None):
        self.mindstates = list(mindstates)
        self.stop_after = stop_after
        self.missing = set(missing)
        self.appraised = 0
        self.slept = 0
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Appraisal": {
                    "rank": 8,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            }
            if self.mindstates
            else {},
            hostiles={},
            possessions=POSSESSIONS if possessions is None else possessions,
        )

    def ask(self, s, command, *_):
        self.sent.append(command)
        if command.startswith("appraise my "):
            noun = command.split()[2]
            if noun in self.missing:
                return MISSING
            self.appraised += 1
            if self.mindstates:
                self.state.experience["Appraisal"]["mindstate"] = self.mindstates.pop(0)
            return CERTAIN.replace("scimitar", noun)
        if command == "exp appraisal":
            return "Appraisal:   8 11% dabbling  (1/34)\n"
        return ""

    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return None

    def command(self, timeout=None):
        if self.stop_after is not None and self.appraised >= self.stop_after:
            self.stop_after = None
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.slept += seconds
        if self.mindstates:
            self.state.experience["Appraisal"]["mindstate"] = self.mindstates.pop(0)


def run(fake, args=()):
    script.ask = fake.ask  # act.ask, imported by name (#407)
    script.clock = lambda: fake.slept  # the per-item wait runs on the fake's sleeps
    script.run(fake, script.parse_args(list(args)))
    return "\n".join(fake.echoed)


def appraisals(fake):
    return [c for c in fake.sent if c.startswith("appraise ")]


def test_it_appraises_the_inventory_in_rotation_pouch_first_until_mind_lock():
    # One lap, then the ten-minute wait an item needs before it teaches
    # again (#382); the pool locks meanwhile.
    fake = Fake(mindstates=[1, 5, 10, 20, 30, 34])
    out = run(fake, ["once"])
    assert appraisals(fake) == [
        "appraise my pouch quick",
        "appraise my scimitar quick",
        "appraise my sack quick",
    ]
    assert "every item appraised in the last 10 min" in out
    assert (
        "appraise: 3 item(s) in rotation (pouch, scimitar, sack) — Appraisal 1/34"
        in out
    )
    # The answer is quoted as the game wrote it, its case kept (#407).
    assert "appraise: pouch answered 'You are certain that the pouch weighs" in out
    assert out.count("answered") == 1  # the first answer only, for the capture
    assert "Appraisal at 34/34 — done" in out


def test_an_item_the_game_cannot_find_leaves_the_rotation_and_an_empty_one_ends():
    fake = Fake(mindstates=[1] + [5] * 20, missing={"sack"}, stop_after=4)
    out = run(fake)
    assert "appraise my sack quick" in fake.sent
    assert appraisals(fake).count("appraise my sack quick") == 1
    assert "the game finds no sack — out of the rotation (2 left)" in out
    assert "returning as asked" in out

    gone = Fake(mindstates=[1, 5], missing={"pouch", "scimitar", "sack"})
    out = run(gone)
    assert "nothing left to appraise — stopping" in out


def test_the_items_argument_and_careful_replace_the_inventory_and_quick():
    fake = Fake(mindstates=[1, 5, 34])
    run(fake, ["items=shield,zills", "careful", "once"])
    assert appraisals(fake)[:2] == [
        "appraise my shield careful",
        "appraise my zills careful",
    ]


def test_it_holds_at_the_lock_and_appraises_again_once_drained(monkeypatch):
    # Locked at the start; the hold's polls read 34, 30, then 27 — below
    # 28 — and a lap runs; a typed return after two appraisals ends it.
    # The poll is the trainer's (#407), a second here so the sleeps add up.
    monkeypatch.setattr(trainer, "LOCK_POLL", 1)
    fake = Fake(mindstates=[34, 34, 30, 27, 5, 6], stop_after=2)
    out = run(fake, ["until=34"])
    assert "mind-locked (34/34) — holding until it drains" in out
    assert "drained to 27/34 — appraising again" in out
    assert appraisals(fake) == ["appraise my pouch quick", "appraise my scimitar quick"]
    assert fake.slept == 3
    assert "returning as asked" in out


def test_no_appraisal_in_exp_and_nothing_on_you_are_said_and_end():
    fake = Fake(mindstates=[], possessions=[])
    fake.ask = lambda s, command, *_: "" if command == "exp appraisal" else ""
    out = run(fake)
    assert "EXP shows no Appraisal — nothing to train" in out
    assert appraisals(fake) == []

    bare = Fake(mindstates=[1], possessions=[])
    out = run(bare)
    assert "nothing to appraise — items=<noun,noun>" in out


def test_danger_ends_the_run():
    fake = Fake(mindstates=[1, 5, 5, 5])
    fake.state.hostiles = {"1": True}
    out = run(fake)
    assert "hostiles in the room — stopping" in out
    assert appraisals(fake) == []


def test_the_exp_window_without_the_skill_is_asked_and_seeded():
    # The seed never moves (no mindstates), so a typed return ends the
    # run after one appraisal rather than MAX_LAPS ten-minute waits.
    fake = Fake(mindstates=[], stop_after=1)
    fake.state.experience = {}
    run(fake, ["once"])
    assert fake.sent[0] == "exp appraisal"
    assert fake.state.experience["Appraisal"] == {
        "rank": 8,
        "percent": 0,
        "mindstate": 1,
        "rate": "dabbling",
    }


# --- gem pouches in a container, and the per-item wait (#382) -----------------

# Captured 2026-09-28 on Crannach's fuzzy gem pouches (Appraisal 1205).
IN_THERE = "You can't appraise the fuzzy gem pouch in there.\n"
TIED = (
    "The fuzzy gem pouch is a container.\nYou are certain that the fuzzy gem pouch "
    "weighs exactly 51 stones.\nYou sort through the gems and finally decide that "
    "they're worth a total of about 1515348 Kronars.\nRoundtime: 5 seconds.\n"
)
CLOSED = (
    "The fuzzy gem pouch is a container, and can be opened and closed.\nYou'll need "
    "to open the fuzzy gem pouch to examine its contents.\n"
)
EMPTY = "There doesn't appear to be anything in the fuzzy gem pouch.\n"

PACKED = [
    {"noun": "pack", "depth": 0, "exist": "10", "container_exist": None},
    {"noun": "pouch", "depth": 1, "exist": "11", "container_exist": "10"},
    {"noun": "pouch", "depth": 1, "exist": "12", "container_exist": "10"},
    {"noun": "pouch", "depth": 1, "exist": "13", "container_exist": "10"},
    {"noun": "helm", "depth": 0, "exist": "20", "container_exist": None},
]


class Packed(Fake):
    """The pack's pouches: GET #id IN #10 puts one in the right hand,
    PUT #id IN #10 takes it back; each pouch answers as `answers` says."""

    def __init__(self, answers, **kwargs):
        super().__init__(possessions=PACKED, **kwargs)
        self.answers = answers
        self.state.left_hand = None
        self.state.right_hand = None

    def ask(self, s, command, *_):
        self.sent.append(command)
        words = command.split()
        if words[0] == "get":
            self.state.right_hand = {"noun": "pouch", "exist": words[1][1:]}
            return "You get a fuzzy gem pouch from inside your hunting pack.\n"
        if words[0] == "put":
            self.state.right_hand = None
            return "You put your pouch in your hunting pack.\n"
        if words[0] == "appraise":
            exist = words[1][1:]
            if self.stop_after is not None and self.appraised >= self.stop_after:
                self.stopped = True
            self.appraised += 1
            if self.mindstates:
                self.state.experience["Appraisal"]["mindstate"] = self.mindstates.pop(0)
            if exist in self.answers and exist not in (self.state.right_hand or {}).get(
                "exist", ""
            ):
                return IN_THERE
            return self.answers.get(exist, TIED)
        return super().ask(s, command)

    def put(self, command, cleanup=False):
        self.sent.append(command)
        if command.startswith("put "):
            self.state.right_hand = None


def test_pouches_in_a_container_are_got_appraised_in_hand_and_put_back():
    fake = Packed({"12": CLOSED, "13": EMPTY}, mindstates=[1] + [5] * 20 + [34] * 5)
    out = run(fake, ["once"])
    assert fake.sent[:3] == [
        "get #11 in #10",
        "appraise #11 quick",
        "put #11 in #10",
    ]
    assert "get #12 in #10" in fake.sent and "put #12 in #10" in fake.sent
    assert "appraise #20 quick" in fake.sent  # the worn helm, after the pouches
    # The worn pack is appraised too, after the pouches it holds.
    assert "appraise: 5 item(s) in rotation (pouch in the pack x3, pack, helm)" in out
    assert "the pouch in the pack is closed — nothing to appraise in it" in out
    assert "the pouch in the pack is empty — out of the rotation (3 left)" in out
    assert fake.state.right_hand is None  # every pouch back in the pack


def test_no_item_is_appraised_twice_within_the_wait():
    fake = Packed({}, mindstates=[1] + [5] * 1300, stop_after=6)
    run(fake)
    times = {}
    for command in appraisals(fake):
        times.setdefault(command, 0)
        times[command] += 1
    # Two laps of the four items in 1,200 fake seconds, never three.
    assert max(times.values()) <= 2
    assert fake.slept >= 600


def test_a_stop_with_a_pouch_in_hand_puts_it_back():
    class Stopped(Packed):
        def waitrt(self):
            if self.state.right_hand is not None:
                raise ScriptStopped()

    fake = Stopped({}, mindstates=[1, 5, 5])
    with pytest.raises(ScriptStopped):
        run(fake)
    assert fake.sent[-1] == "put #11 in #10"
    assert "the item in hand went back where it came from" in "\n".join(fake.echoed)


def test_a_named_item_inside_a_container_is_said_and_dropped():
    # appraisal_items naming a pouch in the pack: refused where it lies.
    fake = Fake(mindstates=[1, 5, 5, 5], possessions=[], stop_after=1)

    def ask(s, command, *_):
        fake.sent.append(command)
        fake.appraised += 1  # the typed return comes after the first
        return IN_THERE if "second" in command else CERTAIN

    fake.ask = ask
    out = run(fake, ["items=second pouch,shield", "once"])
    assert "the second pouch is inside a container" in out


def test_labels_come_from_the_names_not_the_last_word():
    # "pouch in the hide x37" (2026-09-28): a name's last word is no noun.
    from client.game.appraisal import label_of, targets

    pack = {
        "noun": "hide",
        "depth": 0,
        "exist": "42",
        "name": "a large hunting pack crafted from wyvern hide",
    }
    pouch = {
        "noun": "pouch",
        "depth": 1,
        "exist": "43",
        "container_exist": "42",
        "name": "a fuzzy gem pouch (closed)",
    }
    assert label_of(pack) == "large hunting pack"
    assert [t["label"] for t in targets([pack, pouch])] == [
        "fuzzy gem pouch in the large hunting pack",
        "large hunting pack",
    ]


# --- APPRAISE FOCUS beside the rotation (#383) ---

# The wiki's start and end lines; the CHECK and refusal answers are
# dr-scripts' appraisal.lic patterns, the idle CHECK a guess.
FOCUS_STARTED = (
    "You carefully examine your deobar coffer, focusing beyond any individual "
    "details.  Instead you concentrate your efforts toward honing your knowledge "
    "of locksmithing based on its abstract.\n"
)
FOCUS_EXPLORED = "Your focused insight of locksmithing has been fully explored.\n"
IDLE_CHECK = "You feel ready for any sort of appraisal focus.\n"  # captured 2026-09-29
RUNNING_CHECK = "You are currently focusing on your deobar coffer.\n"
BOOST_CHECK = "You have completed your study of the deobar coffer.\n"


class FocusFake(Fake):
    """A Fake at 1205 Appraisal answering the focus: CHECK answers come
    off `checks` (the last one stays), APPRAISE FOCUS answers
    `focus_answer`, and `events` maps an appraisal's count to a line
    that arrives with its answer."""

    def __init__(
        self,
        *args,
        checks=(IDLE_CHECK,),
        focus_answer=FOCUS_STARTED,
        rank=1205,
        events=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.state.experience["Appraisal"]["rank"] = rank
        self.checks = list(checks)
        self.focus_answer = focus_answer
        self.events = dict(events or {})

    def ask(self, s, command, *_):
        if command == "appraise focus check":
            self.sent.append(command)
            return self.checks.pop(0) if len(self.checks) > 1 else self.checks[0]
        if command.startswith("appraise focus "):
            self.sent.append(command)
            return self.focus_answer
        if command.startswith("get my "):
            self.sent.append(command)
            return "You get a deobar coffer from inside your haversack.\n"
        if command.startswith("stow my "):
            self.sent.append(command)
            return "You put your coffer in your haversack.\n"
        answer = super().ask(s, command)
        if command.startswith("appraise my ") and self.appraised in self.events:
            answer += self.events.pop(self.appraised)
        return answer


FOCUS_START = [
    "appraise focus check",
    "get my coffer",
    "appraise focus my coffer",
    "stow my coffer",
]


def test_a_focus_starts_beside_the_rotation_and_is_checked_while_it_runs():
    fake = FocusFake(
        mindstates=[1, 5, 10, 20, 30, 34], checks=[IDLE_CHECK, RUNNING_CHECK]
    )
    out = run(fake, ["once", "focus=coffer"])
    assert fake.sent[:5] == FOCUS_START + ["appraise my pouch quick"]
    assert "APPRAISE FOCUS on coffer beside the rotation" in out
    assert "APPRAISE FOCUS on the coffer begun" in out
    assert "APPRAISE FOCUS CHECK answered 'You feel ready for any sort" in out
    assert fake.sent.count("appraise focus my coffer") == 1
    assert fake.sent.count("appraise focus check") >= 2  # every FOCUS_POLL
    assert "Appraisal at 34/34 — done" in out


def test_below_200_ranks_the_rotation_runs_alone():
    fake = FocusFake(mindstates=[1, 5, 10, 34], rank=150)
    out = run(fake, ["once", "focus=coffer"])
    assert "APPRAISE FOCUS needs 200 Appraisal ranks, 150 here" in out
    assert not [c for c in fake.sent if c.startswith("appraise focus")]


def test_a_research_project_in_progress_turns_the_focus_off_never_repeated():
    # appraisal.lic sends the focus again on this answer; that would end
    # the research project.
    fake = FocusFake(
        mindstates=[1, 5, 10, 34],
        focus_answer="You will lose your progress on your research if you do that.\n",
    )
    out = run(fake, ["once", "focus=coffer"])
    assert "a magical research project is in progress" in out
    assert "focus off for the run" in out
    assert fake.sent.count("appraise focus my coffer") == 1
    assert fake.sent.count("appraise focus check") == 1
    assert "stow my coffer" in fake.sent  # the item goes back all the same


def test_a_research_portion_running_refuses_the_focus_once_for_the_run():
    # Captured 2026-09-29 beside a RESEARCH AUGMENTATION portion: read
    # as a focus already running, it drew a refusal every two minutes.
    fake = FocusFake(
        mindstates=[1, 5, 10, 34],
        focus_answer="You are already working on a different research project.\n",
    )
    out = run(fake, ["once", "focus=magic"])
    assert "a magical research project is in progress" in out
    assert fake.sent.count("appraise focus magic") == 1
    assert fake.sent.count("appraise focus check") == 1


def test_a_boost_still_running_starts_no_focus():
    fake = FocusFake(mindstates=[1, 5, 10, 34], checks=[BOOST_CHECK])
    run(fake, ["once", "focus=coffer"])
    assert "get my coffer" not in fake.sent
    assert "appraise focus my coffer" not in fake.sent


def test_a_boost_that_runs_out_starts_the_next_focus_at_once():
    fake = FocusFake(mindstates=[1, 5, 10, 34], events={2: FOCUS_EXPLORED})
    out = run(fake, ["once", "focus=coffer"])
    assert "the focus boost has run out — a new focus next" in out
    scimitar = fake.sent.index("appraise my scimitar quick")
    assert fake.sent[scimitar + 1 : scimitar + 6] == FOCUS_START + [
        "appraise my sack quick"
    ]


def test_a_concept_is_focused_with_nothing_fetched():
    fake = FocusFake(mindstates=[1, 5, 10, 34], checks=[IDLE_CHECK, RUNNING_CHECK])
    run(fake, ["once", "focus=offense"])
    assert "appraise focus offense" in fake.sent
    assert not [c for c in fake.sent if c.startswith(("get my", "stow my"))]


def test_an_item_the_game_cannot_find_turns_the_focus_off():
    fake = FocusFake(mindstates=[1, 5, 10, 34])
    fake.ask = lambda s, command, *_, inner=fake.ask: (
        (fake.sent.append(command) or MISSING)
        if command.startswith("get my ")
        else inner(s, command)
    )
    out = run(fake, ["once", "focus=coffer"])
    assert "no coffer to focus on" in out and "focus off for the run" in out
    assert "appraise focus my coffer" not in fake.sent
