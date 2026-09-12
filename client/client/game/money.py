"""Coins as the game states them — copper totals, denominations, INFO's
wealth and debt — shared by ;sheet, ;wealth and ;debt.

Every amount the game prints is a list of denominations ("1 gold, 5
silver and 1 bronze Kronars") and, in INFO, a copper total in
parentheses; a WITHDRAW takes one denomination at a time. This module
converts both ways (10000/1000/100/10/1 copper per platinum/gold/
silver/bronze/copper, per lich's common-money) and splits INFO into
carried coin and provincial debt per currency. Captured 2026-09-12:
"You owe 1 gold, 5 silver and 1 bronze Kronars to the Principality of
Zoluren. (1510 copper Kronars)".
"""

import re

COPPER_PER = {
    "platinum": 10_000,
    "gold": 1_000,
    "silver": 100,
    "bronze": 10,
    "copper": 1,
}
DENOMINATIONS = tuple(COPPER_PER)  # largest first
CURRENCIES = ("Kronars", "Lirums", "Dokoras")

_AMOUNT = re.compile(
    r"(?P<count>[\d,]+)\s+(?P<denomination>platinum|gold|silver|bronze|copper)"
)
# "11 copper Lirums (11 copper Lirums)." / "(90 copper Kronars)" — INFO
# states every holding and debt with a copper total in parentheses.
_COPPER = re.compile(r"\((\d+) copper (Kronars|Lirums|Dokoras)\)")
_DEBT_SECTION = re.compile(r"^Debt:", re.MULTILINE)


def to_copper(text):
    """The copper total of a denomination list ("1 gold, 5 silver and
    1 bronze"); 0 when the text names none."""
    total = 0
    for amount in _AMOUNT.finditer(text):
        count = int(amount.group("count").replace(",", ""))
        total += count * COPPER_PER[amount.group("denomination")]
    return total


def split(copper):
    """[(count, denomination)] for a copper total, largest coins first,
    zero counts left out: 1510 → [(1, "gold"), (5, "silver"), (1, "bronze")]."""
    parts, left = [], int(copper)
    for denomination in DENOMINATIONS:
        count, left = divmod(left, COPPER_PER[denomination])
        if count:
            parts.append((count, denomination))
    return parts


def phrase(copper, currency=""):
    """ "1 gold, 5 silver and 1 bronze Kronars" — the game's own shape."""
    parts = [f"{count} {denomination}" for count, denomination in split(copper)]
    if not parts:
        parts = ["0 copper"]
    words = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"{words} {currency}".strip()


def parse_wealth(text):
    """Carried coin and debt in copper per currency, from INFO:
    {"carried": {currency: copper}, "debt": {currency: copper}}."""
    debt_at = _DEBT_SECTION.search(text)
    at = debt_at.start() if debt_at else len(text)
    wealth = {"carried": {}, "debt": {}}
    for section, chunk in (("carried", text[:at]), ("debt", text[at:])):
        for amount, currency in _COPPER.findall(chunk):
            wealth[section][currency] = wealth[section].get(currency, 0) + int(amount)
    return wealth
