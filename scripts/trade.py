"""Run Trader caravan contracts in Zoluren, Ilithi and to Riverhaven:  ;trade

    ;trade            deliver, pay the dues, take the next contract, load it, feed the caravan, lead it there; again
    ;trade interprovince  the same, each contract for another province (the broker's) where one is offered: the Crossing, Shard
    ;trade return     typed while it runs: deliver what is held, take no new contract, return the caravan at the clerk
    ;trade history    every contract logged: per route the count, the pay and the profit in Kronars, the minutes

What it does
  - Starts at an outpost of Zoluren — the Crossing, Arthe Dale, Stone Clan,
    Dirge, Wolf Clan, Tiger Clan, Leth Deriel — or Ilithi — Shard, Fayrin's
    Rest, Steelclaw Clan, Darkling Wood — or Riverhaven, with your caravan at
    the outpost (RECALL CARAVAN finds it); with none, rents one at the clerk
    (RENT CARAVAN, 400 Kronars or 288 Dokoras).
  - Started beside its caravan away from an outpost (a run stopped on the road),
    goes on from there with the crate it holds.
  - At the clerk: hands in the contract for this town and is paid; PAY CLERK.
  - After a delivery with a teller near the clerk (the Crossing, Dirge, Leth,
    Shard, Riverhaven), banks the purse and keeps 20,000 copper for dues and fees (;bank).
  - At the minister: ASK MINISTER FOR CONTRACT; dues owed are drawn at the
    nearest teller when the purse is short, and paid first. With
    `interprovince`, ASK BROKER FOR CONTRACT instead (the Crossing's and
    Riverhaven's Foreign Trade Offices, Shard's Provincial Broker), its charge paid at the clerk
    before loading; the minister elsewhere.
  - The clerk loads the crate; the caravan is fed from your feedbag and told to
    LEAD TO the contract's town; you follow it, then walk it to the outpost.
    Leth Deriel is by the Crossing and Alfren's Ferry, the caravan following
    you aboard (77 Kronars for the goods; with none on you ;bank fetches
    them while the caravan waits at the dock). A contract between Zoluren and
    Ilithi (a broker's) goes by Leth Deriel and the Obsidian Pass
    gondola, the caravan walked after you and riding along.
  - Riverhaven (the Crossing broker's) is led to by Dirge and walked to over
    the Faldesu ferry; at Dirge ;bank tops the purse up to 500 Lirums for
    the fare first. Back, the ferry and a lead to Dirge from the riverbank.
  - On a lead, runs the profile's `lead_training` script (perform: ;perform once
    here), ended on arrival; with none playing and fewer than 60 bunches in the
    feedbag, forages grass every 15 seconds (you follow through the roundtime).
  - Every contract goes into history.db's contracts table: charge, pay, times.

When it stops
  - ;trade return once nothing is held, the caravan returned (RETURN CARAVAN;
    kept, said, while its storage box holds anything); ;stop trade at once,
    the caravan kept
  - at Riverhaven once delivered and paid, the caravan kept: no minister's
    contract is taken there; with `interprovince` its broker's is (its minister's towns are beyond the routes)
  - a contract for a town ;trade does not lead to (Therengia past Riverhaven):
    said, kept unpaid and unloaded
  - hostiles holding you on a lead while the caravan goes on: you get clear
    (the escape every trainer uses), said
  - a caravan RECALL cannot place, a rental refused, no feedbag or no grass
    in it, a lead refused or given up,
    a teller that refuses, an answer it does not know (said)

The towns, the contract and the wordings are client/game/trade.py's,
the log client/game/tradelog.py's; docs/trade.md.
"""

from client.game import (
    flight,
    hands,
    loop,
    money,
    probe,
    shop,
    trade,
    tradelog,
    travel,
    walker,
)
from client.game.act import ask, missing, said, unknown
from client.game.mapdb import pause_seconds, ride_args, ride_of, translate_embedded

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
answer. Elanthipedia: Caravan (the lead destinations; it says a lead
to the Crossing ends at the Northeast Gate), Trader (RENT CARAVAN).

The first script run (the same night) ran Wolf Clan → Arthe Dale: the
lead took six minutes and ended at Arthe Dale's outpost, the clerk paid
14,586. It first stopped on an unread contract (the familiar stream)
and on the Arthe Dale lead's answer, which lacks the acknowledgement
line; both fixed in 9bdebcc. The unattended run after it led between
Arthe Dale, the Crossing, Wolf Clan and Tiger Clan, 2 to 7
minutes a leg, and Tiger Clan to Dirge in 11½: every lead ended at the
outpost — the Crossing's at Commerce Avenue, not the wiki's Northeast
Gate, Dirge's at Gateway Road, not the North Roads Caravansary — so
bring() had not had to walk the caravan. The bank runs, after the
Crossing's and Dirge's deliveries, kept 2 platinum and walked back.

Leth Deriel, driven by hand and then unattended both ways the next
morning: the caravan followed onto Alfren's Ferry and off at either
bank (the ferry was out a minute or so each time), LEAD TO LETH from the
south bank ended at the Oakenheart Circle outpost, and LEAD TO CROSSING
from Leth ended at the south bank dock, so bring() rode the ferry and
walked the six rooms to Commerce Avenue, a followed step every 5 s.

The first broker contract (the Crossing to Shard, 427 jars of pickled
eel, the same afternoon) ran unattended once loaded by hand: the ferry,
LEAD TO LETH, 77 followed rooms up the Obsidian Pass, a three-minute
wait for the gondola, the caravan in the cab ("Your two auroch caravan
entered a weathered wooden gondola, following you."), 70 followed rooms
to Brickwell Tower. 27 minutes from Commerce Avenue to Shard's clerk,
who paid 78,568 Dokoras against 43,833 Kronars charged, and took back
the caravan the Crossing had rented out.

`;trade interprovince` takes that contract itself in the order the hand
run did (the operator named the verb: "broker" says too little): ASK BROKER FOR CONTRACT (the minister's wordings, "The broker"
for "The minister"), PAY CLERK for the charge, then the clerk's
loading. Whether the clerk loads a broker contract unpaid, as it does
the minister's, was never tried. Shard's broker, the map's room 14305
(Brickwell Tower's Provincial Broker), answered the first
`;trade interprovince` the same way: 559 sacks of marsh chestnuts for
the Crossing, 22,265 Dokoras wholesale and 7,814 dues, worth 102,856
Kronars. That run stopped at the Segoltha's south bank: Alfren's Ferry
wanted 77 Kronars and the purse held only Dokoras ("You haven't got
enough kronars to pay for your trip."); bring() fetches a refused
fare since.

Riverhaven, driven by hand from the Crossing's broker the same day (47,840
Lirums in 73 minutes, #555): LEAD TO DIRGE ended at Gateway Road, LEAD
TO RIVERHAVEN from there (no walk to the caravansary the wiki names)
at North Road, Ferry in six minutes; the Faldesu's captain wanted 152
Lirums for character and goods and refused without them, and the caravan
followed aboard, off at Riverhaven's dock, up the ramp and through the
arch to Town Hall Road. The Lirums were changed at Dirge's teller, 67
rooms from the ferry, so ;trade tops them up at Gateway Road, two rooms
from it, before the lead on. The way back is Elanthipedia's (Trade
Route): a lead to Dirge from North Road, Riverbank, one room south of
the dock; not yet driven.
"""

PREFIX = "trade"
LEAD_MINUTES = 20  # the Crossing to Wolf Clan took 3½
FOLLOW_SECONDS = 30  # a step's wait for the caravan to catch up
# A command sent in roundtime is dropped: "...wait 3 seconds." (an INV
# LIST typed mid-walk took a step's move, 2026-10-15).
WAITED = "...wait"
LOW_GRASS = 5
# Grass is foraged on a lead while the feedbag holds fewer than this:
# the caravan eats on about two legs in five (seven of seventeen,
# 2026-10-15), one bunch a meal.
GRASS_TOP = 60
FORAGE_EVERY = 15  # seconds between FORAGE GRASS tries on a lead
HOSTILE_POLL = 5  # the longest a lead waits between looks at the room
# Looks in one room among hostiles: the caravan has gone on and you
# are held (the Lava Fields outside Dirge, 2026-10-15).
HELD_LOOKS = 2
READ_STREAMS = ("", "familiar")
READ_SECONDS = 5
# A teller this many rooms from the clerk gets the pay after a delivery:
# the Crossing's (14), Dirge's (3), Leth Deriel's (5); the others are 40 and more.
BANK_ROOMS = 20
# Copper Kronars kept on hand after banking: the dues and fees ahead (a
# contract's charges at the minister ran 4,522 and 5,625 Kronars).
KEEP = 20_000
RECALL_TRIES = 6  # after a RENT, the assistant brings the caravan round
RECALL_WAIT = 10
FERRY = "ferry"  # a route step the walker rides: Alfren's Ferry, the Faldesu's
GONDOLA = "gondola"  # and the Obsidian Pass gondola, Leth Deriel to Shard
RIDDEN = {"ferry": FERRY, "faldesu": FERRY, "gondola": GONDOLA}  # the map's names
# The scripts a lead can run (#558), with the arguments that keep them in
# place: ;perform never walks home for a room that refuses a song, and
# ends at mind-lock.
TRAINERS = {"perform": ("once", "here")}
STOP_GRACE = 10  # seconds a trainer gets to end on its typed return


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
        # "Fayrin's" may not name it: the one contract held, then.
        answer = ask(s, "get my contract")
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


def rent(s, db, place):
    """A caravan rented at this town's clerk (RENT CARAVAN, 400 Kronars or
    288 Dokoras, drawn at a teller when the purse is short): its name
    once RECALL finds it, or None, said."""
    coin = trade.coin(place)
    fee = trade.RENT_FEE[coin]
    if not shop.afford(s, ask, PREFIX, fee, coin, db=db, retry="run ;trade again"):
        return None
    if not walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk"):
        return None
    answer = ask(s, "rent caravan")
    if trade.RENTED not in answer:
        if trade.RENT_SHORT in answer:
            s.echo(f"{PREFIX}: not enough coin for the caravan's {fee} {coin}")
        else:
            unknown(s, PREFIX, "RENT CARAVAN", answer)
        return None
    s.echo(f"{PREFIX}: rented a caravan at {place} for {fee} {coin}")
    for _ in range(RECALL_TRIES):
        name, _ = trade.caravan(ask(s, "recall caravan"))
        if name:
            return name
        s.sleep(RECALL_WAIT)
    s.echo(
        f"{PREFIX}: RECALL does not find the rented caravan yet — ;trade again in a minute"
    )
    return None


def return_caravan(s, db, place, name):
    """The rented caravan handed back at this town's clerk (RETURN
    CARAVAN), its storage box rummaged at the outpost first: True once
    returned; kept, said, when the box holds anything or the answer is
    not the box's (the caravan not at the outpost)."""
    if not walk(s, db, trade.TOWNS[place].outpost, f"the {place} outpost"):
        return False
    ask(s, f"open storage box on {name}")
    answer = ask(s, f"rummage in storage box on {name}")
    ask(s, f"close storage box on {name}")
    if trade.BOX_EMPTY not in answer:
        s.echo(f"{PREFIX}: the caravan is kept — its storage box: {said(answer)!r}")
        return False
    if not walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk"):
        return False
    answer = ask(s, "return caravan")
    if not any(word in answer for word in trade.RETURNED):
        unknown(s, PREFIX, "RETURN CARAVAN", answer)
        return False
    s.echo(f"{PREFIX}: the caravan returned at {place}")
    return True


def bank_run(s, db, coin="Kronars"):
    """After a delivery and the dues: the purse banked at a teller near
    the clerk with KEEP kept (;bank keep=KEEP back, which walks back
    here); nothing with no teller near or no more than KEEP on hand."""
    here = travel.here(s, db)
    tellers = db.rooms_tagged("bank")
    route = db.path(here, tellers) if here is not None and tellers else None
    if route is None or len(route) > BANK_ROOMS:
        return
    if money.carried(s, coin, ask) <= KEEP:
        return
    s.echo(f"{PREFIX}: banking the pay, keeping {money.phrase(KEEP, coin)}")
    run_bank(s, [f"keep={KEEP}", "back"])


def run_bank(s, args):
    """;bank with `args`, waited for; said when it would not start."""
    if not s.run("bank", args):
        s.echo(f"{PREFIX}: could not start ;bank — the purse stays as it is")
        return
    try:
        while s.is_running("bank"):
            s.sleep(1)
    except BaseException:
        s.kill("bank")  # ;stop trade takes the ;bank with it
        raise


def ferry_lirums(s):
    """The Faldesu ferry's fare on hand before the lead to Riverhaven:
    ;bank at Dirge's teller and changer, two rooms from Gateway Road,
    tops the purse up to FALDESU_LIRUMS, KEEP kept. A fare still short is
    the ferry's to refuse and bring() fetches it there."""
    if money.carried(s, "Lirums", ask) >= trade.FALDESU_LIRUMS:
        return
    s.echo(f"{PREFIX}: Lirums for the Faldesu ferry first")
    run_bank(s, [f"keep={KEEP}", f"lirums={trade.FALDESU_LIRUMS}", "back"])


def settle(s, db, place, copper):
    """`copper` of the town's coin on hand (drawn at a teller when short),
    then PAY CLERK at its clerk; True once paid, False, said, otherwise."""
    if not shop.afford(
        s, ask, PREFIX, copper, trade.coin(place), db=db, retry="run ;trade again"
    ):
        return False
    if not walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk"):
        return False
    s.echo(f"{PREFIX}: {pay(s)}")
    return True


def issue(s, db, place, broker=False):
    """A new contract from this town's minister, or its broker for
    another province, dues paid first: (wholesale, dues) in copper, or
    None, said."""
    who = "broker" if broker else "minister"
    room = trade.BROKERS[place] if broker else trade.TOWNS[place].minister
    for _ in range(2):
        if not walk(s, db, room, f"the {place} trade {who}"):
            return None
        answer = ask(s, f"ask {who} for contract")
        kind, value = trade.minister(answer)
        if kind == "issued":
            return value
        if kind == "held":
            s.echo(f"{PREFIX}: the {who} says you still hold a contract from {place}")
            return None
        if kind != "dues":
            unknown(s, PREFIX, f"ASK {who.upper()}", answer)
            return None
        s.echo(
            f"{PREFIX}: {value:,} {trade.coin(place)} of dues owed to {place} — paying them"
        )
        if not settle(s, db, place, value):
            return None
    s.echo(f"{PREFIX}: the {who} still asks for dues — stopping")
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


def take(s, db, place, broker=False):
    """Issue, read, log and load this town's next contract, the broker's
    with `broker` where a broker is known (BROKERS): the Contract, or
    None, said."""
    broker = broker and place in trade.BROKERS
    charged = issue(s, db, place, broker)
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
    if trade.town(contract.destination) is None:
        # A broker's contract for a province ;trade cannot reach: kept
        # unpaid and unloaded, the operator's to take on or not.
        s.echo(
            f"{PREFIX}: {contract.destination} is beyond ;trade's routes — the"
            f" contract is yours, its {(wholesale or 0) + (dues or 0):,}"
            f" {trade.coin(place)} owed at the clerk, nothing loaded"
        )
        return None
    # The clerk loaded the first broker contract with its charge paid
    # (2026-10-15); whether it loads one unpaid is untried.
    if broker and not settle(s, db, place, (wholesale or 0) + (dues or 0)):
        return None
    return contract if load(s, db, place, seq) else None


def feed(s, name):
    """Feed the caravan from the feedbag (worn or carried): the grass
    left in it, or None, said, without a feedbag or grass or with an
    answer it does not know."""
    grass = trade.grass(ask(s, "look in my feedbag"))
    if not grass:
        s.echo(
            f"{PREFIX}: no grass in your feedbag — FORAGE GRASS and put it in, then ;trade"
        )
        return None
    if grass < LOW_GRASS:
        s.echo(f"{PREFIX}: {grass} grass left in your feedbag")
    hands.free(s)
    worn = not missing(ask(s, "remove my feedbag"), ("aren't wearing", "not wearing"))
    if not worn and missing(ask(s, "get my feedbag")):
        s.echo(f"{PREFIX}: no feedbag on you")
        return None
    answer = ask(s, f"give {name}")
    if worn:
        ask(s, "wear my feedbag")
    else:
        hands.stow(s, "feedbag")
    if any(word in answer for word in trade.FED):
        return grass - 1
    if any(word in answer for word in trade.NOT_HUNGRY):
        return grass
    unknown(s, PREFIX, "the feeding", answer)
    return None


def arrival(text):
    """The lead's end in `text`: its ARRIVED or LEAD_FAILED line, or None."""
    for line in str(text or "").splitlines():
        if trade.ARRIVED in line or trade.LEAD_FAILED in line:
            return line
    return None


def heard(s):
    """The lead's end among the lines queued now, read without waiting:
    ask() clears the queue before it sends, and an arrival line queued
    then would be lost."""
    while (line := s.get(timeout=0)) is not None:
        if arrival(line):
            return line
    return None


def forage(s, grass):
    """FORAGE GRASS once while led, a find put in the feedbag (`grass`
    counts it): the lead's end if it came in an answer, None otherwise;
    `grass` set to None when the room or the hands will not allow it."""
    answer = ask(s, "forage grass")
    s.waitrt()
    if trade.GRASS_FOUND in answer.lower():
        put = ask(s, "put my grass in my feedbag")
        if not missing(put):
            grass[0] += 1
        return arrival(answer) or arrival(put)
    if any(word in answer for word in trade.FORAGE_BLOCKED):
        grass[0] = None  # not on this lead
    return arrival(answer)


def trainers(s):
    """The profile's `lead_training` scripts ;trade knows how to run on a
    lead (TRAINERS), the rest said once."""
    from client.game.profile import load_profile

    wanted = [
        str(name).lower()
        for name in load_profile(character(s)).get("lead_training") or []
    ]
    unknown = [name for name in wanted if name not in TRAINERS]
    if unknown:
        s.echo(f"{PREFIX}: no lead training for {', '.join(unknown)} — skipped")
    return [name for name in wanted if name in TRAINERS]


def start_training(s, names):
    """The first of `names` started as a child script, its name; None
    when none would start (one already running is the operator's)."""
    for name in names or ():
        if s.run(name, list(TRAINERS[name])):
            s.echo(f"{PREFIX}: ;{name} while the caravan leads")
            return name
    return None


def stop_training(s, name):
    """A lead's trainer ended: the typed `return` every script answers,
    then a ;stop after STOP_GRACE seconds."""
    if not name or not s.is_running(name):
        return
    s.tell(name, "return")
    for _ in range(STOP_GRACE):
        if not s.is_running(name):
            return
        s.sleep(1)
    s.kill(name)


def lead(s, name, place, grass=None, training=()):
    """TELL the caravan TO LEAD TO `place` and follow it; True on
    arrival, False, said, when the driver refuses or gives up. A
    `training` script runs while led, ended on arrival (#558); with none
    running and `grass` ([the feedbag's count]) below GRASS_TOP, grass
    is foraged on the way: a led character follows through the
    roundtime."""
    s.clear()
    answer = ask(s, f"tell {name} to lead to {trade.lead_name(place)}")
    if trade.LEADING not in answer:
        s.echo(f"{PREFIX}: the driver did not take the lead ({said(answer)!r})")
        return False
    s.echo(f"{PREFIX}: leading to {place}")
    trainer = start_training(s, training)
    try:
        deadline = probe.clock() + LEAD_MINUTES * 60
        line, held, room = None, 0, None
        while line is None and probe.clock() < deadline:
            busy = trainer is not None and s.is_running(trainer)
            topping = (
                not busy
                and grass is not None
                and grass[0] is not None
                and grass[0] < GRASS_TOP
            )
            wait = (
                FORAGE_EVERY
                if topping or busy
                else min(HOSTILE_POLL, deadline - probe.clock())
            )
            line = s.waitfor(trade.ARRIVED, trade.LEAD_FAILED, timeout=wait)
            if line is not None:
                break
            here = getattr(s.state, "room_uid", None)
            held = held + 1 if flight.hostiles_present(s.state) and here == room else 0
            room = here
            if held >= HELD_LOOKS:
                stop_training(s, trainer)
                trainer = None
                flight.react(s, PREFIX)
                s.echo(
                    f"{PREFIX}: held by hostiles on the lead to {place} — the caravan"
                    " goes on alone; find it (RECALL CARAVAN) and ;trade again"
                )
                return False
            if topping:
                line = heard(s) or forage(s, grass)
    finally:
        stop_training(s, trainer)
    if line is None or trade.LEAD_FAILED in line:
        s.echo(f"{PREFIX}: the lead to {place} did not arrive ({line or 'no word'})")
        return False
    return True


def steps(route):
    """Each edge of a route as the game commands it sends — FERRY for
    Alfren's Ferry and the Faldesu's, GONDOLA for the gondola, which the
    walker rides (the bank or the cab's direction the argument) — or
    None when one is a scripted edge a caravan cannot follow."""
    out = []
    for _, command in route:
        ride = RIDDEN.get(ride_of(command)) if command.startswith(";e") else None
        if ride:
            out.append((ride, ride_args(command)))
            continue
        sent = translate_embedded(command) if command.startswith(";e") else [command]
        if not sent:
            return None
        out.append(sent)
    return out


def fare(s, db, name, coin):
    """A ferry fare the purse lacked (a run back from Ilithi carries only
    Dokoras: "You haven't got enough kronars to pay for your trip."),
    fetched by ;bank at the nearest teller with the caravan told to wait
    at the dock: True back at the dock with the caravan following."""
    dock = travel.here(s, db)
    ask(s, f"tell {name} to wait")
    if not walker.fetch_fare(s, coin[0] if coin else ""):
        return False
    if not walk(s, db, dock, "the ferry dock"):
        return False
    return said(ask(s, f"tell {name} to follow"), trade.FOLLOW_ORDERED)


def bring(s, db, name, room):
    """Walk the caravan to `room` (the outpost) one room at a time,
    waiting for it to follow each (trade.lic's take_caravan_to); True
    there. Every lead so far ended at the outpost; this is for one that
    stops short of it."""
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
        if commands[0] == FERRY:
            # The caravan follows aboard and off again; GO DOCK is the
            # step it is waited for on.
            ride = walker.ride_ferry(s, commands[1])
            if ride.startswith("fare") and fare(s, db, name, ride.split()[1:]):
                ride = walker.ride_ferry(s, commands[1])
            if ride != "landed":
                s.echo(f"{PREFIX}: the ferry crossing failed — the caravan is with you")
                return False
            commands = ["go dock"]
        elif commands[0] == GONDOLA:
            # The caravan follows into the cab, and the cab's direction
            # waits for it (trade.lic's ride_gondola); OUT is the step
            # it is waited for on after.
            ride = walker.ride_gondola(
                s,
                commands[1],
                aboard=lambda: s.waitfor(trade.FOLLOWING, timeout=FOLLOW_SECONDS),
            )
            if ride != "landed":
                s.echo(
                    f"{PREFIX}: the gondola ride failed ({ride}) — the caravan is with you"
                )
                return False
            commands = ["out"]
        for command in commands:
            pause = pause_seconds(command)
            if pause is not None:
                s.sleep(pause)
                continue
            s.waitrt()
            s.put(command)
        line = s.waitfor(trade.FOLLOWING, WAITED, timeout=FOLLOW_SECONDS)
        if line is not None and WAITED in line:
            s.waitrt()
            s.put(commands[-1])
            line = s.waitfor(trade.FOLLOWING, timeout=FOLLOW_SECONDS)
        if line is None:
            s.echo(f"{PREFIX}: the caravan fell behind after {commands[-1]!r}")
            return False
    ask(s, f"tell {name} to wait")
    return travel.here(s, db) == room


def leg(s, db, name, origin, destination, grass=None, training=()):
    """The caravan from `origin`'s outpost to `destination`'s: led, then
    walked to the outpost when the lead stops short. Riverhaven is led
    to by Dirge (LEAD TO RIVERHAVEN from Gateway Road ends at the north
    road's ferry, the caravan walked over the Faldesu), and back led to
    Dirge from the riverbank south of that ferry. Leth Deriel is
    across the Segoltha, so a leg to or from it goes by the Crossing and
    Alfren's Ferry (trade.lic's do_lead_from and do_lead_to): to it, led
    to the Crossing, walked over the ferry to the south bank, led to
    Leth; from it, led toward the Crossing and walked over the ferry to
    the Crossing's outpost. A leg between Zoluren and Ilithi (a broker's
    contract) goes by Leth Deriel's outpost and Shard's, the caravan
    walked between them over the Obsidian Pass gondola."""
    if origin == destination:
        return True
    if (origin in trade.THERENGIA) != (destination in trade.THERENGIA):
        dirge = trade.VIA_DIRGE
        if destination in trade.THERENGIA:
            if not leg(s, db, name, origin, dirge, grass, training):
                return False
            ferry_lirums(s)
            return lead(s, name, destination, grass, training) and bring(
                s, db, name, trade.TOWNS[destination].outpost
            )
        return (
            bring(s, db, name, trade.RIVERBANK)
            and lead(s, name, dirge, grass, training)
            and bring(s, db, name, trade.TOWNS[dirge].outpost)
            and leg(s, db, name, dirge, destination, grass, training)
        )
    if (origin in trade.ILITHI) != (destination in trade.ILITHI):
        out, into = ("Shard", trade.ACROSS)
        if destination in trade.ILITHI:
            out, into = into, out
        return (
            leg(s, db, name, origin, out, grass, training)
            and bring(s, db, name, trade.TOWNS[into].outpost)
            and leg(s, db, name, into, destination, grass, training)
        )
    crossing = trade.TOWNS["Crossing"].outpost
    if origin == trade.ACROSS:
        if not lead(s, name, "Crossing", grass, training) or not bring(
            s, db, name, crossing
        ):
            return False
        origin = "Crossing"
    if destination == trade.ACROSS:
        if origin != "Crossing" and not (
            lead(s, name, "Crossing", grass, training) and bring(s, db, name, crossing)
        ):
            return False
        if not bring(s, db, name, trade.FERRY_SOUTH):
            return False
    if origin == destination:
        return True
    return lead(s, name, destination, grass, training) and bring(
        s, db, name, trade.TOWNS[destination].outpost
    )


def main(s):
    opts = parse_args(s.args)
    if opts["verb"] == "history":
        history(s)
        return
    broker = opts["verb"] == "interprovince"
    db = travel.mapdb()
    training = trainers(s)
    place = nearest_town(s, db)
    if place is None:
        s.echo(f"{PREFIX}: not at an outpost ;trade knows — walk to one")
        return
    answer = ask(s, "recall caravan")
    name, beside = trade.caravan(answer)
    if not name and trade.NO_CARAVAN[0] in answer:
        name = rent(s, db, place)
        if not name:
            return
    elif not name:
        s.echo(
            f"{PREFIX}: no caravan found ({said(answer)!r}) — bring it to the outpost"
        )
        return
    while True:
        contract = held(s)
        delivered = False
        # Started beside the caravan with its crate bound elsewhere (a run
        # stopped mid-walk): it goes on from here, not back to the outpost.
        beside = (
            beside
            and contract is not None
            and contract.presented
            and trade.town(contract.destination) != place
        )
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
                bank_run(s, db, trade.coin(place))
            if loop.wants_stop(s):
                s.echo(f"{PREFIX}: nothing held — done at {place}")
                return_caravan(s, db, place, name)
                return
            if place in trade.THERENGIA and not (broker and place in trade.BROKERS):
                # Its minister's towns are beyond the routes: a contract
                # taken there would only leave its charge owed.
                s.echo(
                    f"{PREFIX}: done at {place} — ;trade leads no further in"
                    " Therengia yet; the caravan waits (RETURN CARAVAN at the"
                    " clerk hands it back)"
                )
                return
            contract = take(s, db, place, broker)
            if contract is None:
                return
        destination = trade.town(contract.destination)
        if destination is None:
            s.echo(
                f"{PREFIX}: the contract is for {contract.destination}, which ;trade"
                " does not lead to — deliver it yourself"
            )
            return
        if not beside and not walk(
            s, db, trade.TOWNS[place].outpost, f"the {place} outpost"
        ):
            return
        beside = False
        grass = feed(s, name)
        if grass is None or not leg(s, db, name, place, destination, [grass], training):
            return
        place = destination
