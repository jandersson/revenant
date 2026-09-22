"""Train Alchemy by crushing remedies in the mortar, and fill the society's work orders:  ;remedies

    ;remedies                 the head salve — dried nemoih in the mortar, CRUSHed until Alchemy mind-locks
    ;remedies chest           another chapter-3 salve (neck, abdominal, chest, head, back, eye); its dried herb must be on you
    ;remedies count=2         finish that many remedies, then end
    ;remedies until=30        stop at that mindstate instead of 34
    ;remedies once            exit at mind-lock instead of holding for the drain
    ;remedies work            an easy work order: ask the master, craft each stack, bundle it, hand the logbook in, once
    ;remedies work count=3    that many orders; `challenging` or `hard` for the harder tiers
    ;remedies return          (typed while it runs) finish the crush in hand and end

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

`work` is the society's order (Elanthipedia: Work orders): the logbook
in hand, ASK <master> FOR EASY REMEDIES WORK where the master stands
(Lanshado in the Crossing society's Tool Shop, map 8860 — the profile's
`crafting_master` and `crafting_hall`), the order read back ("an order
for some blister cream. I need 2 stacks (5 uses each) finely-crafted
... due in 65 roisaen"), each stack crafted from the herbs on you
(none left is said, with what to buy at the society's Supplies — the
script buys nothing), BUNDLE <remedy> WITH MY LOGBOOK, and GIVE MY
LOGBOOK TO <master> for the pay ("are given 1146 Kronars in return"
for two stacks of blister cream at rank 6, 748 Kronars of herbs and
coal in). An order the book has no page for is said and left. GIVE is
the script's own: the session refuses it from outside (#161).

The mortar and the pestle fill both hands: the weapon is SHEATHEd
first, the pestle is stowed for every fetch and taken back for the
crush, the mortar before the logbook comes out. Nothing is ever
dropped. It stops at mind-lock (holding until the drain, `once`
exits), on `return`, on death or hostiles (the shared escape), when
the herb, the water, the catalyst or the book is not on you, and when
a CRUSH answers nothing the table knows three times. ;train runs it as
a task (skills: ["Alchemy"], return_word "return"; `"args": ["work"]`
for the orders).
Stop with:  ;stop remedies, or ;remedies return.
"""

from client.game import flight, probe
from client.game.loop import danger, ensure_mindstate, mindstate, pause, wants_stop
from client.game.probe import classify
from client.game.remedies import (
    BUNDLED,
    CRUSH_OUTCOMES,
    NO_MASTER,
    POURED,
    STUDIED,
    TOO_HARD,
    crush_command,
    parse_args,
    parse_logbook,
    parse_order,
    payment,
    recipe,
)

SKILL = "Alchemy"
RESUME_BELOW = 28
LOCK_POLL = 30
COLLECT_SECONDS = 3
TAIL_SECONDS = 1.5
MAX_CRUSHES = 400  # the fuse under the loop
MISSES = 3  # unrecognized CRUSH answers before the run ends
STUDIES = 2  # STUDYs per remedy before the recipe is called wrong
DEFAULT_MASTER = "lanshado"
DEFAULT_HALL = "8860"  # the Crossing Alchemy Society's Tool Shop


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


def redraw(s, profile):
    """WIELD the weapon back: the game finds it where SHEATHE put it."""
    weapon = profile.get("weapon") or ""
    if weapon:
        ask(s, f"wield my {weapon}")


def missing(answer):
    return "referring" in answer or "could not find" in answer


def study(s, chapter, page, what):
    """The page STUDied: the book out (a hand freed of the pestle if
    need be), turned to the chapter and page, studied, stowed. False
    when the book is not on you or the game did not say it is ready."""
    answer = ask(s, "get my book")
    if missing(answer):
        s.echo("remedies: no remedies book on you — stopping")
        return False
    ask(s, f"turn my book to chapter {chapter}")
    ask(s, f"turn my book to page {page}")
    answer = ask(s, "study my book")
    s.waitrt()
    ask(s, "stow my book")
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
        s.echo(f"remedies: no {noun} on you — the {what} is missing, stopping")
        ask(s, "get my pestle")
        return False
    verb = "pour" if what == "water" else "put"
    answer = ask(s, f"{verb} my {noun} in my mortar")
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


def craft(s, spec, what, catalyst, options, tally):
    """One remedy from `spec` (chapter, page, herb, extra, noun): the
    page studied, the herb in, CRUSH until finished with the water, the
    second herb and the catalyst put in as asked. The finished remedy
    is left in the mortar. Returns None when done, else why it could
    not be: "stopped", "locked", the missing thing, "beyond".

    `tally` counts crushes and unrecognized answers across the run;
    the mortar and pestle are in hand on entry and on exit."""
    chapter, page, herb, extra, noun = spec
    if not study(s, chapter, page, what):
        return "book"
    started = False
    misses = 0
    studies = 1
    if not fetch_into_mortar(s, herb, "herb"):
        return f"dried {herb}"
    for _ in range(MAX_CRUSHES):
        if why := danger(s):
            return why
        if wants_stop(s):
            return "stopped"
        value = mindstate(s, SKILL)
        if value is not None and value >= options["until"]:
            if options["once"]:
                return "locked"
            if not hold_at_lock(s, options["until"]):
                return "stopped"
        answer = ask(s, crush_command(herb, started, noun))
        s.waitrt()
        tally["crushes"] += 1
        outcome = classify(answer, CRUSH_OUTCOMES)
        if outcome == "crushed":
            started = True
            misses = 0
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
            ask(s, "stow my pestle")
            if not study(s, chapter, page, what):
                ask(s, "get my pestle")
                return "book"
            ask(s, "get my pestle")
        elif outcome == "free hand":
            ask(s, "stow my pestle")
            ask(s, "get my pestle")
        elif outcome == "missing" and not started:
            if not fetch_into_mortar(s, herb, "herb"):
                return f"dried {herb}"
        else:
            misses += 1
            tally["unrecognized"] += 1
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: unrecognized CRUSH answer {first!r} — please report it")
            if misses >= MISSES:
                return "unrecognized"
    return "fuse"


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


def order(s, master, level):
    """The logbook in hand, the order asked and read back; the parsed
    order or None (said)."""
    if missing(ask(s, "get my logbook")):
        s.echo("remedies: no work order logbook on you — stopping")
        return None
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


def bundle(s, noun):
    """The remedy in one hand, the logbook in the other, BUNDLEd; the
    logbook's count read back. (remaining, roisaen) or None."""
    ask(s, "get my logbook")
    answer = ask(s, f"bundle my {noun} with my logbook")
    if not any(word in answer for word in BUNDLED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: BUNDLE answered {first!r}")
    state, remaining, due = parse_logbook(ask(s, "read my logbook"))
    ask(s, "stow my logbook")
    if state == "done":
        return 0, due
    return remaining, due


def work(s, options, profile):
    """The work orders: one order asked, its stacks crafted and bundled,
    the logbook handed in — `count` times (once by default) or until
    something ends it."""
    master = str(profile.get("crafting_master") or DEFAULT_MASTER).lower()
    catalyst = str(profile.get("catalyst") or "").strip()
    tally = {"crushes": 0, "unrecognized": 0}
    orders = 0
    earned = 0
    while True:
        if not to_master(s, profile):
            s.echo("remedies: could not reach the crafting hall — stopping")
            break
        parsed = order(s, master, options["level"])
        if parsed is None:
            break
        spec = recipe(parsed["item"])
        if spec is None:
            s.echo(
                f"remedies: the book has no page for {parsed['item']} — ask again later"
            )
            break
        if not tools_in_hand(s):
            break
        remaining = parsed["count"]
        why = None
        while remaining > 0:
            why = craft(s, spec, parsed["item"], catalyst, options, tally)
            if why is not None:
                break
            take_out(s, spec[4])
            remaining, due = bundle(s, spec[4])
            s.echo(f"remedies: {spec[4]} bundled — {remaining} more, {due} roisaen")
            if remaining and not tools_in_hand(s):
                why = "tools"
                break
        ask(s, "stow my pestle")
        ask(s, "stow my mortar")
        if why is not None:
            if why.startswith("dried") or why in ("water", catalyst):
                s.echo(
                    f"remedies: out of {why} — the society's Supplies sells the herbs and "
                    "water, the Forging Society's Supplies the coal; the order waits in "
                    "the logbook"
                )
            else:
                s.echo(f"remedies: {why} — the order waits in the logbook")
            break
        if not to_master(s, profile):
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
        s.echo(f"remedies: order {orders} paid {paid} Kronars")
        if options["count"] and orders >= options["count"]:
            break
        if options["count"] == 0:
            break  # one order by default: the herbs run out, the time is short
    s.echo(
        f"remedies: {orders} order(s), {earned} Kronars, {tally['crushes']} crush(es) — "
        f"{SKILL} {mindstate(s, SKILL)}/34"
    )


def run(s, options):
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
        redraw(s, profile)
        if danger(s) and "hostiles" in (danger(s) or ""):
            flight.react(s, "remedies")


def main(s):
    run(s, parse_args(s.args or []))
