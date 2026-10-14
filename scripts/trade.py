"""Run Trader caravan contracts around Zoluren:  ;trade

    ;trade            deliver, pay the dues, take the next contract, load it, feed the caravan, lead it there; again
    ;trade return     deliver what is held and stop at the clerk, no new contract (typed while it runs: the same)
    ;trade history    every contract logged: per route the count, the pay, the profit, the minutes

What it does
  - Starts at a Zoluren outpost — the Crossing, Arthe Dale, Stone Clan, Dirge,
    Wolf Clan or Tiger Clan — with your caravan at the outpost (RECALL CARAVAN
    finds it; RENT CARAVAN at a shipment clerk, 400 Kronars, rents one).
  - At the clerk: hands in the contract for this town and is paid; PAY CLERK.
  - After a delivery with a teller near the clerk (the Crossing, Dirge), banks
    the purse and keeps 20,000 copper Kronars for dues and fees (;bank).
  - At the minister: ASK MINISTER FOR CONTRACT; dues owed are drawn at the
    nearest teller when the purse is short, and paid first.
  - The clerk loads the crate; the caravan is fed from your feedbag and told to
    LEAD TO the contract's town; you follow it, then walk it to the outpost.
  - Every contract goes into history.db's contracts table: charge, pay, times.

When it stops
  - ;trade return once nothing is held; ;stop trade at once
  - a contract for a town it does not lead to (Leth Deriel, another province): said, kept
  - no caravan, no feedbag or no grass in it, a lead refused or given up,
    a teller that refuses, an answer it does not know (said)

The towns, the contract and the wordings are client/game/trade.py's,
the log client/game/tradelog.py's; docs/trade.md.
"""

from client.game import hands, loop, money, probe, shop, trade, tradelog, travel
from client.game.act import ask, missing, said, unknown
from client.game.mapdb import pause_seconds, translate_embedded

_NOTES = """
Built from one contract driven by hand on 2026-10-15: the Crossing's
minister asked for 2,375 Kronars of dues first, issued a Wolf Clan
contract for 13 saber hilts (3,537 wholesale, 985 dues), the clerk
loaded it for 50 copper, the driver fed the bullocks from the feedbag,
and LEAD TO WOLF CLAN took 3½ minutes from Commerce Avenue to the Wolf
Clan outpost's door, where the clerk paid 11,791. dr-scripts' trade.lic
is the procedure (contract, clerk, feed, lead, the caravan following
step by step) and the source of the wordings not yet seen live: the
follow line, a refused or failed lead, a held contract, the no-goods
answer. Elanthipedia: Caravan (the lead destinations: a lead to the
Crossing ends at the Northeast Gate, so the last stretch is walked with
the caravan following), Trader (RENT CARAVAN).

The first script run (the same night) ran Wolf Clan → Arthe Dale: the
lead took six minutes and ended at Arthe Dale's outpost, the clerk paid
14,586. It first stopped on an unread contract (the familiar stream)
and on the Arthe Dale lead's answer, which lacks the acknowledgement
line; both fixed in 9bdebcc.
"""

PREFIX = "trade"
LEAD_MINUTES = 20  # the Crossing to Wolf Clan took 3½
FOLLOW_SECONDS = 30  # a step's wait for the caravan to catch up
LOW_GRASS = 5
READ_STREAMS = ("", "familiar")
READ_SECONDS = 5
# A teller this many rooms from the clerk gets the pay after a delivery:
# the Crossing's (14) and Dirge's (3); the other outposts are 40 and more.
BANK_ROOMS = 20
# Copper Kronars kept on hand after banking: the dues and fees ahead (a
# contract's charges at the minister ran 4,522 and 5,625 Kronars).
KEEP = 20_000


def parse_args(args):
    words = [str(arg).lower() for arg in args or []]
    return {"verb": words[0] if words else ""}


def character(s):
    return getattr(getattr(s, "state", None), "name", None) or ""


def history(s):
    routes = tradelog.summary(character(s) or None)
    if not routes:
        s.echo(f"{PREFIX}: no contracts logged yet")
        return
    for route in routes:
        s.echo(f"{PREFIX}: {tradelog.describe(route)}")


def nearest_town(s, db):
    """The TOWNS key whose outpost, minister or clerk is nearest the
    character by the map, or None off the map."""
    here = travel.here(s, db)
    rooms = {room: name for name, town in trade.TOWNS.items() for room in town}
    route = db.path(here, set(rooms)) if here is not None else None
    if route is None:
        return None
    return rooms[route[-1][0] if route else here]


def walk(s, db, room, describe):
    if travel.here(s, db) == room:
        return True
    return travel.go(s, {room}, describe, db=db)


def held(s):
    """The contract on the character, read (READ MY CONTRACT), or None.
    The game pushes the contract's text to the familiar stream, which
    ask() does not read: the first live ;trade stopped on an unread
    contract (2026-10-15)."""
    while s.get(timeout=0, streams=READ_STREAMS) is not None:
        pass  # what came before the READ is not its answer
    s.put("read my contract")
    text = ""
    deadline = probe.clock() + READ_SECONDS
    while probe.clock() < deadline:
        piece = s.get(timeout=0.5, streams=READ_STREAMS)
        if piece is None:
            continue
        text += piece
        if trade.READ_END in piece or missing(piece):
            break
    return trade.contract(text)


def deliver(s, db, place):
    """Hand this town's contract to its clerk; True once paid."""
    if not walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk"):
        return False
    answer = ask(s, f"get my {trade.contract_noun(place)}")
    if missing(answer):
        s.echo(f"{PREFIX}: no {place} contract on you")
        return False
    answer = ask(s, "give my contract to clerk")
    kind, value = trade.clerk(answer)
    if kind == "paid":
        paid, coin = value
        tradelog.log_delivery(character(s), place, paid)
        s.echo(f"{PREFIX}: {place} paid {paid:,} {coin or ''}".rstrip())
        return True
    hands.stow(s, "contract")
    if kind == "no goods":
        s.echo(f"{PREFIX}: the clerk found no goods — is the caravan at the outpost?")
    else:
        unknown(s, PREFIX, "GIVE", answer)
    return False


def pay(s):
    """PAY CLERK at the clerk here; the answer's line."""
    answer = ask(s, "pay clerk")
    return said(answer, trade.SETTLED + (trade.PART_PAID, trade.NO_COINS))


def bank_run(s, db):
    """After a delivery and the dues: the purse banked at a teller near
    the clerk with KEEP kept (;bank keep=KEEP back, which walks back
    here); nothing with no teller near or no more than KEEP on hand."""
    here = travel.here(s, db)
    tellers = db.rooms_tagged("bank")
    route = db.path(here, tellers) if here is not None and tellers else None
    if route is None or len(route) > BANK_ROOMS:
        return
    if money.carried(s, "Kronars", ask) <= KEEP:
        return
    s.echo(f"{PREFIX}: banking the pay, keeping {money.phrase(KEEP, 'Kronars')}")
    if not s.run("bank", [f"keep={KEEP}", "back"]):
        s.echo(f"{PREFIX}: could not start ;bank — the purse stays as it is")
        return
    try:
        while s.is_running("bank"):
            s.sleep(1)
    except BaseException:
        s.kill("bank")  # ;stop trade takes the ;bank with it
        raise


def issue(s, db, place):
    """A new contract from this town's minister, dues paid first:
    (wholesale, dues) in copper, or None, said."""
    town = trade.TOWNS[place]
    for _ in range(2):
        if not walk(s, db, town.minister, f"the {place} trade minister"):
            return None
        answer = ask(s, "ask minister for contract")
        kind, value = trade.minister(answer)
        if kind == "issued":
            return value
        if kind == "held":
            s.echo(
                f"{PREFIX}: the minister says you still hold a contract from {place}"
            )
            return None
        if kind != "dues":
            unknown(s, PREFIX, "ASK MINISTER", answer)
            return None
        s.echo(f"{PREFIX}: {value:,} Kronars of dues owed to {place} — paying them")
        if not shop.afford(s, ask, PREFIX, value, db=db, retry="run ;trade again"):
            return None
        if not walk(s, db, town.clerk, f"the {place} shipment clerk"):
            return None
        s.echo(f"{PREFIX}: {pay(s)}")
    s.echo(f"{PREFIX}: the minister still asks for dues — stopping")
    return None


def load(s, db, place, seq):
    """Give the new contract to this town's clerk, who loads the crate;
    True once loaded, the contract stowed."""
    if not walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk"):
        return False
    if not hands.holding(s, "contract"):
        ask(s, "get my contract")
    answer = ask(s, "give my contract to clerk")
    kind, fee = trade.clerk(answer)
    hands.stow(s, "contract")
    if kind == "loaded":
        tradelog.log_fee(seq, fee)
        return True
    if kind == "too heavy":
        s.echo(
            f"{PREFIX}: the clerk says the load is too much — rent a caravan (RENT CARAVAN)"
        )
    else:
        unknown(s, PREFIX, "GIVE", answer)
    return False


def take(s, db, place):
    """Issue, read, log and load this town's next contract: the
    Contract, or None, said."""
    charged = issue(s, db, place)
    if charged is None:
        return None
    contract = held(s)
    if contract is None:
        s.echo(f"{PREFIX}: could not read the new contract — stopping")
        return None
    wholesale, dues = charged
    seq = tradelog.log_issue(character(s), place, contract, wholesale, dues)
    s.echo(
        f"{PREFIX}: {contract.goods} for {contract.destination},"
        f" worth {contract.worth or '?'} on delivery"
    )
    return contract if load(s, db, place, seq) else None


def feed(s, name):
    """Feed the caravan from the feedbag (worn or carried); False, said,
    without a feedbag or grass."""
    grass = trade.grass(ask(s, "look in my feedbag"))
    if not grass:
        s.echo(
            f"{PREFIX}: no grass in your feedbag — FORAGE GRASS and put it in, then ;trade"
        )
        return False
    if grass < LOW_GRASS:
        s.echo(f"{PREFIX}: {grass} grass left in your feedbag")
    hands.free(s)
    worn = not missing(ask(s, "remove my feedbag"), ("aren't wearing", "not wearing"))
    if not worn and missing(ask(s, "get my feedbag")):
        s.echo(f"{PREFIX}: no feedbag on you")
        return False
    answer = ask(s, f"give {name}")
    if worn:
        ask(s, "wear my feedbag")
    else:
        hands.stow(s, "feedbag")
    if not said(answer, trade.FED + (trade.NOT_HUNGRY,)) or missing(answer):
        unknown(s, PREFIX, "the feeding", answer)
        return False
    return True


def lead(s, name, place):
    """TELL the caravan TO LEAD TO `place` and follow it; True on
    arrival, False, said, when the driver refuses or gives up."""
    s.clear()
    answer = ask(s, f"tell {name} to lead to {place.lower()}")
    if trade.LEADING not in answer:
        s.echo(f"{PREFIX}: the driver did not take the lead ({said(answer)!r})")
        return False
    s.echo(f"{PREFIX}: leading to {place}")
    line = s.waitfor(trade.ARRIVED, trade.LEAD_FAILED, timeout=LEAD_MINUTES * 60)
    if line is None or trade.LEAD_FAILED in line:
        s.echo(f"{PREFIX}: the lead to {place} did not arrive ({line or 'no word'})")
        return False
    return True


def steps(route):
    """Each edge of a route as the game commands it sends, or None when
    one is a scripted edge (a ferry) a caravan cannot follow."""
    out = []
    for _, command in route:
        sent = translate_embedded(command) if command.startswith(";e") else [command]
        if not sent:
            return None
        out.append(sent)
    return out


def bring(s, db, name, room):
    """Walk the caravan to `room` (the outpost) one room at a time,
    waiting for it to follow each (trade.lic's take_caravan_to); True
    there. A lead to the Crossing ends at the Northeast Gate."""
    here = travel.here(s, db)
    if here == room:
        return True
    route = db.path(here, [room]) if here is not None else None
    edges = steps(route) if route else None
    if not edges:
        s.echo(
            f"{PREFIX}: no plain walk from here to the outpost — bring the caravan yourself"
        )
        return False
    if not said(ask(s, f"tell {name} to follow"), trade.FOLLOW_ORDERED):
        s.echo(f"{PREFIX}: the caravan would not follow")
        return False
    for commands in edges:
        s.clear()
        for command in commands:
            pause = pause_seconds(command)
            if pause is not None:
                s.sleep(pause)
                continue
            s.waitrt()
            s.put(command)
        if s.waitfor(trade.FOLLOWING, timeout=FOLLOW_SECONDS) is None:
            s.echo(f"{PREFIX}: the caravan fell behind after {commands[-1]!r}")
            return False
    ask(s, f"tell {name} to wait")
    return travel.here(s, db) == room


def main(s):
    opts = parse_args(s.args)
    if opts["verb"] == "history":
        history(s)
        return
    returning = opts["verb"] == "return"
    db = travel.mapdb()
    name, _ = trade.caravan(ask(s, "recall caravan"))
    if not name:
        s.echo(f"{PREFIX}: no caravan — RENT CARAVAN at a shipment clerk (400 Kronars)")
        return
    place = nearest_town(s, db)
    if place is None:
        s.echo(f"{PREFIX}: not at a Zoluren outpost ;trade knows — walk to one")
        return
    while True:
        contract = held(s)
        delivered = False
        if contract and trade.town(contract.destination) == place:
            if not deliver(s, db, place):
                return
            contract, delivered = None, True
        if contract and not contract.presented and trade.town(contract.origin) == place:
            # Issued here and never loaded: a stop between the minister and
            # the clerk. Logged now, the minister's charges unknown.
            seq = tradelog.log_issue(character(s), place, contract)
            if not load(s, db, place, seq):
                return
        if contract is None:
            walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk")
            s.echo(f"{PREFIX}: {pay(s)}")
            if delivered:
                bank_run(s, db)
            if returning or loop.wants_stop(s):
                s.echo(f"{PREFIX}: nothing held — done at {place}")
                return
            contract = take(s, db, place)
            if contract is None:
                return
        destination = trade.town(contract.destination)
        if destination is None:
            s.echo(
                f"{PREFIX}: the contract is for {contract.destination}, which ;trade"
                " does not lead to — deliver it yourself"
            )
            return
        if not walk(s, db, trade.TOWNS[place].outpost, f"the {place} outpost"):
            return
        if not feed(s, name) or not lead(s, name, destination):
            return
        if not bring(s, db, name, trade.TOWNS[destination].outpost):
            return
        place = destination
        returning = returning or loop.wants_stop(s)
