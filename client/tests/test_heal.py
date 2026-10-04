"""How ;heal treats wounds with herbs — these tests are the manual.

HEALTH read into wounds, each answered by the herb table (client/game/
herbs.py): the first herb the town sells, one EAT per herb; a herb not
carried is named with its shop, and `buy` fetches coins from the
teller (bank.withdraw), ORDERs and OFFERs at the herbalist (shop.buy),
then eats; the purse is read off WEALTH (money.purse, #407). EAT's and the
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
WEALTH_BROKE = "Wealth:\n  No Kronars.\n  No Lirums.\n  No Dokoras.\n"
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
# Captured 2026-09-25: an ORDER while a quote is still open, and REFUSE.
OPEN_ORDER = (
    "Mauriga smiles patiently and says, \"Master Lanival, you've already ordered "
    "something else.  Let's deal with one negotiation at a time, shall we?\""
)
REFUSED = (
    'Mauriga nods to you.  "Perhaps another day.  In the meantime, make sure that '
    'you eat a sicle fruit a day!"'
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
    assert heal.parse_args([]) == {
        "mode": "eat",
        "floor": "insignificant",
        "healer": "",
        "empath": "",
        "stay": False,
    }
    assert heal.parse_args(["buy", "floor=minor"]) | {} == {
        "mode": "buy",
        "floor": "minor",
        "healer": "",
        "empath": "",
        "stay": False,
    }
    assert heal.parse_args(["quentin"])["mode"] == "npc"
    assert heal.parse_args(["quentin"])["healer"] == "quentin"
    # Any other word is an Empath of your own.
    assert heal.parse_args(["riphik"])["mode"] == "empath"
    assert heal.parse_args(["riphik"])["empath"] == "Riphik"
    assert heal.parse_args(["riphik", "stay"])["stay"] is True
    assert heal.parse_args(["arthianna"])["healer"] == "arthianna"
    assert heal.parse_args(["healer=tending"])["healer"] == "tending"


# The NPC healer (#218): Shard's Quentin's Healerium and Knife Clan's
# retired Dokt, both tagged npchealer on the map; the touches and the
# demeanor gate captured 2026-09-19, the hospital lines the wiki's.
HOSPITALS = MapDB(
    [
        {"id": 100, "uid": [1], "title": ["[Town, Square]"], "wayto": {}},
        {
            "id": 8908,
            "uid": [8908],
            "title": ["[Quentin's Healerium]"],
            "image": "Ilithi, Shard.jpg",
            "tags": ["npchealer"],
            "wayto": {},
        },
        {
            "id": 6218,
            "uid": [6218],
            "title": ["[Knife Clan, Healer's Kitchen]"],
            "tags": ["dokt", "npchealer"],
            "wayto": {},
        },
        {
            "id": 8720,
            "uid": [8720],
            "title": ["[Riverhaven Hospital, Tending Chamber]"],
            "tags": ["npchealer"],
            "wayto": {},
        },
        {
            "id": 19280,
            "uid": [19280],
            "title": ["[First Bank of Ilithi, Coin Exchange]"],
            "tags": ["exchange"],
            "wayto": {},
        },
    ]
)
WEALTH_KRONARS = "Wealth:\n  2 gold, 5 silver Kronars (2500 copper Kronars).\n  No Lirums.\n  No Dokoras.\n"
CHANGED = (
    "You hand your money to the money-changer, who counts it and hands you "
    "1 gold, 7 silver, and 5 bronze Dokoras.\n"
)
WEALTH_DOKORAS = "Wealth:\n  No Kronars.\n  No Lirums.\n  8 silver, 2 bronze Dokoras (802 copper Dokoras).\n"
FRIENDLY = "You now regard empaths with a friendly demeanor.\n"
TOUCHES = (
    "You lie down.\n"
    "Quentin glances oddly at you and then touches your nervous system, "
    "snickering all the while.  After a moment it feels better.\n"
    "[72 Dokoras are taken from you.]\nRoundtime:  2 seconds.\n"
    "Quentin glances oddly at you and then touches your chest, snickering all "
    "the while.  After a moment it feels better.\n[54 Dokoras are taken from you.]\n"
    'Quentin whispers, "Just between you and me and the Queen, I think you '
    "don't really need healing.  Are you just my friend or something?\"\n"
)
PULL_AWAY = (
    "You lie down.\nThe healer Quentin looks towards you, and you pull away.\n"
    "[Change your overall DEMEANOR or your DEMEANOR towards EMPATHS if you wish "
    "the healer Quentin to heal you.]\n"
)


def test_npc_walks_to_the_healer_not_the_retired_one_and_pays_per_part(monkeypatch):
    monkeypatch.setattr(heal, "HEALER_POLL", 0.01)
    monkeypatch.setattr(heal, "HEALER_QUIET", 0.02)
    s = Fake(
        {
            "wealth": [WEALTH_DOKORAS],
            "demeanor": [FRIENDLY],
            "lie down": [TOUCHES],
            "stand": ["You stand back up.\n"],
            "health": [CLEAN],
        }
    )
    reason, eaten = heal.run(
        s, heal.parse_args(["quentin"]), mapdb=HOSPITALS, walk_fn=walk
    )
    assert (reason, eaten) == ("healed", [])
    assert s.walks == [{8908}]  # by name: not Dokt's kitchen, not Riverhaven
    assert s.sent == [
        "wealth",
        "demeanor friendly empath",
        "lie down",
        "stand",
        "health",
    ]
    assert any(
        "took 126 Dokoras for 2 part(s)" in t and "HEALTH is clean" in t
        for t in s.echoed
    )
    # His "don't really need healing" ends the visit at once (2026-09-21).
    assert any("the rest needs no healing" in t for t in s.echoed)


def test_quentin_exchanges_a_kronar_purse_into_dokoras_by_him_first(monkeypatch):
    # Cecil banks in Kronars; Quentin takes Dokoras. The province is the
    # map's town for his room ("Ilithi, Shard"), and the money-changer
    # is the one nearest him, not the one behind in the Crossing.
    monkeypatch.setattr(heal, "HEALER_POLL", 0.01)
    monkeypatch.setattr(heal, "HEALER_QUIET", 0.02)
    s = Fake(
        {
            "wealth": [WEALTH_KRONARS],
            "exchange": [CHANGED],
            "demeanor": [FRIENDLY],
            "lie down": [TOUCHES],
            "stand": ["You stand back up.\n"],
            "health": [CLEAN],
        }
    )
    reason, _ = heal.run(s, heal.parse_args(["quentin"]), mapdb=HOSPITALS, walk_fn=walk)
    assert reason == "healed"
    assert s.walks == [{19280}, {8908}]
    assert s.sent[:2] == ["wealth", "exchange all kronars to dokoras"]
    assert any(
        "exchanged your kronars for 1 gold, 7 silver, and 5 bronze Dokoras" in t
        for t in s.echoed
    )


def test_small_change_alone_is_no_fee_and_walks_to_no_money_changer():
    # #389: the changer takes 10 copper or more; 4 copper Kronars by
    # Quentin are no fee, so no walk to him either.
    s = Fake(
        {"wealth": ["Wealth:\n  4 copper Kronars (4 copper Kronars).\n  No Dokoras.\n"]}
    )
    reason, _ = heal.run(s, heal.parse_args(["quentin"]), mapdb=HOSPITALS, walk_fn=walk)
    assert reason == "no coins"
    assert s.walks == []
    assert not any(c.startswith("exchange") for c in s.sent)
    assert any("under the money-changer's minimum" in t for t in s.echoed)


def test_a_healer_who_finds_no_wound_ends_the_visit_at_once(monkeypatch):
    # Arthianna, 2026-09-21, to a patient with scars alone.
    monkeypatch.setattr(heal, "HEALER_POLL", 0.01)
    monkeypatch.setattr(heal, "HEALER_WAIT", 5.0)  # never waited out
    s = Fake(
        {
            "wealth": [WEALTH_KRONARS],
            "demeanor": [FRIENDLY],
            "lie down": [
                'You lie down.\nArthianna nudges you.  "What are you doing lying '
                'there with the wounded?" she grins.\n'
            ],
            "health": [CLEAN],
        }
    )
    hospitals = MapDB(
        [
            {
                "id": 9691,
                "uid": [9691],
                "title": ["[Arthianna's Clinic, Healing Tent]"],
                "tags": ["npchealer"],
                "wayto": {},
            }
        ]
    )
    reason, _ = heal.run(
        s, heal.parse_args(["arthianna"]), mapdb=hospitals, walk_fn=walk
    )
    assert reason == "not healed"
    assert s.sent == [
        "wealth",
        "demeanor friendly empath",
        "lie down",
        "stand",
        "health",
    ]
    assert any("the rest needs no healing" in t for t in s.echoed)


RIVERHAVEN = MapDB(
    [
        {
            "id": 7821,
            "uid": [1017303],
            "title": ["[Barbarian Guild, Lower Amphitheatre]"],
            "wayto": {"8720": "go grate"},
            "timeto": {"8720": 0.2},
        },
        {
            "id": 8720,
            "uid": [8720],
            "title": ["[Riverhaven Hospital, Tending Chamber]"],
            "tags": ["npchealer"],
            "wayto": {},
        },
        {
            "id": 1000,
            "uid": [1000],
            "title": ["[Arthianna's Clinic, Healing Tent]"],
            "image": "Zoluren, Leth Deriel.jpg",
            "tags": ["npchealer"],
            "wayto": {},
        },
        {
            "id": 19280,
            "uid": [19280],
            "title": ["[Leth Deriel, Coin Exchange]"],
            "tags": ["exchange"],
            "wayto": {},
        },
    ]
)
WEALTH_LIRUMS = (
    "Wealth:\n  No Kronars.\n  1 bronze and 3 copper Lirums (13 copper Lirums).\n"
    "  No Dokoras.\n"
)
# Captured 2026-09-26, Riverhaven's Fraethis and a purse of 13 Lirums.
ON_CREDIT = (
    "You lie down.\n"
    "Fraethis approaches you and touches you.\n"
    "Your chest tingles for a moment, then suddenly feels a bit better.  The "
    "Empath looks a bit pale.\n"
    "[Your debt to Therengia has been increased by 172 Lirums.]\n"
    "Roundtime:  1 seconds.\n"
)


def test_npc_goes_to_the_healer_nearest_and_pays_in_his_towns_coin(monkeypatch):
    # 2026-09-26: the lowest-numbered healer (Arthianna, 1000, Zoluren)
    # set the coin, the Riverhaven Barbarian's Lirums read as foreign,
    # and the visit stopped looking for a money-changer it could not
    # reach. The nearest from where he stands is Fraethis (8720), whose
    # town's coin the Lirums are: no exchange, straight to him.
    monkeypatch.setattr(heal, "HEALER_POLL", 0.01)
    monkeypatch.setattr(heal, "HEALER_QUIET", 0.02)
    s = Fake(
        {
            "wealth": [WEALTH_LIRUMS],
            "demeanor": [FRIENDLY],
            "lie down": [ON_CREDIT],
            "stand": ["You stand back up.\n"],
            "health": [CLEAN],
        }
    )
    s.state.room_uid = 1017303
    reason, _ = heal.run(s, heal.parse_args(["npc"]), mapdb=RIVERHAVEN, walk_fn=walk)
    assert reason == "healed"
    assert s.walks == [{8720}]
    assert not any(c.startswith("exchange") for c in s.sent)
    # The part paid on credit is a part healed, said as debt.
    assert any(
        "put 172 Lirums on your Therengia debt for 1 part(s)" in t for t in s.echoed
    )


def test_npc_stops_on_an_empty_purse_and_reports_a_refusal(monkeypatch):
    monkeypatch.setattr(heal, "HEALER_POLL", 0.01)
    monkeypatch.setattr(heal, "HEALER_WAIT", 0.02)
    s = Fake({"wealth": [WEALTH_BROKE]})
    reason, _ = heal.run(s, heal.parse_args(["npc"]), mapdb=HOSPITALS, walk_fn=walk)
    assert reason == "no coins" and s.walks == []
    assert any("purse is empty" in t for t in s.echoed)
    s = Fake(
        {
            "wealth": [WEALTH_DOKORAS],
            "demeanor": ["Demeanor what?\n"],
            "lie down": [PULL_AWAY],
            "health": [HEALTH],
        }
    )
    reason, _ = heal.run(s, heal.parse_args(["npc"]), mapdb=HOSPITALS, walk_fn=walk)
    assert reason == "not healed"
    assert "stand" in s.sent
    assert any("would not touch you" in t for t in s.echoed)
    assert any("unrecognized demeanor answer" in t for t in s.echoed)


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
            # plovik leaves is looked for twice: as her "plovik leaf", then
            # as the table names it
            "eat": [MISSING] * 6 + [ATE] * 5,
            "wealth": [WEALTH_BROKE],
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
    # ORDER by her catalog's whole name — the stem alone is answered
    # out of stock (#308) — then eat and stow at once so a hand stays
    # free for the next.
    at = s.sent.index("order jadice flower")
    assert s.sent[at : at + 4] == [
        "order jadice flower",
        "offer 812",
        "eat my jadice flower",
        "stow my jadice flower",
    ]
    assert "order plovik leaf" in s.sent  # the table's plovik leaves
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
            "eat": [MISSING] * 6 + [ATE] * 5,
            "wealth": ["Wealth:\n  9 gold Kronars (9000 copper Kronars).\n"],
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
    s = Fake({"health": [scars], "eat": [MISSING] * 5, "rub": [MISSING] * 5})
    reason, eaten = heal.run(s, heal.parse_args(["buy"]), mapdb=MAP, walk_fn=walk)
    assert reason == "done" and eaten == []
    assert s.walks == []  # no teller, no herbalist
    assert not any(c.startswith("order") for c in s.sent)
    assert sum("not sold to eat in the Crossing" in t for t in s.echoed) >= 2
    assert not any("(Crossing) (Crossing)" in t for t in s.echoed)
    assert heal.store_tag("jadice flower") == "herbalist"
    assert heal.store_tag("genich stem") is None


def test_a_quote_above_the_purse_is_refused_and_said():
    s = Fake(
        {
            "health": [HEALTH],
            "eat": [MISSING] * 5,
            "wealth": ["Wealth:\n  9 silver Kronars (900 copper Kronars).\n"],
            "withdraw": ["The clerk counts out some coins and hands them over."] * 6,
            "order": [QUOTE.replace("812", "5000")] * 5,
        }
    )
    heal.run(s, heal.parse_args(["buy"]), mapdb=MAP, walk_fn=walk)
    assert not any(c.startswith("offer") for c in s.sent)
    # shop.buy's line (#407): the quote REFUSEd, said with the purse.
    assert sum("more than the 3436 carried — refused" in t for t in s.echoed) == 4
    assert s.sent.count("refuse") == 4  # aloe never quoted


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


def test_a_salve_is_rubbed_a_potion_drunk_and_the_rest_eaten():
    # dr-scripts' heal-remedy.lic: salves and saps are rubbed on,
    # potions drunk. Mauriga sells the table's nilos grass as a salve.
    assert heal.product("nilos grass") == "nilos salve"
    assert heal.product("plovik leaves") == "plovik leaf"
    assert heal.product("aloe leaves") == "aloe leaves"
    assert heal.take_command("nilos salve") == "rub my nilos salve"
    assert heal.take_command("sufil sap") == "rub my sufil sap"
    assert heal.take_command("ithor potion") == "drink my ithor potion"
    assert heal.take_command("jadice flower") == "eat my jadice flower"


def test_an_order_left_open_is_refused_before_the_next():
    # Captured 2026-09-25: a quote still open blocks every ORDER until
    # REFUSE closes it.
    s = Fake(
        {
            "wealth": ["Wealth:\n  9 gold Kronars (9000 copper Kronars).\n"],
            "order": [OPEN_ORDER, QUOTE],
            "refuse": [REFUSED],
            "offer": [SOLD],
            "eat": [ATE],
        }
    )
    eaten = heal.buy(s, ["jadice flower"], MAP, walk)
    assert s.sent[s.sent.index("refuse") - 1] == "order jadice flower"
    assert s.sent.count("order jadice flower") == 2
    assert eaten == ["jadice flower"]


def test_a_bought_herbs_rest_the_store_container_refuses_goes_to_the_backpack(
    monkeypatch,
):
    # #416 (2026-10-02): with STORE HERBS set to a herb bag with no room,
    # the STOW of what is left after the eat is refused and the game
    # leaves it in hand; hands.stow puts it in the default container.
    monkeypatch.setattr(heal.hands, "_DEFAULTS", {})
    s = Fake(
        {
            "wealth": ["Wealth:\n  9 gold Kronars (9000 copper Kronars).\n"],
            "order": [QUOTE],
            "offer": [SOLD],
            "eat": [ATE],
            "stow": ["There isn't any more room in the bag for that."],
            "store": ["         Default:  a rugged backpack\n"],
            "put": ["You put your flower in your backpack."],
        }
    )
    assert heal.buy(s, ["jadice flower"], MAP, walk) == ["jadice flower"]
    assert s.sent[-3:] == [
        "stow my jadice flower",
        "store default",
        "put my jadice flower in my backpack",
    ]
    assert "the jadice flower went in the backpack — no room where STOW puts it" in (
        s.echoed
    )


def test_a_quote_above_the_purse_is_refused_not_left_open():
    s = Fake(
        {
            "wealth": ["Wealth:\n  9 gold Kronars (9000 copper Kronars).\n"],
            "order": [QUOTE.replace("812", "9500")],
            "refuse": [REFUSED],
        }
    )
    assert heal.buy(s, ["jadice flower"], MAP, walk) == []
    assert s.sent[-1] == "refuse"


def test_the_captured_rub_and_eat_answers_read_as_taken():
    # The first buy by catalog name, 2026-09-25.
    for answer in (
        "You rub a portion of some nilos salve on yourself.",
        "You eat a portion of some hulnik grass.",
    ):
        assert heal.probe.classify(answer, heal.EAT_OUTCOMES) == "ok"


class EmpathWorld:
    """The Empath's side as helper.py sees it: the registry, the login
    cache, the spawn, the wire, the room and the scripts it runs."""

    def __init__(self, sessions=(), scripts=((),)):
        self.registry = list(sessions)
        self.scripts = [list(names) for names in scripts]
        self.sent = []
        self.spawned = []
        self.clock = 0.0

    def sessions(self):
        return self.registry

    def account_for(self, name):
        return {"Uthmor": "TESTACCT", "Sable": "TESTACCT"}.get(name)

    def has_password(self, account):
        return True

    def spawn(self, name, account, parent_port=None):
        self.spawned.append(name)
        return 4260

    def own_port(self):
        return 4242

    def send(self, port, line):
        self.sent.append((port, line.split("\t", 1)[-1]))
        if line.endswith(";logout"):
            self.registry = [r for r in self.registry if r["port"] != port]
        return True

    def room_of(self, port):
        return "100"  # the Empath stands in the patient's room

    def scripts_of(self, port):
        return self.scripts.pop(0) if len(self.scripts) > 1 else self.scripts[0]

    def now(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += seconds


def patient(health):
    fake = Fake({"health": health})
    fake.state.uid = None
    return fake


def empath_call(fake, world, stay=False, monkeypatch=None):
    monkeypatch.setattr(heal, "locate", lambda db, state: 100)
    return heal.call_empath(fake, "Uthmor", stay, MAP, io=world)


def test_an_empath_of_your_own_is_logged_in_brought_and_logged_out(monkeypatch):
    # The operator, 2026-09-27: `;heal riphik` — the Empath called in
    # the way ;train calls a teacher, Sable (on the same account) given
    # ;logout first, ;empath <you> waited out, then logged out again.
    world = EmpathWorld(
        sessions=[{"port": 4243, "character": "Sable"}],
        scripts=[["empath"], ["empath"], []],
    )
    fake = patient([HEALTH, CLEAN])
    reason = empath_call(fake, world, monkeypatch=monkeypatch)
    assert reason == "Uthmor is done"
    assert world.sent[0] == (4243, ";logout")
    assert world.spawned == ["Uthmor"]
    assert (4260, ";empath lanival") in world.sent
    assert world.sent[-1] == (4260, ";logout")
    assert (4260, ";empath return") not in world.sent


def test_an_empath_running_its_own_train_is_left_to_it(monkeypatch):
    # #470: two loops would drive one character.
    world = EmpathWorld(
        sessions=[{"port": 4261, "character": "Uthmor"}], scripts=[["xp", "train"]]
    )
    fake = patient([HEALTH, CLEAN])
    reason = empath_call(fake, world, monkeypatch=monkeypatch)
    assert reason == "Uthmor is running ;train — ;stop it there first"
    assert world.sent == []


def test_an_empath_told_to_stay_or_already_in_stays_logged_in(monkeypatch):
    world = EmpathWorld(scripts=[["empath"], []])
    fake = patient([HEALTH, CLEAN])
    empath_call(fake, world, stay=True, monkeypatch=monkeypatch)
    assert (4260, ";logout") not in world.sent
    assert "heal: Uthmor stays logged in" in fake.echoed
    # One already logged in is found, used, and left as found.
    found = EmpathWorld(sessions=[{"port": 4261, "character": "Uthmor"}], scripts=[[]])
    empath_call(patient([HEALTH, CLEAN]), found, monkeypatch=monkeypatch)
    assert found.spawned == [] and (4261, ";logout") not in found.sent


def test_no_wound_calls_no_empath(monkeypatch):
    world = EmpathWorld()
    fake = patient([CLEAN])
    assert empath_call(fake, world, monkeypatch=monkeypatch) == "no wounds"
    assert world.sent == [] and world.spawned == []
