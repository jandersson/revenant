"""Train a character by plan — tasks until their skills fill, then rest:  ;train

    ;train               run the plan until stopped (or its `cycles` run out)
    ;train once          one train-rest cycle
    ;train task <name>   that one task, once, no rest (a helper's login and logout included)
    ;train plan          print the plan it would run
    ;train status        the tracked skills' mindstates (also while running)
    ;train init [force]  write the starter plan (force overwrites one)
    ;train skip          (typed while it runs) end the current task, or the rest
    ;train rest          (typed while it runs) stop training and rest now
    ;train return        (typed while it runs) the task's script gets its own return
                         word (;hunt finishes the kill, walks home); no task or rest follows
    ;stop train          quit at once; a task's script stops with it

What it does
  - Runs each task whose skills sit below the target mindstate, until they reach
    it or its time budget runs out: a bundled script, a command loop, or a helper's.
  - Rests in a safe room (several rotate) until every trained skill has drained
    to `rest_until`, when the pool converts to ranks, or `rest_minutes` pass (an
    hour by default); a skill the almanac refills meanwhile is not waited for.
  - `rest_mode: logout` logs out for the rest once its top-ups are done (or the
    cap hits); start ;train again at the next login.
  - Keeps the most skills moving: a task whose skills drain first trains again
    during the rest (`top_up`, once a rest).
  - In the rests: soul deeds when `soul` is on, stat points from the plan's `tdp` list,
    and, wounded, the vela'tohr plant in `plant_room` touched and rested beside.
  - The interludes (the profile's `almanac`, a typed `;break`) between tasks and in rests.
  - Hostiles at the rest send it to the next safe room, or next door.

When it stops
  - death, or a cycle in which no task trained
  - the game's maintenance shutdown within `shutdown_minutes`
  - the plan's `cycles` done, ;train return, or ;stop train
  - a logout rest's QUIT (`rest_mode: logout`)

The plan is ~/.revenant/training/<name>.yaml; docs/training.md explains every key.
"""

import sqlite3
import time

from client.game import act, almanac, drain, flight, helper, interlude, travel
from client.game.history import database_path

from client.game.training import (
    HUNT_RETURN_GRACE,
    describe,
    favors_cap,
    load_plan,
    next_task,
    plan_path,
    rest_cap,
    rested,
    safe_room,
    top_up_tasks,
    satisfied,
    save_plan,
    starter_plan,
    status_lines,
    task_minutes,
    task_mindstates,
    task_target,
    tracked_skills,
    validate,
)


# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Train a character by plan — tasks until their skills fill, then rest:  ;train

The orchestrator: a loop over your training plan
(~/.revenant/training/<name>.yaml — ;train init writes a starter,
;train plan shows it, docs/training.md explains every key). Each task ties skills to what trains them — a bundled
script (;athletics, ;hunt) started and watched, a plain command
loop (play my flute) run in place, or a helper's script alone (an
Empath's ;empath <you>, the task lasting while it runs; `when`
wounded skips it while the injuries panel is clean, `when` favors<10
skips it once the exp window's favors reach 10 — the ;favors task,
kept at the operator's cap of 10 rather than bought with LTB points,
2026-09-28) — and the loop runs the tasks whose
skills sit below the target mindstate, each until its skills reach
the target or its time budget runs out. When every task is trained it
walks to a safe room (several rotate, rest by rest), sends the rest
commands (sit), and holds until every trained skill has drained to
the rest floor — that is when the pool converts to ranks; a task
whose own skills all drain first trains again in the meantime
(`top_up`, on by default: eight of Cecil's skills sat empty for most
of a 107-minute rest, the operator, 2026-09-27) — then
starts the next cycle. A rest opens with the drain model's guess
at its length (client/game/drain.py, #300: the guild's skillset tiers
and the rates fitted from ;xp's rows); the exp window still ends it.
Death ends the loop (deathwatch has it); a
task's own script handles its own danger, and hostiles at the rest
send it to the next safe room — or, with one or none, out of the
room to rest next door, and after a few such moves the rest is given
up for the cycle (a rest among things biting you never drains, #182).

    ;train           run the plan until stopped (or its cycles run out)
    ;train once      one train-rest cycle
    ;train task <name>   that one task, once, no rest — a helper's login and logout included
    ;train plan      print the plan it would run
    ;train status    the tracked skills' mindstates (also while running)
    ;train init      write the starter plan (init force overwrites)

While it runs:  ;train skip  ends the current task (or the rest),
;train rest  stops training and rests now, ;train return  ends the
run gracefully — the task's script gets its own return word (;hunt
finishes the kill and walks home), and no task or rest follows (#338).
Stop with:  ;stop train — at once, and a task's script stops with it. A script task ends early with the
task's return word when it has one (hunt's ;hunt return finishes
the kill and walks home), killed after the grace otherwise; scripts that
exit on their own (a rung the map lost) end the task for this
cycle and are not restarted until the next one; a script gone within
seconds of starting is a failed start, and one that crashed is said
so with its error — a cycle in which no task trained stops the loop
rather than resting. The loop is
scaffolding for training scripts still to be written: a task is one
line of JSON, and the plan is the only place a character's routine
lives.
The game's maintenance announcement ("DragonRealms will be shutting
down in N minutes", the parser's `shutdown_at`) ends the run before
the link drops (#277, after lich-5's DRParser.shutting_down?): once
it is within the plan's `shutdown_minutes` (3), the task in hand gets
its return word — the hunt finishes the kill and walks home — a rest
ends, and ;train stops with a word to start it again after.
The rest's cap and the logout rest (#412, the operator, 2026-10-02): a
rest online burns the rested-experience bank (docs/experience.md) for
nothing new — the bank refills only offline, and the pools drain
either way — and the rest of 06:15 that day ran to 12:49 because the
almanac kept refilling Attunement, a skill the plan trained, before
it drained. So rest_minutes 0 is an hour (training.REST_CAP), a skill
the almanac fills during a rest (almanac.STUDIED from the rest's
start) is not waited for, and rest_mode "logout" sends QUIT once every
task with skills has had its top-up or the cap hits, never among
hostiles; the next login starts the plan from its first task, so the
resume is starting ;train (or autostarting it). Later a per-skill
scheduler replaces the cycle: a task runs when its own skills are
low, no global rest.
"""

clock = time.monotonic  # tests replace it
EXIT_WAIT = 10  # seconds a killed task script gets to wind down
QUICK_EXIT = 5  # a task script gone this soon after starting never got going
LEAVE_ATTEMPTS = 5  # rooms left for hostiles before a rest is given up (#182)
SOUL_DEEDS = ("badge", "tithe", "pray", "song")  # the order ;train runs them in a rest
SOUL_MINUTES = 12  # a deed's run, walk included, before train stops waiting
TDP_POINTS_PER_REST = 3  # stat points bought in one rest at most (#230)
TDP_MINUTES = 12  # one ;tdp run, the walk there and back included
INFO_SECONDS = 2  # INFO's answer window in the rest
INFO_TAIL = 0.5
WORDS = ("skip", "rest", "return", "status")
# rest()'s answer to a typed return: the run ends, no next cycle (#338).
RETURNED = "return"
# rest()'s answer after a logout rest's QUIT (#412): the link ends with it.
LOGGED_OUT = "logout"


def experience(s):
    return dict(getattr(s.state, "experience", None) or {})


def hostiles_present(state):
    return bool(getattr(state, "hostiles", None))


def crash_of(s, name):
    """How a task's script died, from the handle's crash record (#181);
    None on a clean exit or a handle without the record."""
    asking = getattr(s, "crashed", None)
    return asking(name) if callable(asking) else None


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


def flee(s):
    """The burst out of a room hostiles hold — client/game/flight.py's,
    shared with every trainer since #285: STAND, retreat twice, a
    compass exit, judged by the room changing, up to eight tries."""
    return flight.react(s, "train")


def progress(plan, task, experience_now):
    states = task_mindstates(task, experience_now)
    if not states:
        return "no skills tracked"
    target = task_target(plan, task)
    return ", ".join(f"{skill} {state}/{target}" for skill, state in states.items())


def stop_script(s, task):
    """End a task's script: the return word first, when it has one,
    then the kill once the grace runs out; wait for the thread to go.
    A hunt's grace is at least HUNT_RETURN_GRACE: it sells and banks
    on its way out."""
    name = task["script"]
    if not s.is_running(name):
        return
    if task["return_word"]:
        s.tell(name, task["return_word"])
        s.echo(f"train: told ;{name} {task['return_word']} — waiting for it to finish")
        grace = task["return_grace"]
        if name == "hunt":
            grace = max(grace, HUNT_RETURN_GRACE)
        deadline = clock() + grace
        while s.is_running(name) and clock() < deadline:
            s.sleep(1)
    if s.is_running(name):
        s.kill(name)
    deadline = clock() + EXIT_WAIT
    while s.is_running(name) and clock() < deadline:
        s.sleep(0.25)


def shutdown_soon(s, plan):
    """True once the game's announced maintenance shutdown (the parser's
    `shutdown_at`, #277) is within the plan's `shutdown_minutes`: the
    task in hand gets its return word and the run ends, so the character
    is not cut mid-hunt when the link drops."""
    at = getattr(s.state, "shutdown_at", None)
    now = getattr(s.state, "server_time", None)
    if not at or not now:
        return False
    return (int(at) - int(now)) / 60 <= plan.get("shutdown_minutes", 3)


def watch(s, plan, task, deadline, running=None):
    """The shared loop of both task kinds: why the task ends ("dead",
    "shutdown", "target", "timeout", "skip", "rest", "ended"), or None
    to carry on. running() says whether a script task's script is
    still up."""
    if s.dead:
        return "dead"
    settle_helpers(s)
    if shutdown_soon(s, plan):
        return "shutdown"
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
    started = clock()
    try:
        while True:
            reason = watch(s, plan, task, deadline, running=lambda: s.is_running(name))
            if reason == "ended" and hostiles_present(s.state):
                # The script stopped on hostiles and left the character
                # among them (the invasion of 2026-09-22, #285): out of
                # the room first, then the next task from safety.
                s.echo(f"train: ;{name} ended among hostiles — getting away")
                flee(s)
                return "hostiles"
            if reason == "ended" and (error := crash_of(s, name)):
                # Died with a traceback (#181): the session log has it.
                s.echo(f"train: ;{name} crashed — {error}; a failed {task['name']}")
                return "crashed"
            if reason == "ended" and clock() - started < QUICK_EXIT:
                # Gone within seconds: it refused its room (hostiles,
                # no map edge), it did not train (#182).
                s.echo(
                    f"train: ;{name} ended within {QUICK_EXIT}s of starting — "
                    f"a failed start, not a trained {task['name']}"
                )
                return "failed"
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
    "return": "returned on request",
    "skipped": "could not start",
    "failed": "failed to start",
    "crashed": "its script crashed",
    "shutdown": "wound down for the game's shutdown",
    "hostiles": "ended among hostiles — got away",
    "helper done": "its helper's script ended",
    "healed": "healed — the helper finishes on its own",
    "unneeded": "not needed",
}
UNTRAINED = ("skipped", "failed", "crashed")  # a task that never trained


HelperIO = helper.SessionIO  # the world helper.py acts on


SPAWNED = set()  # helper names this loop logged in (logged out at their last task)
# helper_after "after": name -> (Helper, script), logged out once the
# script has ended — Riphik after healing himself too, while Cecil has
# gone on (the operator, 2026-09-28).
LINGERING = {}


def study_almanac(s, plan=None):
    """The interludes due (client/game/interlude.py — the profile's
    almanac, a typed ;break) run, never with hostiles about — between
    tasks and in the rests, the moments no other script holds the
    hands."""
    if s.dead or hostiles_present(s.state):
        return
    interlude.run_due(s)


def profile_of(s):
    from client.game.profile import load_profile

    return load_profile(getattr(s.state, "name", None) or "")


def settle_helpers(s):
    """Every lingering helper whose script has ended, logged out; one
    whose session does not say is left be."""
    if not LINGERING:
        return
    io = HelperIO(s, None)
    for name, (active, script) in list(LINGERING.items()):
        if helper.running(io, active, script) is False:
            del LINGERING[name]
            if helper.finish(io, active, script, False, s.echo, ended=True):
                SPAWNED.discard(name)


def start_helper(s, task, db, walk):
    """The task's helper logged in, brought to the room and started on
    its script — the student walked there first. The Helper, or None
    when the task has none or it could not be had (said)."""
    spec = helper.spec_of(task)
    if not spec:
        return None
    LINGERING.pop(spec["name"].lower(), None)  # wanted again: not logged out
    io = HelperIO(s, db)
    active = helper.ensure(io, spec["name"], s.echo, SPAWNED, own_port=io.own_port())
    if active is None:
        return None
    if active.spawned:
        SPAWNED.add(spec["name"].lower())
    target = spec["room"]
    if db is not None and walk is not None:
        if target:
            if not travel.go(s, target, repr(target), db=db, walk=walk):
                s.echo(f"train: could not reach room {target} for the class")
        else:
            from client.game.walker import locate

            here = locate(db, s.state)
            target = str(here) if here is not None else ""
    if target and not helper.bring(io, active, target, s.echo):
        return active  # the task runs anyway; the teacher may still arrive
    helper.start(io, active, spec["script"], spec["args"])
    s.echo(f"train: {spec['name']} started ;{spec['script']} {' '.join(spec['args'])}")
    return active


def end_helper(s, task, active, following, db, ended=False):
    """The helper's script returned (unless it `ended` on its own); its
    session logged out unless the next task keeps it."""
    if active is None:
        return
    spec = helper.spec_of(task)
    keep = helper.keeps(following, active.name)
    if task.get("helper_after") == "stay" and not keep:
        keep = True
        s.echo(f"train: {active.name} stays logged in")
    if task.get("helper_after") == "after" and not keep and ended:
        io = HelperIO(s, db)
        if helper.running(io, active, spec["script"]) is not False:
            # Still at it (healing himself): out once the script ends.
            LINGERING[active.name.lower()] = (active, spec["script"])
            s.echo(f"train: {active.name} logs out once ;{spec['script']} is done")
            return
    if helper.finish(HelperIO(s, db), active, spec["script"], keep, s.echo, ended):
        SPAWNED.discard(active.name.lower())


def run_helper_task(s, plan, task, deadline, active, db):
    """A task whose work is the helper's, with no script or commands of
    its own: Riphik's `;empath cecil` while Cecil holds still. It lasts
    while the helper's script runs; "helper done" once it has ended."""
    io = HelperIO(s, db)
    script = helper.spec_of(task)["script"]
    # A helper that stays needs no waiting on past the student's own
    # need: Riphik healed Cecil in ninety seconds and then himself for
    # eight minutes while Cecil stood by (2026-09-27). A `when: wounded`
    # task ends once the panel is clean; the helper's script runs on.
    healed_ends = task.get("when") == "wounded" and task.get("helper_after") in (
        "stay",
        "after",
    )
    while True:
        reason = watch(s, plan, task, deadline)
        if reason is not None:
            return reason
        if helper.running(io, active, script) is False:
            return "helper done"
        if healed_ends and not wounded(s):
            return "healed"
        s.sleep(plan["poll"])


def wounded(s):
    """True when the injuries panel shows a wound or a scar."""
    return bool(getattr(s.state, "injuries", None))


# Embrace of the Vela'Tohr (#443): an Empath's ethereal plant heals a
# non-Empath who TOUCHes it, slowly, while they stay in its room out of
# combat; it never heals another Empath and is gone when its Empath logs
# out (Elanthipedia: Embrace of the Vela'tohr). Riphik cast one in the
# Paladins' Guild Chambers, 2026-10-03: "You also see an ethereal
# vela'tohr plant". The touch's wordings are the wiki's until captured.
PLANT = "vela'tohr plant"
PLANT_TOUCHED = (
    "empathic connection forming",
    "your wounds tingle",
    "wounds knit shut",
)


def plant_step(s, plan, db, walk, room):
    """A wounded rest at the plan's `plant_room`: walked there, TOUCH
    PLANT, and the rest stays beside it while it heals (#443). The room
    the rest keeps: the plant's when one stands there, else `room`,
    walked back to."""
    target = str(plan.get("plant_room") or "").strip()
    if not target or not wounded(s):
        return room
    travel.go(s, target, repr(target), db=db, walk=walk)
    if PLANT not in (getattr(s.state, "room_objs", "") or "").lower():
        s.echo(f"train: no vela'tohr plant at {target} — resting as usual")
        if room is not None and str(room) != target:
            travel.go(s, room, repr(room), db=db, walk=walk)
        return room
    answer = act.ask(s, "touch plant")
    if any(word in answer.lower() for word in PLANT_TOUCHED):
        s.echo("train: touched the vela'tohr plant — resting beside it while it heals")
    else:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"train: TOUCH PLANT answered {first!r} — resting beside it anyway")
    return target


def task_named(plan, wanted):
    """The plan's task called `wanted` (case ignored), or None."""
    wanted = str(wanted or "").strip().lower()
    return next((t for t in plan.get("tasks", []) if t["name"].lower() == wanted), None)


def following_task(plan, task):
    """The task after this one in the plan's order, or None."""
    names = [t.get("name") for t in plan.get("tasks", [])]
    if task.get("name") in names:
        index = names.index(task.get("name")) + 1
        if index < len(names):
            return plan["tasks"][index]
    return None


def run_task(s, plan, task, db=None, walk=None):
    """One task, setup to teardown; why it ended (watch's reasons). A
    task with a helper has the helper logged in, brought and started
    before the setup, and returned and logged out after the teardown
    (client/game/helper.py)."""
    study_almanac(s, plan)  # between tasks: the hands are the loop's
    if task.get("when") == "wounded" and not wounded(s):
        s.echo(f"train: {task['name']} — not wounded, skipped")
        return "unneeded"
    cap = favors_cap(task.get("when"))
    if cap is not None:
        have = getattr(s.state, "favors", None)
        if have is None or have >= cap:
            held = "not read yet" if have is None else f"{have}"
            s.echo(f"train: {task['name']} — favors {held} (cap {cap}), skipped")
            return "unneeded"
    budget = task_minutes(plan, task)
    deadline = clock() + budget * 60 if budget else None
    limit = f"up to {budget} min" if budget else "no time limit"
    s.echo(f"train: {task['name']} — {progress(plan, task, experience(s))} ({limit})")
    active = start_helper(s, task, db, walk)
    send_each(s, task["setup"])
    if task["script"]:
        reason = run_script_task(s, plan, task, deadline)
    elif task["commands"]:
        reason = run_command_task(s, plan, task, deadline)
    elif active is not None:
        reason = run_helper_task(s, plan, task, deadline, active, db)
    else:
        s.echo(f"train: {task['name']} has no script, commands or helper — skipped")
        reason = "skipped"
    end_helper(
        s,
        task,
        active,
        following_task(plan, task),
        db,
        ended=reason in ("helper done", "healed"),
    )
    if reason != "dead":
        send_each(s, task["teardown"])
        s.echo(
            f"train: {task['name']} {ENDINGS.get(reason, reason)} — "
            f"{progress(plan, task, experience(s))}"
        )
    return reason


def train_cycle(s, plan, db=None, walk=None):
    """Every task once, in the plan's order, skipping the ones already
    at target: "trained" when the cycle is complete, "dead" on death,
    "nothing" when every task that ran failed to start (#182)."""
    spent = set()
    outcomes = []
    while True:
        if s.dead:
            return "dead"
        task = next_task(plan, experience(s), spent)
        if task is None:
            break
        reason = run_task(s, plan, task, db, walk)
        if reason in ("dead", "shutdown", "return"):
            return reason
        spent.add(task["name"])
        outcomes.append(reason)
        if reason == "rest":
            return "trained"
    if outcomes and all(reason in UNTRAINED for reason in outcomes):
        return "nothing"
    return "trained"


def soul_due(s, plan):
    """The soul deeds whose timers allow them now, in SOUL_DEEDS order —
    [] unless the plan's `soul` is on (#227). Reads the timers `;soul`
    keeps in ~/.revenant/soul/<name>.json, so the two never tithe twice.
    With no fresh state reading the reading comes first (["read"]: RUB
    at an orb, else the nearest soulstone arch, #231), and while the
    reading says pristine nothing is due: the deeds restore a soul,
    they do not maintain one (the operator, 2026-09-20)."""
    if plan.get("soul", "off") != "on":
        return []
    from client.game import soul

    timers = soul.load_timers(getattr(s.state, "name", None) or "")
    if soul.last_state(timers) is None and soul.due(timers, "read") == 0:
        return ["read"]
    if not soul.deeds_needed(timers):
        return []
    return [
        deed
        for deed in SOUL_DEEDS
        if not timers.get(f"{deed}_off") and soul.due(timers, deed) == 0
    ]


def soul_step(s, plan, db, walk, room):
    """One due soul deed, run as `;soul <deed>` and waited for, then the
    walk back to the rest's room when the deed moved the character
    (the tithe, the prayer, the song); the badge prays where it stands. True
    when a deed ran (#227)."""
    due = soul_due(s, plan)
    if not due:
        return False
    deed = due[0]
    if s.is_running("soul"):
        s.echo("train: a ;soul is already running — leaving the deed to it")
        return False
    if not s.run("soul", [deed]):
        return False
    s.echo(
        "train: soul reading — ;soul read"
        if deed == "read"
        else f"train: soul deed — ;soul {deed}"
    )
    started = clock()
    while s.is_running("soul"):
        if s.dead or clock() - started >= SOUL_MINUTES * 60:
            s.kill("soul")
            break
        s.sleep(min(5, plan["poll"]))
    if room is not None and deed != "badge":
        travel.go(s, room, repr(room), db=db, walk=walk)
        send_each(s, plan["rest_commands"])
    return True


def tdp_step(s, plan, quote):
    """One stat point bought in a rest when the plan says where the
    TDPs go (#230): INFO for the stats and the points, the plan's goals
    or the guild's tiers for the stat (client/game/tdp.py), the wiki's
    cost against the points past the reserve, then `;tdp train <stat>
    +1` — which walks to the trainer, buys the one point the game
    quotes and walks back — waited for. True when a point was bought.

    `quote` is the rest's memory (#282): the first poll's INFO prices
    the next point and keeps it there, and the polls after read the
    TDP count off the exp window (`s.state.tdps`, pushed every pulse)
    instead of asking INFO again — 247 INFOs went out on 2026-09-22 for
    5 points against a 45-point cost. A purchase clears the quote (the
    stats moved); a rest that cannot afford the point says so once."""
    entries = plan.get("tdp") or []
    if not entries or s.is_running("tdp") or quote.get("done"):
        return False
    from client.game import probe
    from client.game import tdp as tdp_model

    reserve = plan.get("tdp_reserve", 0)
    if "cost" in quote:
        known = getattr(s.state, "tdps", None)
        tdps = known if known is not None else quote["tdps"]
        if tdps - reserve < quote["cost"]:
            return False  # still short: no INFO until the window says otherwise
    info = tdp_model.parse_info(probe.ask(s, "info", INFO_SECONDS, INFO_TAIL))
    if info["tdps"] is None or not info["stats"]:
        s.echo("train: INFO gave no TDPs — no stat bought this rest")
        return False
    try:
        goals = tdp_model.plan_goals(entries, info["stats"])
    except ValueError as error:
        s.echo(f"train: the plan's tdp list — {error}")
        return False
    choice = tdp_model.next_stat(info["stats"], goals, info.get("guild"))
    if choice is None:
        quote["done"] = True  # every goal reached: nothing more this rest
        return False
    stat, value = choice
    cost = tdp_model.point_cost(value)
    quote.update(tdps=info["tdps"], cost=cost)
    if info["tdps"] - reserve < cost:
        if not quote.get("said"):
            quote["said"] = True
            s.echo(
                f"train: {info['tdps']} TDPs, the next point ({stat} {value} → "
                f"{value + 1}) costs {cost} — no stat this rest"
            )
        return False
    quote.clear()  # a purchase moves the stats: the next poll prices anew
    if not s.run("tdp", ["train", stat.lower(), "+1"]):
        return False
    s.echo(
        f"train: TDPs — {stat} {value} → {value + 1} (about {cost} of {info['tdps']})"
    )
    started = clock()
    while s.is_running("tdp"):
        if s.dead or clock() - started >= TDP_MINUTES * 60:
            s.kill("tdp")
            break
        s.sleep(min(5, plan["poll"]))
    return True


def drain_inputs(name):
    """(guild, Wisdom) from the latest ;sheet snapshot in history.db,
    each None without one."""
    queries = (
        "SELECT guild FROM character WHERE character_name = ?"
        " AND guild IS NOT NULL ORDER BY logged_at DESC LIMIT 1",
        "SELECT value FROM stats WHERE character_name = ?"
        " AND stat = 'Wisdom' ORDER BY logged_at DESC LIMIT 1",
    )
    answers = []
    try:
        connection = sqlite3.connect(database_path())
    except sqlite3.Error:
        return None, None
    try:
        for query in queries:
            try:
                row = connection.execute(query, (name,)).fetchone()
            except sqlite3.Error:
                row = None  # no table yet: ;sheet has never run here
            answers.append(row[0] if row else None)
    finally:
        connection.close()
    return tuple(answers)


def drain_note(s, plan):
    """The drain model's guess at the rest's length (#300), or None for
    a guild or skill the model does not place, or nothing to drain. A
    guess only: the rest still ends on the exp window."""
    guild, wisdom = drain_inputs(getattr(s.state, "name", None) or "")
    estimate = drain.rest_estimate(
        experience(s), tracked_skills(plan), plan["rest_until"], guild, wisdom
    )
    if not estimate or estimate[1] is None:
        return None
    minutes, skill = estimate
    return f"train: the drain model expects about {round(minutes)} min — {skill} drains last"


def top_up(s, plan, tasks, db, walk):
    """A pause in the rest: the drained tasks (and the `when` tasks
    before them) run once, in plan order; why the pass ended."""
    names = ", ".join(task["name"] for task in tasks)
    s.echo(f"train: drained — {names} before the rest goes on")
    for task in tasks:
        if s.dead:
            return "dead"
        reason = run_task(s, plan, task, db, walk)
        if reason in ("dead", "shutdown", "return", "rest"):
            return reason
    return "done"


def refilled_since(plan, mark):
    """The plan's skills the almanac has filled since `mark` (a length
    of almanac.STUDIED taken when the rest began), in the plan's
    spelling: the rest does not wait for those (#412)."""
    tracked = {skill.lower(): skill for skill in tracked_skills(plan)}
    return [
        tracked[skill.lower()]
        for skill in almanac.STUDIED[mark:]
        if skill.lower() in tracked
    ]


def rounds_done(plan, topped):
    """True once a rest has nothing left to do online: top_up off, or
    every task with skills has had its one top-up (#412)."""
    if plan.get("top_up", "on") != "on":
        return True
    return all(task["name"] in topped for task in plan["tasks"] if task["skills"])


def log_out(s, why):
    """The rest taken offline (#412): the rested bank refills only
    offline, and the pools drain either way. Said first — the link ends
    with the QUIT — then QUIT, as ;logout and ;deathwatch do (a script's
    own QUIT passes the session's policy; an outsider's is refused)."""
    s.echo(
        f"train: {why} — logging out for the rest (QUIT); "
        "start me again at the next login"
    )
    s.waitrt()
    s.put("quit")
    return LOGGED_OUT


def rest(s, plan, db, walk, index):
    """The rest: to the index-th safe room, the rest commands, then hold
    until every trained skill has drained or the cap passes; a task whose
    own skills drain first is trained in the meantime (top_up), and a
    skill the almanac refilled is not waited for. Returns the next rest's
    index, None on death, RETURNED on a typed return, or LOGGED_OUT once
    a logout rest has sent its QUIT (#412)."""
    room = safe_room(plan, index)
    if room is not None:
        travel.go(s, room, repr(room), db=db, walk=walk)
        index += 1
    room = plant_step(s, plan, db, walk, room)
    send_each(s, plan["rest_commands"])
    cap = rest_cap(plan)
    logout = plan.get("rest_mode", "online") == "logout"
    until = f"every trained skill is at {plan['rest_until']}/34 or below"
    s.echo(
        f"train: resting until {until} (at most {cap} min)"
        + (" — logging out once the top-ups are done" if logout else "")
    )
    estimate = drain_note(s, plan)
    if estimate:
        s.echo(estimate)
    started = clock()
    mark = len(almanac.STUDIED)
    refilled = set()  # the plan's skills the almanac filled this rest (#412)
    moves = 0
    bought = 0
    quote = {}  # the rest's TDP pricing (#282)
    # Each task tops up once a rest: ;boxes with no box to open left
    # Locksmithing at 0/34 — "drained" at every look — and ran again
    # every poll (2026-09-27).
    topped = set()
    while True:
        if s.dead:
            return None
        settle_helpers(s)
        study_almanac(s, plan)
        soul_step(s, plan, db, walk, room)
        if s.dead:
            return None
        if bought < TDP_POINTS_PER_REST and tdp_step(s, plan, quote):
            bought += 1
            continue
        for skill in refilled_since(plan, mark):
            if skill not in refilled:
                refilled.add(skill)
                s.echo(
                    f"train: the almanac refilled {skill} — the rest will not wait for it"
                )
        if rested(plan, experience(s), ignore=refilled):
            s.echo("train: rested — the pool has drained")
            return index
        ready = [
            task
            for task in top_up_tasks(plan, experience(s))
            if task["name"] not in topped
        ]
        if any(task["skills"] for task in ready):
            topped.update(task["name"] for task in ready)
            ended = top_up(s, plan, ready, db, walk)
            if ended == "dead":
                return None
            if ended == "return":
                return RETURNED
            if ended == "shutdown":
                return index  # run() ends the run
            room = safe_room(plan, index)
            if room is not None:
                travel.go(s, room, repr(room), db=db, walk=walk)
                index += 1
            room = plant_step(s, plan, db, walk, room)
            send_each(s, plan["rest_commands"])
            s.echo("train: back to the rest")
            continue
        if shutdown_soon(s, plan):
            return index  # run() ends the run
        capped = clock() - started >= cap * 60
        if logout:
            # Never a QUIT among hostiles: the moves below come first.
            if not hostiles_present(s.state):
                if rounds_done(plan, topped):
                    return log_out(s, "the top-ups are done")
                if capped:
                    return log_out(s, f"{cap} minutes of rest")
        elif capped:
            s.echo(f"train: {cap} minutes of rest — moving on")
            return index
        word = user_word(s, plan)
        if word == "skip":
            s.echo("train: rest skipped")
            return index
        if word == "return":
            return RETURNED  # run() ends the run
        if hostiles_present(s.state):
            # A rest among things biting you never drains (#182): out of
            # the room, to the next safe room when the plan has one,
            # next door otherwise, and given up after a few moves.
            moves += 1
            if moves > LEAVE_ATTEMPTS:
                s.echo(
                    f"train: hostiles found the rest {LEAVE_ATTEMPTS} times — "
                    "giving it up for this cycle"
                )
                return index
            if len(plan["safe_rooms"]) > 1:
                s.echo("train: hostiles at the safe room — moving to the next one")
                flee(s)
                travel.go(s, safe_room(plan, index), db=db, walk=walk)
                index += 1
            else:
                s.echo("train: hostiles here — leaving the room to rest next door")
                flee(s)
            send_each(s, plan["rest_commands"])
        s.sleep(plan["poll"])


def run(s, plan, cycles, db=None, walk=None):
    """The loop: train, rest, repeat cycles times (0 = until stopped)."""
    cycle = 0
    index = 0
    if plan.get("soul", "off") == "on" and s.is_running("soul"):
        # ;train manages the soul deeds itself (#227): a keep loop
        # started by hand would pray with roundtime in the middle of a
        # hunt, so it is taken over here and its deeds run in the rests.
        s.kill("soul")
        s.echo("train: taking over ;soul — its deeds run in the rests from now on")
    while not cycles or cycle < cycles:
        cycle += 1
        s.echo(f"train: cycle {cycle} — training")
        outcome = train_cycle(s, plan, db, walk)
        if outcome == "dead":
            s.echo("train: you are dead — stopping; deathwatch has it")
            return
        if outcome == "nothing":
            s.echo(
                "train: no task trained this cycle — stopping rather than resting; "
                "check the scripts' own echoes and the plan"
            )
            return
        if outcome == "shutdown" or shutdown_soon(s, plan):
            s.echo(
                "train: the game is shutting down for maintenance — stopping; "
                "start me again after it"
            )
            return
        if outcome == "return":
            s.echo("train: returned on request — the run ends here")
            return
        index = rest(s, plan, db, walk, index)
        if index is None:
            s.echo("train: you are dead — stopping; deathwatch has it")
            return
        if index == LOGGED_OUT:
            return  # said before the QUIT; the link ends with it
        if index == RETURNED:
            s.echo("train: returned on request — the rest and the run end here")
            return
        if shutdown_soon(s, plan):
            s.echo(
                "train: the game is shutting down for maintenance — stopping; "
                "start me again after it"
            )
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
    guild, _ = drain_inputs(name)
    save_plan(name, starter_plan(name, guild))
    s.echo(f"train: starter plan written to {path}")
    if str(guild or "").lower() == "empath":
        s.echo("train: no hunt in it — an Empath's attack is empathic shock (#444)")
    # The operator, 2026-10-03: "i have no idea what any of the things
    # do" — the file alone explains nothing; the dialog labels each.
    s.echo(
        "train: File > Training Plan... shows each setting with what it does; "
        ";train plan prints the plan in words; docs/training.md has the tables"
    )


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
    db, walk = travel_engine(s, plan)
    if word == "task":
        # One task by name, once, no rest: the way to try a task — a
        # helper class with its login and logout — without the whole
        # cycle in front of it (the operator, 2026-09-22).
        wanted = " ".join(s.args[1:])
        task = task_named(plan, wanted)
        if task is None:
            names = ", ".join(t["name"] for t in plan["tasks"])
            s.echo(f"train: no task named {wanted!r} — the plan has: {names}")
            return
        reason = run_task(s, plan, task, db, walk)
        s.echo(f"train: task {task['name']} {ENDINGS.get(reason, reason)} — done")
        return
    cycles = 1 if word == "once" else plan["cycles"]
    run(s, plan, cycles, db=db, walk=walk)
