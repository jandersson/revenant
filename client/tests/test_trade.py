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

from client.game import money, trade, tradelog
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
BOX_EMPTY = "You rummage through a storage box but there is nothing in there.\n"
RETURNED = (
    "\"Ah, Lanival, good to see you're still in one piece after your travels."
    "  Let's see, now, everything appears to be in order with your caravan, so"
    " you're free to go now.  If you have any dues outstanding, though, you might"
    " want to take care of them while you're here.\"  As the clerk makes note of"
    " your return, another worker goes outside to retrieve your caravan.\n"
)


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
    assert trade.town("Leth Deriel") == "Leth Deriel"  # by the ferry
    assert trade.town("Riverhaven") is None  # another province
    assert trade.lead_name("Leth Deriel") == "leth"
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


def _ferry(bank):
    return (
        ";e if Script.exists?('bescort'); start_script('bescort', ['ferry', '"
        + bank
        + "']); wait_while{ running?('bescort') }; else; echo 'ESCORT REQUIRED"
        " DOWNLOAD IT FROM THE REPO'; start_script ('escort'); wait_while{"
        " running?('escort') }; end"
    )


MAP = MapDB(
    [
        {"id": 895, "uid": [10155], "title": ["[The Crossing, Commerce Avenue]"],
         "wayto": {"8916": "go doors", "1900": "go bank", "957": "go pier"}},
        {"id": 957, "uid": [10400], "title": ["[The Crossing, Alfren's Ferry]"],
         "wayto": {"1904": _ferry("leth"), "895": "go square"}},
        {"id": 1904, "uid": [241003],
         "title": ["[Southern Trade Route, Segoltha South Bank]"],
         "wayto": {"957": _ferry("crossing")}},
        {"id": 2039, "uid": [175001], "title": ["[Leth Deriel, Oakenheart Circle]"],
         "wayto": {"9004": "go mean-looking shanty"}},
        {"id": 9004, "uid": [175100], "title": ["[Eshar's Trading Post, Main Room]"],
         "wayto": {"2039": "out"}},
        {"id": 1900, "uid": [10200], "title": ["[Provincial Bank, Teller]"],
         "wayto": {"895": "out"}, "tags": ["bank"]},
        {"id": 8916, "uid": [13047], "title": ["[Traders' Guild, Shipment Center]"],
         "wayto": {"895": "out", "8915": "north"}},
        {"id": 8915, "uid": [13046], "title": ["[Traders' Guild, Hall of Records]"],
         "wayto": {"8916": "south"}},
        {"id": 1533, "uid": [152008], "title": ["[Wolf Clan Home, Dirt Road]"],
         "wayto": {"8997": "go guild outpost", "1534": "west"}},
        {"id": 1534, "uid": [152009], "title": ["[Wolf Clan Home, Dirt Road]"],
         "wayto": {"1533": "east"}},
        {"id": 8191, "uid": [130001], "title": ["[Brickwell Tower, Courtyard]"],
         "wayto": {"8193": "go arch"}},
        {"id": 8193, "uid": [130003], "title": ["[Brickwell Tower, Dispatch]"],
         "wayto": {"8191": "out", "8197": "east"}},
        {"id": 8197, "uid": [130007], "title": ["[Brickwell Tower, Trade Minister]"],
         "wayto": {"8193": "west"}},
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
        self.purse = 0  # copper Kronars, as WEALTH reads them
        self.ran = []
        # Where each LEAD TO lands, and where GO DOCK steps off the ferry.
        self.leads = {"wolf clan": 1533, "crossing": 895, "leth": 2039}
        self.landing = None
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
            self.room = self.leads.get(command.split(" to lead to ")[1], 1533)
            if self.return_after_lead:
                self.typed.append("return")
        elif command in ("east", "west", "go pier", "go square", "go dock"):
            self.room = {
                "east": 1533,
                "west": 1534,
                "go pier": 957,
                "go square": 895,
                "go dock": self.landing,
            }[command]
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

    def run(self, name, args=()):
        self.ran.append((name, list(args)))
        return True

    def is_running(self, name):
        return False

    def kill(self, name):
        pass

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

    def ride_ferry(s, bank=""):
        s.sent.append(f"(the ferry to {bank})")
        s.landing = 1904 if bank == "leth" else 957
        return "landed"

    module.walker = SimpleNamespace(ride_ferry=ride_ferry)
    module.money = SimpleNamespace(
        carried=lambda s, currency="Kronars", ask=None: s.purse, phrase=money.phrase
    )
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
    "rummage in storage box": [BOX_EMPTY],
    "return caravan": [RETURNED],
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
    # Then out to the caravan's box, and back to the clerk to return it.
    assert world.walks == [8915, 8916, 895, 8997, 1533, 8997]
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
    far = CONTRACT.replace("Wolf Clan", "Riverhaven")
    answers = dict(LEG, **{"read my contract": ["What were you referring to?", far]})
    world = World(answers)
    script.main(world)
    assert not any(" to lead to " in c for c in world.sent)
    assert any("Riverhaven, which ;trade does not lead to" in e for e in world.echoed)


NO_CARAVAN = "You don't recall having a caravan.\n"
RENTED = (
    "The clerk nods and says, \"All right, that's a 400 Kronars fee for a"
    ' rental...."\n'
    "You count out your 400 Kronars and pay the clerk, who sends his assistant"
    " out to get your transportation together.\n"
)
RENT_SHORT = (
    "The clerk nods and says, \"All right, that's a 400 Kronars fee for a"
    ' rental...."\n'
    "You attempt to pay the clerk, but you don't have enough money.  After"
    " haggling with the clerk for several moments, he finally shrugs at you and"
    ' says, "Sorry, can\'t put it in your dues.  Ya gotta pay up front."\n'
)


def test_with_no_caravan_one_is_rented_at_the_clerk_and_the_run_goes_on(script):
    # The operator, 2026-10-15: "when ;trade starts without a caravan,
    # have it RENT CARAVAN at the nearest outpost's clerk".
    answers = dict(
        LEG, **{"recall caravan": [NO_CARAVAN, RECALLED], "rent caravan": [RENTED]}
    )
    world = World(answers, return_after_lead=True)
    script.main(world)
    assert world.sent[:3] == ["recall caravan", "rent caravan", "recall caravan"]
    assert "trade: rented a caravan at Crossing for 400 Kronars" in world.echoed
    assert "tell bullock-drawn caravan to lead to wolf clan" in world.sent


def test_return_with_no_caravan_rents_nothing(script):
    world = World({"recall caravan": [NO_CARAVAN]})
    world.args = ["return"]
    script.main(world)
    assert world.sent == ["recall caravan"]
    assert world.echoed == ["trade: no caravan — nothing to deliver or return"]


def test_a_caravan_recall_cannot_place_is_not_rented_over(script):
    world = World(
        {"recall caravan": ["You don't recall where you left your caravan.\n"]}
    )
    script.main(world)
    assert world.sent == ["recall caravan"]
    assert "bring it to the outpost" in world.echoed[0]


def test_a_rental_short_of_coin_stops(script):
    answers = {"recall caravan": [NO_CARAVAN], "rent caravan": [RENT_SHORT]}
    world = World(answers)
    script.main(world)
    assert world.sent == ["recall caravan", "rent caravan"]
    assert "trade: not enough coin for the caravan's 400 Kronars" in world.echoed


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


TO_CROSSING = LOADED_CONTRACT.replace("Wolf Clan", "Crossing").replace(
    "Issued by:  Crossing", "Issued by:  Wolf Clan"
)


def test_a_delivery_near_a_teller_banks_the_pay_and_keeps_the_reserve(script):
    # The operator, 2026-10-15: "a banking run when it finishes a contract
    # near a bank - but keep a reasonable sum for expenses".
    answers = dict(
        LEG,
        **{"read my contract": [TO_CROSSING], "give my contract to clerk": [DELIVERED]},
    )
    world = World(answers)
    world.args = ["return"]
    world.purse = 31_000
    script.main(world)
    assert world.ran == [("bank", [f"keep={script.KEEP}", "back"])]
    out = "\n".join(world.echoed)
    assert "trade: Crossing paid 11,791 Kronars" in out
    assert out.index("dues are settled") < out.index("banking the pay")
    assert out.index("banking the pay") < out.index("nothing held — done at Crossing")


def test_no_bank_run_with_no_more_than_the_reserve_on_hand(script):
    world = World({})
    world.purse = script.KEEP
    script.bank_run(world, MAP)
    assert world.ran == []


def test_no_bank_run_far_from_a_teller(script):
    world = World({}, room=8997)  # Wolf Clan: no teller within reach
    world.purse = 50_000
    script.bank_run(world, MAP)
    assert world.ran == []
    script.BANK_ROOMS = 0  # the Crossing's teller is two rooms off
    world.room = 8916
    script.bank_run(world, MAP)
    assert world.ran == []


def test_the_graceful_end_returns_the_caravan_once_its_box_is_empty(script):
    # The operator, 2026-10-15: "return the caravan on the next stop -
    # then build it in to the script". Captured at Stone Clan that night.
    world = World(LEG)
    world.args = ["return"]
    script.main(world)
    sent = world.sent
    tail = [c for c in sent if "storage box" in c or c == "return caravan"]
    assert tail == [
        "open storage box on bullock-drawn caravan",
        "rummage in storage box on bullock-drawn caravan",
        "close storage box on bullock-drawn caravan",
        "return caravan",
    ]
    assert world.walks == [895, 8916]  # the box at the outpost, then the clerk
    assert "trade: the caravan returned at Crossing" in world.echoed


def test_a_caravan_with_anything_in_its_box_is_kept(script):
    answers = dict(
        LEG,
        **{
            "rummage in storage box": [
                "You rummage through a storage box and see a fur packing crate.\n"
            ]
        },
    )
    world = World(answers)
    world.args = ["return"]
    script.main(world)
    assert "return caravan" not in world.sent
    assert any("the caravan is kept" in e for e in world.echoed)


FOLLOWED = (
    "You pass on the order to follow to your driver, who makes sure your"
    " weathered caravan does your bidding.\n"
)
LED = (
    "You pass on the order to lead to your driver, who makes sure your"
    " weathered caravan does your bidding.\n"
)
CROSSING_ANSWERS = {
    "tell weathered caravan to follow": [FOLLOWED],
    "tell weathered caravan to lead": [LED],
}


def test_the_ferry_is_a_step_the_walker_rides():
    # Alfren's Ferry is a scripted edge: ridden, not refused (2026-10-15).
    script = _script()
    route = MAP.path(895, [1904])
    assert script.steps(route) == [["go pier"], (script.FERRY, "leth")]


def test_a_leg_to_leth_deriel_goes_by_the_crossing_and_the_ferry(script):
    # Captured by hand on 2026-10-15: led to the Crossing, walked onto
    # Alfren's Ferry with the caravan following aboard and off, then
    # LEAD TO LETH from the south bank.
    world = World(CROSSING_ANSWERS, room=1533)
    assert script.leg(world, MAP, "weathered caravan", "Wolf Clan", "Leth Deriel")
    assert [c for c in world.sent if c.startswith(("tell", "go ", "(the"))] == [
        "tell weathered caravan to lead to crossing",
        "tell weathered caravan to follow",
        "go pier",
        "(the ferry to leth)",
        "go dock",
        "tell weathered caravan to wait",
        "tell weathered caravan to lead to leth",
    ]
    assert world.room == 2039


def test_a_leg_from_leth_deriel_crosses_back_by_the_ferry(script):
    # trade.lic's do_lead_from: led toward the Crossing — here to the
    # south bank — then walked over the ferry to the Crossing's outpost.
    world = World(CROSSING_ANSWERS, room=2039)
    world.leads["crossing"] = 1904
    world.leads["arthe dale"] = 1073
    assert script.leg(world, MAP, "weathered caravan", "Leth Deriel", "Arthe Dale")
    assert [c for c in world.sent if c.startswith(("tell", "go ", "(the"))] == [
        "tell weathered caravan to lead to crossing",
        "tell weathered caravan to follow",
        "(the ferry to crossing)",
        "go dock",
        "go square",
        "tell weathered caravan to wait",
        "tell weathered caravan to lead to arthe dale",
    ]
    assert world.room == 1073


FOUND_GRASS = "You manage to find some grass.\n"
PUT_GRASS = "You put your grass in your tan canvas feedbag.\n"
NO_HAND = (
    "You really need to have at least one hand free to properly collect something.\n"
)


class Slow(World):
    """A lead whose arrival comes after `quiet` empty waits."""

    def __init__(self, answers, quiet=2, **kwargs):
        super().__init__(answers, **kwargs)
        self.quiet = quiet

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        if self.quiet:
            self.quiet -= 1
            return None
        return super().waitfor(*patterns, timeout=timeout, streams=streams)


GRASS_ANSWERS = {
    "tell weathered caravan to lead": [LED],
    "forage grass": [FOUND_GRASS],
    "put my grass": [PUT_GRASS],
}


def test_grass_is_foraged_while_led_below_the_top_up(script):
    # The operator, 2026-10-15: "Lets add top up logic" — a led
    # character follows through the forage's roundtime (Elanthipedia:
    # Trader, caravan drivers), trade.lic's forage_grass on a lead.
    world = Slow(GRASS_ANSWERS, quiet=2, room=1533)
    grass = [10]
    assert script.lead(world, "weathered caravan", "Wolf Clan", grass)
    assert world.sent.count("forage grass") == 2
    assert world.sent.count("put my grass in my feedbag") == 2
    assert grass == [12]


def test_no_forage_at_the_top_up(script):
    world = Slow(GRASS_ANSWERS, quiet=2, room=1533)
    assert script.lead(world, "weathered caravan", "Wolf Clan", [script.GRASS_TOP])
    assert "forage grass" not in world.sent


def test_an_arrival_inside_a_forage_answer_ends_the_lead(script):
    # ask() clears the queue: the arrival read in the forage's own answer.
    answers = dict(GRASS_ANSWERS, **{"forage grass": [FOUND_GRASS + ARRIVED]})
    world = Slow(answers, quiet=5, room=1533)
    assert script.lead(world, "weathered caravan", "Wolf Clan", [10])
    assert world.sent.count("forage grass") == 1


def test_a_forage_the_hands_refuse_is_not_tried_again_on_that_lead(script):
    answers = dict(GRASS_ANSWERS, **{"forage grass": [NO_HAND]})
    world = Slow(answers, quiet=3, room=1533)
    grass = [10]
    assert script.lead(world, "weathered caravan", "Wolf Clan", grass)
    assert world.sent.count("forage grass") == 1
    assert grass == [None]


def test_the_feeding_reads_fed_not_hungry_and_unknown(script):
    feeding = {
        "look in my feedbag": [FEEDBAG],
        "remove my feedbag": ["You remove a tan canvas feedbag from your belt.\n"],
    }
    fed = World(dict(feeding, **{"give weathered caravan": [FED]}))
    assert script.feed(fed, "weathered caravan") == 6  # seven, one eaten
    not_hungry = (
        "You offer the tan canvas feedbag to the caravan driver.  He calls"
        ' over to you, "Nope, they are all set for now."\n'
    )
    full = World(dict(feeding, **{"give weathered caravan": [not_hungry]}))
    assert script.feed(full, "weathered caravan") == 7
    odd = World(dict(feeding, **{"give weathered caravan": ["The driver frowns.\n"]}))
    assert script.feed(odd, "weathered caravan") is None
    assert any("the feeding" in e for e in odd.echoed)


def test_ilithi_trades_in_dokoras_and_leads_to_darkling():
    # The operator, 2026-10-15: "Lets ;trade in Ilithi" (Elanthipedia:
    # Trade Route, Ilithi; trade.lic's "darkling").
    assert trade.coin("Shard") == "Dokoras"
    assert trade.coin("Crossing") == "Kronars"
    assert trade.town("Fayrin's Rest") == "Fayrin's Rest"
    assert trade.lead_name("Darkling Wood") == "darkling"


def test_a_caravan_rented_in_shard_is_paid_in_dokoras(script):
    afforded = []
    script.shop = SimpleNamespace(
        afford=lambda s, ask, prefix, copper, currency="Kronars", **k: (
            afforded.append((copper, currency)) or True
        )
    )
    world = World(
        {"recall caravan": [NO_CARAVAN], "rent caravan": [RENT_SHORT]}, room=8193
    )
    script.main(world)
    assert afforded == [(400, "Dokoras")]
    assert "trade: not enough coin for the caravan's 400 Dokoras" in world.echoed


def test_a_contract_its_town_word_does_not_name_is_got_plainly(script):
    # "Fayrin's Rest contract": GET MY FAYRIN'S CONTRACT may not parse.
    world = World(
        {
            "get my fayrin's contract": ["What were you referring to?\n"],
            "get my contract": ["You get a Fayrin's Rest contract.\n"],
            "give my contract to clerk": [DELIVERED],
        },
        room=19278,
    )
    script.travel.go = lambda s, rooms, describe="", db=None, walk=None: True
    assert script.deliver(world, MAP, "Fayrin's Rest")
    assert world.sent[:2] == ["get my fayrin's contract", "get my contract"]
