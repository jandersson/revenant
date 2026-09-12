"""Pay off your provincial debt, fetching the coins from the bank first:  ;debt

    ;debt              INFO: what you carry and what you owe, per currency (spends nothing)
    ;debt pay          walk to the bank for the shortfall, then to the debt office, PAY ALL, walk back
    ;debt pay stay     ... and stay at the debt office

Debt is what the province charges when you have no coins in hand: a
stat trainer's fee (;tdp, 2 Kronars per TDP), a fine, a fee. It is
paid in person at a debt collector's office with PAY ALL (or PAY
<amount>), or remotely through the urchin runners' BANK DEBT, a paid
service (Elanthipedia: Pay command, Withdraw command; the office
locations are the map's `debt` tag, the tellers its `bank` tag). The
script reads INFO for the debt and the coins carried, and when the
coins fall short walks to the nearest teller and WITHDRAWs the
difference one denomination at a time — a teller that knows no
account for you, or holds too little, stops it there with the answer
echoed; put coins in the character's hands (GIVE from another) and
run it again. Then it walks to the nearest debt office, PAYs, and
reads INFO again: the debt gone is the only success it reports. It
stops on death, and walks back to where it started unless told
`stay`. The nearest office is the map's word: a debt owed to Zoluren
is paid in Zoluren (Crossing, Leth Deriel); from another province the
PAY answer names the right towns and the script echoes it.
Stop with:  ;stop debt
"""

from client.game import probe
from client.game.mapdb import MapDB
from client.game.money import parse_wealth, phrase, split
from client.game.walker import locate, walk

COLLECT_SECONDS = 3  # a command's answer, opening window
TAIL_SECONDS = 1.5  # ... and the tail past its roundtime

# A teller's refusals — the account line captured 2026-09-11 ("you do not
# seem to have an account with us"); the rest are assumptions until
# captured. Success is not classified: INFO afterwards is the judge.
WITHDRAW_REFUSALS = (
    "do not seem to have an account",
    "not have enough",
    "don't have enough",
    "insufficient",
    "cannot",
    "can't",
)


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def echo_lines(s, text):
    for line in text.splitlines():
        if line.strip():
            s.echo(f"debt: {line.strip()}")


def wealth(s):
    """INFO's carried coin and debt, echoed per currency; the dict."""
    info = parse_wealth(ask(s, "info"))
    for currency in sorted(set(info["carried"]) | set(info["debt"])):
        carried = info["carried"].get(currency, 0)
        owed = info["debt"].get(currency, 0)
        s.echo(f"debt: {currency}: carrying {phrase(carried)}, owing {phrase(owed)}")
    if not info["debt"]:
        s.echo("debt: you owe nothing")
    return info


def owed_first(info):
    """(currency, copper owed, copper carried) for the first currency
    with a debt, or None."""
    for currency, copper in info["debt"].items():
        if copper > 0:
            return currency, copper, info["carried"].get(currency, 0)
    return None


def fetch(s, shortfall, currency, mapdb, walk_fn):
    """Walk to the nearest teller and WITHDRAW the shortfall, one
    denomination per command. False when a teller refused."""
    tellers = mapdb.rooms_tagged("bank")
    if not tellers:
        s.echo("debt: the map has no room tagged 'bank'")
        return False
    if not walk_fn(s, mapdb, set(tellers), describe="the bank teller"):
        s.echo("debt: could not reach a teller — stopping")
        return False
    s.echo(f"debt: withdrawing {phrase(shortfall, currency)}")
    for count, denomination in split(shortfall):
        answer = ask(s, f"withdraw {count} {denomination}")
        echo_lines(s, answer)
        if any(needle in answer.lower() for needle in WITHDRAW_REFUSALS):
            s.echo(
                "debt: the teller refused — put the coins in your hands "
                "(GIVE from another character) and run ;debt pay again"
            )
            return False
    return True


def run(s, words, mapdb=None, walk_fn=walk):
    if not words:
        wealth(s)
        return
    if words[0].lower() != "pay":
        s.echo("usage: ;debt  |  ;debt pay [stay]")
        return
    stay = len(words) > 1 and words[-1].lower() == "stay"
    if mapdb is None:
        s.echo("debt: paying needs the map — none loaded")
        return
    info = wealth(s)
    debt = owed_first(info)
    if debt is None:
        return
    currency, owed, carried = debt
    start = locate(mapdb, s.state)
    if carried < owed:
        if not fetch(s, owed - carried, currency, mapdb, walk_fn):
            return
        info = parse_wealth(ask(s, "info"))
        carried = info["carried"].get(currency, 0)
        if carried < owed:
            s.echo(
                f"debt: still short — carrying {phrase(carried, currency)} "
                f"against {phrase(owed, currency)} owed — stopping"
            )
            return
    offices = mapdb.rooms_tagged("debt")
    if not offices:
        s.echo("debt: the map has no room tagged 'debt'")
        return
    if not walk_fn(s, mapdb, set(offices), describe="the debt office"):
        s.echo("debt: could not reach a debt office — stopping")
        return
    if s.dead:
        s.echo("debt: you are dead — stopping")
        return
    echo_lines(s, ask(s, "pay all"))
    after = wealth(s)
    left = after["debt"].get(currency, 0)
    if left:
        s.echo(
            f"debt: still owing {phrase(left, currency)} — the PAY answer above says why"
        )
    else:
        s.echo(f"debt: paid {phrase(owed, currency)}")
    if not stay and start is not None and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("debt: could not walk back — you are at the debt office")


def main(s):
    words = list(s.args)
    if words and words[0].lower() == "pay":
        run(s, words, mapdb=MapDB.load())
    else:
        run(s, words)
