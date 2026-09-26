"""Repair your gear at the nearest repair shop:  ;repair

    ;repair              appraise what you wear and hold, take every piece at or below the floor to the nearest shop, wait, wear it back
    ;repair check        appraise only: each piece's condition, nothing moves
    ;repair plate shield those pieces, whatever their condition (worn, held, or GOT from a container)
    ;repair floor=70     repair pieces whose condition tops out at or below 70 % (the profile's `repair_floor`, else 80)
    ;repair tools        ANALYZE the profile's `repair_tools` (mortar, pestle...) and take every one at or below the floor to Rangu
    ;repair tools pestle that tool, whatever its condition
    ;repair pickup       walk to the shop your tickets name and collect what is ready
    ;repair ... back     walk back to where you started when done
    ;repair return       (typed while it runs) hand in nothing more, collect the tickets already given, end

Weapons, shields and armor wear down in use, and a repair shop's NPC
mends any of them for coin (Elanthipedia: Repair; dr-scripts'
repair.lic is the same errand). Each piece is APPRAISEd QUICK (5 s of
roundtime) for its condition, the wiki's ten phrases from "in pristine
condition" to "battered and practically destroyed", each a band of
the item's health; a piece whose band tops out at or below the floor
is taken in — a worn one REMOVEd, a held one given from the hand. The
rest stay on. An answer without a condition (a pouch, a sack) is
skipped. The pieces are the profile's `repair_items` when set, else
what the hands hold and everything worn as the parser's last INV LIST
saw it (;sheet takes one at login).

The script walks to the nearest room the map tags `repair` whose
repairman it knows (client/game/repair.py's SHOPS, after dr-scripts'
base-town.yaml: Catrox in the Crossing, Randal at Wolf Clan, ...),
GIVEs the piece for the estimate — "That will cost 108 Kronars to
repair ... ready in 5 roisaen", in copper — and GIVEs it again at once
to pay: the offer lapses within twenty seconds. The ticket he hands
back is STOWed. A piece he calls unscratched goes back on. A price
the purse cannot cover puts the piece back; after the round the
shortfall is WITHDRAWn at the nearest teller (client/game/bank.py)
and those pieces go in on a second round. Then it waits the longest
estimate out at the shop — a roisaen is a minute — GETs each ticket,
GIVEs it back ("handed back some light full plate"), a "not done for
another N roisaen" waited out, and WEARs each worn piece back; a held
one stays in the hand. Captured 2026-09-24 at Catrox's Forge (#307).
Stops on death. `pickup` collects tickets from an earlier run: LOOK
AT MY TICKET names the shop, the script walks there and hands each in.

`tools` is the same errand for crafting tools, which no weapon or
armor shop takes: each is GOT and ANALYZEd — APPRAISE names no
condition for a tool, ANALYZE does, in the same phrases, 10 s of
roundtime — and STOWed back, and the worn ones go to the Crossing
Engineering Society's Repairman Rangu ("Only crafting tools are
repaired here"; Elanthipedia: Engineering Society (Crossing), Crafting
tools), who quotes and tickets the way Catrox does and hands each tool
back to be STOWed. A pestle "battered and practically destroyed" cost
20 Kronars and 10 roisaen there (2026-09-26); a new one is 125, and a
tool that far gone is past field repair with a wire brush and oil
(Blacksmithing techniques: Advanced Tool Repair).
Stop with:  ;stop repair, or ;repair return (keeps the tickets' pickup).
"""

from client.game import bank, probe
from client.game.loop import wants_stop
from client.game.mapdb import MapDB
from client.game.money import parse_wealth, phrase
from client.game.profile import load_profile
from client.game.repair import (
    DEFAULT_FLOOR,
    SHOPS,
    TOOL_SHOPS,
    candidates,
    classify_give,
    classify_pickup,
    condition,
    needs_repair,
    read_ticket,
    shop_room,
)
from client.game.walker import locate, walk

COLLECT_SECONDS = 3
TAIL_SECONDS = 1
ROISAEN_SECONDS = 60  # a roisaen is a real minute (client/game/eltime.py)
ALMOST_SECONDS = 30  # "just give me a few more moments here"
MAX_PICKUP_TRIES = 12  # per ticket: the fuse under the waits
MAX_TICKETS = 20

NOT_FOUND = ("what were you referring", "could not find", "don't have", "not wearing")


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def missing(answer):
    lowered = (answer or "").lower()
    return any(needle in lowered for needle in NOT_FOUND)


def hands(s):
    return [getattr(s.state, "right_hand", None), getattr(s.state, "left_hand", None)]


def parse_words(words):
    """(mode, items, floor, back) from the words typed after ;repair."""
    mode, items, floor, back = "repair", [], None, False
    for word in words:
        lowered = word.lower()
        if lowered in ("check", "pickup", "tools"):
            mode = lowered
        elif lowered == "back":
            back = True
        elif lowered.startswith("floor=") and lowered[6:].isdigit():
            floor = int(lowered[6:])
        else:
            items.append(lowered)
    return mode, items, floor, back


def appraise(s, pieces, floor, echo_all=True):
    """APPRAISE QUICK each (noun, place); the ones at or below the floor,
    as [(noun, place, reading)]. Every reading is echoed."""
    due = []
    for noun, place in pieces:
        if s.dead:
            return due
        answer = ask(s, f"appraise my {noun} quick")
        s.waitrt()
        if missing(answer):
            s.echo(f"repair: no {noun} on you — skipped")
            continue
        reading = condition(answer)
        if reading is None:
            continue
        verdict = needs_repair(reading, floor)
        if echo_all or verdict:
            mark = " — to repair" if verdict else ""
            s.echo(
                f"repair: {noun} is {reading[0]} ({reading[1]}-{reading[2]} %){mark}"
            )
        if verdict:
            due.append((noun, place, reading))
    return due


def analyze(s, tools, floor):
    """GET and ANALYZE each tool noun, STOW it back unless it was in a
    hand; the ones at or below the floor as [(noun, place, reading)],
    place "held" or "stowed". Every reading is echoed."""
    due = []
    held = {h.get("noun") for h in hands(s) if isinstance(h, dict)}
    for noun in tools:
        if s.dead:
            return due
        place = "held" if noun in held else "stowed"
        if place == "stowed":
            if not free_hand(s):
                return due
            answer = ask(s, f"get my {noun}")
            s.waitrt()
            if missing(answer):
                s.echo(f"repair: no {noun} on you — skipped")
                continue
        reading = condition(ask(s, f"analyze my {noun}"))
        s.waitrt()
        if place == "stowed":
            ask(s, f"stow my {noun}")
            s.waitrt()
        if reading is None:
            s.echo(f"repair: ANALYZE named no condition for the {noun} — skipped")
            continue
        verdict = needs_repair(reading, floor)
        mark = " — to repair" if verdict else ""
        s.echo(f"repair: {noun} is {reading[0]} ({reading[1]}-{reading[2]} %){mark}")
        if verdict:
            due.append((noun, place, reading))
    return due


def free_hand(s):
    """A hand empty for a REMOVE or a ticket: the left hand's item STOWed
    when both are full. False, said, when it would not go."""
    right, left = hands(s)
    if not right or not left:
        return True
    noun = left.get("noun") if isinstance(left, dict) else None
    answer = ask(s, f"stow my {noun}" if noun else "stow left")
    s.waitrt()
    if missing(answer) or "no room" in answer.lower() or "can't" in answer.lower():
        s.echo(f"repair: both hands full and the {noun} would not stow — stopping")
        return False
    s.echo(f"repair: stowed the {noun} to free a hand")
    return True


def take(s, noun, place):
    """The piece into a hand: a worn one REMOVEd, a held one already
    there, anything else GOT. False, said, when it did not come."""
    if place == "held" and any(
        isinstance(h, dict) and h.get("noun") == noun for h in hands(s)
    ):
        return True
    if not free_hand(s):
        return False
    if place != "stowed":
        answer = ask(s, f"remove my {noun}")
        s.waitrt()
        if not missing(answer):
            return True
    answer = ask(s, f"get my {noun}")
    s.waitrt()
    if missing(answer):
        s.echo(f"repair: could not take the {noun} off or out — skipped")
        return False
    return True


def put_back(s, noun, place):
    """The piece where it was: worn ones WORN back, a stowed tool
    STOWed, a held one left in the hand."""
    if place == "stowed":
        ask(s, f"stow my {noun}")
        s.waitrt()
    elif place == "worn":
        answer = ask(s, f"wear my {noun}")
        s.waitrt()
        if missing(answer) or "can't" in answer.lower():
            ask(s, f"stow my {noun}")
            s.waitrt()
            s.echo(f"repair: the {noun} would not go on — stowed")


def hand_in(s, name, due, purse):
    """GIVE each due piece to `name` twice — the estimate, then the
    payment; a first GIVE answered with a ticket paid an estimate still
    standing (Rangu, 2026-09-26: back from the teller within seconds)
    and counts as handed in. Returns (given, short, stopped): given [(noun, place,
    roisaen)], short [(noun, place, copper, currency)] the purse could
    not cover, stopped True once "return" was typed. `purse`
    ({currency: copper}) is spent down as tickets come back."""
    given, short = [], []
    for noun, place, _ in due:
        if s.dead or wants_stop(s):
            s.echo("repair: handing in nothing more")
            return given, short, True
        if not take(s, noun, place):
            continue
        answer = classify_give(ask(s, f"give my {noun} to {name}"))
        if answer["kind"] == "busy":
            s.sleep(5)
            answer = classify_give(ask(s, f"give my {noun} to {name}"))
        if answer["kind"] == "ticket":
            copper, currency = answer["copper"], answer["currency"]
            if purse is not None and copper and currency:
                purse[currency] = purse.get(currency, 0) - copper
            cost = phrase(copper, currency) if copper and currency else "the estimate"
            s.echo(
                f"repair: {noun} handed in for {cost}, "
                f"ready in {answer['roisaen']} roisaen"
            )
            ask(s, "stow my ticket")
            s.waitrt()
            given.append((noun, place, answer["roisaen"]))
            continue
        if answer["kind"] != "quote":
            reason = {
                "undamaged": "not a scratch on it",
                "refused": f"{name} will not repair it",
                "short": "not enough coin",
            }.get(answer["kind"], "no estimate")
            s.echo(f"repair: {noun}: {reason} — put back")
            put_back(s, noun, place)
            continue
        copper, currency = answer["copper"], answer["currency"]
        if purse is not None and purse.get(currency, 0) < copper:
            s.echo(
                f"repair: {noun} costs {phrase(copper, currency)}, you carry "
                f"{phrase(purse.get(currency, 0), currency)} — put back for now"
            )
            short.append((noun, place, copper, currency))
            put_back(s, noun, place)
            continue
        paid = classify_give(ask(s, f"give my {noun} to {name}"))
        if paid["kind"] != "ticket":
            s.echo(f"repair: {noun}: {name} did not take it — put back")
            put_back(s, noun, place)
            if paid["kind"] == "short":
                short.append((noun, place, copper, currency))
            continue
        if purse is not None:
            purse[currency] = purse.get(currency, 0) - copper
        roisaen = paid["roisaen"] or answer["roisaen"]
        s.echo(
            f"repair: {noun} handed in for {phrase(copper, currency)}, "
            f"ready in {roisaen} roisaen"
        )
        ask(s, "stow my ticket")
        s.waitrt()
        given.append((noun, place, roisaen))
    return given, short, False


def wait_out(s, seconds):
    """Sleep `seconds` in one-second slices; a typed return is noted
    (the tickets are collected anyway), death ends it: False."""
    left = seconds
    noted = False
    while left > 0:
        s.sleep(min(1, left))
        left -= 1
        if s.dead:
            return False
        if not noted and wants_stop(s):
            s.echo("repair: return noted — collecting the tickets first")
            noted = True
    return True


def collect(s, name, places):
    """Hand each of `name`'s tickets back until none is left, waiting out
    "not done for another N roisaen"; each piece back goes where
    `places` ({noun: place}) says, worn by default. The count."""
    returned = 0
    for _ in range(MAX_TICKETS):
        if s.dead:
            return returned
        if not free_hand(s):
            return returned
        if missing(ask(s, f"get my {name} ticket")):
            return returned
        s.waitrt()
        for _try in range(MAX_PICKUP_TRIES):
            answer = classify_pickup(ask(s, f"give my ticket to {name}"))
            if answer["kind"] == "returned":
                noun = answer["noun"]
                s.echo(f"repair: {answer['item']} back")
                put_back(s, noun, places.get(noun, "worn"))
                returned += 1
                break
            if answer["kind"] == "wait":
                seconds = answer["roisaen"] * ROISAEN_SECONDS or ALMOST_SECONDS
                s.echo(f"repair: not ready — waiting {seconds} s")
                if not wait_out(s, seconds):
                    return returned
                continue
            s.echo(f"repair: {name} did not take the ticket — kept, stopping")
            ask(s, "stow my ticket")
            return returned
        else:
            s.echo("repair: waited too long on a ticket — kept, stopping")
            ask(s, "stow my ticket")
            return returned
    return returned


def purse_of(s):
    """WEALTH's carried coin per currency, or None when unreadable."""
    carried = parse_wealth(ask(s, "wealth"))["carried"]
    return carried or None


def walk_to_shop(s, mapdb, walk_fn, rooms=None, shops=SHOPS):
    """Walk to the nearest known repair shop (`shops`: the gear shops by
    default, TOOL_SHOPS for tools); its repairman's name, or None, said.
    A gear shop must carry the map's `repair` tag; the tool shop has
    none."""
    tagged = set(mapdb.rooms_tagged("repair"))
    goals = {
        room
        for room in (rooms or shops)
        if room in mapdb.rooms and (room in TOOL_SHOPS or room in tagged)
    }
    if not goals:
        s.echo("repair: the map has no repair shop whose repairman is known")
        return None
    if not walk_fn(s, mapdb, goals, describe="the repair shop"):
        s.echo("repair: could not reach a repair shop — stopping")
        return None
    here = locate(mapdb, s.state)
    name = {**SHOPS, **TOOL_SHOPS}.get(here)
    if name is None:
        s.echo("repair: arrived, but not in a shop whose repairman is known")
    return name


def repair(s, mapdb, walk_fn, due, shops=SHOPS):
    """Hand every due piece in at the nearest shop, fetch coins for what
    the purse could not cover, wait and collect. The pieces back."""
    name = walk_to_shop(s, mapdb, walk_fn, shops=shops)
    if name is None:
        return 0
    shop = locate(mapdb, s.state)
    purse = purse_of(s)
    given, short, stopped = hand_in(s, name, due, purse)
    if short and not s.dead and not stopped:
        currency = short[0][3]
        need = sum(copper for *_, copper, cur in short if cur == currency)
        need -= (purse or {}).get(currency, 0)
        if need > 0 and bank.withdraw(
            s, mapdb, walk_fn, ask, "repair", need, currency, retry="run ;repair again"
        ):
            if walk_fn(s, mapdb, {shop}, describe=f"{name}'s shop"):
                more, _, _ = hand_in(
                    s, name, [(n, p, None) for n, p, *_ in short], purse_of(s)
                )
                given += more
    if not given:
        s.echo("repair: nothing handed in")
        return 0
    longest = max(roisaen or 0 for *_, roisaen in given)
    if longest:
        s.echo(f"repair: waiting {longest} roisaen for {name}")
        if not wait_out(s, longest * ROISAEN_SECONDS):
            return 0
    return collect(s, name, {noun: place for noun, place, _ in given})


def pickup(s, mapdb, walk_fn):
    """Collect tickets from an earlier run: the ticket names the shop."""
    if not free_hand(s):
        return 0
    if missing(ask(s, "get my ticket")):
        s.echo("repair: no repair ticket on you")
        return 0
    ticket = read_ticket(ask(s, "look at my ticket"))
    ask(s, "stow my ticket")
    if ticket is None:
        s.echo("repair: that ticket names no shop — stopping")
        return 0
    room = shop_room(ticket["shop"])
    if room is None:
        s.echo(f"repair: {ticket['shop']}'s shop is not one the map knows — stopping")
        return 0
    name = walk_to_shop(s, mapdb, walk_fn, rooms={room})
    if name is None:
        return 0
    return collect(s, name, {})


def run(s, words, mapdb=None, walk_fn=walk, profile=None):
    mode, items, floor, back = parse_words(words)
    profile = profile if profile is not None else load_profile(s.state.name)
    if floor is None:
        floor = int(profile.get("repair_floor") or DEFAULT_FLOOR)
    if mode == "pickup":
        if mapdb is None:
            s.echo("repair: pickup needs the map — none loaded")
            return
        start = locate(mapdb, s.state)
        count = pickup(s, mapdb, walk_fn)
        s.echo(f"repair: {count} piece{'s' if count != 1 else ''} collected")
        walk_home(s, mapdb, walk_fn, start, back)
        return
    if mode == "tools":
        tools = items or profile.get("repair_tools") or []
        if not tools:
            s.echo(
                "repair: no tools named — ;repair tools pestle mortar, or the "
                "profile's repair_tools"
            )
            return
        tools = [str(tool).strip().lower() for tool in tools]
        due = analyze(s, tools, 100 if items else floor)
        if not due:
            s.echo(f"repair: no tool at or below {floor} % — all good")
            return
        if mapdb is None:
            s.echo("repair: walking to a shop needs the map — none loaded")
            return
        start = locate(mapdb, s.state)
        count = repair(s, mapdb, walk_fn, due, shops=TOOL_SHOPS)
        s.echo(f"repair: {count} of {len(due)} repaired")
        walk_home(s, mapdb, walk_fn, start, back)
        return
    listed = items or profile.get("repair_items") or []
    pieces = candidates(getattr(s.state, "possessions", None) or [], hands(s), listed)
    if not pieces:
        s.echo("repair: nothing to look at — ;sheet inv lists what you wear")
        return
    # Named pieces go in whatever their condition: the floor is 100.
    due = appraise(s, pieces, 100 if items else floor)
    if mode == "check":
        s.echo(f"repair: {len(due)} to repair at a floor of {floor} %")
        return
    if not due:
        s.echo(f"repair: nothing at or below {floor} % — all good")
        return
    if mapdb is None:
        s.echo("repair: walking to a shop needs the map — none loaded")
        return
    start = locate(mapdb, s.state)
    count = repair(s, mapdb, walk_fn, due)
    s.echo(f"repair: {count} of {len(due)} repaired")
    walk_home(s, mapdb, walk_fn, start, back)


def walk_home(s, mapdb, walk_fn, start, back):
    if back and start is not None and not s.dead and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("repair: could not walk back — you are at the shop")


def main(s):
    words = list(s.args)
    mode = parse_words(words)[0]
    run(s, words, mapdb=None if mode == "check" else MapDB.load())
