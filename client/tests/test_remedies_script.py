"""How ;remedies trains — these tests are the manual. The weapon sheathed,
the page studied, the mortar and pestle in hand, the dried herb in the
mortar, CRUSH after CRUSH with the water poured when asked, the salve
left unfinished when the catalyst is wanted and none is named, and the
run ending on the lock, a return or a missing herb (#284)."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

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
    "You peruse the head salve instructions and quickly realize the design is far "
    "beyond your abilities.\nYou now feel ready to begin the crafting process.\n"
    "Roundtime: 12 sec.\n"
)
CRUSHED = (
    "With short strokes you crush some unfinished nemoih salve with your pestle.  "
    "A poorly-timed sneeze contaminates the mixture!\nRoundtime: 20 sec.\n"
)
NEED_WATER = (
    CRUSHED + "You need another splash of water to continue crafting some unfinished "
    "nemoih salve.  You believe you can just pour or put it inside the mortar and "
    "continue crushing the unfinished remedy inside.\n"
)
# Captured 2026-09-22 with a tiny coal nugget from the Forging Society.
NEED_CATALYST = (
    CRUSHED + "You need another catalyst material to continue crafting some "
    "unfinished nemoih salve.  You believe you can just pour or put it inside "
    "the mortar and continue crushing the unfinished remedy inside.\n"
)
SHAVINGS = (
    "You vigorously rub the nugget alongside the mortar to scrape some shavings "
    "into the mixture.\n"
)
FINISHED = (
    "With short strokes you crush some unfinished nemoih salve with your pestle.  "
    "The pestle slips and falls upon the dirty floor!  You hastily pick it back up.\n"
    "Roundtime: 12 sec.\n"
    "Applying the final touches, you complete working on some dirty nemoih salve.\n"
)
POURED = "You toss the water into the mortar and mix it in thoroughly.\n"
MISSING = "What were you referring to?\n"


class Fake:
    """A handle: each command prefix has a queue of answers; the Alchemy
    mindstate steps once per CRUSH answered."""

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
                return queue.pop(0) if queue else ""
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
        DEFAULTS | {"weapon": "scimitar", "weapon_container": "scabbard"},
    )


def run(fake, args=()):
    script.probe = SimpleNamespace(ask=fake.ask)
    script.run(fake, script.parse_args(list(args)))
    return "\n".join(fake.echoed)


def crushes(fake):
    return [c for c in fake.sent if c.startswith("crush ")]


def test_the_study_the_herb_the_water_and_the_stop_at_the_catalyst():
    fake = Fake(
        {
            "get my book": ["You get a book of apprentice remedies instructions."],
            "study my book": [STUDIED],
            "get my mortar": ["You get an iron mortar."],
            "get my pestle": ["You get an iron pestle."] * 4,
            "get my nemoih": ["You get some dried nemoih."],
            "get my water": ["You get some water."],
            "pour my water in my mortar": [POURED],
            "crush my nemoih in my mortar with my pestle": ["Crush what?", NEED_WATER],
            "crush my salve in my mortar with my pestle": [CRUSHED, NEED_CATALYST],
        },
        mindstates=[0, 1, 1, 2, 3],
    )
    out = run(fake)
    # the weapon sheathed, the page studied and the book put away
    assert fake.sent[:2] == ["exp alchemy", "sheathe my scimitar in my scabbard"][
        0:2
    ] or ("sheathe my scimitar in my scabbard" in fake.sent)
    assert "turn my book to chapter 3" in fake.sent
    assert "turn my book to page 4" in fake.sent
    assert fake.sent.index("study my book") < fake.sent.index("stow my book")
    assert "beyond the ranks" in out
    # nothing in the mortar: the first crush is answered "Crush what?",
    # the herb goes in, and the second crush starts the salve
    first_crushes = [
        i
        for i, c in enumerate(fake.sent)
        if c == "crush my nemoih in my mortar with my pestle"
    ]
    assert (
        first_crushes[0]
        < fake.sent.index("put my nemoih in my mortar")
        < first_crushes[1]
    )
    assert "pour my water in my mortar" in fake.sent
    assert crushes(fake) == [
        "crush my nemoih in my mortar with my pestle",
        "crush my nemoih in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
    ]
    assert "wants a catalyst and the profile names none" in out
    # the tools stowed and the weapon back, nothing dropped
    assert fake.sent[-3:] == [
        "stow my pestle",
        "stow my mortar",
        "wield my scimitar",
    ]
    assert not any(c.startswith("drop") for c in fake.sent)


def test_a_finished_salve_is_stowed_counted_and_the_next_started(monkeypatch):
    fake = Fake(
        {
            "study my book": [STUDIED],
            "get my pestle": [""] * 6,
            "crush my nemoih in my mortar with my pestle": [CRUSHED],
            "crush my salve in my mortar with my pestle": [FINISHED],
        },
        mindstates=[0, 5, 10],
    )
    out = run(fake, ["count=1"])
    assert "remedies: head salve finished (1)" in out
    assert "stow my salve" in fake.sent
    assert "1 salve(s) made" in out


def test_the_profiles_catalyst_goes_in_when_asked_and_is_stowed_after():
    from client.game.profile import DEFAULTS, save_profile

    save_profile(
        "Lanival",
        DEFAULTS
        | {"weapon": "scimitar", "weapon_container": "scabbard", "catalyst": "nugget"},
    )
    fake = Fake(
        {
            "study my book": [STUDIED],
            "get my pestle": [""] * 6,
            "get my nugget": ["You get a tiny coal nugget from inside your backpack."],
            "put my nugget in my mortar": [SHAVINGS],
            "crush my nemoih in my mortar with my pestle": [NEED_CATALYST],
            "crush my salve in my mortar with my pestle": [CRUSHED, FINISHED],
        },
        mindstates=[0, 5, 10, 15],
    )
    out = run(fake, ["count=1"])
    assert "put my nugget in my mortar" in fake.sent
    assert fake.sent.index("stow my nugget") > fake.sent.index(
        "put my nugget in my mortar"
    )
    assert "remedies: head salve finished (1)" in out


def test_a_typed_return_ends_after_the_crush_in_hand_and_the_lock_holds():
    fake = Fake(
        {
            "study my book": [STUDIED],
            "get my pestle": [""] * 6,
            "crush my nemoih in my mortar with my pestle": [CRUSHED] * 10,
            "crush my salve in my mortar with my pestle": [CRUSHED] * 10,
        },
        mindstates=[0, 5, 10, 15],
        stop_after=3,
    )
    out = run(fake)
    assert len(crushes(fake)) == 3
    assert "stopping as asked" in out

    locked = Fake(
        {
            "study my book": [STUDIED],
            "get my pestle": [""] * 6,
            "crush my nemoih in my mortar with my pestle": [CRUSHED] * 10,
            "crush my salve in my mortar with my pestle": [CRUSHED] * 10,
        },
        mindstates=[0, 34],
    )
    out = run(locked, ["once"])
    assert "Alchemy at 34/34 — done" in out


def test_no_herb_no_book_and_no_alchemy_are_said_and_end():
    fake = Fake(
        {
            "study my book": [STUDIED],
            "get my pestle": [""] * 4,
            "get my nemoih": [MISSING],
            "crush my nemoih in my mortar with my pestle": ["Crush what?"],
        }
    )
    out = run(fake)
    assert "no nemoih on you" in out and "out of dried nemoih" in out

    bookless = Fake({"get my book": [MISSING]})
    out = run(bookless)
    assert "no remedies book on you" in out
    assert crushes(bookless) == []

    nothing = Fake({})
    nothing.state.experience = {}
    out = run(nothing)
    assert "EXP shows no Alchemy" in out
