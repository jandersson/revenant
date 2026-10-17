"""Run Trader caravan contracts in Zoluren, Ilithi, Forfedhdar and Therengia:  ;trade

    ;trade            deliver, pay the dues, take the next contract, load it, feed the caravan, lead it there; again
    ;trade interprovince  the same, each contract for another province (the broker's) where one is offered: the Crossing, Shard
    ;trade circuit    hold a contract from every town at once, the caravan led to the nearest town with business
    ;trade return     typed while it runs: deliver what is held, take no new contract, return the caravan at the clerk
    ;trade pause      typed while it runs: deliver what is held, take no new contract, stop with the caravan kept at the outpost
    ;trade history    every contract logged: per route the count, the pay and the profit in Kronars, the minutes

What it does
  - Starts at an outpost of Zoluren — the Crossing, Arthe Dale, Stone Clan,
    Dirge, Wolf Clan, Tiger Clan, Leth Deriel — or Ilithi — Shard, Fayrin's
    Rest, Steelclaw Clan, Darkling Wood — or Forfedhdar — Hibarnhvidar, Boar
    Clan, Raven's Point, Ain Ghazal — or Therengia — Riverhaven,
    Therenborough, Langenfirth, Fornsted, Hvaral, Muspar'i — with your
    caravan at the outpost (RECALL CARAVAN finds it); with none, rents one
    at the clerk (RENT CARAVAN, 400 Kronars, 288 Dokoras or 320 Lirums).
  - Forfedhdar: Boar Clan, and Ain Ghazal to Raven's Point, by way of
    Hibarnhvidar; Ain Ghazal across the river by the ferry. Its contracts
    for other provinces are left unloaded.
  - Therengia: Riverhaven to Langenfirth and back by way of Therenborough.
    Fornsted, Hvaral and Muspar'i trade among themselves only (no caravan
    way through the Ker'Leor forest): Fornsted led to Hvaral from past
    Arnshal Keep's gate, which wants a passport (fetched at Therenborough's
    Ibec Hall, the caravan waiting, when yours is missing or expired);
    Muspar'i walked to from Hvaral over the free sand barge. A contract
    between them and the other three is left unloaded.
  - A minister's contract for a town ;trade does not lead to is kept unpaid
    and unloaded, said, and the run goes on as a circuit of the province's
    other towns, held at an outpost while every town waits on one until it
    expires (6 anlaen, three hours); with `interprovince`, a broker's
    beyond the routes stops it.
  - A lead the driver turns down is told again from the room trade.lic
    leads from (Barony Pass, Outside Langenfirth, the Arnshal Road's two
    ends, Forfedhdar's).
  - An expired contract is put in the waste bin by Therenborough's clerk
    at a circuit's stop there, never dropped; elsewhere it is kept.
  - A crate no clerk will pay for (its contract expired, or loaded for a
    town beyond the routes) comes off the caravan at a circuit's stop:
    PUSH and PULL STURDY CRATE, the game's way, not a DROP; kept while
    another caravan is in the room.
  - Started beside its caravan away from an outpost (a run stopped on the road),
    goes on from there with the crate it holds; near its town, walks the
    caravan to the outpost and delivers.
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
  - On a lead, grass first: with fewer than 60 bunches in the feedbag, forages
    grass every 15 seconds (you follow through the roundtime). Then the profile's
    `lead_training` scripts one at a time (perform: ;perform once here stay;
    appraise: ;appraise once stay; research: ;research once stay over its five
    projects, Gauge Flow cast first), the emptiest skill first, the next when one
    ends, the one running ended on arrival. A trainer waits hostiles out in
    place, never fleeing off the lead; ;trade itself decides when they hold you.
  - `circuit` (within a province): at each stop every contract for the town is
    handed in, and the town's own taken when none from it is held (the game
    allows one per town); the next stop is the nearest town a held crate goes
    to or no contract from it is held, by the shortest leg history.db
    measured, else the map. return and pause take no new contract and end
    once every held one is delivered.
  - Every contract goes into history.db's contracts table: charge, pay, times.

When it stops
  - ;trade return once nothing is held, the caravan returned (RETURN CARAVAN;
    kept, said, while its storage box holds anything); ;trade pause once nothing
    is held, the caravan kept at the outpost; ;stop trade at once, the caravan kept
  - with `interprovince`, a broker's contract beyond the routes: said,
    kept unpaid and unloaded
  - hostiles holding you on a lead while the caravan goes on: you get clear
    (the escape every trainer uses), said
  - a caravan RECALL cannot place, a rental refused, no feedbag or no grass
    in it, a lead refused or given up,
    a teller that refuses, an answer it does not know (said)

The towns, the contract and the wordings are client/game/trade.py's,
the log client/game/tradelog.py's; docs/trade.md.
"""

from client.game import (
    discard,
    flight,
    haul,
    hands,
    loop,
    money,
    probe,
    shop,
    trade,
    tradelog,
    travel,
)
from client.game.act import ask, missing, said, unknown

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

Fornsted, Hvaral and Muspar'i (#555, 2026-10-17) are trade.lic's
do_lead_from and do_lead_to and the wiki's Trade Route, not yet driven:
Therenborough to Fornsted was walked through the Ker'Leor forest (44
rooms, no lead) until the first drive, 2026-10-18: the bramble passage
west of Barony Pass took two minutes before the caravan came through,
morah creepers engaged at every room after it, and at the first fallen
tree the character climbed over and the caravan stayed behind; the way
on climbs four more times. Fornsted to Hvaral is led from Arnshal Road, Keep
Entrance, past Arnshal Keep's west gate and its passport (bescort's
hvaral_passport), and back from the Mountain Approach; Hvaral to
Muspar'i is walked aboard the free sand barge (bescort's sandbarge).
Before they were built, a contract for one of them blocked its minister
for two to eight hours, three destinations in five.

A crate loaded for Fornsted rode on undelivered once the forest was
found impassable (2026-10-18, #586): the contract's paper went in the
bin on expiry and nothing took the crate off. Elanthipedia's Trader
gives two ways, the expired contract to the destination's clerk (out
of reach here) or PUSH and PULL CRATE ON CARAVAN; unload() is
trade.lic's dump_crate, the LOOK before and after the judge. Driven by
hand at Langenfirth's outpost the same night (the Fornsted crate, alone
on the caravan): the PUSH put it first to be offloaded, the first PULL
asked for a second within 20 seconds, the second pulled it off with the
driver's help, and the crate fell to the ground in the room; the LOOK
after listed only the storage box. The contract still reads presented
with its crate gone, so a restart beside the caravan counts only a
crate it can deliver as a load on the road.
"""

PREFIX = "trade"
LEAD_MINUTES = 20  # the Crossing to Wolf Clan took 3½
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
# The scripts a lead can run (#558), with the arguments that keep them in
# place: ;perform never walks home for a room that refuses a song, and
# ends at mind-lock; ;appraise works the character's own items, each put
# back, and ends at mind-lock; ;research casts Gauge Flow and researches
# a project for each of five skills (moving is no interruption). Each with
# the skills it trains, ranked by the emptiest.
TRAINERS = {
    "perform": (("once", "here", "stay"), ("Performance",)),
    "appraise": (("once", "stay"), ("Appraisal",)),
    "research": (
        ("once", "stay", "stream", "augmentation", "utility", "warding", "fundamental"),
        ("Attunement", "Augmentation", "Utility", "Warding", "Arcana"),
    ),
}
STOP_GRACE = 10  # seconds a trainer gets to end on its typed return
# A minister's contract runs 6 anlaen, three hours (Therenborough's, 2026-10-17):
# with every town waiting on one beyond the routes, a circuit re-reads its
# contracts every EXPIRY_POLL seconds, for four hours at most.
EXPIRY_POLL = 300
EXPIRY_POLLS = 48
# READ MY <ordinal> CONTRACT, one per town at most: Zoluren's seven.
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")


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


def held(s, ordinal=""):
    """The contract on the character, read (READ MY CONTRACT; READ MY
    SECOND CONTRACT with `ordinal`), or None. The game pushes the
    contract's text to the familiar stream, which ask() does not read:
    the first live ;trade stopped on an unread contract (2026-10-15)."""
    while s.get(timeout=0, streams=READ_STREAMS) is not None:
        pass  # what came before the READ is not its answer
    s.put(f"read my {ordinal} contract" if ordinal else "read my contract")
    text = ""
    deadline = probe.clock() + READ_SECONDS
    while probe.clock() < deadline:
        piece = s.get(timeout=0.5, streams=READ_STREAMS)
        if piece is None:
            continue
        text += piece
        if trade.READ_END in piece or trade.EXPIRED in piece or missing(piece):
            break
    return trade.contract(text)


def held_all(s):
    """Every contract on the character, READ MY FIRST CONTRACT, SECOND
    and on until one is not there: a list, [] with none (#556)."""
    contracts = []
    for ordinal in ORDINALS:
        contract = held(s, ordinal)
        if contract is None:
            break
        contracts.append(contract)
    return contracts


def deliver(s, db, place, only=True):
    """Hand this town's contract to its clerk; True once paid. GET MY
    CONTRACT stands in for the town's noun only when the contract is
    the `only` one held: with several, it could be another town's."""
    if not walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk"):
        return False
    answer = ask(s, f"get my {trade.contract_noun(place)}")
    if missing(answer) and only:
        # "Fayrin's" may not name it: the one contract held, then.
        answer = ask(s, "get my contract")
    elif missing(answer):
        # Nor "Muspar'i", maybe: the one READ finds for this town, by its ordinal.
        mine = [
            ordinal
            for ordinal, c in zip(ORDINALS, held_all(s))
            if c.presented and trade.town(c.destination) == place
        ]
        if mine:
            answer = ask(s, f"get my {mine[0]} contract")
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
    """A caravan rented at this town's clerk (RENT CARAVAN, 400 Kronars,
    288 Dokoras or 320 Lirums, drawn at a teller when the purse is short): its name
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
    elif kind == "away":
        s.echo(
            f"{PREFIX}: the clerk wants the caravan at the {place} outpost and it is"
            " not there — bring it in and ;trade again"
        )
    else:
        unknown(s, PREFIX, "GIVE", answer)
    return False


def beyond(contract):
    """True for a contract ;trade does not carry (trade.routable)."""
    return not trade.routable(
        trade.town(contract.origin), trade.town(contract.destination)
    )


def take(s, db, place, broker=False):
    """Issue, read, log and load this town's next contract, the broker's
    with `broker` where a broker is known (BROKERS): the Contract (unpaid
    and unloaded, said, when beyond the routes), or None, said."""
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
    if beyond(contract):
        # A contract for a town ;trade cannot reach: kept unpaid and
        # unloaded, the operator's to take on or not. Stowed: with one in
        # a hand READ MY SECOND CONTRACT read the backpack's second, and
        # its first went unread (Hvaral's, Riverhaven, 2026-10-17).
        hands.stow(s, "contract")
        s.echo(
            f"{PREFIX}: {contract.destination} is beyond ;trade's routes — the"
            f" contract is yours, its {(wholesale or 0) + (dues or 0):,}"
            f" {trade.coin(place)} owed at the clerk, nothing loaded"
        )
        return contract
    # The clerk loaded the first broker contract with its charge paid
    # (2026-10-15); whether it loads one unpaid is untried.
    if broker and not settle(s, db, place, (wholesale or 0) + (dues or 0)):
        return None
    return contract._replace(presented=True) if load(s, db, place, seq) else None


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


def trainers(s, quiet=False):
    """The profile's `lead_training` scripts ;trade knows how to run on a
    lead (TRAINERS), the rest said unless `quiet`. Read again before
    every leg, so a profile change applies on the next lead."""
    from client.game.profile import load_profile

    wanted = [
        str(name).lower()
        for name in load_profile(character(s)).get("lead_training") or []
    ]
    unknown = [name for name in wanted if name not in TRAINERS]
    if unknown and not quiet:
        s.echo(f"{PREFIX}: no lead training for {', '.join(unknown)} — skipped")
    return [name for name in wanted if name in TRAINERS]


def start_training(s, names, tried):
    """The next of `names` started as a child script, its name, the one
    whose emptiest skill holds the least first (the most skills moving; a
    skill the exp window does not list is empty), ties in the profile's
    order; each is tried once a lead (`tried` collects them). None when
    none is left that would start (one already running is the operator's)."""
    left = [name for name in names or () if name not in tried]
    left.sort(
        key=lambda name: min(
            loop.mindstate(s, skill) or 0 for skill in TRAINERS[name][1]
        )
    )
    for name in left:
        tried.append(name)
        if s.run(name, list(TRAINERS[name][0])):
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
    arrival, None, said, when the driver turns the lead down, False,
    said, when the lead gives up. Grass
    comes first: while `grass` ([the feedbag's count]) is below GRASS_TOP
    it is foraged on the way (the operator: "grass forage should take
    prio just so he doesn't run out of feed"); then the `training`
    scripts run one at a time, the emptiest skill first, the one running
    ended on arrival (#558). A led character follows through the
    roundtime."""
    s.clear()
    answer = ask(s, f"tell {name} to lead to {trade.lead_name(place)}")
    if trade.LEADING not in answer:
        s.echo(f"{PREFIX}: the driver did not take the lead ({said(answer)!r})")
        return None
    s.echo(f"{PREFIX}: leading to {place}")
    tried, trainer = [], None
    try:
        deadline = probe.clock() + LEAD_MINUTES * 60
        line, held, room = None, 0, None
        while line is None and probe.clock() < deadline:
            topping = (
                grass is not None and grass[0] is not None and grass[0] < GRASS_TOP
            )
            if trainer is not None and not s.is_running(trainer):
                trainer = None  # it ended: the next, below
            if trainer is None and not topping:
                trainer = start_training(s, training, tried)
            busy = trainer is not None
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


def bring(s, db, name, room):
    """Walk the caravan to `room` (the outpost) one followed room at a
    time (client/game/haul.py). Every lead so far ended at the outpost;
    this is for one that stops short of it."""
    return haul.bring(s, db, name, room, PREFIX)


def leg(s, db, name, origin, destination, grass=None, training=()):
    """The caravan from `origin`'s outpost to `destination`'s: led, then
    walked to the outpost when the lead stops short. Riverhaven is led
    to by Dirge (LEAD TO RIVERHAVEN from Gateway Road ends at the north
    road's ferry, the caravan walked over the Faldesu), and back led to
    Dirge from the riverbank south of that ferry; the rest of Therengia by
    way of Riverhaven. Leth Deriel is
    across the Segoltha, so a leg to or from it goes by the Crossing and
    Alfren's Ferry (trade.lic's do_lead_from and do_lead_to): to it, led
    to the Crossing, walked over the ferry to the south bank, led to
    Leth; from it, led toward the Crossing and walked over the ferry to
    the Crossing's outpost. A leg between Zoluren and Ilithi (a broker's
    contract) goes by Leth Deriel's outpost and Shard's, the caravan
    walked between them over the Obsidian Pass gondola."""
    if origin == destination:
        return True
    if trade.via(origin, destination) is not None:
        return province_leg(s, db, name, origin, destination, grass, training)
    if (origin in trade.THERENGIA) != (destination in trade.THERENGIA):
        gate = "Riverhaven"  # Therengia's way to Dirge
        if gate not in (origin, destination):
            return leg(s, db, name, origin, gate, grass, training) and leg(
                s, db, name, gate, destination, grass, training
            )
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


def province_leg(s, db, name, origin, destination, grass=None, training=()):
    """A leg within Forfedhdar or Therengia (#555), town by town
    (trade.via: Hibarnhvidar, #583; Therenborough, Fornsted, Hvaral): a
    pair with a lead of its own (trade.LEADS, one way each) led straight
    there, Ain Ghazal's riding the ferry; a pair with none (trade.WALKS)
    walked, Muspar'i's over the sand barge. A lead the driver turns down
    is told again from the room trade.lic leads from (trade.lead_from;
    Fornsted's past Arnshal Keep's passport gate), the caravan walked
    there first."""
    step = trade.via(origin, destination)
    if step != destination:
        return province_leg(s, db, name, origin, step, grass, training) and (
            province_leg(s, db, name, step, destination, grass, training)
        )
    if (origin, destination) in trade.WALKS:
        return bring(s, db, name, trade.TOWNS[destination].outpost)
    led = lead(s, name, destination, grass, training)
    start = trade.lead_from(origin, destination)
    if led is None and start is not None:
        s.echo(f"{PREFIX}: walking the caravan out to lead from there")
        if not bring(s, db, name, start):
            return False
        led = lead(s, name, destination, grass, training)
    return bool(led) and bring(s, db, name, trade.TOWNS[destination].outpost)


def province(place):
    """The towns a circuit from `place` works: Ilithi's, Forfedhdar's,
    Therengia's, else Zoluren's (Leth Deriel among them)."""
    for towns in (trade.ILITHI, trade.FORFEDHDAR, trade.THERENGIA):
        if place in towns:
            return towns
    return tuple(
        town
        for town in trade.TOWNS
        if town not in trade.ILITHI + trade.THERENGIA + trade.FORFEDHDAR
    )


def next_stop(db, place, towns, legs):
    """The nearest of `towns` from `place` (#556): by `legs`, the shortest
    delivered contract either way (tradelog.leg_minutes), when it knows
    every one; else by the map's walk, outpost to outpost, for all of
    them, since a led caravan is slower than the map's walk."""
    towns = sorted(towns)

    def measured(town):
        return legs.get((place, town), legs.get((town, place)))

    if all(measured(town) is not None for town in towns):
        return min(towns, key=measured)

    def walked(town):
        start, goal = trade.TOWNS[place].outpost, trade.TOWNS[town].outpost
        route = db.path(start, {goal})
        return db.seconds_of(start, route) if route is not None else float("inf")

    return min(towns, key=walked)


def held_from(contracts):
    """The towns a contract is held from, an expired one aside: a minister
    refuses another only until the last would have expired (trade.lic's
    force_contract_from), and one beyond the routes is never delivered."""
    return {trade.town(c.origin) for c in contracts if not c.expired}


def unloaded(contract):
    """True for a contract ;trade carries whose crate was never loaded:
    its business is at the town that issued it, where the clerk loads it."""
    return not (contract.presented or contract.expired or beyond(contract))


def business(contract):
    """The town a held contract calls at next: its destination once
    loaded, its origin while unloaded; None for one beyond the routes or
    expired."""
    if contract.expired or beyond(contract):
        return None
    return trade.town(contract.destination if contract.presented else contract.origin)


def stranded(crates, contracts):
    """The index of the first crate in `crates` (trade.crates) no clerk
    will pay for, or None: one a held contract beyond the routes names,
    or one from a held expired contract's origin that no live contract
    accounts for. A crate with neither (a contract lost) is kept."""

    def key(name):
        return trade.town(name) or name

    live = [
        (key(c.origin), key(c.destination), beyond(c))
        for c in contracts
        if not c.expired
    ]
    lapsed = {key(c.origin) for c in contracts if c.expired}
    for index, crate in enumerate(crates):
        match = next((m for m in live if m[:2] == crate), None)
        if match:
            live.remove(match)
            if match[2]:
                return index
        elif crate[0] in lapsed:
            return index
    return None


def unload(s, name, contracts):
    """Every stranded crate taken off the caravan beside the character,
    one at a time: PUSH <ordinal> STURDY CRATE, PULL STURDY CRATE twice
    (trade.lic's dump_crate; Elanthipedia's Trader: "PULL CRATE ON
    CARAVAN to dump it"), then LOOK again, the crate gone the judge. The
    second PULL is the game's confirmation, due within 20 seconds; the
    crate falls to the ground in the room. The game's own way to take a
    crate off a caravan, the game's goods, not a DROP of an item.
    Never with another caravan in the room, whose crates an ordinal might
    reach. The number taken off; a crate still listed, or an answer it
    does not expect, ends it, said."""
    room = str(getattr(getattr(s, "state", None), "room_objs", "") or "").lower()
    if room.count(name.split()[-1].lower()) > 1:
        s.echo(f"{PREFIX}: another caravan here — stranded crates kept for now")
        return 0
    gone = 0
    load = trade.crates(ask(s, f"look {name}"))
    for _ in ORDINALS:
        index = stranded(load, contracts)
        if index is None or index >= len(ORDINALS):
            break
        origin, destination = load[index]
        answer = ask(s, f"push {ORDINALS[index]} sturdy crate")
        if trade.GRABBED not in answer:
            unknown(s, PREFIX, "PUSH", answer)
            break
        for _ in range(2):
            answer = ask(s, "pull sturdy crate")
        after = trade.crates(ask(s, f"look {name}"))
        if after != load[:index] + load[index + 1 :]:
            s.echo(
                f"{PREFIX}: the {origin} crate for {destination} is still on the"
                f" caravan ({said(answer)!r}) — kept"
            )
            break
        load, gone = after, gone + 1
        s.echo(f"{PREFIX}: the {origin} crate for {destination} taken off the caravan")
    return gone


def put_away(s, db, place, contracts):
    """Every expired contract held put in this town's waste bin
    (trade.TRASH), never dropped: each got by its ordinal, read again in
    hand (READ MY CONTRACT reads the held one first) and PUT in the bin
    only when it reads expired. The number put away; an answer it does
    not expect keeps the contract, stowed, said."""
    room = trade.TRASH.get(place)
    if room is None or not any(c.expired for c in contracts):
        return 0
    gone = 0
    for _ in ORDINALS:
        index = next((i for i, c in enumerate(contracts) if c.expired), None)
        if index is None or not walk(s, db, room, f"the {place} waste bin"):
            break
        ask(s, f"get my {ORDINALS[index]} contract")
        lapsed = held(s) if hands.holding(s, "contract") else None
        answer = (
            discard.trash(s, "contract", ask) if lapsed and lapsed.expired else None
        )
        if answer is None:
            if hands.holding(s, "contract"):
                hands.stow(s, "contract")
            s.echo(f"{PREFIX}: could not put an expired contract away — kept")
            break
        gone += 1
        contracts = held_all(s)
    if gone:
        s.echo(f"{PREFIX}: {gone} expired contract(s) put in the {place} waste bin")
    return gone


def town_stop(s, db, name, place, contracts, due):
    """A circuit's work in this town: every `due` contract handed in, one
    issued here and never loaded loaded, PAY CLERK, the pay banked, the
    stranded crates taken off the caravan, and the town's own contract
    taken when none from it is held (not after a typed return or pause).
    The contracts still held, or None, said."""
    for _ in due:
        if not deliver(s, db, place, only=len(contracts) == 1):
            return None
    loaded = []
    for c in (c for c in contracts if c not in due):
        if unloaded(c) and trade.town(c.origin) == place:
            # Issued here and never loaded: a stop between the minister
            # and the clerk, or a town routed since it was issued.
            if not load(s, db, place, tradelog.log_issue(character(s), place, c)):
                return None
            c = c._replace(presented=True)
        loaded.append(c)
    contracts = loaded
    walk(s, db, trade.TOWNS[place].clerk, f"the {place} shipment clerk")
    s.echo(f"{PREFIX}: {pay(s)}")
    if due:
        bank_run(s, db, trade.coin(place))
    # Before the bin: an expired contract held is what marks its crate.
    if any(c.expired or (c.presented and beyond(c)) for c in contracts) and walk(
        s, db, trade.TOWNS[place].outpost, f"the {place} outpost"
    ):
        unload(s, name, contracts)
    if put_away(s, db, place, contracts):
        contracts = held_all(s)  # what is left
    ending = paused(s) or loop.wants_stop(s)
    if not ending and place not in held_from(contracts):
        contract = take(s, db, place)
        if contract is None:
            return None
        contracts.append(contract)
    return contracts


def expiry(s, place, contracts):
    """Held at `place` while every town waits on a contract beyond the
    routes (its minister issues none until it expires): True once one
    has expired, False at a typed return or pause or after EXPIRY_POLLS
    reads, said once with its ceiling."""
    s.echo(
        f"{PREFIX}: every town waits on a contract beyond the routes"
        f" ({', '.join(c.destination or 'expired' for c in contracts)}) — holding"
        f" at {place}"
        f" until one expires (up to {EXPIRY_POLL * EXPIRY_POLLS // 3600} hours)"
    )
    for _ in range(EXPIRY_POLLS):
        s.sleep(EXPIRY_POLL)
        if paused(s) or loop.wants_stop(s):
            return False
        if any(c.expired for c in held_all(s)):
            return True
    s.echo(f"{PREFIX}: none expired — stopping, the caravan kept at {place}")
    return False


def circuit(s, db, name, place, beside, training):
    """;trade circuit (#556): every contract for this town handed in,
    the town's own taken when none from it is held, the caravan led to
    the nearest town with business (a held crate goes to it, or no
    contract from it is held); again. A typed return or pause takes no
    new contract and ends once nothing is held."""
    while True:
        contracts = held_all(s)
        due = [
            c for c in contracts if c.presented and trade.town(c.destination) == place
        ]
        # Started beside its caravan with crates loaded (a run stopped on
        # the road): with none for this town it goes on from where it
        # stands, as the one-contract run does; with some, it is brought in.
        # With nothing loaded it is brought in for the clerk (2026-10-17: two
        # Fornsted contracts issued before Fornsted was routed), and with
        # nothing it can deliver: a contract beyond the routes reads
        # presented with its crate taken off (Langenfirth, 2026-10-18).
        if beside and not any(c.presented and not beyond(c) for c in contracts):
            if not bring(s, db, name, trade.TOWNS[place].outpost):
                return
            beside = False
        if not (beside and not due):
            if beside and not bring(s, db, name, trade.TOWNS[place].outpost):
                return
            beside = False
            contracts = town_stop(s, db, name, place, contracts, due)
            if contracts is None:
                return
        # Business: a town a held crate goes to, or one no contract is held
        # from yet, to take its own (trade.lic's set_next_outpost): without
        # the second, every stop's new contract would be the only one held.
        towns = {business(c) for c in contracts} - {None}
        if not (paused(s) or loop.wants_stop(s)):
            towns |= {
                town
                for town in province(place)
                if town not in held_from(contracts) and trade.routable(place, town)
            }
        towns.discard(place)
        if not towns:
            waiting = contracts and not (paused(s) or loop.wants_stop(s))
            if waiting and all(beyond(c) for c in contracts):
                if expiry(s, place, contracts):
                    continue
                return
            if contracts:
                s.echo(
                    f"{PREFIX}: what is held is for towns ;trade does not lead to"
                    f" ({', '.join(c.destination or 'expired' for c in contracts)})"
                    " — yours to deliver"
                )
            elif paused(s):
                s.echo(f"{PREFIX}: paused at {place} — the caravan kept at the outpost")
            else:
                s.echo(f"{PREFIX}: nothing held — done at {place}")
                return_caravan(s, db, place, name)
            return
        destination = next_stop(db, place, towns, tradelog.leg_minutes(character(s)))
        crates = sum(
            c.presented and trade.town(c.destination) == destination for c in contracts
        )
        loads = sum(
            unloaded(c) and trade.town(c.origin) == destination for c in contracts
        )
        s.echo(
            f"{PREFIX}: {len(contracts)} contract(s) held — next {destination} ("
            + (
                f"{crates} crate(s) for it"
                if crates
                else f"{loads} contract(s) to load"
                if loads
                else "its contract to take"
            )
            + ")"
        )
        if not beside and not walk(
            s, db, trade.TOWNS[place].outpost, f"the {place} outpost"
        ):
            return
        beside = False
        grass = feed(s, name)
        training = trainers(s, quiet=True)
        if grass is None or not leg(s, db, name, place, destination, [grass], training):
            return
        place = destination


def paused(s):
    """True once "pause" was typed at ;trade, held for the run. Read here
    first: loop.wants_stop drops every typed word but "return", which
    this keeps for it."""
    if getattr(s, "_pause_typed", False):
        return True
    while (line := s.command(timeout=0)) is not None:
        word = line.lower()
        flag = (
            "_pause_typed"
            if "pause" in word
            else "_return_typed"
            if "return" in word
            else None
        )
        if flag:
            try:
                setattr(s, flag, True)
            except AttributeError:  # a fake without attributes
                pass
            if flag == "_pause_typed":
                return True
    return False


def main(s):
    opts = parse_args(s.args)
    if opts["verb"] == "pause":
        s.echo(
            f"{PREFIX}: not running — nothing to pause (type ;trade pause while it runs)"
        )
        return
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
    if trade.RECALL_BUSY in answer:
        # Engaged: out of combat first, the RECALL after the retreats
        # through the type-ahead.
        s.put("retreat")
        s.put("retreat")
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
    if opts["verb"] == "circuit":
        circuit(s, db, name, place, beside, training)
        return
    while True:
        contract = held(s)
        delivered = False
        if contract and unloaded(contract) and trade.town(contract.origin) != place:
            # Issued elsewhere and never loaded: the circuit takes it back
            # to its clerk, the other contracts along.
            s.echo(
                f"{PREFIX}: the {contract.destination} contract is not loaded — on as a circuit"
            )
            circuit(s, db, name, place, beside, training)
            return
        if beside and contract is not None and not contract.presented:
            # Nothing loaded: the caravan is brought in for the clerk.
            if not bring(s, db, name, trade.TOWNS[place].outpost):
                return
        # Started beside the caravan with its crate loaded (a run stopped
        # mid-walk): it goes on from where it stands, brought to the
        # outpost first when this is its town.
        beside = beside and contract is not None and contract.presented
        if contract and trade.town(contract.destination) == place:
            if beside and not bring(s, db, name, trade.TOWNS[place].outpost):
                return
            if not deliver(s, db, place):
                return
            contract, delivered, beside = None, True, False
        if (
            contract
            and not contract.presented
            and trade.town(contract.origin) == place
            and not beyond(contract)
        ):
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
            if paused(s):
                s.echo(
                    f"{PREFIX}: paused at {place} — the caravan kept at the outpost;"
                    " ;trade carries on with it"
                )
                return
            if loop.wants_stop(s):
                s.echo(f"{PREFIX}: nothing held — done at {place}")
                return_caravan(s, db, place, name)
                return
            contract = take(s, db, place, broker)
            if contract is None:
                return
        if beyond(contract):
            if broker:
                s.echo(
                    f"{PREFIX}: the contract is for {contract.destination or '(expired)'}, which"
                    " ;trade does not lead to — deliver it yourself"
                )
                return
            # The minister issues no other while it is held (Therenborough's
            # Muspar'i contract, 2026-10-17): the province's other towns
            # go on, a contract held from each (#555).
            s.echo(
                f"{PREFIX}: the {contract.destination or 'expired'} contract kept unloaded —"
                f" on as a circuit from {place}"
            )
            circuit(s, db, name, place, beside, training)
            return
        destination = trade.town(contract.destination)
        if not beside and not walk(
            s, db, trade.TOWNS[place].outpost, f"the {place} outpost"
        ):
            return
        beside = False
        grass = feed(s, name)
        training = trainers(s, quiet=True)
        if grass is None or not leg(s, db, name, place, destination, [grass], training):
            return
        place = destination
