# The hunting model ;hunt assumes

`;hunt` fights a ground in a loop from a per-character profile: walk
there, ready weapon and stance, attack until the room empties, skin and
search each kill, move along the ground, come home on a limit. This
file records what the script believes about the game and which of it
is captured versus assumed — the fixtures in `client/tests/test_hunt.py`
pin the same wordings. The fight itself follows [combat.md](combat.md).

## The profile

One JSON file per character, `~/.revenant/profiles/<name>.json`, edited
from File → Character Profile… (the dialog builds itself from
`client/game/profile.py`'s FIELDS, so the file and the form never disagree).
It holds what no script should hard-code:

| setting | what the loop does with it |
| --- | --- |
| hunting_ground | a `;go2` target; every room it resolves to is the ground, walked to at the start and cycled when a room runs empty |
| prey | the noun ATTACK gets; empty swings at whatever engages you |
| home | a `;go2` target walked to when the hunt ends |
| weapon, weapon_container | `GET my <weapon> [FROM my <container>]` before the first swing; it stays in hand when the hunt ends (stowed, it parries nothing — 2026-09-12), the container is only where it is fetched from, and where it goes for the moment the first skin of a run is bundled |
| stance | `STANCE SET <args>` once, before the first swing |
| skin, skin_knife | `SKIN <corpse>` after each kill; a named knife is fetched before and stowed after |
| loot_container | where skins and non-gem finds go (`PUT my <item> IN my <container>`, else `STOW my <item>`) |
| gem_pouch | finds are tried into the pouch first; what the pouch refuses is stowed like loot |
| bundle | skins go onto a bundling rope worn as a lumpy bundle: one kept in the loot container is worn before the first swing, the first skin of a run starts one from the rope in that container, every later skin goes straight into the worn bundle as SKIN cuts it (the hand tags are the judge), and `;skins` sells it. No rope: said once, skins stowed loose |
| buffs | self-cast spells kept up through the hunt: each is PREPAREd and CAST before the weapon is drawn and again, before a swing, whenever the Spells window no longer lists it (a parser without that window re-casts every ten minutes); a refusal drops the spell for the run, said once |
| train_casting | a magic skill ("Augmentation"): while it sits below mind-lock and mana is above the floor, the first buff is recast between swings, at least twenty seconds apart, with the mana fed rising by two each cast from the minimum until the game warns of strain (or a cast fails), then held one step under — a failure at the minimum ends the training casts for the run; at lock, back to casting only when the buff runs out |
| health_floor | below it: the burst escape (retreat, retreat, first exit), then home |
| wound_floor | a severity name; HEALTH is asked after each kill and whenever the health bar drops, and a wound that bad or worse anywhere (external, scar, internal, internal scar) breaks off like the health floor. Empty never asks. Model: [wounds.md](wounds.md) |
| train_skills | the hunt ends when every one of them sits at mindstate 34 in the exp window |
| max_kills | a fuse; 0 hunts until stopped, locked or the ground empties |

`;hunt return` (typed while it runs) ends the loop before the next
swing and walks home; `;stop hunt` quits where it stands (the rule for
every script: the typed word is the graceful end, `;stop` the abrupt one).
`;hunt here` skips the walk to the ground; `;hunt profile` prints the
profile it would use.

## What is captured and what is assumed

Captured (the 2026-08-22 traffic behind combat.md, and the first live
`;hunt` on 2026-09-05 — a circle-1 Paladin against ship's rats at
Barana's Shipyard):

- the kill lines "The cougar slowly tips over and falls down." and
  "The ship's rat falls to the ground and lies still." — the corpse
  noun is the word before the kill phrase ("rat"). The first run knew
  only the cougar wording, missed the rat's kill and never skinned;
- "The ship's rat is already quite dead." — a corpse soaking swings,
  which the loop disposes of (skin, search) like a fresh kill, and
  after two more such answers declares the room clear; the noun can
  be several words;
- the corpse's `<crtrStatus>` keeps `hostile="1"` and adds `dead="1"`
  — the parser now drops it from the hostile set, which is what let
  the first run swing at the body five times;
- "There is nothing else to face!  What are you trying to attack?" —
  the room is clear even while the hostile state lags;
- SEARCH <corpse> removes it and clears the noun.

Captured on the second live hunt (2026-09-12, the same character and
ground, seven kills):

- two skin successes: "With preternatural poise, you work loose a
  sterling example of a rat pelt from the rat carcass." and "Working
  deftly, you skillfully remove a rat tail from the remains of a ship's
  rat.  The task is difficult, but the rewards are worth it." — the
  item is the noun before "from". The tail's line landed after the
  skin's roundtime and outside the table, so nothing stowed the tail
  and the next three skins answered "You must have one hand free to
  skin." That answer now stows what the parser's `left_hand` names
  (or STOW LEFT) and skins once more;
- "The ship's rat has already been searched for that!" and "You
  should probably wait until a ship's rat is dead first." — the corpse
  is gone and its noun found a live rat; both count as a gone corpse,
  nothing to report;
- ATTACK from beyond melee advances first — "You aren't close enough
  to attack." / "You begin to advance on a ship's rat." — and a second
  ATTACK meanwhile only answers "You are already advancing on a ship's
  rat." The three ranges are [combat.md](combat.md)'s; the loop now
  waits for the "melee range" line (yours or the creature's) before
  the next swing, up to ten seconds;
- **every swing and kill line arrives inside `<pushStream
  id="combat"/>`**, in this log and in every hunt log since
  2026-08-22. The engine routes that block as the `combat` stream, the
  main window shows it, but the answer collector read the story stream
  alone — so no kill was ever seen from ATTACK's answer. The skins that
  did happen came from the corpse-swing path ("is already quite dead"
  is a plain story line), kills were never counted, and the empty-move
  counter, which only a counted kill resets, ran out after eighteen
  room moves: both instances that day ended "ground empty" among live
  rats. `probe.collect` now reads the story and the combat stream
  (`STORY_STREAMS`).

Assumed, pending capture (each one is a keyword table in the script,
and any answer outside the table is echoed as
`hunt: unrecognized ...` so it can be reported and pinned):

- the other kill wordings ("goes still", "collapses", "keels over");
- the other skinning answers — success is also read as "obtain…" /
  "you skin", with the item's noun the last word of "obtaining a rat
  pelt"; "nothing to skin with" / "bare hands" turns skinning off for
  the run; "ruin" / "botch" counts as a failed skin;
- the search answers — "You find …" names what turned up, "find
  nothing" / "nothing of value" is an empty corpse;
- that a searched-up item must be picked up (`GET <item>`) before it
  can be pouched or stowed, and that a pouch refuses non-gems with a
  "can't" wording;
- that the skin lands in the free hand, so `STOW LEFT` is the fallback
  when the answer names no item.

Rats at Barana's Shipyard (the first-cut ground, map tag `rats`, rooms
6046–6054) are level-1 creatures with no loot; their skins are a rat
pelt, tail or bones (Elanthipedia: Rat). SKIN wants an edged weapon in
hand or a worn belt knife (Elanthipedia: Skinning) — a handaxe does.
The gem pouch page describes `FILL POUCH WITH <container>` for bulk
moves; the loop pouches one find at a time instead.

## Another player's room

A room another player is already hunting in is theirs — the
community's unwritten rule, and the operator's (2026-09-12, after
`;hunt` fought rats in a shipyard room with two other players in it).
Sharing a spawn takes their kills. The parser keeps the room's
players from the `room players` component ("Also here: Sky Knight
Kaldean who is darkened by an unnatural shadow, Sand Flower Cyranth,
Cecil and Penello." — the name is the last word before any "who is",
titles before it), and the loop reads it on every arrival in a room
of the ground: a player already there makes it theirs, the loop says
so and moves on to the next room without a swing, and a ground with
someone in every room is left to them ("ground taken"). Someone who
arrives while the fight is on has come into our room and is not the
rule's concern. `;athletics` does the same at a rung and at each
rotation stop: their spot, the next-best rung. Claude driving by hand
checks the room first.

## Bundling and selling skins

Loose skins sell one SELL at a time; a bundle sells as one item and
holds up to 200 ([Bundle command](https://elanthipedia.play.net/Bundle_command)).
The rope is free at the tanner's, the bundle starts from a rope in one
hand and a skin in the other, every further skin is one BUNDLE with
the bundle held, and the tanner hands the rope back with the coins.
Captured 2026-09-12 at [Falken's Tannery](https://elanthipedia.play.net/Falken's_Tannery)
in the Crossing (map 8266, tag `crossing tannery`; every tannery on
the map carries `tannery`), the whole pass by hand with seven rat skins
from the day's hunt:

```
> ask falken for rope
The tanner Falken says, "Sure, I have a piece here you can have for free."
The tanner Falken hands you a rope.
> get my pelt from my sack
You get a rat pelt from inside your canvas sack.
> bundle
You bundle up your rat pelt with your bundling rope.
> get my tail from my sack
You get a rat tail from inside your canvas sack.
> bundle
You carefully fit a rat tail into your bundle.
> ask falken to appraise my bundle
You ask the tanner Falken to appraise a lumpy bundle.
The tanner Falken looks the lumpy bundle over carefully, then whispers, "I can give 111 Kronars for it."
> sell my bundle
You ask the tanner Falken to buy a lumpy bundle.
The tanner Falken ponders over the bundle for a while, then hands you 111 Kronars.
Tanner Falken says, "And there's your rope back again."
```

INFO agreed: 4778 → 4889 copper. The rope lands in the free hand as a
`bundling rope` (the hand tags name it `rope`), the bundle is a `lumpy
bundle` in the hand that held the first skin, and none of the commands
cost roundtime.

The game's own BUNDLE HELP (quoted on the wiki page) settles where the
bundle lives while hunting: "Bundles can be worn", and "when skinning,
pelts are automatically bundled into any held or worn bundle" that is
not full and has auto-bundling on — the default for a lumpy bundle
(ADJUST BUNDLE switches it; a tied bundle defaults to off, and TOGGLE
BUNDLE <location> picks where it is worn). So the profile's `bundle`
setting has `;hunt` wear the bundle and expect the skinning hand to
stay empty after SKIN; a skin that still lands in hand gets one BUNDLE,
and if it stays the bundle is taken as full and the run stows loose.
The first skin of a run, with no bundle yet, starts one: weapon into
its container, rope out, BUNDLE, WEAR, weapon back. `;skins` walks to
the nearest `tannery`, REMOVEs the bundle, SELLs it from the hand,
keeps the rope, and stays there (`;skins back` walks back: the first
scripted run returned to the rats with the weapon stowed). The first bundled hunt ran the same
evening and captured the rest:

```
> get my rope from my sack
You get some bundling rope from inside your canvas sack.
> bundle
You bundle up your rat pelt with your bundling rope.
> wear my bundle
You sling a lumpy bundle over your shoulder.
> skin rat                          (the next kill, bundle worn)
With preternatural poise, you work loose a sterling example of a rat pelt from the rat carcass.
You carefully fit a rat pelt into your bundle.
> remove my bundle                  (;skins, at the tannery)
You sling a lumpy bundle off from over your shoulder.
> sell my bundle
The tanner Falken ponders over the bundle for a while, then hands you 33 Kronars.
```

The auto-bundled skin shows in the hand tags for a moment and is gone
by the time the answer window closes, so the empty hand is what the
script reads. Two pelts fetched 33 Kronars where seven skins had
fetched 111. A later run began with the bundle still worn from the
run before, and `GET my bundle FROM my sack` missed it ("What were
you referring to?"); the operator's suggestion, TAP, answers "You tap
a lumpy bundle that you are wearing." without moving anything, and "I
could not find what you were referring to." for none, so the hunt
asks TAP first and fetches only what is not already worn. Still open:
what `;skins` should do with loose skins in the sack — it sells the
bundle alone.

## Buffs under the hunt

A Paladin's first spells are self-buffs, and the hunt keeps the
profile's `buffs` list up. Captured 2026-09-12 on the circle-1 Paladin,
Heroic Strength ([Elanthipedia](https://elanthipedia.play.net/Heroic_Strength):
+Strength and +Stamina for 10-40 minutes, minimum prep 1, an intro
spell for Paladins) prepared and cast by hand with the hunt stopped:

```
> prepare heroic strength
Since you're not feeding enough power into the spell pattern to make it coherent, you quickly work your way to the minimum required.
You begin chanting a prayer to invoke the Heroic Strength spell.
> cast                              (ten seconds later)
You gesture.
The spell takes effect, the invisible flame of your soul intertwining with your flesh.  You feel holy strength and vigor course through your body.
You feel fully attuned to the mana streams again.
```

The game marks the prepared spell with `<spell>Heroic Strength</spell>`
(`None` once cast) and rewrites the Spells window on every pulse —
`<clearStream id="percWindow"/>` then `Heroic Strength  (10 roisaen)`,
a roisan being a real minute — which the parser keeps as
`prepared_spell` and `active_spells` (client/engine/xml_data.py). The
loop casts a buff the window does not list, before the first swing
and before any later one; a session whose parser predates that state
re-casts on a ten-minute timer, the wiki's shortest duration. The
first scripted cast, with the spell still running, answered "You
gesture." and "Your soul and body intertwine tighter, the bond renewed
by the spell." — no "takes effect" — and the window went back to 10
roisaen, so a renewal counts as a cast. Two things follow from the
first capture: no "fully prepared" line came in the
ten seconds before the cast, so the loop waits eight seconds after
PREPARE rather than for a wording; and every cast of a Holy buff
trains Augmentation, so a buffed hunt trains that skill on the side
(list it in `train_skills` to hunt until it locks). To train it on
purpose, `train_casting` names the skill and the loop recasts the
first buff between swings until it locks (the casting lives in
`client/game/buffs.py`, which `;athletics` runs in its award-timer
waits too): Elanthipedia's magic
category says every standard cast trains Primary Magic, the spell's
field and Attunement, and that "fewer but larger spellcasts are more
efficient in terms of experience than smaller but more frequent
spellcasts", so each training cast feeds two more mana than the last,
from the minimum up, until PREPARE answers "You have to strain to
harness the energy for this spell" (the wiki's wording, unobserved
here) or the cast fails, and holds one step under from then on; a
failure at the minimum ends the training casts for the run. The
first live run (2026-09-12) started the ramp at 5 mana and every cast
answered "Your spell barely backfires." or "Your spell backfires
somewhat." — a circle-1 Paladin cannot hold 5 — yet Augmentation
went from 3 to 5 ranks in three casts, so a backfire still trains;
the ramp now starts at the minimum. A mana floor of 40% and a
twenty-second gap between casts keep the fight going. Manifest Force,
the apprenticeship barrier, stacks with Aspirant's Aegis, the circle-1
ward the free spell slot could take. The failure wordings (a spell
not known, a collapsed pattern) are assumptions until captured.

## Out of scope in the first cut

Offensive magic and ranged attacks, a policy for several opponents at
once, selling gems, and buying arrows or ammunition. Each is a
profile setting and a branch away, once captures show the wordings.
Buffs and skin bundles were the first two to land (2026-09-12).
