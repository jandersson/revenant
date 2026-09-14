"""Eat the herb that treats each wound, buying what is missing:  ;heal

    ;heal                HEALTH, then EAT a carried herb for every wound at the floor or worse
    ;heal list           the wounds, the herbs that treat them and the town's shop; nothing eaten
    ;heal buy            ... coins from the teller, the missing herbs ORDERed at the herbalist, eaten
    ;heal floor=minor    treat wounds this bad or worse (default insignificant)
    ;heal return         (typed while it runs) end after the herb in hand

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
Society's dried lots are crafting stock. A catalog merchant sells by
ORDER, which quotes, then OFFER of the quoted sum (HELP SHOPS; Grek's
knife 2026-09-14: "Well done! Here, take your knife."). `buy` reads
INFO for the coins carried, WITHDRAWs the wiki-priced shortfall at the
nearest teller (map tag `bank`), walks to the herbalist, ORDERs and
OFFERs each missing herb by its first word (her catalog says "plovik
leaf" where the table says "plovik leaves"), eats it on the spot and
stows what is left, so a hand stays free for the next one. Captured
2026-09-14 at Mauriga's: "That is a very wise selection.  I can give
the root to you for 875 kronars.", "Mauriga smiles as she hands you
your purchase.", with both hands full "Mauriga notices that your
hands are full, and places it on the counter instead." (the script
GETs it from the counter), "I'm so sorry to disappoint you, but I
don't have that reagent in stock.", and EAT's "You eat a portion of
a nemoih root." — a root has portions, and the rest goes in the sack.
A herb the shop quotes above the purse is skipped, said so. Nothing
walks back afterwards.
Stops on death and on `return`.
Stop with:  ;stop heal (at once), or ;heal return for a clean finish.
"""

import re

from client.game import herbs, probe
from client.game.mapdb import MapDB
from client.game.money import parse_wealth, phrase, split
from client.game.walker import avoided_rooms, walk
from client.game.wounds import SEVERITIES, level, parse_health
from client.settings import load_settings

TOWN = "Crossing"
DEFAULT_FLOOR = "insignificant"
COLLECT_SECONDS = 3
TAIL_SECONDS = 1.0
HEALTH_SECONDS = 2

# Mauriga's Botanicals' prices from Elanthipedia (2026-09-14), the
# estimate `buy` withdraws against; the shop's quote is the judge.
PRICES = {
    "jadice flower": 812,
    "plovik leaves": 812,
    "nilos grass": 812,
    "hulnik grass": 812,
    "nemoih root": 875,
    "georin grass": 875,
    "sufil sap": 875,
    "yelith root": 937,
    "ithor potion": 937,
    "muljin sap": 937,
    "junliar stem": 937,
    "blocil potion": 937,
    "riolur leaf": 1000,
}
FALLBACK_PRICE = 1000  # a herb the table does not price
# EAT, captured 2026-09-14: "You eat a portion of a nemoih root." An
# answer outside the tables counts as eaten and is reported.
EAT_OUTCOMES = (
    ("missing", ("what were you referring", "could not find", "referring to")),
    ("ok", ("you eat", "you take a bite", "you chew", "you swallow", "you nibble")),
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
SALE_OUTCOMES = (
    ("refused", ("don't have enough", "not enough", "can't afford", "insufficient")),
    ("counter", ("places it on the counter",)),
    ("ok", ("hands you your purchase", "take your", "hands you", "here you go")),
)
WITHDRAW_REFUSALS = ("you do not have", "insufficient", "no account", "don't have that")


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def parse_args(args):
    options = {"mode": "eat", "floor": DEFAULT_FLOOR}
    for arg in args:
        low = arg.strip().lower()
        if low in ("list", "buy"):
            options["mode"] = low
        elif low.startswith("floor="):
            options["floor"] = low.split("=", 1)[1]
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


def shops_for(herb, town=TOWN):
    """The town's stores for a herb, deduplicated, in the wiki's order."""
    stores = []
    for _, names in herbs.sources_in(herb, town):
        for name in names:
            if name not in stores:
                stores.append(name)
    return stores


def wants_stop(s):
    while (line := s.command(timeout=0)) is not None:
        if "return" in line.lower():
            return True
    return False


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


def stem(herb):
    """The word the shop and the hands know a herb by: "jadice" of
    "jadice flower"."""
    return herb.split()[0]


def eat(s, herb):
    """EAT the herb; "missing", "ok", or None for a wording outside the
    tables (reported by the caller, counted as eaten)."""
    answer = ask(s, f"eat my {herb}")
    return probe.classify(answer, EAT_OUTCOMES), answer


def eat_and_stow(s, herb, eaten):
    """EAT a herb just bought (by its stem, the noun in hand) and stow
    what is left — a root has portions — so a hand stays free."""
    outcome, answer = eat(s, stem(herb))
    if outcome == "missing":
        s.echo(f"heal: {herb} is not in hand to eat")
        return
    if outcome is None:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"heal: unrecognized eat answer {first!r} — please report it")
    eaten.append(herb)
    s.echo(f"heal: ate {herb}")
    ask(s, f"stow my {stem(herb)}")


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
    """Coins for the wanted herbs, then each ORDERed by its stem, paid
    for and eaten at the nearest herbalist, one at a time so a hand
    stays free; the herbs eaten, in order."""
    estimate = sum(PRICES.get(herb, FALLBACK_PRICE) for herb in wanted)
    purse = carried(s)
    if purse < estimate and not withdraw(s, estimate - purse, mapdb, walk_fn, avoid):
        return []
    purse = max(purse, estimate)
    shops = mapdb.rooms_tagged("herbalist")
    if not shops:
        s.echo("heal: the map has no room tagged 'herbalist'")
        return []
    if not walk_fn(s, mapdb, set(shops), describe="the herbalist", avoid=avoid):
        s.echo("heal: could not reach the herbalist — stopping")
        return []
    eaten = []
    for herb in wanted:
        if s.dead:
            break
        answer = ask(s, f"order {stem(herb)}")
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        if any(word in answer.lower() for word in OUT_OF_STOCK):
            s.echo(f"heal: {herb} is not in stock here")
            continue
        match = _QUOTE.search(answer)
        if not match:
            s.echo(f"heal: no quote for {herb} — {first}")
            continue
        price = int(match.group(1).replace(",", ""))
        if price > purse:
            s.echo(
                f"heal: {herb} is {price} Kronars, more than the {purse} carried — skipped"
            )
            continue
        answer = ask(s, f"offer {price}")
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        outcome = probe.classify(answer, SALE_OUTCOMES)
        if outcome == "refused":
            s.echo(f"heal: the herbalist refused {price} for {herb} — {first}")
            continue
        if outcome is None:
            s.echo(f"heal: unrecognized sale answer {first!r} — please report it")
        purse -= price
        s.echo(f"heal: bought {herb} for {price} Kronars")
        if outcome == "counter":
            ask(s, f"get {stem(herb)} from counter")
        eat_and_stow(s, herb, eaten)
    return eaten


def run(s, options, mapdb=None, walk_fn=walk, avoid=()):
    """Returns (reason, eaten)."""
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
    db = MapDB.load() if options["mode"] == "buy" else None
    avoid = avoided_rooms(db, load_settings().get("avoid_rooms")) if db else ()
    reason, eaten = run(s, options, mapdb=db, avoid=avoid)
    s.echo(f"heal: {reason} — {len(eaten)} herb(s) eaten")
