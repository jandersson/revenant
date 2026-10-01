"""Buying (#407): the quote read, the sale closed the shop's way, the
purse topped up first — one buy() and one afford() for the four
scripts that each wrote them (;remedies, ;heal, ;boxes, ;outfit).

    if shop.afford(s, ask, "remedies", need, "Kronars", db=mapdb, walk=walk):
        price = shop.buy(s, ask, "remedies", "order 7", expect="nugget")

Shops close a sale three ways, and the quote's own line says which: a
catalog merchant haggles — ORDER quotes ("I can let that go for...62
kronars", "prepared to offer it to you for 125 kronars"), OFFER
<amount> buys, and a second ORDER answers "We're still dealing" (#234);
a society's shop sells by ORDER twice ("You can purchase a coal nugget
for 120 Kronars. Just order it again and we'll see it done!"); a plain
shop takes BUY (;outfit's Tobb's: outside buy(), its answer judged by
client/game/outfit.py). A quote left open blocks every ORDER ("one
negotiation at a time"): buy() REFUSEs it and asks again. A purchase
the merchant "places on the counter" is taken from it.
"""

import re

from client.game import act, bank, money, travel, walker

# The quote: the item (when the merchant names it) and the price, in
# copper of the shop's coin, whatever the merchant's phrasing.
_QUOTES = (
    re.compile(
        r"you can purchase (?P<item>.+?) for (?P<price>[\d,]+) "
        r"(?P<currency>kronars|lirums|dokoras)",
        re.IGNORECASE,
    ),
    re.compile(
        r"offer it to you for (?P<price>[\d,]+) (?P<currency>kronars|lirums|dokoras)",
        re.IGNORECASE,
    ),
    re.compile(
        r"let that go for\s*\.*\s*(?P<price>[\d,]+) (?P<currency>kronars|lirums|dokoras)",
        re.IGNORECASE,
    ),
)
# The last resort, any "N kronars" in the answer: a bystander's line
# could carry one, which is why the merchant's own phrasings go first.
_ANY_PRICE = re.compile(
    r"(?P<price>\d[\d,]*)\s*(?P<currency>kronars|lirums|dokoras)", re.I
)

ORDER_AGAIN = ("order it again",)  # a society's shop: the second ORDER buys
OPEN_ORDER = ("one negotiation at a time", "already ordered something")
OUT_OF_STOCK = ("don't have that reagent", "not in stock", "don't carry")
BOUGHT = (
    "takes some coins from you and hands you",  # a society's shop
    "hands over your",  # Ragge's
    "hands you your purchase",
    "take your",
    "hands you",
    "here you go",
)
COUNTER = ("places it on the counter",)
SALE_REFUSED = ("don't have enough", "not enough", "can't afford", "insufficient")


def quote(answer):
    """(item, price) from an ORDER's answer — the item lowered, "" when
    the merchant names none; the price in copper — or None when the
    answer quotes nothing."""
    for pattern in _QUOTES:
        match = pattern.search(answer or "")
        if match:
            item = (match.groupdict().get("item") or "").strip().lower()
            return item, int(match.group("price").replace(",", ""))
    match = _ANY_PRICE.search(answer or "")
    return ("", int(match.group("price").replace(",", ""))) if match else None


def buy(s, ask, prefix, order, *, expect=None, purse=None, max_price=None, noun=None):
    """ORDER (the `order` command), the quote checked — against `expect`
    (a word the quoted item must carry), `purse` and `max_price` (copper)
    — and the sale closed the shop's way; the price paid, or None said
    when the shop kept the item. A purchase left on the counter is got
    from it by `noun` (the quoted item's last word by default)."""
    answer = ask(s, order)
    lowered = answer.lower()
    if any(word in lowered for word in OPEN_ORDER):
        ask(s, "refuse")  # a quote left open blocks every ORDER
        answer = ask(s, order)
        lowered = answer.lower()
    if any(word in lowered for word in OUT_OF_STOCK):
        s.echo(f"{prefix}: {order.upper()} — not in stock here")
        return None
    quoted = quote(answer)
    if quoted is None:
        s.echo(f"{prefix}: no quote for {order.upper()} — {act.said(answer)}")
        return None
    item, price = quoted
    what = item or order.upper()
    if expect and expect.lower() not in item:
        ask(s, "refuse")
        s.echo(f"{prefix}: {order.upper()} quoted {item!r}, not {expect} — refused")
        return None
    if purse is not None and price > purse:
        ask(s, "refuse")
        s.echo(
            f"{prefix}: {what} is {price} copper, more than the {purse} carried — refused"
        )
        return None
    if max_price is not None and price > max_price:
        ask(s, "refuse")
        s.echo(
            f"{prefix}: {what} is {price} copper, over the {max_price} expected — refused"
        )
        return None
    closing = (
        order if any(word in lowered for word in ORDER_AGAIN) else f"offer {price}"
    )
    answer = ask(s, closing)
    lowered = answer.lower()
    if any(word in lowered for word in SALE_REFUSED):
        ask(s, "refuse")
        s.echo(
            f"{prefix}: the shop refused {price} for {what} — {act.said(answer, SALE_REFUSED)}"
        )
        return None
    if any(word in lowered for word in COUNTER):
        ask(s, f"get {noun or (item.split()[-1] if item else 'it')} from counter")
    elif not any(word in lowered for word in BOUGHT):
        act.unknown(s, prefix, closing.upper(), answer)
    return price


def afford(
    s, ask, prefix, copper, currency="Kronars", *, db=None, walk=None, retry="try again"
):
    """True when the purse holds `copper` of `currency` (WEALTH read),
    or once the shortfall is WITHDRAWn at the nearest teller
    (bank.withdraw, which walks there and says what the teller said);
    False, said, when the teller refused or could not be reached."""
    have = money.carried(s, currency, ask)
    if have >= copper:
        return True
    return bank.withdraw(
        s,
        db or travel.mapdb(),
        walk or walker.walk,
        ask,
        prefix,
        copper - have,
        currency,
        retry=retry,
    )
