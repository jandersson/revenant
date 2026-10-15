"""The commodity pits — these tests are the manual (#557). ;commodities
reads a pit's board and logs it, walks to every pit to read them all,
and carries a good: ORDER at the pit clerk, the guild's pack animal
walked room by room to the buyer's town, SELL at its shipment clerk.
The board, ORDER and SELL answers are the ones captured by hand on
2026-10-15 (client/game/commodities.py, client/game/commoditylog.py,
scripts/commodities.py).
"""

import importlib.util
import pathlib
import re
from types import SimpleNamespace

import pytest

from client.game import commodities, commoditylog, haul, trade
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]

CROSSING_BOARD = """\
           The Crossing Trader Guild Commodity Pit Board
Commodity       Price   Units         Commodity       Price   Units
-------------------------------------------------------------------------
Diamonds        1685  Good Stores     Pearls          725   Good Stores
Gold            1124  Good Stores     Silver          805   Good Stores
Iron ore        77    Surplus!        Charcoal        49    Nearly Out!
Amber           195   Going Fast      Saffron         827   *SOLD OUT!*
Cinnamon        338   *SOLD OUT!*     Papyrus         148   Surplus!
Oranges         218   *SOLD OUT!*     Limes           355   *SOLD OUT!*
Slate           345   Surplus!        Brass           455   Surplus!
Lead            307   Surplus!        Copper          214   Going Fast
Bronze          301   Nearly Out!     Silk            540   Surplus!
Cotton          78    Surplus!        Wool            80    Surplus!
Velvet          200   Going Fast      Lace            261   Going Fast
Deobar oil      59    Surplus!        Myrrh           181   Surplus!
Salt            54    Surplus!        Indigo          152   Good Stores
Purple dye      300   Going Fast      Barley          56    Surplus!
Wheat           108   Surplus!        Oats            149   Surplus!
Corn            47    Good Stores     Acanth          225   Surplus!
Taffelberries   160   *SOLD OUT!*     Apples          40    *SOLD OUT!*
"""
# The same evening's other boards, the goods that matter here.
ARTHE = {
    "diamonds": (1939, "Good Stores"),
    "pearls": (783, "Nearly Out!"),
    "saffron": (732, "Going Fast"),
    "silk": (561, "Surplus!"),
}
LETH = {
    "diamonds": (1765, "Nearly Out!"),
    "saffron": (704, "Going Fast"),
    "silk": (631, "Surplus!"),
}
ORDERED = (
    "The clerk nods as he checks out your order.  He accepts your payment of"
    " 84250 Kronars plus the usual cut of 2712 to the guild, bringing the total"
    " to 86962.  He nods to his assistants, who start to pack up your purchases.\n"
)
SOLD = (
    "The clerk looks over a clipboard on which he has the latest buying prices"
    ' for the town.  "Well, Lanival," he nods, "I can pay you 96950 kronars for'
    ' your pouches of diamonds at this time.  So, here you go."  He smiles as he'
    " hands you your Kronars and instructs an assistant to divest you of the"
    " goods.\n"
    "That was the last of your pouches of diamonds.\n"
)


def render(town, goods):
    """A board in the game's two columns, for the pits not captured whole."""
    title = f"The {town}" if town == "Crossing" else town
    cells = [
        f"{good.capitalize():<16}{price:<6}{stock:<14}"
        for good, (price, stock) in goods.items()
    ]
    rows = ["".join(cells[i : i + 2]).rstrip() + "\n" for i in range(0, len(cells), 2)]
    return (
        f"           {title} Trader Guild Commodity Pit Board\n"
        "Commodity       Price   Units         Commodity       Price   Units\n"
        + "-" * 73
        + "\n"
        + "".join(rows)
    )


# The model


def test_a_board_is_read_for_its_town_and_every_goods_price_and_stock():
    board = commodities.board(CROSSING_BOARD)
    assert board.town == "Crossing"  # "The Crossing" on the board
    assert len(board.goods) == 34
    assert board.goods["diamonds"] == (1685, "Good Stores")
    assert board.goods["iron ore"] == (77, "Surplus!")
    assert board.goods["charcoal"] == (49, "Nearly Out!")
    assert board.goods["saffron"] == (827, "*SOLD OUT!*")
    assert board.goods["taffelberries"] == (160, "*SOLD OUT!*")
    assert set(board.goods) == set(commodities.BANDS)
    assert commodities.board("You see nothing unusual.") is None


def test_a_board_read_without_its_line_breaks_reads_the_same():
    # The familiar stream's lines reached ;trade without their breaks.
    glued = CROSSING_BOARD.replace("\n", "")
    assert commodities.board(glued) == commodities.board(CROSSING_BOARD)
    arthe = commodities.board(render("Arthe Dale", ARTHE))
    assert arthe.town == "Arthe Dale" and arthe.goods == ARTHE


def test_the_pit_clerks_order_and_the_shipment_clerks_sale_are_read():
    assert commodities.order(ORDERED) == (84250, 2712)
    leth = (
        "The clerk nods as he checks out your order.  He accepts your payment of"
        " 3520 Kronars plus the usual cut of 99 to the guild, bringing the total"
        " to 3619."
    )
    assert commodities.order(leth) == (3520, 99)
    assert commodities.order("To purchase goods, ORDER <amount> <commodity>.") is None
    assert commodities.sale(SOLD) == 96950
    assert commodities.sale("I could not find what you were referring to.") is None


def test_a_stock_word_is_its_bands_lowest_count():
    # Diamonds: Going Fast 10-49, Good Stores 50-79, Surplus 80-100.
    assert commodities.held("diamonds", "Good Stores") == 50
    assert commodities.held("diamonds", "Nearly Out!") == 1
    assert commodities.held("diamonds", "*SOLD OUT!*") == 0
    # A buyer takes up to one short of Surplus from there.
    assert commodities.room("diamonds", "Good Stores") == 29
    assert commodities.room("diamonds", "*SOLD OUT!*") == 79
    assert commodities.room("diamonds", "Surplus!") == 0  # buys none


def test_the_plan_buys_what_the_seller_holds_and_the_buyer_takes_short_of_surplus():
    # 50 diamonds sold into Arthe Dale's Good Stores tipped it to Surplus!
    # (2026-10-15): the plan carries 29.
    boards = {
        "Crossing": commodities.board(CROSSING_BOARD).goods,
        "Arthe Dale": ARTHE,
        "Leth Deriel": LETH,
    }
    plan = commodities.plan(boards, "Crossing")
    assert (plan.good, plan.units, plan.buy, plan.sell) == (
        "diamonds",
        29,
        "Crossing",
        "Arthe Dale",
    )
    assert plan.sold == 29 * 1939
    assert plan.bought == commodities.cost(1685, 29) > 29 * 1685
    assert plan.profit == plan.sold - plan.bought
    # Silk reads Surplus! at both buyers: never planned.
    assert all(
        commodities.plan({"Crossing": {"silk": goods["silk"]}, town: goods}, "Crossing")
        is None
        for town, goods in (("Arthe Dale", ARTHE), ("Leth Deriel", LETH))
    )


def test_the_plan_weighs_the_whole_trade_not_the_spread_a_unit():
    # Corn, 47 at the Crossing to 92 at Arthe Dale (Nearly Out!): 243 units
    # the Crossing surely holds clear more than 29 diamonds.
    boards = {
        "Crossing": commodities.board(CROSSING_BOARD).goods,
        "Arthe Dale": dict(ARTHE, corn=(92, "Nearly Out!")),
    }
    plan = commodities.plan(boards, "Crossing")
    assert (plan.good, plan.units, plan.sell) == ("corn", 243, "Arthe Dale")
    assert plan.profit == 243 * 92 - commodities.cost(47, 243)


def test_a_spread_too_thin_for_the_walk_is_no_plan():
    boards = {"Leth Deriel": {"saffron": (704, "Going Fast")}, "Crossing": {}}
    boards["Crossing"]["saffron"] = (720, "*SOLD OUT!*")
    assert commodities.plan(boards, "Leth Deriel") is None


# The log


@pytest.fixture
def history(monkeypatch, tmp_path):
    connect = commoditylog._connect
    path = tmp_path / "history.db"
    monkeypatch.setattr(commoditylog, "_connect", lambda _path: connect(path))
    return path


def test_every_board_read_is_logged_and_the_latest_is_read_back(history):
    commoditylog.log_board("Lanival", commodities.Board("Arthe Dale", ARTHE))
    commoditylog.log_board("Lanival", commodities.board(CROSSING_BOARD))
    later = dict(ARTHE, diamonds=(1939, "Surplus!"))
    commoditylog.log_board("Lanival", commodities.Board("Arthe Dale", later))
    latest = commoditylog.latest()
    assert set(latest) == {"Arthe Dale", "Crossing"}
    assert latest["Arthe Dale"][1]["diamonds"] == (1939, "Surplus!")
    assert len(latest["Crossing"][1]) == 34


def test_a_trade_is_open_until_its_sale(history):
    seq = commoditylog.log_buy(
        "Lanival", "diamonds", 50, "Crossing", 84250, 2712, "Arthe Dale"
    )
    assert commoditylog.open_trade("Lanival") == (
        seq,
        "diamonds",
        50,
        "Crossing",
        84250,
        2712,
        "Arthe Dale",
    )
    assert commoditylog.open_trade("Sable") is None
    commoditylog.log_sale(seq, "Arthe Dale", 96950)
    assert commoditylog.open_trade("Lanival") is None


# The script


def _script():
    spec = importlib.util.spec_from_file_location(
        "commodities_script", REPO / "scripts/commodities.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The pits, their clerks and outposts; one road stands for the 45 rooms
# from Commerce Avenue to Arthe Dale's Cul-de-sac.
MAP = MapDB(
    [
        {"id": 895, "uid": [10155], "title": ["[The Crossing, Commerce Avenue]"],
         "wayto": {"8916": "go doors", "1072": "west", "2039": "go pier"}},
        {"id": 8916, "uid": [13047], "title": ["[Traders' Guild, Shipment Center]"],
         "wayto": {"895": "out", "19275": "south"}},
        {"id": 19275, "uid": [13048], "title": ["[Traders' Guild, The Pit]"],
         "wayto": {"8916": "north"}},
        {"id": 1072, "uid": [20001], "title": ["[Arthe Dale, Village Road]"],
         "wayto": {"895": "east", "1073": "west"}},
        {"id": 1073, "uid": [20002], "title": ["[Arthe Dale, Cul-de-sac]"],
         "wayto": {"1072": "east", "8998": "go yellow building"}},
        {"id": 8998, "uid": [20003], "title": ["[Swotting Hall, Foyer]"],
         "wayto": {"1073": "out", "8999": "go wood door"}},
        {"id": 8999, "uid": [20004], "title": ["[Swotting Hall, Trader's Center]"],
         "wayto": {"8998": "go wood door", "9000": "west"}},
        {"id": 9000, "uid": [20005], "title": ["[Swotting Hall, Trader's Pit]"],
         "wayto": {"8999": "east"}},
        {"id": 2039, "uid": [175001], "title": ["[Leth Deriel, Oakenheart Circle]"],
         "wayto": {"9004": "go mean-looking shanty", "895": "go bridge"}},
        {"id": 9004, "uid": [175100], "title": ["[Eshar's Trading Post, Main Room]"],
         "wayto": {"2039": "out", "13550": "west"}},
        {"id": 13550, "uid": [175101], "title": ["[Eshar's Trading Post, The Pit]"],
         "wayto": {"9004": "east"}},
    ]
)  # fmt: skip
PIT_OF = {room: town for town, room in commodities.PITS.items()}
RECALL_BESIDE = (
    "You seem to recall that you left your lumbering auroch right behind you.\n"
)
FOLLOWS = "You grab hold of your lumbering auroch's harness and make it follow.\n"


class Pits:
    """The handle: boards by pit (READ on the familiar stream, as live),
    answers by command prefix, rooms moved by the walks and by a step
    the lent auroch follows when told to."""

    def __init__(self, boards, answers=(), room=19275, glued=False):
        self.boards = boards
        self.answers = {k: list(v) for k, v in dict(answers).items()}
        self.glued = glued
        self.room = room
        self.animal = None  # the auroch's room once lent
        self.following = False
        self.sent, self.echoed, self.walks, self.heard, self.pending = (
            [],
            [],
            [],
            [],
            [],
        )
        self.typed = []
        self.args = []
        self.state = SimpleNamespace(name="Lanival", right_hand=None, left_hand=None)

    def answer(self, command):
        if command == "read board":
            town = PIT_OF.get(self.room)
            text = render(town, self.boards[town]) if town else "Read what?\n"
            return text.replace("\n", "") if self.glued else text
        if command.startswith("order "):
            self.animal = trade.TOWNS[PIT_OF[self.room]].outpost
        if command == "recall caravan":
            if self.animal is None:
                return "You don't recall having a caravan.\n"
            if self.animal == self.room:
                return RECALL_BESIDE
            return "You recall that your lumbering auroch should be located in...\n[Somewhere]\n"
        if command == "tell lumbering auroch to follow":
            self.following = self.animal == self.room
            return FOLLOWS
        if command == "tell lumbering auroch to wait":
            self.following = False
            return "You tell your lumbering auroch to wait.\n"
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                return queue.pop(0) if len(queue) > 1 else queue[0]
        return ""

    def put(self, command):
        self.sent.append(command)
        wayto = MAP.rooms.get(self.room, {}).get("wayto", {})
        moves = {way: int(room) for room, way in wayto.items()}
        if command in moves:
            self.room = moves[command]
            if self.following:
                self.animal = self.room
                self.heard.append("Your lumbering auroch, following you, arrives.\n")
        text = self.answer(command)
        stream = "familiar" if command == "read board" else ""
        if self.glued and stream:
            self.pending = [(stream, text)]
        else:
            self.pending = [(stream, line + "\n") for line in text.splitlines()]

    def get(self, timeout=None, streams=("",)):
        while timeout != 0 and self.pending:
            stream, text = self.pending.pop(0)
            if stream in streams:
                return text
        return None

    def clear(self):
        self.pending = []

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        while self.heard:
            line = self.heard.pop(0)
            if any(re.search(pattern, line) for pattern in patterns):
                return line
        return None

    def command(self, timeout=None):
        return self.typed.pop(0) if self.typed else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


@pytest.fixture
def script(monkeypatch, tmp_path, history):
    module = _script()

    def go(s, rooms, describe="", db=None, walk=None):
        route = MAP.path(s.room, set(rooms))
        s.room = route[-1][0] if route else s.room
        s.walks.append(s.room)
        return True

    fake = SimpleNamespace(mapdb=lambda: MAP, here=lambda s, db=None: s.room, go=go)
    module.travel = fake
    monkeypatch.setattr(haul, "travel", fake)
    module.shop = SimpleNamespace(afford=lambda *a, **k: True)
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    return module


BOARDS = {
    "Crossing": commodities.board(CROSSING_BOARD).goods,
    "Arthe Dale": ARTHE,
    "Leth Deriel": LETH,
}


def test_read_logs_the_board_where_you_stand(script):
    world = Pits(BOARDS, glued=True)
    world.args = ["read"]
    script.main(world)
    assert world.sent == ["read board"]
    assert "commodities: Crossing's board read, 34 goods logged" in world.echoed
    assert commoditylog.latest()["Crossing"][1]["diamonds"] == (1685, "Good Stores")


def test_read_outside_a_pit_says_so(script):
    world = Pits(BOARDS, room=895)
    world.args = ["read"]
    script.main(world)
    assert world.echoed == ["commodities: no commodity board here ('Read what?')"]


def test_the_survey_reads_every_pit_nearest_first(script):
    world = Pits(BOARDS, room=1073)
    script.main(world)
    assert world.walks == [9000, 19275, 13550]
    assert set(commoditylog.latest()) == set(commodities.PITS)


def test_a_typed_return_ends_the_survey_after_this_pit(script):
    world = Pits(BOARDS, room=1073)
    world.typed = ["return"]
    script.main(world)
    assert world.walks == [9000]
    assert "commodities: done at Arthe Dale" in world.echoed


def test_plan_reads_the_logged_boards_and_sends_nothing(script):
    for town, goods in BOARDS.items():
        commoditylog.log_board("Lanival", commodities.Board(town, goods))
    world = Pits(BOARDS)
    world.args = ["plan"]
    script.main(world)
    assert world.sent == []
    assert world.echoed[0].startswith(
        "commodities: 29 diamonds from Crossing to Arthe Dale: about"
    )


SALE = {
    "order": [
        ORDERED.replace("84250", "48865")
        .replace("2712", "1564")
        .replace("86962", "50429")
    ],
    "sell": [SOLD.replace("96950", "56231")],
}


def test_a_trade_buys_here_walks_the_animal_and_sells_at_the_buyer(script):
    for town in ("Arthe Dale", "Leth Deriel"):
        commoditylog.log_board("Lanival", commodities.Board(town, BOARDS[town]))
    world = Pits(BOARDS, SALE)
    world.args = ["trade"]
    script.main(world)
    sent = world.sent
    assert sent[:2] == ["read board", "order 29 diamonds"]
    # Out to the auroch at Commerce Avenue, then room by room with it.
    assert sent[sent.index("order 29 diamonds") + 1 :] == [
        "recall caravan",
        "recall caravan",
        "tell lumbering auroch to follow",
        "west",
        "west",
        "tell lumbering auroch to wait",
        "read board",
        "sell 29 diamonds",
    ]
    assert world.walks[-3:] == [895, 9000, 8999]
    out = "\n".join(world.echoed)
    assert "commodities: bought 29 diamonds for 48,865 and a cut of 1,564" in out
    assert "commodities: sold 29 diamonds at Arthe Dale for 56,231 — 5,802" in out
    assert commoditylog.open_trade("Lanival") is None


def test_a_trade_stopped_on_the_road_is_carried_on_beside_the_animal(script):
    commoditylog.log_buy(
        "Lanival", "diamonds", 29, "Crossing", 48865, 1564, "Arthe Dale"
    )
    world = Pits(BOARDS, SALE, room=1072)
    world.animal = 1072
    world.args = ["trade"]
    script.main(world)
    assert "order 29 diamonds" not in world.sent
    assert world.sent[:3] == [
        "recall caravan",
        "tell lumbering auroch to follow",
        "west",
    ]
    assert world.sent[-1] == "sell 29 diamonds"
    assert commoditylog.open_trade("Lanival") is None


def test_a_buyer_now_in_surplus_keeps_the_goods_on_the_animal(script):
    commoditylog.log_buy(
        "Lanival", "diamonds", 29, "Crossing", 48865, 1564, "Arthe Dale"
    )
    boards = dict(BOARDS, **{"Arthe Dale": dict(ARTHE, diamonds=(1939, "Surplus!"))})
    world = Pits(boards, SALE, room=1073)
    world.animal = 1073
    world.args = ["trade"]
    script.main(world)
    assert not any(command.startswith("sell") for command in world.sent)
    assert any("reads diamonds 1939 Surplus!" in line for line in world.echoed)
    assert commoditylog.open_trade("Lanival") is not None


def test_no_trade_without_another_pits_board(script):
    world = Pits(BOARDS, SALE)
    world.args = ["trade"]
    script.main(world)
    assert world.sent == ["read board"]
    assert world.echoed[-1].startswith(
        "commodities: nothing at Crossing worth carrying"
    )


def test_an_animal_not_at_the_outpost_is_said_and_the_trade_kept(script):
    commoditylog.log_board("Lanival", commodities.Board("Arthe Dale", ARTHE))
    world = Pits(BOARDS, SALE)
    world.args = ["trade"]
    world.answer = lambda command, real=world.answer: (
        "You don't recall having a caravan.\n"
        if command == "recall caravan"
        else real(command)
    )
    script.main(world)
    assert world.echoed[-1].startswith(
        "commodities: your pack animal is not beside you"
    )
    assert commoditylog.open_trade("Lanival")[1:3] == ("diamonds", 29)
