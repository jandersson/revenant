# Tasks

A task is an errand an NPC gives for coin: ask a task giver, accept inside thirty seconds, do it, and the one you deliver to pays. `;task <giver>` runs a delivery, a search, an item recovery, a foraging or a skinning task end to end; the other kinds are accepted and handed to you until their wordings are captured (#505).

## Using ;task

```
;task cormyn         ask Cormyn and accept the offer; a kind in the profile's task_declines is declined
;task                carry on the task in the journal (after a stop, or a shop's night)
;task item=basket    ... naming the item when the record of the accept is gone
;task any            walk to the nearest giver whose ten minutes are up and ask
;task any radius=40  ... a giver at most 40 steps away
;task loop           task after task until one ends short (radius= too)
;task history        what each giver has offered: the kinds, where, the pay, the minutes
;task return         finish the step in hand and stop
```

- Every offer, taken or declined, is a row in history.db's `tasks` table: the giver, the kind, the item, the creature and the area or recipient. The end adds the pay, the time and, for a search, the room it was found in and on which SEARCH. `;task history` reads them back per giver and kind. `uv run python tools/task_backfill.py` reads the offers made before the table out of the game logs.

- Every offer is accepted inside its thirty seconds unless the profile's `task_declines` names its kind. The script runs a delivery, a search and a recovery; any other kind it accepts, records and hands to you, saying the offer.
- A recovery runs `;hunt task`: the area's rooms are the ground, the profile's weapons fight whatever engages, and the hunt ends when a kill's death line drops the item (`As grey poloh'izh dies, you see it drop a worn gauntlet onto the ground.`); it picks the item up and goes home, then `;task` carries it to the giver. A profile with no weapon gets the recovery handed over: a spell caster's kill is not built.
- A skinning task runs `;hunt task` on the bestiary's nearest ground for the creature: every kill skinned, the hides kept loose (no bundle, since each GIVE counts one), until the count. Then `;task` gives them one at a time.
- A delivery's item is stowed for the walk and taken out again at the recipient, who is found through the givers' table in the model, or, for a wanderer with no room (an old blind beggar in The Crossing), by `;seek` through that town's streets, or along every room titled its place ("Researcher Trelmik in Reshalia Trade Road"). A search kneels and searches each room of the area in turn, waiting out every roundtime (about twelve seconds), picks up the find, and carries it back to the giver.
- A shop shut for the night is waited for: `;task` tries the door each game hour (fifteen real minutes), eight times at most. Any other walk that ends short is said; `;task` again from there carries on.

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
- Asking again inside the ten-minute cooldown: `"I am sorry, you must wait before I can give you a task."` Declining, letting it lapse and cancelling (`ask <giver> for task cancel`) all start the same ten minutes. `;task` keeps each giver's clock and says the minutes left rather than ask inside them.
- The same answer from a giver never asked: an offer taken elsewhere a moment before (36 s, not 93 s). `;task loop` leaves two minutes between asks.
- A delivery's end: the recipient thanks you by name and `hands you 314 Lirums`; `task` then reads `You are not currently on a task.`
- An item recovery's end: GIVE the item to the giver, who answers with the same thanks and `hands you 777 Kronars` (Cormyn's worn gauntlet).
- Foraging and skinning offers share a shape: `I need 13 nuloe stems.` against `I need 6 skins from the province's storm bull population. ... I think they have a storm bull hide.` Each GIVE counts as one item, so a bundle counts as one.

## What bites

- **The far province's coin.** Ferries and barges want it (the Faldesu ferry 30 lirums, the Throne City barges 120 each way), and a plain `;bank` changes it straight back. `;bank lirums=300` buys and keeps it.
- **A shut door.** Shops close at night: `You stop as you realize that the marble house is closed for the night.` `;go2` says the shop opens at sunrise and stops; `;task` waits for it.
- **Rides the walker lacks.** The Riverhaven–Throne City barge is boarded by its name (`go riverhawk`) at the Salt Yard dock and left with `go dock`; `;go2` carries you to the dock and from the far one (#506).
- **A skin, not a part.** A bare SKIN takes a creature's part when it has one (a storm bull's jagged horn). A skinning task's hunt sends `ARRANGE <corpse> FOR SKIN` first, and the SKIN after it cuts the hide ([hunting.md](hunting.md#arrange-which-piece-skin-takes)).
- **The giver's pool.** Cormyn offered the same far item recovery twice before a delivery; a script's allowed kinds and areas decide the accept.

Givers and their task kinds are on Elanthipedia's Task page; the Crossing has Cormyn (House of Heirlooms), Amfitro (Viper's Nest Inn) and the guild leaders, and an Estate Holder representative beside Fang Cove's EXIT portal gives skinning tasks only. See [movement.md](movement.md) for the walker and [bibliography.md](bibliography.md) for the sources.
