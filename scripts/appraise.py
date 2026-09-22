"""Train Appraisal by appraising your own things:  ;appraise

    ;appraise                      APPRAISE each item on you in turn, quick, until Appraisal mind-locks
    ;appraise items=pouch,shield   items of your own instead of the profile's `appraisal_items` or the inventory
    ;appraise careful              full appraisals instead of QUICK (a longer roundtime, the same learning)
    ;appraise until=30             stop at that mindstate instead of 34
    ;appraise once                 exit at mind-lock instead of holding for the drain
    ;appraise return               (typed while it runs) finish the appraisal in hand and end

Every APPRAISE of an item on you teaches Appraisal, at any rank; a
valuable or many-part item — a gem pouch, a bundle, a weapon, armor —
teaches most, else the whole inventory does (Elanthipedia: Appraisal
skill, Appraise command; client/game/appraisal.py is the model, after
dr-scripts' appraisal.lic, which cycles the same way). The rotation is
the profile's `appraisal_items` when set, else everything worn or held
as the parser's last INV LIST saw it (the autostarted ;sheet takes one
at login; ;sheet inv refreshes it), a pouch and a bundle first. Each
item is APPRAISEd QUICK and the roundtime waited out; one the game
cannot find or will not appraise is dropped from the rotation and said
once, and an empty rotation ends the run. The mindstate is the exp
window's (EXP APPRAISAL when it does not list the skill). At mind-lock
the script holds until Appraisal drains below 28, then goes round
again; `once` exits at the lock. ;train runs it as a task (skills:
["Appraisal"], return_word "return"). It stops on death and on
hostiles in the room. Creatures are never appraised (they teach
nothing below 76 ranks) and other players never (uncouth).
The answers' wordings are uncaptured (2026-09-22): the first answer of
a run is echoed as "appraise: <item> answered ..." so they become
fixtures — report them.
Stop with:  ;stop appraise, or ;appraise return.
"""

from client.game import probe
from client.game import flight
from client.game.appraisal import (
    NOT_FOUND,
    REFUSED,
    appraise_command,
    parse_args,
    rotation,
)
from client.game.loop import danger, ensure_mindstate, mindstate, pause, wants_stop

SKILL = "Appraisal"
MIND_LOCK = 34
RESUME_BELOW = 28  # resume once enough has drained to be worth a lap
LOCK_POLL = 30
COLLECT_SECONDS = 2
TAIL_SECONDS = 0.5
MAX_LAPS = 400  # the fuse under the loop


def ask(s, command):
    """The game's answer to one command, lower-cased."""
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS).lower()


def profile_items(s):
    """The profile's `appraisal_items`, or []."""
    name = getattr(s.state, "name", None)
    if not name:
        return []
    from client.game.profile import load_profile

    return list(load_profile(name).get("appraisal_items") or [])


def hold_at_lock(s, until):
    """Wait at mind-lock until the mindstate drains below RESUME_BELOW
    (or the target, when lower); False when the wait is interrupted."""
    s.echo(f"appraise: {SKILL} mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        value = mindstate(s, SKILL)
        if value is not None and value <= floor:
            s.echo(f"appraise: drained to {value}/34 — appraising again")
            return True


def appraise(s, noun, careful):
    """One APPRAISE, the roundtime waited out: "ok", "not found" or
    "refused"."""
    answer = ask(s, appraise_command(noun, careful))
    s.waitrt()
    if any(word in answer for word in NOT_FOUND):
        return "not found", answer
    if any(word in answer for word in REFUSED):
        return "refused", answer
    return "ok", answer


def run(s, options):
    value = ensure_mindstate(s, SKILL, ask)
    if value is None:
        s.echo(f"appraise: EXP shows no {SKILL} — nothing to train")
        return
    items = rotation(
        getattr(s.state, "possessions", None),
        options["items"] or profile_items(s),
    )
    if not items:
        s.echo(
            "appraise: nothing to appraise — items=<noun,noun>, the profile's "
            "appraisal_items, or ;sheet inv first so the inventory is known"
        )
        return
    s.echo(
        f"appraise: {len(items)} item(s) in rotation ({', '.join(items)}) — "
        f"{SKILL} {value}/34"
    )
    reported = False
    for _ in range(MAX_LAPS):
        for noun in list(items):
            reason = danger(s)
            if reason:
                s.echo(f"appraise: {reason} — stopping")
                if "hostiles" in reason:
                    flight.react(s, "appraise")
                return
            if wants_stop(s):
                s.echo("appraise: stopping as asked")
                return
            value = mindstate(s, SKILL)
            if value is not None and value >= options["until"]:
                if options["once"]:
                    s.echo(f"appraise: {SKILL} at {value}/34 — done")
                    return
                if not hold_at_lock(s, options["until"]):
                    s.echo("appraise: stopping")
                    return
            outcome, answer = appraise(s, noun, options["careful"])
            if outcome != "ok":
                items.remove(noun)
                s.echo(
                    f"appraise: the game {'finds no' if outcome == 'not found' else 'will not appraise the'} "
                    f"{noun} — out of the rotation ({len(items)} left)"
                )
                if not items:
                    s.echo("appraise: nothing left to appraise — stopping")
                    return
                continue
            if not reported:
                reported = True
                first = (answer.strip().splitlines() or ["(silence)"])[0]
                s.echo(f"appraise: {noun} answered {first!r}")
    s.echo(f"appraise: {MAX_LAPS} laps — stopping")


def main(s):
    run(s, parse_args(s.args or []))
