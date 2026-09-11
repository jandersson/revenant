# The training loop ;train runs

`;train` is the orchestrator: it runs the trainers a character's plan
names, each until the skills it trains reach a target mindstate, and
once every task is trained it rests in a safe room until those skills
have drained into ranks — then goes again. It is scaffolding: the loop
knows nothing about any skill, and a task is one line of JSON tying
skills to whatever trains them. This file records the plan, the loop,
and what it assumes about the game; `client/tests/test_training.py`
and `test_train_script.py` pin the same behavior.

## The plan

One JSON file per character, `~/.revenant/training/<name>.json`
(`REVENANT_TRAINING` moves the directory). `;train init` writes a
starter — the two bundled trainers, the hunt task's skills taken from
the character's profile — and `;train plan` prints what the file says.
There is no dialog yet; the file is coerced on load, so a string where
a number belongs or a comma-separated list where a JSON list belongs
still works, and a mistake the loop cannot live with (a task naming no
script and no commands, an unknown order) is reported and refuses to
run.

| key | what the loop does with it |
| --- | --- |
| safe_rooms | `;go2` targets; each rest walks to the next one in the list, round and round. Empty rests wherever training ended |
| rest_commands | sent on arrival at the safe room (`sit`) |
| target | a task's skills are trained once every one sits at this mindstate or above (0-34; default 30) |
| rest_until | the rest ends once every skill any task trains has drained to this or below (default 10) |
| rest_minutes | a cap on the rest; 0 waits for the drain |
| task_minutes | a task's time budget, when it never reaches the target; 0 is no budget |
| order | `listed` runs tasks in file order; `lowest` runs the task whose least-trained skill is lowest first |
| poll | seconds between mindstate checks |
| cycles | train-rest cycles before exiting; 0 loops until stopped (`;train once` is 1) |
| tasks | the list below |

A task:

| key | what the loop does with it |
| --- | --- |
| name | how it is reported; defaults to the script's name |
| skills | the exp-window names it trains (`Small Edged`, case ignored); the task is done when all of them reach the target. No skills: the task runs its time budget once per cycle |
| script, args | started as `;<script> <args>` and watched; a script the user already runs by hand is left alone and the task skipped |
| stop_word, stop_grace | how the script is ended at the target: the word is delivered as `;<script> <word>` would be, and the kill follows once the grace (seconds, default 120) runs out. No word: killed at once |
| commands, pace | instead of a script: the commands cycled in the loop's own thread, roundtime waited out, `pace` seconds apart |
| setup, teardown | commands sent before the task and after it (`get my flute` / `stow my flute`) |
| target, minutes | this task's own target and time budget, overriding the plan's |

Unknown keys survive a save, so a task can grow a field before the
loop learns it.

## The loop

1. **Train.** Every task once per cycle, in the plan's order, skipping
   the ones whose skills already sit at the target. A task ends at the
   target, at its time budget, when its script exits on its own (an
   empty hunting ground, a rung the map lost), on `;train skip`, or on
   death. Its script is ended with the stop word first — `;hunt stop`
   finishes the kill and walks home — and killed after the grace.
2. **Rest.** With every task trained, walk to the next safe room, send
   the rest commands, and hold, polling the exp window, until every
   skill the plan trains has drained to `rest_until` or below (or the
   cap). `;train skip` ends the rest early; `;train rest` while
   training starts it early.
3. **Again**, until the cycles run out or `;stop train` — which stops
   the running task's script too.

Death ends the loop at any point: deathwatch owns death, and the
loop's only job is to take the child script down with it. Hostiles at
the safe room move the rest to the next safe room when the plan has
more than one (the burst escape, then the walk); with one safe room
the loop warns and stays.

## What it assumes

- **The exp window is the gauge.** A task's progress is its skills'
  mindstates as `client/engine/xml_data.py` parses the window (0-34); a skill
  the window doesn't show is at 0. Resting until the pool drains is
  the outflow model in [experience.md](experience.md): the pool
  converts to ranks in pulses regardless of activity, and a full pool
  wastes inflow.
- **Trainers handle their own danger.** `;athletics` breaks off from
  hostiles and holds below its health floor; `;hunt` has the profile's
  floors. The orchestrator watches only for death and for the goal.
- **Draining is one floor for every skill.** Skills drain at different
  rates; `rest_until` is checked against every tracked skill, so the
  slowest one sets the rest's length. `rest_minutes` caps it, and a
  higher floor shortens every rest.
- **A stopped script leaves the character wherever it was.** A task
  without a stop word is killed mid-action; the next task's script
  starts from there (the bundled trainers walk to their own spots).
  `teardown` is for what must be undone (a wielded instrument), not a
  walk home.

Nothing here is captured from the game beyond what the trainers and
the experience model already pin; the loop sends no command of its
own except the plan's (`rest_commands`, `setup`, `teardown`,
`commands`) and the burst escape. The first attended run is the place
to learn what the rest floor and the budgets should default to.

## Out of scope in the first cut

A dialog for the plan (the file is the interface), a trainer per
skill (each new script is one task line away), conditions beyond
mindstate (time of day, rested-experience hours, a spell's duration),
and running two tasks at once (a spell buff kept up under a hunt).
Each is a plan key and a branch away.
