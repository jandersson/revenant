"""How ;heal treats wounds with herbs — these tests are the manual.

HEALTH read into wounds, each answered by the herb table (client/game/
herbs.py): the first herb the town sells, one EAT per herb; a herb not
carried is named with its shop, and `buy` fetches coins from the
teller, ORDERs and OFFERs at the herbalist, then eats. EAT's and the
herbalist's wordings are assumptions until the first run (#198).
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _heal():
    spec = importlib.util.spec_from_file_location(
        "heal_script", REPO / "scripts/heal.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


heal = _heal()
heal.COLLECT_SECONDS = 0.01
heal.TAIL_SECONDS = 0.01

MAP = MapDB(
    [
        {"id": 100, "uid": [1], "title": ["[Town, Square]"], "wayto": {}},
        {
            "id": 8259,
            "uid": [14010],
            "title": ["[Mauriga's Botanicals, Salesroom]"],
            "tags": ["herbalist"],
            "wayto": {},
        },
        {
            "id": 1900,
            "uid": [1901],
            "title": ["[Provincial Bank, Teller]"],
            "tags": ["bank"],
            "wayto": {},
        },
    ]
)

# A circle-1 Paladin's HEALTH after an evening of badgers (2026-09-14).
HEALTH = (
    "Your body feels at full strength.\nYour spirit feels full of life.\n"
    "You have some minor abrasions to the head, some minor abrasions to the left "
    "arm, minor swelling and bruising around the left leg compounded by cuts and "
    "bruises about the left leg, some tiny scratches to the chest, some minor "
    "twitching."
)
CLEAN = "Your body feels at full strength.\nYour spirit feels full of life.\nYou have no significant injuries."
# Captured 2026-09-14 on the first ;heal buy at Mauriga's Botanicals.
ATE = "You eat a portion of a nemoih root."
MISSING = "What were you referring to?"
INFO_BROKE = "Wealth:\n  No Kronars.\n  No Lirums.\n  No Dokoras.\n"
QUOTE = (
    'Mauriga says, "That is a very wise selection.  I can give the root to you '
    'for 812 kronars."'
)
SOLD = "Mauriga smiles as she hands you your purchase."
ON_COUNTER = (
    SOLD + "\nMauriga notices that your hands are full, and places it on the "
    "counter instead."
)
NO_STOCK = (
    "Mauriga says, \"I'm so sorry to disappoint you, but I don't have that "
    'reagent in stock."'
)


class Fake:
    def __init__(self, answers):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.commands = []
        self.walks = []
        self.pending = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(name="Lanival", room=100)

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if queue else ""
                self.pending = [line + "\n" for line in text.splitlines()]
                return

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def command(self, timeout=None):
        return self.commands.pop(0) if self.commands else None

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    return True


def test_the_arguments_are_a_mode_and_a_floor():
    assert heal.parse_args([]) == {"mode": "eat", "floor": "insignificant"}
    assert heal.parse_args(["buy", "floor=minor"]) == {"mode": "buy", "floor": "minor"}


def test_list_names_a_herb_and_its_shop_for_every_wound_and_eats_nothing():
    s = Fake({"health": [HEALTH]})
    reason, eaten = heal.run(s, heal.parse_args(["list"]))
    assert (reason, eaten) == ("listed", [])
    assert s.sent == ["health"]
    lines = "\n".join(s.echoed)
    assert (
        "jadice flower for left arm external insignificant; left leg external minor"
        in lines
    )
    assert "nemoih root for head external insignificant" in lines
    assert "yelith root for left leg internal minor" in lines
    assert "Mauriga's Botanicals" in lines
    # The chest's tiny scratches sit under the default floor? No —
    # negligible is above insignificant, so plovik is named too.
    assert "plovik leaves for chest external negligible" in lines


def test_one_eat_per_herb_and_the_missing_ones_named_with_their_shop():
    s = Fake({"health": [HEALTH], "eat my jadice flower": [ATE], "eat": [MISSING] * 9})
    reason, eaten = heal.run(s, heal.parse_args([]))
    assert reason == "done"
    assert eaten == ["jadice flower"]
    eats = [c for c in s.sent if c.startswith("eat")]
    assert eats.count("eat my jadice flower") == 1  # two limb wounds, one herb
    # The wiki's shop table puts nemoih at the Alchemy Society (its
    # store names carry the town twice, as generated).
    assert any("no nemoih root carried — Alchemy Society" in t for t in s.echoed)
    assert any("no yelith root carried — Mauriga's Botanicals" in t for t in s.echoed)
    # The skin's twitching: aloe leaves, which no shop in town stocks.
    assert any(
        "no aloe leaves carried — no shop the table knows" in t for t in s.echoed
    )
    assert not any("unrecognized" in t for t in s.echoed)


def test_a_floor_leaves_the_light_wounds_alone_and_clean_health_is_said():
    s = Fake({"health": [HEALTH], "eat": [ATE] * 9})
    heal.run(s, heal.parse_args(["floor=minor"]))
    eats = [c for c in s.sent if c.startswith("eat")]
    assert eats == ["eat my jadice flower", "eat my yelith root", "eat my aloe leaves"]
    s = Fake({"health": [CLEAN]})
    assert heal.run(s, heal.parse_args([])) == ("no wounds", [])


def test_buy_fetches_the_shortfall_orders_offers_and_eats(travel_map=MAP):
    s = Fake(
        {
            "health": [HEALTH],
            "eat": [MISSING] * 5 + [ATE] * 5,
            "info": [INFO_BROKE],
            "withdraw": ["The clerk counts out some coins and hands them over."] * 6,
            "order": [QUOTE] * 5,
            "offer": [SOLD] * 5,
        }
    )
    reason, eaten = heal.run(s, heal.parse_args(["buy"]), mapdb=MAP, walk_fn=walk)
    assert reason == "done"
    assert s.walks == [{1900}, {8259}]
    withdrawn = [c for c in s.sent if c.startswith("withdraw")]
    assert withdrawn  # the wiki-priced estimate, largest coins first
    # ORDER by the stem (her "plovik leaf" refused "plovik leaves"),
    # then eat and stow at once so a hand stays free for the next.
    at = s.sent.index("order jadice")
    assert s.sent[at : at + 4] == [
        "order jadice",
        "offer 812",
        "eat my jadice",
        "stow my jadice",
    ]
    # Aloe leaves are on no Crossing catalog: said so, never ordered.
    assert sorted(eaten) == sorted(
        ["jadice flower", "nemoih root", "plovik leaves", "yelith root"]
    )
    assert sum("bought" in t for t in s.echoed) == 4
    assert any("aloe leaves is not sold to eat" in t for t in s.echoed)


def test_a_purchase_set_on_the_counter_is_fetched_and_one_out_of_stock_is_said():
    s = Fake(
        {
            "health": [HEALTH],
            "eat": [MISSING] * 5 + [ATE] * 5,
            "info": ["Wealth:\n  9 gold Kronars (9000 copper Kronars).\n"],
            "order": [NO_STOCK, QUOTE, QUOTE, QUOTE, NO_STOCK],
            "offer": [SOLD, ON_COUNTER, SOLD],
        }
    )
    reason, eaten = heal.run(s, heal.parse_args(["buy"]), mapdb=MAP, walk_fn=walk)
    assert s.walks == [{8259}]  # coins enough: no teller
    assert any(c.endswith(" from counter") for c in s.sent)
    assert len(eaten) == 3
    # Four herbs ordered (aloe is on no catalog): one out of stock.
    assert sum("not in stock here" in t for t in s.echoed) == 1
    assert sum("no " in t and " carried" in t for t in s.echoed) == 2


def test_a_herb_no_store_sells_to_eat_is_said_and_never_walked_for():
    # 2026-09-20: scars only — genich stem, nuloe stem and the rest come
    # from the Alchemy Society's dried lots, crafting stock, and the run
    # walked to Mauriga's and ORDERed all of them out of stock.
    scars = (
        "Your body feels at full strength.\nYour spirit feels full of life.\n"
        "You have a few nearly invisible scars along the neck, a constant "
        "twitching in the left arm, a few nearly invisible scars along the abdomen."
    )
    s = Fake({"health": [scars], "eat": [MISSING] * 5})
    reason, eaten = heal.run(s, heal.parse_args(["buy"]), mapdb=MAP, walk_fn=walk)
    assert reason == "done" and eaten == []
    assert s.walks == []  # no teller, no herbalist
    assert not any(c.startswith("order") for c in s.sent)
    assert sum("not sold to eat in the Crossing" in t for t in s.echoed) >= 2
    assert not any("(Crossing) (Crossing)" in t for t in s.echoed)
    assert heal.store_tag("jadice flower") == "herbalist"
    assert heal.store_tag("genich stem") is None


def test_a_quote_above_the_purse_is_skipped_and_said():
    s = Fake(
        {
            "health": [HEALTH],
            "eat": [MISSING] * 5,
            "info": ["Wealth:\n  9 silver Kronars (900 copper Kronars).\n"],
            "withdraw": ["The clerk counts out some coins and hands them over."] * 6,
            "order": [QUOTE.replace("812", "5000")] * 5,
        }
    )
    heal.run(s, heal.parse_args(["buy"]), mapdb=MAP, walk_fn=walk)
    assert not any(c.startswith("offer") for c in s.sent)
    assert sum("skipped" in t for t in s.echoed) == 4  # aloe never quoted


def test_bleeding_is_pointed_at_tend_and_an_unknown_eat_answer_is_reported():
    bleeding = (
        HEALTH
        + "\n\nBleeding\n     Area       Rate\n-----------------------\n     l. leg     light\n"
    )
    s = Fake({"health": [bleeding], "eat": ["Something strange happens."] * 9})
    reason, eaten = heal.run(s, heal.parse_args([]))
    assert any(";tend first" in t for t in s.echoed)
    assert eaten  # an unknown answer still counts as eaten
    assert any("unrecognized eat answer" in t for t in s.echoed)


def test_return_and_death_end_the_run():
    s = Fake({"health": [HEALTH], "eat": [ATE] * 9})
    s.commands = ["return"]
    assert heal.run(s, heal.parse_args([])) == ("returning on request", [])
    s = Fake({"health": [HEALTH]})
    s.dead = True
    assert heal.run(s, heal.parse_args([]))[0] == "you are dead"


@pytest.mark.parametrize(
    "area, expected",
    [("left arm", "limb"), ("right foot", "limb"), ("head", "head"), ("skin", "skin")],
)
def test_limbs_fold_into_the_herb_tables_limb(area, expected):
    assert heal.herb_area(area) == expected
