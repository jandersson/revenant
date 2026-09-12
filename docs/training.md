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

## Spending TDPs: ;tdp

Stats rise by spending Time Development Points, one point per TRAIN
typed twice in that stat's training room, and `;tdp train <stat>
[goal]` does the walk and the spending with every point confirmed by
the game's own numbers. `;tdp` alone shows INFO's eight stats and the
TDPs; `;tdp agility 12` quotes the next point (the stat's own command)
and the whole climb (TDP PROJECT) without spending.

Captured 2026-09-12 on a circle-1 Dwarf at Agility 8 with 347 TDPs:

```
> agility
Your base Agility is eight (8).
It will cost you 28 TDPs to raise your Agility from 8 to 9.
You currently have 347 TDPs available.
> tdp project agility 12
It will cost you 132 TDPs to reach 12 points in Agility.
> tdp
You have 347 TDPs.
> dir agility
Directions towards Agility training in Crossing: Southwest.
Type DIR STOP to stop these direction suggestions.
```

The figures match Elanthipedia's formula ([Attributes](https://elanthipedia.play.net/Attributes)):
a point from value *v* costs 3*v* plus the race's modifier times
*v* // 2 in integer math (a Dwarf pays +1 on Agility: 24 + 4 = 28; 28
+ 31 + 35 + 38 = 132), and 15*v* from 100 up. `client/game/tdp.py`
carries the formula for estimates and tests; the script trusts the
quote. DIR keeps repeating its hint every few lines until DIR STOP,
so the script never uses it — the map tags every training room
(`agility`, `strength`, ... one per stat per city; Crossing's are
50984-50989 plus the Academy rooms) and the walker takes it there.

The TRAIN pair itself, captured the same day when `;tdp train agility
+2` ran attended (Agility 8 → 10, TDPs 347 → 288):

```
> train
You consult with the teachers and together decide that it will take 28 moon cycles until you successfully train your agility to 9 ranks.  There is also a fee of 56 Kronars to complete this training.
That would leave you 319 time development points afterward.  If this is OK, you will need to STUDY once again to get your new rank.
> train
(You now have 319 time development points.)
The trainer notes how young you are and that you should keep some coins to help you get equipped.  So, the cost of 56 Kronars is added to your Provincial debt.
(Your debt has increased by 56 Kronars.)
After what seems an astonishing amount of time, you find you have completed your training in agility.
Your attempts to train are praiseworthy, but you must find both the proper place and the proper teacher first.
```

Three things the wiki does not say. A point costs coins as well:
a fee of 2 Kronars per TDP (56 for 28, 62 for 31), and a character
carrying none has it put on the provincial debt (930 → 1048 copper
over the two points), which is the debt that blocks GIVE in
[social.md](social.md) — carry coins to the trainer. The "moon cycles"
are flavor; the point lands at once. And the completed training is
followed by the same "must find both the proper place and the proper
teacher" line that TRAIN answers in the wrong room, so the script
reads "completed your training" before it reads a refusal. It still
re-asks the stat after every pair and stops the moment the value has
not risen, echoing both answers; it buys only points the quoted TDPs
cover, stops on death, echoes the fee and debt lines, and walks back
to where it started unless told `stay`. The Elanthipedia rule of thumb
that a guild may refuse a character with any stat below 8 is the
reason to spend early.

One thing the game did that is not understood (#165): over eleven
points in a day the TDP count rose six times by exactly the previous
point's Kronar fee — after every mental-stat point (Discipline,
Wisdom, Charisma, Intelligence), never after Agility or Reflex — so
the character ended with more TDPs than he started with. The gain
shows only in the next TRAIN's quote, and the game's three figures
agree with each other every time, so the script's reading is not the
cause; it trusts the quote before each point and cannot overspend.

## Out of scope in the first cut

A dialog for the plan (the file is the interface), a trainer per
skill (each new script is one task line away), conditions beyond
mindstate (time of day, rested-experience hours, a spell's duration),
and running two tasks at once (a spell buff kept up under a hunt).
Each is a plan key and a branch away.
