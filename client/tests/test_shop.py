"""client.game.shop: the quote read, the sale closed the shop's way, the
purse topped up first (#407) — one buy() for the society's ORDER-twice,
the haggler's OFFER, and the counter."""

from types import SimpleNamespace

from client.game import bank, money, shop

SOCIETY_QUOTE = "You can purchase a coal nugget for 120 Kronars.  Just order it again and we'll see it done!\n"
SOCIETY_BOUGHT = "The clerk takes some coins from you and hands you a coal nugget.\n"
RAGGE_QUOTE = 'Ragge says, "I\'d be prepared to offer it to you for 125 kronars."\n'
RAGGE_BOUGHT = "Ragge hands over your ordinary lockpick.\n"
HAGGLE_QUOTE = 'The herbalist says, "I can let that go for...62 kronars."\n'
COUNTER = "The herbalist takes your coins and places it on the counter.\n"


class Fake:
    def __init__(self, answers):
        self.answers = dict(answers)
        self.sent, self.echoed = [], []

    def ask(self, s, command):
        self.sent.append(command)
        value = self.answers.get(command, "")
        if isinstance(value, list):
            return value.pop(0) if value else ""
        return value

    def echo(self, text):
        self.echoed.append(text)


def test_quote_reads_every_merchants_phrasing():
    assert shop.quote(SOCIETY_QUOTE) == ("a coal nugget", 120)
    assert shop.quote(RAGGE_QUOTE) == ("", 125)
    assert shop.quote(HAGGLE_QUOTE) == ("", 62)
    assert shop.quote("That will be 1,250 Kronars, friend.") == ("", 1250)
    assert shop.quote("We're still dealing.") is None


def test_a_societys_shop_sells_by_order_twice():
    s = Fake({"order 7": [SOCIETY_QUOTE, SOCIETY_BOUGHT]})
    assert shop.buy(s, s.ask, "remedies", "order 7", expect="nugget") == 120
    assert s.sent == ["order 7", "order 7"]
    assert s.echoed == []


def test_a_haggler_sells_by_offer_and_a_counter_purchase_is_taken():
    s = Fake({"order nilos salve": HAGGLE_QUOTE, "offer 62": COUNTER})
    assert shop.buy(s, s.ask, "heal", "order nilos salve", noun="salve") == 62
    assert s.sent == ["order nilos salve", "offer 62", "get salve from counter"]


def test_an_open_quote_is_refused_first_and_a_wrong_item_or_price_refused():
    opened = Fake(
        {
            "order ordinary lockpick": [
                "Sorry, one negotiation at a time.\n",
                RAGGE_QUOTE,
            ],
            "offer 125": RAGGE_BOUGHT,
        }
    )
    assert shop.buy(opened, opened.ask, "boxes", "order ordinary lockpick") == 125
    assert opened.sent[:3] == [
        "order ordinary lockpick",
        "refuse",
        "order ordinary lockpick",
    ]
    wrong = Fake({"order 7": SOCIETY_QUOTE})
    assert shop.buy(wrong, wrong.ask, "remedies", "order 7", expect="flower") is None
    assert wrong.sent == ["order 7", "refuse"]
    assert "quoted 'a coal nugget', not flower" in wrong.echoed[0]
    dear = Fake({"order ordinary lockpick": RAGGE_QUOTE})
    assert (
        shop.buy(dear, dear.ask, "boxes", "order ordinary lockpick", max_price=100)
        is None
    )
    assert dear.sent == ["order ordinary lockpick", "refuse"]
    short = Fake({"order 7": SOCIETY_QUOTE})
    assert shop.buy(short, short.ask, "remedies", "order 7", purse=50) is None


def test_out_of_stock_no_quote_and_a_refused_sale_are_said():
    out = Fake({"order nilos salve": "I don't carry that.\n"})
    assert shop.buy(out, out.ask, "heal", "order nilos salve") is None
    assert out.echoed == ["heal: ORDER NILOS SALVE — not in stock here"]
    silent = Fake({"order 7": "The clerk looks at you blankly.\n"})
    assert shop.buy(silent, silent.ask, "remedies", "order 7") is None
    assert silent.echoed[0].startswith("remedies: no quote for ORDER 7 — ")
    refused = Fake(
        {
            "order nilos salve": HAGGLE_QUOTE,
            "offer 62": "You don't have enough coins.\n",
        }
    )
    assert shop.buy(refused, refused.ask, "heal", "order nilos salve") is None
    assert refused.sent[-1] == "refuse"
    assert "the shop refused 62" in refused.echoed[0]


def test_an_unrecognized_closing_answer_is_reported_but_counted():
    s = Fake({"order 7": [SOCIETY_QUOTE, "Something wholly new.\n"]})
    assert shop.buy(s, s.ask, "remedies", "order 7") == 120
    assert s.echoed == [
        "remedies: unrecognized ORDER 7 answer 'Something wholly new.' — please report it"
    ]


def test_afford_reads_wealth_and_withdraws_the_shortfall(monkeypatch):
    s = Fake({"wealth": "Wealth:\n  1 silver Kronars (100 copper Kronars).\n"})
    assert shop.afford(s, s.ask, "boxes", 100) is True
    assert s.sent == ["wealth"]
    drawn = []
    monkeypatch.setattr(
        bank,
        "withdraw",
        lambda s, db, walk, ask, prefix, copper, currency, retry="": (
            drawn.append((prefix, copper, currency)) or True
        ),
    )
    assert shop.afford(
        s, s.ask, "boxes", 350, db=SimpleNamespace(), walk=lambda *a, **k: True
    )
    assert drawn == [("boxes", 250, "Kronars")]


def test_money_purse_and_carried_read_wealth():
    s = Fake(
        {
            "wealth": "Wealth:\n  2 silver, 3 bronze, and 2 copper Kronars (232 copper Kronars).\n  No Lirums.\n  No Dokoras.\n"
        }
    )
    assert money.purse(s, s.ask) == {"Kronars": 232, "Lirums": 0, "Dokoras": 0}
    assert money.carried(s, "Kronars", s.ask) == 232
    assert money.carried(s, "Lirums", s.ask) == 0
