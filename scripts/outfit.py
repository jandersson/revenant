"""Buy a new character the essentials it lacks:  ;outfit

    ;outfit          INVENTORY's worn list read; each missing essential bought at its shop, worn, the profile set; then back where you started
    ;outfit check    list what is missing and where it is sold; buy nothing
    ;outfit stay     ... and stay at the last shop instead of walking back

The essentials are client/game/outfit.py's catalog; the first is a
worn skinning knife, so ;hunt skins with the hand the weapon leaves
free (a held knife fills it: "You must have one hand free to skin.").
After dr-scripts' new-character.lic, which buys a new character's
knife at the same shop. Each
missing one is an errand: walk to the shop's map room, count the purse
(WEALTH), and when it is short of the price in the shop's coin WITHDRAW
the difference at the nearest teller — the shop's own town, once
there — or, when the teller refuses, EXCHANGE the purse's other coins
at the nearest money-changer (client/game/bank.py, as ;bank does); then
BUY, WEAR ("You attach a small steel skinning knife with a
leather-wrapped hilt to your wrist."), and the profile's keys the
entry names are set (the knife clears `skin_knife`, so ;hunt stops
fetching a held one). A purchase the shop refuses, or a purse that
stays short, ends the run with the game's line. The knife is Tobb's
at Knife Clan, 500 Kronars (Elanthipedia: Tobb's Smithy, Skinning
knife; captured 2026-09-13), #341. Stops on death.
Stop with:  ;stop outfit.
"""

from client.game import bank
from client.game.act import ask, said
from client.game.mapdb import MapDB
from client.game.money import CURRENCIES, parse_wealth, phrase
from client.game.outfit import (
    ESSENTIALS,
    bought,
    missing,
    parse_args,
    put_on,
    worn_items,
)
from client.game.profile import load_profile, save_profile
from client.game.walker import locate, walk


def carried(s, currency):
    return parse_wealth(ask(s, "wealth"))["carried"].get(currency, 0)


def exchange_in(s, mapdb, walk_fn, currency):
    """Every other coin in the purse EXCHANGEd into `currency` at the
    nearest money-changer; False when there is none to exchange or no
    changer to reach."""
    purse = parse_wealth(ask(s, "wealth"))["carried"]
    others = [c for c in CURRENCIES if c != currency and purse.get(c, 0) > 0]
    if not others:
        return False
    changers = mapdb.rooms_tagged("exchange")
    if not changers or not walk_fn(
        s, mapdb, set(changers), describe="the money-changer"
    ):
        s.echo("outfit: could not reach a money-changer")
        return False
    for other in others:
        answer = ask(s, bank.exchange_command(other.lower(), currency.lower()))
        got = bank.handed(answer)
        s.echo(
            f"outfit: exchanged your {other} for {got}"
            if got
            else f"outfit: the money-changer answered {said(answer)!r}"
        )
    return True


def afford(s, mapdb, walk_fn, essential):
    """The price in the purse, in the shop's coin: the shortfall fetched
    from the nearest teller, else exchanged from the purse's other
    coins. True when the purse covers it after."""
    price, currency = essential["price"], essential["currency"]
    short = price - carried(s, currency)
    if short <= 0:
        return True
    s.echo(f"outfit: {phrase(short, currency)} short of the price")
    if bank.withdraw(
        s, mapdb, walk_fn, ask, "outfit", short, currency, retry="start ;outfit again"
    ):
        if carried(s, currency) >= price:
            return True
    if exchange_in(s, mapdb, walk_fn, currency) and carried(s, currency) >= price:
        return True
    s.echo(
        f"outfit: the purse still lacks {phrase(price, currency)} for the "
        f"{essential['name']} — bring the coin and start ;outfit again"
    )
    return False


def outfit_one(s, mapdb, walk_fn, essential):
    """One essential bought and worn; True when it went on."""
    shop = essential["shop"]
    if shop not in mapdb.rooms:
        s.echo(f"outfit: the map has no room {shop} for {essential['shop_name']}")
        return False
    if not walk_fn(s, mapdb, {shop}, describe=essential["shop_name"]):
        s.echo(f"outfit: could not reach {essential['shop_name']} — stopping")
        return False
    if not afford(s, mapdb, walk_fn, essential):
        return False
    if locate(mapdb, s.state) != shop and not walk_fn(
        s, mapdb, {shop}, describe=essential["shop_name"]
    ):
        s.echo(f"outfit: could not walk back to {essential['shop_name']} — stopping")
        return False
    answer = ask(s, essential["buy"])
    if not bought(answer):
        s.echo(f"outfit: {essential['buy']} answered {said(answer)!r} — stopping")
        return False
    answer = ask(s, essential["wear"])
    s.waitrt()
    if not put_on(answer):
        s.echo(
            f"outfit: bought the {essential['name']}, but {essential['wear']} "
            f"answered {said(answer)!r} — it is in hand"
        )
        return False
    s.echo(f"outfit: {said(answer)}")
    name = getattr(s.state, "name", None)
    if essential["profile"] and name:
        profile = load_profile(name)
        profile.update(essential["profile"])
        save_profile(name, profile)
        keys = ", ".join(
            f"{key}={value!r}" for key, value in essential["profile"].items()
        )
        s.echo(f"outfit: profile set — {keys}")
    return True


def run(s, words, mapdb, walk_fn=walk):
    options = parse_args(words)
    worn = worn_items(ask(s, "inventory"))
    todo = missing(worn, ESSENTIALS)
    if not todo:
        names = ", ".join(essential["name"] for essential in ESSENTIALS)
        s.echo(f"outfit: nothing missing — {names} already worn")
        return
    for essential in todo:
        s.echo(
            f"outfit: no {essential['name']} — {essential['shop_name']}, "
            f"{phrase(essential['price'], essential['currency'])}"
        )
    if options["check"]:
        return
    start = locate(mapdb, s.state)
    done = 0
    for essential in todo:
        if s.dead or not outfit_one(s, mapdb, walk_fn, essential):
            break
        done += 1
    s.echo(f"outfit: {done} of {len(todo)} bought and worn")
    if s.dead or not options["back"] or start is None:
        return
    if locate(mapdb, s.state) != start and not walk_fn(
        s, mapdb, {start}, describe="where you started"
    ):
        s.echo("outfit: could not walk back — you are where the errand ended")


def main(s):
    run(s, list(s.args or []), MapDB.load())
