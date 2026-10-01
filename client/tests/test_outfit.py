"""How ;outfit buys a new character's essentials (#341) — these tests are
the manual. INVENTORY's worn list says what is there; a missing
essential is bought at its shop and worn, the purse topped up at the
teller when short, and the profile set after."""

import importlib.util
import json
import pathlib
from types import SimpleNamespace

from client.game import outfit

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "outfit_script", REPO / "scripts/outfit.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

# Captured 2026-09-13 at Tobb's Smithy (Lanival's knife).
BOUGHT = (
    "You decide to purchase the knife, and pay the sales clerk 500 Kronars.\n"
    "The sales clerk hands you your skinning knife.\n"
)
ATTACHED = "You attach a small steel skinning knife with a leather-wrapped hilt to your wrist.\n"
WORN_WITH_KNIFE = (
    "Your worn items are:\n"
    "  a simple cambrinth anklet\n"
    "  a small steel skinning knife with a leather-wrapped hilt\n"
    "  a large canvas sack\n"
)
WORN_WITHOUT = "Your worn items are:\n  some doeskin leathers\n  a shoulder sack\n"
PURSE = "Wealth:\n  6 silver Kronars (600 copper Kronars).\n"
SHORT_PURSE = "Wealth:\n  1 silver Kronars (100 copper Kronars).\n"


def test_the_worn_list_says_whether_a_knife_is_already_worn():
    assert outfit.worn_items(WORN_WITH_KNIFE)[1].startswith(
        "a small steel skinning knife"
    )
    assert outfit.missing(outfit.worn_items(WORN_WITH_KNIFE)) == []
    assert [e["name"] for e in outfit.missing(outfit.worn_items(WORN_WITHOUT))] == [
        "worn skinning knife"
    ]
    assert outfit.bought(BOUGHT) and outfit.put_on(ATTACHED)
    assert not outfit.bought("You don't have enough coins to buy that.\n")


class Fake:
    def __init__(self, answers, room=1000):
        self.answers = answers  # command prefix -> answer, or a list used in turn
        self.sent, self.echoed, self.walks = [], [], []
        self.dead = False
        self.state = SimpleNamespace(name="Sable", room=room)

    def ask(self, s, command, *_):
        self.sent.append(command)
        for prefix, answer in self.answers.items():
            if command.startswith(prefix):
                if isinstance(answer, list):
                    return answer.pop(0) if len(answer) > 1 else answer[0]
                return answer
        return ""

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass


class Map:
    rooms = {1000: {}, 6206: {}, 1900: {}, 1950: {}}

    def rooms_tagged(self, tag):
        return {"bank": [1900], "exchange": [1950]}.get(tag, [])

    def resolve(self, query):
        return []  # travel.go resolves settings' avoid_rooms here (#407)


def run(fake, words=(), tmp_path=None, monkeypatch=None):
    script.ask = fake.ask  # act.ask, imported by name (#407)
    script.locate = lambda mapdb, state: state.room

    def walk(s, mapdb, goals, describe="", avoid=()):
        s.walks.append(sorted(goals))
        s.state.room = sorted(goals)[0]
        return True

    script.run(fake, list(words), Map(), walk_fn=walk)
    return "\n".join(fake.echoed)


def test_check_lists_what_is_missing_and_walks_nowhere():
    fake = Fake({"inventory": WORN_WITHOUT})
    out = run(fake, ["check"])
    assert (
        "no worn skinning knife — Tobb's Smithy at Knife Clan, 5 silver Kronars" in out
    )
    assert fake.walks == []


def test_a_missing_knife_is_bought_worn_and_the_profile_stops_fetching_one(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    (tmp_path / "sable.json").write_text(json.dumps({"skin_knife": "knife"}))
    fake = Fake(
        {
            "inventory": WORN_WITHOUT,
            "wealth": PURSE,
            "buy skinning knife": BOUGHT,
            "wear my skinning knife": ATTACHED,
        }
    )
    out = run(fake)
    assert fake.walks == [[6206], [1000]]  # the shop, then back where it started
    assert fake.sent.index("buy skinning knife") < fake.sent.index(
        "wear my skinning knife"
    )
    assert "You attach a small steel skinning knife" in out
    assert json.loads((tmp_path / "sable.json").read_text())["skin_knife"] == ""
    assert "1 of 1 bought and worn" in out


def test_a_short_purse_is_topped_up_at_the_teller_before_the_buy(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    fake = Fake(
        {
            "inventory": WORN_WITHOUT,
            "wealth": [SHORT_PURSE, PURSE],
            "withdraw": "The clerk counts out 4 silver Kronars and hands them to you.\n",
            "buy skinning knife": BOUGHT,
            "wear my skinning knife": ATTACHED,
        }
    )
    out = run(fake, ["stay"])
    assert fake.walks == [[6206], [1900], [6206]]  # shop, teller, shop; stays
    assert "withdraw 4 silver" in fake.sent
    assert "outfit: withdrawing 4 silver Kronars" in out  # shop.afford's shortfall
    assert "buy skinning knife" in fake.sent


# The changer's refusal of 4 copper Dokoras, captured 2026-09-29 (#389).
TOO_SMALL = (
    "The money-changer says crossly, \"A transaction that small isn't worth my "
    'time.  The minimum is one bronze or ten coppers."\n'
)
SMALL_CHANGE = (
    "Wealth:\n  1 silver Kronars (100 copper Kronars).\n  No Lirums.\n"
    "  4 copper Dokoras (4 copper Dokoras).\n"
)


def test_a_sum_under_the_changers_minimum_is_kept_not_counted_as_exchanged():
    # The teller refuses, the 4 copper Dokoras go to the changer, and his
    # refusal is a kept sum, not an exchange — ;outfit's own exchange loop
    # lacked #389's minimum until it went through bank.exchange_each.
    fake = Fake(
        {
            "inventory": WORN_WITHOUT,
            "wealth": SMALL_CHANGE,
            "withdraw": "You do not seem to have an account with us.\n",
            "exchange": TOO_SMALL,
        }
    )
    out = run(fake, ["stay"])
    assert fake.walks == [[6206], [1900], [1950]]  # shop, teller, changer
    assert "the teller refused" in out and "start ;outfit again" in out
    assert fake.sent.count("exchange all dokoras to kronars") == 1
    assert "outfit: the dokoras are under the changer's minimum — kept" in out
    assert "exchanged your" not in out
    assert "the purse still lacks 5 silver Kronars for the worn skinning knife" in out
    assert "buy skinning knife" not in fake.sent
    assert "0 of 1 bought and worn" in out


def test_a_refused_purchase_ends_the_run_with_the_shops_line(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    fake = Fake(
        {
            "inventory": WORN_WITHOUT,
            "wealth": PURSE,
            "buy skinning knife": 'The clerk says, "That item is not for sale."\n',
        }
    )
    out = run(fake)
    assert "wear my skinning knife" not in fake.sent
    assert "answered 'The clerk says, \"That item is not for sale.\"' — stopping" in out
    assert "0 of 1 bought and worn" in out


def test_a_character_already_wearing_one_buys_nothing():
    fake = Fake({"inventory": WORN_WITH_KNIFE})
    out = run(fake)
    assert "nothing missing" in out
    assert fake.walks == []
