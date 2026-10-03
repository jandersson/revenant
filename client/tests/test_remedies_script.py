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
    NEED_ALCOHOL,
    NEED_CATALYST,
    NEED_HERB,
    NEED_WATER,
    NO_INSTRUCTIONS,
    ORDER,
    PAID,
    QUOTE,
)

from client.game.remedies import CATALYST_STOCK

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "remedies_script", REPO / "scripts/remedies.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
find_master = script.find_master  # the real search; run() fakes the module's

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
WEALTH_POOR = "Wealth:\n  1 silver Kronars (100 copper Kronars).\n  No Lirums.\nDebt:\n  No debt.\n"


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
    monkeypatch.setenv("REVENANT_WORKORDERS", str(tmp_path / "workorders"))
    from client.game.profile import DEFAULTS, save_profile

    save_profile(
        "Lanival",
        DEFAULTS
        | {"weapon": "scimitar", "weapon_container": "scabbard", "catalyst": "nugget"},
    )


@pytest.fixture(autouse=True)
def teller(monkeypatch):
    """The purse is read off WEALTH for real (shop.afford, #407); the
    teller's walk and WITHDRAW are the fake's, the shortfall recorded in
    its `withdrawn` — and the map is never loaded (it would download)."""
    from client.game import bank, travel

    monkeypatch.setattr(travel, "mapdb", lambda: SimpleNamespace())
    monkeypatch.setattr(
        bank,
        "withdraw",
        lambda s, db, walk, ask, prefix, copper, currency, retry="try again": (
            s.withdrawn.append(copper) or True
        ),
    )


def run(fake, args=()):
    script.ask = fake.ask
    script.to_master = lambda s, profile: True  # the walks are the walker's
    script.find_master = lambda s, profile, master, **_: True
    script.walk_to = lambda s, target, describe: fake.walked.append(str(target)) or True
    script.run(fake, script.parse_args(list(args)))
    return "\n".join(fake.echoed)


def crushes(fake):
    return [c for c in fake.sent if c.startswith("crush ")]


def ledger_rows():
    from client.game.history import database_path
    from client.game.workorders import open_ledger, rows

    connection = open_ledger(database_path())
    try:
        return rows(connection, character="Lanival", discipline="remedies")
    finally:
        connection.close()


def test_the_head_salve_is_studied_crushed_watered_catalysed_and_stowed():
    fake = Fake(
        {
            "study my book": [TOO_HARD],
            "get my dried nemoih": ["You get some dried nemoih."],
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
    assert "wield my scimitar" not in fake.sent  # it ends sheathed
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
    assert fake.sent[-2:] == ["stow my pestle", "stow my mortar"]


BUSY_MORTAR = (
    "You realize the dried nemoih is not required to continue crafting the "
    "georin salve, so you stop.\n"
)


def test_a_remedy_left_in_the_mortar_is_finished_first_and_the_mortar_freed():
    # 2026-09-23: a run that ended on a missing catalyst left a nemoih
    # salve in the mortar; the next order's flowers were refused and
    # the script spun on "Crush what?" four times a second. Now the
    # remedy in the mortar is finished, taken out and stowed first.
    fake = Fake(
        {
            "study my book": [TOO_HARD],
            "get my dried nemoih": ["You get some dried nemoih."],
            "put my nemoih in my mortar": [
                BUSY_MORTAR,
                "You put your nemoih in your iron mortar.",
            ],
            "get my water": ["You get some water."],
            "pour my water in my mortar": [POURED],
            "crush my nemoih in my mortar with my pestle": [NEED_WATER],
            "crush my salve in my mortar with my pestle": [FINISHED, CRUSHED, FINISHED],
        },
        mindstates=[0, 1, 2, 3, 4, 5],
    )
    out = run(fake, ["count=1"])
    # "georin salve" is what the game calls the neck salve in progress.
    assert "the mortar already holds an unfinished neck salve" in out
    assert "the mortar holds an unfinished neck salve — finishing it first" in out
    assert "the neck salve is done and stowed — the mortar is free" in out
    assert "remedies: head salve finished (1)" in out
    # The neck salve's page (3, 1) studied before its crush, the head
    # salve's (3, 4) before the nemoih went in.
    assert fake.sent.index("turn my book to page 1") < fake.sent.index(
        "get my salve from my mortar"
    )
    assert fake.sent.count("put my nemoih in my mortar") == 2
    assert crushes(fake) == [
        "crush my salve in my mortar with my pestle",
        "crush my nemoih in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
    ]


def test_the_mortar_is_looked_in_first_and_a_leftover_finished_before_the_study():
    # 2026-09-23, the second spin: after a restock the order loop
    # resumed "the remedy in the mortar" as its own and crushed "my
    # cream" over a nemoih salve — three "Crush what?" and the run
    # ended. Every craft now LOOKs first, and the leftover is done
    # before this recipe's page is studied.
    fake = Fake(
        {
            "look in my mortar": [
                "In the iron mortar you see some unfinished georin salve.\n",
                "There is nothing in there.\n",
            ],
            "study my book": [TOO_HARD],
            "get my dried nemoih": ["You get some dried nemoih."],
            "put my nemoih in my mortar": ["You put your nemoih in your iron mortar."],
            "crush my nemoih in my mortar with my pestle": [CRUSHED],
            "crush my salve in my mortar with my pestle": [FINISHED, FINISHED],
        },
        mindstates=[0, 1, 2, 3, 4, 5],
    )
    out = run(fake, ["count=1"])
    assert "the mortar holds an unfinished neck salve — finishing it first" in out
    assert "remedies: head salve finished (1)" in out
    # The neck salve's page studied and crushed before the head salve's
    # page; the nemoih went in only once the mortar was free.
    assert fake.sent.index("turn my book to page 1") < fake.sent.index(
        "turn my book to page 4"
    )
    assert fake.sent.index("get my salve from my mortar") < fake.sent.index(
        "put my nemoih in my mortar"
    )
    assert crushes(fake) == [
        "crush my salve in my mortar with my pestle",
        "crush my nemoih in my mortar with my pestle",
        "crush my salve in my mortar with my pestle",
    ]


def test_a_crush_refused_again_and_again_ends_the_run_instead_of_spinning():
    fake = Fake(
        {
            "study my book": [TOO_HARD],
            "get my dried nemoih": ["You get some dried nemoih."],
            "put my nemoih in my mortar": ["You put your nemoih in your iron mortar."],
            "crush my nemoih in my mortar with my pestle": ["Crush what?\n"],
        },
        mindstates=[0, 1, 2, 3, 4, 5],
    )
    out = run(fake)
    assert "CRUSH refused again and again" in out
    assert len(crushes(fake)) <= 3


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
    fake = Fake({"study my book": [STUDIED], "get my dried nemoih": [MISSING]})
    out = run(fake)
    assert "no dried nemoih on you" in out
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
            "get my dried flowers": ["You get some dried red flowers."],
            "put my flowers in my mortar": [
                "You put your flowers in your iron mortar."
            ],
            "get my water": ["You get some water."],
            "pour my water in my mortar": [POURED],
            "get my dried nemoih": ["You get some dried nemoih."],
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
    assert fake.sent.index(
        "stow my logbook", fake.sent.index("give my logbook to lanshado")
    )
    # The order is ledgered: the pay, the two stacks at catalog prices,
    # nothing spent, eight crushes, the rank before and after.
    row = ledger_rows()[-1]
    assert row["item"] == "blister cream" and row["stacks"] == 2
    assert row["level"] == "easy" and row["quality"] == "finely-crafted"
    assert (row["earned"], row["cost"], row["spent"]) == (1146, 780, 0)
    assert row["crushes"] == 9 and row["rank_before"] == 2 and row["rank_after"] == 2
    assert row["crush_seconds"] == 159  # the fixtures' "Roundtime: N sec." summed
    out = run(Fake({}), ["ledger"])
    assert "order(s): " in out and "blister cream (easy)" in out
    assert "wield my scimitar" not in fake.sent  # it ends sheathed
    assert not fake.walked  # nothing ran out


def work_answers(**extra):
    """The answers of a two-stack blister cream order with everything
    on you, `extra` laid over them."""
    return {
        "ask lanshado for easy remedies work": [ORDER],
        "read my logbook": [LOGBOOK_NONE, LOGBOOK_OPEN, LOGBOOK_DONE],
        "study my book": [STUDIED],
        "get my dried flowers": ["You get some dried red flowers."],
        "put my flowers in my mortar": ["You put your flowers in your iron mortar."],
        "get my water": ["You get some water."],
        "pour my water in my mortar": [POURED],
        "get my dried nemoih": ["You get some dried nemoih."],
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
    # the Forging Society's for a stock of nuggets (#393), each quoted
    # then bought and stowed, and the remedy left in the mortar taken up
    # again.
    fake = Fake(
        work_answers(
            wealth=[WEALTH_POOR],
            **{
                "get my dried flowers": [MISSING, "You get some dried red flowers."],
                "get my water": [MISSING, "You get some water."],
                "get my nugget": [MISSING, "You get a tiny coal nugget."],
                "order 13": [QUOTE, BOUGHT, QUOTE, BOUGHT],
                "order 1": [QUOTE_WATER, BOUGHT_WATER]
                + [QUOTE_NUGGET, BOUGHT_NUGGET] * CATALYST_STOCK,
            },
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert fake.walked == ["8862", "8862", "8775"]
    # 686 for the flowers and 310 for the nuggets, 100 in the purse.
    assert fake.withdrawn == [586, 210]
    assert fake.sent.count("order 13") == 4
    assert fake.sent.count("order 1") == 2 + 2 * CATALYST_STOCK
    assert fake.sent.count("stow my flowers") == 2
    # The stock stowed as bought, one more after the second stack's put.
    assert fake.sent.count("stow my nugget") == CATALYST_STOCK + 1
    assert "stow my water" in fake.sent
    assert fake.sent.index("stow my mortar") < fake.sent.index("order 13")
    assert "bought 2 x flowers" in out and "bought 1 x water" in out
    assert f"bought {CATALYST_STOCK} x nugget" in out
    # The stack begun goes on after a restock: the flowers go in once
    # per stack, and the page is studied again before the crushes resume.
    assert crushes(fake).count("crush my flowers in my mortar with my pestle") == 2
    assert fake.sent.count("study my book") == 5  # three restocks, two stacks
    # 686 flowers, 62 water, 310 nuggets: the stock is spent in this order.
    assert "order 1 paid 1146 Kronars (88 clear of 1058 spent so far)" in out
    assert "1 order(s), 1146 Kronars earned, 1058 spent" in out
    assert ledger_rows()[-1]["spent"] == 1058


# The ointment order and its alcohol (#427). The CRUSH answer and LOOK
# IN MY MORTAR are captured (2026-10-03); the alcohol's POUR answer is
# not yet, so the water's line stands in for it.
ORDER_OINTMENT = ORDER.replace("blister cream", "moisturizing ointment")
FINISHED_OINTMENT = FINISHED.replace("blister cream", "moisturizing ointment")
POURED_ALCOHOL = POURED.replace("water", "alcohol")
QUOTE_ALCOHOL = QUOTE.replace(
    "(25 pieces) dried red flowers", "10 splashes of grain alcohol"
).replace("343", "81")
BOUGHT_ALCOHOL = BOUGHT.replace(
    "(25 pieces) dried red flowers", "10 splashes of grain alcohol"
)


def ointment_answers(**extra):
    """A two-stack moisturizing ointment order with everything on you,
    `extra` laid over it."""
    return {
        "ask lanshado for easy remedies work": [ORDER_OINTMENT],
        "read my logbook": [LOGBOOK_NONE, LOGBOOK_OPEN, LOGBOOK_DONE],
        "study my book": [STUDIED],
        "get my dried flowers": ["You get some dried red flowers."],
        "put my flowers in my mortar": ["You put your flowers in your iron mortar."],
        "get my alcohol": ["You get some grain alcohol."],
        "pour my alcohol in my mortar": [POURED_ALCOHOL],
        "get my dried plovik": ["You get some dried plovik."],
        "put my plovik in my mortar": [SHAVINGS.replace("nugget", "plovik")],
        "get my nugget": ["You get a tiny coal nugget."],
        "put my nugget in my mortar": [SHAVINGS],
        "crush my flowers in my mortar with my pestle": [NEED_ALCOHOL],
        "crush my ointment in my mortar with my pestle": [
            NEED_HERB,
            NEED_CATALYST,
            FINISHED_OINTMENT,
        ],
        "bundle my ointment with my logbook": [BUNDLED.replace("cream", "ointment")],
        "give my logbook to lanshado": [PAID],
    } | extra


def test_an_ointment_is_crushed_with_alcohol_not_water():
    # 2026-10-03: three of five orders were moisturizing ointment, and
    # each stopped at its first crush: "You need another splash of
    # alcohol" was an answer the table lacked (#427).
    fake = Fake(ointment_answers(), mindstates=[3] + [5] * 20)
    out = run(fake, ["work", "count=1"])
    assert "turn my book to page 2" in fake.sent
    assert fake.sent.count("pour my alcohol in my mortar") == 2  # once a stack
    assert "get my water" not in fake.sent
    assert "stow my alcohol" in fake.sent
    assert "unrecognized" not in out
    assert fake.sent.count("bundle my ointment with my logbook") == 2
    assert "order 1 paid 1146 Kronars" in out
    assert not fake.walked  # nothing ran out


def test_alcohol_run_out_is_bought_at_the_supplies():
    # No alcohol on you: ORDER 2 at the Society's Supplies, ten splashes
    # for 81 Kronars, and the ointment begun goes on.
    fake = Fake(
        ointment_answers(
            wealth=[WEALTH_POOR],
            **{
                "get my alcohol": [MISSING, "You get some grain alcohol."],
                "order 2": [QUOTE_ALCOHOL, BOUGHT_ALCOHOL],
            },
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert "no alcohol on you — the alcohol is missing" in out
    assert fake.walked == ["8862"]
    assert fake.sent.count("order 2") == 2
    assert "bought 1 x alcohol for 8 bronze and 1 copper Kronars" in out
    # The flowers went in once per stack: the restock resumed the first.
    assert crushes(fake).count("crush my flowers in my mortar with my pestle") == 2
    assert "order 1 paid 1146 Kronars (1065 clear of 81 spent so far)" in out


def test_an_ointment_left_in_the_mortar_is_finished_with_alcohol_first():
    # Cecil's mortar since 04:32 on 2026-10-03: an unfinished ointment
    # (captured LOOK). A blister cream order finishes it first, its
    # alcohol bought, and only then puts the cream's flowers in. The
    # mortar is looked in twice before the restock (the order's craft,
    # then the leftover's own) and twice after.
    leftover = "In the iron mortar you see some unfinished moisturizing ointment.\n"
    fake = Fake(
        work_answers(
            wealth=[WEALTH_POOR],
            **{
                "look in my mortar": [leftover] * 4 + ["There is nothing in there.\n"],
                "get my alcohol": [MISSING, "You get some grain alcohol."],
                "pour my alcohol in my mortar": [POURED_ALCOHOL],
                "order 2": [QUOTE_ALCOHOL, BOUGHT_ALCOHOL],
                "get my dried plovik": ["You get some dried plovik."],
                "put my plovik in my mortar": [SHAVINGS.replace("nugget", "plovik")],
                "crush my ointment in my mortar with my pestle": [
                    NEED_ALCOHOL,
                    NEED_ALCOHOL,
                    NEED_HERB,
                    NEED_CATALYST,
                    FINISHED_OINTMENT,
                ],
            },
        ),
        mindstates=[3] + [5] * 40,
    )
    out = run(fake, ["work", "count=1"])
    assert "the mortar holds an unfinished moisturizing ointment — finishing it" in out
    assert "bought 1 x alcohol" in out
    assert "the moisturizing ointment is done and stowed — the mortar is free" in out
    assert fake.sent.index("get my ointment from my mortar") < fake.sent.index(
        "put my flowers in my mortar"
    )
    assert "order 1 paid 1146 Kronars" in out


def test_a_bystanders_line_in_a_crush_window_is_not_a_miss():
    # Three passers-by in a row used to end the run as three
    # unrecognized answers (2026-09-22); the crush is sent again.
    fake = Fake(
        work_answers(
            **{
                "crush my flowers in my mortar with my pestle": [
                    "Swoth runs south.\n",
                    "Swoth just arrived.\n",
                    "Swoth runs south.\n",
                    NEED_WATER,
                ]
            }
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert "unrecognized" not in out
    assert "order 1 paid 1146 Kronars" in out


REJECTED = (
    "The work order requires items of a higher quality, so you decide against "
    "bundling that.\n"
)


def test_a_remedy_below_the_orders_quality_is_disposed_of_and_another_made(
    monkeypatch,
):
    # Captured 2026-09-22: the third cream of an order refused at the
    # logbook. It is stowed, a fourth stack is crafted, the order is
    # paid, and the ledger's cost counts three stacks for two owed.
    fake = Fake(
        work_answers(
            **{
                "bundle my cream with my logbook": [BUNDLED, REJECTED, BUNDLED],
                "read my logbook": [
                    LOGBOOK_NONE,
                    LOGBOOK_OPEN,
                    LOGBOOK_OPEN,
                    LOGBOOK_DONE,
                ],
                "crush my cream in my mortar with my pestle": [
                    NEED_HERB,
                    NEED_CATALYST,
                    FINISHED,
                    NEED_HERB,
                    NEED_CATALYST,
                    FINISHED,
                    NEED_HERB,
                    NEED_CATALYST,
                    FINISHED,
                ],
            }
        ),
        mindstates=[3] + [5] * 40,
    )
    from client.game import discard

    monkeypatch.setattr(discard, "droppable_items", lambda: frozenset({"cream"}))
    out = run(fake, ["work", "count=1"])
    assert (
        "below the order's quality — disposed of, another stack for the 1 still "
        "owed (1/3)" in out
    )
    assert fake.sent.count("bundle my cream with my logbook") == 3
    assert fake.sent.count("drop my cream") == 1  # settings.json's droppable
    assert "stow my cream" not in fake.sent
    assert "order 1 paid 1146 Kronars" in out
    row = ledger_rows()[-1]
    assert row["stacks"] == 2 and row["cost"] == 3 * 390
    assert '"rejected": 1' in row["extra"]
    assert "x2+1 rejected" in run(Fake({}), ["ledger"])
    # Three rejections in one order give it up; the order waits.
    poor = Fake(
        work_answers(
            **{
                "bundle my cream with my logbook": [REJECTED],
                "read my logbook": [
                    LOGBOOK_NONE,
                    LOGBOOK_OPEN.replace("1 more", "2 more"),  # the count never moves
                ],
                "crush my cream in my mortar with my pestle": [
                    NEED_HERB,
                    NEED_CATALYST,
                    FINISHED,
                ],
            }
        ),
        mindstates=[3] + [5] * 60,
    )
    monkeypatch.setattr(discard, "droppable_items", lambda: frozenset())
    out = run(poor, ["work", "count=1"])
    assert (
        "3 remedies below the order's quality — the order waits in the logbook" in out
    )
    assert "drop refused: 'cream'" in out and "drop my cream" not in poor.sent
    assert poor.sent.count("stow my cream") == 3  # the list refused: stowed
    assert "give my logbook to lanshado" not in poor.sent


def test_an_order_left_half_done_keeps_its_spend_for_the_run_that_finishes_it():
    # Run 1: the first stack needs coal (a stock of ten nuggets
    # bought), the second stack's flowers are gone and the shop quotes
    # something else — the order waits. Run 2 resumes the logbook's
    # order and hands it in: one row, two stacks, the coal counted.
    from client.game.workorders import load_open

    first = Fake(
        work_answers(
            wealth=[WEALTH_POOR],
            **{
                "get my nugget": [MISSING, "You get a tiny coal nugget."],
                "order 1": [QUOTE_NUGGET, BOUGHT_NUGGET] * CATALYST_STOCK,
                "get my dried flowers": ["You get some dried red flowers.", MISSING],
                "order 13": [QUOTE_WATER],
            },
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(first, ["work"])
    assert f"bought {CATALYST_STOCK} x nugget" in out  # two owed, the rest stock
    assert "the order waits in the logbook" in out
    kept = load_open("Lanival")
    assert kept["item"] == "blister cream" and kept["count"] == 2
    assert kept["spent"] == 310 and kept["crushes"] == 4
    second = Fake(
        work_answers(**{"read my logbook": [LOGBOOK_OPEN, LOGBOOK_DONE]}),
        mindstates=[5] * 30,
    )
    out = run(second, ["work", "count=1"])
    assert "310 Kronars and 4 crushes so far carried over" in out
    row = ledger_rows()[-1]
    assert (row["stacks"], row["spent"], row["crushes"]) == (2, 310, 8)
    assert load_open("Lanival") is None


def test_a_shop_that_quotes_something_else_ends_the_purchase():
    fake = Fake(
        work_answers(
            wealth=[WEALTH_POOR],
            **{"get my dried flowers": [MISSING], "order 13": [QUOTE_WATER]},
        )
    )
    out = run(fake, ["work"])
    assert "ORDER 13 quoted '10 splashes of water', not flowers — refused" in out
    assert "out of dried flowers — the order waits in the logbook" in out
    assert fake.sent.count("order 13") == 1
    assert fake.sent[fake.sent.index("order 13") + 1] == "refuse"  # the quote closed
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


def test_a_return_mid_order_finishes_the_order_before_ending():
    # ;train's return word lands during the first stack: the order is
    # crafted to the end and handed in, and no second order is asked.
    fake = Fake(work_answers(), mindstates=[3] + [5] * 30, stop_after=2)
    out = run(fake, ["work"])
    assert "return — finishing the order in hand first" in out
    assert fake.sent.count("bundle my cream with my logbook") == 2
    assert "order 1 paid 1146 Kronars" in out
    assert fake.sent.count("ask lanshado for easy remedies work") == 1
    assert "stopping as asked — the order is handed in" in out


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


# The map keys its rooms by int (the search looked them up by str once
# and found no building at the hand-in, 10:28 on 2026-09-23).
SOCIETY = {
    8859: {"title": ["[[Crossing Alchemy Society, Entrance]]"]},
    8860: {"title": ["[[Crossing Alchemy Society, Tool Shop]]"]},
    8861: {"title": ["[[Crossing Alchemy Society, Bookstore]]"]},
    8862: {"title": ["[[Crossing Alchemy Society, Supplies]]"]},
    8863: {"title": ["[[Crossing Alchemy Society, Office]]"]},
    909: {"title": ["[[Crossing, Alchemy Street]]"]},
}


class Society:
    """A map with the society's rooms, resolving the hall's id."""

    rooms = SOCIETY

    def resolve(self, query):
        return [int(query)] if query.isdigit() and int(query) in SOCIETY else []


MASTER_LISTING = (
    "You also see Alchemy Society Master Lanshado, a clerk, a plant grinder "
    "and a dry press."
)


def test_the_master_is_looked_for_through_the_building_when_the_hall_lacks_him():
    # 01:26 on 2026-09-23: the Tool Shop listed a clerk and no master
    # ("Lanshado steadies himself and shuffles away"); he wanders the
    # society's rooms, so the script walks them until one names him.
    fake = Fake({})
    fake.state.room_objs = "You also see a clerk, a plant grinder and a dry press."
    script.to_master = lambda s, profile: True

    def walk_to(s, target, describe):
        fake.walked.append(str(target))
        if str(target) == "8863":
            fake.state.room_objs = MASTER_LISTING
        return True

    script.walk_to = walk_to
    mapdb = Society()
    assert find_master(fake, {}, "lanshado", mapdb=mapdb, here=8860)
    assert fake.walked == [
        "8859",
        "8861",
        "8862",
        "8863",
    ]  # the street is not the building
    assert "looking through the building's 4 other room(s)" in "\n".join(fake.echoed)
    assert "found lanshado in room 8863" in "\n".join(fake.echoed)

    fake.state.room_objs = MASTER_LISTING
    fake.walked.clear()
    hall_walks = []
    script.to_master = lambda s, profile: hall_walks.append(1) or True
    assert find_master(fake, {}, "lanshado", mapdb=mapdb, here=8860)
    assert fake.walked == [] and hall_walks == []  # in his room: no walk at all
    script.to_master = lambda s, profile: True

    # The walker cannot name the room (here=None): the hall anchors it.
    fake.state.room_objs = "You also see a clerk."
    fake.walked.clear()
    lost = Fake({})
    lost.state.room_objs = "You also see a clerk."

    def walk_lost(s, target, describe):
        lost.walked.append(str(target))
        if str(target) == "8863":
            lost.state.room_objs = MASTER_LISTING
        return True

    script.walk_to = walk_lost
    assert find_master(lost, {}, "lanshado", mapdb=mapdb, here=None)
    assert lost.walked == ["8859", "8860", "8861", "8862", "8863"]


def test_a_master_nowhere_in_the_building_ends_the_search_after_two_laps():
    fake = Fake({})
    fake.state.room_objs = "You also see a clerk."
    script.to_master = lambda s, profile: True
    script.walk_to = lambda s, target, describe: fake.walked.append(str(target)) or True
    mapdb = Society()
    assert not find_master(fake, {}, "lanshado", mapdb=mapdb, here=8860)
    assert len(fake.walked) == 8  # two laps of four rooms
    assert "nowhere in the building after 2 lap(s)" in "\n".join(fake.echoed)
    street = SimpleNamespace(rooms={909: SOCIETY[909]}, resolve=lambda q: [])
    assert not find_master(fake, {}, "lanshado", mapdb=street, here=909)
    assert "no other room of the building" in "\n".join(fake.echoed)


def test_an_ask_that_finds_him_gone_looks_again_once():
    # He shuffled away between the arrival and the ASK: one more search
    # and one more ASK, then the order.
    fake = Fake({"ask lanshado for easy remedies work": [NOT_HERE, ORDER]})
    script.ask = fake.ask
    sought = []
    parsed = script.order(
        fake, "lanshado", "easy", seek=lambda: sought.append(1) or True
    )
    assert sought == [1]
    assert parsed and parsed["item"] == "blister cream"
    assert fake.sent.count("ask lanshado for easy remedies work") == 2


# Captured 2026-09-26: an order past its due time, the logbook's word and
# the master's when asked anyway.
LOGBOOK_EXPIRED = (
    "You open your logbook and sort through its contents.\n"
    "This logbook is tracking a work order that has expired.  You must untie any "
    "items bundled with the logbook then ASK the trainer for another work order.\n"
)
MASTER_UNTIE_FIRST = (
    'Lanshado looks at your logbook and says, "Hmm, you realize you have items '
    "bundled with the logbook, and should untie them before getting a new work "
    'order."\n'
)


def test_an_expired_order_is_untied_and_a_new_one_asked():
    # 2026-09-26: a blister cream order from the night before stopped
    # every ;remedies work after it ("no order read, stopping").
    fake = Fake(
        work_answers(
            **{
                "read my logbook": [LOGBOOK_EXPIRED, LOGBOOK_OPEN, LOGBOOK_DONE],
                "untie my logbook": [
                    # Captured 2026-09-26, the first live untie.
                    "You untie the cream from the logbook.\n",
                    # Captured 2026-09-26, the logbook bare.
                    "You have nothing bundled with the logbook.\n",
                ],
            }
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert "the logbook's order expired — untying it for a new one" in out
    assert fake.sent.index("untie my logbook") < fake.sent.index(
        "ask lanshado for easy remedies work"
    )
    assert "order 1 paid 1146 Kronars" in out
    assert "please report it" not in out  # both wordings are known


def test_a_master_asking_to_untie_first_gets_the_logbook_untied_and_asked_again():
    fake = Fake(
        work_answers(
            **{
                "ask lanshado for easy remedies work": [MASTER_UNTIE_FIRST, ORDER],
                "untie my logbook": ["There is nothing tied to your logbook.\n"],
            }
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert fake.sent.count("ask lanshado for easy remedies work") >= 2
    assert "untie my logbook" in fake.sent
    assert "no order read" not in out


# Captured 2026-09-30 (#397): an order that ran out while it was worked,
# the BUNDLE's answer and the master's at the hand-in.
BUNDLE_EXPIRED = (
    "This work order has expired.  You should give this logbook to a crafting "
    "trainer to have it cleared, or ask a trainer for a new work order.\n"
)
HANDIN_EXPIRED = (
    "Apparently the work order time limit has expired.  You should untie any items "
    "bundled with it and then ask Lanshado for another.\n"
)
UNTIED = "You untie the cream from the logbook.\n"
UNTIED_NONE = "You have nothing bundled with the logbook.\n"


def test_an_order_expiring_at_a_bundle_is_untied_and_another_asked():
    # 2026-09-30 10:54: the BUNDLE answered the expiry, the READ after it
    # was taken for "0 more", and the run walked the dead order to the
    # master. The stack is stowed for the next order instead, the next
    # READ unties the logbook, and a new order is asked and filled.
    fake = Fake(
        work_answers(
            **{
                "read my logbook": [
                    LOGBOOK_NONE,
                    LOGBOOK_EXPIRED,
                    LOGBOOK_EXPIRED,
                    LOGBOOK_OPEN,
                    LOGBOOK_DONE,
                ],
                "bundle my cream with my logbook": [BUNDLE_EXPIRED, BUNDLED],
                "untie my logbook": [UNTIED, UNTIED_NONE],
            }
        ),
        mindstates=[3] + [5] * 60,
    )
    out = run(fake, ["work", "count=1"])
    assert "please report it" not in out
    assert out.count("the logbook's order expired — untying it for a new one") == 1
    first_bundle = fake.sent.index("bundle my cream with my logbook")
    assert "stow my cream" in fake.sent[first_bundle:]
    assert fake.sent.count("ask lanshado for easy remedies work") == 2
    asks = [i for i, c in enumerate(fake.sent) if c.startswith("ask lanshado")]
    assert asks[0] < fake.sent.index("untie my logbook") < asks[1]
    assert fake.sent.count("give my logbook to lanshado") == 1  # only the new one
    assert "order 1 paid 1146 Kronars" in out


def test_an_order_expiring_at_the_hand_in_is_untied_and_another_asked():
    # 2026-09-30 10:54: the master's expiry answer stopped the run
    # ("the master answered ... to the logbook — stopping").
    fake = Fake(
        work_answers(
            **{
                "read my logbook": [
                    LOGBOOK_NONE,
                    LOGBOOK_OPEN,
                    LOGBOOK_DONE,
                    LOGBOOK_EXPIRED,
                    LOGBOOK_OPEN,
                    LOGBOOK_DONE,
                ],
                "give my logbook to lanshado": [HANDIN_EXPIRED, PAID],
                "untie my logbook": [UNTIED, UNTIED, UNTIED_NONE],
            }
        ),
        mindstates=[3] + [5] * 60,
    )
    out = run(fake, ["work", "count=1"])
    assert "to the logbook — stopping" not in out
    assert out.count("the logbook's order expired — untying it for a new one") == 1
    assert fake.sent.count("untie my logbook") == 3
    assert fake.sent.count("ask lanshado for easy remedies work") == 2
    assert "order 1 paid 1146 Kronars" in out


def test_an_order_expiring_after_a_return_ends_the_run_there():
    # A typed `return` finishes the order in hand; the hand-in finds it
    # expired and the run ends without asking another — the next run's
    # READ unties it.
    fake = Fake(
        work_answers(**{"give my logbook to lanshado": [HANDIN_EXPIRED]}),
        mindstates=[3] + [5] * 60,
        stop_after=1,
    )
    out = run(fake, ["work"])
    assert "the order expired — stopping as asked; the next run unties it" in out
    assert fake.sent.count("ask lanshado for easy remedies work") == 1
    assert "untie my logbook" not in fake.sent


def test_a_full_stack_the_combine_refuses_is_the_one_used():
    # 2026-10-01 10:22 (#402): 21 pieces in hand, the next stack full —
    # "That stack of herbs is too large to add more to." — read as "would
    # not join": the full stack was stowed and the run foraged 75 pieces.
    fake = Fake(
        {
            "count my flowers": [
                "You count out 21 pieces of material there.\n",
                "You count out 75 pieces of material there.\n",
            ],
            "get dried flowers from my backpack": [
                "You get some dried red flowers from inside your backpack.\n"
            ],
            "combine flowers with flowers": [
                "That stack of herbs is too large to add more to.\n"
            ],
        }
    )
    fake.state.possessions = [
        {"exist": "1", "name": "a rugged backpack", "noun": "backpack", "depth": 0},
        {
            "exist": "2",
            "name": "some dried red flowers",
            "noun": "flowers",
            "container_exist": "1",
            "depth": 1,
        },
    ]
    script.ask = fake.ask
    assert script.full_stack(fake, "flowers") is True
    assert "put my second flowers in my backpack" in fake.sent
    assert "stow my flowers" not in fake.sent
    assert fake.sent.count("get dried flowers from my backpack") == 1


def test_a_run_merges_the_herb_stacks_first_and_says_so(monkeypatch):
    # #402: fifteen stacks of dried red flowers sat in the backpack while
    # the run foraged more. `;remedies merge` merges each dried herb a
    # container lists twice or more (client/game/herbstacks.py) and ends.
    merged = []
    monkeypatch.setattr(
        script.herbstacks,
        "merge",
        lambda s, ask, herb, container, ids=None: (
            merged.append((herb, container, ids)) or (9, 4)
        ),
    )
    fake = Fake(
        {
            "look in my backpack": [
                "In the backpack you see some dried red flowers, an iron mortar, "
                "some dried nemoih and some dried red flowers.\n"
            ],
        }
    )
    fake.state.possessions = [
        {"exist": "1", "name": "a rugged backpack", "noun": "backpack", "depth": 0},
        {
            "exist": "2",
            "name": "some dried red flowers",
            "noun": "flowers",
            "container_exist": "1",
            "depth": 1,
        },
    ]
    fake.state.possessions += [
        {"exist": "3", "name": "a black gem pouch", "noun": "pouch", "depth": 0},
        {
            "exist": "4",
            "name": "a tiny ruby",
            "noun": "ruby",
            "container_exist": "3",
            "depth": 1,
        },
        {
            "exist": "5",
            "name": "some dried red flowers",
            "noun": "flowers",
            "container_exist": "1",
            "depth": 1,
        },
    ]
    out = run(fake, ["merge"])
    # INV LIST first, the stacks by their ids (#414); no LOOK IN needed.
    assert "inv list" in fake.sent
    assert "look in my pouch" not in fake.sent  # no herb there
    assert merged == [
        ("dried red flowers", "backpack", ["2", "5"])
    ]  # one nemoih: left alone
    assert (
        "remedies: 9 stacks of dried red flowers in the backpack merged into 4" in out
    )
    assert not any(c.startswith(("crush", "study")) for c in fake.sent)


def test_a_pestle_worn_past_use_stops_the_crushing_at_once():
    # Captured 2026-09-26: "The iron pestle is far too damaged to be used
    # for that." read as a bystander's line (no "you") and the crushes ran
    # on — 34 in two minutes until stopped by hand.
    worn = "The iron pestle is far too damaged to be used for that.\n"
    fake = Fake(
        work_answers(**{"crush my cream in my mortar with my pestle": [worn]}),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert sum(c.startswith("crush ") for c in fake.sent) <= 2
    assert "the tool needs repair or replacing" in out


def test_a_stopped_run_puts_the_pestle_and_mortar_away():
    # 2026-09-26: a ;stop remedies left both in hand, and ;forage after it
    # could not collect with no hand free.
    fake = Fake({})
    puts = []
    fake.put = lambda command, cleanup=False: puts.append((command, cleanup))
    fake.state.left_hand = {"noun": "pestle"}
    fake.state.right_hand = {"noun": "mortar"}
    script.put_tools_away(fake)
    assert puts == [("stow my pestle", True), ("stow my mortar", True)]


# #324: the stacks untied from an expired order, as INV LIST keeps them
# (2026-09-26): two finished creams in the backpack, a third begun in
# the mortar.
CREAMS_ON_HAND = [
    {"exist": "1", "name": "a rugged backpack", "noun": "backpack", "depth": 0},
    {
        "exist": "2",
        "name": "some blister cream",
        "noun": "cream",
        "container_exist": "1",
        "depth": 1,
    },
    {
        "exist": "3",
        "name": "some blister cream",
        "noun": "cream",
        "container_exist": "1",
        "depth": 1,
    },
    {
        "exist": "4",
        "name": "an iron mortar",
        "noun": "mortar",
        "container_exist": "1",
        "depth": 1,
    },
    {
        "exist": "5",
        "name": "some unfinished blister cream",
        "noun": "cream",
        "container_exist": "4",
        "depth": 2,
    },
]


def test_the_finished_stacks_on_hand_are_the_stacks_found():
    assert script.stacks_on_hand(CREAMS_ON_HAND, "blister cream") == [
        "backpack",
        "backpack",
    ]
    assert script.stacks_on_hand(CREAMS_ON_HAND, "nemoih salve") == []


def test_stacks_already_carried_are_bundled_before_any_crush():
    # 2026-09-26: the run crushed a third cream with two in the pack and
    # 10 roisaen left; bundled by hand, "You notate the cream in the
    # logbook then bundle it up for delivery." each.
    fake = Fake(
        work_answers(
            **{
                "get my blister cream from my backpack": [
                    "You get some blister cream from inside your backpack.\n"
                ],
            }
        ),
        mindstates=[3] + [5] * 30,
    )
    fake.state.possessions = CREAMS_ON_HAND
    out = run(fake, ["work", "count=1"])
    assert fake.sent.count("get my blister cream from my backpack") == 2
    assert fake.sent.count("bundle my cream with my logbook") == 2
    assert fake.crushes == 0
    assert "a blister cream from the backpack bundled — 1 more" in out
    assert "order 1 paid" in out


# Captured 2026-09-27 (Cecil's blister cream): GET MY NUGGET found a
# looted lead nugget, not the coal one the catalyst is.
LEAD_REFUSED = (
    "You cannot find a way to add that as an ingredient to the salve.\n"
    "You realize the lead nugget is not required to continue crafting the "
    "head salve, so you stop.\n"
)


def test_a_catalyst_the_remedy_refuses_stops_the_craft_not_a_loop():
    # 2026-09-27: the refusal read as "another remedy in the mortar",
    # the fetch counted as done, and CRUSH / PUT went round 370 times
    # until the 400-crush fuse while the work order's timer ran.
    fake = Fake(
        {
            "study my book": [TOO_HARD],
            "get my dried nemoih": ["You get some dried nemoih."],
            "put my nemoih in my mortar": ["You put your nemoih in your iron mortar."],
            "get my nugget": ["You get a medium lead nugget."],
            "put my nugget in my mortar": [LEAD_REFUSED],
            "crush my nemoih in my mortar with my pestle": [CRUSHED],
            "crush my salve in my mortar with my pestle": [NEED_CATALYST],
        },
        mindstates=[0] * 10,
    )
    out = run(fake, ["count=1"])
    assert "found something the remedy refuses as its catalyst" in out
    assert fake.sent.count("put my nugget in my mortar") == 1
    assert len(crushes(fake)) == 2


def test_a_catalyst_named_coal_nugget_is_bought_as_the_catalog_nugget():
    from client.game.profile import DEFAULTS, save_profile

    save_profile(
        "Lanival",
        DEFAULTS
        | {
            "weapon": "scimitar",
            "weapon_container": "scabbard",
            "catalyst": "coal nugget",
        },
    )
    fake = Fake(
        work_answers(
            wealth=[WEALTH_POOR],
            **{
                "get my coal nugget": [MISSING, "You get a tiny coal nugget."],
                "put my coal nugget in my mortar": [SHAVINGS],
                "order 1": [QUOTE_NUGGET, BOUGHT_NUGGET] * CATALYST_STOCK,
            },
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert "8775" in fake.walked
    assert f"bought {CATALYST_STOCK} x coal nugget" in out
    assert "stow my coal nugget" in fake.sent


# The herb's size (#370), captured 2026-09-28: a foraged 12-piece stack,
# a bought 25, the mortar measuring off its 25 from the 37 combined.
PACK = [
    {
        "exist": "1",
        "noun": "backpack",
        "name": "a rugged backpack",
        "container_exist": None,
    },
    {
        "exist": "2",
        "noun": "flowers",
        "name": "some dried red flowers",
        "container_exist": "1",
    },
]
TWELVE = "You count out 12 pieces of material there.\n"
THIRTY_SEVEN = "You count out 37 pieces of material there.\n"
FROM_PACK = "You get some dried red flowers from inside your backpack.\n"
JOINED = "You combine the stacks of herbs together.\n"
MEASURED = (
    "The mortar can only hold 25 pieces of material.  So you count off and place "
    "only that many inside.\n"
)
WRONG_SIZE = (
    "You notice the workorder calls for stacks of 5 for each remedy, and think it "
    "best to mark and cut the remedy down to the required size before bundling.\n"
)


def _fetching(answers):
    fake = Fake(answers)
    fake.state.possessions = PACK
    script.ask = fake.ask
    return fake


def test_a_short_herb_stack_is_combined_with_another_before_the_mortar():
    fake = _fetching(
        {
            "get my dried flowers": ["You get some dried red flowers."],
            "count my flowers": [TWELVE, THIRTY_SEVEN],
            "get dried flowers from my backpack": [FROM_PACK],
            "combine flowers with flowers": [JOINED],
            "put my flowers in my mortar": [MEASURED],
        }
    )
    assert script.fetch_into_mortar(fake, "flowers", "herb") is True
    sent = fake.sent
    assert sent.index("combine flowers with flowers") < sent.index(
        "put my flowers in my mortar"
    )
    assert sent.index("stow my mortar") < sent.index(
        "get dried flowers from my backpack"
    )
    # The mortar took its 25; the other 12 go back, then the pestle.
    after = sent[sent.index("put my flowers in my mortar") :]
    assert after[:3] == [
        "put my flowers in my mortar",
        "stow my flowers",
        "get my pestle",
    ]


def test_a_herb_stack_too_short_to_top_up_is_stowed_and_bought_for():
    fake = _fetching(
        {
            "get my dried flowers": ["You get some dried red flowers."],
            "count my flowers": [TWELVE],
            "get dried flowers from my backpack": [MISSING],
        }
    )
    assert script.fetch_into_mortar(fake, "flowers", "herb") is False
    assert "put my flowers in my mortar" not in fake.sent
    assert "stow my flowers" in fake.sent
    assert any("fewer than 25 pieces" in text for text in fake.echoed)


def test_the_stack_in_hand_is_counted_by_its_id_when_the_tag_carries_one():
    # #402: a bare COUNT MY FLOWERS names the first stack of that noun,
    # whatever kind; the hand tag's id names the one held (items.name).
    fake = _fetching({"count #77": ["You count out 25 pieces of material there.\n"]})
    fake.state.left_hand = {"noun": "flowers", "name": "red flowers", "exist": "77"}
    assert script.full_stack(fake, "flowers") is True
    assert fake.sent == ["count #77"]


def test_a_remedy_of_another_stack_size_is_kept_not_bundled_or_dropped():
    fake = _fetching(
        {
            "bundle my cream with my logbook": [WRONG_SIZE],
            "read my logbook": [LOGBOOK_OPEN],
        }
    )
    outcome, remaining, _ = script.bundle(fake, "cream", 4)
    assert outcome == "size"
    assert "stow my cream" in fake.sent
    assert not any(c.startswith("drop") for c in fake.sent)


class Foraging(Fake):
    """A handle that can start ;forage: it runs for `polls` looks."""

    def __init__(self, answers, polls=2):
        super().__init__(answers)
        self.started, self.killed, self.polls = [], [], polls

    def run(self, name, args):
        self.started.append((name, list(args)))
        return True

    def is_running(self, name):
        self.polls -= 1
        return self.polls >= 0

    def kill(self, name):
        self.killed.append(name)


SPEC = ("2", "1", "flowers", "nemoih", "cream", "water")


def test_a_return_during_a_forage_lets_it_press_and_finishes_the_order(
    monkeypatch,
):
    # 2026-10-01 19:10 (#406): ;train's return killed ;forage mid-press —
    # 105 fresh pieces never pressed — and the run bought four stacks.
    fake = Foraging({}, polls=3)
    words = iter(["return"])
    fake.command = lambda timeout=None: next(words, None)
    script.ask = fake.ask
    bought = []
    monkeypatch.setattr(script, "buy", lambda *args: bought.append(args) or True)
    tally = {"spent": 0}
    had = script.restock(
        fake, SPEC, "nugget", "dried flowers", 4, tally, {"forage_herbs": True}
    )
    assert had is True
    assert fake.killed == [] and bought == []
    assert tally["ending"] is True
    assert "remedies: return — finishing the order in hand first" in fake.echoed


def test_the_herb_is_fetched_dried_never_a_fresh_stack_of_its_noun():
    # 2026-10-01 19:11:25 (#406): GET MY FLOWERS took "some red flowers"
    # (fresh), which neither counts to 25 nor combines with the dried
    # stacks, and four stacks were bought with five full ones on hand.
    fake = Fake(work_answers(), mindstates=[3] + [5] * 30)
    run(fake, ["work", "count=1"])
    assert "get my flowers" not in fake.sent
    assert "get my dried flowers" in fake.sent
    assert "get my dried nemoih" in fake.sent


def test_a_herb_run_out_is_foraged_once_an_order_before_any_is_bought(monkeypatch):
    fake = Foraging({})
    script.ask = fake.ask
    bought = []
    monkeypatch.setattr(
        script,
        "buy",
        lambda s, noun, count, shop, catalog, tally: (
            bought.append((noun, count)) or True
        ),
    )
    tally = {"spent": 0}
    had = script.restock(
        fake, SPEC, "nugget", "dried flowers", 3, tally, {"forage_herbs": True}
    )
    assert had is True
    assert fake.started == [("forage", ["herb", "red", "flower", "pieces=75"])]
    assert bought == []
    # The second shortage in the same order is bought, not foraged again.
    script.restock(
        fake, SPEC, "nugget", "dried flowers", 3, tally, {"forage_herbs": True}
    )
    assert len(fake.started) == 1 and bought == [("flowers", 3)]


def test_without_forage_herbs_the_herb_is_bought(monkeypatch):
    fake = Foraging({})
    script.ask = fake.ask
    bought = []
    monkeypatch.setattr(
        script,
        "buy",
        lambda s, noun, count, shop, catalog, tally: (
            bought.append((noun, count)) or True
        ),
    )
    script.restock(fake, SPEC, "nugget", "dried flowers", 2, {"spent": 0}, {})
    assert fake.started == [] and bought == [("flowers", 2)]


def test_the_catalyst_is_bought_as_a_stock_not_an_orders_worth(monkeypatch):
    # #393: three nuggets for a two-stack order sent the next order to
    # the Forging Society's Supplies again, twice in one task.
    fake = Foraging({})
    bought = []
    monkeypatch.setattr(
        script,
        "buy",
        lambda s, noun, count, shop, catalog, tally: (
            bought.append((noun, count)) or True
        ),
    )
    script.restock(fake, SPEC, "nugget", "nugget", 2, {"spent": 0}, {})
    script.restock(fake, SPEC, "nugget", "nugget", 12, {"spent": 0}, {})
    assert bought == [("nugget", CATALYST_STOCK), ("nugget", 13)]


def test_a_stray_stack_in_hand_is_stowed_before_the_tools(monkeypatch):
    # 2026-09-30 (#395): a herb stack ;forage left in hand, the mortar in
    # the other, and the pestle and the book found no hand.
    sent = []
    handle = SimpleNamespace(
        state=SimpleNamespace(
            left_hand=None, right_hand={"noun": "flowers", "name": "dried red flowers"}
        ),
        echo=lambda text: None,
    )
    monkeypatch.setattr(
        script, "ask", lambda s, command: sent.append(command) or "You get it."
    )
    assert script.tools_in_hand(handle)
    assert sent == ["stow my flowers", "get my mortar", "get my pestle"]


# --- the restock guard (#413) ------------------------------------------------


def test_a_shortage_found_again_right_after_its_buy_ends_the_order():
    # #413 (2026-10-01): a bare COUNT that read another stack than the one
    # bought kept the flowers "short", and the restock bought 31 times in
    # 20 minutes. One buy per shortage: the same want with no crush since
    # ends the order, the reason said.
    fake = Fake(
        work_answers(
            **{
                "get my dried flowers": [MISSING, "You get some dried red flowers."],
                "count my flowers": [TWELVE],
                "get dried flowers from my backpack": [MISSING],
                "order 13": [QUOTE, BOUGHT, QUOTE, BOUGHT],
            }
        ),
        mindstates=[3] + [5] * 30,
    )
    fake.state.possessions = PACK
    out = run(fake, ["work", "count=1"])
    assert fake.sent.count("order 13") == 4  # two stacks, bought once
    assert "bought 2 x flowers" in out
    assert (
        "flowers bought for this shortage already and the craft still finds none" in out
    )
    assert "the flowers bought are not found — the order waits in the logbook" in out


def test_water_short_again_after_crushing_is_bought_again():
    # The guard is for a want repeated with no crush since its buy; the
    # second stack's water, gone after real crushing, is bought as before.
    # (A resumed craft crushes on without fetching water again, so each
    # stack asks for water once: two misses, then the third stack's find.)
    fake = Fake(
        work_answers(
            **{
                "get my water": [MISSING, MISSING, "You get some water."],
                "order 1": [QUOTE_WATER, BOUGHT_WATER, QUOTE_WATER, BOUGHT_WATER],
            }
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert fake.sent.count("order 1") == 4
    assert out.count("bought 1 x water") == 2
    assert "order 1 paid 1146 Kronars" in out


def test_a_buy_that_leaves_the_load_overburdened_stops_the_run():
    # #413 and #411: five full stacks already read overburdened at the
    # clerk, and the walk after failed sitting. ENCUMBRANCE after each buy.
    fake = Fake(
        work_answers(
            **{
                "get my dried flowers": [MISSING, "You get some dried red flowers."],
                "order 13": [QUOTE, BOUGHT, QUOTE, BOUGHT],
                "encumbrance": ["  Encumbrance : Overburdened\n"],
            }
        ),
        mindstates=[3] + [5] * 30,
    )
    out = run(fake, ["work", "count=1"])
    assert "encumbrance" in fake.sent
    assert (
        "the load reads Overburdened after buying flowers — stopping before a walk fails"
        in out
    )
    assert "Overburdened after buying flowers — the order waits in the logbook" in out
    assert "study my book" not in fake.sent[fake.sent.index("encumbrance") :]


def test_a_load_short_of_the_limit_passes_the_buy():
    fake = _fetching({"encumbrance": ["  Encumbrance : Very Heavy Burden\n"]})
    assert script.overloaded(fake, "flowers", {}) is False
    fake = _fetching({"encumbrance": ["  Encumbrance : Tottering Under Burden\n"]})
    tally = {}
    assert script.overloaded(fake, "flowers", tally) is True
    assert tally["why"] == "Tottering Under Burden after buying flowers"


def test_twenty_buys_in_a_run_end_it():
    fake = _fetching({})
    tally = {"crushes": 3, "spent": 0, "restocks": script.RESTOCKS_PER_RUN}
    assert script.restock(fake, SPEC, "nugget", "dried flowers", 1, tally) is False
    assert tally["why"] == f"{script.RESTOCKS_PER_RUN} buys this run"
    assert not any(c.startswith("order") for c in fake.sent)


# --- a herb STOW the STORE container refuses (#416) -----------------------------


def test_a_herb_stow_the_store_container_refuses_goes_to_the_backpack(monkeypatch):
    # #416 (2026-10-02): a herb bag set as STORE HERBS refused a stack and
    # the game left it in hand, so the next GET had no hand for the pestle.
    # hands.stow falls back to the default container and the craft goes on.
    monkeypatch.setattr(script.hands, "_DEFAULTS", {})
    fake = _fetching(
        {
            "get my dried flowers": ["You get some dried red flowers."],
            "count my flowers": [THIRTY_SEVEN],
            "put my flowers in my mortar": [MEASURED],
            "stow my flowers": ["There isn't any more room in the bag for that."],
            "store default": ["         Default:  a rugged backpack\n"],
            "put my flowers in my backpack": ["You put your flowers in your backpack."],
        }
    )
    assert script.fetch_into_mortar(fake, "flowers", "herb") is True
    assert fake.sent[-4:] == [
        "stow my flowers",
        "store default",
        "put my flowers in my backpack",
        "get my pestle",
    ]
    assert "the flowers went in the backpack — no room where STOW puts it" in (
        fake.echoed
    )


# --- a bought stack that does not answer to "dried" (#420) ------------------------


def test_a_bought_dried_stack_is_reached_by_the_plain_nouns_ordinals():
    # #420 (2026-10-02): the Society's "dried red flowers" answer to
    # "flowers" but not to "dried"; a fresh stack taken on the way goes
    # back where it came from and the next ordinal reaches past it. The
    # containers INV LIST shows are walked in turn by FROM MY <container>:
    # a bare MY SECOND <herb> missed a stack the backpack held (17:36).
    fake = _fetching(
        {
            "get my dried flowers": [MISSING],
            "get flowers from my backpack": [
                "You get some red flowers from inside your backpack.\n"
            ],
            "put my flowers in my backpack": [
                "You put your flowers in your backpack.\n"
            ],
            "get second flowers from my backpack": [
                "You get some dried red flowers from inside your backpack.\n"
            ],
            "count my flowers": [THIRTY_SEVEN],
            "put my flowers in my mortar": [MEASURED],
        }
    )
    assert script.fetch_into_mortar(fake, "flowers", "herb") is True
    assert fake.sent[1:5] == [
        "get my dried flowers",
        "get flowers from my backpack",
        "put my flowers in my backpack",
        "get second flowers from my backpack",
    ]
    assert "put my flowers in my mortar" in fake.sent
    assert not any("missing" in text for text in fake.echoed)


def test_no_dried_stack_among_the_nouns_items_is_the_herb_missing():
    fake = _fetching(
        {
            "get my dried flowers": [MISSING],
            "get flowers from my backpack": [
                "You get some red flowers from inside your backpack.\n"
            ],
            "put my flowers in my backpack": [
                "You put your flowers in your backpack.\n"
            ],
            "get second flowers from my backpack": [MISSING],
        }
    )
    assert script.fetch_into_mortar(fake, "flowers", "herb") is False
    assert "remedies: no dried flowers on you — the herb is missing" in fake.echoed
    assert fake.sent[-1] == "get my pestle"


def test_a_bought_stack_in_a_container_joins_by_the_plain_nouns_ordinals():
    # full_stack's container walk reaches the bought stacks the same way.
    fake = _fetching(
        {
            "get my dried flowers": ["You get some dried red flowers."],
            "count my flowers": [TWELVE, THIRTY_SEVEN],
            "get dried flowers from my backpack": [MISSING],
            "get flowers from my backpack": [
                "You get some dried red flowers from inside your backpack.\n"
            ],
            "combine flowers with flowers": [JOINED],
            "put my flowers in my mortar": [MEASURED],
        }
    )
    assert script.fetch_into_mortar(fake, "flowers", "herb") is True
    sent = fake.sent
    assert sent.index("get flowers from my backpack") < sent.index(
        "combine flowers with flowers"
    )
