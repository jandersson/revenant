# The hunting model ;hunt assumes

`;hunt` fights a ground in a loop from a per-character profile: walk
there, ready weapon and stance, attack until the room empties, skin and
search each kill, move along the ground, come home on a limit. This
file records what the script believes about the game and which of it
is captured versus assumed — the fixtures in `client/tests/hunt_arena.py` and the `test_hunt*.py` files
pin the same wordings. The fight itself follows [combat.md](combat.md).

## The profile

One JSON file per character, `~/.revenant/profiles/<name>.json`, edited
from File → Character Profile… (the dialog builds itself from
`client/game/profile.py`'s FIELDS, so the file and the form never disagree).
It holds what no script should hard-code:

| setting | what the loop does with it |
| --- | --- |
| hunting_ground | a `;go2` target; every room it resolves to is the ground, walked to at the start and cycled when a room runs empty |
| prey | the noun ATTACK gets; empty swings at whatever engages you (the vineyard's cougars and, at night, grendels — 2026-09-21). The kill's noun then comes off the kill line, the creature's phrase cut before its verb chain ("A small grendel grunts and collapses." skinned "and" until #270), and a pattern aimed at the foe is released when the foe falls under the filler, prey noun or none (#271) |
| home | a `;go2` target walked to when the hunt ends |
| weapon, weapon_container | `WIELD my <weapon>` before the first swing — the game searches the inventory and remembers the source (captured 2026-09-22: "You draw out your steel scimitar from the leather scabbard, gripping it firmly in your right hand."; #259's scimitar in the sack is found that way), `SHEATHE my <weapon> in my <container>` to put it back ("You sheathe the steel scimitar in your leather scabbard."; a bare SHEATHE works after a WIELD, else asks "where?" and STOW follows); DRAW is an attack maneuver, never the draw; it stays in hand when the hunt ends (stowed, it parries nothing — 2026-09-12), the container is only where it is fetched from, and where it goes for the moment the first skin of a run is bundled |
| stance | `STANCE SET <args>` once, before the first swing |
| skin, skin_knife | `SKIN <corpse>` after each kill; a named knife is fetched before and stowed after. Elanthipedia's Skinning page: "Using a skinning knife gives the largest bonus, closely followed by the belt worn knives", and a worn one "will automatically be used to skin without taking it out, as long as you have one free hand". Two kinds exist (2026-09-14): Grek's (Kaerna Village, 375 Kronars, ORDER then OFFER) cannot be worn ("You can't wear that!") and would be a held `skin_knife: knife` — the hand it sits in is never taken for the skin; Tobb's Smithy in the Knife Clan (map 6206, 500 Kronars, the shop dr-scripts' new-character.lic buys from) sells a "small steel skinning knife with a leather-wrapped hilt" that WEARs on the wrist ("You attach ... to your wrist."), which leaves `skin_knife` empty and both hands free |
| loot_container | where skins and non-gem finds go (`PUT my <item> IN my <container>`, else `STOW my <item>`). Full — "There isn't any more room in the sack for that." (2026-09-21) — a skin is tried with a bare STOW, and refused again it stays in hand and skinning is off for the run, said with the remedy: `;skins` sells the loose skins in a hand or the container one at a time (#261, #262) |
| gem_pouch | finds are tried into the pouch first; what the pouch refuses is stowed like loot |
| bundle | skins go onto a bundling rope worn as a lumpy bundle: one kept in the loot container is worn before the first swing, the first skin of a run starts one from the rope in that container, every later skin goes straight into the worn bundle as SKIN cuts it (the hand tags are the judge), and `;skins` sells it. No rope: said once, skins stowed loose. A first skin BUNDLE will not take (a curved claw, 2026-09-21: "You don't have any bundles or they're all full or too tightly packed!") is stowed loose and the next skin starts the bundle (#260) |
| buffs | self-cast spells kept up through the hunt: each is PREPAREd and CAST before the weapon is drawn and again, before a swing, whenever the Spells window no longer lists it (a parser without that window re-casts every ten minutes); a refusal drops the spell for the run, said once |
| train_casting | a magic skill ("Augmentation"): while it sits below mind-lock and mana is above the floor, the first buff is recast between swings, `cast_gap` seconds apart, with the mana fed rising by two each cast from the minimum until the game warns of strain (or a cast fails), then held one step under — a failure at the minimum ends the training casts for the run; at lock, back to casting only when the buff runs out |
| cambrinth | a held cambrinth piece's noun ("flake"): before every training cast the loop GETs it, CHARGEs it with `cambrinth_mana` (the charge is what trains Arcana), INVOKEs it so the stored mana feeds the cast, CASTs, and stows it; a piece the game will not charge (worn, or outranking the skill) is off for the run, said once; with no `train_casting` the cambrinth alone drives the cast cadence until Arcana locks; a `;stop` between the GET and the stow puts the piece back on the way out (`buffs.put_back_if_held`, the script's finally, 2026-09-20). Wordings and the pieces' capacities: [Cambrinth](#cambrinth) below |
| cambrinth_mana | mana per charge, the piece's capacity (1 for a flake, 5 for the grey ring, 12 for the anklet) |
| cambrinth_worn | the piece is worn between casts (an anklet, an armband): the cycle REMOVEs it for the charge and WEARs it back, since a worn piece refuses a charge — "Try though you may, you find it too clumsy to charge the cambrinth anklet while wearing it." (2026-09-20). A piece that is not on the body after all (REMOVE: "Remove what?" — the anklet was in the sack after a death and a raising, 2026-09-20) is GOT from its container instead and worn back afterwards; a charge that finds it in neither hand ("You'll have to hold it, set it on the ground, or put it on something first.") gets one more GET and one more charge before the cambrinth is off for the run |
| cast_gap | seconds between training casts, 60 by default. A cast cycle with a cambrinth piece is eight commands, and at 20 s the first badger hunt (2026-09-14, #189) ran cast cycle, one or two swings, cast cycle: seven swings to the badger's 42 in four minutes. One cast a minute trains both skills the same and leaves the fight to the weapon |
| debilitation | a targeted spell ("Stun Foe") cast at the prey between swings while Debilitation sits below lock: PREPARE (the mana ramping like the training casts, never past DISCERN's estimate of the caster's most — five backfires on 2026-09-20), CAST <prey>, one per `cast_gap`, taking turns with the buff training cast so a swing never carries two casts; a collapse at the minimum turns it off for the run. Model: [Debilitation](#debilitation) below (#192) |
| targeted | an attack spell ("Footman's Strike") cast at the prey between swings while Targeted Magic sits below lock, on the same cast gap and mana ramp as `debilitation`; the buff training cast, the debilitation cast and this one rotate, one cast per swing at most. Model: [Targeted Magic](#targeted-magic) below (#200) |
| health_floor | below it: the burst escape (retreat, retreat, first exit), then home — or, with no home, the nearest room off the ground, said so (#185: a break-off that ended on the ground left the character among the rats that hurt it, and they killed it two and a half hours later, 2026-09-13) |
| wound_floor | a severity name — empty means `harmful`, where bleeding starts, said once at the start (#236: an unset floor guarded nothing through an hour of eels), `off` never asks; after each kill and whenever the health bar drops, the injuries panel the game pushes is read first — clean means nothing to ask — and HEALTH is asked only when it shows a wound; a wound that bad or worse anywhere (external, scar, internal, internal scar) breaks off like the health floor. Empty never asks. Model: [wounds.md](wounds.md) |
| train_skills | the hunt ends when every one of them sits at mindstate 34 in the exp window |
| max_kills | a fuse; 0 hunts until stopped or locked — an empty ground is waited out (a pause after every empty lap, then the next lap), never left. Two fuses need no field: 60 swings without a kill, or three stuns in one fight ("lightly stunning you"; a kill resets the count), end the hunt as a break-off — "the ground is beyond you", the burst escape, then home (#236: an hour of grass eels on 2026-09-20 gave no kill and nine stuns while the health bar never crossed the floor) |
| smite | a Paladin: one swing a minute is SMITE instead of ATTACK, spent only when the game answers with its conviction line — the free smite regenerates every minute and Conviction experience comes at most once a minute ([Smite command](https://elanthipedia.play.net/Smite_command), #183). SMITE CHECK goes out first and with no free blow the swing is an ATTACK: a smite past the free ones draws on the soul pool, and with the pool empty it harms the soul (#217, [soul.md](soul.md)) |
| tactics | tactical maneuvers in rotation (`bob`, `circle`, `weave`): every third swing is the next one instead of ATTACK while Tactics sits below mind-lock; SMITE keeps its minute ahead of them; a maneuver the foe wins ("You hesitate and change your mind, circle back awkwardly.  The cougar easily out maneuvers you.", 4 s roundtime, the vineyard cougars 2026-09-21, #265) is an attempt like any other; three answers outside the table turn them off for the run. Model and captures: [Tactics](#tactics) below (#190) |
| perception | HUNT for tracks once a room of the ground has emptied, and on every lap of an empty ground, at most once per 75 seconds while Perception sits below lock — the skill's own learning timer; the tracks are not followed. Model: [Tracks](#tracks) below (#194) |
| weapons | the weapons the hunt cycles through, one turn per kill, each with the skill it trains — `handaxe:Small Edged:sack` (the container it goes back into between turns), `fists:Brawling` for the brawling attacks with nothing in hand. A turn whose skill is mind-locked sits out until it drains; every turn locked ends the hunt. A single turn is that turn (`fists:Brawling` alone hunts bare-handed whatever `weapon` says — below two entries the list was ignored until 2026-09-20). Empty: `weapon` alone, never swapped (#238; [Weapons in rotation](#weapons-in-rotation-and-the-fists) below) |
| brawling | the brawling attacks the fists turn swings in rotation instead of ATTACK (`punch`, `kick`, `elbow`): what trains Brawling; punch wants a free hand, the other two none. At range PUNCH answers "Actually, using a weapon would probably be a bit more effective." and KICK its dirt emote, no roundtime on either: the loop ADVANCEs and waits for melee, as the maneuvers' "must be closer" does (#257). Empty: the fists turn is skipped, said once |
| attune_start | not the hunt's: where `;attune` walks before building its street loop, a `;go2` target; empty loops from wherever it stands (`;attune from=<target>` overrides it for one run) |

`;hunt return` (typed while it runs) ends the loop before the next
swing and walks home; `;stop hunt` quits where it stands (the rule for
every script: the typed word is the graceful end, `;stop` the abrupt one).
`;hunt here` skips the walk to the ground; `;hunt profile` prints the
profile it would use.

## What is captured and what is assumed

Captured (the 2026-08-22 traffic behind combat.md, and the first live
`;hunt` on 2026-09-05 — a circle-1 Paladin against ship's rats at
Barana's Shipyard):

- the kill line "The ship's rat falls to the ground and lies still."
  — the corpse noun is the word before the kill phrase ("rat"). The
  first run knew only "The cougar slowly tips over and falls down."
  from 2026-08-22, missed the rat's kill and never skinned — and that
  cougar line was never a kill: every capture of it (the cougar, the
  rats of 2026-09-12 and 13, a badger on 2026-09-14) is a knockdown,
  the creature's `<crtrStatus>` gaining `stunned="1" prone="1"`,
  "lying down" in the room listing, then "leaps to its feet"; the
  badger hunt skinned and searched one that stood up ("You can't skin
  something that's not dead!") and counted the kill (#197). Since
  2026-09-14 a knockdown is nothing to act on. A second knockdown
  wording shares the kill line's first words — "A striped badger
  screams and falls to the ground grasping its mangled left leg!",
  then "grimaces as it stands back up" at the SKIN (2026-09-20, #240)
  — so the needle is the whole phrase, "falls to the ground and lies
  still", or the cougars' "falls to the ground lifeless" (2026-08-22),
  never the first words alone;
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

## Cambrinth

Charging a cambrinth piece is what trains Arcana (Elanthipedia:
[Cambrinth](https://elanthipedia.play.net/Cambrinth), [Arcana
skill](https://elanthipedia.play.net/Arcana_skill)); the stored mana
then feeds the next cast through INVOKE or decays an eighth every 500
seconds. A piece that outranks the skill channels nothing: the
32-mana braided armband at Arcana 1 answered every CHARGE with "You
fail to channel any of the energy into the armband." and taught
nothing, while a 1-mana round flake took the charge and moved Arcana
1.00 to 1.36 on one mana (2026-09-14). [Herilo's
Artifacts](https://elanthipedia.play.net/Herilo's_Artifacts), the
Crossing's artificer (map tag `artificer`), sells the pieces by
capacity — flake 1 (162 Kronars), grey ring 5, anklet 12, armband 32,
orb 50 — and notes that only the 1- and 5-mana pieces work at 0 ranks.
Captured on the flake: CHARGE "You harness a small amount of energy
and attempt to channel it into your cambrinth flake. / You are able to
channel all the energy into the flake. / The cambrinth flake absorbs
all of the energy. / Roundtime: 2 sec."; a full piece "is already
holding as much power as you could possibly charge it with. / Your
harnessed energy dissipates uselessly."; FOCUS "pulses brightly with
Holy energy. You guess you can perceive 1 line worth of spell energy
bound within the flake. [You can use INVOKE to activate the energy
held in this device.]"; INVOKE "You reach for its center and forge a
magical link to it, readying all of its mana for your use."; the cast
"Your cambrinth flake emits a loud *snap* as it discharges all its
power to aid your spell."; and a worn piece "Try though you may, you
find it too clumsy to charge the cambrinth armband while wearing it."
— so the profile names a held piece, kept in the loot container.

The simple cambrinth anklet (12 mana, 1,500 Kronars at Herilo's Artifacts, map 19152, bought 2026-09-20 at Arcana 17 — the wiki's rule of thumb is Arcana ranks equal to the capacity, and the 32-mana armband failed at rank 1) takes a full charge: "You harness a small amount of energy and attempt to channel it into your cambrinth anklet. / You are able to channel all the energy into the anklet. / The cambrinth anklet absorbs all of the energy. / Roundtime: 4 sec." and INVOKE answers "The cambrinth anklet pulses with Holy energy.  You reach for its center and forge a magical link to it, readying all of its mana for your use. / Roundtime: 1 sec." Worn, it refuses the charge like the armband — "Try though you may, you find it too clumsy to charge the cambrinth anklet while wearing it." — so with `cambrinth_worn` the cycle REMOVEs it first and WEARs it back after the cast; the character keeps it on his ankle between casts.

## Smiting for Conviction

Paladins train Conviction two ways only: a SMITE with the weapon or a
RUSH with a shield ([Conviction skill](https://elanthipedia.play.net/Conviction_skill)).
Captured 2026-09-13 on a ship's rat: from range SMITE answers exactly
as ATTACK does ("You aren't close enough to attack." / "You are
already advancing on a ship's rat."), under roundtime "...wait 4
seconds.", and at melee "Drawing strength from your conviction, you
execute a divinely inspired strike!" followed by the ordinary swing
line and a 6-second roundtime; Conviction entered the exp window at
rank 4 after the one strike. Free smites regenerate one a minute and
the experience is granted at most once a minute ([Smite command](https://elanthipedia.play.net/Smite_command)),
so the loop smites one swing a minute and attacks the rest — a smite
that drew the advance or a roundtime is not counted as spent. A smite
is fueled by Conviction's free blows first and the soul pool after,
and a smite with the pool empty harms the soul — an evening of them
took the Paladin to chalky grey and the glyph quest's orb refused him
(#217, [soul.md](soul.md)). So SMITE CHECK goes out before each smite
(captured 2026-09-20 at Conviction 49: "You contemplate the strength
of your conviction. / Your conviction is enough to deliver three blows
against your enemies before you must either rest or draw upon your
spiritual strength to continue.") and with no blow counted the swing
is an ATTACK and the minute is spent; a smite the game answers
"Drawing upon holy wrath, you execute a divinely inspired strike!"
(the wiki's soul-pool line) turns smiting off for the run. The wording
of a SMITE CHECK with no free blows is still to capture. RUSH is
not built: Cecil wears no shield and its answers are uncaptured.

## Debilitation

Debilitation "is trained in combat, by casting spells on enemies
utilizing skill caps comparable with other combat skills"
([Debilitation skill](https://elanthipedia.play.net/Debilitation_skill));
a Paladin's are Halt, Stun Foe and Shatter.
[Stun Foe](https://elanthipedia.play.net/Stun_Foe) is the intro one: a
battle spell on a PC or creature, Holy, prep 1 to 33 mana, instant,
"Stuns target" on a magic-versus-fortitude contest. The wiki's cast
line is "A brilliant stream of pure white light jumps from you to
<target>, warping into a spiraling force that slams into it!"; at
minimum mana the first scripted cast (2026-09-14, a striped badger)
read "You gesture at a striped badger. / A stream of dull golden light
jumps from you to a striped badger, which warps into a spiraling force
as it slams into it! / You also see a striped badger that appears
stunned." — the light scales with the mana fed. Too much mana answers
"Your spell hopelessly backfires." (captured 2026-09-14 on the ramp's
second step; the ramp then holds one step under, and the next cast
landed). A backfire is not free: "A tingling sensation spreads through
your body." is a nerve wound that dampens the casting after it, and
five of them came in one evening (2026-09-20: Stun Foe at 4 mana,
Footman's Strike at 6) while DISCERN had said "The spell requires at
minimum 1 mana streams and you think you can reinforce it with 2
more, for a total of 3 streams." and "... with 0 more, for a total of
2 streams." So the estimate is the ceiling now: every ramp — the two
targeted slots' and the training buff's, which is DISCERNed for it —
climbs to the game's total and no further, and an estimate at the
spell's minimum means no ramp at all. The resist wording is uncaptured. A stunned creature does not attack, so the
cast spares bites
while the weapon works. The profile's `debilitation` names the spell,
and the loop casts it at the prey before a swing on the same cast gap
and mana ramp as the buff training cast, the two taking turns when
both are due — a swing never carries two casts (2026-09-14, #192).

## Targeted Magic

Targeted Magic is trained by casting attack spells at creatures, at
the challenge a weapon skill would want
([Targeted Magic skill](https://elanthipedia.play.net/Targeted_Magic_skill)).
A Paladin's first is
[Footman's Strike](https://elanthipedia.play.net/Footman%27s_Strike):
Holy, prep 2 to 50 mana, instant, prerequisite Stun Foe. It "draws on
the caster's melee weapon in hand as a focus for the spell, which
dictates the shape of its manifestation ... Holding a missile weapon
or being unarmed causes the spell to fail", so the loop casts it only
in the fight, weapon drawn. The wiki's cast line is "You gesture at
<target> with your <weapon>."; the hit, resist and unarmed-failure
wordings are uncaptured until the first live run (an "unrecognized
cast answer" echo is the thing to report). The profile's `targeted`
names the spell, and the loop casts it at the prey before a swing on
the same cast gap and mana ramp as the debilitation spell; the buff
training cast, the debilitation cast and this one take turns in that
order, so a swing never carries two casts (#200).

The ranks come first. Footman's Strike is a basic-tier spell
([Paladin spells](https://elanthipedia.play.net/Paladin_spells)), and
the Targeted Magic page puts the ranks to cast one at minimum mana at
"around 1 rank for intro, around 20 for basic"; Paladins have no intro
Targeted Magic spell. At Targeted Magic 1 the first scripted strike
(2026-09-18, a striped badger) answered "You gesture at a striped
badger with your oak-hafted handaxe. / Currently lacking the skill to
complete the pattern, your spell fails completely." — and the loop,
not knowing the line, stepped the mana up and spent a PREPARE and a
CAST on it every rotation (#202). Now that answer turns the slot off
for the run with the rank named, and before the weapon is drawn each
targeted spell is DISCERNed once
([Discern command](https://elanthipedia.play.net/Discern_command):
eight seconds of roundtime, no mana, "You think you could weave at
most 27 mana streams into this spell."), so "You don't think you are
able to cast this spell" ([Talk:Regenerate](https://elanthipedia.play.net/Talk:Regenerate))
costs no cast at all. The operator's own DISCERN (2026-09-18) gave
the spell's description first — "This is a targeted spell, which must
be TARGETed at a specific opponent. ... To begin to be able to cast
this spell, you will need to reach the rank of a promising novice.
... It requires the Targeted Magic skill to cast effectively." — then
the refusal and "Roundtime: 13 sec." A promising novice is ranks 10 to
19 ([Experience](https://elanthipedia.play.net/Experience): the novice
tier is lowly, promising, able, trained and full by tens), so the
strike wants Targeted Magic 10, and the DISCERN echo names that floor
beside the rank held. How a Paladin earns those first ranks is an open
question for the operator; the slot waits.

Being targeted magic, the strike is cast the TARGET way
([Target command](https://elanthipedia.play.net/Target_command)):
PREPARE <spell> <mana>, TARGET <prey> ("You begin to weave mana lines
into a target pattern around <target>." then, after the pattern's
time, "Your formation of a targeting pattern around <target> has
completed."), CAST with no argument. Those wordings are the wiki's
until a cast lands; a missing target RELEASEs the pattern (#203).

## Casts between swings

A cast never idles. PREPARE is answered during weapon roundtime — in
the 2026-09-18 log every "You begin chanting a prayer" landed one to
nine seconds before the preceding swing's roundtime ended — so the
loop PREPAREs (and TARGETs), sends the iteration's swing while the
pattern forms, waits the swing's roundtime, collects what is left of
the prepare time for the ready line, and CASTs; the cast wraps the
swing rather than adding one, so the cadence is still one swing per
iteration and the prepare wait costs nothing. A battle spell's pattern
(Stun Foe, Footman's Strike: 8 s) is covered by that one swing; a
non-battle spell's is not — Heroic Strength formed for 26 s at Cecil's
Holy Magic on 2026-09-20 and the hunt stood the other 22 under the
badger's claws, once a minute — so while the parser's cast time says
a swing's roundtime (4 s) still fits before the ready line, the loop
swings again, each swing counted toward the fuses (#250). The wait
for the ready line keeps one second past the cast time's second: the
clock is whole seconds, and a pattern whose cast time equals the last
prompt's second is still forming for a fraction no stamp shows — a
CAST sent then read "You feel fully prepared" as its answer and missed
"Your spell barely backfires." (#263, 2026-09-21). A kill read
off a swing with one hostile in the parser's set clears the room in
the tally — the dead one's status frame never comes (#244), and a
CAST at it answered "The striped badger is already dead, so that's a
bit pointless." while the pattern stayed held, so the next PREPARE
was refused ("You have already fully prepared the Stun Foe spell!")
and its TARGET said "This spell cannot be targeted." (#252, all three
captured 2026-09-20): each of those wordings now RELEASEs the pattern,
and the refused PREPARE is sent once more. It is dr-scripts'
combat-trainer shape (its spell process prepares, keeps attacking,
and casts on the ready flag or the prep timer). A foe that went down
under the filler swing has a pattern aimed at it RELEASEd rather than
cast at nothing; a self-cast buff casts regardless (#203).

## Weapons in rotation, and the fists

The profile's `weapons` are the turns one hunt cycles through, one
per kill (#238; the operator, 2026-09-20: no argument per weapon type,
"the script should just cycle weapons that are being trained"). Each
entry names the weapon, the skill it trains and the container it goes
back into — `handaxe:Small Edged:sack` — and after every kill the
next turn whose skill sits below mind-lock takes the hands: the last
weapon PUT back in its container, the hands cleared with STOW, the
next one GOT; a turn whose skill is locked sits out until it drains,
and when every turn is locked the hunt ends "every weapon skill
mind-locked". The fists turn (`fists:Brawling`) draws nothing: the
parry stick and the brass knuckles are worn and work worn, PUNCH
wants a free hand, and the profile's `brawling` attacks — PUNCH,
KICK, ELBOW — go out in rotation in place of ATTACK. Brawling
"encompasses the use of a character's body and improvised or
brawling-specific weapons" and is "commonly trained as an auxiliary
weapon skill" ([Brawling skill](https://elanthipedia.play.net/Brawling_skill));
[PUNCH](https://elanthipedia.play.net/Punch_command) "requires a free
hand", [ELBOW](https://elanthipedia.play.net/Elbow_command) "does not
require a free hand, so it stays available when both hands are full",
and KICK works with both hands full too. Parry Ability "dictates your
character's ability to fend off an incoming melee or pole-ranged
attack with the weapon in your right hand" and "parrying also teaches
some of the skill of the weapon you are parrying with"
([Parry Ability skill](https://elanthipedia.play.net/Parry_Ability_skill)),
so a parry stick — a weapon with no skill of its own — trains Parry
Ability alone; worn, it parries as it is and both hands stay free for
the punches. Milgrym's
Weapons in the Crossing (map 8263) sells a polished steel parry stick
at 1,250 Kronars and brass knuckles or elbow spikes at 575 each
([Milgrym's Weapons](https://elanthipedia.play.net/Milgrym%27s_Weapons)),
worn brawling gear that PUNCH and ELBOW use on their own. The kill
line, the skinning, the casts and the maneuvers are the plain hunt's,
and the attacks answer in the combat stream shaped like any weapon
swing, so they need no table of their own. Captured 2026-09-20 on the
first live fists turn, a striped badger, the knuckles and the stick
worn (Brawling 7 78% → 8 02% and a rank in one turn):

```
< Moving with the precision of a mongoose, you punch your brass knuckle at a striped badger.  A striped badger attempts to dodge, avoiding only some of the blow.  The knuckle lands a hard hit to the badger's right arm.
< You punch your brass knuckle at a striped badger.  A striped badger evades, just stepping out of harm's way.
< Moving with indomitable grace, you kick your foot at a striped badger.  A striped badger fails to dodge, avoiding only some of the blow.  The foot lands a good strike to the badger's left arm.
< Moving as a single sinuous force, you elbow your plate-clad elbow at a striped badger.  A striped badger fails to dodge, only slightly avoiding the blow.  The elbow lands a solid hit to the badger's left leg.
```

The targeted cast on that turn gestured "with your brass knuckles"
and struck as ever. The `;train` hunt task lists every weapon skill —
`"skills": ["Small Edged", "Brawling"]` — so the task runs until all
of them reach the plan's target.

## Tactics

Tactics trains like a weapon skill, at melee against an opponent of
suitable challenge, from the tactical maneuvers and ANALYZE
([Tactics skill](https://elanthipedia.play.net/Tactics_skill): "the
current way to train it is to use tactical maneuvers (like WEAVE and
BOB) and using ANALYZE"); it is a Lore skill, secondary for a Paladin.
The wiki's low-risk rotation is BOB, CIRCLE and WEAVE between attacks:
[BOB](https://elanthipedia.play.net/Bob_command) is "barely fatiguing",
"very balance building" and restores a little fatigue,
[CIRCLE](https://elanthipedia.play.net/Circle_command) is "moderately
fatiguing" and builds position,
[WEAVE](https://elanthipedia.play.net/Weave_command) is "extremely
fatiguing" and "much costlier than BOB or CIRCLE for the same purpose";
all three are non-damaging, "temporarily penalize all defenses", cannot
be used while grappled, and take `<verb> [<target>]`. Captured
2026-09-14 by hand on a striped badger, each followed by a balance line
and "Roundtime: 3 sec.":

```
> bob badger
You bob suddenly, lowering yourself into a smaller target.
> circle badger
You sidestep a striped badger suddenly, moving in a short circle around it.
> circle badger
You fake a striped badger, first moving one way and then another, leaving it off balance.
> weave badger
You weave back and forth, trying to distract your opponent.
```

Tactics entered the exp window at rank 3 on the first BOB. So the
profile's `tactics` list is a rotation and the loop makes every third
swing the next maneuver in it, with the prey as target, while Tactics
sits below lock: a maneuver takes a swing's roundtime and deals no
damage, so the other two swings keep the kill coming and SMITE keeps
its minute ahead of them. A maneuver from range does not advance the
way ATTACK does — "You must be closer to use tactical abilities on
your opponent." (captured 2026-09-20 on a badger closing from pole
range) — so the loop ADVANCEs on the prey and waits for melee range
before the next swing; any other answer outside the three lines is echoed as
unrecognized, and three of them in a row turn the maneuvers off for
the run. ANALYZE, GRAPPLE, SHOVE and TRIP are not built.

## Tracks

HUNT "searches the rooms around you for the tracks of nearby creatures
and players, and travels to whichever one you choose"
([Hunt command](https://elanthipedia.play.net/Hunt_command)): `HUNT`
reads the tracks in an 8-second roundtime, `HUNT <#>` walks to one. It
teaches Instinct (Rangers) and Perception, each on its own 75-second
learning timer, and fails where hunting is not permitted, with items
underfoot, or while engaged. Captured 2026-09-14, of all places in a
guild office:

```
> hunt
You take note of all the tracks in the area, so that you can hunt anything nearby down.
To the out:
  1)   an armored sentry
To the out, east:
  2)   an armored sentry
Roundtime: 8 sec.
```

The empty answer, "You were unable to locate any followable tracks.",
is the wiki's and was captured the same night on an empty Brambles
room. With the profile's `perception` on, the loop HUNTs once when a
room of the ground has emptied (after the corpse is searched, before
the move) and on every lap of an empty ground, at most once per 75
seconds, until Perception locks; the tracks are not followed, the
ground's rooms are the map's. Three answers outside the two lines in a
row turn the step off for the run. Following a track to the next
creature is not built (#194).

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

A crowd of creatures is not the same rule. The room's own listing
(`room objs`, "You also see a musk hog, a musk hog and a rusty
ladder.") bolds each creature and NPC and arrives with the room,
before any of them engages, so the parser's `room_creatures` is a head
count on arrival. `;athletics` skips a rung or a rotation stop at
three of them (dr-scripts' `climb?` rule: creatures interrupt a
climb). `;hunt` never moves on for a crowd: a full room is what a hunt
farms, fought one at a time with the health and wound floors as the
guard (the operator, 2026-09-12). `;status` shows both lists.

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
scripted run returned to the rats with the weapon stowed); `;skins
bank` goes on to the nearest room tagged `bank` and DEPOSITs ALL —
captured 2026-09-14 at the Provincial Bank after Falken paid 217
Kronars for four badger pelts: "The clerk slides a small metal box
across the counter into which you drop all your Kronars.  She counts
them carefully and records the deposit in her ledger." — which is
`;bank`'s line now ([training.md](training.md), #235): `;skins bank`
runs `;bank` and waits for it instead of depositing itself (the
operator, 2026-09-20: "it should just do ;bank"), and the plan keeps
selling and banking as two tasks, `skins` then `bank` (#196). The
first bundled hunt ran the same
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
the ramp now starts at the minimum. A mana floor of 40% and the
profile's `cast_gap` between casts (60 s by default) keep the fight
going: at 20 s the first badger hunt (2026-09-14) ran cast cycle, one
or two swings, cast cycle — with the flake a cycle is eight commands —
and in four minutes the Paladin swung seven times to the badger's 42
(#189). Manifest Force,
the apprenticeship barrier, stacks with Aspirant's Aegis, the circle-1
ward the free spell slot could take. The failure wordings (a spell
not known, a collapsed pattern) are assumptions until captured.

## Aiming past a corpse

The room's listing names its creatures in order, corpses marked ("a
cougar which appears dead, a rise in the cliff, a cougar and a cougar",
captured 2026-09-22), and the game counts them by ordinal: the corpse
is "cougar", the live ones "second cougar" and "third cougar". ATTACK
COUGAR reaches the corpse — "already quite dead", the swing spent
(CORPSE_SWINGS then decides the room is clear). `;hunt` now aims each
swing with `client/game/creatures.py`'s `aim`: the plain noun when the
first of it lives, the ordinal phrase when corpses come first, the
plain noun when every one is dead (the game then says so and the
corpse is disposed of). lich-5's `add_ordinals_to_duplicates` does the
same for dr-scripts (#278). The listing lags a kill by one push, so
the first swing after a kill may still meet the corpse; the second is
aimed past it.

The balance word the game states ("solidly balanced", the base of
twelve; docs/protocol.md) is tallied per swing and reported at the
end of the run — a reading for the experiment, no rule yet (#280):
dr-scripts' combat-trainer holds attacks while badly off balance.

## Out of scope in the first cut

Ranged attacks, a policy for several opponents at once, selling
gems, and buying arrows or ammunition. Each is a profile setting and a
branch away, once captures show the wordings. Buffs and skin bundles
were the first two to land (2026-09-12); offensive magic followed as
the profile's targeted spell, one cast per swing (#200).

Gems are kept, not sold: a filled gem pouch is `;appraise`'s best
item (Elanthipedia: Appraisal skill), so `;hunt` pouches every gem it
finds and no script sells one — the operator's rule, 2026-09-22
(#283 is the second pouch once the first holds its seventy).
