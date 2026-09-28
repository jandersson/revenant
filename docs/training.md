# Training with ;train

`;train` runs your character's training plan: each task until its skills reach a target mindstate, then a rest until they drain into ranks, then again. The plan is one JSON file per character; the loop knows nothing about any skill beyond what the plan says.

## The loop

1. **Train.** Run each task in order, skipping any whose skills already sit at the target. A task ends at the target, at its time budget, or when its script exits.
2. **Rest.** Walk to the next safe room, send the rest commands (`sit`), and wait until every trained skill has drained to the rest floor. The rest opens with a guess at how long that takes.
3. **Repeat** until the plan's cycles run out or you end it.

Death ends the loop. Each trainer handles its own danger; hostiles at a rest move it to the next safe room or next door.

## Commands

| Command | Does |
| --- | --- |
| `;train` | run the plan until stopped |
| `;train once` | one train-and-rest cycle |
| `;train task <name>` | that one task, once, no rest |
| `;train plan` | print the plan |
| `;train status` | the tracked skills' mindstates |
| `;train init` | write a starter plan (`init force` overwrites) |

While it runs:

- `;train skip` — end the current task, or the rest.
- `;train rest` — stop training and rest now.
- `;train return` — end gracefully: the task's script finishes (`;hunt` finishes the kill and walks home), and nothing follows.
- `;stop train` — end at once, the task's script with it.

A game shutdown announcement winds the run down the same way as `return`, a few minutes before the link drops.

## The plan

Edit it in File → Training Plan…, or by hand in `~/.revenant/training/<name>.json`. `;train init` writes a starter from your profile: climbs, the hunt, skins sold, gear repaired, the purse banked, foraging.

| Plan key | Meaning |
| --- | --- |
| `target` | train each task's skills to this mindstate, 0-34 (30) |
| `rest_until` | rest until every trained skill drains to this (10) |
| `rest_minutes` | cap on a rest; 0 waits for the drain |
| `task_minutes` | time budget per task; 0 is none (30) |
| `order` | `listed`, or `lowest` (least-trained task first) |
| `safe_rooms` | where to rest, rotated; empty rests where training ended |
| `rest_commands` | sent on arrival at the safe room |
| `cycles` | train-rest cycles; 0 loops until stopped |
| `poll` | seconds between mindstate checks |
| `soul` | `on` for a Paladin: soul deeds in the rests while the soul is below pristine ([soul.md](soul.md)) |
| `top_up` | `on` (default): a task whose own skills have all drained trains again during the rest, with the `when` tasks just before it |
| `tdp` | TDPs spent in the rests: stat targets (`stamina 30`) or `auto` for the guild's order |
| `tdp_reserve` | TDPs never spent |
| `shutdown_minutes` | wind down this close to a game shutdown (3) |

A task:

| Task key | Meaning |
| --- | --- |
| `name` | how it is reported |
| `skills` | exp-window names it trains (`Small Edged`) |
| `script`, `args` | started as `;<script> <args>` |
| `return_word` | how the script is ended gracefully (`return`); empty kills it at once |
| `return_grace` | seconds after the word before the kill (120) |
| `commands`, `pace` | commands cycled instead of a script, `pace` seconds apart |
| `setup`, `teardown` | sent before and after the task (`get my flute` / `stow my flute`) |
| `target`, `minutes` | this task's own target and budget |
| `helper`, `helper_script`, `helper_args`, `helper_room` | a second character of yours logged in for the task, such as a teacher for `;listen`; one sharing its account with a logged-in character logs that one out first |
| `helper_after` | `stay`: the helper stays logged in after the task, ready for the next; `after`: the helper logs out once its script ends. With either, a `when: wounded` task ends once you are clean, the helper finishing on its own |
| `when` | `wounded`: skipped while the injuries panel is clean |

A task with no `skills` runs once per cycle for its `minutes`: selling skins, banking, spending TDPs, a timed box farm.

A task with a helper and no `script` or `commands` lasts while the helper's script runs: an Empath healing you after a hunt.

A few tasks:

```json
{"name": "hunt", "skills": ["Brawling"], "script": "hunt", "return_word": "return"}
{"name": "bank", "skills": [], "script": "bank"}
{"name": "books", "skills": ["Scholarship"], "script": "scholarship", "args": ["books"], "return_word": "return"}
{"name": "heal", "helper": "Riphik", "helper_script": "empath", "helper_args": ["cecil"], "helper_room": "7890", "helper_after": "stay", "when": "wounded", "minutes": 20}
```

## Trainers

Each is a script with its own manual (`;help <name>`). Under `;train`, give each `"return_word": "return"`.

| Script | Trains |
| --- | --- |
| `hunt` | weapons, defenses, magic ([hunting.md](hunting.md)) |
| `athletics` | Athletics |
| `forage` | Outdoorsmanship, Perception |
| `attune` | Attunement (power walking; `here` for Moon Mages) |
| `perform` | Performance |
| `scholarship books` | Scholarship |
| `appraise` | Appraisal |
| `boxes` | Locksmithing, on the hunt's boxes |
| `remedies work` | Alchemy, as paid work orders |
| `research` | a Barbarian's Augmentation, Warding, Utility |
| `listen` / `teach` | a class between two of your characters |
| `tdp plan` | spends TDPs (no skill) |

## Plan well

- **Count the skills moving.** More pools above 0/34 learn more than one pool held full; a full pool wastes what it would have learned.
- **The slowest skill sets the rest's length.** Lower `rest_until` means longer rests; `rest_minutes` caps them. With `top_up` on, the tasks that drained first train again in the meantime.
- **A task killed without a return word leaves the character where it stood.** Use `teardown` for what must be undone, such as a held instrument.

How fast pools drain is in [experience.md](experience.md).
