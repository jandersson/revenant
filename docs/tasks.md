# Tasks

A task is an errand an NPC gives for coin: ask a task giver, accept inside thirty seconds, do it, and the one you deliver to pays. `;task <giver>` runs a delivery end to end; the other kinds are declined until their wordings are captured (#505).

## Using ;task

```
;task cormyn         ask Cormyn; a kind in the profile's task_kinds is accepted, the rest declined
;task                carry on the task in the journal (after a stop, or a shop's night)
;task item=basket    ... naming the item when the record of the accept is gone
;task return         finish the step in hand and stop
```

- The profile's `task_kinds` (default `delivery`) decides the accept; the offer is judged inside its thirty seconds.
- A delivery's item is stowed for the walk and taken out again at the recipient, who is found through the givers' table in the model.
- A walk that ends short is said with the reason to try: a shop shut for the night (wait a game hour), or the barge the walker lacks (#506). `;task` again from there carries on.

## The flow

```
ask <giver> for task      the offer, and a 30 s window
accept task               take it (decline task, or silence, refuses it)
task                      the journal: the task in hand and the tally of those done
give <item> to <person>   a delivery's end: the recipient pays
```

| Kind | What it is |
|---|---|
| delivery | carry an item from the giver to a named person, often in another province; the recipient pays, there is no walk back |
| item recovery | kill a named creature in a named area until one drops the item; no count, no bound |
| kill | a count of a creature in an area, then back to the giver |
| boss | hunt an area until the named boss spawns, kill it |
| foraging, skinning | bring back a forageable or a creature's skin |
| searching | kneel and search an area until the item turns up |

## What the game says

- The offer ends with `[You may accept by typing ACCEPT TASK, or decline by typing DECLINE TASK.  You have 30 seconds to decide.]` — parse and decide before the ask, not after.
- Silence past the window: `"Very well, I guess you do not wish to help me."`
- Asking again inside the ten-minute cooldown: `"I am sorry, you must wait before I can give you a task."` Declining, letting it lapse and cancelling (`ask <giver> for task cancel`) all start the same ten minutes.
- A delivery's end: the recipient thanks you by name and `hands you 314 Lirums`; `task` then reads `You are not currently on a task.`

## What bites

- **The far province's coin.** Ferries and barges want it (the Faldesu ferry 30 lirums, the Throne City barges 120 each way), and a plain `;bank` changes it straight back. `;bank lirums=300` buys and keeps it.
- **A shut door.** Shops close at night: `You stop as you realize that the marble house is closed for the night.` A game hour is fifteen real minutes, so wait for sunrise rather than give up; `;go2` only reports a stall on it.
- **Rides the walker lacks.** The Riverhaven–Throne City barge is boarded by its name (`go riverhawk`) at the Salt Yard dock and left with `go dock`; `;go2` carries you to the dock and from the far one (#506).
- **The giver's pool.** Cormyn offered the same far item recovery twice before a delivery; a script's allowed kinds and areas decide the accept.

Givers and their task kinds are on Elanthipedia's Task page; the Crossing has Cormyn (House of Heirlooms), Amfitro (Viper's Nest Inn) and the guild leaders. See [movement.md](movement.md) for the walker and [bibliography.md](bibliography.md) for the sources.
