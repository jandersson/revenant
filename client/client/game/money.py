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
_NONE = re.compile(r"^\s*No (Kronars|Lirums|Dokoras)\.", re.MULTILINE)
_DEBT_SECTION = re.compile(r"^Debt:", re.MULTILINE)
_SECTION = re.compile(r"^(Wealth|Debt):", re.MULTILINE)  # in either order (#266)
_NO_DEBT = re.compile(r"^\s*No debt\.", re.MULTILINE)


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
    {"carried": {currency: copper}, "debt": {currency: copper}}.
    "No Kronars." is a carried 0 and "No debt." a debt of 0 in every
    currency INFO listed — a paid debt has to reach the history as a
    zero, or the newest row stays the old debt (captured 2026-09-12).
    An INFO that never answered gives empty dicts. The sections come
    in either order: WEALTH printed Debt above Wealth on 2026-09-21
    and the purse read as empty (#266), so each header opens its own
    chunk wherever it falls, and text before the first header is the
    purse, INFO's old shape."""
    marks = list(_SECTION.finditer(text))
    chunks = [("carried", text[: marks[0].start()])] if marks else [("carried", text)]
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        section = "carried" if mark.group(1) == "Wealth" else "debt"
        chunks.append((section, text[mark.start() : end]))
    wealth = {"carried": {}, "debt": {}}
    for section, chunk in chunks:
        for amount, currency in _COPPER.findall(chunk):
            wealth[section][currency] = wealth[section].get(currency, 0) + int(amount)
        if section == "carried":
            for currency in _NONE.findall(chunk):
                wealth["carried"].setdefault(currency, 0)
    if any(_NO_DEBT.search(chunk) for section, chunk in chunks if section == "debt"):
        for currency in wealth["carried"]:
            wealth["debt"].setdefault(currency, 0)
    return wealth
