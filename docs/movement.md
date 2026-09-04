# The movement model automation assumes

Anything in revenant that walks — `;go2`, `;athletics`' ladder trips,
`;favors`' grotto run, every future traveler — goes through
client/walker.py, and this file records the mechanics it leans on,
with their evidence. The map itself is the community database
(client/mapdb.py, the elanthia-online lich map); this file is about
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
(the #72 cougar death, captured 2026-08-22).

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

Routes are weighted by the map's `timeto` travel times (Dijkstra;
missing/Ruby values cost a plain 0.2s step), so they optimize
minutes, not hops. Rooms on the settings avoid list (`avoid_rooms`,
;go2-style targets; the #72 cougar grounds by default) carry an
hour's penalty on entry: travel detours around them whenever a clean
route exists, and otherwise announces the crossing before the first
step — the cougar cliffs are a corridor on the real map, so routes
through them warn rather than pretend safety. `;go2 direct <target>`
skips the list for one trip.

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
