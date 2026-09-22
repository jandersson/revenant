"""Bank the purse — exchange the foreign coins, deposit all:  ;bank

    ;bank              WEALTH, then the money-changer for every foreign currency (EXCHANGE ALL ... TO the province's coin), then the teller (DEPOSIT ALL); stays at the bank
    ;bank back         ... and walk back to where you started
    ;bank keep=500     leave that many copper of the province's coin in the purse (for a tithe, a fee); 0 by default
                       an empty purse with a keep walks to the teller and withdraws it (a kit to buy, 2026-09-22)

Coins weigh, and a hunt's takings and the far towns' change pile up
(the operator, 2026-09-20: a bank loop in ;train "will reduce
encumbrance"). WEALTH says what the purse holds; every currency that
is not the province's own — Kronars in Zoluren, Lirums in Therengia,
Dokoras in Ilithi and the islands, read off the room's title
(client/game/soul.py) — is exchanged at the nearest room the map tags
`exchange` (Elanthipedia: Exchange command — "You hand your money to
the money-changer.  After collecting a modest fee, he hands you 8
silver, and 6 copper Kronars.", captured 2026-09-20), then everything
goes to the nearest teller (`bank`) with DEPOSIT ALL (Elanthipedia:
Deposit command; the clerk "records the deposit in her ledger"). With
nothing foreign the money-changer is skipped; with nothing at all
nothing is walked. `keep=N` withdraws N copper back after the deposit
so a tithe or a trainer's fee is still in the purse (Elanthipedia:
Withdraw command). In ;train a task `{"script": "bank"}` with no
skills runs it once per cycle (client/game/bank.py is the model).
Stops on death. Stop with:  ;stop bank.
"""

from client.game import probe
from client.game.bank import (
    deposit,
    exchange_command,
    foreign,
    handed,
    home_currency,
)
from client.game.mapdb import MapDB
from client.game.money import parse_wealth, split
from client.game.walker import locate, walk

COLLECT_SECONDS = 3
TAIL_SECONDS = 1.5


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def parse_args(words):
    options = {"back": False, "keep": 0}
    for word in words or []:
        lowered = str(word).lower()
        key, sep, value = lowered.partition("=")
        if lowered == "back":
            options["back"] = True
        elif sep and key == "keep" and value.isdigit():
            options["keep"] = int(value)
    return options


def exchange(s, mapdb, walk_fn, currencies, home):
    """Walk to the money-changer and EXCHANGE ALL of each currency into
    the province's; False when no exchange is on the map or reachable."""
    changers = mapdb.rooms_tagged("exchange")
    if not changers:
        s.echo("bank: the map has no room tagged 'exchange' — the foreign coins stay")
        return False
    if not walk_fn(s, mapdb, set(changers), describe="the money-changer"):
        s.echo("bank: could not reach a money-changer — the foreign coins stay")
        return False
    for currency in currencies:
        answer = ask(s, exchange_command(currency, home))
        got = handed(answer)
        if got:
            s.echo(f"bank: exchanged your {currency} for {got}")
        else:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"bank: the money-changer answered {first!r} to the {currency}")
    return True


def withdraw_back(s, copper, home):
    """WITHDRAW `copper` of the province's coin, one denomination per
    command (Elanthipedia: Withdraw command)."""
    for count, denomination in split(copper):
        ask(s, f"withdraw {count} {denomination}")
    s.echo(f"bank: kept {copper} copper {home} in the purse")


def run(s, words, mapdb, walk_fn=walk):
    options = parse_args(words)
    start = locate(mapdb, s.state)
    title = getattr(s.state, "room_title", "") or ""
    home = home_currency(title)
    wealth = parse_wealth(ask(s, "wealth"))
    carried = wealth["carried"]
    if not any(carried.values()):
        if options["keep"] <= 0:
            s.echo("bank: the purse is empty — nothing to bank")
            return
        # Nothing to deposit, something to fetch: the keep is what the
        # purse should hold, so the teller hands it over (2026-09-22, the
        # alchemy kit; an outside WITHDRAW the session refuses, #161 —
        # the script's own is the sanctioned one).
        s.echo(
            f"bank: the purse is empty — withdrawing the {options['keep']} copper keep"
        )
        tellers = mapdb.rooms_tagged("bank")
        if not tellers or not walk_fn(
            s, mapdb, set(tellers), describe="the bank teller"
        ):
            s.echo("bank: could not reach a teller — nothing withdrawn")
            return
        withdraw_back(s, options["keep"], home)
        if options["back"] and start is not None and locate(mapdb, s.state) != start:
            if not walk_fn(s, mapdb, {start}, describe="where you started"):
                s.echo("bank: could not walk back — you are at the bank")
        return
    currencies = foreign(wealth, home)
    if currencies:
        exchange(s, mapdb, walk_fn, currencies, home)
        if s.dead:
            return
    else:
        s.echo(f"bank: nothing foreign in the purse — {home} only")
    if not deposit(s, mapdb, walk_fn, ask, "bank"):
        return
    if options["keep"] > 0:
        withdraw_back(s, options["keep"], home)
    if options["back"] and start is not None and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("bank: could not walk back — you are at the bank")


def main(s):
    words = [str(word) for word in (s.args or [])]
    run(s, words, MapDB.load())
