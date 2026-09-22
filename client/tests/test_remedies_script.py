"""How ;remedies trains and fills work orders — these tests are the
manual. The weapon sheathed, the page studied, the herb in the mortar,
CRUSH after CRUSH with the water, the second herb and the catalyst put
in as asked, the remedy stowed or bundled with the logbook, the logbook
handed in for the pay; a run ending on the lock, a return, a missing
herb or a recipe the game refuses (#284)."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from test_remedies import (
    CRUSHED,
    FINISHED,
    LOGBOOK_DONE,
    LOGBOOK_OPEN,
    NEED_CATALYST,
    NEED_HERB,
    NEED_WATER,
    NO_INSTRUCTIONS,
    ORDER,
    PAID,
)

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "remedies_script", REPO / "scripts/remedies.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

STUDIED = (
    "You scan the blister cream instructions with a glance and confidently discern "
    "most of the design's minutiae.\nYou now feel ready to begin the crafting "
    "process.\nRoundtime: 8 sec.\n"
)
TOO_HARD = (
    "You peruse the head salve instructions and quickly realize the design is far "
    "beyond your abilities.\nYou now feel ready to begin the crafting process.\n"
    "Roundtime: 12 sec.\n"
)
SHAVINGS = (
    "You vigorously rub the nugget alongside the mortar to scrape some shavings "
    "into the mixture.\n"
)
POURED = "You toss the water into the mortar and mix it in thoroughly.\n"
BUNDLED = "You notate the cream in the logbook then bundle it up for delivery.\n"
MISSING = "What were you referring to?\n"
NOT_HERE = "To whom are you speaking?\n"


class Fake:
    """A handle: each command prefix has a queue of answers (the last
    answer repeats once the queue is dry); the Alchemy mindstate steps
    once per CRUSH answered."""

    def __init__(self, answers, mindstates=(0,), stop_after=None):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.mindstates = list(mindstates)
        self.stop_after = stop_after
        self.crushes = 0
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Alchemy": {
                    "rank": 2,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            },
            hostiles={},
            room_uid=44301,
            left_hand=None,
            right_hand={"noun": "scimitar", "exist": "1", "name": "a steel scimitar"},
        )

    def ask(self, s, command, *_):
        self.sent.append(command)
        if command.startswith("crush "):
            self.crushes += 1
            if self.mindstates:
                self.state.experience["Alchemy"]["mindstate"] = self.mindstates.pop(0)
        if command.startswith("sheathe my scimitar"):
            self.state.right_hand = None
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                if len(queue) > 1:
                    return queue.pop(0)
                return queue[0] if queue else ""
        return ""

    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return None

    def command(self, timeout=None):
        if self.stop_after is not None and self.crushes >= self.stop_after:
            self.stop_after = None
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


@pytest.fixture(autouse=True)
def profile(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path / "profiles"))
    from client.game.profile import DEFAULTS, save_profile

    save_profile(
        "Lanival",
        DEFAULTS
        | {"weapon": "scimitar", "weapon_container": "scabbard", "catalyst": "nugget"},
    )


def run(fake, args=()):
    script.probe = SimpleNamespace(ask=fake.ask)
    script.to_master = lambda s, profile: True  # the walk is the walker's
    script.run(fake, script.parse_args(list(args)))
    return "\n".join(fake.echoed)


def crushes(fake):
    return [c for c in fake.sent if c.startswith("crush ")]


def test_the_head_salve_is_studied_crushed_watered_catalysed_and_stowed():
    fake = Fake(
        {
            "study my book": [TOO_HARD],
            "get my nemoih": ["You get some dried nemoih."],
            "put my nemoih in my mortar": ["You put your nemoih in your iron mortar."],
            "get my water": ["You get some water."],
            "pour my water in my mortar": [POURED],
            "get my nugget": ["You get a tiny coal nugget."],
            "put my nugget in my mortar": [SHAVINGS],
            "crush my nemoih in my mortar with my pestle": [NEED_WATER],
            "crush my salve in my mortar with my pestle": [
                CRUSHED,
                NEED_CATALYST,
                CRUSHED,
                FINISHED,
            ],
        },
        mindstates=[0, 1, 2, 3, 4, 5],
    )
    out = run(fake, ["count=1"])
    assert "sheathe my scimitar in my scabbard" in fake.sent
    assert fake.sent.index("study my book") < fake.sent.index(
        "put my nemoih in my mortar"
    )
    assert (
        "turn my book to chapter 3" in fake.sent
        and "turn my book to page 4" in fake.sent
    )
    assert "beyond the ranks" in out
    assert crushes(fake) == [
        "crush my nemoih in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
    ]
    assert "pour my water in my mortar" in fake.sent
    assert fake.sent.index("stow my nugget") > fake.sent.index(
        "put my nugget in my mortar"
    )
    assert "remedies: head salve finished (1)" in out
    assert "stow my salve" in fake.sent
    assert fake.sent[-1] == "wield my scimitar"
    assert not any(c.startswith("drop") for c in fake.sent)


def test_without_a_catalyst_the_salve_waits_in_the_mortar():
    from client.game.profile import DEFAULTS, save_profile

    save_profile(
        "Lanival", DEFAULTS | {"weapon": "scimitar", "weapon_container": "scabbard"}
    )
    fake = Fake(
        {
            "study my book": [TOO_HARD],
            "crush my nemoih in my mortar with my pestle": [CRUSHED],
            "crush my salve in my mortar with my pestle": [NEED_CATALYST],
        },
        mindstates=[0, 1, 2],
    )
    out = run(fake)
    assert "wants a catalyst and the profile names none" in out
    assert fake.sent[-3:] == ["stow my pestle", "stow my mortar", "wield my scimitar"]


def test_a_spent_study_is_studied_again_and_a_second_refusal_ends_it():
    # 2026-09-22: three crushes of the wrong herb spent the readiness;
    # the right herb was refused until the page was studied again.
    fake = Fake(
        {
            "study my book": [STUDIED],
            "crush my nemoih in my mortar with my pestle": [NO_INSTRUCTIONS, CRUSHED],
            "crush my salve in my mortar with my pestle": [FINISHED],
        },
        mindstates=[0, 1, 2, 3],
    )
    out = run(fake, ["count=1"])
    assert fake.sent.count("study my book") == 2
    assert "head salve finished (1)" in out
    stubborn = Fake(
        {
            "study my book": [STUDIED],
            "crush my nemoih in my mortar with my pestle": [NO_INSTRUCTIONS],
        }
    )
    out = run(stubborn)
    assert stubborn.sent.count("study my book") == 2
    assert "wrong page or herb" in out


def test_a_typed_return_ends_after_the_crush_in_hand_and_the_lock_holds():
    fake = Fake(
        {
            "study my book": [STUDIED],
            "crush my nemoih in my mortar with my pestle": [CRUSHED],
            "crush my salve in my mortar with my pestle": [CRUSHED],
        },
        mindstates=[0, 5, 10, 15],
        stop_after=3,
    )
    out = run(fake)
    assert len(crushes(fake)) == 3
    assert "stopped" in out
    locked = Fake(
        {
            "study my book": [STUDIED],
            "crush my nemoih in my mortar with my pestle": [CRUSHED],
            "crush my salve in my mortar with my pestle": [CRUSHED],
        },
        mindstates=[0, 34],
    )
    out = run(locked, ["once"])
    assert "locked" in out


def test_no_herb_no_book_and_no_alchemy_are_said_and_end():
    fake = Fake({"study my book": [STUDIED], "get my nemoih": [MISSING]})
    out = run(fake)
    assert "no nemoih on you" in out
    bookless = Fake({"get my book": [MISSING]})
    out = run(bookless)
    assert "no remedies book on you" in out
    assert crushes(bookless) == []
    nothing = Fake({})
    nothing.state.experience = {}
    out = run(nothing)
    assert "EXP shows no Alchemy" in out


def test_a_work_order_is_asked_crafted_bundled_and_handed_in():
    # Captured 2026-09-22: two stacks of blister cream, 1146 Kronars.
    fake = Fake(
        {
            "ask lanshado for easy remedies work": [ORDER],
            "study my book": [STUDIED],
            "get my flowers": ["You get some dried red flowers."],
            "put my flowers in my mortar": [
                "You put your flowers in your iron mortar."
            ],
            "get my water": ["You get some water."],
            "pour my water in my mortar": [POURED],
            "get my nemoih": ["You get some dried nemoih."],
            "put my nemoih in my mortar": [SHAVINGS.replace("nugget", "nemoih")],
            "get my nugget": ["You get a tiny coal nugget."],
            "put my nugget in my mortar": [SHAVINGS],
            "crush my flowers in my mortar with my pestle": [NEED_WATER],
            "crush my cream in my mortar with my pestle": [
                NEED_HERB,
                NEED_CATALYST,
                FINISHED,
                NEED_WATER,
                NEED_HERB,
                NEED_CATALYST,
                FINISHED,
            ],
            "bundle my cream with my logbook": [BUNDLED],
            "read my logbook": [LOGBOOK_OPEN, LOGBOOK_DONE],
            "give my logbook to lanshado": [PAID],
        },
        mindstates=[3] + [5] * 20,
    )
    out = run(fake, ["work"])
    assert (
        "order — 2 stack(s) of blister cream, finely-crafted, due in 65 roisaen" in out
    )
    assert (
        "turn my book to chapter 2" in fake.sent
        and "turn my book to page 1" in fake.sent
    )
    assert fake.sent.count("study my book") == 2  # once per stack
    assert fake.sent.count("bundle my cream with my logbook") == 2
    assert "stow my nemoih" in fake.sent  # the second herb's stack goes back
    assert fake.sent.index("stow my mortar") < fake.sent.index(
        "bundle my cream with my logbook"
    )
    assert "cream bundled — 1 more, 33 roisaen" in out
    assert "cream bundled — 0 more, 22 roisaen" in out
    assert "give my logbook to lanshado" in fake.sent
    assert "order 1 paid 1146 Kronars" in out
    assert "1 order(s), 1146 Kronars" in out
    assert fake.sent[-1] == "wield my scimitar"


def test_an_order_the_book_lacks_a_missing_master_and_no_herbs_are_said():
    fake = Fake(
        {
            "ask lanshado for easy remedies work": [
                ORDER.replace("blister cream", "stomach tonic")
            ]
        }
    )
    out = run(fake, ["work"])
    assert "no page for stomach tonic" in out
    gone = Fake({"ask lanshado for easy remedies work": [NOT_HERE]})
    out = run(gone, ["work"])
    assert "lanshado is not here" in out
    bare = Fake(
        {
            "ask lanshado for easy remedies work": [ORDER],
            "study my book": [STUDIED],
            "get my flowers": [MISSING],
        }
    )
    out = run(bare, ["work"])
    assert "out of dried flowers" in out and "Supplies sells the herbs" in out
