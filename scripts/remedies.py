"""Train Alchemy crushing remedies, or fill the society's work orders:  ;remedies

    ;remedies                 the head salve, CRUSHed until Alchemy mind-locks
    ;remedies <salve>         another chapter-3 salve (neck, abdominal, chest, head, back, eye;
                              or salve=<name>); its dried herb must be on you
    ;remedies count=2         finish that many remedies (orders, with work), then end
    ;remedies until=30        stop at that mindstate instead of 34
    ;remedies once            end at mind-lock instead of holding or, with work, working on
    ;remedies work            the Alchemy Society's easy work orders, one after another, for the pay
    ;remedies work hard       a harder tier: challenging or hard
    ;remedies ledger          the orders on record: pay, materials, profit, the last few
    ;remedies merge           merge each dried herb's stacks into full ones of 75, then end
    ;remedies return          (typed while it runs) finish the remedy, or the order, in hand and end
    ;stop remedies            quit at once; the mortar and pestle are stowed

What it does
  - STUDies the book page, puts the herb's dried stack in the mortar and CRUSHes,
    adding water (alcohol for an ointment), the second herb and the catalyst as
    the game asks.
  - Work: reads the logbook (resumes, hands in or clears an order), finds the master,
    crafts and bundles each stack, hands the logbook in for the pay. An order that
    expires on the way is untied, its stacks stowed for the next, and another asked.
  - Buys what runs out (herbs, water, alcohol, coal ten at a time), coins from the bank
    when short, and finishes a remedy left in the mortar first; one buy per
    shortage, and ENCUMBRANCE read after each.
  - First merges each dried herb's stacks in every container into full stacks
    of 75 and one short one (a stack caps at 75).
  - A herb stack short of 25 pieces is combined with the herb's other stacks
    first (foraged ones from ;forage herb); the mortar takes 25 of a bigger one.
  - With the profile's `forage_herbs`, red flowers it runs out of are foraged
    (;forage herb, once an order) before any are bought.
  - The mortar and pestle are the profile's `mortar` and `pestle`, named whole
    ("iron mortar"): a looted stone mortar in the same pack is never taken.
  - A remedy too poor for the order is discarded if `droppable` names it, else stowed.
  - A remedy not of the order's 5 uses is cut to 5 (MARK, BREAK) or topped up from
    another stack of it (COMBINE); what is broken off is stowed for the next order.
  - Every order handed in is a row in history.db, summed by `;remedies ledger`.

When it stops
  - mind-lock with `once` (else it holds for the drain, or works on under `work`)
  - `count` reached, or ;remedies return
  - death or hostiles (the shared escape)
  - the herb, liquid, catalyst or book not on you, or CRUSH answers it cannot read
  - a shortage the craft still finds right after its buy, 20 buys in a run, or a
    load reading Overburdened after one

Profile keys: `catalyst` (coal nugget), `forage_herbs`, `crafting_master`, `crafting_hall`. ;train runs
it as an Alchemy task (`"args": ["work"]` for orders, with `return_grace` and `minutes`
long enough to finish one). The recipes and wordings are client/game/remedies.py's.
"""

import logging
import time

from client.game import (
    discard,
    encumbrance,
    flight,
    hands,
    herbstacks,
    items,
    shop,
    trainer,
    travel,
)
from client.game.act import ask, missing
from client.game.loop import danger, ensure_mindstate, mindstate, wants_stop
from client.game.probe import classify
from client.game.money import phrase
from client.game.seek import present
from client.game.remedies import (
    MASTER_UNTIE,
    BUNDLED,
    building_rooms,
    CATALYST_STOCK,
    LIQUIDS,
    COMBINED,
    CRUSH_OUTCOMES,
    FORAGE_NAMES,
    BROKEN,
    MARKED,
    MORTAR_BUSY,
    MORTAR_FULL,
    STACK_PIECES,
    STACK_USES,
    WRONG_SIZE,
    containers_of,
    containers_with,
    pieces,
    NO_MASTER,
    ORDER_EXPIRED,
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
    recipe,
    roundtime_of,
    sellable,
    shortage,
    unsold,
    uses,
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

# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Train Alchemy by crushing remedies in the mortar, and fill the society's work orders:  ;remedies

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
profile's `catalyst`, named `coal nugget`: a looted lead nugget answers
GET MY NUGGET too, and a refused catalyst stops the craft), one use each. "Applying the final touches,
you complete working on some blister cream." ends it and the remedy is
stowed, or bundled with the logbook under `work`.

`work` is the society's orders (Elanthipedia: Work orders), run as a
living: the logbook in hand and READ first — an order it still tracks
is resumed, a complete one handed in, an expired one (past its due
time: "This logbook is tracking a work order that has expired.")
UNTIEd and its stacks stowed before a new one is asked, 2026-09-26 — one
that expires while it is worked, at a BUNDLE or the hand-in, goes the
same way through the next READ, #397 — and
every order bundles the finished stacks of its remedy INV LIST shows
in a container before any crush, #324 —
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
per item through client/game/shop.py (the purse read off WEALTH, the
shortfall fetched at the teller, the quote checked against the noun
before the second ORDER buys it, a wrong quote REFUSEd), each
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
The restock guard (#413, 2026-10-01/02): ;remedies work bought dried
red flowers 31 times in 20 minutes — about 24,700 Kronars, 39 stacks
by morning — because a bare COUNT MY FLOWERS read another stack than
the one just bought, the shortage repeated, and nothing bounded it;
five full stacks already read overburdened at the clerk (#406) and
the walk then failed sitting (#411). The stack in hand is counted by
its id since #407 step 3; the guard here is the bound: a shortage the
craft finds again with no crush since its buy ends the order with the
reason said, RESTOCKS_PER_RUN buys end a run, and ENCUMBRANCE is read
after every buy — LOAD_LIMIT or past it stops the run where the
operator can lighten the load (Elanthipedia's Encumbrance page: the
heavier the load, the less able to stand).
"""

SKILL = "Alchemy"
MAX_CRUSHES = 400  # the fuse under the loop
MISSES = 3  # unrecognized CRUSH answers before the run ends
REFUSALS = 2  # "Crush what?" answers in a row before the run ends
STUDIES = 2  # STUDYs per remedy before the recipe is called wrong
DEFAULT_MASTER = "lanshado"
DEFAULT_HALL = "8860"  # the Crossing Alchemy Society's Tool Shop
MASTER_LAPS = 2  # laps of the building's rooms looking for the master
RESTOCKS_PER_RUN = 20  # buys in one run at most (#413)
LOAD_LIMIT = (
    "Overburdened"  # a buy leaving the load here or past it stops the run (#413)
)


# The mortar and pestle as the profile spells them (`mortar`, `pestle`:
# "iron mortar", "iron pestle"), set by run() for every send below: a
# bare MY MORTAR took a looted stone mortar out of the same pack and
# the remedies went into it (#478).
TOOLS = {"mortar": "mortar", "pestle": "pestle"}


def name_tools(profile):
    for tool in TOOLS:
        TOOLS[tool] = str((profile or {}).get(tool) or tool).strip().lower() or tool


def my(tool):
    """The tool as the profile spells it: "my iron pestle"."""
    return f"my {TOOLS[tool]}"


def profile_of(s):
    name = getattr(s.state, "name", None)
    if not name:
        return {}
    from client.game.profile import load_profile

    return load_profile(name)


def clear_hands(s, profile):
    """The weapon SHEATHEd where WIELD drew it from, anything else STOWed:
    the mortar and the pestle want both hands. Never DROP."""
    weapon = (profile.get("weapon") or "").lower()
    container = profile.get("weapon_container") or ""
    keep = ()
    if weapon and container and hands.holding(s, weapon):
        hands.sheathe(s, weapon, container, ask=ask)
        keep = (weapon,)
    hands.free(s, keep=keep, ask=ask)


def study(s, chapter, page, what):
    """The page STUDied: the book out (a hand freed of the pestle if
    need be), turned to the chapter and page, studied, stowed. False
    when the book is not on you or the game did not say it is ready."""
    # The mortar and pestle fill both hands ("You need a free hand to
    # pick that up.", 2026-09-22): the pestle down for the book, up after.
    ask(s, f"stow {my('pestle')}")
    answer = ask(s, "get my book")
    if missing(answer):
        s.echo("remedies: no remedies book on you — stopping")
        ask(s, f"get {my('pestle')}")
        return False
    ask(s, f"turn my book to chapter {chapter}")
    ask(s, f"turn my book to page {page}")
    answer = ask(s, "study my book")
    s.waitrt()
    ask(s, "stow my book")
    ask(s, f"get {my('pestle')}")
    lowered = answer.lower()
    if any(word in lowered for word in TOO_HARD):
        s.echo(
            f"remedies: {what} is beyond the ranks — mishaps ahead, the crushes still teach"
        )
    if not any(word in lowered for word in STUDIED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: STUDY answered {first!r} — stopping")
        return False
    return True


def fetch_into_mortar(s, noun, what):
    """The pestle down, `noun` GOT and PUT (water POURed) in the mortar,
    what stays in hand stowed, the pestle back up. False when the game
    finds no such thing on you. A herb's dried stack is reached by
    herbstacks.get_dried — "dried <herb>" first, then the plain noun's
    ordinals with the GET's answer judging: a plain GET MY FLOWERS took
    a fresh stack (2026-10-01, #406), and the Society's bought stacks
    answer to "flowers" but not to "dried" (#420). In hand it goes by
    its id, else the plain noun — never "dried <herb>" again."""
    dried = what in ("herb", "second herb")
    ask(s, f"stow {my('pestle')}")
    if dried:
        answer = herbstacks.get_dried(s, ask, noun)
    else:
        answer = ask(s, f"get my {noun}")
    if answer is None or (not dried and missing(answer)):
        shown = f"dried {noun}" if dried else noun
        s.echo(f"remedies: no {shown} on you — the {what} is missing")
        ask(s, f"get {my('pestle')}")
        return False

    def held():
        return items.name(s, f"my {noun}")

    def token():
        return items.ref(s, f"my {noun}") or noun

    if what == "herb" and not full_stack(s, noun):
        s.echo(
            f"remedies: the dried {noun} on you come to fewer than {STACK_PIECES} "
            f"pieces — the {what} is missing"
        )
        hands.stow(s, token(), ask=ask)
        ask(s, f"get {my('pestle')}")
        return False
    verb = "pour" if what in LIQUIDS else "put"
    answer = ask(s, f"{verb} {held()} in {my('mortar')}")
    lowered = answer.lower()
    if what == "herb" and any(word in lowered for word in MORTAR_FULL):
        hands.stow(s, token(), ask=ask)  # the mortar took its 25; the rest back
    if any(word in lowered for word in MORTAR_BUSY):
        # Another remedy is in progress in the mortar (2026-09-23): the
        # herb stays in hand for the caller, the pestle comes back up.
        held = remedy_in_mortar(answer)
        name = held[0] if held else "remedy"
        s.echo(f"remedies: the mortar already holds an unfinished {name}")
        hands.stow(s, token(), ask=ask)
        ask(s, f"get {my('pestle')}")
        return f"busy:{name}"
    if what in LIQUIDS and not any(word in lowered for word in POURED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: the pour answered {first!r}")
    if what != "herb":
        hands.stow(s, token(), ask=ask)  # the liquid, the second herb's stack, a nugget
    ask(s, f"get {my('pestle')}")
    return True


def full_stack(s, noun):
    """The herb in hand (its plain noun, "flowers") brought to
    STACK_PIECES: COUNT it, and while it is short combine the herb's
    other dried stacks into it, container by container (the mortar set
    down meanwhile, for the hand), each reached by herbstacks.get_dried
    (#420). True when it holds enough — or COUNT says nothing, the old
    way (#370)."""

    def in_hand():
        # The stack held, by its id when the hand tag carries one (#402:
        # a bare noun takes the first item of that noun), else MY <noun>
        # — read afresh each time, a COMBINE gives its result a new id.
        return items.name(s, f"my {noun}")

    def pair():
        # Both held stacks by their ids when the tags carry them (#402),
        # else the plain noun twice: the two in hand are the two.
        ids = list(herbstacks.held(s))
        if len(ids) == 2:
            return f"#{ids[0]}", f"#{ids[1]}"
        return noun, noun

    held = pieces(ask(s, f"count {in_hand()}"))
    if held is None or held >= STACK_PIECES:
        return True
    ask(s, f"stow {my('mortar')}")
    possessions = getattr(s.state, "possessions", None)
    # Where INV LIST showed the herb, else every container (a stack
    # bought since the login listing): never the gem pouch first.
    places = containers_with(possessions, noun) or containers_of(possessions)
    for container in places:
        while held < STACK_PIECES:
            if herbstacks.get_dried(s, ask, noun, container=container) is None:
                break
            first_stack, second_stack = pair()
            joined = ask(s, f"combine {first_stack} with {second_stack}").lower()
            if any(word in joined for word in herbstacks.FULL + herbstacks.LEFT_OVER):
                # One of the two is full (#402): it is the stack to use,
                # the other goes back — 2026-10-01 stowed the full one
                # and foraged with 96 pieces on hand. Two stacks of the
                # noun in hand: this COUNT and the PUT go by the game's
                # own order (first, second), so both name the noun bare.
                first = pieces(ask(s, f"count my {noun}")) or 0
                which = "second " if first >= STACK_PIECES else ""
                ask(s, f"put my {which}{noun} in my {container}")
                held = pieces(ask(s, f"count {in_hand()}")) or held
                continue
            if not any(word in joined for word in COMBINED):
                hands.stow(s, noun, ask=ask)  # one of the two back: they would not join
                break
            held = pieces(ask(s, f"count {in_hand()}")) or held
        if held >= STACK_PIECES:
            break
    ask(s, f"get {my('mortar')}")
    return held >= STACK_PIECES


def refused_ingredient(s, noun, what):
    """The game would not take what GET MY <noun> found for the remedy
    in progress ("...is not required to continue crafting the blister
    cream"): another thing answered to the noun — a looted lead nugget
    for the coal one, 2026-09-27, CRUSH and PUT went round 370 times
    until the fuse. Said, and the craft stops; the remedy waits in the
    mortar."""
    s.echo(
        f"remedies: GET MY {noun.upper()} found something the remedy refuses as its "
        f"{what} — name it more exactly in the profile (coal nugget); stopping"
    )
    return "refused"


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
    chapter, page, herb, extra, noun, liquid = spec
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
            elif not trainer.hold_at_lock(
                s, "remedies", SKILL, options["until"], again="crushing again"
            ):
                return "stopped"
        answer = ask(
            s, crush_command(herb, started, noun, TOOLS["mortar"], TOOLS["pestle"])
        )
        s.waitrt()
        tally["crushes"] += 1
        tally["crush_seconds"] = tally.get("crush_seconds", 0) + roundtime_of(answer)
        outcome = classify(answer, CRUSH_OUTCOMES)
        if outcome == "tool worn":
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(
                f"remedies: {first} — the tool needs repair or replacing "
                "(;repair tools takes it to Rangu); stopping"
            )
            return "tool"
        if outcome == "crushed":
            started = True
            misses = 0
            refused = 0
        elif outcome in ("need water", "need alcohol"):
            # The liquid the game names (#427: the ointment's alcohol),
            # bought at the Supplies like the water when none is on you.
            started = True
            wanted = outcome.split()[-1]
            fetched = fetch_into_mortar(s, wanted, wanted)
            if isinstance(fetched, str):
                return refused_ingredient(s, wanted, wanted)
            if not fetched:
                return wanted
        elif outcome == "need herb":
            started = True
            if not extra:
                s.echo("remedies: the game wants a second herb the page did not list")
                return "second herb"
            fetched = fetch_into_mortar(s, extra, "second herb")
            if isinstance(fetched, str):
                return refused_ingredient(s, extra, "second herb")
            if not fetched:
                return f"dried {extra}"
        elif outcome == "need catalyst":
            started = True
            if not catalyst:
                s.echo(
                    "remedies: the remedy wants a catalyst and the profile names none "
                    "— it stays unfinished in the mortar for the next run"
                )
                return "catalyst"
            fetched = fetch_into_mortar(s, catalyst, "catalyst")
            if isinstance(fetched, str):
                return refused_ingredient(s, catalyst, "catalyst")
            if not fetched:
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
            ask(s, f"stow {my('pestle')}")
            ask(s, f"get {my('pestle')}")
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
    answer = ask(s, f"look in {my('mortar')}")
    held = unfinished_in_mortar(answer)
    if held is None and "unfinished" in answer.lower():
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
    hands.stow(s, spec[4], ask=ask)
    if not tools_in_hand(s):
        return "mortar"
    s.echo(f"remedies: the {name} is done and stowed — the mortar is free")
    return None


def take_out(s, noun):
    """The finished remedy out of the mortar into a hand: the pestle
    stowed first, then the mortar (a free hand for whatever is next)."""
    ask(s, f"stow {my('pestle')}")
    ask(s, f"get my {noun} from {my('mortar')}")
    ask(s, f"stow {my('mortar')}")


def stacks_on_hand(possessions, item):
    """Finished stacks of `item` ("blister cream") the parser's INV LIST
    shows directly in a container — never the unfinished one in the
    mortar — as the containers' nouns, one per stack, in listing order."""
    by_exist = {entry.get("exist"): entry for entry in possessions or []}
    wanted = str(item or "").strip().lower()
    found = []
    for entry in possessions or []:
        name = str(entry.get("name") or "").strip().lower()
        for article in ("some ", "a ", "an "):
            if name.startswith(article):
                name = name[len(article) :]
                break
        if not wanted or name != wanted:
            continue
        holder = by_exist.get(entry.get("container_exist")) or {}
        noun = str(holder.get("noun") or "").lower()
        if noun and noun != "mortar":
            found.append(noun)
    return found


def bundle_on_hand(s, item, noun, remaining):
    """Bundle the finished stacks of the order's remedy already carried
    before a new one is crafted (#324: two blister creams untied from an
    expired order sat in the backpack while the run crushed a third, 10
    roisaen from the deadline). GET MY <item> FROM MY <container>, then
    the craft's own bundle(); a GET that finds none (the listing is as
    old as the last INV LIST) or an answer the table lacks ends it.
    The stacks still owed, None when the order has expired (#397)."""
    stacks = stacks_on_hand(getattr(s.state, "possessions", None), item)
    for container in stacks:
        if remaining <= 0:
            break
        if missing(ask(s, f"get my {item} from my {container}")):
            break
        outcome, left, due = bundle(s, noun, remaining, item)
        if outcome == "expired":
            return None
        if outcome in ("unknown", "size"):
            break
        if outcome == "bundled":
            remaining = left
            s.echo(
                f"remedies: a {item} from the {container} bundled — "
                f"{remaining} more, {due} roisaen"
            )
    return remaining


def tools_in_hand(s):
    # The mortar and pestle fill both hands: anything else held — a herb
    # stack ;forage left behind (2026-09-30, #395) — is stowed first,
    # never dropped, or the pestle and the book find no hand.
    hands.free(s, keep=tuple(TOOLS.values()), ask=ask)
    for tool in ("mortar", "pestle"):
        if missing(ask(s, f"get {my(tool)}")):
            s.echo(f"remedies: no {TOOLS[tool]} on you — stopping")
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
            hands.stow(s, spec[4], ask=ask)
            if options["count"] and salves >= options["count"]:
                why = f"{salves} salve(s) made"
                break
            if not tools_in_hand(s):
                return
            continue
        break
    s.echo(f"remedies: {why} — {salves} salve(s), {SKILL} {mindstate(s, SKILL)}/34")
    ask(s, f"stow {my('pestle')}")
    ask(s, f"stow {my('mortar')}")


def to_master(s, profile):
    """Walk to the crafting hall (the profile's `crafting_hall`, a ;go2
    target; the Crossing society's Tool Shop by default)."""
    target = str(profile.get("crafting_hall") or DEFAULT_HALL)
    return travel.go(s, target, "the crafting hall")


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


def find_master(s, profile, master, mapdb=None, here=None, finishing=False):
    """The master where he stands: the crafting hall first, then the
    building's other rooms, MASTER_LAPS laps, until a listing names
    him. Lanshado wanders the society ("steadies himself and shuffles
    away", "softly shuffles into the area", captured 2026-09-22; the
    operator, 2026-09-23: "he's in the society building somewhere, the
    script just needs to look for him"). False when the hall is out of
    reach, the map shows no building, or he is nowhere in it. A room
    that already lists him is the answer, no walk (the hand-in used to
    walk back to the hall from the room he was found in, 12:10 on
    2026-09-23). A typed return ends the search, except when
    `finishing`: the hand-in of a finished order is part of the
    graceful end, and only danger cuts it (#426: a return's finished
    salves were never delivered, the master two rooms away)."""
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
            if danger(s) or (not finishing and wants_stop(s)):
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
UNTIED_ONE = ("you untie",)


def untie_expired(s):
    """An order past its due time: UNTIE MY LOGBOOK until nothing more is
    tied to it, each piece that comes off STOWed — a stack of the same
    remedy fills a later order — and the saved order cleared, so the
    master will give another (2026-09-26: a blister cream order from the
    night before stopped every ;remedies work after it). UNTIE answers
    "You untie the cream from the logbook." and, with nothing left on
    it, "You have nothing bundled with the logbook." (both captured
    2026-09-26); an answer that is neither is echoed for the report."""
    s.echo("remedies: the logbook's order expired — untying it for a new one")
    for attempt in range(UNTIE_TRIES):
        answer = ask(s, "untie my logbook")
        lowered = answer.lower()
        if not any(word in lowered for word in UNTIED_NONE + UNTIED_ONE):
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: UNTIE answered {first!r} — please report it")
        if any(word in lowered for word in UNTIED_NONE) or not lowered.strip():
            break
        hands.free(s, keep=("logbook",), ask=ask)
    name = getattr(s.state, "name", None) or ""
    if name:
        clear_open(name)


def order(s, master, level, seek=None):
    """The logbook read where it is — an order it still tracks is
    resumed, a complete one goes straight to the master — else, the
    logbook in hand, the order asked and read back; the parsed order or
    None (said). READ wants no hand (the operator, 2026-10-03: "You can
    read the logbook if its in a container"); the ASK wants it held
    (Elanthipedia: Work orders). `seek` finds the master again when the
    ask says he is gone."""
    text = ask(s, "read my logbook")
    if missing(text):
        s.echo("remedies: no work order logbook on you — stopping")
        return None
    state, remaining, due = parse_logbook(text)
    if state == "done":
        s.echo("remedies: the logbook holds a complete order — handing it in")
        return {"item": "", "count": 0, "quality": "", "due": due}
    if state == "open" and logbook_item(text):
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
    ask(s, "get my logbook")
    if state == "expired":
        untie_expired(s)
    answer = ask(s, f"ask {master} for {level} remedies work")
    if (
        any(word in answer.lower() for word in NO_MASTER)
        and seek is not None
        and seek()
    ):
        answer = ask(s, f"ask {master} for {level} remedies work")
    if any(word in answer.lower() for word in MASTER_UNTIE):
        untie_expired(s)
        answer = ask(s, f"ask {master} for {level} remedies work")
    if any(word in answer.lower() for word in NO_MASTER):
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


FIT_JOINS = 3  # other stacks combined into a short remedy at most (#428)


def other_in_hand(s, noun, mine):
    """The id ("#141087237") of the held `noun` that is not `mine`, or
    None."""
    for tag in hands.tags(s).values():
        if (
            tag
            and tag.get("exist")
            and f"#{tag['exist']}" != mine
            and hands._same(tag.get("noun") or "", noun)
        ):
            return f"#{tag['exist']}"
    return None


def other_stack(s, item, noun, mine, places):
    """Another stack of `item` GOT from the first of `places` that has
    one into the free hand, by its id; None when none has (a place that
    has none is dropped from the list)."""
    while places:
        if missing(ask(s, f"get my {item} from my {places[0]}")):
            places.pop(0)
            continue
        other = other_in_hand(s, noun, mine)
        if other is None:
            s.echo(f"remedies: the {item} got has no id to combine by")
        return other
    return None


def fit(s, item, noun):
    """The remedy in hand brought to the order's STACK_USES (#428),
    one hand free on entry: COUNTed; short, another stack of `item`
    COMBINEd into it, FIT_JOINS at most; over, MARKed AT the size and
    BROKEn, the rest stowed for a later order. True when the hand holds
    a stack of that size; False, said, when it cannot be had."""
    mine = items.ref(s, f"my {noun}")
    if mine is None:
        s.echo(f"remedies: the {noun} in hand has no id to size it by — kept")
        return False
    held = uses(ask(s, f"count {mine}"))
    if held is None:
        s.echo(f"remedies: COUNT gave no uses for the {noun} — kept")
        return False
    if held == STACK_USES:
        s.echo(
            f"remedies: the order refused the {noun} for its size at {held} uses "
            "— kept, please report it"
        )
        return False
    possessions = getattr(s.state, "possessions", None)
    places = list(dict.fromkeys(stacks_on_hand(possessions, item))) if item else []
    for _ in range(FIT_JOINS):
        if held >= STACK_USES:
            break
        other = other_stack(s, item, noun, mine, places)
        if other is None:
            break
        joined = ask(s, f"combine {other} with {mine}").lower()
        if not any(word in joined for word in COMBINED):
            hands.stow(s, other, ask=ask)
            break
        mine = items.ref(s, f"my {noun}") or mine  # the result has a new id
        held = uses(ask(s, f"count {mine}")) or held
    if held < STACK_USES:
        s.echo(
            f"remedies: the {noun} holds {held} use(s) and no other {item or noun} "
            f"tops it up to the order's {STACK_USES} — kept"
        )
        return False
    if held > STACK_USES:
        marked = ask(s, f"mark {mine} at {STACK_USES}")
        if not any(word in marked.lower() for word in MARKED):
            first = (marked.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: MARK answered {first!r} — the {noun} kept")
            return False
        broken = ask(s, f"break {mine}")
        if not any(word in broken.lower() for word in BROKEN):
            first = (broken.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: BREAK answered {first!r} — the {noun} kept")
            return False
        rest = other_in_hand(s, noun, mine)
        if rest is None or not hands.stow(s, rest, ask=ask):
            s.echo(f"remedies: the {noun} broken off could not be stowed — kept")
            return False
        s.echo(
            f"remedies: the {noun} cut from {held} uses to {STACK_USES}, "
            "the rest stowed for a later order"
        )
    return True


def bundled_as(s, answer):
    """BUNDLE's answer read: "bundled", "rejected" (the order's
    quality), "size" (not a stack of the order's size), "expired", or
    "unknown" (said, for the report)."""
    lowered = answer.lower()
    if any(word in lowered for word in REJECTED):
        return "rejected"
    if any(word in lowered for word in WRONG_SIZE):
        return "size"
    if any(word in lowered for word in ORDER_EXPIRED):
        return "expired"
    if not any(word in lowered for word in BUNDLED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: BUNDLE answered {first!r} — please report it")
        return "unknown"
    return "bundled"


def bundle(s, noun, expected, item=None):
    """The remedy in one hand, the logbook in the other, BUNDLEd; the
    logbook's count read back. ("bundled" | "rejected" | "size" |
    "unknown" | "expired", remaining, roisaen): rejected is the order's
    quality unmet — the remedy disposed of through discard.drop (stowed
    when the list refuses it), the order still owed its stack; size is
    a remedy fit() could not bring to the order's stack (#428), stowed;
    unknown is an answer the table lacks whose logbook count did not
    move from `expected`, the remedy stowed likewise; expired is an
    order past its due time (#397: the BUNDLE's answer or the READ's),
    the remedy stowed for the next order. `item` ("blister cream") names
    the other stacks a short remedy is topped up from."""
    ask(s, "get my logbook")
    outcome = bundled_as(s, ask(s, f"bundle my {noun} with my logbook"))
    if outcome == "size":
        # Short or over, the same line (#428): the logbook away for the
        # hand MARK/BREAK and COMBINE want, the remedy brought to size,
        # and bundled again.
        ask(s, "stow my logbook")
        fitted = fit(s, item, noun)
        ask(s, "get my logbook")
        if fitted:
            outcome = bundled_as(s, ask(s, f"bundle my {noun} with my logbook"))
    state, remaining, due = parse_logbook(ask(s, "read my logbook"))
    ask(s, "stow my logbook")
    if state == "expired":
        outcome = "expired"
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
            hands.stow(s, noun, ask=ask)
    elif outcome != "bundled":
        hands.stow(s, noun, ask=ask)
    return outcome, remaining, due


def walk_to(s, target, describe):
    """Walk to a map id or tag; True when there (or already there)."""
    return travel.go(s, target, describe)


def buy(s, noun, count, store, catalog, tally):
    """`count` of `noun` ORDERed at `store` — the coins fetched from the
    bank first when the purse is short (shop.afford) — each bought the
    shop's way (shop.buy: the quote checked against the noun before the
    second ORDER buys it), each purchase STOWed. False, said, when the
    quote names something else, the shop keeps the item, or the walk
    fails."""
    # "coal nugget" is the catalog's "nugget": the profile names it
    # whole, since a looted lead nugget answered GET MY NUGGET first.
    number, price = catalog.get(noun) or catalog[noun.split()[-1]]
    need = price * count
    if not shop.afford(s, ask, "remedies", need, "Kronars"):
        return False
    if not walk_to(s, store, "the Supplies"):
        s.echo("remedies: could not reach the Supplies — stopping")
        return False
    for _ in range(count):
        paid = shop.buy(s, ask, "remedies", f"order {number}", expect=noun)
        if paid is None:
            return False
        tally["spent"] += paid
        hands.stow(s, noun, ask=ask)
    s.echo(f"remedies: bought {count} x {noun} for {phrase(need, 'Kronars')}")
    return not overloaded(s, noun, tally)


def overloaded(s, noun, tally):
    """ENCUMBRANCE after a buy (#413): True, said, when the load reads
    LOAD_LIMIT or past it — the walk from here would fail sitting
    (#411), so the run stops where the operator can lighten the load.
    A reading the parser does not know passes."""
    level = encumbrance.parse_level(ask(s, "encumbrance"))
    if not level or encumbrance.level_index(level) < encumbrance.level_index(
        LOAD_LIMIT
    ):
        return False
    s.echo(
        f"remedies: the load reads {level} after buying {noun} — "
        "stopping before a walk fails"
    )
    tally["why"] = f"{level} after buying {noun}"
    return True


FORAGE_POLL = 5  # seconds between looks at the ;forage run


def forage_herb(s, noun, stacks, tally=None):
    """;forage herb for the stacks still owed, waited out (#370): True
    when it ran to its end, False when it would not start or the
    character died meanwhile (the forage stopped too). A `return`
    meanwhile finishes the order, the operator's rule: the forage is let
    finish and press its finds — killing it mid-press left 105 fresh
    pieces unpressed and the run bought four stacks instead (2026-10-01,
    #406)."""
    name = FORAGE_NAMES[noun]
    wanted = stacks * STACK_PIECES
    s.echo(f"remedies: foraging {wanted} pieces of {name} instead of buying")
    if not s.run("forage", ["herb", *name.split(), f"pieces={wanted}"]):
        return False
    while s.is_running("forage"):
        if s.dead:
            s.kill("forage")
            return False
        if wants_stop(s) and tally is not None and not tally.get("ending"):
            tally["ending"] = True
            s.echo("remedies: return — finishing the order in hand first")
        s.sleep(FORAGE_POLL)
    return True


def restock(s, spec, catalyst, why, remaining, tally, profile=None):
    """What the craft ran out of, bought for the stacks still to make —
    the catalyst a stock of CATALYST_STOCK (#393), or one past the order
    when it owes more — or, for a herb the profile's `forage_herbs`
    gathers, foraged once an order first; None when `why` is no
    shortage, else whether it was had."""
    short = shortage(why, spec, catalyst)
    if short is None:
        if str(why or "").startswith("dried "):
            s.echo(f"remedies: the Supplies sells no {why} — it cannot be bought")
        return None
    noun, per_stack, store, catalog = short
    # One buy per shortage (#413): the same want again with no crush
    # since its buy means the craft cannot find what was bought — a
    # bare COUNT that read another stack bought flowers 31 times in 20
    # minutes — and a second buy would only add to the load.
    last = tally.setdefault("restocked", {})
    if last.get(noun) == tally.get("crushes", 0):
        s.echo(
            f"remedies: {noun} bought for this shortage already and the craft "
            "still finds none — stopping rather than buying again"
        )
        tally["why"] = f"the {noun} bought are not found"
        return False
    if tally.get("restocks", 0) >= RESTOCKS_PER_RUN:
        s.echo(f"remedies: {RESTOCKS_PER_RUN} buys this run — stopping")
        tally["why"] = f"{RESTOCKS_PER_RUN} buys this run"
        return False
    if (
        per_stack
        and noun in FORAGE_NAMES
        and (profile or {}).get("forage_herbs")
        and not tally.get("foraged")
    ):
        tally["foraged"] = True  # once an order: a short forage is bought for
        if forage_herb(s, noun, per_stack * remaining, tally):
            return True
        s.echo(f"remedies: no {noun} foraged — buying them")
    last[noun] = tally.get("crushes", 0)
    tally["restocks"] = tally.get("restocks", 0) + 1
    count = max(1, per_stack * remaining)
    if catalyst and noun == catalyst:
        # A spare past the order (a rejected stack cost a 44-room walk,
        # #288), and never under a stock that spares the next orders the
        # Forging Society's Supplies (#393).
        count = max(count + 1, CATALYST_STOCK)
    return buy(s, noun, count, store, catalog, tally)


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
            lack = f"the Supplies sells no {unsold(spec)}"
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


LAPSED = "the order expired"


def lapsed(s, tally):
    """An order that expired while it was worked (#397: the BUNDLE's or
    the hand-in's answer): True to go on to the next order, whose READ
    finds this one expired, unties its stacks and asks for another
    (order, untie_expired); False, said, when the run was told to end."""
    if tally.get("ending") or wants_stop(s):
        s.echo(
            "remedies: the order expired — stopping as asked; the next run unties it"
        )
        return False
    return True


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
        tally.pop("foraged", None)  # each order may forage its herb once
        tally.pop("restocked", None)  # and buys for each shortage once (#413)
        remaining = parsed["count"]
        if remaining and spec:
            remaining = bundle_on_hand(s, parsed["item"], spec[4], remaining)
        if remaining is None:
            if lapsed(s, tally):
                continue
            break
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
                outcome, remaining, due = bundle(s, spec[4], remaining, parsed["item"])
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
                elif outcome == "expired":
                    why = LAPSED
                    break
                elif outcome == "unknown":
                    why = "the bundle answered nothing known"
                    break
                elif outcome == "size":
                    why = f"the {spec[4]} was not the order's stack size"
                    break
                else:
                    s.echo(
                        f"remedies: {spec[4]} bundled — {remaining} more, {due} roisaen"
                    )
                if remaining and not tools_in_hand(s):
                    why = "tools"
                    break
                continue
            ask(s, f"stow {my('pestle')}")
            ask(s, f"stow {my('mortar')}")
            bought = restock(s, spec, catalyst, why, remaining, tally, profile)
            if not bought:
                if bought is False:
                    why = tally.pop("why", None) or f"out of {why}"
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
        ask(s, f"stow {my('pestle')}")
        ask(s, f"stow {my('mortar')}")
        sync_order(s, state, tally, snapshot)
        if why == LAPSED:
            if lapsed(s, tally):
                continue
            break
        if why is not None:
            s.echo(f"remedies: {why} — the order waits in the logbook")
            break
        if not find_master(s, profile, master, finishing=True):
            s.echo("remedies: could not reach the master with the logbook — stopping")
            break
        ask(s, "get my logbook")
        answer = ask(s, f"give my logbook to {master}")
        paid = payment(answer)
        if paid is None and any(word in answer.lower() for word in ORDER_EXPIRED):
            ask(s, "stow my logbook")
            if lapsed(s, tally):
                continue
            break
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


def merge_herbs(s, quiet=False):
    """Every dried herb with two or more stacks in a container merged
    into full stacks and one short one (#402), LOOKing IN only the
    containers INV LIST showed holding a dried item (never the gem
    pouch); said per herb that merged, or once when there was nothing
    to merge (unless `quiet`)."""
    merged = False

    def report(herb, container, result):
        nonlocal merged
        if result is None:
            s.echo(
                f"remedies: merging the {herb} in the {container} met an "
                "answer it does not know — stopped, the stacks put back"
            )
            return
        found, left = result
        if left < found:
            merged = True
            s.echo(
                f"remedies: {found} stacks of {herb} in the {container} merged into {left}"
            )

    # INV LIST first (one roundtime): every stack by its id, which no
    # put-back moves — the ordinal walk found 39 of 57 (#414). The LOOK
    # IN walk stays for a run the listing gave nothing.
    ask(s, "inv list")
    s.waitrt()
    groups = herbstacks.dried_stacks(getattr(s.state, "possessions", None))
    for (container, herb), ids in groups.items():
        report(herb, container, herbstacks.merge(s, ask, herb, container, ids=ids))
    if not groups:
        for container in containers_with(
            getattr(s.state, "possessions", None), "dried"
        ):
            for herb in herbstacks.dried_herbs(ask(s, f"look in my {container}")):
                report(herb, container, herbstacks.merge(s, ask, herb, container))
    if not merged and not quiet:
        s.echo("remedies: no herb stacks to merge")


def run(s, options):
    if options["ledger"]:
        ledger(s)
        return
    profile = profile_of(s)
    name_tools(profile)
    if options["merge"]:
        clear_hands(s, profile)
        merge_herbs(s)
        return
    value = ensure_mindstate(s, SKILL, ask)
    if value is None:
        s.echo(f"remedies: EXP shows no {SKILL} — nothing to train")
        return
    clear_hands(s, profile)
    merge_herbs(s, quiet=True)
    try:
        if options["work"]:
            work(s, options, profile)
        else:
            train(s, options, profile)
    finally:
        put_tools_away(s)
        # The weapon stays sheathed: a hunt WIELDs its own (the operator,
        # 2026-09-22 — no reason for a crafter to end armed).
        if danger(s) and "hostiles" in (danger(s) or ""):
            flight.react(s, "remedies")


def put_tools_away(s):
    """The pestle and the mortar out of the hands at any end, a ;stop
    too (hands.at_end: the cleanup puts that still go out after one): a
    stopped run left both in hand on 2026-09-26, and the next task,
    ;forage, could not collect with no hand free."""
    hands.at_end(s, ("pestle", "mortar"))


def main(s):
    run(s, parse_args(s.args or []))
