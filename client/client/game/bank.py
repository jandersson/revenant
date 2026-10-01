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
province's coin is the teller's (`room_currency`: the map room's title,
location and image read by client/game/soul.py's `currency_for` —
Dokoras in Ilithi and Forfedhdar, Lirums in Therengia and Qi'Reshalia,
Kronars in Zoluren), never the starting room's: a guild hall names no
town (#342). Elanthipedia: Exchange command, Deposit command, Currency.
"""

import re

from client.game import act, travel
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
    if not travel.go(s, set(tellers), "the bank teller", db=mapdb, walk=walk_fn):
        s.echo(f"{prefix}: could not reach a teller — stopping")
        return False
    return withdraw_here(s, ask, prefix, copper, currency, retry)


def withdraw_here(s, ask, prefix, copper, currency, retry="try again"):
    """WITHDRAW `copper` of `currency` at the teller already here, one
    denomination per command, the teller's own lines said; False, said,
    when the teller refused (#407: ;bank's keep and ;enc's ballast drew
    their coins with copies of this loop)."""
    s.echo(f"{prefix}: withdrawing {phrase(copper, currency)}")
    for count, denomination in split(copper):
        answer = ask(s, f"withdraw {count} {denomination}")
        for line in act.lines(answer):
            if any(word in line.lower() for word in COUNTED + WITHDRAW_REFUSALS):
                s.echo(f"{prefix}: {line}")
        if refused(answer):
            s.echo(
                f"{prefix}: the teller refused — put the coins in your hands "
                f"(GIVE from another character) and {retry}"
            )
            return False
    return True


def refused(answer):
    """True when the teller's answer refused a WITHDRAW."""
    lowered = str(answer or "").lower()
    return any(needle in lowered for needle in WITHDRAW_REFUSALS)


def room_currency(mapdb, room):
    """The coin of the province a map room is in: its title, the map's
    location and its image name, read by soul.currency_for — "[Barbarian
    Guild, Lower Amphitheatre]" names no town, and ;bank exchanged a
    Riverhaven purse's Lirums into Kronars on it (2026-09-26, #342)."""
    data = mapdb.rooms.get(room) or {}
    words = list(data.get("title") or [])
    words += [str(data.get("location") or ""), str(data.get("image") or "")]
    return currency_for(" ".join(words))


def nearest(mapdb, start, rooms, ranks=None):
    """The room of `rooms` a walk from `start` would end at, or None
    when there is no start or no way."""
    if start is None or not rooms:
        return None
    route = mapdb.path(start, set(rooms), ranks=ranks)
    if route is None:
        return None
    return route[-1][0] if route else start


def home_currency(title):
    """The province's coin from the room title — soul.currency_for's rule
    (Dokoras in Ilithi and the islands, Lirums in Therengia, Kronars
    elsewhere), the same table the tithe uses."""
    return currency_for(title)


DEPOSITED = ("records the deposit",)  # the clerk's ledger line
_HANDED = re.compile(r"hands you ([^.]+)\.")
# The changer's floor (captured 2026-09-28, and three times on
# 2026-09-29 on a purse's 4 copper Dokoras, #389): 'The money-changer
# says crossly, "A transaction that small isn't worth my time.  The
# minimum is one bronze or ten coppers."'
CHANGER_MINIMUM = 10  # copper
TOO_SMALL = ("isn't worth my time", "the minimum is")


def foreign(wealth, home):
    """The currencies to exchange: every one the purse holds at least the
    changer's minimum of that is not the province's own, in the game's
    order. `wealth` is money.parse_wealth's dict, `home`
    "kronars"/"lirums"/"dokoras"."""
    carried = wealth.get("carried", {})
    return [
        currency.lower()
        for currency in CURRENCIES
        if carried.get(currency, 0) >= CHANGER_MINIMUM
        and currency.lower() != home.lower()
    ]


def small_change(wealth, home):
    """(currency, copper) for each foreign coin the purse holds under the
    changer's minimum: he will not take it, so it stays in the purse."""
    carried = wealth.get("carried", {})
    return [
        (currency, carried[currency])
        for currency in CURRENCIES
        if 0 < carried.get(currency, 0) < CHANGER_MINIMUM
        and currency.lower() != home.lower()
    ]


def exchange_command(currency, home):
    return f"exchange all {currency} to {home}"


def handed(answer):
    """What the money-changer handed over ("8 silver, and 6 copper
    Kronars"), or None when the answer was not his."""
    match = _HANDED.search(answer or "")
    return match.group(1).strip() if match else None


def changer_line(answer):
    """The money-changer's own line in an answer window — one he speaks,
    or one said to the character — never a bystander's ("Cache exchanges
    some words and coins with the money-changer." was quoted as his
    answer, 2026-09-29, #389); None when the window holds none."""
    for line in (answer or "").splitlines():
        if line.strip().lower().startswith(("the money-changer", "you ")):
            return line.strip()
    return None


def exchange_each(s, ask, prefix, currencies, home):
    """EXCHANGE ALL of each currency into `home` where the character
    stands (the money-changer's room), each outcome said: the coins he
    handed over, a sum under his minimum kept, or his own line."""
    for currency in currencies:
        answer = ask(s, exchange_command(currency, home))
        got = handed(answer)
        if got:
            s.echo(f"{prefix}: exchanged your {currency} for {got}")
        elif any(word in answer.lower() for word in TOO_SMALL):
            s.echo(f"{prefix}: the {currency} are under the changer's minimum — kept")
        else:
            line = changer_line(answer)
            said = f"answered {line!r}" if line else "said nothing"
            s.echo(f"{prefix}: the money-changer {said} to the {currency}")


def deposit(s, mapdb, walk_fn, ask, prefix, tellers=None):
    """Walk to the nearest teller (of `tellers`, else every one the map
    tags) and DEPOSIT ALL: the clerk's ledger line is reported as a
    deposit, any other answer echoed line by line. False when no teller
    is on the map or reachable — the coins stay in the purse (#196)."""
    tellers = tellers or mapdb.rooms_tagged("bank")
    if not tellers:
        s.echo(f"{prefix}: the map has no room tagged 'bank' — the coins stay with you")
        return False
    if not travel.go(s, set(tellers), "the bank teller", db=mapdb, walk=walk_fn):
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
