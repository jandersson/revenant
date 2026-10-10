# Movement

`;go2 <target>` walks the character anywhere the community map knows, by the fastest route. Every script that travels (`;hunt`, `;athletics`, `;heal npc`...) uses the same walker, so what holds here holds for them.

## Using ;go2

```
;go2 1234            a map room id
;go2 bank            a map tag (bank, herbalist, npchealer, ...)
;go2 herald street   part of a room title
;go2 home            the profile's home room
;go2 safe            the training plan's first safe room
;go2 direct <target> ignore the avoid list for this trip
;go2                 where the map thinks you are
;go2 update          download a fresh map
```

- The first use downloads the map (~13 MB) into `~/.revenant/mapdb/`.
- `;stop go2` stops the walk where it stands.
- To find a wandering NPC the map has no room for, use `;seek <noun>`: it loops the nearby streets until a room lists it, then stops there.

## What the walk does for you

- **Stands up first** if you are sitting or kneeling, and reads the answer: overburdened, it stops with "bank or stow the load first" instead of walking on seated; unbalanced, it waits a moment and stands again.
- **Waits out roundtime** before every step; a step the game answers "...wait N seconds." is sent again once that roundtime is over.
- **Searches for hidden ways:** a map edge that SEARCHes first repeats the SEARCH (15 at most) until something is found — one often finds nothing.
- **Escapes an engagement:** a step that stalls gets RETREAT, RETREAT and the step again, once.
- **Checks every room** it lands in against the route, and stops rather than guessing when it is lost.
- **Goes round a closed way:** a guild or circle gate ("not experienced enough"), an exit the game cannot find, or a climb that failed twice is dropped from the route and the walk replans from where you stand. A gate stays dropped for every later walk until the session is relaunched.
- **Leaves a room the map has no exits for** by trying OUT and the compass exits, and remembers the way in `~/.revenant/mapdb/local.json`.

## Rides

| Ride | Between | Fare |
| --- | --- | --- |
| Faldesu ferry | the Crossing's North Road and Riverhaven | 30 Lirums; short of it, a young character rides on debt and anyone else is turned away |
| Alfren's Ferry | the Crossing and the Segoltha's south bank (the way to Leth Deriel and Shard) | 35 Kronars |
| Obsidian Pass gondola | the two platforms over the Chasm | free |
| The Jolas | Mer'Kresh's Wharf End and Hara'jaal's Sumilo Dock (it waits up to an hour for the ship) | free |
| Sea mammoths | Fang Cove's dock and Ratha's Shore Walk (the massive one), or Acenamacra's pier (the tall one) | free |

The walker boards, waits for a ferry that is out (up to fifteen minutes), and steps off at the far side. Turned away for the fare, it runs `;bank keep=200 lirums=200` (the coin the captain named, from the nearest teller and the money-changer) and plans the walk again, once a walk. A ride costs five minutes in the planner, so a land route wins where one exists. The other escort routes (airships, barges) are not walkable.

A mammoth is joined (`join sea mammoth`) and sets you ashore itself. A Premium character walks from the Crossing to Ratha by the meeting portal into Fang Cove and the mammoth; Fang Cove's exit portal only returns you to the town you came in by: a walk from outside never plans through it, and inside the walker plans only the exit to the town it saw you enter from (unknown after a relaunch, when a wrong landing plans again from there).

A character with an Estate Holder ring (the profile's `estate_ring`, e.g. `copper band`, worn) is PUSHed to Fang Cove when the walk from there is far shorter — about 300 steps or more — or the only one; from inside Fang Cove a PULL returns to the room the walker last pushed from. The walker STUDYs the ring first, since each verb is charged once an hour. PUSH works only outdoors; refused, the walk goes on foot. After a PUSH no exit portal is planned: it returns you to the town you last came in by.

A Moon Mage standing at a Grazhir shard crosses the Astral Plane to another with `;astral <shard>` (`;astral list` names the shards learned): Moongate in, the pillars, Moongate out, about four minutes. `harness=` sets the mana held (100 by default).

Ratha to Hara'jaal is the Tasia'zaul, from the lower Uasin Dock behind a guard's bribe: `;harajaal` gets you down there (`;harajaal quest` on a first trip). The ship itself is not a walker ride yet.

Hara'jaal's Glaren Kweld grass is dozens of rooms under one title, three of them on the map. The walker crosses it the way bescort does: down the slope, then NORTHEAST until a room lists a rock; out, NORTHEAST until a slope, then CLIMB SLOPE. A walk begun lost in the grass goes NORTHEAST to the rock first. With a poloh'izh in the room each move goes as RETREAT, RETREAT and the move.

The Riverhaven–Throne City barge is ridden the same way: at the Salt Yard's barge dock or Throne City's Stone Docks the walker waits for a barge, boards it by name (`go riverhawk`, `go glory`), pays the 120 lirums, and steps off at the far dock. Fifteen minutes is the longest it waits.

## Rooms to avoid

`avoid_rooms` in `~/.revenant/settings.json` lists `;go2`-style targets the planner detours around. The default is the cougar grounds. Ratha's Bazaar, a maze whose ways shift, is always avoided. When no clean detour exists, the walk says so before the first step and goes through. `;go2 direct` skips the list once.

## Climbs

A climb depends on Athletics ranks, then Agility and Strength, then load, armor and injuries.

- When the game turns a climb back, the walker stands, stows whatever the game named as hindering, and tries once more.
- A second refusal closes that way and replans. If there is no other way, it stops and names the load and the choices: shed it, train Athletics (`;athletics`), or go the long way.
- Climbs the map gates by skill ("needs Athletics 540") are skipped when your ranks fall short, judged from the exp window. If the only way is gated, the walk stops before it starts and says what it needs.
- `;climbexp` records each climb attempt so you can see where your ranks stand against an obstacle.

## Caveats

- Circle and guild gates are unknown until the game refuses one; the walker learns them per walk, not permanently.
- Edges that need a password, citizenship or a spell are treated as closed.
- The towns' meeting portals into Fang Cove open only when the character's profile says `premium` (the account has Premium).
- From Fang Cove the walk leaves by the EXIT portal (`go portal`), which returns you to the town you entered from; a landing elsewhere than planned replans from there.
- Inside a sub-room (a Fang Cove tent) the game reports the room outside's id; the walker goes by the title there.
