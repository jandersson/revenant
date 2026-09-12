"""Train a character by plan — tasks until their skills fill, then rest:  ;train

The orchestrator: a loop over your training plan
(~/.revenant/training/<name>.json — ;train init writes a starter,
;train plan shows it, docs/training.md explains every key). Each task ties skills to what trains them — a bundled
script (;athletics, ;hunt) started and watched, or a plain command
loop (play my flute) run in place — and the loop runs the tasks whose
skills sit below the target mindstate, each until its skills reach
the target or its time budget runs out. When every task is trained it
walks to a safe room (several rotate, rest by rest), sends the rest
commands (sit), and holds until every trained skill has drained to
the rest floor — that is when the pool converts to ranks — then
starts the next cycle. Death ends the loop (deathwatch has it); a
task's own script handles its own danger, and hostiles at the safe
room send the rest to the next safe room.

    ;train           run the plan until stopped (or its cycles run out)
    ;train once      one train-rest cycle
    ;train plan      print the plan it would run
    ;train status    the tracked skills' mindstates (also while running)
    ;train init      write the starter plan (init force overwrites)

While it runs:  ;train skip  ends the current task (or the rest),
;train rest  stops training and rests now. Stop with:  ;stop train —
a task's script stops with it. A script task ends early with the
task's return word when it has one (hunt's ;hunt return finishes
the kill and walks home), killed after the grace otherwise; scripts that
exit on their own (an empty hunting ground) end the task for this
cycle and are not restarted until the next one. The loop is
scaffolding for training scripts still to be written: a task is one
line of JSON, and the plan is the only place a character's routine
lives.
"""

import time

from client.game.training import (
    describe,
    load_plan,
    next_task,
    plan_path,
    rested,
    safe_room,
    satisfied,
    save_plan,
    starter_plan,
    status_lines,
    task_minutes,
    task_mindstates,
    task_target,
    validate,
)

clock = time.monotonic  # tests replace it
EXIT_WAIT = 10  # seconds a killed task script gets to wind down
WORDS = ("skip", "rest", "status")


def experience(s):
    return dict(getattr(s.state, "experience", None) or {})


def hostiles_present(state):
    return bool(getattr(state, "hostiles", None))


def user_word(s, plan):
    """The last control word typed at the running script (;train skip,
    ;train rest); status is answered here and not returned."""
    word = None
    while (line := s.command(timeout=0)) is not None:
        candidate = line.strip().lower()
        if candidate == "status":
            for text in status_lines(plan, experience(s)):
                s.echo(text)
        elif candidate in WORDS:
            word = candidate
        else:
            s.echo(f"train: while running I understand ;train {' / '.join(WORDS)}")
    return word


def send_each(s, commands):
    for command in commands:
        s.put(command)
        s.waitrt()


def progress(plan, task, experience_now):
    states = task_mindstates(task, experience_now)
    if not states:
        return "no skills tracked"
    target = task_target(plan, task)
    return ", ".join(f"{skill} {state}/{target}" for skill, state in states.items())


def stop_script(s, task):
    """End a task's script: the return word first, when it has one,
    then the kill once the grace runs out; wait for the thread to go."""
    name = task["script"]
    if not s.is_running(name):
        return
    if task["return_word"]:
        s.tell(name, task["return_word"])
        s.echo(f"train: told ;{name} {task['return_word']} — waiting for it to finish")
        deadline = clock() + task["return_grace"]
        while s.is_running(name) and clock() < deadline:
            s.sleep(1)
    if s.is_running(name):
        s.kill(name)
    deadline = clock() + EXIT_WAIT
    while s.is_running(name) and clock() < deadline:
        s.sleep(0.25)


def watch(s, plan, task, deadline, running=None):
    """The shared loop of both task kinds: why the task ends ("dead",
    "target", "timeout", "skip", "rest", "ended"), or None to carry
    on. running() says whether a script task's script is still up."""
    if s.dead:
        return "dead"
    if running is not None and not running():
        return "ended"
    if satisfied(plan, task, experience(s)):
        return "target"
    if deadline is not None and clock() >= deadline:
        return "timeout"
    return user_word(s, plan)


def run_script_task(s, plan, task, deadline):
    name = task["script"]
    if not s.run(name, task["args"]):
        s.echo(f"train: could not start ;{name} — skipping {task['name']}")
        return "skipped"
    try:
        while True:
            reason = watch(s, plan, task, deadline, running=lambda: s.is_running(name))
            if reason in ("ended", "dead"):
                return reason  # nothing to wind down, or no time to
            if reason is not None:
                stop_script(s, task)
                return reason
            s.sleep(plan["poll"])
    finally:
        if s.is_running(name):
            s.kill(name)  # ;stop train (and death) take the child down too


def run_command_task(s, plan, task, deadline):
    commands = task["commands"]
    index = 0
    while True:
        reason = watch(s, plan, task, deadline)
        if reason is not None:
            return reason
        s.put(commands[index % len(commands)])
        index += 1
        s.waitrt()
        s.sleep(task["pace"])


ENDINGS = {
    "target": "at target",
    "timeout": "time budget spent",
    "ended": "its script ended on its own",
    "skip": "skipped",
    "rest": "resting on request",
    "skipped": "could not start",
}


def run_task(s, plan, task):
    """One task, setup to teardown; why it ended (watch's reasons)."""
    budget = task_minutes(plan, task)
    deadline = clock() + budget * 60 if budget else None
    limit = f"up to {budget} min" if budget else "no time limit"
    s.echo(f"train: {task['name']} — {progress(plan, task, experience(s))} ({limit})")
    send_each(s, task["setup"])
    if task["script"]:
        reason = run_script_task(s, plan, task, deadline)
    else:
        reason = run_command_task(s, plan, task, deadline)
    if reason != "dead":
        send_each(s, task["teardown"])
        s.echo(
            f"train: {task['name']} {ENDINGS.get(reason, reason)} — "
            f"{progress(plan, task, experience(s))}"
        )
    return reason


def train_cycle(s, plan):
    """Every task once, in the plan's order, skipping the ones already
    at target: "trained" when the cycle is complete, "dead" otherwise."""
    spent = set()
    while True:
        if s.dead:
            return "dead"
        task = next_task(plan, experience(s), spent)
        if task is None:
            return "trained"
        reason = run_task(s, plan, task)
        if reason == "dead":
            return "dead"
        spent.add(task["name"])
        if reason == "rest":
            return "trained"


def go_to(s, db, walk, target):
    """Walk to a ;go2 target; True on arrival."""
    goals = db.resolve(target)
    if not goals:
        s.echo(f"train: nothing in the map matches safe room {target!r}")
        return False
    return walk(s, db, goals, describe=repr(target))


def rest(s, plan, db, walk, index):
    """The rest: to the index-th safe room, the rest commands, then hold
    until every trained skill has drained (or the cap). Returns the
    next rest's index, or None on death."""
    room = safe_room(plan, index)
    if room is not None:
        go_to(s, db, walk, room)
        index += 1
    send_each(s, plan["rest_commands"])
    cap = plan["rest_minutes"]
    until = f"every trained skill is at {plan['rest_until']}/34 or below"
    s.echo(f"train: resting until {until}" + (f" (at most {cap} min)" if cap else ""))
    started = clock()
    while True:
        if s.dead:
            return None
        if rested(plan, experience(s)):
            s.echo("train: rested — the pool has drained")
            return index
        if cap and clock() - started >= cap * 60:
            s.echo(f"train: {cap} minutes of rest — moving on")
            return index
        if user_word(s, plan) == "skip":
            s.echo("train: rest skipped")
            return index
        if hostiles_present(s.state):
            if len(plan["safe_rooms"]) > 1:
                s.echo("train: hostiles at the safe room — moving to the next one")
                exits = list(getattr(s.state, "compass", None) or [])
                s.put("retreat")
                s.put("retreat")
                s.put(exits[0] if exits else "out")
                s.waitrt()
                go_to(s, db, walk, safe_room(plan, index))
                index += 1
                send_each(s, plan["rest_commands"])
            else:
                s.echo("train: hostiles at the safe room — intervene, I only rest here")
        s.sleep(plan["poll"])


def run(s, plan, cycles, db=None, walk=None):
    """The loop: train, rest, repeat cycles times (0 = until stopped)."""
    cycle = 0
    index = 0
    while not cycles or cycle < cycles:
        cycle += 1
        s.echo(f"train: cycle {cycle} — training")
        if train_cycle(s, plan) == "dead":
            s.echo("train: you are dead — stopping; deathwatch has it")
            return
        index = rest(s, plan, db, walk, index)
        if index is None:
            s.echo("train: you are dead — stopping; deathwatch has it")
            return
    s.echo(f"train: {cycle} cycle(s) done")


def travel_engine(s, plan):
    """The map and walker, loaded only when the plan names a safe room."""
    if not plan["safe_rooms"]:
        return None, None
    from client.game.mapdb import MapDB, download, mapdb_path
    from client.game.walker import walk

    if not mapdb_path().is_file():
        s.echo("downloading map database (first use, ~13MB) ...")
        download()
    return MapDB.load(), walk


def init(s, name, force):
    path = plan_path(name)
    if path.is_file() and not force:
        s.echo(f"train: {path} exists — edit it, or ;train init force to overwrite")
        return
    save_plan(name, starter_plan(name))
    s.echo(f"train: starter plan written to {path} — edit it, then ;train plan")


def main(s):
    name = getattr(s.state, "name", None) or ""
    word = s.args[0].lower() if s.args else ""
    if word == "init":
        init(s, name, force=len(s.args) > 1 and s.args[1].lower() == "force")
        return
    plan = load_plan(name)
    if word == "plan":
        s.echo(f"train: plan for {name or 'an unnamed character'} ({plan_path(name)})")
        for line in describe(plan):
            s.echo(f"  {line}")
        return
    if word == "status":
        for line in status_lines(plan, experience(s)):
            s.echo(line)
        return
    problems = validate(plan)
    if problems:
        for problem in problems:
            s.echo(f"train: {problem}")
        s.echo(f"train: fix {plan_path(name)} and try again")
        return
    if not plan["tasks"]:
        s.echo(f"train: no tasks in {plan_path(name)} — ;train init writes a starter")
        return
    cycles = 1 if word == "once" else plan["cycles"]
    db, walk = travel_engine(s, plan)
    run(s, plan, cycles, db=db, walk=walk)
