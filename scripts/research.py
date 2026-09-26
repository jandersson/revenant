"""Train a Barbarian's magic skills by MEDITATE RESEARCH:  ;research

    ;research                       Augmentation, Warding and Utility in turn, the emptiest pool first, until all three mind-lock
    ;research augmentation warding  those skills only (util, aug, ward will do)
    ;research augmentation=buffalo  research that ability for the skill instead of the default
    ;research gap=90                seconds from one research to the next (60)
    ;research until=30              stop at that mindstate instead of 34
    ;research once                  exit when every skill is there instead of holding for the drain
    ;research return                (typed while it runs) finish the research in hand and end

MEDITATE RESEARCH <ability> teaches the skill of that ability whether or
not the Barbarian knows it, and Inner Fire beside it, about a minute
apart, with a roundtime of 6-10 s and no ability slot spent — the Barbarian's magic research
(Elanthipedia: Barbarian new player guide, Meditations; the model and
its assumptions are client/game/research.py and docs/barbarian.md,
#327). The defaults are
dr-scripts' combat-trainer.lic's: MONKEY for Augmentation, TURTLE for
Warding, PREDICTION for Utility. Debilitation cannot be researched —
roars at a foe teach it — so it is not offered.

Each round researches the chosen skill whose pool is emptiest (the exp
window's mindstate; EXP <skill> when the window lacks it, and a skill
the game shows no ranks in yet counts as empty) — on a tie the one
researched longest ago, since at low ranks a research's dabbling has
drained before the next and all three sit at 0 — waits the roundtime
out, then waits the rest of the gap. A skill the exp window does not
move after its research is read with EXP <skill> instead, said once
per skill: the window never shows a Barbarian's Utility, which moved
0.15 to 0.30 % under PREDICTION with no line in it (#327), and pushes
a skill's line only when its text changes — a Warding still dabbling
after a research got none. A name the game does not know
("What did you want to research") drops that skill for the run; a
non-Barbarian's "trouble concentrating" ends it. At mind-lock on every
skill the script holds until one drains below 28, then goes on; `once`
exits instead. ;train runs it as a task (skills: ["Augmentation",
"Warding", "Utility"], return_word "return"). It stops on death and on
hostiles in the room, getting away first.
The begun answer was captured on the first run (2026-09-26); the
unknown-name and non-Barbarian answers are still dr-scripts' and the
wiki's, so every answer outside the table is echoed as "research:
<ability> answered ..." for a fixture.
Stop with:  ;stop research, or ;research return.
"""

from time import monotonic

from client.game import flight, probe
from client.game.loop import (
    danger,
    ensure_mindstate,
    exp_entry,
    mindstate,
    pause,
    read_exp,
    wants_stop,
)
from client.game.research import classify, next_skill, parse_args, research_command

RESUME_BELOW = 28  # resume once enough has drained to be worth a round
LOCK_POLL = 30
COLLECT_SECONDS = 2
TAIL_SECONDS = 0.5
MAX_ROUNDS = 2000  # the fuse under the loop
clock = monotonic


def ask(s, command):
    """The game's answer to one command."""
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def mindstates(s, skills):
    """{skill: mindstate or None} in the order given, from the exp window."""
    return {skill: mindstate(s, skill) for skill in skills}


def hold_at_lock(s, skills, until):
    """Wait with every skill at `until` until one drains below
    RESUME_BELOW (or the target, when lower); False when the wait is
    interrupted."""
    s.echo(f"research: {', '.join(skills)} at {until}/34 — holding until one drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        values = mindstates(s, skills)
        drained = [skill for skill, value in values.items() if (value or 0) <= floor]
        if drained:
            s.echo(
                f"research: {drained[0]} drained to {values[drained[0]] or 0}/34 — researching again"
            )
            return True


def research(s, ability):
    """One MEDITATE RESEARCH, the roundtime waited out: (outcome, answer)."""
    answer = ask(s, research_command(ability))
    s.waitrt()
    return classify(answer), answer


def first_line(answer):
    return (answer.strip().splitlines() or ["(silence)"])[0]


def run(s, options):
    abilities = dict(options["abilities"])
    until = options["until"]
    for skill in abilities:
        if ensure_mindstate(s, skill, ask) is None:
            s.echo(f"research: EXP shows no {skill} yet — its pool counts as empty")
    s.echo(
        "research: "
        + ", ".join(f"{skill} by {ability}" for skill, ability in abilities.items())
        + f", {options['gap']} s apart, until {until}/34"
    )
    last = None
    researched = {}  # skill: the round it was last researched in
    silent = set()  # skills the exp window did not move after a research
    for round_number in range(MAX_ROUNDS):
        reason = danger(s)
        if reason:
            s.echo(f"research: {reason} — stopping")
            if "hostiles" in reason:
                flight.react(s, "research")
            return
        if wants_stop(s):
            s.echo("research: stopping as asked")
            return
        skill = next_skill(mindstates(s, abilities), until, researched)
        if skill is None:
            if options["once"]:
                s.echo(f"research: {', '.join(abilities)} at {until}/34 — done")
                return
            if not hold_at_lock(s, list(abilities), until):
                s.echo("research: stopping")
                return
            continue
        if last is not None:
            left = options["gap"] - (clock() - last)
            if left > 0 and not pause(s, left):
                s.echo("research: stopping")
                return
        last = clock()
        researched[skill] = round_number
        ability = abilities[skill]
        before = exp_entry(s, skill)
        outcome, answer = research(s, ability)
        if outcome == "not a barbarian":
            s.echo(
                f"research: the game answered {first_line(answer)!r} — only a Barbarian researches this way"
            )
            return
        if outcome == "unknown":
            del abilities[skill]
            s.echo(
                f"research: the game knows no ability {ability!r} — {skill} is out of "
                f"the run ({skill.lower()}=<ability> names another)"
            )
            if not abilities:
                s.echo("research: nothing left to research — stopping")
                return
            continue
        if outcome is None:
            s.echo(f"research: {ability} answered {first_line(answer)!r}")
        if exp_entry(s, skill) == before:
            # The window said nothing of the skill: EXP says it (#327).
            read_exp(s, skill, ask)
            if skill not in silent:
                silent.add(skill)
                s.echo(
                    f"research: the exp window did not move {skill} after its "
                    f"research — reading EXP {skill.upper()} whenever it stays silent"
                )
    s.echo(f"research: {MAX_ROUNDS} rounds — stopping")


def main(s):
    run(s, parse_args(s.args or []))
