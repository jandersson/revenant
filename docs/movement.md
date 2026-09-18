# The movement model automation assumes

Anything in revenant that walks — `;go2`, `;athletics`' ladder trips,
`;favors`' grotto run, every future traveler — goes through
client/game/walker.py, and this file records the mechanics it leans on,
with their evidence. The map itself is the community database
(client/game/mapdb.py, the elanthia-online lich map); this file is about
*moving* along it.

## Locating: uid first, title only as a guess

The game stamps every room with a `<nav rm>` uid; the map indexes
them, and the uid is the exact fix whenever the map knows it. Titles
collide — the captured live bug: three rooms titled "[The Crossing,
Eylhaar Bane Road]", where the title+exits guess picked the wrong
segment — so title matching (tie-broken by compass exits) is only the
fallback for unmapped uids. An unknown position is reported, never
guessed (walker.locate, pinned by test_go2.py).

## Arrival is a compass frame, verified by room

The engine emits one synthetic "compass" frame per room the game
describes (identical exits included, so back-and-forth between twin
rooms still signals); the walker treats the next frame as the move's
arrival signal,
then verifies the room itself — uid when the map knows it, normalized
title otherwise — against the route. Two structural rules, both from
captured bugs:

- **Drain stale compass frames before each step.** A leftover frame
  from a previous move once paired with the wrong step and desynced
  the whole walk (the double-frame bug; structurally prevented in
  walker.walk).
- **Stalls and off-course rooms stop the walk.** Never guess onward;
  the failure echo names the step, the command, and the room.

## Engagements: escape by burst, judge by the room

Moving or climbing out of a room auto-retreats first, and engaged
hostiles hinder that exactly like RETREAT (docs/combat.md holds the
range model and the captures). When a step stalls — for any reason,
not only when hostile state says so: the state can be empty while
engaged (#88, captured mid-fight) — the walker bursts retreat →
retreat → step through the game's type-ahead and judges success by
the room changing, not by the room emptying (the cave bear that
would not leave). One burst per step; a stall it cannot fix still
stops the walk. Spaced single retreats lose the race to re-advances
(the #72 cougar death, captured 2026-08-22). The one room the burst
skips is one whose compass shows `out` alone — a bank lobby, a shop —
where nothing engages and a retreat answers "You are already as far
away as you can get!" (#171, captured 2026-09-12 in the First
Provincial Bank when a parser fault, since fixed, hid the arrival);
there the stalled step is simply retried once.

## Climbs the game turns back

A climb edge can be refused for skill, not engagement: the game
weighs Athletics against the obstacle, and anything held or worn
counts against you. Captured 2026-09-11 at the felled tree west of
Crossing (map 6153 → 5705, the only edge to Knife Clan), a circle-1
Paladin with a handaxe in hand and plate on:

```
Your oak-hafted handaxe and plate vambraces make the climb more difficult.
You pick your way up the tree, but reach a point where your footing is questionable.  Reluctantly, you climb back down.
```

A second wording came on the retry, same shape, same ending:

```
You make your way up the tree.  Partway up, you make the mistake of looking down.  Struck by vertigo, you cling to the tree for a few moments, then slowly climb back down.
```

Going down has its own two, captured 2026-09-12 on the Arthe Dale oak
by a rank-10 climber:

```
You attempt to climb down the tree, but you can't seem to find purchase.
You start down the tree, but you find it hard going.  Rather than risking a fall, you make your way back up.
Trying to judge the climb, you peer over the edge.  A wave of dizziness hits you, and you back away from the tree.
```

Every climb the walker sends is a row in history.db's `climbs` table
(#159) — up, the refusal's kind or a stall, with the wording, the
Athletics rank and mindstate the state already holds, nothing asked;
`;climbexp stats` sums them per obstacle and rank band. Until the
walker knew them, a turned-back descent read as a stall:
fifteen seconds of waiting for an arrival, then the retreat burst,
"You are already as far away as you can get!" twice in a tree house,
and one retry. All four wordings are refusals now, so the retry comes
at once and a second refusal stops with the advice.

No room change follows, and each refusal sits the character down.
The walker reads the story while it waits for the compass frame, so a
refusal is recognised at once instead of after the 15-second stall:
it waits the refusal's roundtime out, STANDs (unconditionally: the
posture indicator lands a beat after the refusal text, and a STAND
gated on it read "standing", after which both STOWs answered "You
must stand first." and the climb "You must be standing to do that." —
captured), STOWs each item the first line names (the noun is the last
word; a worn piece answers with a harmless refusal), and climbs once
more. Those two posture refusals count as a turned-back climb too, so
a character who starts a step sitting is stood up rather than
bursted at. A second refusal stops the walk with the load and the
choices — shed it, train Athletics (`;athletics` lists the tree
itself as a rank 0–19 rung, though the Paladin above failed it at
rank 7 in plate), or take the long way — rather than "stalled". A
refusal that names nothing retries bare. The wordings above are the
fixtures; "climb back down" is the refusal signal, and other climbs'
wordings are unknown until captured (#157).

What decides a climb, per Elanthipedia's Athletics page: Athletics
ranks first, then Agility and Strength, then encumbrance, armor
hindrance and injuries; appraising the obstacle beforehand helps.
Where the wiki's rank band and a character's result disagree — the
tree is banded 0–19 and the Paladin above failed it at rank 7 —
`;climbexp` measures it: every attempt becomes a row in history.db's
`climbs` table (`client/game/climblog.py`, #159) with the outcome,
the game's wording, the hindering-items line, rank and mindstate,
INFO's stats, ENC, health and APPRAISE's answer, so the threshold is
read off the rows. `train=<stat>` spends one point first, in the
stat's training room the map tags (TRAIN twice, per the Time
Development Points page), with INFO before and after.

## Ways closed to the character

Some edges the map knows are gated by a circle or a guild the map
cannot see: from The Crossing, Northeast Customs the fastest way to
the Paladins' Guild library is `go trail` into the guild's back
promenade, and a circle-2 Paladin was answered "You're not
experienced enough to go there." and left where he stood (2026-09-18,
#209). The walker used to read that as a stall — retreat burst, one
retry, stop — and it ended the song he was playing. Now the wording
(`GATE_REFUSALS`) is a "closed" arrival: the edge goes into the walk's
closed set, "the way to <title> is closed to you (...) — going round"
is echoed, and the route is planned again from where he stands with
that edge excluded (`MapDB.path(..., closed=)`), up to three times on
one walk. No retreat, no retry. An exit the game cannot find ("I
could not find what you were referring to.", "You can't go there") is
closed the same way. A climb turned back after its one
retry is closed the same way (#211): the walk says what would help
and goes round if the map has another way — the gondola over the
Chasm — and ends only when it has none.

## Gates the map itself writes

Some travel times are Ruby for Lich to evaluate at routing time —
`;e unless DRSkill.getmodrank('Athletics') >= 540 then nil else 0.2
end` on the Obsidian Pass branch into the Chasm — and nil is no edge:
that is how Lich's go2 keeps a low character off a climb. The walker
priced every such edge at a plain step and sent a circle-5 Paladin
with 37 ranks up that branch, turned back twice (2026-09-18, #214).
Now `mapdb.gate_of` reads the expression into a Gate (the skill and
its least rank, the guild, the circle, the edge's price once open)
and `MapDB.path` drops a gated edge the character does not pass,
judged against the exp window's ranks (`walker.character_ranks`; a
skill the window has not listed is rank 0). The parser does not yet
know the character's guild or circle, so a Thief-only door or the
circle-30 Master's Den stays shut for everyone until it does.
Conditions the walker cannot judge — a premium portal, the Riverhaven
Thieves' password, Ilithi citizenship (#215), a known spell — close
the edge outright: a gate is a reason to be careful, not optimistic.
Fixed facts are settled when the expression is read: the walker is
its own bescort where it rides, it walks seen (`invisible?` is
false, so the Crossing's Northeast Customs gate stays open), and this
is DragonRealms Prime (`XMLData.game == 'DRF'` is false, which shuts
the DRF-only twin of the Obsidian Pass guard house). When the only
way is gated the walk stops before its first step and says which
gate and what the character holds: "the route needs Athletics 540
(you have Athletics 37)".

## Edges the map can and cannot walk

`wayto` commands are game commands, except embedded lich Ruby
(";e ..."). Simple sequences of fput/move string literals translate
directly to plain commands (754 of the map's 1087 scripted edges at
last count); `waitrt?` drops out because the walker waits out
roundtime around every command anyway. Anything with logic
(start_script, UserVars, conditionals) stays untranslatable, and the
router routes around it or reports "no walkable path"
(mapdb.translate_embedded / mapdb.walkable).

Routing runs on a networkx DiGraph of the walkable edges (#79) —
built once per load, ~18.5k rooms / ~41.4k edges. The translatable
`;e` edges MUST be in the graph: whole areas (the Segoltha strand
among them) hang off simple scripted edges, and a graph that drops
every `;e` partitions them away — that was the 1429↔10171
"unreachable" mystery, resolved 2026-08-23.

Routes are weighted by the map's `timeto` travel times (Dijkstra; a
missing value costs a plain 0.2s step, a Ruby value is a gate — see
"Gates the map itself writes"), so they optimize
minutes, not hops. Rooms on the settings avoid list (`avoid_rooms`,
;go2-style targets; the #72 cougar grounds by default) carry an
hour's penalty on entry: travel detours around them whenever a clean
route exists, and otherwise announces the crossing before the first
step — the cougar cliffs are a corridor on the real map, so routes
through them warn rather than pretend safety. `;go2 direct <target>`
skips the list for one trip.

## Rides: the Faldesu ferry and the Obsidian Pass gondola

The Crossing and Riverhaven are joined only by the Faldesu ferry: the
map's two edges between North Road, Ferry (1385) and Riverhaven,
Ferry Dock (470) are `start_script('bescort', ['faldesu', ...])`, a
call to dr-scripts' escort script, and until 2026-09-18 the walker
answered "no walkable path" for the whole town (#205). The walker now
rides it (`mapdb.ride_of` names the route — only an edge that *is*
the call; the Marsh's swim edges name the route inside a branch and
have no dock — and `walker.ride_ferry` boards), after bescort's
`take_rh_ferry`, with every wording captured on the first ride
(2026-09-18, Cecil, North Road → Riverhaven):

1. GO FERRY with the ferry out: "[Assuming you mean the ferry His
   Daring Exploit.]" then "I could not find what you were referring
   to." The walker waits for "You can see the ferry "Her Opulence"
   approaching the dock." / "The ferry "Her Opulence" pulls up to the
   dock." and tries again (bescort's other two wordings, "not here"
   and "stuck here until the next one arrives", stay in the table).
2. GO FERRY with the ferry in: "The Captain stops you and requests a
   transportation fee of 30 lirums as you board the craft." and the
   room is the ferry ([Her Opulence], "Obvious paths: none"). Boarding
   is that room change — the compass frame — not a wording: with no
   lirums on you the captain says "Hey," he says, "You haven't got
   enough lirums to pay for your trip.  Come back when you can afford
   the fare." and then "The Captain frowns.  "But I see you're pretty
   young and don't have the sense to keep enough coins on ya fer
   emergencies, so I'll just add it to yer debt." / "[Your debt to the
   province of Therengia is being increased by 30 lirums.]", and you
   are aboard all the same (the first ride stopped the walk on that
   refusal while the character stood on the deck). The fare is in
   lirums on both banks; a refusal that leaves an older character on
   the dock is uncaptured, and the walker stops on "afford the fare"
   only when no room change followed.
3. Aboard: "Next departure in one minute!", "All ashore who's going
   ashore!", "Cast off!", "You feel the ferry shudder slightly as it
   shoves off.", the quarter-way and half-way lines, "You are nearing
   the docks.", then "The ferry "Her Opulence" reaches the dock and
   its crew ties the ferry off." — the walker's cue for GO DOCK, which
   lands on [Riverhaven, Ferry Dock] with the usual compass sync and
   room check. The crossing took about four minutes.

The waits are generous (fifteen minutes each, a ferry's round trip)
and say what they wait for; the edge costs five minutes in the
router, so a land route wins where one exists. The ferries are Her
Opulence and His Daring Exploit (Elanthipedia: Riverhaven Ferry
Dock). The other bescort routes (airships, barges, the Segoltha rope)
stay unwalkable; the Faldesu swim the map also offers (The Marsh,
Stone Road ↔ Riverhaven, Stone Bridge) is bescort's choice only at
Athletics 140.

Alfren's Ferry over the Segoltha (The Crossing, Alfren's Ferry 957 ↔
Southern Trade Route, Segoltha South Bank 1904; bescort's `ferry`
route, in the `if` form) is the same ride with other words, captured
on the first crossing (2026-09-18, the ferries Hodierna's Grace and
Kertigen's Honor): with the ferry out GO FERRY answers "[Assuming you
mean the ferry Hodierna's Grace.]" and "There is no ferry here to go
aboard."; the dock's story then reads "You can see that the ferry
Kertigen's Honor is nearing the dock." and "The ferry Kertigen's
Honor pulls into the dock."; boarding answers "The Captain stops you
and requests a transportation fee of 35 kronars as you board the
craft." and "You hand him your kronars and climb aboard." (the ferry
is the room [Kertigen's Honor]); "You feel the ferry Kertigen's Honor
shudder slightly as it shoves off." and "You are nearing the docks."
come on the way. bescort's other answers ("The Captain gives you a
little nod", "The ferry has just pulled away from the dock") stay in
the tables uncaptured. While a ferry is out the walker tries GO FERRY
again every minute. It is the way south
to Leth Deriel and Shard: the map's other way, the Riverbank tunnel,
runs through a silverfish ground to a panel the game could not find
("I could not find what you were referring to.", 2026-09-18 — the
walk stalled there and the character was bitten to 64 percent before
he was walked out), so the mudflats are on the avoid list and that
answer is a closed edge.

The Obsidian Pass gondola (Obsidian Pass, Platform 2249 ↔ 2904) is
the second ride (#211). The map writes it in the `if
Script.exists?('bescort')` form with GO GONDOLA as the else, so
`ride_of` accepts that form for this route, and the walker follows
bescort's `ride_gondola`, every line captured on the first ride
(2026-09-18): GO GONDOLA lands in the cab ([Gondola, Cab North], a
room, so a compass frame) or answers "There is no wooden gondola
here.  You'll have to wait for it to come back around.", in which
case it waits for "The gondola stops on the platform and the door
silently swings open." (after "The gondola arrives at the center of
the chasm, and keeps heading north." and "The gondola swings closer
to the platform.") and tries again; aboard, it sends the direction
the edge names ("You go south." into [Gondola, Cab South], as bescort
does), "The door swings shut of its own accord, and the gondola
pushes off.", and it waits for "With a soft bump, the gondola comes
to a stop at its destination.", then OUT is the step's move onto the
far platform ("You go out."). The wiki: three minutes across, two at
each platform, LOOK GONDOLA shows its progress, and the way under it
wants 550 ranks of Athletics — the first walk was routed under it
until the branch's refusal ("A wave of dizziness hits you, and you
back away from the branch.") closed that way and the route went
through the gondola.

## Finding a wandering NPC

A wandering NPC — Riverhaven's Tall Human Peddler, who sells the copper
zills — has no room on the map, so `;go2` cannot reach him (#207).
`;seek <noun>` walks the streets instead: from where the character
stands (or a `from=` target), `client/game/seek.py` builds the same
loop `;attune` power-walks (a chain of nearby rooms joined by plain
compass moves in both directions, out and back, `rooms=` long) and the
script walks it lap after lap (`laps=`, three by default) with the
walker, reading every arrival's listing for the noun. The listing is
the parser's `room_objs`, the whole text of the "room objs" component
— "You also see a news stand with a grinning imp on it, a festive
meeting portal, a simple bench, the Temple, a mud-splattered chest, a
uniformed representative and a young alchemist student." (Riverhaven's
Town Square, 2026-09-18) — split on its commas and "and", and the
entry holding the noun as a whole word is the answer ("a tall human
peddler" for "peddler"); the room's players are read the same way. On
a session whose parser predates `room_objs` the script LOOKs on each
arrival instead. Found, it stops in that room and says so, and nothing
more: the asking and buying are the operator's. Not found, it stops
at the start after the laps. Another player's room is passed through.

## Pacing

Every step waits out roundtime before moving (Script.waitrt: the
announced end on the server clock minus the last prompt's server
time). Travel-climb *experience* has its own 45–60s award timer — a
training concern, not a movement one: docs/experience.md owns it, and
;athletics paces to it.

## Twin rooms: the map lists some places twice

The community map holds pairs of entries for one physical room — same
title, same exits — with only one of the pair carrying the game's uid.
Captured 2026-09-04 (#137): a walk planned through room 670 (Middens,
Gravel Way, no uid) arrived to `<nav rm='200009'/>`, which the map
files under 13100, its twin; the exact uid check declared the walker
off course while it stood in the right room. The map has 67 such twin
groups, 39 with a uid-less twin, and it refreshes wholesale, so the
walker tolerates them instead of the data being fixed:

- `MapDB.same_place(a, b)` — twins share a uid, or share a title and
  an identical wayto dict. Two rooms that merely share a title (roads)
  are not twins.
- The arrival check accepts a twin of the planned room.
- When a room links to both twins with the same command, the graph
  keeps only the uid-bearing edge, so plans name the id the game will
  report.
