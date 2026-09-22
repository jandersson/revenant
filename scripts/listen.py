"""Listen to another character's class until the skill mind-locks:  ;listen

    ;listen masah                  LISTEN TO that teacher; the skill is read off the class
    ;listen masah scholarship      hold on that skill's mindstate instead of the class's
    ;listen masah until=30         end at that mindstate instead of 34
    ;listen masah once             exit at mind-lock instead of holding for the drain
    ;listen masah observe          LISTEN ... OBSERVE: weighted toward Scholarship
    ;listen return                 (typed while it runs) STOP LISTENING and end

A class is the teacher's TEACH <skill> TO <you> (`;teach`) and your
LISTEN TO <teacher> — "You begin to listen to Masah teach the
Scholarship skill." (captured 2026-09-22) — and it teaches the skill
and Scholarship both until one of you moves. This script joins the
class, reads the skill off the answer, and holds: the exp window's
mindstate polled, the lock held until it drains (`once` exits), the
class joined again when it ended (the teacher moved and offered
anew; `;teach` re-offers on its own), up to three refusals in a row.
It ends on `return` (STOP LISTENING), on death or hostiles (the
shared escape), or when no class is offered. `;train` runs it as a
task: `{"skills": ["Scholarship"], "script": "listen", "args":
["masah"], "return_word": "return"}` — the rest's walk ends the
class, the teacher's `;teach` offers it again on return. The wordings
for a class ending on the student's side are uncaptured and read by
shape. Elanthipedia: Listen command. Stop with:  ;stop listen, or
;listen return.
"""

from client.game import flight, probe
from client.game.loop import danger, ensure_mindstate, mindstate, pause
from client.game.probe import classify
from client.game.teaching import (
    CLASS_ENDED,
    LISTEN_OUTCOMES,
    listen_command,
    parse_listen_args,
    taught_skill,
)

COLLECT_SECONDS = 2
TAIL_SECONDS = 1
POLL = 10  # seconds between mindstate looks
REJOIN_AFTER = 15  # seconds after the class ended before LISTENing again
REFUSALS = 3  # LISTENs answered "no class" in a row before the run ends
RESUME_BELOW = 28
LOCK_POLL = 30


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def join(s, options):
    """LISTEN once; ("listening", skill) when in the class, else
    (the failure, None)."""
    answer = ask(s, listen_command(options["teacher"], options["observe"]))
    outcome = classify(answer.lower(), LISTEN_OUTCOMES)
    if outcome in ("listening", "already"):
        return "listening", taught_skill(answer)
    first = (answer.strip().splitlines() or ["(silence)"])[0]
    if outcome is None:
        s.echo(f"listen: LISTEN answered {first!r} — please report it")
        return "unknown", None
    s.echo(f"listen: {first}")
    return outcome, None


def hold_at_lock(s, skill, until):
    s.echo(f"listen: {skill} mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        value = mindstate(s, skill)
        if value is not None and value <= floor:
            s.echo(f"listen: drained to {value}/34 — listening on")
            return True


def leave(s, why):
    ask(s, "stop listening")
    s.echo(f"listen: {why}")


def run(s, options):
    if not options["teacher"]:
        s.echo("listen: whose class? ;listen <teacher> [skill]")
        return
    outcome, skill = join(s, options)
    if outcome != "listening":
        s.echo("listen: no class — stopping")
        return
    skill = options["skill"] or skill or "Scholarship"
    value = ensure_mindstate(s, skill, lambda h, c: ask(h, c))
    if value is None:
        s.echo(f"listen: EXP shows no {skill} — nothing to train")
        ask(s, "stop listening")
        return
    s.echo(f"listen: in {options['teacher']}'s class — {skill} {value}/34")
    s.flag("class ended", *CLASS_ENDED)
    refusals = 0
    retry = False  # a rejoin refused: try again next poll, no new line needed
    try:
        while True:
            if not pause(s, POLL):
                why = danger(s)
                if why:
                    leave(s, f"{why} — stopping")
                    if "hostiles" in why:
                        flight.react(s, "listen")
                    return
                leave(s, "stopping as asked")
                return
            value = mindstate(s, skill)
            if value is not None and value >= options["until"]:
                if options["once"]:
                    leave(s, f"{skill} at {value}/34 — done")
                    return
                if not hold_at_lock(s, skill, options["until"]):
                    leave(s, "stopping as asked")
                    return
            if s.flagged("class ended") or retry:
                if not retry:
                    s.echo(
                        f"listen: the class ended — listening again in {REJOIN_AFTER} s"
                    )
                if not pause(s, REJOIN_AFTER):
                    leave(s, "stopping as asked")
                    return
                outcome, _ = join(s, options)
                if outcome == "listening":
                    refusals, retry = 0, False
                    continue
                refusals += 1
                if refusals >= REFUSALS:
                    s.echo(f"listen: no class offered {REFUSALS} times — stopping")
                    return
                retry = True
    finally:
        s.unflag("class ended")


def main(s):
    run(s, parse_listen_args(s.args or []))
