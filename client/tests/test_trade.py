"""Caravan contracts — these tests are the manual (#552). ;trade pays the
dues, takes the minister's contract, has the clerk load it, feeds the
caravan, tells it to LEAD TO the contract's town, follows, and hands
the contract in for the pay; every contract is a row in history.db.
The answers are a Crossing → Wolf Clan run's, captured 2026-10-15
(client/game/trade.py, client/game/tradelog.py, scripts/trade.py).
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game import trade, tradelog
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]

CONTRACT = (
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
    " Trading Contract Issued by:  Crossing\n"
    " The guild office at Wolf Clan requires 13 ornate saber hilts,\n"
    " to be delivered within about 4 anlaen.\n"
    " The bearer of the goods and this contract will receive,\n"
    " upon safe and timely delivery of the merchandise, a payment\n"
    " in the form of the local currency.\n"
    " This contract has yet to be presented to the Crossing guild\n"
    " clerk.\n"
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
    "You estimate these goods are currently worth 11791 Kronars on delivery.\n"
)
LOADED_CONTRACT = CONTRACT.replace(
    " This contract has yet to be presented to the Crossing guild\n clerk.\n", ""
)
ISSUED = (
    "The minister plucks a contract from the hands of a passing clerk and hands it"
    ' to you.  "Here we go," she says, "We have charged you the wholesale price of'
    " 3537 Kronars for the goods, the receiving guild will pay you full price!"
    "  Therein lies profit!  Also I will charge you 985 in dues which are owed to"
    ' this guild, for a total of 4522."  The minister then nods and adds, "Good'
    ' luck, Lanival."\n'
)
DUES_OWED = (
    "The minister reminds you that you still owe 2375 Kronars in dues to The"
    " Crossing and asks that you pay the clerk before she issues you a new"
    " contract.\n"
)
SETTLED = "You count out some coins, and the clerk notes that your dues are settled.\n"
NO_DUES = 'The clerk says, "You do not owe dues, Lanival!"\n'
LOADED = (
    'The shipment clerk accepts your contract and peruses it.  "Okay," the clerk'
    " says.  \"Let's see... that's 13 ornate saber hilts, with a total weight"
    ' of...65 pounds!"\n'
    'The clerk adds, "Do not forget to feed your bullock-drawn caravan.  Guild'
    ' requirements."\n'
    "After a bit of discussion, a pair of assistants carefully lift the crate and"
    " carry it out the door, heading in the direction of your bullock-drawn"
    " caravan.\n"
    'The clerk says, "Okay...total fee for transportation additions is 50 copper'
    ' Kronars."\n'
    '"Good luck!" the clerk says, grinning, and goes back to work.\n'
)
DELIVERED = (
    'The shipment clerk accepts your contract and peruses it.  "Ah, yes," he'
    ' smiles.  "We did order this, didn\'t we?"  With a quick snap of his fingers,'
    " he calls for an assistant to help you unload your merchandise for his"
    " inspection.\n"
    "The shipment clerk carefully looks through the inventory which his assistant"
    " has placed on a counter.\n"
    "The shipment clerk finds everything in order with your merchandise."
    '  "You\'re a good Trader, Lanival." he says, handing you your payment of'
    " 11791 Kronars.\n"
)
RECALLED = (
    "You recall that your bullock-drawn caravan should be located in...\n"
    "[The Crossing, Commerce Avenue]\n"
)
FEEDBAG = (
    "In the tan canvas feedbag you see some grass, some grass, some grass, some"
    " grass, some grass, some grass and some grass.\n"
)
FED = (
    "The driver takes the feedbag from you and begins feeding the caravan.  The"
    ' driver hands back the feedbag and says, "They are well fed now sir."\n'
)
LEADING = (
    "The driver of your bullock-drawn caravan acknowledges the order to lead to"
    " Wolf Clan.\n"
    "You pass on the order to lead to your driver, who makes sure your"
    " bullock-drawn caravan does your bidding.\n"
)
ARRIVED = (
    "The bullock-drawn caravan stops and waits, having arrived at its destination.\n"
)
GOT_CONTRACT = "You get a Wolf Clan contract from inside your sturdy backpack.\n"
STOWED = "You put your contract in your sturdy backpack.\n"


# The model


def test_a_contract_is_read_for_its_towns_goods_and_worth():
    contract = trade.contract(CONTRACT)
    assert contract.origin == "Crossing"
    assert contract.destination == "Wolf Clan"
    assert contract.goods == "13 ornate saber hilts"
    assert (contract.worth, contract.currency) == (11791, "Kronars")
    assert contract.presented is False
    assert trade.contract(LOADED_CONTRACT).presented is True
    assert trade.contract("What were you referring to?") is None


def test_a_contract_read_without_its_line_breaks_keeps_its_origin():
    # Live, 2026-10-15: the familiar stream's lines came without breaks,
    # the origin ran on into the next line, and a contract issued and
    # never loaded was led off unloaded.
    contract = trade.contract(CONTRACT.replace("\n", ""))
    assert contract.origin == "Crossing"
    assert (contract.destination, contract.goods) == (
        "Wolf Clan",
        "13 ornate saber hilts",
    )
    assert contract.presented is False


def test_a_lead_is_taken_with_or_without_the_drivers_acknowledgement():
    # To Arthe Dale the driver says only the second line (2026-10-15).
    alone = (
        "You pass on the order to lead to your driver, who makes sure your"
        " bullock-drawn caravan does your bidding.\n"
    )
    assert trade.LEADING in LEADING and trade.LEADING in alone


def test_the_minister_issues_asks_for_dues_or_says_one_is_held():
    assert trade.minister(ISSUED) == ("issued", (3537, 985))
    assert trade.minister(DUES_OWED) == ("dues", 2375)
    assert trade.minister("You still have another contract from here.") == (
        "held",
        None,
    )
    assert trade.minister("The minister ignores you.") == (None, None)


def test_the_clerk_loads_at_the_issue_and_pays_at_the_destination():
    # Both open "The shipment clerk accepts your contract".
    assert trade.clerk(LOADED) == ("loaded", 50)
    assert trade.clerk(DELIVERED) == ("paid", (11791, "Kronars"))
    assert trade.clerk("What have you done with the goods?") == ("no goods", None)


def test_recall_names_the_caravan_and_whether_it_is_here():
    assert trade.caravan(RECALLED) == ("bullock-drawn caravan", False)
    # Nearby, a direction instead of a room (Arthe Dale's clerk, 2026-10-15).
    assert trade.caravan(
        "You seem to recall your bullock-drawn caravan should be somewhere to the east."
    ) == ("bullock-drawn caravan", False)
    assert trade.caravan(
        "You seem to recall that you left your bullock-drawn caravan right behind you."
    ) == ("bullock-drawn caravan", True)
    assert trade.caravan("You don't recall having a caravan.") == (None, False)


def test_the_feedbag_counts_its_grass():
    assert trade.grass(FEEDBAG) == 7
    assert trade.grass("There is nothing in there.") == 0


def test_towns_are_named_the_way_the_table_keys_them():
    assert trade.town("The Crossing") == "Crossing"
    assert trade.town("Wolf Clan") == "Wolf Clan"
    assert trade.town("Leth Deriel") is None  # a ferry away
    assert trade.contract_noun("Wolf Clan") == "wolf contract"


# The log


def test_a_contract_is_logged_from_issue_to_pay(tmp_path):
    db = tmp_path / "history.db"
    contract = trade.contract(CONTRACT)
    seq = tradelog.log_issue("Lanival", "Crossing", contract, 3537, 985, path=db)
    tradelog.log_fee(seq, 50, path=db)
    tradelog.log_delivery("Lanival", "Wolf Clan", 11791, path=db)
    (route,) = tradelog.summary("Lanival", path=db)
    assert route["origin"] == "Crossing" and route["destination"] == "Wolf Clan"
    assert (route["contracts"], route["delivered"]) == (1, 1)
    assert route["paid"] == 11791
    assert route["profit"] == 11791 - 3537 - 985 - 50
    assert route["minutes"] is not None
    assert tradelog.describe(route).startswith(
        "Crossing → Wolf Clan: 1 contract, 1 delivered, paid 11,791, profit 7,219"
    )


def test_a_delivery_pays_the_oldest_open_contract_for_that_town(tmp_path):
    db = tmp_path / "history.db"
    contract = trade.contract(CONTRACT)
    first = tradelog.log_issue("Lanival", "Crossing", contract, 3537, 985, path=db)
    tradelog.log_issue("Lanival", "Crossing", contract, 3000, 900, path=db)
    tradelog.log_delivery("Lanival", "Wolf Clan", 11791, path=db)
    (route,) = tradelog.summary("Lanival", path=db)
    assert (route["contracts"], route["delivered"]) == (2, 1)
    assert route["profit"] == 11791 - 3537 - 985  # the first one's charges
    assert first == 1
    assert tradelog.summary("Sable", path=db) == []


# The script


def _script():
    spec = importlib.util.spec_from_file_location(
        "trade_script", REPO / "scripts/trade.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MAP = MapDB(
    [
        {"id": 895, "uid": [10155], "title": ["[The Crossing, Commerce Avenue]"],
         "wayto": {"8916": "go doors"}},
        {"id": 8916, "uid": [13047], "title": ["[Traders' Guild, Shipment Center]"],
         "wayto": {"895": "out", "8915": "north"}},
        {"id": 8915, "uid": [13046], "title": ["[Traders' Guild, Hall of Records]"],
         "wayto": {"8916": "south"}},
        {"id": 1533, "uid": [152008], "title": ["[Wolf Clan Home, Dirt Road]"],
         "wayto": {"8997": "go guild outpost", "1534": "west"}},
        {"id": 1534, "uid": [152009], "title": ["[Wolf Clan Home, Dirt Road]"],
         "wayto": {"1533": "east"}},
        {"id": 8997, "uid": [152101], "title": ["[Wolf Clan Trader Outpost]"],
         "wayto": {"1533": "out"}},
    ]
)  # fmt: skip

CONTRACT_HELD = {"exist": "194592295", "noun": "contract", "name": "Wolf Clan contract"}
FEEDBAG_HELD = {"exist": "5001", "noun": "feedbag", "name": "tan canvas feedbag"}


class World:
    """The handle: answers by command prefix, rooms moved by the walks,
    the lead and a followed step; `heard` are lines that come after an
    answer (the caravan's arrival, its following), read by waitfor."""

    def __init__(self, answers, room=8916, return_after_lead=False):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.return_after_lead = return_after_lead
        self.sent, self.echoed, self.walks, self.heard = [], [], [], []
        self.pending = []
        self.typed = []
        self.dead = False
        self.args = []
        self.room = room
        self.state = SimpleNamespace(
            name="Lanival", right_hand=None, left_hand=None, hostiles={}
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        if command == "ask minister for contract" or command.startswith("get my wolf"):
            self.state.right_hand = dict(CONTRACT_HELD)
        elif command.startswith("give my contract"):
            self.state.right_hand = None
        elif command == "remove my feedbag":
            self.state.right_hand = dict(FEEDBAG_HELD)
        elif command.startswith(("stow", "wear")):
            self.state.right_hand = None
        elif " to lead to " in command:
            self.heard.append(ARRIVED)
            self.room = 1533
            if self.return_after_lead:
                self.typed.append("return")
        elif command in ("east", "west"):
            self.room = {"east": 1533, "west": 1534}[command]
            self.heard.append("Your bullock-drawn caravan, following you, arrives.\n")
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else "")
                # READ's contract comes on the familiar stream, as live.
                stream = "familiar" if trade.READ_END in text else ""
                self.pending = [(stream, line + "\n") for line in text.splitlines()]
                return

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
            if any(pattern in line for pattern in patterns):
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
def script(monkeypatch, tmp_path):
    module = _script()

    def go(s, rooms, describe="", db=None, walk=None):
        s.walks.append(min(rooms))
        s.room = min(rooms)
        return True

    module.travel = SimpleNamespace(
        mapdb=lambda: MAP, here=lambda s, db=None: s.room, go=go
    )
    module.shop = SimpleNamespace(afford=lambda *a, **k: True)
    monkeypatch.setattr(
        tradelog, "_connect", _in(tmp_path / "history.db", tradelog._connect)
    )
    return module


def _in(path, connect):
    return lambda _path: connect(path)


LEG = {
    "recall caravan": [RECALLED],
    "read my contract": ["What were you referring to?", CONTRACT, LOADED_CONTRACT],
    "pay clerk": [SETTLED, NO_DUES],
    "ask minister": [ISSUED],
    "give my contract to clerk": [LOADED, DELIVERED],
    "stow": [STOWED],
    "look in my feedbag": [FEEDBAG],
    "remove my feedbag": ["You remove a tan canvas feedbag from your belt.\n"],
    "give bullock-drawn caravan": [FED],
    "wear my feedbag": ["You attach a tan canvas feedbag to your belt.\n"],
    "tell bullock-drawn caravan to lead": [LEADING],
    "get my wolf contract": [GOT_CONTRACT],
}


def test_a_leg_takes_a_contract_leads_the_caravan_and_is_paid(script):
    # Typed "return" during the lead: the leg is finished, no next contract.
    world = World(LEG, return_after_lead=True)
    script.main(world)
    out = "\n".join(world.echoed)
    sent = world.sent
    assert sent[:2] == ["recall caravan", "read my contract"]
    assert sent.index("pay clerk") < sent.index("ask minister for contract")
    assert sent.index("ask minister for contract") < sent.index(
        "give my contract to clerk"
    )
    assert "give bullock-drawn caravan" in sent
    assert "tell bullock-drawn caravan to lead to wolf clan" in sent
    assert "get my wolf contract" in sent
    assert world.walks == [8915, 8916, 895, 8997]
    assert "trade: 13 ornate saber hilts for Wolf Clan, worth 11791 on delivery" in out
    assert "trade: leading to Wolf Clan" in out
    assert "trade: Wolf Clan paid 11,791 Kronars" in out
    assert "trade: nothing held — done at Wolf Clan" in out
    (route,) = tradelog.summary("Lanival")
    assert route["delivered"] == 1 and route["profit"] == 11791 - 3537 - 985 - 50


def test_dues_owed_are_paid_before_the_contract(script):
    answers = dict(LEG, **{"ask minister": [DUES_OWED, ISSUED]})
    world = World(answers, return_after_lead=True)
    script.main(world)
    out = "\n".join(world.echoed)
    assert "trade: 2,375 Kronars of dues owed to Crossing — paying them" in out
    asks = [i for i, c in enumerate(world.sent) if c == "ask minister for contract"]
    pays = [i for i, c in enumerate(world.sent) if c == "pay clerk"]
    assert len(asks) == 2 and asks[0] < pays[1] < asks[1]


def test_return_with_nothing_held_stops_at_the_clerk(script):
    world = World(LEG)
    world.args = ["return"]
    script.main(world)
    assert "ask minister for contract" not in world.sent
    assert "trade: nothing held — done at Crossing" in world.echoed


def test_a_contract_for_a_town_it_cannot_lead_to_is_left_with_you(script):
    leth = CONTRACT.replace("Wolf Clan", "Leth Deriel")
    answers = dict(LEG, **{"read my contract": ["What were you referring to?", leth]})
    world = World(answers)
    script.main(world)
    assert not any(" to lead to " in c for c in world.sent)
    assert any("Leth Deriel, which ;trade does not lead to" in e for e in world.echoed)


def test_no_caravan_no_trade(script):
    world = World({"recall caravan": ["You don't recall having a caravan.\n"]})
    script.main(world)
    assert world.sent == ["recall caravan"]
    assert "RENT CARAVAN" in world.echoed[0]


def test_an_empty_feedbag_stops_before_the_lead(script):
    answers = dict(LEG, **{"look in my feedbag": ["There is nothing in there.\n"]})
    world = World(answers)
    script.main(world)
    assert not any(" to lead to " in c for c in world.sent)
    assert any("no grass in your feedbag" in e for e in world.echoed)


def test_the_contract_is_read_off_the_familiar_stream(script):
    # The first live run (2026-10-15) read nothing: READ pushes the
    # contract to <pushStream id="familiar">, which ask() does not read.
    world = World({"read my contract": [CONTRACT]})
    contract = script.held(world)
    assert contract.destination == "Wolf Clan"
    assert world.sent == ["read my contract"]


def test_a_contract_issued_and_never_loaded_is_loaded_and_led(script):
    # The first live run stopped holding the minister's contract; the
    # next run loads it at the clerk instead of asking for another.
    answers = dict(LEG, **{"read my contract": [CONTRACT, LOADED_CONTRACT]})
    world = World(answers, return_after_lead=True)
    script.main(world)
    assert "ask minister for contract" not in world.sent
    assert world.sent.index("give my contract to clerk") < world.sent.index(
        "tell bullock-drawn caravan to lead to wolf clan"
    )
    (route,) = tradelog.summary("Lanival")
    assert route["delivered"] == 1 and route["paid"] == 11791
    assert route["profit"] == 11791 - 50  # the minister's charges unknown


def test_the_caravan_is_walked_to_the_outpost_one_followed_room_at_a_time(script):
    world = World({"tell bullock-drawn caravan to follow": [
        "You pass on the order to follow to your driver, who makes sure your"
        " bullock-drawn caravan does your bidding.\n"
    ]}, room=1534)  # fmt: skip
    assert script.bring(world, MAP, "bullock-drawn caravan", 1533)
    assert world.sent == [
        "tell bullock-drawn caravan to follow",
        "east",
        "tell bullock-drawn caravan to wait",
    ]


def test_history_reads_the_log_back(script):
    contract = trade.contract(CONTRACT)
    seq = tradelog.log_issue("Lanival", "Crossing", contract, 3537, 985)
    tradelog.log_fee(seq, 50)
    tradelog.log_delivery("Lanival", "Wolf Clan", 11791)
    world = World({})
    world.args = ["history"]
    script.main(world)
    assert world.sent == []
    assert world.echoed[0].startswith("trade: Crossing → Wolf Clan: 1 contract")
