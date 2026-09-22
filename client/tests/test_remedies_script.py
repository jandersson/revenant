"""How ;remedies trains and fills work orders — these tests are the
manual. The weapon sheathed, the page studied, the herb in the mortar,
CRUSH after CRUSH with the water, the second herb and the catalyst put
in as asked, the remedy stowed or bundled with the logbook, the logbook
handed in for the pay and the next order asked — the herbs, water and
coal bought as they run out, the logbook's own order resumed; a run
ending on the lock, a return, a shop that quotes something else or a
recipe the game refuses (#284)."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from test_remedies import (
    BOUGHT,
    CRUSHED,
    FINISHED,
    LOGBOOK_DONE,
    LOGBOOK_NONE,
    LOGBOOK_OPEN,
    NEED_CATALYST,
    NEED_HERB,
    NEED_WATER,
    NO_INSTRUCTIONS,
    ORDER,
    PAID,
    QUOTE,
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
QUOTE_WATER = QUOTE.replace(
    "(25 pieces) dried red flowers", "10 splashes of water"
).replace("343", "62")
BOUGHT_WATER = BOUGHT.replace("(25 pieces) dried red flowers", "10 splashes of water")
QUOTE_NUGGET = QUOTE.replace(
    "(25 pieces) dried red flowers", "a tiny coal nugget"
).replace("343", "31")
BOUGHT_NUGGET = BOUGHT.replace("(25 pieces) dried red flowers", "a tiny coal nugget")
INFO_POOR = "Wealth:\n  1 silver Kronars (100 copper Kronars).\n  No Lirums.\nDebt:\n  No debt.\n"


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
        self.walked, self.withdrawn = [], []
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
    script.to_master = lambda s, profile: True  # the walks are the walker's
    script.walk_to = lambda s, target, describe: fake.walked.append(str(target)) or True
    script.withdraw_coins = lambda s, copper: fake.withdrawn.append(copper) or True
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
            "read my logbook": [LOGBOOK_NONE, LOGBOOK_OPEN, LOGBOOK_DONE],
            "give my logbook to lanshado": [PAID],
        },
        mindstates=[3] + [5] * 20,
    )
    out = run(fake, ["work", "count=1"])
    assert fake.sent.index("read my logbook") < fake.sent.index(
        "ask lanshado for easy remedies work"
    )  # an order left in the logbook would be resumed instead
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
    assert "order 1 paid 1146 Kronars (1146 clear of 0 spent so far)" in out
    assert "1 order(s), 1146 Kronars earned, 0 spent" in out
    assert fake.sent[-1] == "wield my scimitar"
    assert not fake.walked  # nothing ran out


def work_answers(**extra):
    """The answers of a two-stack blister cream order with everything
    on you, `extra` laid over them."""
    return {
        "ask lanshado for easy remedies work": [ORDER],
        "read my logbook": [LOGBOOK_NONE, LOGBOOK_OPEN, LOGBOOK_DONE],
        "study my book": [STUDIED],
        "get my flowers": ["You get some dried red flowers."],
        "put my flowers in my mortar": ["You put your flowers in your iron mortar."],
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
            NEED_HERB,
            NEED_CATALYST,
            FINISHED,
        ],
        "bundle my cream with my logbook": [BUNDLED],
        "give my logbook to lanshado": [PAID],
    } | extra


def test_the_herbs_water_and_coal_are_bought_as_they_run_out():
    # No red flowers on you, the water gone after the first crush, no
    # nugget: the tools stowed, the coins fetched, the Supplies walked
    # to for two stacks of flowers (one per remedy owed) and the water,
    # the Forging Society's for two nuggets, each quoted then bought and
    # stowed, and the remedy left in the mortar taken up again.
    fake = Fake(
        work_answers(
            info=[INFO_POOR],
            **{
                "get my flowers": [MISSING, "You get some dried red flowers."],
                "get my water": [MISSING, "You get some water."],
                "get my nugget": [MISSING, "You get a tiny coal nugget."],
                "order 13": [QUOTE, BOUGHT, QUOTE, BOUGHT],
                "order 1": [
                    QUOTE_WATER,
                    BOUGHT_WATER,
                    QUOTE_NUGGET,
                    BOUGHT_NUGGET,
                    QUOTE_NUGGET,
                    BOUGHT_NUGGET,
                ],
            },
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert fake.walked == ["8862", "8862", "8775"]
    assert fake.withdrawn == [586]  # 686 for the flowers, 100 in the purse
    assert fake.sent.count("order 13") == 4 and fake.sent.count("order 1") == 6
    assert fake.sent.count("stow my flowers") == 2
    # Two nuggets stowed as bought, one more after the second stack's put.
    assert fake.sent.count("stow my nugget") == 3 and "stow my water" in fake.sent
    assert fake.sent.index("stow my mortar") < fake.sent.index("order 13")
    assert "bought 2 x flowers" in out and "bought 1 x water" in out
    assert "bought 2 x nugget" in out
    # The stack begun goes on after a restock: the flowers go in once
    # per stack, and the page is studied again before the crushes resume.
    assert crushes(fake).count("crush my flowers in my mortar with my pestle") == 2
    assert fake.sent.count("study my book") == 5  # three restocks, two stacks
    assert "order 1 paid 1146 Kronars (336 clear of 810 spent so far)" in out
    assert "1 order(s), 1146 Kronars earned, 810 spent" in out


def test_a_shop_that_quotes_something_else_ends_the_purchase():
    fake = Fake(
        work_answers(
            info=[INFO_POOR],
            **{"get my flowers": [MISSING], "order 13": [QUOTE_WATER]},
        )
    )
    out = run(fake, ["work"])
    assert "ORDER 13 answered" in out and "not flowers" in out
    assert "out of dried flowers — the order waits in the logbook" in out
    assert fake.sent.count("order 13") == 1
    assert "0 order(s), 0 Kronars earned, 0 spent" in out


def test_the_logbooks_open_order_is_resumed_and_a_complete_one_handed_in():
    fake = Fake(
        work_answers(**{"read my logbook": [LOGBOOK_OPEN, LOGBOOK_DONE]}),
        mindstates=[3] + [5] * 20,
    )
    out = run(fake, ["work", "count=1"])
    assert "resuming the logbook's order — 1 more blister cream, 33 roisaen" in out
    assert "ask lanshado for easy remedies work" not in fake.sent
    assert fake.sent.count("bundle my cream with my logbook") == 1
    assert "order 1 paid 1146 Kronars" in out
    done = Fake(work_answers(**{"read my logbook": [LOGBOOK_DONE]}))
    out = run(done, ["work", "count=1"])
    assert "holds a complete order" in out and "order 1 paid 1146 Kronars" in out
    assert not crushes(done)


def test_orders_follow_one_another_until_return_and_the_lock_only_says_so():
    # Eight crushes fill the first order; the typed return after the pay
    # ends the run before a second is asked. Mind-locked from the
    # start, the crushes go on for the pay — said once — unless `once`.
    fake = Fake(work_answers(), mindstates=[34] * 30, stop_after=8)
    out = run(fake, ["work"])
    assert fake.sent.count("ask lanshado for easy remedies work") == 1
    assert "stopping as asked" in out and "1 order(s), 1146 Kronars earned" in out
    assert out.count("mind-locked (34/34) — the order goes on for the pay") == 1
    once = Fake(work_answers(), mindstates=[34] * 30)
    out = run(once, ["work", "once"])
    assert "locked — the order waits in the logbook" in out
    assert not crushes(once)


def test_an_order_the_book_lacks_a_missing_master_and_no_herbs_are_said():
    fake = Fake(
        {
            "ask lanshado for easy remedies work": [
                ORDER.replace("blister cream", "stomach tonic")
            ]
        }
    )
    out = run(fake, ["work"])
    assert "no page for stomach tonic — asking for another order" in out
    assert "no page for stomach tonic — 3 orders asked, stopping" in out
    assert fake.sent.count("ask lanshado for easy remedies work") == 3
    unsold = Fake(
        {
            "ask lanshado for easy remedies work": [
                ORDER.replace("blister cream", "back salve")
            ]
        }
    )
    out = run(unsold, ["work"])
    assert "the Supplies sells no dried hulnik — asking for another order" in out
    gone = Fake({"ask lanshado for easy remedies work": [NOT_HERE]})
    out = run(gone, ["work"])
    assert "lanshado is not here" in out
