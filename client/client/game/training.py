"""Training plans: what a character trains, with what, and when to rest.

A plan is ~/.revenant/training/<character>.json — one file per
character, read by ;train (scripts/train.py), edited from the GUI's
File → Training Plan… dialog (client/gui/plan_dialog.py, built from
PLAN_FIELDS and TASK_FIELDS below) or by hand. It names the tasks — each a skill list tied to the
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
     "shutdown_minutes": 3,         end the run this close to an announced shutdown
     "tasks": [
      {"name": "climbs", "script": "athletics", "skills": ["Athletics"]},
      {"name": "rats", "script": "hunt", "skills": ["Small Edged", "Evasion"],
       "return_word": "return", "minutes": 45},
      {"name": "music", "commands": ["play my flute"], "pace": 8,
       "skills": ["Performance"], "setup": ["get my flute"],
       "teardown": ["stow my flute"]}
     ]
    }

A task has either a script (started as ;<script> <args>, watched, and
stopped once its skills reach the target — with return_word first,
the way ;hunt return finishes the kill and walks home, killed after
return_grace seconds; a plan saved with the old stop_word / stop_grace
keys is read as these, its "stop" as "return") or commands (cycled in this thread, pace seconds
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
    "soul": "off",
    "tdp": [],
    "tdp_reserve": 0,
    # The run ends, the task in hand wound down first, once the game's
    # announced shutdown is this close (#277).
    "shutdown_minutes": 3,
    "tasks": [],
}
SOUL = ("off", "on")
# The choices behind each "choice" plan field, for the dialog.
CHOICES = {"order": None, "soul": SOUL}  # order's are ORDERS, defined below

TASK_DEFAULTS = {
    "name": "",
    "skills": [],
    "script": "",
    "args": [],
    "return_word": "",
    "return_grace": 120,
    "commands": [],
    "pace": 5,
    "setup": [],
    "teardown": [],
    # A helper character logged in for the task (client/game/helper.py):
    # the teacher of a class. Empty: none.
    "helper": "",
    "helper_script": "",
    "helper_args": [],
    "helper_room": "",
    # None: the plan's value applies.
    "target": None,
    "minutes": None,
}

ORDERS = ("listed", "lowest")

# The schema the GUI's Training Plan dialog builds from
# (client/gui/plan_dialog.py): (key, label, kind, help) per plan setting
# and per task setting, in display order. Kinds: "int", "optint" (blank
# means the plan's value), "choice" (one of ORDERS), "str", "list"
# (comma-separated in the dialog). Adding a key means a default and a
# row here; the dialog picks it up without a change of its own.
PLAN_FIELDS = (
    ("safe_rooms", "Safe rooms (;go2 targets, rotated)", "list", "home, 1900"),
    ("rest_commands", "Sent on arrival at the safe room", "list", "sit"),
    ("target", "Train each task's skills to mindstate", "int", "0-34"),
    ("rest_until", "Rest until every skill drains to", "int", "0-33"),
    ("rest_minutes", "Cap on a rest, minutes", "int", "0: until drained"),
    ("task_minutes", "Time budget per task, minutes", "int", "0: until the target"),
    ("order", "Task order", "choice", "listed, or the least-trained first"),
    ("poll", "Seconds between mindstate checks", "int", ""),
    ("cycles", "Train-rest cycles", "int", "0: until stopped"),
    ("soul", "Soul deeds in the rests (a Paladin)", "choice", "on or off"),
    (
        "tdp",
        "TDPs spent in the rests: stat targets, or auto",
        "list",
        "stamina 30, strength 30 — or auto",
    ),
    ("tdp_reserve", "TDPs kept unspent", "int", "0"),
    ("shutdown_minutes", "Wind down when the shutdown is within, minutes", "int", "3"),
)
TASK_FIELDS = (
    ("name", "Name", "str", "how the task is reported"),
    ("skills", "Skills it trains", "list", "Small Edged, Evasion"),
    ("script", "Script", "str", "hunt — or leave empty and give commands"),
    ("args", "Script arguments", "list", ""),
    ("return_word", "Return word", "str", "return — empty: killed at once"),
    ("return_grace", "Seconds before the kill", "int", "120"),
    ("commands", "Commands cycled instead of a script", "list", "play my flute"),
    ("pace", "Seconds between commands", "int", ""),
    ("setup", "Before the task", "list", "get my flute"),
    ("teardown", "After the task", "list", "stow my flute"),
    ("helper", "Helper character", "str", "Fallanor — logged in for the task"),
    ("helper_script", "Helper's script", "str", "teach (the default)"),
    ("helper_args", "Helper's arguments", "list", "parry ability, to, cecil"),
    ("helper_room", "Room for both", "str", "7890 — blank: where you stand"),
    ("target", "Own target mindstate", "optint", "blank: the plan's"),
    ("minutes", "Own time budget, minutes", "optint", "blank: the plan's"),
)

_INTS = (
    "target",
    "rest_until",
    "rest_minutes",
    "task_minutes",
    "poll",
    "cycles",
    "tdp_reserve",
    "shutdown_minutes",
)
_TASK_INTS = ("return_grace", "pace")
_TASK_OPTIONAL_INTS = ("target", "minutes")
_LISTS = ("safe_rooms", "rest_commands", "tdp")
_TASK_LISTS = ("skills", "args", "commands", "setup", "teardown", "helper_args")


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


def _renamed(values):
    """The task keys as this build names them: a plan saved before
    2026-09-12 said stop_word / stop_grace, and its word "stop" is
    what "return" means now (;stop <name> is the abrupt end)."""
    values = dict(values)
    if "stop_word" in values and "return_word" not in values:
        word = str(values.pop("stop_word") or "").strip()
        values["return_word"] = "return" if word.lower() == "stop" else word
    if "stop_grace" in values and "return_grace" not in values:
        values["return_grace"] = values.pop("stop_grace")
    return values


CHOICES["order"] = ORDERS


def normalize_task(values, index=0) -> dict:
    """A task with every key present and coerced. An unnamed task is
    named after its script, else task<n>."""
    task = dict(TASK_DEFAULTS)
    if not isinstance(values, dict):
        values = {}
    values = _renamed(values)
    for key, value in values.items():
        if key in _TASK_LISTS:
            task[key] = _list(value)
        elif key in _TASK_INTS:
            task[key] = _int(value, TASK_DEFAULTS[key])
        elif key in _TASK_OPTIONAL_INTS:
            task[key] = None if value in (None, "") else _int(value, None)
        elif key in ("name", "script", "return_word"):
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
        elif key in ("order", "soul"):
            clean[key] = str(value or "").strip().lower() or DEFAULTS[key]
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
    """The plan ;train init writes: the bundled trainers — climbs, the
    hunt (its skills from the character's profile), the skins sold and
    banked after it, the purse banked (the foreign coins exchanged,
    everything deposited, #235), the TDPs spent where the plan's `tdp`
    list says (`;tdp plan`, a task in the order, the operator
    2026-09-20), and foraging for Outdoorsmanship. Edit from there
    — every key is documented in this module's docstring."""
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
                "return_word": "return",
            }
        ),
        # Selling and banking are distinct tasks (the operator, 2026-09-20):
        # ;skins sells, ;bank banks the purse (#235).
        normalize_task({"name": "skins", "script": "skins"}),
        normalize_task({"name": "bank", "script": "bank"}),
        normalize_task({"name": "tdps", "script": "tdp", "args": ["plan"]}),
        normalize_task(
            {
                "name": "forage",
                "script": "forage",
                "skills": ["Outdoorsmanship"],
                "return_word": "return",
            }
        ),
    ]
    return plan


def validate(plan: dict) -> list:
    """What would make the loop misbehave, one line each; [] is fine."""
    problems = []
    if plan["order"] not in ORDERS:
        problems.append(f"order {plan['order']!r} is not one of {', '.join(ORDERS)}")
    if plan.get("soul", "off") not in SOUL:
        problems.append(f"soul {plan['soul']!r} is not one of {', '.join(SOUL)}")
    for entry in plan.get("tdp") or []:
        words = str(entry).split()
        if words == ["auto"]:
            continue
        if (
            len(words) != 2
            or not words[1].isdigit()
            or words[0].lower()
            not in (
                "strength",
                "reflex",
                "agility",
                "charisma",
                "discipline",
                "wisdom",
                "intelligence",
                "stamina",
            )
        ):
            problems.append(f"tdp entry {entry!r} is not '<stat> <target>' or 'auto'")
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
    found = [
        (name, entry)
        for name, entry in (experience or {}).items()
        if str(name).strip().lower() == wanted and isinstance(entry, dict)
    ]
    # The window's own spelling wins over a lowercase seed from before
    # #295: the seed never moves, and a rest waiting on it never ends
    # (Cecil's, 02:09 to 09:00 on 2026-09-23).
    for name, entry in found:
        if name != name.lower():
            return int(entry.get("mindstate", 0))
    return int(found[0][1].get("mindstate", 0)) if found else 0


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
            if task["return_word"]:
                how += f" (return word {task['return_word']!r})"
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
