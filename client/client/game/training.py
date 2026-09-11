"""Training plans: what a character trains, with what, and when to rest.

A plan is ~/.revenant/training/<character>.json — one file per
character, read by ;train (scripts/train.py) and hand-edited (there is
no dialog yet). It names the tasks — each a skill list tied to the
script (or plain command loop) that trains it — the mindstate the
skills must reach, where to rest and until what mindstate they must
drain. This module is the Qt-free half: the schema with its defaults,
the file, and the decisions the loop makes (which task next, is a
task done, is the rest over, which safe room). REVENANT_TRAINING
overrides the directory (tests point it at a temp dir). Model and
assumptions: docs/training.md.

A plan, with every key the loop reads:

    {
     "safe_rooms": ["home"],        ;go2 targets, rotated rest by rest
     "rest_commands": ["sit"],      sent on arrival at the safe room
     "target": 30,                  a task's skills are trained at this mindstate
     "rest_until": 10,              rest until every trained skill drained to this
     "rest_minutes": 0,             cap on a rest; 0 = until drained
     "task_minutes": 30,            per-task time budget; 0 = until the target
     "order": "listed",             or "lowest": the least-trained task first
     "poll": 30,                    seconds between mindstate checks
     "cycles": 0,                   train-rest cycles; 0 = until stopped
     "tasks": [
      {"name": "climbs", "script": "athletics", "skills": ["Athletics"]},
      {"name": "rats", "script": "hunt", "skills": ["Small Edged", "Evasion"],
       "stop_word": "stop", "minutes": 45},
      {"name": "music", "commands": ["play my flute"], "pace": 8,
       "skills": ["Performance"], "setup": ["get my flute"],
       "teardown": ["stow my flute"]}
     ]
    }

A task has either a script (started as ;<script> <args>, watched, and
stopped once its skills reach the target — with stop_word first, the
way ;hunt stop finishes the kill and walks home, killed after
stop_grace seconds) or commands (cycled in this thread, pace seconds
apart, roundtime waited out). Its target and minutes override the
plan's; setup and teardown bracket it. A task with no skills runs its
time budget once per cycle.
"""

import json
import os
from pathlib import Path

from client.game.profile import load_profile, slug

MIND_LOCK = 34

DEFAULTS = {
    "safe_rooms": [],
    "rest_commands": [],
    "target": 30,
    "rest_until": 10,
    "rest_minutes": 0,
    "task_minutes": 30,
    "order": "listed",
    "poll": 30,
    "cycles": 0,
    "tasks": [],
}

TASK_DEFAULTS = {
    "name": "",
    "skills": [],
    "script": "",
    "args": [],
    "stop_word": "",
    "stop_grace": 120,
    "commands": [],
    "pace": 5,
    "setup": [],
    "teardown": [],
    # None: the plan's value applies.
    "target": None,
    "minutes": None,
}

ORDERS = ("listed", "lowest")

_INTS = ("target", "rest_until", "rest_minutes", "task_minutes", "poll", "cycles")
_TASK_INTS = ("stop_grace", "pace")
_TASK_OPTIONAL_INTS = ("target", "minutes")
_LISTS = ("safe_rooms", "rest_commands")
_TASK_LISTS = ("skills", "args", "commands", "setup", "teardown")


def training_dir() -> Path:
    return Path(
        os.environ.get("REVENANT_TRAINING", "~/.revenant/training")
    ).expanduser()


def plan_path(character) -> Path:
    return training_dir() / f"{slug(character)}.json"


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _list(value):
    """A list of stripped strings; a comma-separated string splits."""
    if isinstance(value, str):
        value = value.split(",")
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def normalize_task(values, index=0) -> dict:
    """A task with every key present and coerced. An unnamed task is
    named after its script, else task<n>."""
    task = dict(TASK_DEFAULTS)
    if not isinstance(values, dict):
        values = {}
    for key, value in values.items():
        if key in _TASK_LISTS:
            task[key] = _list(value)
        elif key in _TASK_INTS:
            task[key] = _int(value, TASK_DEFAULTS[key])
        elif key in _TASK_OPTIONAL_INTS:
            task[key] = None if value in (None, "") else _int(value, None)
        elif key in ("name", "script", "stop_word"):
            task[key] = str(value or "").strip()
        else:
            task[key] = value  # a key this build doesn't know: kept as is
    task["name"] = task["name"] or task["script"] or f"task{index + 1}"
    return task


def normalize(values: dict) -> dict:
    """A plan coerced to its kinds — the file is hand-edited, and a
    typo must not break the loop."""
    clean = {}
    for key, value in values.items():
        if key in _LISTS:
            clean[key] = _list(value)
        elif key in _INTS:
            clean[key] = _int(value, DEFAULTS[key])
        elif key == "order":
            clean[key] = str(value or "").strip().lower() or DEFAULTS["order"]
        elif key == "tasks":
            tasks = value if isinstance(value, list) else []
            clean[key] = [normalize_task(task, i) for i, task in enumerate(tasks)]
        else:
            clean[key] = value
    return clean


def load_plan(character) -> dict:
    """Defaults merged with whatever the character's file holds."""
    merged = dict(DEFAULTS)
    try:
        with open(plan_path(character), encoding="utf-8") as stream:
            stored = json.load(stream)
    except (OSError, ValueError):
        return merged
    if isinstance(stored, dict):
        merged.update(normalize(stored))
    return merged


def save_plan(character, plan: dict) -> Path:
    path = plan_path(character)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return path


def starter_plan(character) -> dict:
    """The plan ;train init writes: the two bundled trainers, the hunt
    task taking its skills from the character's profile. Edit from
    there — every key is documented in this module's docstring."""
    profile = load_profile(character)
    plan = dict(DEFAULTS)
    plan["safe_rooms"] = [profile["home"]] if profile["home"] else []
    plan["tasks"] = [
        normalize_task(
            {"name": "climbs", "script": "athletics", "skills": ["Athletics"]}
        ),
        normalize_task(
            {
                "name": "hunt",
                "script": "hunt",
                "skills": list(profile["train_skills"]),
                "stop_word": "stop",
            }
        ),
    ]
    return plan


def validate(plan: dict) -> list:
    """What would make the loop misbehave, one line each; [] is fine."""
    problems = []
    if plan["order"] not in ORDERS:
        problems.append(f"order {plan['order']!r} is not one of {', '.join(ORDERS)}")
    if not 0 <= plan["target"] <= MIND_LOCK:
        problems.append(f"target {plan['target']} is outside 0-{MIND_LOCK}")
    if not 0 <= plan["rest_until"] < MIND_LOCK:
        problems.append(f"rest_until {plan['rest_until']} is outside 0-{MIND_LOCK - 1}")
    if plan["poll"] < 1:
        problems.append("poll must be at least 1 second")
    names = set()
    for task in plan["tasks"]:
        if task["script"] and task["commands"]:
            problems.append(f"task {task['name']}: a script or commands, not both")
        elif not task["script"] and not task["commands"]:
            problems.append(f"task {task['name']}: names no script and no commands")
        if task["name"] in names:
            problems.append(f"task {task['name']}: the name is used twice")
        names.add(task["name"])
        if task["pace"] < 0:
            problems.append(f"task {task['name']}: pace must be 0 or more")
    return problems


# -- the decisions ---------------------------------------------------------


def mindstate(experience, skill) -> int:
    """A skill's mindstate 0-34 from the exp window's dict; 0 when the
    window doesn't show it (nothing learning). Names match ignoring
    case, so a plan may say "small edged"."""
    wanted = skill.strip().lower()
    for name, entry in (experience or {}).items():
        if name.strip().lower() == wanted:
            return int(entry.get("mindstate", 0))
    return 0


def task_mindstates(task, experience) -> dict:
    return {skill: mindstate(experience, skill) for skill in task["skills"]}


def task_target(plan, task) -> int:
    return plan["target"] if task["target"] is None else task["target"]


def task_minutes(plan, task) -> int:
    return plan["task_minutes"] if task["minutes"] is None else task["minutes"]


def satisfied(plan, task, experience) -> bool:
    """True when every skill of the task sits at or above its target.
    A task with no skills is never satisfied — it runs its time budget
    once per cycle."""
    if not task["skills"]:
        return False
    target = task_target(plan, task)
    return all(state >= target for state in task_mindstates(task, experience).values())


def tracked_skills(plan) -> list:
    """Every skill any task trains, in first-seen order."""
    seen = []
    for task in plan["tasks"]:
        for skill in task["skills"]:
            if skill.lower() not in {s.lower() for s in seen}:
                seen.append(skill)
    return seen


def rested(plan, experience) -> bool:
    """True once every tracked skill has drained to rest_until or
    below — the rest is over. A plan tracking no skills is always
    rested."""
    return all(
        mindstate(experience, skill) <= plan["rest_until"]
        for skill in tracked_skills(plan)
    )


def next_task(plan, experience, spent=()):
    """The task to run now, or None when the cycle is complete: not
    already run this cycle (spent, by name), not satisfied. "listed"
    takes them in file order; "lowest" takes the one whose least-trained
    skill is lowest (a skill-less task counts as 0)."""
    spent = set(spent)
    candidates = [
        task
        for task in plan["tasks"]
        if task["name"] not in spent and not satisfied(plan, task, experience)
    ]
    if not candidates:
        return None
    if plan["order"] == "lowest":
        return min(
            candidates,
            key=lambda task: min(task_mindstates(task, experience).values() or [0]),
        )
    return candidates[0]


def safe_room(plan, index):
    """The safe room for the index-th rest — the list rotated — or
    None when the plan names none (rest where the training ended)."""
    rooms = plan["safe_rooms"]
    if not rooms:
        return None
    return rooms[index % len(rooms)]


def describe(plan: dict) -> list:
    """The plan as ;train plan prints it."""
    lines = [
        f"safe rooms: {', '.join(plan['safe_rooms']) or '(rest in place)'}",
        f"rest commands: {', '.join(plan['rest_commands']) or '(none)'}",
        f"target {plan['target']}/34, rest until {plan['rest_until']}/34"
        + (f" or {plan['rest_minutes']} min" if plan["rest_minutes"] else ""),
        f"order {plan['order']}, {plan['task_minutes'] or 'no'} min per task, "
        f"poll {plan['poll']}s, "
        + (f"{plan['cycles']} cycle(s)" if plan["cycles"] else "until stopped"),
    ]
    if not plan["tasks"]:
        lines.append("tasks: (none — edit the plan file)")
    for task in plan["tasks"]:
        if task["script"]:
            how = f";{task['script']}" + (
                " " + " ".join(task["args"]) if task["args"] else ""
            )
            if task["stop_word"]:
                how += f" (stop word {task['stop_word']!r})"
        else:
            how = " | ".join(task["commands"]) + f" every {task['pace']}s"
        skills = ", ".join(task["skills"]) or "no skills (runs its budget)"
        extras = []
        if task["target"] is not None:
            extras.append(f"target {task['target']}")
        if task["minutes"] is not None:
            extras.append(f"{task['minutes'] or 'no'} min")
        lines.append(
            f"  {task['name']}: {skills} — {how}"
            + (f" [{', '.join(extras)}]" if extras else "")
        )
    return lines


def status_lines(plan, experience) -> list:
    """One line per tracked skill with its mindstate against the target."""
    return [
        f"  {skill}: {mindstate(experience, skill)}/34"
        for skill in tracked_skills(plan)
    ] or ["  (no skills tracked)"]
