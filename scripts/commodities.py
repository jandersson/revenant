"""Read the Traders' commodity pits and carry a good from one to another:  ;commodities

    ;commodities          walk to each pit (the Crossing, Arthe Dale, Leth Deriel), the nearest first, and read its board
    ;commodities read     read the board of the pit you stand in
    ;commodities plan     the best trade from each pit by the boards read in the last 6 hours; nothing sent
    ;commodities trade    buy the best at the nearest pit, walk the guild's pack animal to the buyer's town, sell it there
    ;commodities return   typed while it walks the pits: done after this one

What it does
  - Every board read goes into history.db's commodities table: pit, good,
    price, stock word, time.
  - trade picks the good and the buyer from this pit's board and the others'
    latest: as many units as this pit surely holds and the buyer takes short
    of Surplus! (a pit with a surplus buys none), worth 2,000 Kronars clear
    of the guild's cut. Then ORDER <n> <good> at the pit clerk (the coin
    drawn at a teller when the purse is short), RECALL CARAVAN at the outpost
    for the lent animal, TELL it TO FOLLOW room by room (by Alfren's Ferry
    for Leth Deriel), the buyer's board read again, SELL <n> <good> at its
    shipment clerk. Each trade is a row in commodity_trades.
  - A trade stopped on the way is carried on by the next ;commodities trade,
    started beside the animal.

When it stops
  - trade: once sold, the animal kept; no board here, no trade worth the walk
  - the animal not beside you at the outpost, or falling behind (said)
  - the buyer's board reading Surplus! or a price below what was paid: said,
    the goods kept on the animal
  - an ORDER or SELL answer it does not know (said); ;stop commodities at once

The pits and wordings are client/game/commodities.py's, the log
client/game/commoditylog.py's, the animal's walk client/game/haul.py's;
docs/commodities.md.
"""

from client.game import (
    commodities,
    commoditylog,
    haul,
    loop,
    probe,
    shop,
    trade,
    travel,
)
from client.game.act import ask, missing, said, unknown

_NOTES = """
Built from the pits worked by hand on 2026-10-15 (#557): all three boards
read, then 5 saffron bought at Leth Deriel (3,520 and a cut of 99), carried
on a lent auroch over Alfren's Ferry and sold at the Crossing's shipment
clerk for 3,970, and 50 diamonds bought at the Crossing (84,250 and 2,712)
and sold at Arthe Dale's for 96,950, which tipped its diamonds from Good
Stores to Surplus!. The units are sized from Elanthipedia's stock bands so
the next sale stays short of that. Not yet seen live: RECALL CARAVAN naming
a lent animal (trade.lic reads it the caravan's way), an ORDER refused for
coin or for the animal's load, SELL into a Surplus! pit, how the animal is
handed back, a two-word good's ORDER (IRON ORE). The animal was never fed
on the 45-room walk.
"""

PREFIX = "commodities"
READ_STREAMS = ("", "familiar")
READ_SECONDS = 5


def character(s):
    return getattr(getattr(s, "state", None), "name", None) or ""


def walk(s, db, room, describe):
    return travel.here(s, db) == room or travel.go(s, {room}, describe, db=db)


def read_board(s):
    """READ BOARD here, read off the familiar stream (as a contract is) and
    logged: the Board, or None, said."""
    while s.get(timeout=0, streams=READ_STREAMS) is not None:
        pass  # what came before the READ is not its answer
    s.put("read board")
    text = ""
    deadline = probe.clock() + READ_SECONDS
    while probe.clock() < deadline:
        piece = s.get(timeout=0.5, streams=READ_STREAMS)
        if piece is None:
            if text:
                break  # the board comes in one push
            continue
        text += piece
        if missing(piece):
            break
    board = commodities.board(text)
    if board is None:
        s.echo(f"{PREFIX}: no commodity board here ({said(text)!r})")
        return None
    commoditylog.log_board(character(s), board)
    s.echo(f"{PREFIX}: {board.town}'s board read, {len(board.goods)} goods logged")
    return board


def survey(s, db):
    """Each pit walked to, the nearest first, and its board read."""
    left = dict(commodities.PITS)
    while left:
        if not travel.go(s, set(left.values()), "the nearest commodity pit", db=db):
            return
        board = read_board(s)
        if board is None or board.town not in left:
            return
        del left[board.town]
        if left and loop.wants_stop(s):
            s.echo(f"{PREFIX}: done at {board.town}")
            return


def boards(here=None):
    """The latest boards logged, {town: goods}, `here`'s Board laid over."""
    out = {town: goods for town, (_, goods) in commoditylog.latest().items()}
    if here is not None:
        out[here.town] = here.goods
    return out


def describe(plan):
    return (
        f"{plan.units} {plan.good} from {plan.buy} to {plan.sell}:"
        f" about {plan.bought:,} paid, {plan.sold:,} sold, {plan.profit:,} Kronars clear"
    )


def show_plans(s):
    logged = boards()
    if not logged:
        s.echo(f"{PREFIX}: no board read in the last {commoditylog.FRESH_HOURS} hours")
        return
    for town in commodities.PITS:
        plan = commodities.plan(logged, town)
        s.echo(
            f"{PREFIX}: {describe(plan) if plan else f'nothing worth it from {town}'}"
        )


def buy(s, db, town, plan):
    """ORDER the plan's units at this pit, the coin drawn first when
    short: the trade's log seq and (price, cut), or None, said."""
    if not shop.afford(
        s, ask, PREFIX, plan.bought, db=db, retry="run ;commodities trade again"
    ):
        return None
    if not walk(s, db, commodities.PITS[town], f"the {town} commodity pit"):
        return None
    answer = ask(s, f"order {plan.units} {plan.good}")
    paid = commodities.order(answer)
    if paid is None:
        unknown(s, PREFIX, "ORDER", answer)
        return None
    price, cut = paid
    s.echo(
        f"{PREFIX}: bought {plan.units} {plan.good} for {price:,} and a cut of {cut:,}"
    )
    seq = commoditylog.log_buy(
        character(s), plan.good, plan.units, town, price, cut, plan.sell
    )
    return seq, price, cut


def animal(s, db, town=None):
    """The pack animal's name once beside it (RECALL CARAVAN), walked to
    `town`'s outpost first when it is not; None, said, otherwise."""
    answer = ask(s, "recall caravan")
    name, beside = trade.caravan(answer)
    if not beside and town is not None:
        walk(s, db, trade.TOWNS[town].outpost, f"the {town} outpost")
        answer = ask(s, "recall caravan")
        name, beside = trade.caravan(answer)
    if name and beside:
        return name
    s.echo(
        f"{PREFIX}: your pack animal is not beside you ({said(answer)!r}) — stand"
        " beside it and ;commodities trade again"
    )
    return None


def sell(s, db, seq, good, units, cost, town):
    """At `town`: its board read again, then SELL at its shipment clerk
    unless the good now reads Surplus! or pays less than `cost`; True
    once sold."""
    if not walk(s, db, commodities.PITS[town], f"the {town} commodity pit"):
        return False
    board = read_board(s)
    if board is None:
        return False
    price, stock = board.goods.get(good, (0, commodities.SURPLUS))
    if stock == commodities.SURPLUS or price * units < cost:
        s.echo(
            f"{PREFIX}: {town} reads {good} {price} {stock} — {units} would bring"
            f" {price * units:,} against {cost:,} paid; the goods stay on your animal"
        )
        return False
    if not walk(s, db, trade.TOWNS[town].clerk, f"the {town} shipment clerk"):
        return False
    answer = ask(s, f"sell {units} {good}")
    paid = commodities.sale(answer)
    if paid is None:
        unknown(s, PREFIX, "SELL", answer)
        return False
    commoditylog.log_sale(seq, town, paid)
    s.echo(
        f"{PREFIX}: sold {units} {good} at {town} for {paid:,} —"
        f" {paid - cost:,} Kronars over the {cost:,} paid"
    )
    return True


def carry(s, db):
    """One trade: the open one carried on, else the best bought at the
    nearest pit; True once sold."""
    held = commoditylog.open_trade(character(s))
    if held is not None:
        seq, good, units, town, price, cut, buyer = held
        s.echo(f"{PREFIX}: carrying on — {units} {good} from {town} to {buyer}")
        name = animal(s, db)
    else:
        pits = set(commodities.PITS.values())
        if not travel.go(s, pits, "the nearest commodity pit", db=db):
            return False
        here = read_board(s)
        if here is None:
            return False
        town = here.town
        plan = commodities.plan(boards(here), town)
        if plan is None:
            s.echo(
                f"{PREFIX}: nothing at {town} worth carrying by the boards of the"
                f" last {commoditylog.FRESH_HOURS} hours — ;commodities reads them all"
            )
            return False
        s.echo(f"{PREFIX}: {describe(plan)}")
        bought = buy(s, db, town, plan)
        if bought is None:
            return False
        seq, price, cut = bought
        good, units, buyer = plan.good, plan.units, plan.sell
        name = animal(s, db, town)
    if name is None:
        return False
    if not haul.bring(s, db, name, trade.TOWNS[buyer].outpost, PREFIX):
        return False
    return sell(s, db, seq, good, units, (price or 0) + (cut or 0), buyer)


def main(s):
    verb = str(s.args[0]).lower() if s.args else ""
    if verb == "plan":
        show_plans(s)
        return
    db = travel.mapdb()
    if verb == "read":
        read_board(s)
    elif verb == "trade":
        carry(s, db)
    elif verb:
        s.echo(f"{PREFIX}: no verb {verb!r} — ;commodities help")
    else:
        survey(s, db)
