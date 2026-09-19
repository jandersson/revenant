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
starter — climbs, the hunt, the skins sold and banked, and foraging, the hunt task's skills taken from
the character's profile — and `;train plan` prints what the file says.
File → Training Plan… in the client edits it: the plan settings as a
form, the tasks as an ordered list with add, remove, up and down, the
selected task as a form, every row built from the same schema the
loop reads (`PLAN_FIELDS` / `TASK_FIELDS`), and OK refuses a plan the
validator rejects, listing why; the starter plan fills the dialog
when no file exists yet. The file is coerced on load, so a string where
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
| return_word, return_grace | how the script is ended at the target: the word is delivered as `;<script> <word>` would be (`return` for the bundled trainers), and the kill follows once the grace (seconds, default 120) runs out. No word: killed at once. A plan saved with the old `stop_word` / `stop_grace` keys still loads, its "stop" read as "return" |
| commands, pace | instead of a script: the commands cycled in the loop's own thread, roundtime waited out, `pace` seconds apart |
| setup, teardown | commands sent before the task and after it (`get my flute` / `stow my flute`) |
| target, minutes | this task's own target and time budget, overriding the plan's |

Unknown keys survive a save, so a task can grow a field before the
loop learns it.

## The loop

1. **Train.** Every task once per cycle, in the plan's order, skipping
   the ones whose skills already sit at the target. A task ends at the
   target, at its time budget, when its script exits on its own (a
   rung the map lost; `;hunt` waits an empty ground out rather than
   exiting), on `;train skip`, or on
   death. Its script is ended with the return word first — `;hunt
   return` finishes the kill and walks home — and killed after the grace.
2. **Rest.** With every task trained, walk to the next safe room, send
   the rest commands, and hold, polling the exp window, until every
   skill the plan trains has drained to `rest_until` or below (or the
   cap). `;train skip` ends the rest early; `;train rest` while
   training starts it early.
3. **Again**, until the cycles run out or `;stop train` — which stops
   the running task's script too.

Death ends the loop at any point: deathwatch owns death, and the
loop's only job is to take the child script down with it. Hostiles at
the rest move it: to the next safe room when the plan has more than
one (the burst escape, then the walk), out of the room to rest next
door otherwise, and after five such moves in one rest it is given up
for the cycle — a rest among things biting you never drains, since
the attacked skills stay full (2026-09-12: twenty minutes among rats
with Evasion and Parry locked, #182). A script task gone within five
seconds of starting is a failed start (`;attune` refusing a room with
hostiles in it, a rung the map lost), said so and not counted as
trained; a cycle in which no task trained stops the loop instead of
resting.

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
  without a return word is killed mid-action; the next task's script
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

One thing the game did that took a day to understand (#165): over
eleven points the TDP count rose six times by exactly twice the
previous point's cost — after every point that started *below* the
character's racial starting stat, never after one at or above it.
DR3 made TDPs a derived number, recalculated on every rank gain from
ranks and circles minus the stats, and it assumes every character
began at the race's starting values ([DR-Socharis,
2012](https://elanthipedia.play.net/Post:Long_Time,_No_Post_-_10/02/2012_-_03:51));
a DR1-era character whose rolled stats sit below those starts has
each such point counted the other way, so raising it toward the start
nets +cost. Predicted and confirmed with Stamina: the point that
ended at the Dwarf start of 12 came back double, the one that ended
at 13 did not. `;tdp` flags the stats still below the start; train
those first.

## Foraging: ;forage

Outdoorsmanship, a Survival skill, trains by foraging (also mining,
lumberjacking, fishing, tending parasites, companions), and COLLECT
for the easiest item pays best: "the easier item you collect, the more
you will get, which grants more experience" ([Outdoorsmanship
skill](https://elanthipedia.play.net/Outdoorsmanship_skill)). `COLLECT
<item> PRACTICE` "gains experience without generating items", so no
piles are left to KICK; the base roundtime is 15 seconds, falling only
past 1350 ranks ([Collect
command](https://elanthipedia.play.net/Collect_command)). Perception
lists "Foraging (COLLECT <item> being the most efficient)" first among
its trainers, so the same loop feeds it ([Perception
skill](https://elanthipedia.play.net/Perception_skill)). `;forage`
(scripts/forage.py) COLLECTs the item — rock by default — with
PRACTICE until Outdoorsmanship mind-locks, `;forage <item> <n>` for n
collects, `;forage return` to end after the one in hand. The community
map tags each room with what it yields (`rock` on 142 of the
Crossing's rooms, 1204 map-wide), so a room without the item is left
for the nearest tagged one through the walker; `here` skips that.
Captured on the first run, 2026-09-14, on the Crossing's streets at
rank 1: the practice answers "You wander around and poke your fingers
into a few places, wondering what you might find." and "You find
something dead and lifeless, is this what you were looking for?" with
a 6-second roundtime (the wiki's 15-second base is not what a rank-1
character saw) and Outdoorsmanship rising 1 74% dabbling → learning
on the first; the near misses "You are certain you could find what
you were looking for, if you had a bit more luck.", "You are sure you
knew what you were looking for when you started to forage." and "You
begin to forage around, but can't quite seem to remember what it was
you were looking for."; and "You forage around
but are unable to find anything." (6 s) in a room with nothing to
collect and on a failed try where there is something — so three of
those in a row end the run only before the first success, ten after.
An answer outside the table is echoed once per wording while the run
goes on. Under `;train`: `"script": "forage",
"skills": ["Outdoorsmanship"], "return_word": "return"` (#193).

## Power walking: ;attune

Attunement trains by perceiving mana — POWER, PERCEIVE or
CONCENTRATE — and a room pays once per sixty seconds
([Attunement skill](https://elanthipedia.play.net/Attunement_skill),
[Perceive command](https://elanthipedia.play.net/Perceive_command)),
so every guild but the Moon Mages walks: perceive, step to the next
room, perceive again. `;attune` builds a chain of streets from where
you stand (plain compass moves in both directions, so shop doors and
climbs are never part of it), walks it out and back POWERing on each
arrival, waits out a room that paid within the minute, and holds at
mind-lock until enough drains to be worth the laps. `;attune here`
perceives in place once a minute, which is how a Moon Mage trains it:
lunar mana is everywhere. Standalone it is a standing trainer like
`;athletics`: it holds at the lock and walks again once the pool has
drained, until stopped; `;attune once` exits at the lock instead.
Under `;train` (`"script": "attune", "skills": ["Attunement"],
"return_word": "return"`) the loop ends the task itself when Attunement
reaches the plan's target — the word lands within a second,
held or walking — and moves to the next task.

Captured 2026-09-12 on a circle-1 Paladin at rank 2, on the
Crossing's Hodierna Way:

```
> power
You reach out with your weak senses and see glowing streams of golden Holy mana radiating through the area.  Waves of black ripple through the mana streams.
Roundtime: 8 sec.
```

The room's first POWER took Attunement from thoughtful (4/34) to
considering (6/34); a second POWER in the same room within the minute
gave nothing; one room east, the next POWER paid again. The roundtime
was 8-9 s, the wiki's 8-12 at low ranks. "Waves of black ripple
through the mana streams" rode along on every perceive that day and
is not understood — some influence on the local mana, not the
character's. The script stops on death or hostiles, when eight
perceives in a row gain nothing (a guild that cannot sense mana), and
when the map has no street to loop from the starting room.

## Playing: ;perform

Performance trains by playing an instrument: PLAY (song) {mood} ON
{instrument} starts a song that then runs on its own, and the skill
learns while it plays ([Performance skill](https://elanthipedia.play.net/Performance_skill),
[Play command](https://elanthipedia.play.net/Play_command)). The Play
page gives the song per rank band — scales to 39, arpeggios to 49,
ditty to 58, ballad to 69, waltz to 79, march to 99, lament to 124,
hymn to 179, polka to 219, reel to 249, serenade to 299, psalm to
349, tango to 449, bolero to 474, nocturne to 524, requiem to 549, a
concerto from 550 — and says off-key or halting moods make any song
easier, so `;perform` plays the band's song off-key on the profile's
`instrument` (`instrument=`, `song=`, `mood=` override it), watches
the mindstate, starts the song again when the story says it ended,
and at mind-lock STOPs PLAY and holds until the pool has drained
(`once` exits instead). Under `;train` (`"script": "perform",
"skills": ["Performance"], "return_word": "return"`) the loop ends it
at the plan's target; the word stops the song first. It stops on
death, on hostiles, without the instrument, and when EXP shows no
Performance.

Captured 2026-09-18 on a rank-2 Paladin, a pair of copper zills worn
on a finger (Riverhaven's peddler, 500 Lirums), aboard the Faldesu
ferry:

```
> play scales off-key on my zills
You fumble slightly as you begin an off-key ruff on your copper zills.
You continue playing on your copper zills.
You continue to fumble through a few uncertain rhythms on your copper zills, but it doesn't sound like what you intended.
> play scales on my zills
You're already playing a song!  You'll need to stop that one first.
> stop play
You stop playing your song.
```

Performance went 2 00% learning → thoughtful within the first minute
and reached rank 3 on the second song. Whether a song ends on its
own, and its wording, is uncaptured (the script's ENDED table is a
guess); so is a PLAY with no instrument on you.

## Reading: ;scholarship books

Scholarship trains by "reading books at a library"
([Scholarship skill](https://elanthipedia.play.net/Scholarship_skill));
the RECALL forms the wiki also lists ([Recall command](https://elanthipedia.play.net/Recall_command):
HOLIDAY, IMMORTAL <name>, HERB) answered but registered nothing at
rank 2 (2026-09-18), so the plan's recall task is gone and
`;scholarship books` reads. A Lorethew library lends by call letters
(the sign: "Use the Call Letters of a book to get it (GET). Look on
the shelves for a complete listing ... You are granted use of our
books (READ) ... Please return all books"): LOOK SHELVES prints the
table of titles and letters; GET <letters>; READ MY BOOK ("You get an
urge to open it up and read the contents."); OPEN MY BOOK; READ MY
BOOK again into the page reader, where a bare number turns to that
page ("Reading:  INTRODUCTION: ..."), "?" prints the help, a number
past the end answers "'17' is not a page in this book!" and Q closes
the book. Nothing but a number or Q goes out while the reader is open
(it takes anything else for a page), and Q never goes out outside it
(it is some other verb there). STOW MY BOOK — or PUT ... IN MY
<container> — returns the book: "You return the book to where it
belongs." No DROP.

Measured on a Paladin at Scholarship 2 in the guild library: four
books (13, about 3, 15 and 19 pages) took the skill to rank 4 at 24
percent in fifteen minutes; a book teaches per read, not per page
(the three-page story moved it as much as the thirteen-page
introduction), teaches nothing read again at once, and taught again
70 minutes later. So the script reads the shelves through, returns
each book, and after a lap that taught nothing waits `timer` minutes
(60 by default; the timer's true length is unmeasured). At mind-lock
the book is closed and returned and the script holds like `;attune`
(`once` exits). It stops on death or hostiles with the book returned,
waits out bleeding (the sign: "Please do not read a book while
bleeding"), and walks to the profile's `library` first (`library=`
overrides). Under `;train`: `"script": "scholarship", "args":
["books"], "skills": ["Scholarship"], "return_word": "return"`.
`;scholarship classes` — listening to classes at the town's nexus
rooms — is planned on #210 and not built.

## Out of scope in the first cut

A dialog for the plan (the file is the interface), a trainer per
skill (each new script is one task line away), conditions beyond
mindstate (time of day, rested-experience hours, a spell's duration),
and running two tasks at once. `;hunt` keeps its own buffs up and
recasts one to train a magic skill (its profile's `buffs` and
`train_casting`, [hunting.md](hunting.md); `;cast` runs that loop on
its own, standing still, with a POWER a minute for Attunement — the
gondola ride, the ferry, the wait at an altar, #225); a buff kept up under any
other trainer is still the orchestrator's to learn. Each is a plan key
and a branch away.
