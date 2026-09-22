"""Train Alchemy by crushing a salve in the mortar, step by step:  ;remedies

    ;remedies                 the head salve — dried nemoih in the mortar, CRUSHed until Alchemy mind-locks
    ;remedies chest           another chapter-3 salve (neck, abdominal, chest, head, back, eye); its dried herb must be on you
    ;remedies count=2         finish that many salves, then end
    ;remedies until=30        stop at that mindstate instead of 34
    ;remedies once            exit at mind-lock instead of holding for the drain
    ;remedies return          (typed while it runs) finish the crush in hand and end

Alchemy trains by making remedies: every CRUSH of a salve in progress
teaches (Alchemy 0/34 to rank 3 in four crushes, captured 2026-09-22 at
the Crossing Alchemy Society; client/game/remedies.py holds the
wordings), and crushing a raw flower teaches nothing — the 2014
shortcut in Pfanston's Guide to Remedies is gone. The salve wants the
apprentice remedies book's page STUDied once ("You now feel ready to
begin the crafting process."), five pieces of the dried herb in the
mortar, a splash of water when the game asks for one ("You need
another splash of water to continue crafting ...") and, last, a
catalyst (Elanthipedia: Remedies discipline: seolarn weed, coal, a
pure ingot). The society sells none: a Crossing Paladin's catalyst is
an open question (#284), so a run with no `catalyst` in the profile
crushes until the game asks for one, says so, and leaves the salve
unfinished in the mortar — the next run continues it, and every crush
up to that point has taught. With a catalyst on you the salve is
finished and stowed, and the next one starts from the herb.

The mortar and the pestle fill both hands: the weapon goes back in its
container first, the pestle is stowed for every fetch (the herb, the
water, the catalyst) and taken back for the crush. Everything comes
from the backpack or the profile's loot container by noun; nothing is
ever dropped. It stops at mind-lock (holding until the drain, `once`
exits), on `return`, on death or hostiles, when the herb, the water or
the book is not on you, and when a CRUSH answers nothing the table
knows three times. ;train runs it as a task (skills: ["Alchemy"],
return_word "return"). A work order (ASK LANSHADO FOR EASY REMEDIES
WORK: "an order for some blister cream. I need 2 stacks (5 uses each)
finely-crafted ... due in 65 roisaen", captured 2026-09-22) waits on
the catalyst too.
Stop with:  ;stop remedies, or ;remedies return.
"""

from client.game import flight, probe
from client.game.loop import danger, ensure_mindstate, mindstate, pause, wants_stop
from client.game.probe import classify
from client.game.remedies import (
    CHAPTER,
    CRUSH_OUTCOMES,
    POURED,
    STUDIED,
    TOO_HARD,
    crush_command,
    herb_for,
    page_for,
    parse_args,
)

SKILL = "Alchemy"
RESUME_BELOW = 28
LOCK_POLL = 30
COLLECT_SECONDS = 3
TAIL_SECONDS = 1.5
MAX_CRUSHES = 400  # the fuse under the loop
MISSES = 3  # unrecognized CRUSH answers before the run ends


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
    """The weapon into its container, anything else STOWed: the mortar
    and the pestle want both hands. Never DROP."""
    weapon = (profile.get("weapon") or "").lower()
    container = profile.get("weapon_container") or ""
    for noun in hand_nouns(s):
        if noun == weapon and container:
            ask(s, f"put my {noun} in my {container}")
        else:
            ask(s, f"stow my {noun}")


def redraw(s, profile):
    weapon = profile.get("weapon") or ""
    container = profile.get("weapon_container") or ""
    if weapon and container:
        ask(s, f"get my {weapon} from my {container}")


def study(s, salve):
    """The page STUDied once per run: the book out, turned to the
    chapter and page, studied, stowed. False when the book is not on
    you or the game did not say it is ready."""
    answer = ask(s, "get my book")
    if "referring" in answer or "could not find" in answer:
        s.echo("remedies: no remedies book on you — stopping")
        return False
    ask(s, f"turn my book to chapter {CHAPTER}")
    ask(s, f"turn my book to page {page_for(salve)}")
    answer = ask(s, "study my book")
    s.waitrt()
    ask(s, "stow my book")
    if any(word in answer for word in TOO_HARD):
        s.echo(
            f"remedies: the {salve} salve is beyond the ranks — mishaps ahead, the crushes still teach"
        )
    if not any(word in answer for word in STUDIED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: STUDY answered {first!r} — stopping")
        return False
    return True


def fetch_into_mortar(s, noun, what):
    """The pestle down, `noun` GOT and PUT in the mortar, the pestle
    back up. False when the game finds no such thing on you."""
    ask(s, "stow my pestle")
    answer = ask(s, f"get my {noun}")
    if "referring" in answer or "could not find" in answer:
        s.echo(f"remedies: no {noun} on you — the {what} is missing, stopping")
        ask(s, "get my pestle")
        return False
    verb = "pour" if what == "water" else "put"
    answer = ask(s, f"{verb} my {noun} in my mortar")
    if what == "water" and not any(word in answer for word in POURED):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"remedies: the pour answered {first!r}")
    if what == "water":
        ask(s, f"stow my {noun}")
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


def run(s, options):
    profile = profile_of(s)
    salve = options["salve"]
    herb = herb_for(salve)
    catalyst = str(profile.get("catalyst") or "").strip()
    value = ensure_mindstate(s, SKILL, ask)
    if value is None:
        s.echo(f"remedies: EXP shows no {SKILL} — nothing to train")
        return
    clear_hands(s, profile)
    if not study(s, salve):
        redraw(s, profile)
        return
    for tool in ("mortar", "pestle"):
        answer = ask(s, f"get my {tool}")
        if "referring" in answer or "could not find" in answer:
            s.echo(f"remedies: no {tool} on you — stopping")
            redraw(s, profile)
            return
    s.echo(f"remedies: {salve} salve from dried {herb} — {SKILL} {value}/34")
    started = False  # a salve in progress in the mortar
    salves = 0
    misses = 0
    reason = "the crush fuse"
    for _ in range(MAX_CRUSHES):
        if why := danger(s):
            reason = f"{why}"
            break
        if wants_stop(s):
            reason = "stopping as asked"
            break
        value = mindstate(s, SKILL)
        if value is not None and value >= options["until"]:
            if options["once"]:
                reason = f"{SKILL} at {value}/34 — done"
                break
            if not hold_at_lock(s, options["until"]):
                reason = "stopping"
                break
        answer = ask(s, crush_command(herb, started))
        s.waitrt()
        outcome = classify(answer, CRUSH_OUTCOMES)
        if outcome == "crushed":
            started = True
            misses = 0
        elif outcome == "need water":
            started = True
            if not fetch_into_mortar(s, "water", "water"):
                reason = "out of water"
                break
        elif outcome == "need catalyst":
            started = True
            if not catalyst:
                reason = (
                    "the salve wants a catalyst and the profile names none — it "
                    "stays unfinished in the mortar for the next run"
                )
                break
            if not fetch_into_mortar(s, catalyst, "catalyst"):
                reason = "out of catalyst"
                break
        elif outcome == "finished":
            salves += 1
            started = False
            s.echo(f"remedies: {salve} salve finished ({salves})")
            ask(s, "stow my pestle")
            ask(s, "get my salve")
            ask(s, "stow my salve")
            ask(s, "get my pestle")
            if options["count"] and salves >= options["count"]:
                reason = f"{salves} salve(s) made"
                break
            if not fetch_into_mortar(s, herb, "herb"):
                reason = f"out of dried {herb}"
                break
        elif outcome == "missing" and not started:
            # Nothing in the mortar yet: the herb goes in first.
            if not fetch_into_mortar(s, herb, "herb"):
                reason = f"out of dried {herb}"
                break
        elif outcome == "no instructions":
            reason = "the game wants the page studied — STUDY refused or lost"
            break
        elif outcome == "free hand":
            ask(s, "stow my pestle")
            ask(s, "get my pestle")
        else:
            misses += 1
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"remedies: unrecognized CRUSH answer {first!r} — please report it")
            if misses >= MISSES:
                reason = f"{MISSES} unrecognized answers"
                break
    s.echo(f"remedies: {reason} — {salves} salve(s), {SKILL} {mindstate(s, SKILL)}/34")
    ask(s, "stow my pestle")
    ask(s, "stow my mortar")
    redraw(s, profile)
    if "hostiles" in reason:
        flight.react(s, "remedies")


def main(s):
    run(s, parse_args(s.args or []))
