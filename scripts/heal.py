"""Eat the herb that treats each wound, buying what is missing:  ;heal

    ;heal                HEALTH, then EAT a carried herb for every wound at the floor or worse
    ;heal list           the wounds, the herbs that treat them and the town's shop; nothing eaten
    ;heal buy            ... coins from the teller, the missing herbs ORDERed at the herbalist, eaten
    ;heal floor=minor    treat wounds this bad or worse (default insignificant)
    ;heal npc            walk to the nearest NPC healer, DEMEANOR FRIENDLY EMPATH, LIE DOWN, paid per part in the province's coin
    ;heal quentin        ... Shard's Quentin by name (arthianna, fraethis, healer=<word in the room's title> likewise); foreign coins EXCHANGEd at the money-changer by the healer first
    ;heal <empath>       log in your own Empath character (riphik), walk them to you, ;empath <you>, log them out
    ;heal <empath> stay  ... and leave them logged in for the next time
    ;heal return         (typed while it runs) end after the herb in hand, or tell the Empath to finish

Wounds are read from HEALTH by client/game/wounds.py (area, kind,
severity) and answered by client/game/herbs.py, whose table is
Elanthipedia's Healing herbs page: jadice flower for external limb
wounds, nemoih root for the head, plovik leaves for the chest, yelith
root for internal limb damage, and so on — the first herb the town
sells, else the first the table names, one EAT per herb per run since
a herb heals its part over time (docs/healing.md). Bleeding is not
healed here: a bleeder is reported and ;tend is the answer. In the
Crossing the herbalist is Mauriga's Botanicals (map tag `herbalist`,
room 8259; Elanthipedia lists jadice, plovik, nilos, hulnik, nemoih,
georin and sufil at 812-875 Kronars and yelith, ithor, muljin,
junliar, blocil and riolur at 937-1000, 2026-09-14); the Alchemy
Society's dried lots are crafting stock, so a herb only the Society
lists — the scar herbs genich, ojhenik, nuloe, dioica — is not for
sale to eat in the Crossing, said so before any walk (a run walked to
Mauriga's and ORDERed all four of them, 2026-09-20; scars mend under
an Empath). A catalog merchant sells by
ORDER, which quotes, then OFFER of the quoted sum (HELP SHOPS; Grek's
knife 2026-09-14: "Well done! Here, take your knife."). `buy` reads
INFO for the coins carried, WITHDRAWs the wiki-priced shortfall at the
nearest teller (map tag `bank`), walks to the herbalist, ORDERs and
OFFERs each missing herb by her catalog's whole name — READ PAGE 1 and
2 at her pedestal, captured 2026-09-25: the table's nilos grass and
georin grass are her Nilos Salve and Georin Salve, plovik leaves her
Plovik Leaf, and "order jadice" alone is answered out of stock while
"order jadice flower" quotes (#308) — takes it on the spot and stows
what is left, so a hand stays free for the next one. A salve or sap is
RUBbed on, a potion DRUNK, the rest EATen (dr-scripts' heal-remedy.lic;
RUB captured 2026-09-25: "You rub a portion of some nilos salve on
yourself.", DRINK not yet), a carried herb looked for in
the catalog's form first, then as foraged. A quote it will not pay is
REFUSEd — an open one blocks every ORDER after it ("you've already
ordered something else.  Let's deal with one negotiation at a time"),
and REFUSE answers "Perhaps another day." Captured
2026-09-14 at Mauriga's: "That is a very wise selection.  I can give
the root to you for 875 kronars.", "Mauriga smiles as she hands you
your purchase.", with both hands full "Mauriga notices that your
hands are full, and places it on the counter instead." (the script
GETs it from the counter), "I'm so sorry to disappoint you, but I
don't have that reagent in stock.", and EAT's "You eat a portion of
a nemoih root." — a root has portions, and the rest goes in the sack.
A herb the shop quotes above the purse is skipped, said so. Nothing
walks back afterwards.
An Empath of your own (`;heal riphik`, any word that is not one of the
above) is logged in the way ;train logs in a helper
(client/game/helper.py): found in the registry or spawned off the
keychain — the account's other character given ;logout first, since
an account plays one character at a time — walked to the room you
stand in, and started on `;empath <you>`, which takes every wound
and scar and heals the Empath after (scripts/empath.py). This waits
while that runs (the Empath session's `scripts` state), then logs a
spawned Empath out unless told `stay`; one already logged in stays.
The operator, 2026-09-27: Riphik heals new characters better than
any herb, scars and internal bleeding included.
`npc` is the hospital instead of herbs — what heals nerve damage and
internal scars no shop's herb touches (#218): the nearest room the map
tags `npchealer` (Knife Clan's retired Dokt excluded; Shard's Quentin,
Riverhaven's Fraethis, Elanthipedia: Hospital), DEMEANOR FRIENDLY
EMPATH (Quentin's gate: "The healer Quentin looks towards you, and you
pull away." with a neutral one; the demeanor stays friendly after —
the operator, 2026-09-21), LIE DOWN, and he works part by part —
"Quentin glances oddly at you and then touches your nervous system,
snickering all the while.  After a moment it feels better." /
"[72 Dokoras are taken from you.]", captured 2026-09-19 — until twenty
quiet seconds; then STAND, HEALTH, and what he took and what is left
are said. The healer is the nearest from where the character stands,
and his town decides the coin (the lowest-numbered one on the map
decided it until 2026-09-26, when a Riverhaven Barbarian was sent to
exchange his Lirums in another province and never left). A healer
paid on credit when the purse runs short — "[Your debt to Therengia
has been increased by 172 Lirums.]", Riverhaven's Fraethis, captured
2026-09-26 — is counted as a paid part and said as debt. An empty purse stops it before the walk: he takes the
province's coins (Dokoras in Shard — the province read off the map's
town for his room), and a purse of foreign coins only is EXCHANGEd
first at the money-changer nearest him (First Bank of Ilithi's Coin
Exchange), the way ;bank does it. Nothing walks back afterwards.
Stops on death and on `return`.
Stop with:  ;stop heal (at once), or ;heal return for a clean finish.
"""

import re

from client.game import helper, herbs, probe
from client.game.loop import wants_stop
from client.game.bank import exchange_command, foreign, handed
from client.game.mapdb import MapDB
from client.game.money import parse_wealth, phrase, split
from client.game.soul import currency_for
from client.game.walker import avoided_rooms, locate, walk
from client.game.wounds import SEVERITIES, level, parse_health
from client.settings import load_settings

TOWN = "Crossing"
DEFAULT_FLOOR = "insignificant"
COLLECT_SECONDS = 3
TAIL_SECONDS = 1.0
HEALTH_SECONDS = 2

# Mauriga's Botanicals' catalog by the herb table's name: what she
# sells it as — READ PAGE 1 / READ PAGE 2 at her pedestal, captured
# 2026-09-25 ("Nilos Salve", "Georin Salve", "Plovik Leaf": the table's
# nilos grass, georin grass and plovik leaves come from her as those)
# — and Elanthipedia's price (2026-09-14), the estimate `buy`
# withdraws against; the shop's quote is the judge. ORDER wants the
# whole catalog name: "order jadice" is answered out of stock, "order
# jadice flower" quotes (#308).
CATALOG = {
    "jadice flower": ("jadice flower", 812),
    "plovik leaves": ("plovik leaf", 812),
    "nilos grass": ("nilos salve", 812),
    "hulnik grass": ("hulnik grass", 812),
    "nemoih root": ("nemoih root", 875),
    "georin grass": ("georin salve", 875),
    "sufil sap": ("sufil sap", 875),
    "yelith root": ("yelith root", 937),
    "ithor potion": ("ithor potion", 937),
    "muljin sap": ("muljin sap", 937),
    "junliar stem": ("junliar stem", 937),
    "blocil potion": ("blocil potion", 937),
    "riolur leaf": ("riolur leaf", 1000),
}
PRICES = {herb: price for herb, (_, price) in CATALOG.items()}
# How a remedy is taken, by its last word (dr-scripts' heal-remedy.lic:
# salves and saps are rubbed on, potions drunk, the rest eaten).
RUBBED = ("salve", "sap", "unguent", "ointment", "poultice", "poultices")
DRUNK = ("potion", "tonic", "elixir", "draught")
FALLBACK_PRICE = 1000  # a herb the table does not price
# EAT, captured 2026-09-14: "You eat a portion of a nemoih root." An
# answer outside the tables counts as eaten and is reported.
EAT_OUTCOMES = (
    (
        "missing",
        (
            "what were you referring",
            "could not find",
            "referring to",
            "rub what",
            "drink what",
        ),
    ),
    # "You rub a portion of some nilos salve on yourself." (captured
    # 2026-09-25); "you drink" is heal-remedy.lic's, not captured yet.
    (
        "ok",
        (
            "you eat",
            "you take a bite",
            "you chew",
            "you swallow",
            "you nibble",
            "you rub",
            "you drink",
            "you take a drink",
        ),
    ),
)
# ORDER's quote and OFFER's sale at a catalog merchant. Grek's
# 2026-09-14: "I can let that go for a mere 375 kronars." / "Well
# done! Here, take your knife."; Mauriga's the same day: "That is a
# very wise selection.  I can give the root to you for 875 kronars.",
# "Mauriga smiles as she hands you your purchase.", with both hands
# full "Mauriga notices that your hands are full, and places it on
# the counter instead.", and out of stock "I'm so sorry to disappoint
# you, but I don't have that reagent in stock."
_QUOTE = re.compile(r"(\d[\d,]*)\s*kronars?", re.IGNORECASE)
OUT_OF_STOCK = ("don't have that reagent", "not in stock", "don't carry")
# A quote still open blocks the next ORDER (captured 2026-09-25):
# "Master Lanival, you've already ordered something else.  Let's deal
# with one negotiation at a time, shall we?" REFUSE closes one: "Mauriga
# nods to you.  "Perhaps another day.  In the meantime, make sure that
# you eat a sicle fruit a day!"" (Elanthipedia: Offer command).
OPEN_ORDER = ("one negotiation at a time", "already ordered something")
SALE_OUTCOMES = (
    ("refused", ("don't have enough", "not enough", "can't afford", "insufficient")),
    ("counter", ("places it on the counter",)),
    ("ok", ("hands you your purchase", "take your", "hands you", "here you go")),
)
WITHDRAW_REFUSALS = ("you do not have", "insufficient", "no account", "don't have that")
# The NPC healer (#218; Elanthipedia: Hospital): LIE DOWN starts the
# touches, each "[72 Dokoras are taken from you.]"; Quentin refuses a
# neutral demeanor with "The healer Quentin looks towards you, and you
# pull away." (captured 2026-09-19).
_TAKEN = re.compile(r"\[(\d+) (\w+) are taken from you\.\]")
# A healer paid on credit when the purse runs short (Riverhaven's
# Fraethis, 2026-09-26, 13 Lirums on hand): "[Your debt to Therengia
# has been increased by 172 Lirums.]" — a part healed all the same.
_DEBT = re.compile(r"\[Your debt to (\w+) has been increased by (\d+) (\w+)\.\]")
HEALER_TOUCHED = ("feels better", "touches you", "feels a bit better")
HEALER_REFUSED = ("pull away",)
# The healer done with what he will touch (captured 2026-09-21, the
# internal scars of five backfires left): "Quentin whispers, "Just
# between you and me and the Queen, I think you don't really need
# healing.  Are you just my friend or something?""
# Arthianna's for a patient with scars alone (captured 2026-09-21):
# "Arthianna nudges you.  "What are you doing lying there with the
# wounded?" she grins." — "heals all wounds" stops at scars too.
HEALER_DONE = ("don't really need healing", "lying there with the wounded")
DEMEANOR_SET = ("friendly demeanor",)
HEALER_POLL = 5  # seconds per look at the stream while the healer works
HEALER_WAIT = 90  # seconds for the first touch after LIE DOWN
HEALER_QUIET = 20  # seconds without a touch that end the visit


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def parse_args(args):
    options = {
        "mode": "eat",
        "floor": DEFAULT_FLOOR,
        "healer": "",
        "empath": "",
        "stay": False,
    }
    for arg in args:
        low = arg.strip().lower()
        if low in ("list", "buy", "npc"):
            options["mode"] = low
        elif low.startswith("healer="):
            options["mode"], options["healer"] = "npc", low.split("=", 1)[1]
        elif low in ("quentin", "arthianna", "fraethis"):
            options["mode"], options["healer"] = "npc", low
        elif low.startswith("floor="):
            options["floor"] = low.split("=", 1)[1]
        elif low == "stay":
            options["stay"] = True
        elif low and low != "return":
            # Any other word names an Empath of your own: `;heal riphik`.
            options["mode"], options["empath"] = "empath", arg.strip().capitalize()
    return options


def herb_area(area):
    """HEALTH's area as the herb table's: limbs fold into "limb"."""
    last = area.split()[-1]
    if last in ("arm", "leg", "hand", "foot", "tail"):
        return "limb"
    return last


def prescriptions(health, floor, town=TOWN):
    """{herb: [(area, kind, level)]} for every wound at the floor or
    worse: the first herb the town sells, else the table's first.
    Wounds with no herb at all go under None."""
    plan = {}
    for area, kind, lvl in sorted(health.at_least(floor)):
        options = herbs.remedies(herb_area(area), kind)
        chosen = next((name for name in options if herbs.sources_in(name, town)), None)
        chosen = chosen or (options[0] if options else None)
        plan.setdefault(chosen, []).append((area, kind, lvl))
    return plan


# The stores the map knows, by the herb table's (the wiki's) name and
# the map's tag. A herb none of them lists is not for sale to eat in
# the town: the Alchemy Society's dried lots are crafting stock, and
# the scar herbs come only that way in the Crossing (2026-09-20).
STORE_TAGS = {"Mauriga's Botanicals (Crossing)": "herbalist"}
UNSOLD = "not sold to eat in the {town} (the Alchemy Society's lots are crafting stock; scars mend under an Empath)"
_DOUBLED_TOWN = re.compile(r"\(([^()]+)\) \(\1\)")  # "... (Crossing) (Crossing)"


def shops_for(herb, town=TOWN):
    """The town's stores for a herb, deduplicated, in the wiki's order,
    a doubled town name folded ("Alchemy Society (Crossing) (Crossing)"
    is how the wiki writes it)."""
    stores = []
    for _, names in herbs.sources_in(herb, town):
        for name in names:
            name = _DOUBLED_TOWN.sub(r"(\1)", name)
            if name not in stores:
                stores.append(name)
    return stores


def store_tag(herb, town=TOWN):
    """The map tag of a store that sells the herb to eat — the
    herbalist for everything on her catalog (PRICES, Elanthipedia's
    page of it, whole) or in whose store list she stands — or None."""
    if herb in PRICES:
        return "herbalist"
    for store in shops_for(herb, town):
        if store in STORE_TAGS:
            return STORE_TAGS[store]
    return None


def describe_plan(s, plan, town=TOWN):
    for herb, wounds in plan.items():
        where = ", ".join(shops_for(herb, town)) if herb else ""
        hurt = "; ".join(
            f"{area} {kind.replace('_', ' ')} {SEVERITIES[lvl]}"
            for area, kind, lvl in wounds
        )
        if herb is None:
            s.echo(f"heal: no herb in the table for {hurt}")
        else:
            s.echo(
                f"heal: {herb} for {hurt}" + (f" — sold at {where}" if where else "")
            )


def product(herb):
    """What the herbalist sells a herb as — her catalog's whole name
    ("nilos salve" for the table's nilos grass) — else the herb."""
    return CATALOG.get(herb, (herb, None))[0]


def take_command(item):
    """RUB MY <salve or sap>, DRINK MY <potion>, EAT MY <the rest>."""
    last = item.split()[-1]
    if last in RUBBED:
        return f"rub my {item}"
    if last in DRUNK:
        return f"drink my {item}"
    return f"eat my {item}"


def eat(s, herb):
    """Take the herb — the catalog's form first (a bought salve is
    rubbed on), then the herb itself as foraged; "missing", "ok", or
    None for a wording outside the tables (reported by the caller,
    counted as eaten)."""
    forms = list(dict.fromkeys([product(herb), herb]))
    for form in forms:
        answer = ask(s, take_command(form))
        outcome = probe.classify(answer, EAT_OUTCOMES)
        if outcome != "missing":
            return outcome, answer
    return "missing", answer


def eat_and_stow(s, herb, eaten):
    """Take a herb just bought (by the catalog's name, what is in hand)
    and stow what is left — a root has portions — so a hand stays
    free."""
    item = product(herb)
    answer = ask(s, take_command(item))
    outcome = probe.classify(answer, EAT_OUTCOMES)
    if outcome == "missing":
        s.echo(f"heal: {item} is not in hand to take")
        return
    if outcome is None:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(
            f"heal: unrecognized answer to {take_command(item)!r}: {first!r} — please report it"
        )
    eaten.append(herb)
    s.echo(f"heal: took {item} for {herb}" if item != herb else f"heal: ate {herb}")
    ask(s, f"stow my {item}")


def carried(s):
    """INFO's carried Kronars in copper."""
    info = parse_wealth(ask(s, "info"))
    return info["carried"].get("Kronars", 0)


def withdraw(s, shortfall, mapdb, walk_fn, avoid=()):
    """Walk to the nearest teller and WITHDRAW the shortfall, one
    denomination per command; False when refused or unreachable."""
    tellers = mapdb.rooms_tagged("bank")
    if not tellers:
        s.echo("heal: the map has no room tagged 'bank'")
        return False
    if not walk_fn(s, mapdb, set(tellers), describe="the bank teller", avoid=avoid):
        s.echo("heal: could not reach a teller — stopping")
        return False
    s.echo(f"heal: withdrawing {phrase(shortfall, 'Kronars')}")
    for count, denomination in split(shortfall):
        answer = ask(s, f"withdraw {count} {denomination}")
        if any(word in answer.lower() for word in WITHDRAW_REFUSALS):
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"heal: the teller refused — {first}")
            return False
    return True


def buy(s, wanted, mapdb, walk_fn, avoid=(), town=TOWN):
    """Coins for the wanted herbs, then each ORDERed by the catalog's name, paid
    for and eaten at the store the table says sells it (STORE_TAGS),
    one at a time so a hand stays free; the herbs eaten, in order. A
    herb no known store sells to eat is said so, and walked for by no
    one."""
    for herb in [herb for herb in wanted if store_tag(herb, town) is None]:
        s.echo(f"heal: {herb} is {UNSOLD.format(town=town)}")
    wanted = [herb for herb in wanted if store_tag(herb, town) is not None]
    if not wanted:
        return []
    estimate = sum(PRICES.get(herb, FALLBACK_PRICE) for herb in wanted)
    purse = carried(s)
    if purse < estimate and not withdraw(s, estimate - purse, mapdb, walk_fn, avoid):
        return []
    purse = max(purse, estimate)
    tag = store_tag(wanted[0], town)
    shops = mapdb.rooms_tagged(tag)
    if not shops:
        s.echo(f"heal: the map has no room tagged {tag!r}")
        return []
    if not walk_fn(s, mapdb, set(shops), describe="the herbalist", avoid=avoid):
        s.echo("heal: could not reach the herbalist — stopping")
        return []
    eaten = []
    for herb in wanted:
        if s.dead:
            break
        item = product(herb)
        answer = ask(s, f"order {item}")
        if any(word in answer.lower() for word in OPEN_ORDER):
            ask(s, "refuse")  # a quote left open blocks every ORDER
            answer = ask(s, f"order {item}")
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        if any(word in answer.lower() for word in OUT_OF_STOCK):
            s.echo(f"heal: {herb} is not in stock here")
            continue
        match = _QUOTE.search(answer)
        if not match:
            s.echo(f"heal: no quote for {item} — {first}")
            continue
        price = int(match.group(1).replace(",", ""))
        if price > purse:
            ask(s, "refuse")
            s.echo(
                f"heal: {item} is {price} Kronars, more than the {purse} carried — skipped"
            )
            continue
        answer = ask(s, f"offer {price}")
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        outcome = probe.classify(answer, SALE_OUTCOMES)
        if outcome == "refused":
            ask(s, "refuse")
            s.echo(f"heal: the herbalist refused {price} for {item} — {first}")
            continue
        if outcome is None:
            s.echo(f"heal: unrecognized sale answer {first!r} — please report it")
        purse -= price
        s.echo(f"heal: bought {item} for {price} Kronars")
        if outcome == "counter":
            ask(s, f"get {item} from counter")
        eat_and_stow(s, herb, eaten)
    return eaten


def home_of(mapdb, room):
    """The province's coin at a map room: from its title, else from the
    map's own name for the room's town (Quentin's Healerium names no
    town, its map image "Ilithi, Shard" does)."""
    data = mapdb.rooms[room]
    title = " ".join(data.get("title") or [])
    home = currency_for(title)
    if home == "kronars":
        home = currency_for(str(data.get("image") or ""))
    return home


def change_coins(s, mapdb, walk_fn, healer_room, purse, home, avoid=()):
    """The purse's foreign coins into the healer's province's, at the
    money-changer nearest the healer (the walker's nearest would be the
    one behind, in the town the walk started from). False, said, when
    none is on the map or reachable."""
    changers = mapdb.rooms_tagged("exchange")
    if not changers:
        s.echo("heal: the map has no room tagged 'exchange' — carry the coins yourself")
        return False
    route = mapdb.path(healer_room, changers, avoid=avoid)
    goals = {route[-1][0]} if route else set(changers)
    if not walk_fn(s, mapdb, goals, describe="the money-changer", avoid=avoid):
        s.echo("heal: could not reach a money-changer — stopping")
        return False
    for currency in foreign({"carried": purse}, home):
        answer = ask(s, exchange_command(currency, home))
        got = handed(answer)
        if got:
            s.echo(f"heal: exchanged your {currency} for {got}")
        else:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"heal: the money-changer answered {first!r} to the {currency}")
    return True


def nearest_healer(s, mapdb, rooms, avoid=()):
    """The healer room the walk will reach: the nearest of `rooms` from
    where the character stands (walker.locate), the lowest id when the
    position or a path is unknown. Its town decides the coin and the
    money-changer — the lowest id alone sent a Riverhaven Barbarian's
    Lirums to be exchanged beside a healer in another province, with no
    path there, and the visit stopped before a step (2026-09-26)."""
    here = locate(mapdb, getattr(s, "state", None))
    if here in rooms:
        return here
    if here is not None:
        route = mapdb.path(here, rooms, avoid=avoid)
        if route:
            return route[-1][0]
    return min(rooms)


def visit_healer(s, mapdb, walk_fn=walk, avoid=(), healer=""):
    """The hospital: walk to the nearest NPC healer (or the one named,
    "quentin"), DEMEANOR FRIENDLY EMPATH, LIE DOWN, let the touches run
    until twenty quiet seconds, STAND, HEALTH. What was taken and what
    is left are said. Returns (reason, []) in run()'s shape."""
    if mapdb is None:
        s.echo("heal: the walk to the healer needs the map — none loaded")
        return "no map", []
    rooms = {
        room
        for room in mapdb.rooms_tagged("npchealer")
        if "dokt" not in (mapdb.rooms[room].get("tags") or [])
        and (
            not healer
            or healer in " ".join(mapdb.rooms[room].get("title") or []).lower()
        )
    }
    if not rooms:
        who = (
            f"a healer named {healer!r}"
            if healer
            else "'npchealer' but Knife Clan's kitchen"
        )
        s.echo(f"heal: the map has no room tagged {who}")
        return "no healer", []
    purse = parse_wealth(ask(s, "info"))["carried"]
    if not any(purse.values()):
        s.echo(
            "heal: the purse is empty — the healer takes the province's coins per "
            "part (Dokoras in Shard); ;bank exchanges foreign coins at the "
            "money-changer"
        )
        return "no coins", []
    healer_room = nearest_healer(s, mapdb, rooms, avoid)
    home = home_of(mapdb, healer_room)
    if not purse.get(home.capitalize(), 0):
        # Only foreign coins: the money-changer by the healer first.
        if not change_coins(s, mapdb, walk_fn, healer_room, purse, home, avoid):
            return "no coins", []
    if not walk_fn(s, mapdb, {healer_room}, describe="the NPC healer", avoid=avoid):
        s.echo("heal: could not reach the healer — stopping")
        return "unreachable", []
    taken, parts, currency = 0, 0, ""
    owed, province = 0, ""

    def absorb(text):
        nonlocal taken, parts, currency, owed, province
        touched = False
        for match in _TAKEN.finditer(text):
            taken += int(match.group(1))
            currency = match.group(2)
            parts += 1
            touched = True
        for match in _DEBT.finditer(text):
            province = match.group(1)
            owed += int(match.group(2))
            currency = match.group(3)
            parts += 1
            touched = True
        return touched or any(word in text.lower() for word in HEALER_TOUCHED)

    answer = ask(s, "demeanor friendly empath")
    if not any(word in answer.lower() for word in DEMEANOR_SET):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"heal: unrecognized demeanor answer {first!r} — please report it")
    touched = absorb(answer)
    answer = ask(s, "lie down")
    refused = any(word in answer.lower() for word in HEALER_REFUSED)
    touched = absorb(answer) or touched
    waited = idle = 0
    done = any(word in answer.lower() for word in HEALER_DONE)
    while not refused and not done and not s.dead and not wants_stop(s):
        text = probe.collect(s, HEALER_POLL)
        if any(word in text.lower() for word in HEALER_REFUSED):
            refused = True
            break
        if any(word in text.lower() for word in HEALER_DONE):
            done = True
            absorb(text)
            break
        if absorb(text):
            touched, idle = True, 0
            continue
        idle += HEALER_POLL
        waited += HEALER_POLL
        if touched and idle >= HEALER_QUIET:
            break
        if not touched and waited >= HEALER_WAIT:
            break
    ask(s, "stand")
    if refused:
        s.echo(
            "heal: the healer would not touch you — the demeanor gate; please report the answer"
        )
    if done:
        s.echo(
            "heal: the healer says the rest needs no healing — scars are left to an "
            "Empath or a herb"
        )
    health = parse_health(ask(s, "health"))
    left = ", ".join(health.wounds) if health.wounds else "nothing, HEALTH is clean"
    paid = f"took {taken} {currency or 'coins'}"
    if owed:
        paid = (
            f"took {taken} and put {owed} {currency} on your {province} debt"
            if taken
            else f"put {owed} {currency} on your {province} debt"
        )
    s.echo(f"heal: the healer {paid} for {parts} part(s) — left: {left}")
    return ("healed" if parts else "not healed"), []


EMPATH_SCRIPT = "empath"
EMPATH_MINUTES = (
    30  # the Empath's whole run: a login, the walk, the rounds, the self-heal
)
EMPATH_POLL = 10  # seconds between looks at the Empath's running scripts


def call_empath(s, name, stay, mapdb, io=None):
    """An Empath of your own logged in (or found), brought to your room,
    started on ;empath <you> and waited for; logged out after when this
    run spawned them, unless `stay`. The reason the call ended."""
    if not wounded_now(s):
        return "no wounds"
    patient = str(getattr(s.state, "name", "") or "")
    here = locate(mapdb, getattr(s, "state", None)) if mapdb is not None else None
    if not patient or here is None:
        return f"your room is not on the map — {name} cannot be walked to you"
    io = io or helper.SessionIO(s, mapdb)
    active = helper.ensure(io, name, s.echo, own_port=io.own_port())
    if active is None:
        return f"{name} could not be had"
    ended = False
    reason = f"{name} did not reach you"
    if helper.bring(io, active, str(here), s.echo):
        helper.start(io, active, EMPATH_SCRIPT, [patient.lower()])
        s.echo(f"heal: {name} started ;{EMPATH_SCRIPT} {patient.lower()}")
        reason = f"{name} ran out of time"
        deadline = io.now() + EMPATH_MINUTES * 60
        while io.now() < deadline:
            if s.dead:
                reason = "you are dead"
                break
            if wants_stop(s):
                reason = "returning on request"
                break
            if helper.running(io, active, EMPATH_SCRIPT) is False:
                ended = True
                reason = f"{name} is done"
                break
            io.sleep(EMPATH_POLL)
    helper.finish(io, active, EMPATH_SCRIPT, stay or not active.spawned, s.echo, ended)
    if active.spawned and stay:
        s.echo(f"heal: {name} stays logged in")
    if reason == f"{name} is done" and wounded_now(s):
        reason += " — some wounds remain"
    return reason


def wounded_now(s):
    """HEALTH says a wound, a scar or a bleeder."""
    health = parse_health(ask(s, "health"))
    return bool(health.wounds or health.bleeding)


def run(s, options, mapdb=None, walk_fn=walk, avoid=()):
    """Returns (reason, eaten)."""
    if options["mode"] == "empath":
        return call_empath(s, options["empath"], options["stay"], mapdb), []
    if options["mode"] == "npc":
        return visit_healer(s, mapdb, walk_fn, avoid, healer=options["healer"])
    health = parse_health(ask(s, "health"))
    if not health.wounds and not health.bleeding:
        return "no wounds", []
    if any(row["severity"] for row in health.bleeders()):
        s.echo("heal: you are bleeding — ;tend first")
    plan = prescriptions(health, level(options["floor"]))
    if not plan:
        return f"nothing at {options['floor']} or worse", []
    describe_plan(s, plan)
    if options["mode"] == "list":
        return "listed", []
    eaten, missing = [], []
    for herb in plan:
        if herb is None:
            continue
        if s.dead:
            return "you are dead", eaten
        if wants_stop(s):
            return "returning on request", eaten
        outcome, answer = eat(s, herb)
        if outcome == "missing":
            missing.append(herb)
            continue
        if outcome is None:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"heal: unrecognized eat answer {first!r} — please report it")
        eaten.append(herb)
        s.echo(f"heal: ate {herb}")
    if missing and options["mode"] == "buy" and mapdb is not None:
        eaten.extend(buy(s, missing, mapdb, walk_fn, avoid))
        missing = [herb for herb in missing if herb not in eaten]
    for herb in missing:
        where = ", ".join(shops_for(herb)) or "no shop the table knows"
        s.echo(f"heal: no {herb} carried — {where}")
    return "done", eaten


def main(s):
    options = parse_args(s.args or [])
    db = MapDB.load() if options["mode"] in ("buy", "npc", "empath") else None
    avoid = avoided_rooms(db, load_settings().get("avoid_rooms")) if db else ()
    reason, eaten = run(s, options, mapdb=db, avoid=avoid)
    s.echo(f"heal: {reason} — {len(eaten)} herb(s) eaten")
