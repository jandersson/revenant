"""Train Alchemy by crushing remedies in the mortar, and fill the society's work orders:  ;remedies

    ;remedies                 the head salve — dried nemoih in the mortar, CRUSHed until Alchemy mind-locks
    ;remedies chest           another chapter-3 salve (neck, abdominal, chest, head, back, eye); its dried herb must be on you
    ;remedies count=2         finish that many remedies, then end
    ;remedies until=30        stop at that mindstate instead of 34
    ;remedies once            exit at mind-lock instead of holding for the drain
    ;remedies work            easy work orders, one after another: ask the master (or resume the logbook's), craft each
                              stack, bundle it, hand the logbook in — the herbs, water and coal bought as they run out
    ;remedies work count=3    that many orders, then end; `challenging` or `hard` for the harder tiers
    ;remedies work once       end at mind-lock instead of working on for the pay
    ;remedies ledger          the orders on record: pay, materials, profit, the last few
    ;remedies return          (typed while it runs) finish the crush in hand and end — under `work`, finish the
                              order in hand (every stack and the hand-in) and end; ;stop remedies is the abrupt end

Alchemy trains by making remedies: every CRUSH of one in progress
teaches (Alchemy 0/34 to rank 7 in an evening of three, captured
2026-09-22 at the Crossing Alchemy Society; client/game/remedies.py
holds every wording), and crushing a raw flower teaches nothing — the
2014 shortcut in Pfanston's Guide to Remedies is gone. A remedy is its
book page's recipe, not the wiki's: the page STUDied right before the
first crush (the readiness is spent by the next attempt, a failed one
included, so a "cannot figure out how to do that" means the page is
studied again), the controlling herb's 25-piece dried stack in the
mortar (one stack is one 5-use remedy, the order's unit), then CRUSH
after CRUSH with what the game asks for put in as it asks: a splash of
water, one piece of the page's second herb (blister cream wants
nemoih beside its red flowers), the catalyst last — a tiny coal nugget
from the Crossing Forging Society's Supplies (31 Kronars, the
profile's `catalyst` noun), one use each. "Applying the final touches,
you complete working on some blister cream." ends it and the remedy is
stowed, or bundled with the logbook under `work`.

`work` is the society's orders (Elanthipedia: Work orders), run as a
living: the logbook in hand and READ first — an order it still tracks
is resumed, a complete one handed in, an expired one (past its due
time: "This logbook is tracking a work order that has expired.")
UNTIEd and its stacks stowed before a new one is asked, 2026-09-26 —
else ASK <master> FOR EASY
REMEDIES WORK where the master stands (Lanshado in the Crossing
society's Tool Shop, map 8860 — the profile's `crafting_master` and
`crafting_hall`; he wanders the building — "Lanshado steadies himself
and shuffles away", "softly shuffles into the area" — so a hall
without him is followed by the building's other rooms, two laps,
until a listing names him, 2026-09-23), the order read back ("an order for some blister
cream. I need 2 stacks (5 uses each) finely-crafted ... due in 65
roisaen"); an order the book has no page for, or whose herb the
Supplies does not sell (hulnik, sufil), is asked again, up to three
times — a new order replaces the old without penalty. Each stack is
crafted, BUNDLE <remedy> WITH MY LOGBOOK, and GIVE MY LOGBOOK TO
<master> for the pay ("are given 1146 Kronars in return" for two
stacks of blister cream at rank 6, 748 Kronars of herbs and coal
in), then the next order, until `return` or `count` orders. The
order's quality is enforced: a remedy the master's notes call too
poor ("The work order requires items of a higher quality, so you
decide against bundling that." — one of five at rank 10) is disposed
of — DROPped through client/game/discard.py, so settings.json's
`droppable` must name the remedy noun (cream, salve, ointment), else
it is stowed — and another stack is crafted for the order; three
such in one order end it, the order waiting in the logbook. What runs
out is bought on the spot — the tools stowed, the coins fetched from
the bank's teller when the purse is short, the society's Supplies
(map 8862; the controlling herb a stack per remedy still owed, the
second herb one stack, water ten splashes) or the Forging Society's
Supplies (8775, a coal nugget per remedy) walked to, ORDER # twice
per item (the quote checked against the noun before the buy), each
STOWed — and the walk back resumes the remedy left in the mortar. A
remedy another run left unfinished in the mortar ("You realize the
red flowers is not required to continue crafting the nemoih salve, so
you stop.", 2026-09-23: a run that ended on a missing catalyst) is
finished first, taken out and stowed, then the order's own — every
craft begins with LOOK IN MY MORTAR (no roundtime), so a leftover is
found before the STUDY and before a restock's resume, whichever run
left it; a CRUSH refused twice running ("Crush what?") ends the run
rather than spinning. At
mind-lock the orders go on for the pay (`once` ends there); the
tally at the end is what was earned against what was spent. Every
order handed in is a row in history.db's `work_orders` table
(client/game/workorders.py: the pay, the materials at catalog prices,
the coin spent while it was open, the crushes and the roundtime they
cost — seconds a crush is what better tools lower — the minutes end
to end, the rank before and after; the order in progress lives in
`~/.revenant/workorders/<name>.json` from the master's word to the
pay, so a run that ends mid-order and the run that resumes it add up
to one row, #288), and `;remedies ledger` prints the totals, the profit an
order of each item brings, and the last few. GIVE is the script's
own: the session refuses it from outside (#161).

The mortar and the pestle fill both hands: the weapon is SHEATHEd
first, the pestle is stowed for every fetch and taken back for the
crush, the mortar before the logbook comes out. Nothing is ever
dropped. It stops at mind-lock (holding until the drain, `once`
exits), on `return`, on death or hostiles (the shared escape), when
the herb, the water, the catalyst or the book is not on you, and when
a CRUSH answers nothing the table knows three times. ;train runs it as
a task (skills: ["Alchemy"], return_word "return"; `"args": ["work"]`
for the orders, with `return_grace` long enough for the order in hand
— an easy order of four stacks runs half an hour — and `minutes` to
match, since the return word finishes the order before it ends).
Stop with:  ;stop remedies, or ;remedies return.
"""

import logging
import time

from client.game import discard, flight, probe
from client.game.loop import danger, ensure_mindstate, mindstate, pause, wants_stop
from client.game.probe import classify
from client.game.money import parse_wealth, phrase
from client.game.seek import present
from client.game.remedies import (
    MASTER_UNTIE,
    BOUGHT,
    BUNDLED,
    building_rooms,
    CATALOG,
    CRUSH_OUTCOMES,
    MORTAR_BUSY,
    NO_MASTER,
    ORDER_TRIES,
    POURED,
    remedy_in_mortar,
    unfinished_in_mortar,
    REJECTED,
    REJECTIONS,
    STUDIED,
    TOO_HARD,
    crush_command,
    is_noise,
    logbook_item,
    parse_args,
    parse_logbook,
    parse_order,
    payment,
    quote,
    recipe,
    roundtime_of,
    sellable,
    shortage,
)
from client.game.workorders import (
    clear_open,
    ledger_lines,
    load_open,
    material_cost,
    open_ledger,
    record,
    rows,
    save_open,
)

SKILL = "Alchemy"
RESUME_BELOW = 28
LOCK_POLL = 30
COLLECT_SECONDS = 3
TAIL_SECONDS = 1.5
MAX_CRUSHES = 400  # the fuse under the loop
MISSES = 3  # unrecognized CRUSH answers before the run ends
REFUSALS = 2  # "Crush what?" answers in a row before the run ends
STUDIES = 2  # STUDYs per remedy before the recipe is called wrong
DEFAULT_MASTER = "lanshado"
DEFAULT_HALL = "8860"  # the Crossing Alchemy Society's Tool Shop
MASTER_LAPS = 2  # laps of the building's rooms looking for the master


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS).lower()


def profile_of(s):
    name = getattr(s.state, "name", None)
    if not name:
        return {}
    from client.game.profile import load_profile

    return load_profile(name)


def hand_nouns(s):
    nouns = []
    for side in ("left", "right"):
        held = getattr(s.state, f"{side}_hand", None)
        if isinstance(held, dict) and held.get("noun"):
            nouns.append(held["noun"].lower())
    return nouns


def clear_hands(s, profile):
    """The weapon SHEATHEd into its container, anything else STOWed:
    the mortar and the pestle want both hands. Never DROP."""
    weapon = (profile.get("weapon") or "").lower()
    container = profile.get("weapon_container") or ""
    for noun in hand_nouns(s):
        if noun == weapon and container:
            ask(s, f"sheathe my {noun} in my {container}")
        else:
            ask(s, f"stow my {noun}")


def missing(answer):
    return "referring" in answer or "could not find" in answer


def study(s, chapter, page, what):
    """The page STUDied: the book out (a hand freed of the pestle if
    need be), turned to the chapter and page, studied, stowed. False
    when the book is not on you or the game did not say it is ready."""
    # The mortar and pestle fill both hands ("You need a free hand to
    # pick that up.", 2026-09-22): the pestle down for the book, up after.
    ask(s, "stow my pestle")
    answer = ask(s, "get my book")
    if missing(answer):
        s.echo("remedies: no remedies book on you — stopping")
        ask(s, "get my pestle")
        return False
    ask(s, f"turn my book to chapter {chapter}")
    ask(s, f"turn my book to page {page}")
    answer = ask(s, "study my book")
    s.waitrt()
    ask(s, "stow my book")
    ask(s, "get my pestle")
    if any(word in answer for word in TOO_HARD):
        s.echo(
            f"remedies: {what} is beyond the ranks — mishaps ahead, the crushes still teach"
        )
    if not any(word in answer for word in STUDIED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: STUDY answered {first!r} — stopping")
        return False
    return True


def fetch_into_mortar(s, noun, what):
    """The pestle down, `noun` GOT and PUT (water POURed) in the mortar,
    what stays in hand stowed, the pestle back up. False when the game
    finds no such thing on you."""
    ask(s, "stow my pestle")
    answer = ask(s, f"get my {noun}")
    if missing(answer):
        s.echo(f"remedies: no {noun} on you — the {what} is missing")
        ask(s, "get my pestle")
        return False
    verb = "pour" if what == "water" else "put"
    answer = ask(s, f"{verb} my {noun} in my mortar")
    if any(word in answer for word in MORTAR_BUSY):
        # Another remedy is in progress in the mortar (2026-09-23): the
        # herb stays in hand for the caller, the pestle comes back up.
        held = remedy_in_mortar(answer)
        name = held[0] if held else "remedy"
        s.echo(f"remedies: the mortar already holds an unfinished {name}")
        ask(s, f"stow my {noun}")
        ask(s, "get my pestle")
        return f"busy:{name}"
    if what == "water" and not any(word in answer for word in POURED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: the pour answered {first!r}")
    if what != "herb":
        ask(s, f"stow my {noun}")  # the flask, the second herb's stack, a nugget
    ask(s, "get my pestle")
    return True


def hold_at_lock(s, until):
    s.echo(f"remedies: {SKILL} mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        value = mindstate(s, SKILL)
        if value is not None and value <= floor:
            s.echo(f"remedies: drained to {value}/34 — crushing again")
            return True


def craft(s, spec, what, catalyst, options, tally, started=False):
    """One remedy from `spec` (chapter, page, herb, extra, noun): the
    page studied, the herb in, CRUSH until finished with the water, the
    second herb and the catalyst put in as asked. The finished remedy
    is left in the mortar. Returns None when done, else why it could
    not be: "stopped", "locked", the missing thing, "beyond".

    `started` resumes the unfinished remedy already in the mortar (a
    restock walked away from it): the page studied again, no herb put
    in, the crushes go on. `tally` counts crushes and unrecognized
    answers across the run; the mortar and pestle are in hand on
    entry and on exit."""
    chapter, page, herb, extra, noun = spec
    # What the mortar holds decides where this craft starts (no
    # roundtime): another remedy in progress is finished first (a run
    # that ran out of nuggets left a nemoih salve, and a restock's
    # resume crushed "my cream" over it, 2026-09-23); this one in
    # progress resumes; an empty mortar starts from the herb. Before
    # the STUDY, whose readiness the other remedy's crush would spend.
    held = mortar_holds(s)
    if held is not None and held[1] != spec:
        why = finish_in_mortar(s, held[0], catalyst, options, tally)
        if why is not None:
            return why
        started = False
    elif held is not None:
        started = True  # this recipe, in progress: resumed
    if not study(s, chapter, page, what):
        return "book"
    misses = 0
    studies = 1
    refused = 0
    if not started:
        fetched = fetch_into_mortar(s, herb, "herb")
        if isinstance(fetched, str):
            # The mortar holds another remedy in progress (2026-09-23):
            # finished first, taken out and stowed, then this one.
            why = finish_in_mortar(
                s, fetched.split(":", 1)[1], catalyst, options, tally
            )
            if why is not None:
                return why
            fetched = fetch_into_mortar(s, herb, "herb")
            if isinstance(fetched, str):
                s.echo("remedies: the mortar is still busy — stopping")
                return "mortar"
        if not fetched:
            return f"dried {herb}"
    for _ in range(MAX_CRUSHES):
        if why := danger(s):
            return why
        if wants_stop(s):
            if not options["work"]:
                return "stopped"
            # An order is finished, never left half-done in the logbook
            # for a typed return — ;train's return word at the target or
            # the time budget (the operator, 2026-09-23). ;stop is abrupt.
            if not tally.get("ending"):
                tally["ending"] = True
                s.echo("remedies: return — finishing the order in hand first")
        value = mindstate(s, SKILL)
        if value is not None and value >= options["until"]:
            if options["once"]:
                return "locked"
            if options["work"]:
                # An order pays whatever the mindstate: the crushes go
                # on, said once, and the lock drains on its own.
                if not tally.get("locked"):
                    tally["locked"] = True
                    s.echo(
                        f"remedies: {SKILL} mind-locked ({value}/34) — the order goes on for the pay"
                    )
            elif not hold_at_lock(s, options["until"]):
                return "stopped"
        answer = ask(s, crush_command(herb, started, noun))
        s.waitrt()
        tally["crushes"] += 1
        tally["crush_seconds"] = tally.get("crush_seconds", 0) + roundtime_of(answer)
        outcome = classify(answer, CRUSH_OUTCOMES)
        if outcome == "crushed":
            started = True
            misses = 0
            refused = 0
        elif outcome == "need water":
            started = True
            if not fetch_into_mortar(s, "water", "water"):
                return "water"
        elif outcome == "need herb":
            started = True
            if not extra:
                s.echo("remedies: the game wants a second herb the page did not list")
                return "second herb"
            if not fetch_into_mortar(s, extra, "second herb"):
                return f"dried {extra}"
        elif outcome == "need catalyst":
            started = True
            if not catalyst:
                s.echo(
                    "remedies: the remedy wants a catalyst and the profile names none "
                    "— it stays unfinished in the mortar for the next run"
                )
                return "catalyst"
            if not fetch_into_mortar(s, catalyst, "catalyst"):
                return catalyst
        elif outcome in ("finished", "done already"):
            return None
        elif outcome == "no instructions":
            # The readiness was spent (a failed attempt spends it): the
            # page again, once; twice means the recipe is not this one.
            if studies >= STUDIES:
                s.echo(
                    f"remedies: the game refuses {what} after {studies} studies — wrong page or herb"
                )
                return "beyond"
            studies += 1
            if not study(s, chapter, page, what):
                return "book"
        elif outcome == "free hand":
            ask(s, "stow my pestle")
            ask(s, "get my pestle")
        elif outcome == "missing" and not started:
            # "Crush what?" with nothing in the mortar: the herb fetched
            # again, but not for ever — the first evening's spin was
            # four commands a second on a busy mortar (2026-09-23).
            refused += 1
            if refused >= REFUSALS:
                s.echo(
                    "remedies: CRUSH refused again and again — the mortar or the "
                    "hands are not as expected, stopping"
                )
                return "mortar"
            fetched = fetch_into_mortar(s, herb, "herb")
            if isinstance(fetched, str):
                return "mortar"
            if not fetched:
                return f"dried {herb}"
        elif outcome is None and is_noise(answer):
            tally["noise"] = tally.get("noise", 0) + 1  # a bystander's line
        else:
            misses += 1
            tally["unrecognized"] += 1
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: unrecognized CRUSH answer {first!r} — please report it")
            if misses >= MISSES:
                return "unrecognized"
    return "fuse"


def mortar_holds(s):
    """LOOK IN MY MORTAR (no roundtime): the remedy in progress there as
    (name, recipe), or None for an empty mortar or a remedy the book
    has no page for — said, once, so it can be looked at by hand."""
    answer = ask(s, "look in my mortar")
    held = unfinished_in_mortar(answer)
    if held is None and "unfinished" in answer:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(
            f"remedies: the mortar holds something the book has no page for: {first!r}"
        )
    return held


def finish_in_mortar(s, name, catalyst, options, tally):
    """The remedy another run left unfinished in the mortar, finished
    and stowed so the mortar is free (2026-09-23: a run that ended on
    a missing catalyst left a nemoih salve, and the next order's
    flowers were refused). None when the mortar is free again, else
    why not — the caller's restock buys what it ran out of and comes
    back to it."""
    spec = recipe(name)
    if spec is None:
        s.echo(
            f"remedies: the mortar holds an unfinished {name} the book has no page for"
        )
        return "mortar"
    s.echo(f"remedies: the mortar holds an unfinished {name} — finishing it first")
    why = craft(s, spec, f"the {name}", catalyst, options, tally, started=True)
    if why is not None:
        return why
    take_out(s, spec[4])
    ask(s, f"stow my {spec[4]}")
    if not tools_in_hand(s):
        return "mortar"
    s.echo(f"remedies: the {name} is done and stowed — the mortar is free")
    return None


def take_out(s, noun):
    """The finished remedy out of the mortar into a hand: the pestle
    stowed first, then the mortar (a free hand for whatever is next)."""
    ask(s, "stow my pestle")
    ask(s, f"get my {noun} from my mortar")
    ask(s, "stow my mortar")


def tools_in_hand(s):
    for tool in ("mortar", "pestle"):
        if missing(ask(s, f"get my {tool}")):
            s.echo(f"remedies: no {tool} on you — stopping")
            return False
    return True


def train(s, options, profile):
    """The training loop: the chapter-3 salve crushed until the lock."""
    salve = options["salve"]
    spec = recipe(f"{salve} salve")
    catalyst = str(profile.get("catalyst") or "").strip()
    if not tools_in_hand(s):
        return
    s.echo(
        f"remedies: {salve} salve from dried {spec[2]} — {SKILL} {mindstate(s, SKILL)}/34"
    )
    tally = {"crushes": 0, "unrecognized": 0}
    salves = 0
    while True:
        why = craft(s, spec, f"the {salve} salve", catalyst, options, tally)
        if why is None:
            salves += 1
            s.echo(f"remedies: {salve} salve finished ({salves})")
            take_out(s, spec[4])
            ask(s, f"stow my {spec[4]}")
            if options["count"] and salves >= options["count"]:
                why = f"{salves} salve(s) made"
                break
            if not tools_in_hand(s):
                return
            continue
        break
    s.echo(f"remedies: {why} — {salves} salve(s), {SKILL} {mindstate(s, SKILL)}/34")
    ask(s, "stow my pestle")
    ask(s, "stow my mortar")


def to_master(s, profile):
    """Walk to the crafting hall (the profile's `crafting_hall`, a ;go2
    target; the Crossing society's Tool Shop by default)."""
    from client.game.mapdb import MapDB
    from client.game.walker import locate, walk

    mapdb = MapDB.load()
    target = str(profile.get("crafting_hall") or DEFAULT_HALL)
    goals = mapdb.resolve(target)
    if not goals:
        s.echo(f"remedies: nothing in the map matches crafting_hall {target!r}")
        return False
    if locate(mapdb, s.state) in goals:
        return True
    return walk(s, mapdb, set(goals), describe="the crafting hall")


def master_here(s, master):
    """True when the room's listing or its players name the master."""
    return (
        present(
            master,
            getattr(s.state, "room_objs", "") or "",
            getattr(s.state, "room_players", None) or (),
        )
        is not None
    )


def find_master(s, profile, master, mapdb=None, here=None):
    """The master where he stands: the crafting hall first, then the
    building's other rooms, MASTER_LAPS laps, until a listing names
    him. Lanshado wanders the society ("steadies himself and shuffles
    away", "softly shuffles into the area", captured 2026-09-22; the
    operator, 2026-09-23: "he's in the society building somewhere, the
    script just needs to look for him"). False when the hall is out of
    reach, the map shows no building, or he is nowhere in it. A room
    that already lists him is the answer, no walk (the hand-in used to
    walk back to the hall from the room he was found in, 12:10 on
    2026-09-23)."""
    if master_here(s, master):
        return True
    if not to_master(s, profile):
        return False
    if master_here(s, master):
        return True
    if mapdb is None:
        from client.game.mapdb import MapDB
        from client.game.walker import locate

        mapdb = MapDB.load()
        here = locate(mapdb, s.state)
    # The building is the hall's, whether or not the walker can name
    # the room we stand in.
    hall = mapdb.resolve(str(profile.get("crafting_hall") or DEFAULT_HALL))
    anchor = sorted(hall)[0] if hall else here
    rooms = [room for room in building_rooms(mapdb.rooms, anchor) if room != str(here)]
    if not rooms:
        s.echo(
            f"remedies: {master} is not here, and the map shows no other room of the building"
        )
        return False
    s.echo(
        f"remedies: {master} is not here — looking through the building's "
        f"{len(rooms)} other room(s)"
    )
    for _lap in range(MASTER_LAPS):
        for room in rooms:
            if wants_stop(s) or danger(s):
                return False
            if not walk_to(s, room, f"the building's room {room}"):
                continue
            s.sleep(1)  # the listing lands a beat after the arrival
            if master_here(s, master):
                s.echo(f"remedies: found {master} in room {room}")
                return True
    s.echo(f"remedies: {master} is nowhere in the building after {MASTER_LAPS} lap(s)")
    return False


UNTIE_TRIES = 10  # stacks untied from an expired order's logbook at most
UNTIED_NONE = ("nothing", "what were you referring", "isn't anything", "not bundled")


def untie_expired(s):
    """An order past its due time: UNTIE MY LOGBOOK until nothing more is
    tied to it, each piece that comes off STOWed — a stack of the same
    remedy fills a later order — and the saved order cleared, so the
    master will give another (2026-09-26: a blister cream order from the
    night before stopped every ;remedies work after it). UNTIE's
    answers are uncaptured: the first is echoed for the fixtures."""
    s.echo("remedies: the logbook's order expired — untying it for a new one")
    for attempt in range(UNTIE_TRIES):
        answer = ask(s, "untie my logbook")
        lowered = answer.lower()
        if attempt == 0:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: UNTIE answered {first!r} — please report it")
        if any(word in lowered for word in UNTIED_NONE) or not lowered.strip():
            break
        for side in ("right_hand", "left_hand"):
            held = getattr(s.state, side, None)
            noun = held.get("noun") if isinstance(held, dict) else None
            if noun and noun != "logbook":
                ask(s, f"stow my {noun}")
    name = getattr(s.state, "name", None) or ""
    if name:
        clear_open(name)


def order(s, master, level, seek=None):
    """The logbook in hand and read — an order it still tracks is
    resumed, a complete one goes straight to the master — else the
    order asked and read back; the parsed order or None (said). `seek`
    finds the master again when the ask says he is gone."""
    if missing(ask(s, "get my logbook")):
        s.echo("remedies: no work order logbook on you — stopping")
        return None
    text = ask(s, "read my logbook")
    state, remaining, due = parse_logbook(text)
    if state == "expired":
        untie_expired(s)
    if state == "done":
        ask(s, "stow my logbook")
        s.echo("remedies: the logbook holds a complete order — handing it in")
        return {"item": "", "count": 0, "quality": "", "due": due}
    if state == "open" and logbook_item(text):
        ask(s, "stow my logbook")
        s.echo(
            f"remedies: resuming the logbook's order — {remaining} more "
            f"{logbook_item(text)}, {due} roisaen"
        )
        return {
            "item": logbook_item(text),
            "count": remaining,
            "quality": "",
            "due": due,
            "resumed": True,
        }
    answer = ask(s, f"ask {master} for {level} remedies work")
    if any(word in answer for word in NO_MASTER) and seek is not None and seek():
        answer = ask(s, f"ask {master} for {level} remedies work")
    if any(word in answer.lower() for word in MASTER_UNTIE):
        untie_expired(s)
        answer = ask(s, f"ask {master} for {level} remedies work")
    if any(word in answer for word in NO_MASTER):
        s.echo(f"remedies: {master} is not here — stopping")
        ask(s, "stow my logbook")
        return None
    parsed = parse_order(answer)
    if parsed is None:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: the master answered {first!r} — no order read, stopping")
        ask(s, "stow my logbook")
        return None
    ask(s, "stow my logbook")
    s.echo(
        f"remedies: order — {parsed['count']} stack(s) of {parsed['item']}, "
        f"{parsed['quality']}, due in {parsed['due']} roisaen"
    )
    return parsed


def bundle(s, noun, expected):
    """The remedy in one hand, the logbook in the other, BUNDLEd; the
    logbook's count read back. ("bundled" | "rejected" | "unknown",
    remaining, roisaen): rejected is the order's quality unmet — the
    remedy disposed of through discard.drop (stowed when the list
    refuses it), the order still owed its stack;
    unknown is an answer the table lacks whose logbook count did not
    move from `expected`, the remedy stowed likewise."""
    ask(s, "get my logbook")
    answer = ask(s, f"bundle my {noun} with my logbook")
    outcome = "bundled"
    if any(word in answer for word in REJECTED):
        outcome = "rejected"
    elif not any(word in answer for word in BUNDLED):
        outcome = "unknown"
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: BUNDLE answered {first!r} — please report it")
    state, remaining, due = parse_logbook(ask(s, "read my logbook"))
    ask(s, "stow my logbook")
    if state == "done":
        remaining = 0
    if outcome == "unknown" and remaining < expected:
        outcome = "bundled"  # the count moved: the wording was new, the bundle real
    if outcome == "rejected":
        # Disposed of, not kept (the operator, 2026-09-22): through
        # discard.py — the room's bucket when it has one, else DROP,
        # settings.json's `droppable` naming the remedy noun — and
        # stowed when the list refuses it.
        if discard.drop(s, noun, ask) is None:
            ask(s, f"stow my {noun}")
    elif outcome != "bundled":
        ask(s, f"stow my {noun}")
    return outcome, remaining, due


def walk_to(s, target, describe):
    """Walk to a map id or tag; True when there (or already there)."""
    from client.game.mapdb import MapDB
    from client.game.walker import locate, walk

    mapdb = MapDB.load()
    goals = mapdb.resolve(str(target))
    if not goals:
        s.echo(f"remedies: nothing in the map matches {target!r}")
        return False
    if locate(mapdb, s.state) in goals:
        return True
    return walk(s, mapdb, set(goals), describe=describe)


def carried(s):
    """INFO's carried Kronars in copper (the answer read as the game
    cases it: parse_wealth wants "Wealth:" and "Kronars")."""
    answer = probe.ask(s, "info", COLLECT_SECONDS, TAIL_SECONDS)
    return parse_wealth(answer)["carried"].get("Kronars", 0)


def withdraw_coins(s, copper):
    """The shortfall from the nearest teller (client/game/bank.py's
    WITHDRAW, as ;debt and ;tdp take theirs); False when refused."""
    from client.game.bank import withdraw
    from client.game.mapdb import MapDB
    from client.game.walker import walk

    return withdraw(s, MapDB.load(), walk, ask, "remedies", copper, "Kronars")


def buy(s, noun, count, shop, catalog, tally):
    """`count` of `noun` ORDERed at `shop` — the coins fetched from the
    bank first when the purse is short — each quote checked against
    the noun before the second ORDER buys it, each purchase STOWed.
    False, said, when the quote names something else, the shop keeps
    the item, or the walk fails."""
    number, price = catalog[noun]
    need = price * count
    purse = carried(s)
    if purse < need and not withdraw_coins(s, need - purse):
        return False
    if not walk_to(s, shop, "the Supplies"):
        s.echo("remedies: could not reach the Supplies — stopping")
        return False
    for _ in range(count):
        answer = ask(s, f"order {number}")
        quoted = quote(answer)
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        if quoted is None or noun not in quoted[0]:
            s.echo(
                f"remedies: ORDER {number} answered {first!r}, not {noun} — stopping"
            )
            return False
        answer = ask(s, f"order {number}")
        if not any(word in answer for word in BOUGHT):
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: the purchase of {noun} answered {first!r} — stopping")
            return False
        tally["spent"] += quoted[1]
        ask(s, f"stow my {noun}")
    s.echo(f"remedies: bought {count} x {noun} for {phrase(need, 'Kronars')}")
    return True


def restock(s, spec, catalyst, why, remaining, tally):
    """What the craft ran out of, bought for the stacks still to make;
    None when `why` is no shortage, else whether it was bought."""
    short = shortage(why, spec, catalyst)
    if short is None:
        return None
    noun, per_stack, shop, catalog = short
    count = max(1, per_stack * remaining)
    if catalyst and noun == catalyst:
        count += 1  # a spare nugget: a rejected stack cost a 44-room walk (#288)
    return buy(s, noun, count, shop, catalog, tally)


def next_order(s, master, options, seek=None):
    """An order the book has a page for and the shop the herbs of —
    the master asked again, up to ORDER_TRIES, for one it lacks (a new
    order replaces the old without penalty; Elanthipedia: Work
    orders). (order, spec), or (None, None) said."""
    for attempt in range(1, ORDER_TRIES + 1):
        parsed = order(s, master, options["level"], seek=seek)
        if parsed is None:
            return None, None
        if parsed["count"] == 0:
            return parsed, None  # complete in the logbook: nothing to craft
        spec = recipe(parsed["item"])
        if spec is not None and sellable(spec):
            return parsed, spec
        if spec is None:
            lack = f"the book has no page for {parsed['item']}"
        else:
            unsold = [herb for herb in spec[2:4] if herb and herb not in CATALOG][0]
            lack = f"the Supplies sells no dried {unsold}"
        if attempt < ORDER_TRIES:
            s.echo(f"remedies: {lack} — asking for another order")
        else:
            s.echo(f"remedies: {lack} — {ORDER_TRIES} orders asked, stopping")
    return None, None


def rank_of(s):
    experience = getattr(s.state, "experience", None) or {}
    return (experience.get(SKILL) or {}).get("rank")


COUNTERS = ("spent", "crushes", "crush_seconds", "rejected")


def open_order(s, parsed, level):
    """The order in progress as a persisted state (client/game/
    workorders.py): an order resumed from the logbook takes up the
    file a run before left — its full count, its coin and crushes —
    and a new order starts one."""
    name = getattr(s.state, "name", None) or "unknown"
    kept = load_open(name)
    if (
        parsed.get("resumed")
        and kept
        and str(kept.get("item", "")).lower() == parsed["item"]
    ):
        state = kept
        s.echo(
            f"remedies: the order's {state.get('spent', 0)} Kronars and "
            f"{state.get('crushes', 0)} crushes so far carried over"
        )
    else:
        state = {
            "item": parsed["item"],
            "count": parsed["count"],
            "quality": parsed.get("quality") or "",
            "level": level,
            "due": parsed.get("due"),
            "spent": 0,
            "crushes": 0,
            "crush_seconds": 0,
            "rejected": 0,
            "rank_before": rank_of(s),
            "started": time.time(),
        }
    state["loaded"] = {key: state.get(key, 0) for key in COUNTERS}
    save_open(name, {k: v for k, v in state.items() if k != "loaded"})
    return state


def sync_order(s, state, tally, snapshot):
    """The state's counters brought up to date — what earlier runs
    left plus this run's since the order was taken up — and saved."""
    for key in COUNTERS:
        state[key] = state["loaded"][key] + (tally.get(key, 0) - snapshot[key])
    name = getattr(s.state, "name", None) or "unknown"
    save_open(name, {k: v for k, v in state.items() if k != "loaded"})


def record_order(s, state, spec, catalyst, paid):
    """The order handed in, one row in history.db's work_orders
    (client/game/workorders.py) from the persisted state: the pay,
    the order's stacks at catalog prices — the rejected ones too,
    they cost the same — the coin spent and the crushes since the
    order was taken up, across every run it took, the rank before
    and after. A failure is logged, never ends the run."""
    rejected = state.get("rejected", 0)
    try:
        from client.game.history import database_path

        connection = open_ledger(database_path())
        try:
            record(
                connection,
                character_name=getattr(s.state, "name", None) or "unknown",
                discipline="remedies",
                level=state.get("level") or "easy",
                item=state["item"],
                stacks=state["count"],
                quality=state.get("quality") or "",
                earned=paid,
                cost=material_cost(spec, catalyst) * (state["count"] + rejected)
                if spec
                else 0,
                rejected=rejected,
                spent=state.get("spent", 0),
                crushes=state.get("crushes", 0),
                rank_before=state.get("rank_before"),
                rank_after=rank_of(s),
                minutes=round((time.time() - state.get("started", time.time())) / 60),
                crush_seconds=state.get("crush_seconds", 0),
            )
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("remedies: the order was not ledgered")
    clear_open(getattr(s.state, "name", None) or "unknown")


def ledger(s):
    """`;remedies ledger`: the character's orders on record."""
    from client.game.history import database_path

    connection = open_ledger(database_path())
    try:
        entries = rows(
            connection,
            character=getattr(s.state, "name", None) or None,
            discipline="remedies",
        )
    finally:
        connection.close()
    for line in ledger_lines(entries):
        s.echo(f"remedies: {line}")


def work(s, options, profile):
    """The work orders: an order asked (or the logbook's resumed), its
    stacks crafted and bundled — the herbs, water and coal bought as
    they run out, the coins fetched from the bank — and the logbook
    handed in, order after order until `return`, `count` orders, or
    something ends it."""
    master = str(profile.get("crafting_master") or DEFAULT_MASTER).lower()
    catalyst = str(profile.get("catalyst") or "").strip()
    tally = {"crushes": 0, "unrecognized": 0, "spent": 0}
    orders = 0
    earned = 0
    while True:
        if tally.get("ending"):
            break
        if not find_master(s, profile, master):
            s.echo("remedies: no master to ask — stopping")
            break
        parsed, spec = next_order(
            s, master, options, seek=lambda: find_master(s, profile, master)
        )
        if parsed is None:
            break
        snapshot = {key: tally.get(key, 0) for key in COUNTERS}
        state = open_order(s, parsed, options["level"])
        remaining = parsed["count"]
        why = None
        started = False
        rejected = 0
        if remaining and not tools_in_hand(s):
            break
        while remaining > 0:
            why = craft(s, spec, parsed["item"], catalyst, options, tally, started)
            started = False
            sync_order(s, state, tally, snapshot)
            if why is None:
                take_out(s, spec[4])
                outcome, remaining, due = bundle(s, spec[4], remaining)
                if outcome == "rejected":
                    rejected += 1
                    tally["rejected"] = tally.get("rejected", 0) + 1
                    s.echo(
                        f"remedies: the {spec[4]} is below the order's quality — disposed of, "
                        f"another stack for the {remaining} still owed ({rejected}/{REJECTIONS})"
                    )
                    if rejected >= REJECTIONS:
                        why = f"{rejected} remedies below the order's quality"
                        break
                elif outcome == "unknown":
                    why = "the bundle answered nothing known"
                    break
                else:
                    s.echo(
                        f"remedies: {spec[4]} bundled — {remaining} more, {due} roisaen"
                    )
                if remaining and not tools_in_hand(s):
                    why = "tools"
                    break
                continue
            ask(s, "stow my pestle")
            ask(s, "stow my mortar")
            bought = restock(s, spec, catalyst, why, remaining, tally)
            if not bought:
                if bought is False:
                    why = f"out of {why}"
                break
            if not to_master(s, profile):
                why = "could not walk back to the crafting hall"
                break
            if not tools_in_hand(s):
                why = "tools"
                break
            # The remedy begun stays in the mortar and goes on; only the
            # controlling herb, put in first, starts the stack over.
            started = why != f"dried {spec[2]}"
            why = None
        ask(s, "stow my pestle")
        ask(s, "stow my mortar")
        sync_order(s, state, tally, snapshot)
        if why is not None:
            s.echo(f"remedies: {why} — the order waits in the logbook")
            break
        if not find_master(s, profile, master):
            s.echo("remedies: could not reach the master with the logbook — stopping")
            break
        ask(s, "get my logbook")
        answer = ask(s, f"give my logbook to {master}")
        paid = payment(answer)
        if paid is None:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: the master answered {first!r} to the logbook — stopping")
            ask(s, "stow my logbook")
            break
        orders += 1
        earned += paid
        ask(s, "stow my logbook")
        sync_order(s, state, tally, snapshot)
        record_order(s, state, spec, catalyst, paid)
        s.echo(
            f"remedies: order {orders} paid {paid} Kronars "
            f"({earned - tally['spent']} clear of {tally['spent']} spent so far)"
        )
        if options["count"] and orders >= options["count"]:
            break
        if tally.get("ending") or wants_stop(s):
            s.echo("remedies: stopping as asked — the order is handed in")
            break
    s.echo(
        f"remedies: {orders} order(s), {earned} Kronars earned, {tally['spent']} spent, "
        f"{tally['crushes']} crush(es) — {SKILL} {mindstate(s, SKILL)}/34"
    )


def run(s, options):
    if options["ledger"]:
        ledger(s)
        return
    profile = profile_of(s)
    value = ensure_mindstate(s, SKILL, ask)
    if value is None:
        s.echo(f"remedies: EXP shows no {SKILL} — nothing to train")
        return
    clear_hands(s, profile)
    try:
        if options["work"]:
            work(s, options, profile)
        else:
            train(s, options, profile)
    finally:
        # The weapon stays sheathed: a hunt WIELDs its own (the operator,
        # 2026-09-22 — no reason for a crafter to end armed).
        if danger(s) and "hostiles" in (danger(s) or ""):
            flight.react(s, "remedies")


def main(s):
    run(s, parse_args(s.args or []))
