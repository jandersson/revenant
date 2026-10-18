"""Caravan contracts — these tests are the manual (#552). ;trade pays the
dues, takes the minister's contract, has the clerk load it, feeds the
caravan, tells it to LEAD TO the contract's town, follows, and hands
the contract in for the pay; every contract is a row in history.db.
The answers are a Crossing → Wolf Clan run's, captured 2026-10-15
(client/game/trade.py, client/game/tradelog.py, scripts/trade.py).
"""

import importlib.util
import pathlib
import re
from types import SimpleNamespace

import pytest

from client.game import haul, money, trade, tradelog, walker
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
# The Crossing's broker, 2026-10-15 (#554): the minister's words with
# "The broker", the charge 32,663 wholesale and 11,170 dues.
BROKER_ISSUED = (
    ISSUED.replace("The minister", "The broker")
    .replace("3537", "32663")
    .replace("985", "11170")
    .replace("4522", "43833")
)
BROKER_DUES = (
    "The broker reminds you that you still owe 4048 Kronars in dues to The"
    " Crossing and asks that you pay the clerk before she issues you a new"
    " contract.\n"
)
TO_SHARD = (
    CONTRACT.replace(
        "Wolf Clan requires 13 ornate saber hilts",
        "Shard requires 427 jars of pickled eel",
    )
    .replace("4 anlaen", "6 anlaen")
    .replace("11791 Kronars", "78568 Dokoras")
)
# The Crossing's broker, 2026-10-15 (#555): Riverhaven, paid in Lirums.
TO_RIVERHAVEN = (
    CONTRACT.replace(
        "Wolf Clan requires 13 ornate saber hilts",
        "Riverhaven requires 260 jars of pickled eel",
    )
    .replace("about 4 anlaen", "1 andu and about 6 anlaen")
    .replace("11791 Kronars", "47840 Lirums")
)
BROKER_TO_RIVERHAVEN = (
    BROKER_ISSUED.replace("32663", "17940")
    .replace("11170", "5836")
    .replace("43833", "23776")
)
# Riverhaven's broker, 2026-10-15: a contract for Shard, charged in Lirums.
FROM_RIVERHAVEN = (
    TO_SHARD.replace("Issued by:  Crossing", "Issued by:  Riverhaven")
    .replace("the Crossing guild", "the Riverhaven guild")
    .replace("78568 Dokoras", "152536 Dokoras")
)
RIVERHAVEN_BROKER = (
    BROKER_ISSUED.replace("32663 Kronars", "50729 Lirums")
    .replace("11170", "18464")
    .replace("43833", "69193")
)
PAID_IN_LIRUMS = (
    "The shipment clerk finds everything in order with your merchandise."
    '  "Life is profit!  Profit is life!" he says, handing you your payment of'
    " 47840 Lirums.\n"
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


def test_the_broker_answers_in_the_ministers_words():
    assert trade.minister(BROKER_ISSUED) == ("issued", (32663, 11170))
    assert trade.minister(BROKER_DUES) == ("dues", 4048)
    contract = trade.contract(TO_SHARD)
    assert (contract.origin, contract.destination) == ("Crossing", "Shard")
    assert (contract.worth, contract.currency) == (78568, "Dokoras")


def test_the_clerk_loads_at_the_issue_and_pays_at_the_destination():
    # Both open "The shipment clerk accepts your contract".
    assert trade.clerk(LOADED) == ("loaded", 50)
    assert trade.clerk(DELIVERED) == ("paid", (11791, "Kronars"))
    assert trade.clerk("What have you done with the goods?") == ("no goods", None)


def test_recall_names_the_caravan_and_whether_it_is_here():
    assert trade.caravan(RECALLED) == ("bullock-drawn caravan", False)
    # Three words do not GIVE: "What is it you're trying to give?" (2026-10-15).
    assert trade.caravan(
        "You recall that your polished wood caravan should be located in...\n"
    ) == ("polished caravan", False)
    # Nearby, a direction instead of a room (Arthe Dale's clerk, 2026-10-15).
    assert trade.caravan(
        "You seem to recall your bullock-drawn caravan should be somewhere to the east."
    ) == ("bullock-drawn caravan", False)
    assert trade.caravan(
        "You seem to recall that you left your bullock-drawn caravan right behind you."
    ) == ("bullock-drawn caravan", True)
    assert trade.caravan("You don't recall having a caravan.") == (None, False)


def test_riverhaven_trades_in_lirums_and_is_its_own_province():
    contract = trade.contract(TO_RIVERHAVEN)
    assert (contract.destination, contract.goods) == (
        "Riverhaven",
        "260 jars of pickled eel",
    )
    assert (contract.worth, contract.currency) == (47840, "Lirums")
    assert trade.minister(BROKER_TO_RIVERHAVEN) == ("issued", (17940, 5836))
    assert trade.clerk(PAID_IN_LIRUMS) == ("paid", (47840, "Lirums"))
    assert trade.coin("Riverhaven") == "Lirums"
    assert trade.lead_name("Riverhaven") == "riverhaven"
    assert tradelog.province("Crossing", "Riverhaven") == "Interprovince"
    assert tradelog.province("Riverhaven", "Riverhaven") == "Therengia"


def test_the_feedbag_counts_its_grass():
    assert trade.grass(FEEDBAG) == 7
    assert trade.grass("There is nothing in there.") == 0


def test_towns_are_named_the_way_the_table_keys_them():
    assert trade.town("The Crossing") == "Crossing"
    assert trade.town("Wolf Clan") == "Wolf Clan"
    assert trade.town("Leth Deriel") == "Leth Deriel"  # by the ferry
    assert trade.town("Riverhaven") == "Riverhaven"  # by Dirge and the Faldesu
    assert trade.town("Therenborough") == "Therenborough"
    assert trade.town("Hvaral") == "Hvaral"  # past Fornsted (#555)
    assert trade.town("Ratha") is None  # no caravans in Qi'Reshalia
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
    other = contract._replace(goods="14 ornate saber hilts")
    tradelog.log_issue("Lanival", "Crossing", other, 3000, 900, path=db)
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


def _ferry(bank, route="ferry"):
    return (
        ";e if Script.exists?('bescort'); start_script('bescort', ['"
        + route
        + "', '"
        + bank
        + "']); wait_while{ running?('bescort') }; else; echo 'ESCORT REQUIRED"
        " DOWNLOAD IT FROM THE REPO'; start_script ('escort'); wait_while{"
        " running?('escort') }; end"
    )


def _faldesu(bank):
    # The map's plain form at North Road, Ferry; the Marsh's `if` form is the swim.
    return (
        ";e start_script('bescort', ['faldesu', '"
        + bank
        + "']);wait_while{running?('bescort')};"
    )


# The map's Hvaral–Muspar'i sand barge and Arnshal Keep's west gate (#555).
SANDBARGE = (
    ";e start_script('bescort', ['sandbarge', 'hvaral', 'muspari']);"
    "wait_while { running? 'bescort'}"
)
PASSPORT_GATE = (
    ";e start_script('bescort', ['hvaral_passport']); wait_while{ running?('bescort') }"
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
         "wayto": {"9004": "go mean-looking shanty", "2249": "climb platform"}},
        {"id": 2249, "uid": [176001], "title": ["[Obsidian Pass, Platform]"],
         "wayto": {"2904": _ferry("south", "gondola")}},
        {"id": 2904, "uid": [176002], "title": ["[Obsidian Pass, Platform]"],
         "wayto": {"8191": "go frame"}},
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
        {"id": 1307, "uid": [51104], "title": ["[Dirge, Gateway Road]"],
         "wayto": {}},
        {"id": 1385, "uid": [1385], "title": ["[North Road, Ferry]"],
         "wayto": {"470": _faldesu("haven"), "1384": "south"}},
        {"id": 1384, "uid": [1384], "title": ["[North Road, Riverbank]"],
         "wayto": {"1385": "north"}},
        {"id": 470, "uid": [470], "title": ["[Riverhaven, Ferry Dock]"],
         "wayto": {"463": "go ramp", "1385": _faldesu("crossing")}},
        {"id": 463, "uid": [1010302], "title": ["[Riverhaven, Municipal Pier]"],
         "wayto": {"444": "go arch", "470": "go ramp"}},
        {"id": 444, "uid": [444], "title": ["[Riverhaven, Municipal Pier]"],
         "wayto": {"386": "northwest", "463": "go arch"}},
        {"id": 386, "uid": [1010007], "title": ["[Riverhaven, Town Hall Road]"],
         "wayto": {"444": "go pier", "13751": "go alley", "7876": "go trader guild"}},
        {"id": 13751, "uid": [1017007], "title": ["[Traders' Guild, Shipping Dock]"],
         "wayto": {"386": "out"}},
        {"id": 7876, "uid": [1017001],
         "title": ["[Riverhaven, Traders' Guild Lobby]"], "wayto": {"386": "out"}},
        {"id": 3155, "uid": [1029029],
         "title": ["[Therenborough, Rutilor Boulevard]"], "wayto": {"3232": "go exch"}},
        {"id": 3232, "uid": [1029032],
         "title": ["[Alliance of Exchange, Traders' Center]"], "wayto": {"3155": "out"}},
        {"id": 3766, "uid": [13766], "title": ["[Hvaral, Dry Dock]"],
         "wayto": {"6872": SANDBARGE}},
        {"id": 6872, "uid": [16872], "title": ["[Outside Muspar'i, Barge Platform]"],
         "wayto": {}},
        {"id": 3698, "uid": [13698], "title": ["[Arnshal Keep, First Floor]"],
         "wayto": {"3706": PASSPORT_GATE},
         "timeto": {"3706": ";e if Script.exists?('bescort') then 0.2 else nil end"}},
        {"id": 3706, "uid": [13706], "title": ["[Arnshal Road, Keep Entrance]"],
         "wayto": {}},
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
        self.leads = {
            "wolf clan": 1533,
            "crossing": 895,
            "leth": 2039,
            "dirge": 1307,  # Gateway Road
            "riverhaven": 1385,  # North Road, Ferry
        }
        self.landing = None
        self.state = SimpleNamespace(
            name="Lanival", right_hand=None, left_hand=None, hostiles={}
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        if command in (
            "ask minister for contract",
            "ask broker for contract",
        ) or command.startswith("get my wolf"):
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
                self.typed.append(getattr(self, "after_lead_word", "return"))
        elif command in self.moves():
            self.room = self.moves()[command]
            self.heard.append("Your bullock-drawn caravan, following you, arrives.\n")
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else "")
                # READ's contract comes on the familiar stream, as live.
                stream = "familiar" if trade.READ_END in text else ""
                self.pending = [(stream, line + "\n") for line in text.splitlines()]
                return

    def moves(self):
        """The way the map knows from this room, else the old fixed table;
        GO DOCK and OUT step off a ride where it landed."""
        wayto = MAP.rooms.get(self.room, {}).get("wayto", {})
        fixed = {
            "east": 1533,
            "west": 1534,
            "go pier": 957,
            "go square": 895,
            "go dock": self.landing,
            "climb platform": 2249,
            "go frame": 8191,
            "out": self.landing,
            "go platform": self.landing,
            "go gate": self.landing,
        }
        return {**fixed, **{way: int(room) for room, way in wayto.items()}}

    def get(self, timeout=None, streams=("",)):
        while timeout != 0 and self.pending:
            stream, text = self.pending.pop(0)
            if stream in streams:
                return text
        return None

    def clear(self):
        self.pending = []

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        while self.heard:  # regexes, as the handle's waitfor matches them
            line = self.heard.pop(0)
            if any(re.search(pattern, line) for pattern in patterns):
                return line
        return None

    # A child in `staying` runs until told `return` (or, `deaf`, until
    # killed); any other ends at once, as ;bank does here.
    staying = frozenset()
    deaf = False

    def run(self, name, args=()):
        self.ran.append((name, list(args)))
        if name in self.staying:
            self.running = getattr(self, "running", set()) | {name}
        return True

    def is_running(self, name):
        return name in getattr(self, "running", set())

    def tell(self, name, line):
        self.told = getattr(self, "told", []) + [(name, line)]
        if line == "return" and not self.deaf:
            self.running = getattr(self, "running", set()) - {name}
        return True

    def kill(self, name):
        self.killed = getattr(self, "killed", []) + [name]
        self.running = getattr(self, "running", set()) - {name}

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
        s.landing = {957: 1904, 1904: 957, 1385: 470, 470: 1385}[s.room]
        return "landed"

    def ride_gondola(s, direction="", aboard=None):
        s.sent.append(f"(the gondola {direction})")
        # Captured in the cab, 2026-10-15.
        s.heard.append(
            "Your weathered caravan entered a weathered wooden gondola, following you.\n"
        )
        s.boarded = aboard() is not None
        s.landing = 2904
        return "landed"

    module.walker = SimpleNamespace(ride_ferry=ride_ferry, ride_gondola=ride_gondola)
    # bring() walks through haul's travel and walker: the same fakes.
    monkeypatch.setattr(haul, "travel", module.travel)
    monkeypatch.setattr(haul, "walker", module.walker)
    module.money = SimpleNamespace(
        carried=lambda s, currency="Kronars", ask=None: s.purse, phrase=money.phrase
    )
    monkeypatch.setattr(
        tradelog, "_connect", _in(tmp_path / "history.db", tradelog._connect)
    )
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
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


def test_interprovince_takes_the_brokers_contract_paid_before_loading(script):
    # By hand at the Crossing, 2026-10-15: ASK BROKER FOR CONTRACT, PAY
    # CLERK for its 43,833 Kronars, then the clerk loaded it (#554).
    answers = dict(
        LEG,
        **{
            "ask broker": [BROKER_ISSUED],
            "read my contract": ["What were you referring to?", TO_SHARD],
        },
    )
    world = World(answers)
    world.args = ["interprovince"]
    afforded, legs = [], []
    script.shop = SimpleNamespace(
        afford=lambda s, ask, prefix, copper, coin, **k: (
            afforded.append((copper, coin)) or True
        )
    )

    def leg(s, db, name, origin, destination, *rest):
        legs.append((origin, destination))
        return False  # the run ends here; the leg has its own tests

    script.leg = leg
    script.main(world)
    sent = world.sent
    assert "ask minister for contract" not in sent
    pays = [i for i, c in enumerate(sent) if c == "pay clerk"]
    assert (
        sent.index("ask broker for contract")
        < pays[1]
        < sent.index("give my contract to clerk")
    )
    assert world.walks == [11995, 8916, 895]
    assert afforded == [(43833, "Kronars")]
    assert legs == [("Crossing", "Shard")]
    assert "trade: 427 jars of pickled eel for Shard, worth 78568 on delivery" in (
        world.echoed
    )


def test_a_broker_contract_beyond_the_routes_is_neither_paid_nor_loaded(script):
    far = TO_SHARD.replace("Shard requires", "Hibarnhvidar requires")
    answers = dict(
        LEG,
        **{"ask broker": [BROKER_ISSUED], "read my contract": [far]},
    )
    world = World(answers)
    contract = script.take(world, MAP, "Crossing", broker=True)
    assert (contract.destination, contract.presented) == ("Hibarnhvidar", False)
    assert "give my contract to clerk" not in world.sent
    assert world.sent[-1] == "stow my contract"  # READ's ordinals skip a held one
    assert world.sent.count("pay clerk") == 0
    assert any("43,833 Kronars owed at the clerk" in e for e in world.echoed)


def test_dues_owed_at_the_broker_are_paid_before_its_contract(script):
    world = World(dict(LEG, **{"ask broker": [BROKER_DUES, BROKER_ISSUED]}))
    assert script.issue(world, MAP, "Crossing", broker=True) == (32663, 11170)
    assert "trade: 4,048 Kronars of dues owed to Crossing — paying them" in (
        world.echoed
    )
    assert world.sent == [
        "ask broker for contract",
        "pay clerk",
        "ask broker for contract",
    ]


def test_interprovince_with_no_broker_takes_the_ministers_contract(script):
    answers = dict(LEG, **{"read my contract": [CONTRACT]})
    world = World(answers, room=8997)
    assert script.take(world, MAP, "Wolf Clan", broker=True)
    assert "ask minister for contract" in world.sent
    assert "ask broker for contract" not in world.sent
    assert "pay clerk" not in world.sent


def test_return_typed_with_nothing_held_stops_at_the_clerk(script):
    world = World(LEG)
    world.typed = ["return"]
    script.main(world)
    assert "ask minister for contract" not in world.sent
    assert "trade: nothing held — done at Crossing" in world.echoed


def test_a_contract_for_a_town_it_cannot_lead_to_is_kept_and_the_run_circles(
    script,
):
    # Therenborough's minister, 2026-10-17: Muspar'i, not built then (#555).
    answers = dict(
        LEG,
        **{
            "read my contract": ["What were you referring to?", BEYOND],
            "ask minister": [THEREN_ISSUED],
        },
    )
    world = World(answers, room=3232)
    circled = []
    script.circuit = lambda s, db, name, place, beside, training: circled.append(place)
    script.main(world)
    assert not any(" to lead to " in c for c in world.sent)
    assert "give my contract to clerk" not in world.sent
    assert any("Hibarnhvidar is beyond ;trade's routes" in e for e in world.echoed)
    assert any("18,912 Lirums owed at the clerk" in e for e in world.echoed)
    assert circled == ["Therenborough"]


def test_a_contract_held_beyond_the_routes_is_never_loaded_on_a_rerun(script):
    answers = dict(LEG, **{"read my contract": [BEYOND]})
    world = World(answers, room=3232)
    circled = []
    script.circuit = lambda s, db, name, place, beside, training: circled.append(place)
    script.main(world)
    assert "give my contract to clerk" not in world.sent
    assert "ask minister for contract" not in world.sent
    assert circled == ["Therenborough"]


def test_a_broker_contract_to_riverhaven_is_paid_loaded_and_led(script):
    # The Crossing's broker, 2026-10-15: 260 jars of pickled eel for
    # Riverhaven, stopped at the routes' guard then (#555).
    answers = dict(
        LEG,
        **{
            "ask broker": [BROKER_TO_RIVERHAVEN],
            "read my contract": ["What were you referring to?", TO_RIVERHAVEN],
        },
    )
    world = World(answers)
    world.args = ["interprovince"]
    legs = []
    script.leg = lambda s, db, name, origin, to, *rest: legs.append((origin, to))
    script.main(world)
    assert world.sent.index(
        "pay clerk", world.sent.index("ask broker for contract")
    ) < (world.sent.index("give my contract to clerk"))
    assert legs == [("Crossing", "Riverhaven")]


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
    world.typed = ["return"]
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
    world.typed = ["return"]
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
    world.typed = ["return"]
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
    _script()
    route = MAP.path(895, [1904])
    assert haul.steps(route) == [["go pier"], (haul.FERRY, "leth")]


def test_the_ain_ghazal_ferry_is_a_step_the_walker_rides():
    # 2026-10-16 17:14 (#555): LEAD TO AIN GHAZAL ended at Hibarnhvidar's
    # ferry dock, and bring() said "no plain walk from here".
    ferry1 = (
        ";e start_script('bescort', ['ferry1', 'hibarnhvidar']);"
        "wait_while{running?('bescort')};"
    )
    assert haul.steps([(11027, ferry1), (11028, "north")]) == [
        (haul.FERRY, "hibarnhvidar"),
        ["north"],
    ]


def test_a_leg_to_leth_deriel_goes_by_the_crossing_and_the_ferry(script):
    # Captured by hand on 2026-10-15: led to the Crossing, walked onto
    # Alfren's Ferry with the caravan following aboard and off, then
    # LEAD TO LETH from the south bank.
    world = World(CROSSING_ANSWERS, room=1533)
    assert script.leg(world, MAP, "weathered caravan", "Wolf Clan", "Leth Deriel")
    assert [c for c in world.sent if c.startswith(("tell", "go ", "(the"))] == [
        "tell weathered caravan to lead to crossing",
        "tell weathered caravan to wait",
        "tell weathered caravan to follow",
        "go pier",
        "(the ferry to leth)",
        "go dock",
        "tell weathered caravan to wait",
        "tell weathered caravan to lead to leth",
        "tell weathered caravan to wait",
    ]
    assert world.room == 2039


class Busy(World):
    """The first EAST lands in a typed command's roundtime and is dropped."""

    dropped = False

    def put(self, command):
        if command == "east" and not self.dropped:
            self.dropped = True
            self.sent.append(command)
            self.heard.append("...wait 3 seconds.\n")
            return
        super().put(command)


def test_a_move_dropped_in_roundtime_is_sent_again(script):
    # 2026-10-15: an INV LIST typed mid-walk took ;trade's SOUTHWEST
    # ("...wait 3 seconds."), and the follow wait gave up on the caravan.
    world = Busy(CROSSING_ANSWERS, room=1534)
    assert script.bring(world, MAP, "weathered caravan", 1533)
    assert world.sent == [
        "tell weathered caravan to follow",
        "east",
        "east",
        "tell weathered caravan to wait",
    ]


class Scenic(World):
    """A room whose description says "waits", the caravan a moment behind."""

    def put(self, command):
        super().put(command)
        if command == "east":
            self.heard.insert(
                0, "a shimmering crystal city waits astride a sparkling blue lake.\n"
            )


def test_a_description_that_waits_is_no_dropped_move(script):
    # 2026-10-15: "...wait" unescaped matched "city waits" on the Road to
    # Shard, and the next step left the caravan a room behind.
    world = Scenic(CROSSING_ANSWERS, room=1534)
    assert script.bring(world, MAP, "weathered caravan", 1533)
    assert world.sent.count("east") == 1
    assert world.heard == []  # the step waited for the caravan, not the city


def test_a_run_started_beside_its_caravan_in_its_town_brings_it_in(script):
    beside = "You seem to recall that you left your bullock-drawn caravan right behind you.\n"
    answers = dict(
        LEG,
        **{
            "recall caravan": [beside],
            "read my contract": [LOADED_CONTRACT, "What were you referring to?"],
        },
    )
    world = World(answers, room=1534)  # a room from Wolf Clan's outpost
    brought = []
    script.bring = lambda s, db, name, room: brought.append(room) or True
    script.main(world)
    assert brought == [1533]
    assert "give my contract to clerk" in world.sent


def test_a_run_started_beside_its_caravan_goes_on_from_there(script):
    beside = "You seem to recall that you left your bullock-drawn caravan right behind you.\n"
    answers = dict(
        LEG, **{"recall caravan": [beside], "read my contract": [LOADED_CONTRACT]}
    )
    world = World(answers, room=8915)
    legs = []
    script.leg = lambda s, db, name, origin, destination, *rest: (
        legs.append((origin, destination)) and False
    )
    script.main(world)
    assert world.walks == []  # not back to the Crossing's outpost first
    assert legs == [("Crossing", "Wolf Clan")]


def test_a_fare_the_purse_lacks_is_fetched_with_the_caravan_waiting(script):
    # 2026-10-15: back from Shard with only Dokoras, Alfren's Ferry
    # refused the Kronars fare at the south bank and the run stopped there.
    world = World(CROSSING_ANSWERS, room=1904)
    rides, fetched = ["fare kronars", "landed"], []

    def ride_ferry(s, bank=""):
        s.sent.append(f"(the ferry to {bank})")
        s.landing = 957
        return rides.pop(0)

    script.walker.ride_ferry = ride_ferry

    def fetch_fare(s, coin=""):
        fetched.append(coin)
        s.room = 1900  # ;bank ends at the teller
        return True

    script.walker.fetch_fare = fetch_fare
    assert script.bring(world, MAP, "weathered caravan", 895)
    assert fetched == ["kronars"]
    assert world.walks == [1904]  # back to the dock from the teller
    assert [c for c in world.sent if c.startswith(("tell", "(the", "go "))] == [
        "tell weathered caravan to follow",
        "(the ferry to crossing)",
        "tell weathered caravan to wait",
        "tell weathered caravan to follow",
        "(the ferry to crossing)",
        "go dock",
        "go square",
        "tell weathered caravan to wait",
    ]


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
        "tell weathered caravan to wait",
    ]
    assert world.room == 1073


def test_the_gondola_is_a_step_the_walker_rides():
    _script()
    route = MAP.path(2039, [8191])
    assert haul.steps(route) == [
        ["climb platform"],
        (haul.GONDOLA, "south"),
        ["go frame"],
    ]


def test_the_caravan_boards_the_gondola_before_the_cab_moves(script):
    # trade.lic's ride_gondola: the caravan is waited for in the cab,
    # then OUT at the far platform is the step it follows.
    world = World(CROSSING_ANSWERS, room=2039)
    assert script.bring(world, MAP, "weathered caravan", 8191)
    assert world.boarded
    assert world.sent == [
        "tell weathered caravan to follow",
        "climb platform",
        "(the gondola south)",
        "out",
        "go frame",
        "tell weathered caravan to wait",
    ]


def test_a_broker_contract_to_shard_goes_by_leth_and_the_gondola(script):
    # The Crossing's broker issued a contract for Shard (2026-10-15):
    # over the ferry, led to Leth, walked over the gondola to Shard.
    world = World(CROSSING_ANSWERS, room=895)
    assert script.leg(world, MAP, "weathered caravan", "Crossing", "Shard")
    assert [c for c in world.sent if c.startswith(("tell", "go ", "(the", "out"))] == [
        "tell weathered caravan to follow",
        "go pier",
        "(the ferry to leth)",
        "go dock",
        "tell weathered caravan to wait",
        "tell weathered caravan to lead to leth",
        "tell weathered caravan to wait",
        "tell weathered caravan to follow",
        "(the gondola south)",
        "out",
        "go frame",
        "tell weathered caravan to wait",
    ]
    assert world.room == 8191


def test_a_contract_from_ilithi_to_zoluren_crosses_back_the_same_way(script):
    calls = []
    script.lead = lambda s, name, place, *a: calls.append(("lead", place)) or True
    script.bring = lambda s, db, name, room: calls.append(("bring", room)) or True
    assert script.leg(None, MAP, "caravan", "Fayrin's Rest", "Arthe Dale")
    assert calls == [
        ("lead", "Shard"),
        ("bring", 8191),
        ("bring", 2039),
        ("lead", "Crossing"),
        ("bring", 895),
        ("lead", "Arthe Dale"),
        ("bring", 1073),
    ]


def test_the_faldesu_ferry_is_a_step_the_walker_rides():
    # The map's bescort 'faldesu' edge, ridden like Alfren's Ferry.
    _script()
    assert haul.steps(MAP.path(1385, [386])) == [
        (haul.FERRY, "haven"),
        ["go ramp"],
        ["go arch"],
        ["northwest"],
    ]


def test_a_leg_to_riverhaven_goes_by_dirge_and_the_faldesu(script):
    # Driven by hand on 2026-10-15 (#555): LEAD TO DIRGE, LEAD TO
    # RIVERHAVEN from Gateway Road to the north-road ferry, the caravan
    # aboard and off, up the ramp and through the arch to Town Hall Road.
    world = World(CROSSING_ANSWERS, room=895)
    world.run = lambda name, args=(): (
        world.sent.append(f";{name} {' '.join(args)}") or True
    )
    assert script.leg(world, MAP, "weathered caravan", "Crossing", "Riverhaven")
    assert [
        c for c in world.sent if c.startswith(("tell", "go ", "(the", "north", ";"))
    ] == [
        "tell weathered caravan to lead to dirge",
        "tell weathered caravan to wait",
        ";bank keep=20000 lirums=500 back",  # at Dirge, two rooms from its changer
        "tell weathered caravan to lead to riverhaven",
        "tell weathered caravan to follow",
        "(the ferry to haven)",
        "go dock",
        "go ramp",
        "go arch",
        "northwest",
        "tell weathered caravan to wait",
    ]
    assert world.room == 386


def test_lirums_enough_for_the_ferry_send_no_bank_run(script):
    world = World(CROSSING_ANSWERS, room=1307)
    world.purse = 500
    script.ferry_lirums(world)
    assert world.ran == []


def test_a_contract_from_riverhaven_crosses_back_and_leads_from_the_riverbank(script):
    # Elanthipedia (Trade Route): the lead to Dirge starts at North Road,
    # Riverbank, one room south of the ferry dock.
    world = World(CROSSING_ANSWERS, room=386)
    world.leads["arthe dale"] = 1073
    assert script.leg(world, MAP, "weathered caravan", "Riverhaven", "Arthe Dale")
    assert [
        c for c in world.sent if c.startswith(("tell", "go ", "(the", "south"))
    ] == [
        "tell weathered caravan to follow",
        "go pier",
        "go arch",
        "go ramp",
        "(the ferry to crossing)",
        "go dock",
        "south",
        "tell weathered caravan to wait",
        "tell weathered caravan to lead to dirge",
        "tell weathered caravan to wait",
        "tell weathered caravan to lead to arthe dale",
        "tell weathered caravan to wait",
    ]
    assert world.room == 1073 and world.ran == []


def test_a_delivery_at_riverhaven_takes_its_ministers_next_contract(script):
    # Therenborough and Langenfirth are routes now (#555).
    delivered = TO_RIVERHAVEN.replace(
        " This contract has yet to be presented to the Crossing guild\n clerk.\n", ""
    )
    answers = dict(
        LEG,
        **{
            "read my contract": [delivered, RIVERHAVEN_TO_THEREN],
            "get my riverhaven contract": [
                "You get a Riverhaven contract from inside your sturdy backpack.\n"
            ],
            "give my contract to clerk": [PAID_IN_LIRUMS, LOADED],
        },
    )
    world = World(answers, room=13751)
    legs = []
    script.leg = lambda s, db, name, origin, destination, *rest: (
        legs.append((origin, destination)) and False
    )
    script.main(world)
    assert "trade: Riverhaven paid 47,840 Lirums" in world.echoed
    assert "ask minister for contract" in world.sent
    assert legs == [("Riverhaven", "Therenborough")]


def test_interprovince_at_riverhaven_takes_its_brokers_contract(script):
    delivered = TO_RIVERHAVEN.replace(
        " This contract has yet to be presented to the Crossing guild\n clerk.\n", ""
    )
    answers = dict(
        LEG,
        **{
            "read my contract": [delivered, FROM_RIVERHAVEN],
            "get my riverhaven contract": [
                "You get a Riverhaven contract from inside your sturdy backpack.\n"
            ],
            "give my contract to clerk": [PAID_IN_LIRUMS, LOADED],
            "ask broker": [RIVERHAVEN_BROKER],
        },
    )
    world = World(answers, room=13751)
    world.args = ["interprovince"]
    afforded, legs = [], []
    script.shop = SimpleNamespace(
        afford=lambda s, ask, prefix, copper, coin, **k: (
            afforded.append((copper, coin)) or True
        )
    )
    script.leg = lambda s, db, name, origin, destination, *rest: (
        legs.append((origin, destination)) and False
    )
    script.main(world)
    assert "ask broker for contract" in world.sent
    assert 7877 in world.walks
    assert afforded == [(69193, "Lirums")]
    assert legs == [("Riverhaven", "Shard")]


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


class Held(World):
    """A lead that never arrives, two hostiles in the room."""

    def put(self, command):
        super().put(command)
        self.heard = [line for line in self.heard if ARRIVED not in line]


def test_a_character_held_by_hostiles_on_a_lead_gets_clear_and_stops(script):
    # 2026-10-15: crazed madmen in the Lava Fields outside Dirge engaged
    # the led character, and the caravan went on to Dirge alone.
    world = Held({"tell weathered caravan to lead": [LED]}, room=1533)
    world.state.hostiles = {"197647014": "crazed madman", "197648055": "ghoul"}
    reacted = []
    script.flight = SimpleNamespace(
        hostiles_present=lambda state: bool(state.hostiles),
        react=lambda s, prefix, *a, **k: reacted.append(prefix) or True,
    )
    assert not script.lead(world, "weathered caravan", "Dirge")
    assert reacted == ["trade"]
    assert any("held by hostiles on the lead to Dirge" in e for e in world.echoed)


class Passing(Slow):
    """A lead through rooms with hostiles in them, a new room each look."""

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        self.state.room_uid = getattr(self.state, "room_uid", 0) + 1
        return super().waitfor(*patterns, timeout=timeout, streams=streams)


def test_hostiles_in_rooms_the_lead_passes_do_not_stop_it(script):
    world = Passing({"tell weathered caravan to lead": [LED]}, quiet=4, room=1533)
    world.state.hostiles = {"1": "ghoul"}
    script.flight = SimpleNamespace(
        hostiles_present=lambda state: bool(state.hostiles),
        react=lambda *a, **k: pytest.fail("reacted to a passing room"),
    )
    assert script.lead(world, "weathered caravan", "Dirge")


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
    assert afforded == [(288, "Dokoras")]
    assert "trade: not enough coin for the caravan's 288 Dokoras" in world.echoed


# Therenborough's clerk, 2026-10-17, with 135 Lirums on hand.
THEREN_RENT_SHORT = (
    "The clerk nods and says, \"All right, that's a 320 Lirums fee for a"
    ' rental...."\n'
    "You attempt to pay the clerk, but you don't have enough money.  After"
    " haggling with the clerk for several moments, he finally shrugs at you and"
    ' says, "Sorry, can\'t put it in your dues.  Ya gotta pay up front."\n'
)


def test_a_caravan_rented_in_therengia_is_320_lirums(script):
    afforded = []
    script.shop = SimpleNamespace(
        afford=lambda s, ask, prefix, copper, currency="Kronars", **k: (
            afforded.append((copper, currency)) or True
        )
    )
    world = World({"rent caravan": [THEREN_RENT_SHORT]}, room=3232)
    assert script.rent(world, MAP, "Therenborough") is None
    assert afforded == [(320, "Lirums")]
    assert "trade: not enough coin for the caravan's 320 Lirums" in world.echoed


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


def test_the_lead_plays_the_profiles_trainer_and_stops_it_on_arrival(script):
    # The operator, 2026-10-15: "He is wearing zills, so we can start with
    # ;perform" (#558). The feedbag full, no forage.
    world = Slow(GRASS_ANSWERS, quiet=2, room=1533)
    world.staying = {"perform"}
    full = [script.GRASS_TOP]
    assert script.lead(world, "weathered caravan", "Wolf Clan", full, ["perform"])
    assert world.ran == [("perform", ["once", "here", "stay"])]
    assert "forage grass" not in world.sent
    assert world.told == [("perform", "return")]
    assert "trade: ;perform while the caravan leads" in world.echoed


def test_a_trainer_that_ended_lets_the_grass_forage_resume(script):
    # ;perform once ends itself at mind-lock: the lead forages again.
    world = Slow(GRASS_ANSWERS, quiet=2, room=1533)
    assert script.lead(world, "weathered caravan", "Wolf Clan", [10], ["perform"])
    assert world.sent.count("forage grass") == 2


def test_a_trainer_deaf_to_return_is_stopped(script):
    world = Slow(GRASS_ANSWERS, quiet=1, room=1533)
    world.staying, world.deaf = {"perform"}, True
    full = [script.GRASS_TOP]
    assert script.lead(world, "weathered caravan", "Wolf Clan", full, ["perform"])
    assert world.killed == ["perform"]


def _exp(**minds):
    return {
        skill: {"rank": 100, "percent": 0, "mindstate": mind, "rate": ""}
        for skill, mind in minds.items()
    }


def test_the_emptiest_skill_trains_first_on_a_lead(script):
    # The operator, 2026-10-15: "a list of things to train instead of
    # being one or the other" — the most skills moving.
    world = Slow(GRASS_ANSWERS, quiet=2, room=1533)
    world.state.experience = _exp(Performance=20, Appraisal=3)
    world.staying = {"perform", "appraise"}
    lead = script.lead(
        world,
        "weathered caravan",
        "Wolf Clan",
        [script.GRASS_TOP],
        ["perform", "appraise"],
    )
    assert lead
    assert world.ran == [("appraise", ["once", "stay"])]


def test_research_ranks_by_its_emptiest_skill(script):
    # Five magic skills at 0/34 put ;research ahead of an Appraisal at 3:
    # the run that moves the most skills goes first.
    world = Slow(GRASS_ANSWERS, quiet=2, room=1533)
    world.state.experience = _exp(
        Performance=20,
        Appraisal=3,
        Attunement=30,
        Augmentation=0,
        Utility=34,
        Warding=34,
        Arcana=34,
    )
    world.staying = {"research"}
    lead = script.lead(
        world,
        "weathered caravan",
        "Wolf Clan",
        [script.GRASS_TOP],
        ["perform", "appraise", "research"],
    )
    assert lead
    assert world.ran == [
        (
            "research",
            [
                "once",
                "stay",
                "stream",
                "augmentation",
                "utility",
                "warding",
                "fundamental",
            ],
        )
    ]
    assert world.told == [("research", "return")]


def test_a_trainer_that_ends_hands_the_lead_to_the_next(script):
    world = Slow(GRASS_ANSWERS, quiet=2, room=1533)
    world.state.experience = _exp(Performance=20, Appraisal=3)
    world.staying = {"perform"}  # ;appraise once ends at once (at mind-lock)
    lead = script.lead(
        world,
        "weathered caravan",
        "Wolf Clan",
        [script.GRASS_TOP],
        ["perform", "appraise"],
    )
    assert lead
    assert world.ran == [
        ("appraise", ["once", "stay"]),
        ("perform", ["once", "here", "stay"]),
    ]
    assert "forage grass" not in world.sent
    assert world.told == [("perform", "return")]


def test_grass_is_topped_up_before_any_training(script):
    # The operator, 2026-10-15: "grass forage should take prio just so he
    # doesn't run out of feed".
    world = Slow(GRASS_ANSWERS, quiet=3, room=1533)
    world.staying = {"perform"}
    grass = [script.GRASS_TOP - 1]
    assert script.lead(world, "weathered caravan", "Wolf Clan", grass, ["perform"])
    assert grass == [script.GRASS_TOP]
    assert world.sent.count("forage grass") == 1
    forage = world.sent.index("forage grass")
    assert world.ran == [("perform", ["once", "here", "stay"])]
    assert world.sent.index("put my grass in my feedbag") > forage
    assert world.told == [("perform", "return")]


def test_pause_typed_on_a_lead_stops_after_delivery_with_the_caravan_kept(script):
    # The operator, 2026-10-16: stop and start "without needing to return
    # and rent a new caravan".
    world = World(LEG, return_after_lead=True)
    world.after_lead_word = "pause"
    script.main(world)
    assert "return caravan" not in world.sent
    assert world.sent.count("ask minister for contract") == 1
    assert any("paused at Wolf Clan" in e for e in world.echoed)


def test_pause_when_not_running_starts_nothing(script):
    world = World(LEG)
    world.args = ["pause"]
    script.main(world)
    assert world.sent == []
    assert "not running" in world.echoed[0]


def test_lead_training_is_read_again_before_every_leg(script):
    calls = []
    real = script.trainers
    script.trainers = lambda s, quiet=False: calls.append(quiet) or real(s, quiet)
    script.main(World(LEG, return_after_lead=True))
    assert calls == [False, True]


def test_the_profiles_lead_training_keeps_what_trade_can_run(script):
    from client.game import profile

    profile.save_profile("Lanival", {"lead_training": ["Perform", "appraise", "knit"]})
    world = World({})
    assert script.trainers(world) == ["perform", "appraise"]
    assert world.echoed == ["trade: no lead training for knit — skipped"]


# ;trade circuit (#556)


def _contract(origin, destination, presented=True):
    return trade.Contract(
        origin, destination, "goods", 1000, "Dokoras", presented, False
    )


class Circuit:
    """;trade circuit's helpers replaced: each stop's held contracts come
    from `stops` in turn, every call is recorded, and a leg ends the run
    after `legs` of them."""

    def __init__(self, script, stops, taken=(), legs=1, minutes=None, ending=False):
        self.calls, self.stops, self.taken = [], list(stops), list(taken)
        self.legs = legs
        script.held_all = lambda s: self.stops.pop(0) if self.stops else []
        script.deliver = lambda s, db, place, only=True: self.record(
            "deliver", place, only
        )
        script.load = lambda s, db, place, seq: self.record("load", place)
        script.walk = lambda s, db, room, describe: True
        script.pay = lambda s: "dues settled"
        script.bank_run = lambda s, db, coin="Kronars": self.record("bank", coin)
        script.put_away = lambda s, db, place, contracts: 0
        script.take = lambda s, db, place, broker=False: self.take(place)
        script.feed = lambda s, name: 60
        script.trainers = lambda s, quiet=False: []
        script.bring = lambda s, db, name, room: self.record("bring", room)
        script.return_caravan = lambda s, db, place, name: self.record("return", place)
        script.paused = lambda s: False
        script.loop = SimpleNamespace(wants_stop=lambda s: ending)
        script.leg = lambda s, db, name, origin, destination, *rest: self.leg(
            origin, destination
        )
        script.tradelog = SimpleNamespace(
            leg_minutes=lambda character=None: dict(minutes or {}),
            log_issue=lambda *a, **k: 1,
        )

    def record(self, *call):
        self.calls.append(call)
        return True

    def take(self, place):
        self.calls.append(("take", place))
        return self.taken.pop(0) if self.taken else None

    def leg(self, origin, destination):
        self.calls.append(("leg", origin, destination))
        self.legs -= 1
        return self.legs > 0


def test_a_circuit_stop_hands_in_every_crate_for_it_and_takes_the_towns_own(script):
    world = World({})
    fake = Circuit(
        script,
        stops=[
            [
                _contract("Fayrin's Rest", "Shard"),
                _contract("Steelclaw Clan", "Shard"),
                _contract("Darkling Wood", "Steelclaw Clan"),
            ]
        ],
        taken=[_contract("Shard", "Fayrin's Rest")],
        minutes={("Shard", "Fayrin's Rest"): 5.3, ("Shard", "Steelclaw Clan"): 4.1},
    )
    script.circuit(world, MAP, "ironclad caravan", "Shard", False, [])
    assert fake.calls == [
        ("deliver", "Shard", False),
        ("deliver", "Shard", False),
        ("bank", "Dokoras"),
        ("take", "Shard"),
        ("leg", "Shard", "Steelclaw Clan"),  # 4.1 minutes, nearer than 5.3
    ]
    assert "trade: 2 contract(s) held — next Steelclaw Clan (1 crate(s) for it)" in (
        world.echoed
    )


def test_a_town_whose_contract_is_held_issues_none(script):
    world = World({})
    fake = Circuit(
        script,
        stops=[
            [_contract("Shard", "Darkling Wood"), _contract("Darkling Wood", "Shard")]
        ],
        minutes=SHARD_LEGS,
        legs=1,
    )
    script.circuit(world, MAP, "ironclad caravan", "Shard", False, [])
    assert ("take", "Shard") not in fake.calls
    assert fake.calls[-1] == ("leg", "Shard", "Steelclaw Clan")


# Measured legs from Shard, the nearest first.
SHARD_LEGS = {
    ("Shard", "Steelclaw Clan"): 4.1,
    ("Shard", "Fayrin's Rest"): 5.3,
    ("Shard", "Darkling Wood"): 6.9,
}


def test_a_town_no_contract_is_held_from_is_business_too(script):
    # Fayrin's Rest with nothing held: its contract goes to Darkling Wood,
    # and the nearest stop is Steelclaw Clan, for its own contract — or
    # every stop's new contract would be the only one held.
    world = World({})
    fake = Circuit(
        script,
        stops=[[]],
        taken=[_contract("Fayrin's Rest", "Darkling Wood")],
        minutes={
            ("Fayrin's Rest", "Steelclaw Clan"): 2.2,
            ("Fayrin's Rest", "Shard"): 5.3,
            ("Fayrin's Rest", "Darkling Wood"): 9.0,
        },
    )
    script.circuit(world, MAP, "ironclad caravan", "Fayrin's Rest", False, [])
    assert fake.calls == [
        ("take", "Fayrin's Rest"),
        ("leg", "Fayrin's Rest", "Steelclaw Clan"),
    ]
    assert (
        "trade: 1 contract(s) held — next Steelclaw Clan (its contract to take)"
        in world.echoed
    )


def test_a_return_takes_nothing_new_and_ends_once_nothing_is_held(script):
    world = World({})
    fake = Circuit(
        script,
        stops=[[_contract("Shard", "Fayrin's Rest")], []],
        minutes={("Shard", "Fayrin's Rest"): 5.3},
        legs=2,
        ending=True,
    )
    script.circuit(world, MAP, "ironclad caravan", "Shard", False, [])
    assert ("take", "Shard") not in fake.calls
    assert fake.calls[0] == ("leg", "Shard", "Fayrin's Rest")
    assert fake.calls[-1] == ("return", "Fayrin's Rest")
    assert "trade: nothing held — done at Fayrin's Rest" in world.echoed


def test_the_next_stop_is_measured_when_every_leg_is_known_else_walked():
    script = _script()
    walked = {2840: 30.0, 2702: 60.0, 2874: 10.0}  # outpost: map seconds
    db = SimpleNamespace(
        path=lambda start, goals: [(next(iter(goals)), "go")],
        seconds_of=lambda start, route: walked[route[-1][0]],
    )
    legs = {("Shard", "Fayrin's Rest"): 5.3, ("Darkling Wood", "Shard"): 4.7}
    # Either direction counts: Darkling Wood's 4.7 beats Fayrin's 5.3.
    assert script.next_stop(db, "Shard", {"Fayrin's Rest", "Darkling Wood"}, legs) == (
        "Darkling Wood"
    )
    # Steelclaw Clan unmeasured: all by the map, where it is nearest.
    towns = {"Fayrin's Rest", "Darkling Wood", "Steelclaw Clan"}
    assert script.next_stop(db, "Shard", towns, legs) == "Steelclaw Clan"


def test_every_held_contract_is_read_by_its_ordinal(script):
    world = World(
        {
            "read my first contract": [CONTRACT],
            "read my second contract": [TO_SHARD],
            "read my third contract": ["What were you referring to?"],
        }
    )
    contracts = script.held_all(world)
    assert [c.destination for c in contracts] == ["Wolf Clan", "Shard"]
    assert world.sent == [
        "read my first contract",
        "read my second contract",
        "read my third contract",
    ]


def test_a_legs_time_is_its_shortest_delivered_contract(tmp_path, monkeypatch):
    # A crate carried along a circuit only lengthens its route's time.
    db = tmp_path / "history.db"
    stamps = iter(
        [
            "2026-10-16T00:00:00+00:00",
            "2026-10-16T00:05:00+00:00",
            "2026-10-16T01:00:00+00:00",
            "2026-10-16T01:20:00+00:00",
        ]
    )
    monkeypatch.setattr(tradelog, "now", lambda: next(stamps))
    contract = trade.contract(CONTRACT)
    for _ in range(2):
        tradelog.log_issue("Lanival", "Crossing", contract, path=db)
        tradelog.log_delivery("Lanival", "Wolf Clan", 11791, path=db)
    assert tradelog.leg_minutes("Lanival", path=db) == {("Crossing", "Wolf Clan"): 5.0}


def test_a_circuit_started_on_the_road_goes_on_without_the_clerk(script):
    # Beside its caravan with crates for other towns (a run stopped on a
    # lead): no clerk, no new contract, the lead from where it stands.
    world = World({})
    fake = Circuit(
        script,
        stops=[[_contract("Shard", "Darkling Wood")]],
        minutes=SHARD_LEGS,
    )
    script.circuit(world, MAP, "ironclad caravan", "Shard", True, [])
    assert fake.calls == [("leg", "Shard", "Steelclaw Clan")]
    assert "trade: dues settled" not in world.echoed


# Forfedhdar (#555)


def test_forfedhdar_trades_in_dokoras_and_is_its_own_province():
    for town in trade.FORFEDHDAR:
        assert trade.coin(town) == "Dokoras" and town in trade.TOWNS
    assert trade.lead_name("Raven's Point") == "raven"
    assert tradelog.province("Hibarnhvidar", "Boar Clan") == "Forfedhdar"
    assert tradelog.province("Hibarnhvidar", "Shard") == "Interprovince"
    # Its roads to the other provinces are not built: such a contract
    # is left unloaded, as one beyond the routes is.
    assert trade.routable("Hibarnhvidar", "Ain Ghazal")
    assert not trade.routable("Shard", "Hibarnhvidar")
    assert not trade.routable("Hibarnhvidar", None)


def _forfedhdar(script, refused=()):
    """lead and bring recorded; a lead to a town in `refused` is turned
    down once."""
    calls, turned = [], set()

    def lead(s, name, place, *rest):
        calls.append(("lead", place))
        if place in refused and place not in turned:
            turned.add(place)
            return None
        return True

    script.lead = lead
    script.bring = lambda s, db, name, room: calls.append(("bring", room)) or True
    return calls


def test_boar_clan_is_led_to_and_from_by_way_of_hibarnhvidar(script):
    calls = _forfedhdar(script)
    world = World({})
    assert script.leg(world, MAP, "caravan", "Raven's Point", "Boar Clan")
    assert calls == [
        ("lead", "Hibarnhvidar"),
        ("bring", 3903),
        ("lead", "Boar Clan"),
        ("bring", 4106),
    ]
    calls.clear()
    assert script.leg(world, MAP, "caravan", "Hibarnhvidar", "Raven's Point")
    assert calls == [("lead", "Raven's Point"), ("bring", 4440)]


def test_ain_ghazal_to_ravens_point_goes_by_hibarnhvidar(script):
    # The wiki lists Raven's Point to Ain Ghazal only, and the driver
    # turned the other way down twice on 2026-10-17 (#583).
    calls = _forfedhdar(script)
    world = World({})
    assert script.leg(world, MAP, "caravan", "Ain Ghazal", "Raven's Point")
    assert calls == [
        ("lead", "Hibarnhvidar"),
        ("bring", 3903),
        ("lead", "Raven's Point"),
        ("bring", 4440),
    ]
    calls.clear()
    assert script.leg(world, MAP, "caravan", "Raven's Point", "Ain Ghazal")
    assert calls == [("lead", "Ain Ghazal"), ("bring", 11033)]


def test_a_lead_turned_down_is_told_again_from_trade_lics_room(script):
    calls = _forfedhdar(script, refused={"Ain Ghazal", "Boar Clan"})
    world = World({})
    assert script.leg(world, MAP, "caravan", "Hibarnhvidar", "Ain Ghazal")
    assert calls == [
        ("lead", "Ain Ghazal"),
        ("bring", 3943),  # Haalikshal Highway, East Park
        ("lead", "Ain Ghazal"),
        ("bring", 11033),
    ]
    calls.clear()
    assert script.leg(world, MAP, "caravan", "Hibarnhvidar", "Boar Clan")
    assert calls[:3] == [("lead", "Boar Clan"), ("bring", 3991), ("lead", "Boar Clan")]
    assert "trade: walking the caravan out to lead from there" in world.echoed


# Ain Ghazal's outpost, 2026-10-16 17:27: a lead the driver turns down.
OFF_ROUTE = (
    "The driver of your elk-drawn caravan acknowledges the order, but turns back"
    ' and says, "We are currently not located on or near the caravan route to'
    "  Hibarnhvidar.  You will need to lead us there yourself before I can take"
    ' the caravan to Hibarnhvidar."\n'
)


def test_a_driver_off_the_caravan_route_turns_the_lead_down(script):
    world = World({"tell elk-drawn caravan to lead": [OFF_ROUTE]})
    assert script.lead(world, "elk-drawn caravan", "Hibarnhvidar") is None
    assert any("the driver did not take the lead" in e for e in world.echoed)


# Hibarnhvidar, 2026-10-16 17:48: the caravan followed a bank run off
# the outpost, and the clerk would not load the next crate.
CARAVAN_AWAY = (
    'The shipment clerk accepts your contract and peruses it.  "Okay," the clerk'
    " says.  \"Let's see... that's 20 crates of cobblestones, with a total weight"
    ' of...700 pounds!"\n'
    "The clerk says, \"We can't help you until your elk-drawn caravan is out by the"
    ' Market Road.  Sorry!"\n'
)


def test_a_caravan_off_the_outpost_is_said_not_unrecognized():
    assert trade.clerk(CARAVAN_AWAY) == ("away", None)


def test_a_caravan_already_at_the_room_is_told_to_wait(script):
    # Still set to follow from an earlier walk, it followed the bank run.
    world = World({}, room=3903)
    assert script.bring(world, MAP, "elk-drawn caravan", 3903)
    assert world.sent == ["tell elk-drawn caravan to wait"]


def test_a_contract_read_back_unloaded_keeps_its_row(tmp_path):
    db = tmp_path / "history.db"
    contract = trade.contract(CONTRACT)
    first = tradelog.log_issue("Lanival", "Crossing", contract, 3537, 985, path=db)
    again = tradelog.log_issue("Lanival", "Crossing", contract, path=db)
    assert again == first
    (route,) = tradelog.summary("Lanival", path=db)
    assert route["contracts"] == 1
    # A minister's new issue of the same goods, its charges known, is a
    # contract of its own: they repeat (Darkling Wood's buckles, twice).
    assert tradelog.log_issue("Lanival", "Crossing", contract, 3537, 985, path=db) != (
        first
    )


# Therengia (#555)

# Therenborough's minister, 2026-10-17.
THEREN_ISSUED = (
    ISSUED.replace("3537 Kronars", "14270 Lirums")
    .replace("985", "4642")
    .replace("4522", "18912")
)
TO_MUSPARI = (
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
    " Trading Contract Issued by:  Therenborough\n"
    " The guild office at Muspar'i requires 1982 pots of flax seed oil,\n"
    " to be delivered within 6 anlaen.\n"
    " The bearer of the goods and this contract will receive,\n"
    " upon safe and timely delivery of the merchandise, a payment\n"
    " in the form of the local currency.\n"
    " This contract has yet to be presented to the Therenborough guild\n"
    " clerk.\n"
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
    "You estimate these goods are currently worth 47568 Lirums on delivery.\n"
)
# That contract sent to Forfedhdar, whose roads out are not built: one
# beyond the routes, now that all six of Therengia's towns are.
BEYOND = TO_MUSPARI.replace("Muspar'i requires", "Hibarnhvidar requires")

# A Riverhaven minister's contract for Therenborough, in the Crossing
# contract's words.
RIVERHAVEN_TO_THEREN = (
    CONTRACT.replace("Issued by:  Crossing", "Issued by:  Riverhaven")
    .replace("Wolf Clan requires", "Therenborough requires")
    .replace("the Crossing guild", "the Riverhaven guild")
    .replace("11791 Kronars", "9120 Lirums")
)


def test_therengia_trades_in_lirums_between_its_six_towns():
    assert len(trade.THERENGIA) == 6
    for town in trade.THERENGIA:
        assert trade.coin(town) == "Lirums" and town in trade.TOWNS
    assert tradelog.province("Therenborough", "Langenfirth") == "Therengia"
    assert tradelog.province("Therenborough", "Muspar'i") == "Therengia"
    assert trade.routable("Riverhaven", "Langenfirth")
    assert trade.routable("Therenborough", "Crossing")  # by way of Riverhaven
    # No caravan way through the Ker'Leor forest (2026-10-18): the three
    # towns past it trade among themselves.
    for town in ("Fornsted", "Hvaral", "Muspar'i"):
        assert not trade.routable("Therenborough", trade.town(town))
        assert not trade.routable(town, "Crossing")
    assert trade.routable("Fornsted", "Hvaral")
    assert trade.routable("Muspar'i", "Fornsted")
    assert trade.town("Muspar'i") == "Muspar'i"


def test_a_leg_goes_town_by_town_over_the_leads_and_the_walks():
    assert trade.via("Langenfirth", "Riverhaven") == "Therenborough"
    assert trade.via("Therenborough", "Langenfirth") == "Langenfirth"
    assert trade.via("Therenborough", "Hvaral") is None
    assert trade.via("Muspar'i", "Riverhaven") is None
    assert trade.via("Fornsted", "Muspar'i") == "Hvaral"
    # Forfedhdar's by Hibarnhvidar, as before (#583).
    assert trade.via("Ain Ghazal", "Raven's Point") == "Hibarnhvidar"
    assert trade.via("Raven's Point", "Ain Ghazal") == "Ain Ghazal"
    # Zoluren leads anywhere, and the roads between provinces are leg()'s.
    assert trade.via("Crossing", "Wolf Clan") is None
    assert trade.via("Riverhaven", "Crossing") is None


def test_riverhaven_to_langenfirth_goes_by_way_of_therenborough(script):
    calls = _forfedhdar(script)
    world = World({})
    assert script.leg(world, MAP, "caravan", "Riverhaven", "Langenfirth")
    assert calls == [
        ("lead", "Therenborough"),
        ("bring", 3155),
        ("lead", "Langenfirth"),
        ("bring", 3407),
    ]
    calls.clear()
    assert script.leg(world, MAP, "caravan", "Langenfirth", "Riverhaven")
    assert calls == [
        ("lead", "Therenborough"),
        ("bring", 3155),
        ("lead", "Riverhaven"),
        ("bring", 386),
    ]


def test_a_lead_between_therenborough_and_langenfirth_starts_outside_town(script):
    # Elanthipedia (Trade Route): North Road, Barony Pass to Outside
    # Langenfirth and back.
    calls = _forfedhdar(script, refused={"Langenfirth", "Therenborough"})
    world = World({})
    assert script.leg(world, MAP, "caravan", "Therenborough", "Langenfirth")
    assert calls == [
        ("lead", "Langenfirth"),
        ("bring", 3234),
        ("lead", "Langenfirth"),
        ("bring", 3407),
    ]
    calls.clear()
    assert script.leg(world, MAP, "caravan", "Langenfirth", "Therenborough")
    assert calls == [
        ("lead", "Therenborough"),
        ("bring", 3339),
        ("lead", "Therenborough"),
        ("bring", 3155),
    ]


def test_a_lead_to_riverhaven_turned_down_has_no_room_to_try_again(script):
    # trade.lic's start for it is across the Langenfirth barge.
    calls = _forfedhdar(script, refused={"Riverhaven"})
    world = World({})
    assert not script.leg(world, MAP, "caravan", "Therenborough", "Riverhaven")
    assert calls == [("lead", "Riverhaven")]


def test_a_leg_from_therenborough_out_of_the_province_goes_by_riverhaven(script):
    calls = _forfedhdar(script)
    world = World({})
    assert script.leg(world, MAP, "caravan", "Therenborough", "Crossing")
    assert calls == [
        ("lead", "Riverhaven"),
        ("bring", 386),
        ("bring", trade.RIVERBANK),
        ("lead", "Dirge"),
        ("bring", 1307),
        ("lead", "Crossing"),
        ("bring", 895),
    ]


def test_a_therengia_circuit_works_its_six_towns(script):
    assert script.province("Langenfirth") == trade.THERENGIA


def test_a_circuit_never_loads_nor_leads_to_a_contract_beyond_the_routes(script):
    world = World({})
    fake = Circuit(
        script,
        stops=[[_contract("Therenborough", "Hibarnhvidar", presented=False)]],
        minutes=THEREN_MINUTES,
    )
    script.circuit(world, MAP, "sleek caravan", "Therenborough", False, [])
    # Held from Therenborough, so its minister is not asked; the nearest
    # other town is next, for its own contract.
    assert fake.calls == [("leg", "Therenborough", "Langenfirth")]


def test_an_expired_contract_frees_its_town_for_the_next(script):
    # 6 anlaen for Therenborough's Muspar'i contract: 3 hours, after which
    # its minister issues again. Expired, READ names only its origin.
    world = World({})
    expired = trade.Contract("Therenborough", None, None, None, None, False, True)
    fake = Circuit(
        script,
        stops=[[expired]],
        taken=[_contract("Therenborough", "Langenfirth")],
        minutes=THEREN_MINUTES,
    )
    script.circuit(world, MAP, "sleek caravan", "Therenborough", False, [])
    assert fake.calls[:2] == [
        ("take", "Therenborough"),
        ("leg", "Therenborough", "Langenfirth"),
    ]


# The legs out of Therenborough, shortest first.
THEREN_MINUTES = {
    ("Therenborough", "Langenfirth"): 6.0,
    ("Riverhaven", "Therenborough"): 8.0,
    ("Therenborough", "Fornsted"): 12.0,
    ("Therenborough", "Hvaral"): 20.0,
    ("Therenborough", "Muspar'i"): 45.0,
}


def _waiting(expired=False):
    """A contract beyond the routes held from each of Therengia's towns
    (2026-10-17 21:29, its three western towns unbuilt; a Forfedhdar
    destination stands in for them now)."""
    return [
        _contract(town, "Hibarnhvidar", False)._replace(
            expired=expired and town == "Therenborough"
        )
        for town in trade.THERENGIA
    ]


def test_with_every_town_waiting_the_circuit_holds_until_one_expires(script):
    world = World({})
    fake = Circuit(
        script,
        stops=[_waiting(), _waiting(), _waiting(True), _waiting(True)],
        minutes={("Riverhaven", "Therenborough"): 7.5},
    )
    script.circuit(world, MAP, "sleek caravan", "Riverhaven", False, [])
    assert fake.calls == [("leg", "Riverhaven", "Therenborough")]
    assert sum("holding at Riverhaven" in e for e in world.echoed) == 1
    assert not any("yours to deliver" in e for e in world.echoed)


def test_a_return_typed_while_held_ends_the_wait(script):
    world = World({})
    fake = Circuit(script, stops=[_waiting()] * 3)
    # typed once the hold began
    script.loop = SimpleNamespace(
        wants_stop=lambda s: any("holding at" in e for e in s.echoed)
    )
    script.circuit(world, MAP, "sleek caravan", "Riverhaven", False, [])
    assert not any(call[0] == "leg" for call in fake.calls)
    assert sum("holding at Riverhaven" in e for e in world.echoed) == 1


# Langenfirth's Hvaral contract at 22:35, 2026-10-17, its 2 hours up.
EXPIRED_CONTRACT = (
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
    " Trading Contract Issued by:  Langenfirth\n"
    " The contract is now useless since it has expired.\n"
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
)


def test_an_expired_contract_reads_as_its_origin_alone():
    c = trade.contract(EXPIRED_CONTRACT)
    assert (c.origin, c.destination, c.expired, c.presented) == (
        "Langenfirth",
        None,
        True,
        False,
    )


def test_an_expired_contract_does_not_end_the_reading_of_the_rest(script):
    # It stopped held_all at the second ordinal, and the hold never saw
    # an expired one: Muspar'i's, the third, went unread.
    world = World(
        {
            "read my first contract": [RIVERHAVEN_TO_THEREN],
            "read my second contract": [EXPIRED_CONTRACT],
            "read my third contract": [TO_MUSPARI],
            "read my fourth contract": ["I could not find what you were referring to."],
        }
    )
    contracts = script.held_all(world)
    assert [c.origin for c in contracts] == [
        "Riverhaven",
        "Langenfirth",
        "Therenborough",
    ]
    assert script.held_from(contracts) == {"Riverhaven", "Therenborough"}


class Bin(World):
    """The Alliance of Exchange's Main Hall: a waste bin, and a contract
    in hand after GET MY <ordinal> CONTRACT until it is put in."""

    def put(self, command):
        super().put(command)
        if command.startswith("get my ") and command.endswith(" contract"):
            self.state.right_hand = dict(CONTRACT_HELD)
        elif command.startswith("put my contract in"):
            self.state.right_hand = None


NOT_FOUND = "I could not find what you were referring to."


def test_an_expired_contract_goes_in_therenboroughs_waste_bin(script):
    world = Bin(
        {
            "get my second contract": ["You get a Hvaral contract from your backpack."],
            "read my contract": [EXPIRED_CONTRACT],
            "put my contract in": ["You drop a Hvaral contract in a waste bin."],
            "read my first contract": [RIVERHAVEN_TO_THEREN],
            "read my second contract": [TO_MUSPARI],
            "read my third contract": [NOT_FOUND],
        },
        room=3232,
    )
    world.state.room_objs = "a waste bin"
    held = [
        trade.contract(RIVERHAVEN_TO_THEREN),
        trade.contract(EXPIRED_CONTRACT),
        trade.contract(TO_MUSPARI),
    ]
    assert script.put_away(world, MAP, "Therenborough", held) == 1
    assert world.walks == [3228]
    sent = world.sent
    assert sent.index("get my second contract") < sent.index("read my contract")
    assert sent.index("read my contract") < sent.index("put my contract in bin")
    assert "drop my contract" not in sent
    assert "trade: 1 expired contract(s) put in the Therenborough waste bin" in (
        world.echoed
    )


def test_a_contract_that_reads_live_in_hand_is_stowed_not_binned(script):
    world = Bin(
        {"get my second contract": ["You get..."], "read my contract": [TO_MUSPARI]},
        room=3232,
    )
    world.state.room_objs = "a waste bin"
    held = [trade.contract(RIVERHAVEN_TO_THEREN), trade.contract(EXPIRED_CONTRACT)]
    assert script.put_away(world, MAP, "Therenborough", held) == 0
    assert not any(c.startswith("put my contract") for c in world.sent)
    assert world.sent[-1] == "stow my contract"
    assert "trade: could not put an expired contract away — kept" in world.echoed


def test_expired_contracts_are_kept_where_no_bin_is_known(script):
    world = Bin({}, room=13414)
    assert (
        script.put_away(world, MAP, "Langenfirth", [trade.contract(EXPIRED_CONTRACT)])
        == 0
    )
    assert world.sent == []


# LOOK BULLOCK-DRAWN CARAVAN, captured at the Crossing on 2026-10-15; the
# Fornsted crate is Dijkstra's of 2026-10-17, issued before Fornsted
# went off the routes.
def _report(*routes):
    return "\n".join(
        [
            "You tell the driver to give you an inventory report for your"
            " bullock-drawn caravan.",
            *(
                f"  A sturdy crate is for a contract from {origin} and destined"
                f" for {destination}."
                for origin, destination in routes
            ),
            "  A storage box to carry your items.",
            'The driver calls out, "The animals might like something to eat."',
        ]
    )


FORNSTED_CRATE = ("Therenborough", "Fornsted")
LANGENFIRTH_CRATE = ("Riverhaven", "Langenfirth")


def test_the_caravans_inventory_report_lists_each_crates_towns():
    assert trade.crates(_report(("The Crossing", "Wolf Clan"))) == [
        ("Crossing", "Wolf Clan")
    ]
    # Read whole, the lines run together.
    glued = _report(LANGENFIRTH_CRATE, ("Aesry", "Fornsted")).replace("\n", " ")
    assert trade.crates(glued) == [LANGENFIRTH_CRATE, ("Aesry", "Fornsted")]
    assert (
        trade.crates("You tell the driver ... A storage box to carry your items.") == []
    )


def test_a_crate_beyond_the_routes_or_its_contract_expired_is_stranded(script):
    live = _contract(*LANGENFIRTH_CRATE)
    forest = _contract(*FORNSTED_CRATE)
    lapsed = trade.Contract("Therenborough", None, None, None, None, False, True)
    crates = [LANGENFIRTH_CRATE, FORNSTED_CRATE]
    assert script.stranded(crates, [live, forest]) == 1
    assert script.stranded(crates, [live, lapsed]) == 1
    # A live contract accounts for its own crate; a crate with no contract
    # held at all (one lost) is kept.
    assert script.stranded(crates, [live]) is None
    assert script.stranded([LANGENFIRTH_CRATE], [lapsed]) is None
    # Two crates of one route, one contract expired: the second is its.
    again = [LANGENFIRTH_CRATE, LANGENFIRTH_CRATE]
    gone = trade.Contract("Riverhaven", None, None, None, None, False, True)
    assert script.stranded(again, [live, gone]) == 1


# Langenfirth, 2026-10-18: the Fornsted crate pushed and pulled off.
GRAB = (
    "You grab onto the sturdy crate and maneuver it so it is positioned to be"
    " the first crate offloaded."
)
PULL = (
    "You begin to pull at the sturdy crate on your bullock-drawn caravan.  You"
    " pause for a moment to reconsider if you really want to do this, since you"
    " know you won't be able to get it back on the bullock-drawn caravan once it"
    " is on the ground.\n[If you are sure you want to pull the crate off your"
    " bullock-drawn caravan, repeat this command within 20 seconds.]",
    "You continue to pull at the sturdy crate.  Your driver rushes over to help"
    " you, and together you manage to pull the crate off the bullock-drawn"
    " caravan.  The crate falls to the ground with a loud **THUMP** just missing"
    " your foot.",
)


def test_a_stranded_crate_is_pushed_and_pulled_off_the_caravan(script):
    world = World(
        {
            "look bullock-drawn caravan": [
                _report(LANGENFIRTH_CRATE, FORNSTED_CRATE),
                _report(LANGENFIRTH_CRATE),
            ],
            "push second sturdy crate": [GRAB],
            "pull sturdy crate": list(PULL),
        },
        room=3155,
    )
    world.state.room_objs = "a bullock-drawn caravan with a couple of things on it"
    held = [_contract(*LANGENFIRTH_CRATE), _contract(*FORNSTED_CRATE)]
    assert script.unload(world, "bullock-drawn caravan", held) == 1
    assert world.sent == [
        "look bullock-drawn caravan",
        "push second sturdy crate",
        "pull sturdy crate",
        "pull sturdy crate",
        "look bullock-drawn caravan",
    ]
    assert not any(c.startswith("drop") for c in world.sent)
    assert "trade: the Therenborough crate for Fornsted taken off the caravan" in (
        world.echoed
    )


def test_a_crate_still_listed_after_the_pulls_is_kept_and_said(script):
    world = World(
        {
            "look bullock-drawn caravan": [_report(FORNSTED_CRATE)],
            "push first sturdy crate": [GRAB],
            "pull sturdy crate": [PULL[0]],
        }
    )
    assert (
        script.unload(world, "bullock-drawn caravan", [_contract(*FORNSTED_CRATE)]) == 0
    )
    assert world.sent.count("push first sturdy crate") == 1
    assert world.echoed[-1].startswith(
        "trade: the Therenborough crate for Fornsted is still on the caravan"
    )


def test_a_push_answer_it_does_not_know_pulls_nothing(script):
    world = World(
        {
            "look bullock-drawn caravan": [_report(FORNSTED_CRATE)],
            "push first sturdy crate": ["Push what?"],
        }
    )
    assert (
        script.unload(world, "bullock-drawn caravan", [_contract(*FORNSTED_CRATE)]) == 0
    )
    assert "pull sturdy crate" not in world.sent
    assert "unrecognized PUSH answer" in world.echoed[-1]


def test_no_crate_comes_off_beside_another_traders_caravan(script):
    # The Crossing's outpost, 2026-10-15: another Trader's caravan beside ours.
    world = World({"look bullock-drawn caravan": [_report(FORNSTED_CRATE)]})
    world.state.room_objs = (
        "a scorched and battered caravan pulled by shaggy yaks with several things"
        " on it, a bullock-drawn caravan with a couple of things on it"
    )
    assert (
        script.unload(world, "bullock-drawn caravan", [_contract(*FORNSTED_CRATE)]) == 0
    )
    assert world.sent == []


def test_a_stop_takes_the_stranded_crate_off_before_the_bin(script):
    world = World({})
    lapsed = trade.Contract("Therenborough", None, None, None, None, False, True)
    fake = Circuit(
        script,
        stops=[[lapsed, _contract(*FORNSTED_CRATE)._replace(origin="Langenfirth")]],
        taken=[_contract("Therenborough", "Langenfirth")],
        minutes=THEREN_MINUTES,
    )
    script.walk = lambda s, db, room, describe: fake.record("walk", room)
    script.unload = lambda s, name, contracts: fake.record("unload", name)
    script.put_away = lambda s, db, place, contracts: fake.record("bin", place) and 0
    script.circuit(world, MAP, "sleek caravan", "Therenborough", False, [])
    calls = [call[0] for call in fake.calls]
    assert calls.index("unload") < calls.index("bin")
    assert ("walk", 3155) in fake.calls[: calls.index("unload")]
    assert ("unload", "sleek caravan") in fake.calls


def test_a_restart_beside_a_caravan_carrying_nothing_deliverable_stops_here(script):
    # Langenfirth, 01:13 on 2026-10-18: the Fornsted crate pulled off, its
    # contract still read presented, and the restart held for an expiry
    # instead of taking Langenfirth's contract.
    world = World({})
    fake = Circuit(
        script,
        stops=[
            [
                _contract(*FORNSTED_CRATE),
                _contract("Riverhaven", "Fornsted", presented=False),
            ]
        ],
        taken=[_contract("Langenfirth", "Therenborough")],
        minutes={("Langenfirth", "Therenborough"): 6.0},
    )
    script.circuit(world, MAP, "sleek caravan", "Langenfirth", True, [])
    assert fake.calls[0] == ("bring", 3407)
    assert ("take", "Langenfirth") in fake.calls
    assert not any("holding at" in e for e in world.echoed)


def test_a_stop_with_nothing_stranded_never_looks_at_the_caravan(script):
    world = World({})
    fake = Circuit(
        script,
        stops=[[_contract(*LANGENFIRTH_CRATE)]],
        minutes={("Riverhaven", "Langenfirth"): 30.0},
    )
    script.province = lambda place: ("Riverhaven",)
    script.unload = lambda s, name, contracts: fake.record("unload", name)
    script.circuit(world, MAP, "sleek caravan", "Riverhaven", False, [])
    assert not any(call[0] == "unload" for call in fake.calls)


def test_a_circuit_from_therenborough_never_heads_past_the_forest(script):
    # 2026-10-18: the caravan stayed behind Ker'Leor's first fallen tree.
    world = World({})
    fake = Circuit(
        script,
        stops=[[_contract("Riverhaven", "Langenfirth")]],
        taken=[_contract("Therenborough", "Riverhaven")],
    )
    script.circuit(world, MAP, "sleek caravan", "Therenborough", False, [])
    legs = [call[2] for call in fake.calls if call[0] == "leg"]
    assert legs and not set(legs) & {"Fornsted", "Hvaral", "Muspar'i"}


def test_a_lead_on_the_arnshal_road_turned_down_starts_at_its_ends(script):
    # Elanthipedia (Trade Route): Keep Entrance to Hvaral, past the
    # passport gate; Mountain Approach to Fornsted.
    calls = _forfedhdar(script, refused={"Hvaral", "Fornsted"})
    world = World({})
    assert script.leg(world, MAP, "caravan", "Fornsted", "Hvaral")
    assert calls == [
        ("lead", "Hvaral"),
        ("bring", 3706),
        ("lead", "Hvaral"),
        ("bring", 3751),
    ]
    calls.clear()
    assert script.leg(world, MAP, "caravan", "Hvaral", "Fornsted")
    assert calls == [
        ("lead", "Fornsted"),
        ("bring", 3764),
        ("lead", "Fornsted"),
        ("bring", 3693),
    ]


def test_muspari_has_no_lead_the_caravan_is_walked_over_the_sand_barge(script):
    calls = _forfedhdar(script)
    world = World({})
    assert script.leg(world, MAP, "caravan", "Hvaral", "Muspar'i")
    assert calls == [("bring", 14282)]


def test_the_sand_barge_and_arnshals_gate_are_steps_the_walker_rides():
    assert haul.steps(MAP.path(3766, [6872])) == [(haul.SANDBARGE, "hvaral")]
    assert haul.steps(MAP.path(3698, [3706])) == [(haul.GATE, "")]


def test_the_caravan_rides_the_sand_barge_and_follows_off_it(script):
    world = World(CROSSING_ANSWERS, room=3766)

    def ride_sandbarge(s, start=""):
        s.sent.append(f"(the sand barge from {start})")
        s.landing = 6872
        return "landed"

    script.walker.ride_sandbarge = ride_sandbarge
    script.walker.SANDBARGE_LEAVE = walker.SANDBARGE_LEAVE
    assert script.bring(world, MAP, "weathered caravan", 6872)
    assert [c for c in world.sent if c.startswith(("tell", "go ", "(the"))] == [
        "tell weathered caravan to follow",
        "(the sand barge from hvaral)",
        "tell weathered caravan to follow",  # trade.lic's, as the bargeman signals
        "go platform",
        "tell weathered caravan to wait",
    ]


def test_an_expired_passport_is_fetched_while_the_caravan_waits_at_the_gate(
    script,
):
    world = World(CROSSING_ANSWERS, room=3698)
    world.landing = 3706
    shown = ["passport", "landed"]

    def show_passport(s, _=""):
        s.sent.append("(the passport shown)")
        return shown.pop(0)

    def fetch_passport(s, db):
        s.sent.append("(a passport fetched)")
        s.room = 3147  # Ibec Hall, Passport Office
        return True

    script.walker.show_passport = show_passport
    script.walker.fetch_passport = fetch_passport
    assert script.bring(world, MAP, "weathered caravan", 3706)
    assert world.walks == [3698]  # back to the gate from Ibec Hall
    assert [c for c in world.sent if c.startswith(("tell", "go ", "(", "stow"))] == [
        "tell weathered caravan to follow",
        "(the passport shown)",
        "tell weathered caravan to wait",
        "(a passport fetched)",
        "tell weathered caravan to follow",
        "(the passport shown)",
        "go gate",
        "stow passport",
        "tell weathered caravan to wait",
    ]


def test_a_contract_its_town_does_not_name_is_got_by_its_ordinal(script):
    # GET MY MUSPAR'I CONTRACT may miss, as "Fayrin's" may: with several
    # held, READ finds the one for this town and GET takes it by ordinal.
    loaded = TO_MUSPARI.replace(" has yet to be presented", " was presented")
    world = World(
        {
            "get my muspar'i contract": ["What were you referring to?"],
            "read my first contract": [RIVERHAVEN_TO_THEREN],
            "read my second contract": [loaded],
            "read my third contract": ["I could not find what you were referring to."],
            "get my second contract": ["You get a Muspar'i contract from your pack."],
            "give my contract to clerk": [PAID_IN_LIRUMS],
        },
        room=14289,
    )
    script.tradelog = SimpleNamespace(log_delivery=lambda *a: None)
    assert script.deliver(world, MAP, "Muspar'i", only=False)
    assert "get my second contract" in world.sent
    assert "trade: Muspar'i paid 47,840 Lirums" in world.echoed


def test_contracts_put_away_are_not_counted_as_held(script):
    # Therenborough, 23:36 on 2026-10-17: two binned, "4 contract(s) held".
    world = World({})
    expired = _contract("Langenfirth", "Hvaral", False)._replace(expired=True)
    crate = _contract("Riverhaven", "Langenfirth")
    Circuit(
        script,
        stops=[[expired, crate], [crate]],
        taken=[_contract("Therenborough", "Riverhaven")],
        minutes={
            ("Therenborough", "Langenfirth"): 6.0,
            ("Therenborough", "Riverhaven"): 7.5,
        },
    )
    script.put_away = lambda s, db, place, contracts: 1
    script.circuit(world, MAP, "sleek caravan", "Therenborough", False, [])
    assert any(e.startswith("trade: 2 contract(s) held") for e in world.echoed)


# 23:42 on 2026-10-17: two Fornsted contracts issued, unloaded, before
# Fornsted was routed; the restart led an empty caravan toward Fornsted.


def test_a_contract_never_loaded_is_business_at_its_origin(script):
    world = World({})
    unloaded = _contract("Riverhaven", "Fornsted", presented=False)
    fake = Circuit(
        script,
        stops=[[unloaded]],
        taken=[_contract("Langenfirth", "Therenborough")],
        minutes={
            ("Langenfirth", "Riverhaven"): 13.0,
            ("Langenfirth", "Therenborough"): 6.0,
        },
    )
    script.province = lambda place: ("Riverhaven", "Therenborough", "Langenfirth")
    script.circuit(world, MAP, "sleek caravan", "Langenfirth", False, [])
    # Therenborough has a crate due; Riverhaven, the unloaded contract's
    # origin, is business too, and Fornsted is not.
    assert fake.calls[-1] == ("leg", "Langenfirth", "Therenborough")
    assert not any(
        call[:1] == ("leg",) and call[2] == "Fornsted" for call in fake.calls
    )


def test_the_unloaded_contract_is_loaded_at_its_origins_stop(script):
    world = World({})
    unloaded = _contract("Riverhaven", "Langenfirth", presented=False)
    fake = Circuit(
        script,
        stops=[[unloaded]],
        minutes={("Riverhaven", "Langenfirth"): 30.0},
    )
    script.province = lambda place: ("Riverhaven",)
    script.circuit(world, MAP, "sleek caravan", "Riverhaven", False, [])
    assert fake.calls[0] == ("load", "Riverhaven")
    assert fake.calls[-1] == ("leg", "Riverhaven", "Langenfirth")
    assert any("1 crate(s) for it" in e for e in world.echoed)


def test_a_restart_beside_an_empty_caravan_brings_it_in_first(script):
    world = World({})
    fake = Circuit(
        script,
        stops=[[_contract("Therenborough", "Langenfirth", presented=False)]],
        minutes={("Therenborough", "Langenfirth"): 30.0},
    )
    script.province = lambda place: ("Therenborough",)
    script.circuit(world, MAP, "sleek caravan", "Therenborough", True, [])
    assert fake.calls[:2] == [("bring", 3155), ("load", "Therenborough")]


def test_the_one_contract_run_hands_an_unloaded_one_to_the_circuit(script):
    elsewhere = TO_MUSPARI.replace("Muspar'i requires", "Fornsted requires")
    world = World(dict(LEG, **{"read my contract": [elsewhere]}), room=13751)
    circled = []
    script.circuit = lambda s, db, name, place, beside, training: circled.append(place)
    script.main(world)
    assert circled == ["Riverhaven"]
    assert "give my contract to clerk" not in world.sent


class Brambles:
    """Ker'Leor's bramble passage west of Therenborough (2026-10-17): WEST
    walks you on for two minutes, the caravan arriving only after its end
    line, which this releases once that line is waited for."""

    END = (
        "Just when it seems you will never reach the end of the road, you trek"
        " through a patch of brush to your destination...\n"
    )

    def __init__(self):
        self.sent, self.echoed, self.lines, self.room = [], [], [], 3631
        self.state = SimpleNamespace(name="Lanival", room_objs="")

    def put(self, command):
        self.sent.append(command)
        if command == "west":
            self.room = 3634
            self.lines = ["You squeeze through the brambles and trek west.\n"]

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        if self.room == 3634 and any(p.startswith("Just") for p in patterns):
            self.lines += [
                self.END,
                "Your sleek caravan arrives from the east, following you.\n",
            ]
        while self.lines:
            line = self.lines.pop(0)
            if any(re.search(p, line) for p in patterns):
                return line
        return None

    def clear(self):
        pass

    def waitrt(self):
        pass

    def echo(self, text):
        self.echoed.append(text)


def test_a_caravan_is_waited_for_at_the_end_of_a_passage(script, monkeypatch):
    forest = MapDB(
        [
            {"id": 3631, "uid": [3631], "title": ["[Therenborough Road]"],
             "wayto": {"3634": ";e fput 'west';waitfor 'Just when it seems you will never reach'"}},
            {"id": 3634, "uid": [3634], "title": ["[Ker'Leor, Deep Forest Path]"],
             "wayto": {}},
        ]
    )  # fmt: skip
    monkeypatch.setattr(
        haul, "ask", lambda s, command: "You pass on the order to follow"
    )
    world = Brambles()
    assert haul.bring(world, forest, "sleek caravan", 3634, "trade")
    assert world.sent == ["west"]
    assert world.echoed == []


def test_an_engaged_walk_retreats_before_each_move(script, monkeypatch):
    # Ker'Leor, 2026-10-17: the morah creepers followed and engaged at
    # every room, and a bare move answered "You are engaged to a morah
    # creeper at melee range!".
    forest = MapDB(
        [
            {"id": 3634, "uid": [3634], "title": ["[Ker'Leor, Deep Forest Path]"],
             "wayto": {"3635": "north"}},
            {"id": 3635, "uid": [3635], "title": ["[Ker'Leor, Deep Forest Path]"],
             "wayto": {}},
        ]
    )  # fmt: skip
    monkeypatch.setattr(
        haul, "ask", lambda s, command: "You pass on the order to follow"
    )
    world = World({}, room=3634)
    world.state.hostiles = {"207866039": False}
    world.state.posture = "standing"

    def put(command):
        world.sent.append(command)
        if command == "north":
            world.room = 3635
            world.heard.append(
                "Your sleek caravan arrives from the south, following you.\n"
            )

    world.put = put
    assert haul.bring(world, forest, "sleek caravan", 3635, "trade")
    assert world.sent == ["retreat", "retreat", "north"]


def test_a_recall_refused_in_combat_is_asked_again_after_retreating(script):
    world = World(
        {
            "recall caravan": [
                "You are far too occupied by present matters to search your memory.",
                NO_CARAVAN,
            ],
            "rent caravan": [RENT_SHORT],
        }
    )
    script.main(world)
    assert world.sent[:4] == ["recall caravan", "retreat", "retreat", "recall caravan"]


def test_interprovince_reads_past_contracts_it_cannot_carry(script):
    # 2026-10-18: Dijkstra held three ministers' contracts for Fornsted,
    # and ;trade interprovince stopped on the first one READ found.
    fornsted = TO_MUSPARI.replace("Muspar'i requires", "Fornsted requires")
    answers = dict(
        LEG,
        **{
            "read my contract": [fornsted, FROM_RIVERHAVEN],
            "read my first contract": [fornsted],
            "read my second contract": [fornsted],
            "read my third contract": ["I could not find what you were referring to."],
            "give my contract to clerk": [LOADED],
            "ask broker": [RIVERHAVEN_BROKER],
        },
    )
    world = World(answers, room=13751)
    world.args = ["interprovince"]
    legs = []
    script.shop = SimpleNamespace(afford=lambda *a, **k: True)
    script.leg = lambda s, db, name, origin, destination, *rest: (
        legs.append((origin, destination)) and False
    )
    script.main(world)
    assert "ask broker for contract" in world.sent
    assert legs == [("Riverhaven", "Shard")]
    assert not any("deliver it yourself" in e for e in world.echoed)


def test_go_takes_the_caravan_to_a_town_and_stops(script):
    # 2026-10-18: Riverhaven's broker blocked, the caravan taken empty to
    # Shard's broker.
    world = World(LEG)
    world.args = ["go", "wolf", "clan"]
    legs = []
    script.leg = lambda s, db, name, origin, destination, *rest: (
        legs.append((origin, destination)) or True
    )
    script.main(world)
    assert legs == [("Crossing", "Wolf Clan")]
    assert "give bullock-drawn caravan" in world.sent  # fed first
    assert "ask minister for contract" not in world.sent
    assert world.echoed[-1] == "trade: the caravan waits at the Wolf Clan outpost"


def test_go_to_a_town_with_no_caravan_way_leads_nowhere(script):
    world = World(LEG)
    world.args = ["go", "fornsted"]
    legs = []
    script.leg = lambda s, db, name, origin, destination, *rest: legs.append(origin)
    script.main(world)
    assert legs == []
    assert world.echoed[-1] == "trade: no caravan way from Crossing to fornsted"
