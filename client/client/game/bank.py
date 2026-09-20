"""The purse banked: which coins to EXCHANGE into the province's own and
the money-changer's and the teller's answers, behind ;bank alone —
;skins bank runs ;bank rather than a deposit of its own (the operator,
2026-09-20).

Coins weigh, and a hunt's takings and the far towns' change pile up
(the operator, 2026-09-20: a bank loop in ;train "will reduce
encumbrance"). Captured that day at the Crossing's Provincial Bank:
the Money-changer (map 1902, tagged `exchange`) — "You hand your money
to the money-changer.  After collecting a modest fee, he hands you 8
silver, and 6 copper Kronars." to EXCHANGE ALL DOKORAS TO KRONARS,
"... he hands you 2 silver, 1 bronze, and 8 copper Kronars." for the
Lirums; the Teller (1900, tagged `bank`) — "The clerk slides a small
metal box across the counter into which you drop all your Kronars.
She counts them carefully and records the deposit in her ledger." to
DEPOSIT ALL (first captured 2026-09-14 for ;skins bank). The
province's coin comes from the room title (client/game/soul.py's
`currency_for`: Dokoras in Ilithi and the islands, Lirums in
Therengia, Kronars elsewhere). Elanthipedia: Exchange command,
Deposit command, Currency.
"""

import re

from client.game.money import CURRENCIES, phrase, split
from client.game.soul import currency_for

EXCHANGED = ("hands you",)  # the money-changer's line, the new coins after it
# The teller's withdrawal line (captured 2026-09-12): "The clerk counts
# out 1 gold Kronars and hands them over, making a notation in her
# ledger." The account refusal is captured too ("you do not seem to
# have an account with us", 2026-09-11); the rest are assumptions.
COUNTED = ("counts out",)
WITHDRAW_REFUSALS = (
    "do not seem to have an account",
    "not have enough",
    "don't have enough",
    "insufficient",
    "cannot",
    "can't",
)


def withdraw(s, mapdb, walk_fn, ask, prefix, copper, currency, retry="try again"):
    """Walk to the nearest teller and WITHDRAW `copper` of `currency`, one
    denomination per command (WITHDRAW 6 silver; the teller counts in
    the province's coin). Only the teller's own lines are echoed — the
    bank is a busy room, and ;debt used to echo every arrival and
    exchange of words in its answer window as its own (the operator,
    2026-09-20). False, said, when the map has no teller, the walk
    failed or the teller refused. Shared by ;debt (the shortfall) and
    ;tdp (the trainer's fee, #247)."""
    tellers = mapdb.rooms_tagged("bank")
    if not tellers:
        s.echo(f"{prefix}: the map has no room tagged 'bank'")
        return False
    if not walk_fn(s, mapdb, set(tellers), describe="the bank teller"):
        s.echo(f"{prefix}: could not reach a teller — stopping")
        return False
    s.echo(f"{prefix}: withdrawing {phrase(copper, currency)}")
    for count, denomination in split(copper):
        answer = ask(s, f"withdraw {count} {denomination}")
        lowered = answer.lower()
        for line in answer.splitlines():
            if any(word in line.lower() for word in COUNTED + WITHDRAW_REFUSALS):
                s.echo(f"{prefix}: {line.strip()}")
        if any(needle in lowered for needle in WITHDRAW_REFUSALS):
            s.echo(
                f"{prefix}: the teller refused — put the coins in your hands "
                f"(GIVE from another character) and {retry}"
            )
            return False
    return True


def home_currency(title):
    """The province's coin from the room title — soul.currency_for's rule
    (Dokoras in Ilithi and the islands, Lirums in Therengia, Kronars
    elsewhere), the same table the tithe uses."""
    return currency_for(title)


DEPOSITED = ("records the deposit",)  # the clerk's ledger line
_HANDED = re.compile(r"hands you ([^.]+)\.")


def foreign(wealth, home):
    """The currencies to exchange: every one the purse holds coins of
    that is not the province's own, in the game's order. `wealth` is
    money.parse_wealth's dict, `home` "kronars"/"lirums"/"dokoras"."""
    carried = wealth.get("carried", {})
    return [
        currency.lower()
        for currency in CURRENCIES
        if carried.get(currency, 0) > 0 and currency.lower() != home.lower()
    ]


def exchange_command(currency, home):
    return f"exchange all {currency} to {home}"


def handed(answer):
    """What the money-changer handed over ("8 silver, and 6 copper
    Kronars"), or None when the answer was not his."""
    match = _HANDED.search(answer or "")
    return match.group(1).strip() if match else None


def deposit(s, mapdb, walk_fn, ask, prefix):
    """Walk to the nearest teller and DEPOSIT ALL: the clerk's ledger
    line is reported as a deposit, any other answer echoed line by
    line. False when no teller is on the map or reachable — the coins
    stay in the purse (#196)."""
    tellers = mapdb.rooms_tagged("bank")
    if not tellers:
        s.echo(f"{prefix}: the map has no room tagged 'bank' — the coins stay with you")
        return False
    if not walk_fn(s, mapdb, set(tellers), describe="the bank teller"):
        s.echo(f"{prefix}: could not reach a teller — the coins stay with you")
        return False
    answer = ask(s, "deposit all")
    if any(word in answer.lower() for word in DEPOSITED):
        s.echo(f"{prefix}: deposited all your coins — the clerk recorded it")
        return True
    lines = [line for line in answer.strip().splitlines() if line.strip()]
    for line in lines or ["the teller said nothing to DEPOSIT ALL"]:
        s.echo(f"{prefix}: {line}")
    return True
