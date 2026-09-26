"""How ;repair runs — these tests are the manual. Appraise, walk to the
nearest known shop, GIVE twice (the estimate, the payment), stow the
ticket, wait the roisaen out, hand the ticket back and wear the piece;
the teller for a short purse; the ticket's own shop for `pickup`."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game.mapdb import MapDB
from test_repair import (
    APPRAISE_DENTED,
    APPRAISE_PRISTINE,
    ANALYZE_BATTERED,
    ANALYZE_GOOD,
    LOOK_WAITING,
    NOT_YET,
    PRISTINE,
    QUOTE,
    RANGU_QUOTE,
    RANGU_RETURNED,
    RANGU_TICKET,
    RETURNED,
    TICKET,
)

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "repair_script", REPO / "scripts/repair.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01

MAP = MapDB(
    [
        {"id": 100, "uid": [1], "title": ["[Town, Square]"], "wayto": {}},
        {
            "id": 1900,
            "uid": [9001],
            "title": ["[Provincial Bank, Teller]"],
            "tags": ["bank"],
            "wayto": {},
        },
        {
            "id": 19093,
            "uid": [13020],
            "title": ["[Catrox's Forge, Entryway]"],
            "tags": ["crossing repair", "repair"],
            "wayto": {},
        },
        {
            "id": 19209,
            "uid": [44101],
            "title": [
                "[Crossing Engineering Society, Rangu's Repair Shop and Bookstore]"
            ],
            "wayto": {},  # no `repair` tag: the tool shop is known by room
        },
        {
            "id": 12314,
            "uid": [9003],
            "title": ["[Jeihrem's Barrow, Repair]"],
            "tags": ["repair"],  # no repairman known: never a goal
            "wayto": {},
        },
    ]
)

WORN = [
    {"noun": "plate", "depth": 0, "worn": True},
    {"noun": "shield", "depth": 0, "worn": True},
]
APPRAISE_GOOD = (
    "You believe that the target shield is quite guarded against damage and is "
    "in good condition.\nRoundtime: 5 sec.\n"
)
COUNTED = "The clerk counts out {} Kronars and hands them over, making a notation in her ledger.\n"


# GET of a ticket: the first found, then none left (the refusal is the
# game's usual one for a noun not on you).
GOT_THEN_NONE = [
    "You get a Catrox ticket from inside your sack.",
    "What were you referring to?",
]


def wealth(copper):
    return (
        f"Wealth:\n  {copper} copper Kronars ({copper} copper Kronars).\n  No Lirums.\n"
    )


class Fake:
    """A handle whose answers come from a queue per command prefix."""

    def __init__(self, answers, possessions=WORN, typed=()):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.walks = []
        self.pending = []
        self.slept = 0
        self.dead = False
        self.args = []
        self.typed = list(typed)
        self.state = SimpleNamespace(
            name="Lanival",
            room_uid=1,
            right_hand=None,
            left_hand=None,
            possessions=list(possessions),
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if queue else ""
                self.pending = [line + "\n" for line in text.splitlines()]
                return

    def get(self, timeout=None, streams=("",)):
        if timeout == 0 or not self.pending:
            return None
        return self.pending.pop(0)

    def command(self, timeout=None):
        return self.typed.pop(0) if self.typed else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.slept += seconds


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    s.state.room_uid = db.rooms[min(goals)]["uid"][0]
    return True


def echoes(fake):
    return "\n".join(fake.echoed)


PROFILE = {"repair_floor": 80, "repair_items": []}


def test_a_dented_plate_is_handed_in_waited_for_and_worn_back():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_DENTED],
            "appraise my shield": [APPRAISE_GOOD],
            "wealth": [wealth(200)],
            "give my plate": [QUOTE, TICKET],
            "give my ticket": [RETURNED],
            "get my Catrox ticket": GOT_THEN_NONE,
        }
    )
    script.run(fake, [], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{19093}]
    after_walk = fake.sent[2:]
    assert after_walk == [
        "wealth",
        "remove my plate",
        "give my plate to Catrox",
        "give my plate to Catrox",
        "stow my ticket",
        "get my Catrox ticket",
        "give my ticket to Catrox",
        "wear my plate",
        "get my Catrox ticket",  # none left: done
    ]
    assert fake.slept >= 5 * 60  # the estimate's roisaen, waited at the shop
    assert "plate is a few dents and dings (51-60 %) — to repair" in echoes(fake)
    assert "shield is in good condition (81-90 %)" in echoes(fake)
    assert "repair: 1 of 1 repaired" in echoes(fake)


def test_check_appraises_and_goes_nowhere():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_DENTED],
            "appraise my shield": [APPRAISE_GOOD],
        }
    )
    script.run(fake, ["check"], mapdb=None, walk_fn=walk, profile=PROFILE)
    assert fake.walks == []
    assert fake.sent == ["appraise my plate quick", "appraise my shield quick"]
    assert "repair: 1 to repair at a floor of 80 %" in echoes(fake)


def test_nothing_below_the_floor_walks_nowhere():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_PRISTINE],
            "appraise my shield": [APPRAISE_GOOD],
        }
    )
    script.run(fake, [], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == []
    assert "nothing at or below 80 %" in echoes(fake)


def test_a_named_piece_goes_in_whatever_its_condition_and_comes_back_on_if_unscratched():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_PRISTINE],
            "wealth": [wealth(200)],
            "give my plate": [PRISTINE],
        }
    )
    script.run(fake, ["plate"], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{19093}]
    assert fake.sent[-2:] == ["give my plate to Catrox", "wear my plate"]
    assert "plate: not a scratch on it — put back" in echoes(fake)
    assert "nothing handed in" in echoes(fake)


def test_a_short_purse_puts_the_piece_back_fetches_the_rest_and_goes_round_again():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_DENTED],
            "appraise my shield": [APPRAISE_GOOD],
            "wealth": [wealth(50), wealth(110)],
            "withdraw": [COUNTED.format("5 bronze"), COUNTED.format("8 copper")],
            "give my plate": [QUOTE, QUOTE, TICKET],
            "give my ticket": [RETURNED],
            "get my Catrox ticket": GOT_THEN_NONE,
        }
    )
    script.run(fake, [], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{19093}, {1900}, {19093}]
    assert [c for c in fake.sent if c.startswith("withdraw")] == [
        "withdraw 5 bronze",
        "withdraw 8 copper",
    ]
    assert "costs 1 silver and 8 copper Kronars, you carry 5 bronze Kronars" in echoes(
        fake
    )
    assert fake.sent[-2:] == ["wear my plate", "get my Catrox ticket"]
    assert "repair: 1 of 1 repaired" in echoes(fake)


def test_a_ticket_not_yet_done_is_waited_out_and_given_again():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_DENTED],
            "appraise my shield": [APPRAISE_GOOD],
            "wealth": [wealth(200)],
            "give my plate": [QUOTE, TICKET],
            "give my ticket": [NOT_YET, RETURNED],
            "get my Catrox ticket": GOT_THEN_NONE,
        }
    )
    script.run(fake, [], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.sent.count("give my ticket to Catrox") == 2
    assert fake.slept >= (5 + 4) * 60
    assert fake.sent[-2:] == ["wear my plate", "get my Catrox ticket"]


def test_return_typed_hands_in_nothing_more_but_collects_what_was_given():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_DENTED],
            "appraise my shield": [APPRAISE_DENTED],
            "wealth": [wealth(500)],
            "give my plate": [QUOTE, TICKET],
            "give my ticket": [RETURNED],
            "get my Catrox ticket": GOT_THEN_NONE,
        },
        typed=[None, "return"],
    )
    script.run(fake, [], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert "give my shield to Catrox" not in fake.sent
    assert "handing in nothing more" in echoes(fake)
    assert fake.sent[-2:] == ["wear my plate", "get my Catrox ticket"]


def test_pickup_walks_to_the_shop_the_ticket_names():
    fake = Fake(
        {
            "look at my ticket": [LOOK_WAITING],
            "give my ticket": [RETURNED],
            "get my Catrox ticket": GOT_THEN_NONE,
        }
    )
    script.run(fake, ["pickup"], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{19093}]
    assert "give my ticket to Catrox" in fake.sent
    assert fake.sent[-1] == "get my Catrox ticket"
    assert "repair: 1 piece collected" in echoes(fake)


def test_pickup_without_a_ticket_goes_nowhere():
    fake = Fake({"get my ticket": ["What were you referring to?"]})
    script.run(fake, ["pickup"], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == []
    assert "no repair ticket on you" in echoes(fake)


# --- ;repair tools: crafting tools to the Engineering Society's Rangu ---

TOOLS = {**PROFILE, "repair_tools": ["mortar", "pestle"]}


def test_a_battered_pestle_goes_to_rangu_and_back_into_the_pack():
    # 2026-09-26: every CRUSH answered "far too damaged"; APPRAISE names
    # no condition for a tool, ANALYZE does.
    fake = Fake(
        {
            "analyze my mortar": [ANALYZE_GOOD],
            "analyze my pestle": [ANALYZE_BATTERED],
            "wealth": [wealth(200)],
            "give my pestle": [RANGU_QUOTE, RANGU_TICKET],
            "give my ticket": [RANGU_RETURNED],
            "get my Rangu ticket": [
                "You get a Rangu repair ticket from inside your backpack.",
                "What were you referring to?",
            ],
        },
        possessions=[],
    )
    script.run(fake, ["tools"], mapdb=MAP, walk_fn=walk, profile=TOOLS)
    assert fake.sent[:6] == [
        "get my mortar",
        "analyze my mortar",
        "stow my mortar",
        "get my pestle",
        "analyze my pestle",
        "stow my pestle",
    ]
    assert fake.walks == [{19209}]
    assert fake.sent[6:] == [
        "wealth",
        "get my pestle",
        "give my pestle to Rangu",
        "give my pestle to Rangu",
        "stow my ticket",
        "get my Rangu ticket",
        "give my ticket to Rangu",
        "stow my pestle",
        "get my Rangu ticket",
    ]
    assert fake.slept >= 10 * 60
    assert "pestle is battered and practically destroyed (0-20 %) — to repair" in (
        echoes(fake)
    )
    assert "mortar is in good condition (81-90 %)" in echoes(fake)
    assert "repair: 1 of 1 repaired" in echoes(fake)


def test_an_estimate_still_standing_after_the_teller_is_paid_at_the_first_give():
    # 2026-09-26: back from the teller 9 s after Rangu's quote, the first
    # GIVE paid and handed back a ticket; the run called it "no estimate",
    # said "0 of 1 repaired" and left the pestle's ticket in hand.
    fake = Fake(
        {
            "analyze my mortar": [ANALYZE_GOOD],
            "analyze my pestle": [ANALYZE_BATTERED],
            "wealth": [wealth(0), wealth(20)],
            "withdraw": [COUNTED.format("2 bronze")],
            "give my pestle": [RANGU_QUOTE, RANGU_TICKET],
            "give my ticket": [RANGU_RETURNED],
            "get my Rangu ticket": [
                "You get a Rangu repair ticket from inside your backpack.",
                "What were you referring to?",
            ],
        },
        possessions=[],
    )
    script.run(fake, ["tools"], mapdb=MAP, walk_fn=walk, profile=TOOLS)
    assert fake.walks == [{19209}, {1900}, {19209}]
    assert fake.sent.count("give my pestle to Rangu") == 2
    assert "pestle handed in for 2 bronze Kronars, ready in 10 roisaen" in echoes(fake)
    assert "no estimate" not in echoes(fake)
    assert "repair: 1 of 1 repaired" in echoes(fake)


def test_tools_in_good_condition_go_nowhere():
    fake = Fake(
        {
            "analyze my mortar": [ANALYZE_GOOD],
            "analyze my pestle": [ANALYZE_GOOD],
        },
        possessions=[],
    )
    script.run(fake, ["tools"], mapdb=MAP, walk_fn=walk, profile=TOOLS)
    assert fake.walks == []
    assert "no tool at or below 80 % — all good" in echoes(fake)


def test_tools_without_a_list_say_how_to_name_them():
    fake = Fake({}, possessions=[])
    script.run(fake, ["tools"], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.sent == []
    assert ";repair tools pestle mortar" in echoes(fake)


def test_the_gear_run_never_walks_to_the_tool_shop():
    fake = Fake(
        {
            "appraise my plate": [APPRAISE_DENTED],
            "appraise my shield": [APPRAISE_PRISTINE],
            "wealth": [wealth(200)],
            "give my plate": [QUOTE, TICKET],
            "give my ticket": [RETURNED],
            "get my Catrox ticket": GOT_THEN_NONE,
        }
    )
    script.run(fake, [], mapdb=MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{19093}]
