"""The loop every skill trainer runs (#407): danger, a typed return that
finishes the step in hand, the mind-lock gate and the hold — the script
supplies its step and its words.

    def step(s):                     # one unit of training
        ...                          # None to go on, a reason (text) to end
    why = trainer.train(s, "mechlore", "Mechanical Lore", step, again="braiding again")

train() ends with the reason, said once the common way: "you are dead"
or "hostiles in the room" (loop.danger's words, flight.react first for
the hostiles), "return" (a typed `;<name> return`: "returning as
asked"), "locked" (`once=True` and the skill at `until`), "no skill"
(EXP shows none), or whatever the step returned (said as "<prefix>:
<reason> — stopping"). `finish(s, why)` runs at every end, a `;stop`
included (a finally), for the stow or the walk home. The interludes
run at every safe point, since loop.wants_stop is one.

hold_at_lock() is the hold alone, for a loop not yet on train(): nine
scripts (attune, cast, remedies, appraise, boxes, research,
scholarship, listen, perform) said the same thing nine ways. At
`until`, wait in LOCK_POLL slices until a skill drains to RESUME_BELOW
(or under the target, when lower); False when a return or a danger
interrupts. Several skills (a cast rotation) lock when every one the
window lists is at `until`, and drain when any one is back under the
floor.
"""

from client.game import act, flight
from client.game.loop import danger, ensure_mindstate, mindstate, pause, wants_stop

MIND_LOCK = 34  # mindstate 34/34: nothing more fits
RESUME_BELOW = 28  # resume once enough has drained to be worth a round
LOCK_POLL = 30  # seconds between looks while locked


def _skills(skills):
    """The skills as a list: one name, several, or a callable giving
    the current set (;cast's watched skills grow after the first DISCERN
    and shrink when a buff or POWER is dropped for the run; the gate
    reads it afresh every round)."""
    if callable(skills):
        skills = skills()
    return [skills] if isinstance(skills, str) else list(skills)


def mindstates(s, skills):
    """{skill: mindstate} for the skills the exp window lists, in order."""
    values = {}
    for skill in _skills(skills):
        value = mindstate(s, skill)
        if value is not None:
            values[skill] = value
    return values


def locked(s, skills, until=MIND_LOCK):
    """True when every skill the window lists is at `until` or past it,
    and it lists at least one."""
    values = mindstates(s, skills)
    return bool(values) and all(value >= until for value in values.values())


def drained(s, skills, floor):
    """(skill, value) of the first skill at or under `floor`, else None."""
    for skill, value in mindstates(s, skills).items():
        if value <= floor:
            return skill, value
    return None


def hold_at_lock(
    s,
    prefix,
    skills,
    until=MIND_LOCK,
    again="training again",
    tick=None,
    resume_below=None,
    poll=None,
):
    """Wait at mind-lock until a skill drains to RESUME_BELOW (or under
    `until`, when lower), `tick()` run between looks; True then, False
    when a typed return or a danger interrupted the wait."""
    skills = _skills(skills)
    resume_below = RESUME_BELOW if resume_below is None else resume_below
    poll = LOCK_POLL if poll is None else poll
    names = ", ".join(skills)
    what = "one drains" if len(skills) > 1 else "it drains"
    s.echo(f"{prefix}: {names} mind-locked ({until}/34) — holding until {what}")
    floor = min(resume_below, until - 1)
    while True:
        if not pause(s, poll):
            return False
        low = drained(s, skills, floor)
        if low is not None:
            skill, value = low
            who = f"{skill} drained" if len(skills) > 1 else "drained"
            s.echo(f"{prefix}: {who} to {value}/34 — {again}")
            return True
        if tick is not None:
            tick()


def interrupted(s, prefix, after_hold=False):
    """Why the loop ends now, said, or None: a danger (flight.react for
    hostiles), else a typed return. After an interrupted hold the
    return word was read by the pause already, so no danger means the
    return."""
    reason = danger(s)
    if reason:
        s.echo(f"{prefix}: {reason} — stopping")
        if "hostiles" in reason:
            flight.react(s, prefix)
        return reason
    if after_hold or wants_stop(s):
        s.echo(f"{prefix}: returning as asked")
        return "return"
    return None


def train(
    s,
    prefix,
    skills,
    step,
    until=MIND_LOCK,
    once=False,
    again="training again",
    finish=None,
    tick=None,
    ask=None,
    ensure=True,
):
    """Run `step(s)` until the skill locks (then hold, or end with
    `once`), a typed return, a death or hostiles, or the step returns a
    reason; the reason returned, `finish(s, why)` run at every end.
    `skills` may be a callable for a set that changes during the run
    (read afresh every round); `ensure=False` skips the EXP check for a
    script that trains a skill the window may not list yet (a
    Barbarian's research teaches one he has no ranks in)."""
    ask = ask or act.ask
    why = None
    try:
        if ensure:
            for skill in _skills(skills):
                if ensure_mindstate(s, skill, ask) is None:
                    s.echo(f"{prefix}: EXP shows no {skill} — nothing to train")
                    why = "no skill"
                    return why
        while why is None:
            why = interrupted(s, prefix)
            if why:
                break
            current = _skills(skills)
            if locked(s, current, until):
                if once:
                    s.echo(f"{prefix}: {', '.join(current)} at {until}/34 — done")
                    why = "locked"
                    break
                if not hold_at_lock(s, prefix, current, until, again=again, tick=tick):
                    why = interrupted(s, prefix, after_hold=True)
                continue
            why = step(s)
            if why:
                s.echo(f"{prefix}: {why} — stopping")
    finally:
        if finish is not None:
            finish(s, why)
    return why
