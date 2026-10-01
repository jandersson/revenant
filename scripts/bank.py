"""Bank the purse — exchange the foreign coins, deposit all:  ;bank

    ;bank              WEALTH, then the money-changer for every foreign currency (EXCHANGE ALL ... TO the province's coin), then the teller (DEPOSIT ALL); stays at the bank
    ;bank back         ... and walk back to where you started
    ;bank keep=500     leave that many copper of the province's coin in the purse (for a tithe, a fee); 0 by default
                       an empty purse with a keep walks to the teller and withdraws it (a kit to buy, 2026-09-22)

Coins weigh, and a hunt's takings and the far towns' change pile up
(the operator, 2026-09-20: a bank loop in ;train "will reduce
encumbrance"). WEALTH says what the purse holds; every currency that
is not the province's own — the coin of the teller the walk ends at
(Kronars in Zoluren, Lirums in Therengia and Qi'Reshalia, Dokoras in
Ilithi and Forfedhdar; client/game/bank.py) — is exchanged at the
nearest room of that province the map tags
`exchange` (Elanthipedia: Exchange command — "You hand your money to
the money-changer.  After collecting a modest fee, he hands you 8
silver, and 6 copper Kronars.", captured 2026-09-20), then everything
goes to the nearest teller (`bank`) with DEPOSIT ALL (Elanthipedia:
Deposit command; the clerk "records the deposit in her ledger"). With
nothing foreign the money-changer is skipped; with nothing at all
nothing is walked. A foreign coin under the changer's minimum (10
copper: "A transaction that small isn't worth my time.") stays in the
purse, said once. After the teller, ;wealth reports the bank's figures
(BANK ACCOUNT, logged to history.db) — told `now` when it runs,
started for one report when not. `keep=N` withdraws N copper back after the deposit
so a tithe or a trainer's fee is still in the purse (Elanthipedia:
Withdraw command). In ;train a task `{"script": "bank"}` with no
skills runs it once per cycle (client/game/bank.py is the model).
Stops on death. Stop with:  ;stop bank.
"""

from client.game import travel
from client.game.act import ask
from client.game.bank import (
    deposit,
    exchange_each,
    foreign,
    home_currency,
    nearest,
    room_currency,
    small_change,
)
from client.game.mapdb import MapDB
from client.game.money import parse_wealth, split
from client.game.walker import character_ranks, locate, walk


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
    the province's; False when no exchange is on the map or reachable.
    A changer of the home province is walked to when the map has one."""
    changers = mapdb.rooms_tagged("exchange")
    changers = [room for room in changers if room_currency(mapdb, room) == home] or (
        changers
    )
    if not travel.go(s, set(changers), "the money-changer", db=mapdb, walk=walk_fn):
        s.echo("bank: could not reach a money-changer — the foreign coins stay")
        return False
    exchange_each(s, ask, "bank", currencies, home)
    return True


def withdraw_back(s, copper, home):
    """WITHDRAW `copper` of the province's coin, one denomination per
    command (Elanthipedia: Withdraw command)."""
    for count, denomination in split(copper):
        ask(s, f"withdraw {count} {denomination}")
    s.echo(f"bank: kept {copper} copper {home} in the purse")


def refresh_wealth(s):
    """The money figures fresh after a deposit or a withdrawal (#404,
    the operator, 2026-10-01): ;wealth asks BANK ACCOUNT now and logs
    every branch, the purse and the debt — told when it runs, started
    for one report when it does not. Not waited for."""
    if s.is_running("wealth"):
        s.tell("wealth", "now")
    elif not s.run("wealth", ["now"]):
        s.echo("bank: could not start ;wealth — the bank's figures are not refreshed")


def run(s, words, mapdb, walk_fn=walk):
    options = parse_args(words)
    start = locate(mapdb, s.state)
    # The coin is the teller's, not the starting room's: a guild hall
    # names no town, and a Riverhaven purse's Lirums were exchanged into
    # Kronars the teller would not take (2026-09-26, #342).
    tellers = mapdb.rooms_tagged("bank")
    teller = nearest(mapdb, start, tellers, character_ranks(s.state))
    if teller is not None:
        home = room_currency(mapdb, teller)
        tellers = [teller]
    else:
        home = home_currency(getattr(s.state, "room_title", "") or "")
    wealth = parse_wealth(ask(s, "wealth"))
    carried = wealth["carried"]
    small = small_change(wealth, home)
    for currency, copper in small:
        s.echo(f"bank: {copper} copper {currency} under the changer's minimum — kept")
    currencies = foreign(wealth, home)
    if not currencies and not carried.get(home.capitalize(), 0):
        empty = (
            "the purse holds only small change"
            if any(carried.values())
            else "the purse is empty"
        )
        if options["keep"] <= 0:
            s.echo(f"bank: {empty} — nothing to bank")
            return
        # Nothing to deposit, something to fetch: the keep is what the
        # purse should hold, so the teller hands it over (2026-09-22, the
        # alchemy kit; an outside WITHDRAW the session refuses, #161 —
        # the script's own is the sanctioned one).
        s.echo(f"bank: {empty} — withdrawing the {options['keep']} copper keep")
        if not travel.go(s, set(tellers), "the bank teller", db=mapdb, walk=walk_fn):
            s.echo("bank: could not reach a teller — nothing withdrawn")
            return
        withdraw_back(s, options["keep"], home)
        refresh_wealth(s)
        if options["back"] and start is not None and locate(mapdb, s.state) != start:
            if not travel.go(s, start, "where you started", db=mapdb, walk=walk_fn):
                s.echo("bank: could not walk back — you are at the bank")
        return
    if currencies:
        exchange(s, mapdb, walk_fn, currencies, home)
        if s.dead:
            return
    elif not small:
        s.echo(f"bank: nothing foreign in the purse — {home} only")
    if not deposit(s, mapdb, walk_fn, ask, "bank", tellers):
        return
    if options["keep"] > 0:
        withdraw_back(s, options["keep"], home)
    refresh_wealth(s)
    if options["back"] and start is not None and locate(mapdb, s.state) != start:
        if not travel.go(s, start, "where you started", db=mapdb, walk=walk_fn):
            s.echo("bank: could not walk back — you are at the bank")


def main(s):
    words = [str(word) for word in (s.args or [])]
    run(s, words, MapDB.load())
