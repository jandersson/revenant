"""Hunt your profile's ground, train its weapons, walk home, sell and bank:  ;hunt

    ;hunt                   walk to the ground and hunt until one of the stops below
    ;hunt here              hunt where you stand, no walk
    ;hunt <style>           a hunt style from the profile's `hunts` (its ground, prey, weapons, `until`)
    ;hunt styles            list the profile's hunt styles
    ;hunt profile [style]   print the profile the hunt would use
    ;hunt grounds [rank]    hunting zones for your weakest weapon's rank (or <rank>), nearest first,
                            with the boxes and copper you measured on each, else the wiki's word
    ;hunt return            (typed while it runs) finish the kill and end as below
    ;stop hunt              quit where you stand

What it does
  - Walks to the ground (a map tag, a bestiary zone or a ;go2 target) with the buffs up.
  - Fights one creature at a time: attack, skin (never a creature the wiki says has
    no skin), loot, gems and boxes stowed.
  - Moves room to room; a room another player hunts is theirs and is skipped.
  - Trains the `weapons` in turn: the emptiest pool first, each to `weapon_target`,
    or for `weapon_minutes` at most when a pool will not fill.
  - Between swings, as the profile says: maneuvers, SMITE, training casts,
    HUNT for Perception; a Barbarian's combos, abilities and roars instead.
  - The profile's `almanac` studied whenever its timer allows: in a clear room,
    or mid-fight after a RETREAT to pole range.
  - At the end, says each creature's searches, boxes and coins; history.db keeps
    every search (`loot`), every hunt (`hunts`) and every box picked up (`box_drops`).

When it stops — then walks home, and runs ;skins bank (skins sold, purse banked but 200 copper kept for a ferry fare; ;bank alone when no skin was cut)
  - health below `health_floor`, or a wound at `wound_floor` (also checked before setting out)
  - 60 swings without a kill, or three stuns in one fight
  - every trained skill mind-locked, or the style's `until` (boxes, kills)
  - every room of the ground taken by other players
  - ;hunt return
  - a hunt that never reached the fight (no ground, a wound at the floor) ends without selling
  - an Empath never sets out: attacking a living creature brings empathic shock

The profile is ~/.revenant/profiles/<name>.json (File > Character Profile...);
docs/hunting.md explains every key. Report any "hunt: unrecognized ..." line.
"""

import logging
import re
import time
from collections import Counter

from client.game import (
    act,
    almanac,
    barbarian,
    boxlog,
    buffs,
    cards,
    flight,
    gems,
    guild,
    hands,
    hunting,
    interlude,
    items,
    loot,
    lootlog,
    probe,
    stores,
    travel,
)
from client.game.act import (
    NOT_FOUND,
    ask,
    missing,
    said,
    unknown,
    whole_answer,
)
from client.game.creatures import aim, aim_corpse, noun_of, outgrown, skinnable
from client.game.probe import classify
from client.game.profile import describe, load_profile
from client.game.profile import styles as profile_styles
from client.game.walker import DIRECTIONS, locate, walk
from client.game.wounds import SEVERITIES, level, parse_health

# The pure half — the tables, the kill sentence, the weapon plan, the
# Tally — lives in client/game/hunting.py (#274, #407) and keeps its
# names here, so `hunt.X` still reads it; what a moved function reads
# (hunting.clock, a fuse) it reads off that module, so a test patches
# `hunting`, never the script.
Tally = hunting.Tally
MIND_LOCK = hunting.MIND_LOCK
DEFAULT_WOUND_FLOOR = hunting.DEFAULT_WOUND_FLOOR
DEFAULT_WEAPON_TARGET = hunting.DEFAULT_WEAPON_TARGET
TURN_STALL_SWINGS = hunting.TURN_STALL_SWINGS
SMITE_INTERVAL = hunting.SMITE_INTERVAL
TACTICS_EVERY = hunting.TACTICS_EVERY
FISTS = hunting.FISTS
SKIN_OUTCOMES = hunting.SKIN_OUTCOMES
SEARCH_OUTCOMES = hunting.SEARCH_OUTCOMES
BUNDLE_OUTCOMES = hunting.BUNDLE_OUTCOMES
TAP_OUTCOMES = hunting.TAP_OUTCOMES
is_kill = hunting.is_kill
kill_noun = hunting.kill_noun
items_in = hunting.items_in
named = hunting.named
free_smites = hunting.free_smites
wound_floor = hunting.wound_floor
maneuvers = hunting.maneuvers
brawling = hunting.brawling
parse_weapon = hunting.parse_weapon
weapon_plan = hunting.weapon_plan
has_turns = hunting.has_turns
fists_turn = hunting.fists_turn
plain_swing = hunting.plain_swing
turn_target = hunting.turn_target
turn_minutes = hunting.turn_minutes
turn_expired = hunting.turn_expired
mindstate_of = hunting.mindstate_of
rank_of = hunting.rank_of
locked = hunting.locked
stalled_turn = hunting.stalled_turn
farming = hunting.farming
swing_verb = hunting.swing_verb

# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Hunt a ground in a loop, the way your character does it:  ;hunt

Walks to your profile's hunting ground (;go2's map), readies the weapon
and stance, and fights whatever engages you until you say stop: attack,
retarget past corpses, skin the kill if the profile says so, LOOT it (a
bare LOOT, the last creature fought — no corpse noun needed — its
outcome a row in history.db's `loot` table, the box drop rate per
creature, #329; counted per creature for the end's "searched by
creature" line, and the run's totals with its minutes on the ground a
`hunts` row, so ;hunt grounds says each zone's measured boxes per
search and boxes an hour — the wiki leaves most drop rates blank and
the box-farm question of 2026-10-02 had one 29-minute figure, #419;
every box picked up a `box_drops` row with its item id, which STOW BOX
shows in a hand tag and clears on the same line, read off the parser's
last_held, so ;boxes can tell a box's contents to its creature, #423), pouch
any gems (STOW GEM, and a box STOW BOX, straight off the ground into the
containers STORE names — STORE GEMS IN <gem_pouch> and STORE BOXES
IN <loot_container> sent only when the profile's container changes,
remembered in ~/.revenant/stores/<name>.json; STOW HELP / STORE HELP,
2026-09-26), and move on to the next room of the ground when
this one runs empty — and when the whole ground is empty, wait a
while and lap it again, as long as it takes (the operator, 2026-09-13:
an empty ground is not a reason to go home). Breaks off and walks home below the health floor
(with no home set, a break-off still leaves the ground for the nearest
room off it — a character left standing among what hurt it died there,
2026-09-13, #185; the break-off bursts RETREAT, RETREAT and an exit
until the room really changes, writes a move the map had wrong to the
local map, and a hunt never ends among hostiles — it keeps getting
away, #314)
or at a wound at the profile's wound floor (HEALTH after each kill and
whenever health drops; one already there keeps the hunt from setting
out), when the trained skills mind-lock, at the kill
fuse, or when you type
;hunt return  (the current kill is finished first, then the walk home, then ;skins bank — the skins sold and the purse banked; every end that fought does the same, under ;train too, the operator 2026-09-28).
;stop hunt  quits where it stands.  ;hunt here  skips the walk;  ;hunt profile  prints the profile it would use.
;hunt grounds [rank]  lists the hunting zones whose rank range holds the weakest weapon's rank (or <rank>), nearest first.
The ground (`hunting_ground`) is a map tag, else a hunting zone of
the bestiary — dr-scripts' base-hunting.yaml, client/game/hunting.py:
heggarangi_frog_riverhaven, rats, goblins ... with their rooms and
rank ranges — else a ;go2 target (a room id, a title) (#340).
;hunt <style>  hunts one of the profile's hunt styles — `hunts` in the
profile file, a name to the keys that differ for that kind of hunt
(ground, prey, weapons, skinning, the box limit, the skills) and
`until`, what ends it: "lock" (the trained skills mind-lock, the
default), "boxes" (the loot container holds `box_limit` boxes, or has
no room for the next — the farm for ;boxes, off creatures whose boxes
the rank can read; STOW BOX leaves a refused box in hand, "You pick
up a reinforced oaken chest. There isn't any more room in the sack
for that.", and no box is picked up after it, 2026-09-26), "kills"
(`max_kills`). ;hunt styles lists them; ;hunt profile <style> prints
the merged profile; a ;train task passes the style in its args (#299).

Everything character-specific comes from the profile
(~/.revenant/profiles/<name>.json — File → Character Profile… in the
GUI): weapon and its container, stance, skin or not and with what,
loot container, gem pouch, bundle or not, health floor, ground, home,
skills to train. With `bundle` on, skins go onto a bundling rope worn
as a lumpy bundle (free at any tannery: ASK <tanner> FOR ROPE, kept in
any container): a bundle you already have is worn before the
first swing, the first skin of a run starts one when there is none,
and every later skin goes straight into it as it is cut — one item to
sell with ;skins. No rope means skins are stowed loose, said once.
The rope is fetched as GET MY BUNDLING ROPE: a looted lead rope
answered GET MY ROPE first and no bundle started all day (2026-10-01),
and three refusals in a row stow a run's skins loose without trying on.
A room of the ground with another player already in it on arrival is
theirs: the loop says so and moves on without a swing, and a ground
with someone in every room is left to them (#178). A room full of
creatures is the point, not a reason to leave: the loop fights them
one at a time (the health and wound floors are the guard).
With `smite` on (a Paladin), one swing a minute is SMITE instead of
ATTACK: it is what trains Conviction, a free smite regenerates every
minute and the experience comes at most once a minute (Elanthipedia:
Smite command), so the rest of the swings stay ATTACK. The game says
when the free smite is back — "The strength of your conviction has
fully returned.", 50-61 s after the strike in 711 logged pairs — and
the parser counts the line, so the next swing smites then; the minute
is the fallback for a session that missed it (#191). A SMITE the
game answered with the advance from range or a roundtime is not
spent; the next swing tries again. SMITE CHECK goes out before each
smite, and with no free blow left ("Your conviction is enough to
deliver three blows ..." counts them) the swing is an ATTACK instead:
a smite past the free ones draws on the soul pool, and one with the
pool empty harms the soul (#217; docs/soul.md). A smite the game
answers "Drawing upon holy wrath" turns smiting off for the run.
A swing waits out a stun first (the status indicator, 20 s at most),
and one answered "You are still stunned." did not happen: the maneuver
keeps its turn, a self-combo's attack its place, and neither counts as
a miss (#336).
`tactics` lists tactical maneuvers in rotation ("bob", "circle",
"weave"): every third swing is the next one instead of ATTACK while
Tactics sits below mind-lock in the exp window — a maneuver is what
trains Tactics (Elanthipedia: Tactics skill; Bob, Circle and Weave
commands), it is non-damaging and takes a swing's roundtime, so the
rest stay ATTACK and SMITE keeps its minute; a maneuver answered with
nothing the table knows three times is off for the run (#190).
`buffs` are self-cast spells kept up through the hunt (PREPARE, CAST
before the walk to the ground — not among the prey, where four casts
were a minute standing in the badgers' room, 2026-09-20 — and whenever
the Spells window drops one), and
`train_casting` names the magic skills to train by recasting buffs
between swings — each cast for the skill with the emptiest pool, with
the first buff DISCERN says uses it (#374) — starting a step under
DISCERN's estimate and feeding more up to it until the game warns of
strain (#375), until the skills lock — one cast
per the profile's `cast_gap` seconds (60 by default: at 20 a badger
got six bites per swing, #189).
`debilitation` names a targeted spell ("Stun Foe") cast at the prey
between swings while Debilitation sits below lock — the same cast gap
and mana ramp, taking turns with the buff training cast so a swing
never carries two casts; a stunned foe bites nothing (#192).
`targeted` names an attack spell ("Footman's Strike") cast at the prey
the same way while Targeted Magic sits below lock — it takes the
weapon in hand as its focus, which the fight already holds; the buff
training cast, the debilitation cast and this one take turns, one
cast per swing at most (#200). Each of the two is DISCERNed once
before the weapon is drawn, and a spell the character's ranks cannot
carry — DISCERN's "You don't think you are able to cast this spell",
or a cast that "fails completely" for lack of skill — is off for the
run, the rank named, and the ranks the spell wants when DISCERN says
("reach the rank of a promising novice": 10) (#202, #203).
A cast never idles: the spell is PREPAREd (and a targeted one
TARGETed at the prey, as DISCERN says it must be), the swing goes out
while the pattern forms — PREPARE is answered during weapon roundtime,
so the swing's own roundtime covers the wait, and a long pattern (a
non-battle spell's 26 s) gets a swing per roundtime until it is nearly
ready, #250 — and CAST follows the last swing; a foe that went down
under a swing has the pattern RELEASEd rather than cast at nothing
(#203, after dr-scripts' combat-trainer).
A Barbarian casts nothing (client/game/barbarian.py, #328): `analyze`
names a self-combo ("flame") started whenever none runs while Expertise
sits below lock, its attacks ("... by landing a jab, a feint and a
slice.") swung in turn in place of ATTACK — never on the fists turn,
never in place of SMITE or a maneuver — which is what trains
Expertise; `abilities` lists berserks, forms and meditations kept up
the way `buffs` are, started before the walk and again when one ends
(meditations outside the fight only); `roar` is ROAR <name> at the
prey once a minute while Debilitation sits below lock. The wordings
are dr-scripts' (combat-trainer.lic, data/base-spells.yaml) and lich's
DRCA, uncaptured.
`weapons` lists the weapons the hunt trains, each with the skill it
trains — "handaxe:Small Edged:sack", "fists:Brawling" (the operator,
2026-09-20: no argument per weapon type, #238). The one whose skill
has the emptiest pool fights first and keeps the hands, kill after
kill, until its skill reaches the profile's `weapon_target` (30);
the next emptiest takes over after the kill that got it there, so
one more skill is moving at every hand-over (the operator,
2026-09-26: skills moving is the measure; it was one turn per kill).
With every weapon past the target, the emptiest unlocked one fights
on toward lock. A
turn's weapon is WIELDed after the last one is SHEATHEd back into its
container — WIELD finds it wherever it sits and remembers the place
(#259: the scimitar in the sack, the profile naming the scabbard, and
the turn swung bare-handed, before WIELD did the searching;
Elanthipedia: Wield command, Sheathe command — DRAW is an attack
maneuver, never the draw); the fists turn draws nothing and swings the profile's
`brawling` attacks in rotation — PUNCH, KICK, ELBOW (Elanthipedia:
Brawling skill, Punch command, Elbow command) — with the hands empty,
since PUNCH wants a free hand and a worn parry stick parries as it
is (Elanthipedia: Parry Ability skill), brass knuckles likewise.
Captured 2026-09-20 on a striped badger, the first live fists turn:
"you punch your brass knuckle at a striped badger" (the worn knuckles
are the fist), "you kick your foot at a striped badger", "you elbow
your plate-clad elbow at a striped badger" — each shaped like a
weapon swing in the combat stream, the kill line the same, so the
attacks need no table of their own. A
weapon whose skill sits at mind-lock is skipped until it drains; all
of them locked ends the hunt. A turn that goes twenty swings without a
kill passes to the next (a new weapon at rank 3 cannot finish the
ground's creatures, 2026-09-26); only sixty with no kill from any turn
break the hunt off. The knife, the skins, the casts and the
maneuvers are the same whatever is in hand, SMITE keeps its minute
when the profile smites, and with `weapons` empty the hunt is the
profile's `weapon` alone, never swapped. A single turn listed is that
turn — "fists:Brawling" alone hunts bare-handed whatever `weapon`
says (2026-09-20: the list was ignored below two entries, and every
kill tried to sheathe a scimitar that sat in the sack).
`perception` on: when a room of the ground has emptied, and on every
lap of an empty ground, one HUNT for tracks before moving on, at most
once per 75 seconds while Perception sits below lock — HUNT teaches
Perception on a 75-second timer (Elanthipedia: Hunt command); the
tracks are not followed, the ground's rooms are the map's (#194).
The weapon stays in hand when the hunt ends — stowed, it parries
nothing — and its container is only where the first swing fetches it
from.
Once a hunt, the first room with live creatures is weighed against
the weapon turns' ranks: a creature teaches nothing past its MaxCap
(Elanthipedia's Critter pages, client/game/creatures_data.py), and the
skills past the room's most generous one are said — "the cougar
teaches to rank 49 — Brawling 57, Small Edged 58 past it" — so a
ground the character has outgrown shows at once, not after five
hunts of 0/34 (#322).
The game's answers are classified by keyword (the tables in client/game/hunting.py, model
in docs/hunting.md); a skin or search answer the script cannot place is
echoed as "hunt: unrecognized ..." — report those and they become
fixtures. The skinning and gem-pouch commands follow Elanthipedia's
Skinning and Gem pouch pages; the fight follows docs/combat.md. First
cut: melee, one opponent at a time, no ranged; the only offensive
magic is the profile's targeted spell (#149, #200).
Three things end a fight the character is losing without the health
bar saying so (#236: an hour of grass eels — no kill, nine stuns,
every limb to deep cuts, the bar never below 67): 60 swings without a
kill or three stuns in one fight break the hunt off ("the ground is
beyond you", the burst escape, then home), and an unset `wound_floor`
means harmful, where bleeding starts — said once at the start; `off`
never asks HEALTH.
A swing is aimed by ordinal when a corpse of the prey's noun stands
first in the room's listing — "attack second cougar" — so it reaches
the live one instead of the corpse ("already quite dead", a spent
swing); the parser marks the corpses in `room_creatures_dead` —
which is also what counts a kill: a corpse the listing gained since
the fight in the room began, whatever the death line said (the
farmland goblins' "collapses to the ground, shuddering and moaning
until it ceases all movement" went uncounted, #314; a known line is a
hint, #315) — and
client/game/creatures.py counts them the way the game does, after
lich-5's drdefs.rb (#278). The balance word the game states ("solidly
balanced", lich-5's DRStats.balance) is tallied per swing and
reported at the end — a reading, no rule yet (#280).
"""

MAX_ACTIONS = 600  # swings per run, not forever — the fuse under the loop
# The outer fuse, moves and waits included: an empty ground laps for
# hours (a pause every EMPTY_LAPS laps), never for ever.
MAX_ITERATIONS = 5000
SETTLE_SECONDS = 1.0  # after arriving: the room's creature enumeration
EMPTY_ROOM_WAIT = 20  # seconds between looks when the whole ground is empty
EMPTY_LAPS = 2  # laps of the ground with nothing in it before the pause
# The ground-is-beyond-you fuses (#236): an hour of grass eels gave no
# kill and nine stuns, the health bar never crossed the floor, and the
# profile's wound floor was unset — nothing in the loop said stop while
# every limb went to deep cuts. Now a run of swings without a kill, or
# three stuns in one fight, is a break-off, and an unset wound floor is
# DEFAULT_WOUND_FLOOR (bleeding starts at harmful, docs/wounds.md) with
# "off" for never asking.
KILL_LESS_SWINGS = 60  # swings since the last kill before the hunt ends
STUN_LIMIT = 3  # stuns taken in one fight (a kill resets) before it ends
# Captured 2026-09-20 on the eels: "The teeth lands a light hit that
# lightly pierces the left forearm, lightly stunning you."
_STUNNED = ("stunning you",)
# A command sent while stunned does not happen: "You are still stunned."
# (captured 2026-09-26 on a circle-1 Barbarian among grass eels — a FEINT,
# a DRAW, a CIRCLE and a FEINT inside two seconds, the maneuvers reported
# as unrecognized and the self-combo's queue emptied, #336). The swing
# waits the stun out first (the status indicator, STUN_WAIT at most), and
# an answer that still says so is a swing that never went out.
_STILL_STUNNED = ("you are still stunned",)
STUN_WAIT = 20  # seconds a swing waits for a stun to pass
STUN_POLL = 0.5

# Bare ATTACK with every attacker dead (captured 2026-08-22).
_ALL_DEAD = ("nothing else to face", "what are you trying to attack")
# A corpse soaking swings (captured 2026-08-22, docs/combat.md); the
# noun can be several words — "The ship's rat is already quite dead."
_DEAD_NOUN = re.compile(r"The ((?:[\w'-]+ )*?)([\w'-]+) is already quite dead")
# Swings a corpse soaked after being disposed of before the room is
# declared clear anyway — the hostile state lagged for a whole hunt
# once (2026-09-05, before the parser learned dead="1").
CORPSE_SWINGS = 2
# The game's two "no such thing" wordings are act.NOT_FOUND: a SEARCH
# answered the second went unrecognized on 2026-09-20, so every table
# that knows the first knows both. A container with no room left
# (#262) is items.no_room.
# ATTACK from pole or missile range advances first (docs/combat.md;
# captured 2026-09-12): "You aren't close enough to attack." / "You
# begin to advance on a ship's rat." / "You are already advancing on a
# ship's rat." The swing comes once "melee range" is reached, so the
# loop waits for that line rather than asking again.
_ADVANCING = ("aren't close enough", "begin to advance", "already advancing")
ADVANCE_WAIT = 10  # seconds for "melee range" before the next ATTACK
# A maneuver from range does not advance on its own (captured 2026-09-20
# on a badger closing from pole range): "You must be closer to use
# tactical abilities on your opponent." — the loop ADVANCEs on the prey
# and waits for melee range, as ATTACK's own advance would.
# PUNCH and KICK at range fall through the same way (captured 2026-09-20
# on a badger closing from pole range, #257): PUNCH answers "Actually,
# using a weapon would probably be a bit more effective." and KICK its
# emote, "You kick some dirt on a striped badger in disgust." — neither
# with a roundtime, so the filler loop spent three commands in a second.
_NEED_MELEE = ("must be closer", "using a weapon would probably", "kick some dirt")
# SMITE (captured 2026-09-13 on a rat): "Drawing strength from your
# conviction, you execute a divinely inspired strike!" then the swing
# line as ATTACK would give it, 6 s roundtime. From range it answers
# like ATTACK ("aren't close enough", advancing). One free smite a
# minute, Conviction experience once a minute (Elanthipedia: Smite
# command), so the loop smites once a minute at most (#183).
_SMITE_STRUCK = ("divinely inspired strike",)
# A smite is fueled by Conviction's free blows first and the soul pool
# after (Elanthipedia: Smite command): a free one says "Drawing
# strength from your conviction, ...", a soul-pool one "Drawing upon
# holy wrath, ...", and a smite with the pool empty harms the soul —
# an evening of it took a Paladin to chalky grey (#217). So SMITE CHECK
# goes out first (captured 2026-09-20: "You contemplate the strength of
# your conviction. / Your conviction is enough to deliver three blows
# against your enemies before you must either rest or draw upon your
# spiritual strength to continue.") and the swing smites only while it
# counts a blow; a wrath strike, should one slip through, turns
# smiting off for the run.
_SMITE_WRATH = ("upon holy wrath",)
# SMITE with no weapon in hand — the fists' turn, brass knuckles worn —
# answers "You will need an appropriate weapon to channel a smite upon
# your foe." with no roundtime (captured 2026-10-01). The fists' turn
# never smites; the refusal spends the minute anyway, since the turn
# went 19 refused smites a second apart and handed over "20 swings
# without a kill" after one punch, every hunt (#396).
_SMITE_NO_WEAPON = ("need an appropriate weapon",)
# Tactical maneuvers (captured 2026-09-14 on a striped badger, #190):
# BOB "You bob suddenly, lowering yourself into a smaller target.",
# CIRCLE "You sidestep a striped badger suddenly, moving in a short
# circle around it.", WEAVE "You weave back and forth, trying to
# distract your opponent." — each followed by a balance line and
# "Roundtime: 3 sec.", and Tactics entered the exp window at rank 3 on
# the first BOB. CIRCLE has a second wording (2026-09-20, #240): "You
# fake a striped badger, first moving one way and then another, leaving
# it off balance." From range they do not advance like ATTACK: "You must
# be closer to use tactical abilities on your opponent." (2026-09-20),
# so the loop ADVANCEs on the prey itself (_NEED_MELEE). A maneuver
# aimed at a corpse answers as a swing would — "The striped badger is
# already quite dead." (2026-09-20, a BOB) — and the corpse branch below
# disposes of it; that is not a miss. Anything else is reported, and
# after TACTIC_MISSES of them the maneuvers are off.
# A maneuver the foe wins is an attempt all the same (the vineyard
# cougars, 2026-09-21, #265): "You hesitate and change your mind,
# circle back awkwardly.  The cougar easily out maneuvers you." with a
# 4 s roundtime — seven in the first run at Tactics 23.
_MANEUVER_DONE = (
    "you bob",
    "you sidestep",
    "you fake",
    "you weave",
    "out maneuvers you",
    "change your mind",
)
TACTIC_MISSES = 3  # unrecognized maneuver answers before tactics go off
# HUNT for tracks (captured 2026-09-14 in a guild office, #194): "You
# take note of all the tracks in the area, so that you can hunt
# anything nearby down.", a numbered list, "Roundtime: 8 sec."; "You
# were unable to locate any followable tracks." is the empty answer
# (the wiki's, captured on an empty Brambles room the same night).
# Perception learns from it once per 75 seconds.
_TRACKS_READ = ("take note of all the tracks", "unable to locate any followable tracks")
HUNT_INTERVAL = 75  # seconds between HUNTs: the skill's learning timer
TRACK_MISSES = 3  # unrecognized HUNT answers before the step goes off

# The rope is fetched by its whole name: "Only bundling ropes can be
# utilized, not lead ropes, heavy ropes, or the like." (BUNDLE HELP,
# captured 2026-09-28). A lead rope looted that day sat ahead of the
# bundling rope in the sack, GET MY ROPE took it, and BUNDLE answered
# the "full" wording for every one of 73 skins on 2026-10-01 — each
# stowed loose until the sack was full and one went to the backpack.
ROPE = "bundling rope"
BUNDLE_REFUSALS = 3  # refusals in a row before a run stops trying


def hostiles(state):
    return dict(getattr(state, "hostiles", None) or {})


def next_turn(s, profile, tally, from_current=False, leave=False):
    """The weapons entry to fight with. The one in hand while its skill
    sits below `turn_target` and its `weapon_minutes` have not run out
    (the fallback: a pool the casts' kills never fill hands on all the
    same, 2026-10-02) — a kill does not hand it on; else the open
    turn whose skill has the emptiest pool (the lowest mindstate; the
    lowest rank, then the plan's order after the one in hand, breaking
    ties — after a rest every pool reads 0, and the order alone gave the
    first three weapons each 30-minute hunt while Large Edged and Large
    Blunt, ranks 15 and 9, never got a turn, 2026-09-27), one below the
    target first and one past it, toward lock, when none is below. So
    each weapon fills to the target and the next starts moving (the
    operator, 2026-09-26: the number of skills moving is the measure).
    `from_current` is the hunt's start: nothing is in hand, the emptiest
    pool takes it, the lowest rank and then the plan's order breaking
    ties. `leave` hands the one
    in hand over (a stalled turn). None when no turn is open: every skill
    is locked (a turn with no skill never locks and is never below the
    target — it fights when nothing else can) or, with `leave`, the one
    in hand is the only one. The fists turn is skipped when the profile
    lists no brawling attacks, said once."""
    plan = weapon_plan(profile)
    if from_current:
        order = list(range(len(plan)))
    else:
        order = [(tally.weapon + step) % len(plan) for step in range(1, len(plan) + 1)]
    open_turns = []
    for index in order:
        entry = plan[index]
        if entry["skill"] and locked(s.state, [entry["skill"]]):
            continue
        if not entry["weapon"] and not brawling(profile):
            if not tally.fists_warned:
                tally.fists_warned = True
                s.echo(
                    "hunt: the profile lists no brawling attacks — fists turn skipped"
                )
            continue
        if leave and index == tally.weapon:
            continue
        open_turns.append(index)
    if not open_turns:
        return None

    def pool(index):
        skill = plan[index]["skill"]
        return mindstate_of(s.state, skill) if skill else MIND_LOCK

    target = turn_target(profile)
    held = tally.weapon
    if not from_current and held in open_turns and pool(held) < target:
        others = [index for index in open_turns if index != held]
        if not others or not turn_expired(profile, tally):
            return held
        open_turns = others  # its minutes are up: the emptiest other turn
    below = [index for index in open_turns if pool(index) < target]
    candidates = below or open_turns

    def rank(index):
        skill = plan[index]["skill"]
        return rank_of(s.state, skill) if skill else 0

    # Ties — after a rest every pool reads 0 — go to the skill trained
    # longest ago (the stores file's `turns`), then the lowest rank:
    # the plan's order alone starved the weakest weapons, the rank
    # alone the strongest (Brawling and Small Edged sat at 0 through a
    # hunt that filled the other three, 2026-09-28).
    last = getattr(tally, "turn_times", None) or {}

    def trained(index):
        return last.get(plan[index]["skill"] or "", 0)

    return min(
        candidates,
        key=lambda index: (
            pool(index),
            trained(index),
            rank(index),
            candidates.index(index),
        ),
    )


def arm(s, profile, tally, index):
    """Take the turn at `index`: the current weapon back into its
    container, the hands cleared, the new one GOT (nothing for the
    fists), the profile's `weapon` and `weapon_container` set to it so
    the knife, the skins and the put-back read the turn in hand."""
    entry = weapon_plan(profile)[index]
    if entry["skill"]:
        note_turn(s, tally, entry["skill"])
    if tally.armed and tally.armed != entry["weapon"]:
        unready(s, profile)  # the last turn's weapon back where it lives
    tally.weapon = index
    tally.turn_started = tally.swings
    tally.turn_clock = hunting.clock()
    tally.armed = entry["weapon"]
    profile["weapon"] = entry["weapon"]
    profile["weapon_container"] = entry["container"]
    clear_hands(s, profile)
    draw(s, profile)
    if entry["skill"]:
        s.echo(
            f"hunt: {entry['weapon'] or 'fists'} for {entry['skill']}"
            f" ({mindstate_of(s.state, entry['skill'])}/34) — to {turn_target(profile)}"
        )


def pass_turn(s, profile, tally):
    """The next open turn takes the hands, said; False when there is none
    other than the one in hand."""
    index = next_turn(s, profile, tally, leave=True)
    if index is None or index == tally.weapon:
        return False
    weapon = weapon_plan(profile)[tally.weapon]["weapon"] or "fists"
    s.echo(
        f"hunt: {weapon} has gone {TURN_STALL_SWINGS} swings without a kill — "
        "the next turn"
    )
    arm(s, profile, tally, index)
    return True


def rotate(s, profile, tally):
    """After a kill: the turn in hand keeps the hands until its skill
    reaches the target, then the emptiest open one takes them. False when
    every weapon skill is locked — the hunt's end, unless the hunt is a
    farm (`until` boxes): its end is the box count, and the weapon in
    hand keeps swinging (2026-09-26: the boxes style's mace locked Small
    Blunt five kills in and ended the farm)."""
    tally.rotated_at = tally.kills
    index = next_turn(s, profile, tally)
    if index is None:
        return farming(profile)
    if index != tally.weapon:
        entry = weapon_plan(profile)[tally.weapon]
        if (
            entry["skill"]
            and mindstate_of(s.state, entry["skill"]) < turn_target(profile)
            and turn_expired(profile, tally)
        ):
            s.echo(
                f"hunt: {entry['weapon'] or 'fists'} has had its "
                f"{turn_minutes(profile)} minutes ({entry['skill']} "
                f"{mindstate_of(s.state, entry['skill'])}/34) — the next turn"
            )
        arm(s, profile, tally, index)
    return True


def health(state):
    vitals = getattr(state, "vitals", None) or {}
    return vitals.get("health")


# How long a swing whose answer reads as a kill waits for the room's
# listing to mark the corpse, when it has not yet (#315).
LISTING_WAIT = 1.0


def _room_key(state):
    return (getattr(state, "room_uid", None), getattr(state, "room", None))


def corpses(state):
    """The room listing's corpses by name — "a dour forager goblin which
    appears dead" is "dour forager goblin" (the parser's
    room_creatures / room_creatures_dead, #278) — as a Counter."""
    names = list(getattr(state, "room_creatures", None) or [])
    dead = list(getattr(state, "room_creatures_dead", None) or [])
    return Counter(name for name, flag in zip(names, dead) if flag)


def mark_room(s, tally):
    """Take the room's corpses as the baseline when the fight is in a
    new room: a body on the ground at arrival was someone else's."""
    key = _room_key(s.state)
    if key != tally.dead_room:
        tally.dead_room = key
        tally.dead_seen = corpses(s.state)


def new_corpses(s, tally):
    """The corpses the listing gained since the baseline, oldest name
    first, and the baseline moved to now (a corpse that decayed lowers
    it). The kill is the listing's word, not the death line's: the
    death lines are a list that never ends — the rat's, the cougar's,
    the goblins' "collapses to the ground, shuddering and moaning until
    it ceases all movement" (2026-09-25, missed, #314) — while the
    listing marks every corpse "which appears dead" (dr-scripts'
    combat-trainer loots by DRRoom.dead_npcs the same way, #315)."""
    now = corpses(s.state)
    gained = now - tally.dead_seen
    tally.dead_seen = now
    return list(gained.elements())


def unrecognized(s, tally, what, answer):
    unknown(s, "hunt", what, answer, tally)


def wound_at_floor(s, profile):
    """HEALTH, read against the profile's wound floor: the (area, kind,
    level) that meets it, or None. "" never asks."""
    floor = wound_floor(profile)
    if not floor:
        return None
    try:
        wanted = level(floor)
    except ValueError:
        s.echo(f"hunt: wound floor {floor!r} is not a severity — ignoring it")
        profile["wound_floor"] = "off"
        return None
    # The injuries panel the game pushes on every change (#163) says
    # whether anything is hurt at all: a clean panel means no HEALTH
    # to ask; a lit one means HEALTH decides how bad.
    panel = getattr(s.state, "injuries", None)
    if isinstance(panel, dict) and not panel:
        return None
    health = parse_health(ask(s, "health"))
    for fragment in health.unknown:
        s.echo(f"hunt: unrecognized wound {fragment!r} — please report it")
    hits = health.at_least(wanted)
    return max(hits, key=lambda hit: hit[2]) if hits else None


BROKE_OFF = (  # a break-off's reasons: the ground is left, home or not
    "below the floor",
    "at the wound floor",
    "beyond you",
    "ground taken",
)


def off_ground(db, ground):
    """The mapped rooms one move outside the ground: where a break-off
    with no home goes (#185)."""
    inside = set(ground)
    outside = set()
    for room in ground:
        for dest in db.rooms.get(room, {}).get("wayto") or {}:
            try:
                dest = int(dest)
            except (TypeError, ValueError):
                continue
            if dest not in inside and dest in db.rooms:
                outside.add(dest)
    return outside


def leave_ground(s, db, ground, avoid):
    """No home to walk to after a break-off: the nearest room off the
    ground, said so — never the ground itself (Cecil stood on it two
    and a half hours and died there, 2026-09-13, #185)."""
    goals = off_ground(db, ground)
    if goals and travel.go(s, goals, "off the ground", db=db, walk=walk, avoid=avoid):
        s.echo(
            f"hunt: no home in the profile — left the ground for "
            f"{s.state.room_title}; set home so a break-off walks somewhere safe"
        )
        return True
    s.echo(
        "hunt: no home in the profile and no room off the ground to reach — "
        "you are still on the ground; move, and set home"
    )
    return False


def escape(s, db=None):
    """The break-off: flight's burst — RETREAT, RETREAT, a move through
    the type-ahead (docs/combat.md) — again with the next exit until the
    room changes or no hostile is left, and the move that landed written
    to the local map when the map says otherwise. One blind burst down
    the first exit was the whole of it until 2026-09-26: twice in the
    Crossing farmland it landed in a room the map had under another
    direction, the walk off the ground found no path, and the hunt ended
    with the character among the hostiles (#314). True when clear."""
    for attempt in range(flight.ATTEMPTS):
        candidates = flight.moves(s.state)
        move = candidates[attempt % len(candidates)]
        here = locate(db, s.state) if db is not None else None
        before = getattr(s.state, "room_uid", None)
        s.echo(f"hunt: breaking off — retreating {move}")
        flight.burst(s, move)
        if getattr(s.state, "room_uid", None) != before:
            note_landing(s, db, here, move)
            return True
        if not hostiles(s.state):
            return True
    s.echo("hunt: could not get clear of them — intervene if you can")
    return False


def note_landing(s, db, here, move):
    """The room a move from `here` landed in, written to the local map
    when the map has no such move from there or sends it elsewhere —
    the walker's own correction (#232) for a break-off's move, so the
    next walk plans with it (#314: 1473's southeast is 1479, which the
    map filed under southwest)."""
    if db is None or here is None:
        return
    there = locate(db, s.state)
    if there is None or db.same_place(here, there):
        return
    wayto = db.rooms.get(here, {}).get("wayto") or {}
    # "ne" and "northeast" are one move: the escape sends the compass's
    # abbreviation, the map spells it out (a false "had ne wrong" on the
    # Siergelde Cliffs, 2026-09-26).
    spelled = DIRECTIONS.get(move, move)
    mapped = next(
        (
            dest
            for dest, command in wayto.items()
            if DIRECTIONS.get(command, command) == spelled
        ),
        None,
    )
    try:
        mapped = int(mapped) if mapped is not None else None
    except (TypeError, ValueError):
        mapped = None
    if mapped is not None and db.same_place(mapped, there):
        return
    db.record_edge(here, there, move)
    s.echo(
        f"hunt: the map had {move} from {here} wrong — it leads to {there}; "
        "written to the local map"
    )


def draw(s, profile):
    """The weapon into a hand: WIELD searches the inventory for it and
    remembers where it came from, so SHEATHE puts it back there
    (Elanthipedia: Wield command, Sheathe command; captured 2026-09-22:
    "You draw out your steel scimitar from the leather scabbard,
    gripping it firmly in your right hand.", "You're already holding a
    watered steel scimitar!"). The scimitar that sat in the sack while
    the profile named the scabbard (#259) is found by the game itself
    now. False when the game finds no such weapon at all, said once."""
    weapon = profile["weapon"]
    if not weapon:
        return True
    # By its INV LIST id when listed (#456): the exact weapon, not the
    # first the game matches.
    answer = hands.wield(s, weapon, profile.get("weapon_container") or "", ask=ask)
    if missing(answer.lower()):
        s.echo(f"hunt: no {weapon} to draw — the game finds none on you")
        return False
    return True


def clear_hands(s, profile):
    """STOW whatever a hand holds that is not the thing about to be
    drawn: the hunt and the brawl take turns (the handaxe, then the
    parry stick), and a tool left in hand from the last run would take
    the other hand the next one needs — PUNCH wants a free hand (the
    operator's parry stick, 2026-09-20). Another turn's weapon still in
    hand (every hunt ends with its weapon in hand, go_home) is SHEATHEd
    into its own container first: a STOW sends it to the default one,
    which refused the spear — "The narrow-headed spear is too long to
    fit in the backpack." — and the box farm's sledgehammer came out
    into the other hand beside it (2026-10-03, #439). Never DROP."""
    weapon = profile.get("weapon") or ""
    for other, container in known_weapons(s, profile).items():
        if other != weapon and hands.holding(s, other):
            hands.sheathe(s, other, container, ask=ask)
    hands.free(s, keep=(weapon,) if weapon else (), ask=ask)


def known_weapons(s, profile):
    """{weapon: container} for every weapon the character's profile
    names: this run's turns, then the base list and every hunt style's.
    A style's turns replace the base list, so the box farm's (mace,
    broadsword, sledgehammer) knew nothing of the spear the hunt before
    left in hand, and STOWed it into the backpack's refusal again
    (2026-10-03, #439)."""
    base = load_profile(getattr(s.state, "name", None) or "")
    lists = [weapon_plan(profile)] + [
        [parse_weapon(entry) for entry in source.get("weapons") or []]
        for source in [base, *profile_styles(base).values()]
    ]
    found = {}
    for entries in lists:
        for entry in entries:
            if entry["weapon"] and entry["weapon"] not in found:
                found[entry["weapon"]] = entry["container"]
    return found


def ready(s, profile, tally=None, index=0):
    """Hands cleared, the first turn's weapon in hand and stance set
    before the first swing."""
    if tally is not None and has_turns(profile):
        arm(s, profile, tally, index)
    else:
        clear_hands(s, profile)
        draw(s, profile)
    if profile["stance"]:
        ask(s, f"stance set {profile['stance']}")


def unready(s, profile):
    """The weapon back where it lives: SHEATHE, where WIELD drew it from
    (the game remembers); asked "Sheathe your ... where?" (nothing
    remembered), into the profile's container, else STOW (hands.sheathe)."""
    weapon = profile["weapon"]
    if weapon:
        hands.sheathe(s, weapon, profile["weapon_container"], ask=ask)


def free_hand(s, profile):
    """The weapon out of the hand for a moment: sheathed, or stowed."""
    unready(s, profile)


def held_skin(s, profile):
    """The noun of whatever a hand holds besides the weapon and the
    profile's skinning knife — the skin SKIN just cut — or None when
    nothing did land. Only asked of a handle with hand state (hasattr
    left_hand); a bare one never reaches here. (A held skinning knife,
    Grek's, bought 2026-09-14, sat in the off hand after every cut and
    would have been taken for the skin.)"""
    tools = {profile["weapon"], profile.get("skin_knife") or ""}
    for noun in hands.nouns(s):
        if noun not in tools:
            return noun
    return None


def wear_bundle(s, profile, tally):
    """Before the weapon is drawn: a bundle the character already has
    goes on, so the run's skins land in it — TAP finds it worn from
    the last run, in hand, or in the loot container (a GET from the
    container missed a worn one, 2026-09-12). None anywhere leaves
    tally.bundle None and the first skin starts one."""
    if not profile["bundle"]:
        return
    where = classify(ask(s, "tap my bundle"), TAP_OUTCOMES)
    if where == "none":
        return
    if where != "worn":
        container = profile["loot_container"]
        by_id(
            s,
            "get",
            items.listed_ref(s, "bundle", worn=False),
            f"get my bundle from my {container}" if container else "get my bundle",
        )
        if not put_on_bundle(s):
            bundle_unworn(s, profile, tally)
            return
    tally.bundle = True
    s.echo("hunt: bundle worn — skins go straight into it")


# WEAR MY BUNDLE where the TOGGLE setting puts bundles can find that
# place taken (captured 2026-10-03, #438, after a baldric and a tote
# went on): "You can't wear any more items like that." — and the hunt
# fought on with the bundle in hand, every SKIN "You must have one hand
# free to skin." TOGGLE BUNDLE alone moves the setting to the next place
# ("From now on, your bundles will be draped around your shoulder."; a
# word after it is ignored), and WEAR then matches it: "[Matching your
# bundle to your TOGGLE setting.  See TOGGLE LIST to change this.]" /
# "You drape a lumpy bundle around your shoulders." — the second place
# tried. Elanthipedia's Bundle command names six: shoulder, waist,
# back, around shoulders, belt, and clear.
WEAR_TAKEN = ("can't wear any more",)
TOGGLE_PLACES = 6


def by_id(s, verb, ref, command):
    """VERB the item by its INV LIST id when there is one, else (or
    when the game no longer knows the id, forgotten for the session)
    the noun `command`; the answer (#456)."""
    if ref:
        answer = ask(s, f"{verb} {ref}")
        if not missing(answer):
            return answer
        items.forget(ref)
    return ask(s, command)


def put_on_bundle(s):
    """WEAR the bundle in hand, by its id (#456); a place already taken
    moves the TOGGLE setting on and wears again, up to TOGGLE_PLACES.
    True when it went on."""
    bundle = items.ref(s, "bundle") or "my bundle"
    answer = ask(s, f"wear {bundle}")
    moved = None
    for _ in range(TOGGLE_PLACES):
        if not any(word in answer.lower() for word in WEAR_TAKEN):
            break
        moved = said(ask(s, "toggle bundle"))
        answer = ask(s, f"wear {bundle}")
    if any(word in answer.lower() for word in WEAR_TAKEN) or missing(answer):
        return False
    if moved:
        s.echo(f"hunt: the bundle's place was taken — TOGGLE BUNDLE: {moved}")
    return True


def bundle_unworn(s, profile, tally):
    """A bundle that goes on nowhere: stowed, and the run's skins go
    loose; with no room for it either it stays in hand, and skinning is
    off for the run — a held bundle leaves no hand to skin with (#438)."""
    tally.bundle = False
    if stow(s, profile, "bundle"):
        s.echo(
            "hunt: the bundle goes on nowhere (TOGGLE LIST) — stowed; "
            "skins are stowed loose this run"
        )
        return
    s.echo(
        "hunt: the bundle goes on nowhere and there is no room for it — "
        "it stays in hand and skinning is off for this run"
    )
    profile["skin"] = False


def get_rope(s):
    """The bundling rope into a hand: by its INV LIST id, else GET MY
    BUNDLING ROPE from whatever container holds it (#437, #456)."""
    return by_id(s, "get", items.listed_ref(s, ROPE, worn=False), f"get my {ROPE}")


def make_bundle(s, profile, tally):
    """The first skin of the run, in hand, starts the bundle: the weapon
    goes back to free a hand, GET MY BUNDLING ROPE takes the rope from
    whatever container holds it (#437: GET FROM the loot container
    missed a rope left in the old one, and 49 skins went loose), BUNDLE
    ties the skin to it, the bundle goes on, the weapon comes back.
    True with the bundle worn. No rope: said once, and the run's skins
    are stowed loose. A fists turn has no weapon to put back, and the
    cambrinth piece held for a charged cast can fill the other hand:
    "You need a free hand to pick that up.", then BUNDLE with no rope
    ("You don't have any bundles ...") read as a refusal, and the fang
    went loose (2026-10-03, #451). The piece goes back on (its charge
    stays in it) and the rope is fetched again; with still no hand the
    skin is stowed and the next one tries."""
    free_hand(s, profile)
    answer = get_rope(s)
    piece = profile.get("cambrinth") or ""
    if any(word in answer.lower() for word in loot.FREE_HAND):
        if piece and hands.holding(s, piece):
            ask(
                s,
                f"wear my {piece}"
                if profile.get("cambrinth_worn")
                else f"stow my {piece}",
            )
            answer = get_rope(s)
        if any(word in answer.lower() for word in loot.FREE_HAND):
            s.echo(
                "hunt: no free hand for the bundling rope — this skin is stowed loose"
            )
            draw(s, profile)
            return False
    if missing(answer):
        s.echo(
            "hunt: no bundling rope — ASK a tanner FOR ROPE (it is free); "
            "skins are stowed loose this run"
        )
        tally.bundle = False
        draw(s, profile)
        return False
    answer = ask(s, "bundle")
    outcome = classify(answer, BUNDLE_OUTCOMES)
    if outcome == "ok":
        if not put_on_bundle(s):
            bundle_unworn(s, profile, tally)  # the skin is in it, stowed too
            draw(s, profile)
            return True
        tally.bundle = True
        s.echo("hunt: bundle started and worn — skins go straight into it")
        draw(s, profile)
        return True
    if outcome == "full":
        # This skin will not start a bundle (a curved claw, captured
        # 2026-09-21, #260): stowed loose, the bundle left untried so
        # the next skin starts it — up to BUNDLE_REFUSALS in a row,
        # then the run's skins go loose without the rope's round trip.
        tally.bundle_refusals += 1
        stow(s, profile, ROPE)
        if tally.bundle_refusals >= BUNDLE_REFUSALS:
            tally.bundle = False
            s.echo(
                f"hunt: BUNDLE refused {BUNDLE_REFUSALS} skins in a row — "
                "skins are stowed loose this run"
            )
        else:
            s.echo(
                "hunt: BUNDLE would not take that skin — stowed; "
                "the next one starts the bundle"
            )
        draw(s, profile)
        return False
    unrecognized(s, tally, "bundle", answer)
    tally.bundle = False
    stow(s, profile, ROPE)
    draw(s, profile)
    return False


def cast_buffs(s, profile, tally, fight=False, filler=None):
    """The profile's buffs, cast and kept up by client/game/buffs.py
    with the hunt's answer windows and its unrecognized-answer tally.
    In the fight (`fight`) the targeted spells — the profile's
    `debilitation` and `targeted` — go out at the prey too, taking
    turns with the buff training cast (buffs.next_cast), so a swing
    never carries two casts (#192, #200). Outside the fight, each
    targeted spell is DISCERNed once per run first, so one the ranks
    cannot carry never costs a PREPARE (#202). In the fight the
    iteration's swing (`filler`) goes out while the first pattern
    forms, and the roundtime is waited before the cast — and a long
    pattern (a non-battle spell's 26 s) is swung into again for as
    long as a roundtime fits, every swing counted (#250); True when a
    swing went out, so the loop does not swing again (#203)."""
    state = tally.buffs
    taken = {"alive": None}

    def report(what, answer):
        unrecognized(s, tally, what, answer)

    # A Barbarian's abilities and roar (#328): none for a profile without
    # them, so a caster's hunt is untouched.
    barbarian.keep_abilities(s, profile, tally.barb, ask, "hunt", report, fight=fight)
    if fight:
        barbarian.roar(s, profile, tally.barb, ask, "hunt", report, profile["prey"])

    def fill():
        if taken["alive"] is not None:
            tally.swings += 1  # the loop counted the first
        taken["alive"] = filler()
        s.waitrt()
        return taken["alive"]

    swing_first = fill if fight and filler is not None else None
    if not fight:
        buffs.discern_slots(s, profile, state, ask, "hunt", report)
    turn = buffs.next_cast(s, profile, state) if fight else None
    if turn in buffs.TARGETED_SLOTS:
        buffs.cast_targeted(
            s,
            profile,
            state,
            ask,
            "hunt",
            report,
            turn,
            target=profile["prey"],
            filler=swing_first,
        )
        buffs.cast_buffs(
            s, profile, state, ask, "hunt", report, train=False, filler=swing_first
        )
    else:
        buffs.cast_buffs(s, profile, state, ask, "hunt", report, filler=swing_first)
    return taken["alive"] is not None


def bundled(s, profile, tally):
    """True when the skin just cut is in a worn bundle: it went there on
    its own (the skinning hand is empty), BUNDLE moved it there, or
    make_bundle started one around it. False leaves it to be stowed."""
    if not profile["bundle"] or tally.bundle is False:
        return False
    if not hasattr(s.state, "left_hand"):
        return False  # no hand state to judge by
    if held_skin(s, profile) is None:
        return True
    if tally.bundle:
        ask(s, "bundle")
        held = held_skin(s, profile)
        if held is None:
            return True
        s.echo(
            f"hunt: the bundle took no more (a {held} still in hand) — skins "
            "are stowed loose from here"
        )
        tally.bundle = False
        return False
    return make_bundle(s, profile, tally)


def stow(s, profile, item):
    """An item in hand into the loot container, else the STOW default;
    False when neither has room (#262), the item still in hand."""
    container = profile["loot_container"]
    if container:
        if not items.no_room(ask(s, f"put my {item} in my {container}")):
            return True
    return not items.no_room(ask(s, f"stow my {item}"))


# STORE's option per loot kind and the profile key naming its
# container: STORE BOXES IN <loot_container>, STORE GEMS IN
# <gem_pouch> — bare, STORE HELP's own form: STORE takes one or two
# words and refused "in my herb bag" (#415, 2026-10-02) — sent when
# the container changes (STORE HELP, 2026-09-26: "You can only store things in
# containers that you are wearing"; STORE LIST showed boxes "--Not
# Set--", so a STOWed box went to the default container, the backpack,
# where ;boxes never looked, #323).
STORES = {"box": ("boxes", "loot_container"), "gem": ("gems", "gem_pouch")}


def stores_set(profile, what):
    """True when the hunt set STORE for this kind this run (set_stores)."""
    return what in (profile.get("_stores") or ())


STORED = (
    "you will now store",
)  # captured 2026-09-26: "You will now store boxes in your canvas sack."


# Where the STORE containers ;hunt last set are remembered, per
# character: client/game/stores.py, which ;boxes reads too (#432).
stores_path = stores.path
load_stores = stores.load
remember_stores = stores.remember


def note_turn(s, tally, skill):
    """A weapon turn taken: its skill's time into the stores file's
    `turns`, so the next hunt's ties go to the one trained longest ago."""
    now = time.time()
    tally.turn_times = dict(getattr(tally, "turn_times", None) or {}) | {skill: now}
    character = getattr(s.state, "name", None)
    known = load_stores(character)
    known["turns"] = dict(known.get("turns") or {}) | {skill: now}
    try:
        remember_stores(character, known)
    except OSError:
        pass  # a remembered order is a nicety, never a stop


def set_stores(s, profile):
    """STORE each loot kind in the profile's container — only when that
    container is not the one last set: STORE is the game's own setting
    and stays until changed (the operator, 2026-09-26). The kinds STOW
    GEM / STOW BOX may use are kept in the profile as `_stores` (a
    run-only key); a refusal is said, and that kind is picked up by hand."""
    character = getattr(s.state, "name", None)
    known = load_stores(character)
    done = []
    for what, (option, key) in STORES.items():
        container = str(profile.get(key) or "").strip().lower()
        if not container:
            continue
        if known.get(option) != container:
            answer = ask(s, f"store {option} in {container}")
            if not any(word in answer.lower() for word in STORED):
                s.echo(
                    f"hunt: STORE {option} answered {said(answer)!r} — {option} picked up by hand"
                )
                continue
            known[option] = container
            remember_stores(character, known)
        done.append(what)
    profile["_stores"] = tuple(done)
    return done


def pocket(s, profile, item):
    """Something a search turned up: picked up, then a gem into the gem
    pouch when the profile keeps one, anything else — or a gem the
    pouch refuses — stowed like loot. Only "You put" is a pouching: a
    S'lai scout's plovik leaves went at a full pouch, "There isn't any
    more room in the pouch for that.", and stayed in hand through the
    fight (2026-09-28). With STORE GEMS set this run a gem goes by STOW
    GEM, one command to the pouch, as the operator's did: "You pick up a
    small laced clear crystal." / "You open your pouch and put the clear
    crystal inside, closing it once more." (2026-10-03). It picks up
    first, so it wants a free hand like the GET: both answered "You
    need a free hand to pick that up." with a lockpick in the off hand.
    A gem in hand goes to the pouches by id (gems.put, #456): the STORE
    pouch full, the next one with room takes it."""
    pouch = profile["gem_pouch"]
    gem = pouch and noun_of(item) in loot.GEM_NOUNS
    if gem and stores_set(profile, "gem"):
        answer = ask(s, "stow gem").lower()
        outcome = classify(answer, loot.STOW_OUTCOMES)
        if outcome == "stowed":
            gems.room()
            return
        if outcome in ("gone", "not yours"):
            return
        if outcome == "no room" and "you pick up" in answer:
            # Picked up, and the STORE pouch full: in hand, another
            # pouch INV LIST showed takes it, or it goes with the loot.
            if (
                gems.by_id(s, profile)
                and gems.put(s, profile, gem_ref(s, item), ask)[0]
            ):
                gems.room()
                return
            s.echo(f"hunt: the {pouch} is full — the {item} goes with the loot (#283)")
            gems.mark()
            stow(s, profile, item)
            return
    ask(s, f"get {item}")
    if gem:
        ok, answer = gems.put(s, profile, gem_ref(s, item), ask)
        if ok:
            gems.room()
            return
        if gems.full(answer):
            s.echo(f"hunt: the {pouch} is full — the {item} goes with the loot (#283)")
        gems.mark()  # loose with the loot: the gems chore pouches it later (#437)
    if noun_of(item) in cards.KINDS:
        cards.mark(noun_of(item))  # into its case at the next safe point (#457, #459)
    stow(s, profile, item)


def gem_ref(s, item):
    """The picked-up gem as a PUT names it: its id from the hand, else
    MY <item>."""
    return items.ref(s, noun_of(item)) or f"my {item}"


def has_skin(s, corpse, tally):
    """False when the wiki says the creature behind `corpse` (a noun)
    cannot be skinned — its listing name looked up in SKINNABLE — said
    once a run; True otherwise, the unknown included (#494)."""
    names = [
        name
        for name in (getattr(s.state, "room_creatures", None) or [])
        if noun_of(name) == corpse
    ] or [corpse]
    if not any(skinnable(name) is False for name in names):
        return True
    if corpse not in tally.unskinnable:
        tally.unskinnable.add(corpse)
        s.echo(f"hunt: the {corpse} has no skin — not skinning")
    return False


def skin(s, profile, corpse, tally):
    knife = profile["skin_knife"]
    if knife:
        ask(s, f"get my {knife}")
    answer = ask(s, f"skin {corpse}")
    outcome = classify(answer, SKIN_OUTCOMES)
    if outcome == "hands_full":
        # The last skin never left the off hand (2026-09-12: a rat
        # tail whose success line landed after the roundtime): stow
        # what the parser says is there, or the hand itself, and once more.
        held = hands.held(s)["left"]
        piece = profile.get("cambrinth") or ""
        if held and held == piece and profile.get("cambrinth_worn"):
            # The worn cambrinth piece, off for a charge when the kill
            # came (2026-09-23: the anklet went into the sack as if it
            # were a skin, and the cast's INVOKE found nothing in hand).
            ask(s, f"wear my {piece}")
        elif held:
            stow(s, profile, held)
        else:
            ask(s, "stow left")
        answer = ask(s, f"skin {corpse}")
        outcome = classify(answer, SKIN_OUTCOMES)
    if outcome == "ok":
        tally.skins += 1
        if "into your bundle" in answer.lower() or bundled(s, profile, tally):
            # The game said so ("You carefully fit a pink grendel ear
            # into your bundle.", #272), or the hands say it landed.
            pass  # in the worn bundle, nothing in hand to stow
        elif found := items_in(answer):
            if not stow(s, profile, found[-1]):
                # Nowhere to put it (#262): it stays in hand, and no more
                # are cut this run. Never a DROP.
                s.echo(
                    f"hunt: no room for the {found[-1]} anywhere — it stays in "
                    "hand and skinning is off for this run"
                )
                profile["skin"] = False
        else:
            ask(s, "stow left")  # the skin's hand, by convention (assumption)
    elif outcome == "no_knife":
        s.echo("hunt: nothing to skin with — skinning is off for this run")
        profile["skin"] = False
    elif outcome is None:
        unrecognized(s, tally, "skin", answer)
    if knife:
        stow(s, profile, knife)


def listing(s):
    return str(getattr(s.state, "room_objs", "") or "")


def boxes_full(s, profile, tally, noun, held):
    """The loot container refused a box: no box is picked up for the
    rest of the run — a farm ends on it — said once, with where the
    refused one is (in hand, since a GET or STOW BOX picked it up; never
    dropped)."""
    tally.boxes_full = True
    container = profile.get("loot_container") or "pack"
    where = "is in hand — ;boxes works it first" if held else "stays on the ground"
    s.echo(
        f"hunt: the {container} is full — the {noun} {where}; no more boxes this run"
    )


def grab(s, profile, before, tally):
    """What the search left on the ground, read off the room listing
    (client/game/loot.py, after combat-trainer's LootProcess): each
    lootable entry — coins, a gem, a box, the profile's additions —
    taken with one STOW and its answer read; a gem goes to the pouch
    the profile names instead; another hunter's loot is left; a noun
    the game finds no room for is unlootable for the rest of the run.
    The nouns taken, for the wording path to skip."""
    s.sleep(0.5)  # the listing's rewrite lands a beat after the answer
    taken = []
    creatures = getattr(s.state, "room_creatures", None) or ()
    additions = profile.get("loot_additions") or ()
    subtractions = profile.get("loot_subtractions") or ()
    ignore = profile.get("loot_ignore") or ()
    limit = int(profile.get("box_limit") or 0)
    for entry in loot.new_items(before, listing(s), creatures):
        if not loot.lootable(entry, additions, subtractions, ignore):
            continue
        what = loot.kind(entry)
        # The entry's own noun, coins included: a lone "bronze coin"
        # answers GET COIN, never GET COINS (2026-09-26, the goblins'
        # Dokora left on the ground, "What were you referring to?").
        noun = loot.noun_of(entry)
        if noun in tally.unlootable:
            continue
        if what == "box" and tally.boxes_full:
            continue  # said once, when the container refused the first
        if what == "box" and limit and tally.boxes >= limit:
            s.echo(f"hunt: {limit} box(es) carried — the {noun} stays")
            continue
        if what in ("gem", "box") and stores_set(profile, what):
            # STOW GEM / STOW BOX: the first of its kind on the ground
            # straight into its STORE container, no hand needed (the
            # operator, 2026-09-26); anything but a stow falls through
            # to the GET below.
            since = hands.mark(s)
            answer = ask(s, f"stow {what}").lower()
            outcome = classify(answer, loot.STOW_OUTCOMES)
            if any(line in answer for line in loot.POUCH_FULL):
                outcome = "pouch full"  # the spare pouch is #283
            if outcome == "stowed":
                if what == "box":
                    tally.boxes += 1
                    note_box(s, profile, tally, since, noun, entry)
                else:
                    gems.room()  # the pouch took one: it has room (#437)
                taken.append(noun)
                continue
            if outcome == "not yours":
                s.echo(f"hunt: the {noun} is someone else's — left")
                continue
            if outcome == "no room":
                tally.unlootable.add(noun)
                if what == "box":
                    # "You pick up a reinforced oaken chest. There isn't
                    # any more room in the sack for that." — STOW BOX
                    # leaves the box in hand (2026-09-26): no GET after
                    # it, and no box after it, or the next one takes the
                    # weapon's hand (the casket did, a minute later).
                    boxes_full(s, profile, tally, noun, "you pick up" in answer)
                    taken.append(noun)
                else:
                    s.echo(f"hunt: no room for the {noun} — it stays on the ground")
                continue
            if outcome == "gone":
                continue
            if outcome is None:
                unrecognized(s, tally, f"stow {what}", answer)
        if what == "gem" and profile.get("gem_pouch"):
            pocket(s, profile, noun)
            taken.append(noun)
            continue
        since = hands.mark(s)
        answer = ask(s, f"get {noun}").lower()
        outcome = classify(answer, loot.STOW_OUTCOMES)
        if outcome == "free hand":
            free_hand(s, profile)
            since = hands.mark(s)
            answer = ask(s, f"get {noun}").lower()
            outcome = classify(answer, loot.STOW_OUTCOMES)
        if outcome == "not yours":
            s.echo(f"hunt: the {noun} is someone else's — left")
            continue
        if outcome == "no room":
            tally.unlootable.add(noun)
            if what == "box":
                boxes_full(s, profile, tally, noun, False)
            else:
                s.echo(f"hunt: no room for the {noun} — it stays on the ground")
            continue
        if outcome in ("gone", "held"):
            continue
        if outcome is None:
            unrecognized(s, tally, "get", answer)
            continue
        if what == "coins":
            tally.coins += 1  # coins go to the purse on GET
            continue
        # The box in hand: its tag even where the parser keeps no
        # last_held (a session started before #423).
        held = hands.tag_of(s, noun) if what == "box" else None
        if not stow(s, profile, noun):
            tally.unlootable.add(noun)
            taken.append(noun)
            if what == "box":
                boxes_full(s, profile, tally, noun, True)
            else:
                s.echo(f"hunt: no room for the {noun} anywhere — it stays in hand")
            continue
        if what == "box":
            tally.boxes += 1
            note_box(s, profile, tally, since, noun, entry, held)
        if noun in cards.KINDS:
            cards.mark(noun)  # into its case at the next safe point (#457, #459)
        taken.append(noun)
    return taken


def note_box(s, profile, tally, since, noun, description, held=None):
    """A box picked up, as a history.db `box_drops` row (#423): its item
    id — off the hand tag that showed it, though a STOW straight off the
    ground empties the hand on the same line — beside the creature and
    the search that found it, so ;boxes can tell what it held to the
    creature and the ground."""
    tag = hands.passed_through(s, since, noun) or held
    search = tally.search or {}
    boxlog.log_drop(
        s,
        box_id=(tag or {}).get("exist"),
        noun=noun,
        description=str(description or noun),
        creature=search.get("creature"),
        ground=profile.get("hunting_ground") or "",
        room=getattr(s.state, "room_uid", None),
        loot_seq=search.get("seq"),
    )


def dispose(s, profile, corpse, tally):
    """A kill: skin it when profiled, then a bare LOOT — the last
    creature fought, the goods option, the same effect as SEARCH
    <corpse> (Elanthipedia: Loot command; the operator, 2026-09-23,
    after a swing's wording gave the corpse a pronoun for a noun and
    SEARCH THAT searched the room) — which disposes of the corpse that
    keeps its noun and soaks swings (docs/combat.md); what it left on
    the ground is grabbed off the room's listing, the answer's own
    wording second (the operator, 2026-09-23: a hunt grabs its loot
    whatever the game called it). LOOT's own lines are uncaptured: the
    run's first answer is echoed for the fixtures.

    By the corpse's id when the parser has it (#456): SKIN #id and LOOT
    #id act on exactly that body, as dr-scripts' combat-trainer does;
    a corpse gone by its id is looted bare. With both hands full and the
    weapon in one, the weapon is sheathed for the pickups and drawn
    again (hand_for_loot, #461)."""
    body = next_corpse(s, tally)
    if profile["skin"] and has_skin(s, corpse, tally):
        # By ordinal past a live one of the noun listed first (#325).
        target = body or aim_corpse(
            corpse,
            getattr(s.state, "room_creatures", None),
            getattr(s.state, "room_creatures_dead", None),
        )
        skin(s, profile, target, tally)
    before = listing(s)
    answer = ask(s, f"loot {body}" if body else "loot")
    if body:
        tally.disposed.add(body[1:])
        if missing(answer):
            answer = ask(s, "loot")
    # A stray line closed the window before the search's own lines (#483:
    # "You feel fully rested." and a box uncounted; #477 a creature's own
    # line): read on.
    answer = whole_answer(s, answer, swings=True)
    if not tally.loot_reported:
        tally.loot_reported = True
        s.echo(f"hunt: loot answered {said(answer)!r}")
    outcome = classify(answer, SEARCH_OUTCOMES)
    tally.search = None
    if outcome in ("found", "nothing"):
        # Every search a row in history.db's loot table: the box drop
        # rate per creature and ground, read off data (#329); and a
        # count against its creature for the hunt's end (#419). The
        # creature and the row ride along to a box picked up (#423).
        parsed = lootlog.parse(answer)
        hunting.note_search(tally, parsed, corpse)
        seq = lootlog.log(s, answer, profile.get("hunting_ground") or "")
        tally.search = {
            "creature": (parsed or {}).get("creature") or corpse,
            "seq": seq,
        }
    freed = outcome == "found" and hand_for_loot(s, profile)
    taken = grab(s, profile, before, tally) if outcome is not None else []
    if outcome == "found":
        ignore = profile.get("loot_ignore") or ()
        never = {str(n).strip().lower() for n in profile.get("loot_subtractions") or ()}
        for item in items_in(answer):
            if item in taken or item in tally.unlootable:
                continue
            if tally.boxes_full and item in loot.BOX_NOUNS:
                continue  # no room for it, and a GET would free a hand for it
            if loot.ignored(named(answer, item), ignore):
                continue  # "an embroidery needle" off a scout (#365)
            if noun_of(item) in never:
                continue  # "Never pick up": the runestones (#442)
            since = hands.mark(s)
            pocket(s, profile, item)
            if item in loot.BOX_NOUNS:
                note_box(s, profile, tally, since, item, named(answer, item))
    elif outcome is None:
        unrecognized(s, tally, "loot", answer)
    if freed:
        draw(s, profile)


def hand_for_loot(s, profile):
    """A hand for the search's pickups: True when the weapon was
    sheathed for them, to be drawn again after. A kill mid-cast — the
    weapon in one hand, the cambrinth piece held between its CHARGE and
    INVOKE in the other — answered every GET and STOW GEM with "You need
    a free hand to pick that up.", and a trading card, coins and a jade
    stayed on the ground (2026-10-04, #461). The piece stays in hand
    for the cast."""
    weapon = profile.get("weapon")
    if not (weapon and hands.full(s) and hands.holding(s, weapon)):
        return False
    free_hand(s, profile)
    return True


def next_corpse(s, tally):
    """The corpse to skin and loot, by its id ("#146989491"): the first
    the parser's crtrStatus burst marks dead that this hunt has not
    disposed of; None without one — a session started before #456 keeps
    no corpses, and the noun follows."""
    for exist in getattr(s.state, "corpses", None) or []:
        if str(exist) not in tally.disposed:
            return f"#{exist}"
    return None


def own_characters():
    """The operator's own characters (~/.revenant/login.json, through
    client/game/novelty.py's own_names, as ;sentinel reads them); [] when
    the file cannot be read."""
    try:
        from client.engine.login import load_login_defaults
        from client.game.novelty import own_names

        return own_names(load_login_defaults())
    except Exception:  # noqa: BLE001 - a missing file is no characters
        return []


def occupants(s, own=None):
    """The other players in the room, as the parser read "Also here" —
    never one of the operator's own characters: an Empath grouped with
    the hunter follows him from room to room, and on 2026-09-26 ;hunt
    boxes read him as a hunter in every room of the goblins' ground,
    moved on and on, and gave the ground up ("every room of the ground
    has someone in it")."""
    mine = {str(name).casefold() for name in (own_characters() if own is None else own)}
    names = list(getattr(s.state, "room_players", None) or [])
    return [name for name in names if str(name).casefold() not in mine]


def settle(s, db, ground, avoid, tally):
    """Arrived in a room of the ground: it is someone else's if a player
    is already in it — the community's rule, the operator's (#178,
    2026-09-12) — so move on until an empty room, and give up once the
    whole ground has been tried. True in a room of our own. A crowd of
    creatures is never a reason to move on: farming them is the point
    (the operator, 2026-09-12)."""
    for _ in range(max(len(ground), 1)):
        names = occupants(s)
        if not names:
            return True
        s.echo(f"hunt: {', '.join(names)} hunting here — their room, moving on")
        # Walked out whatever is in it: the creatures are theirs, and
        # next_room's "something arrived — staying" held Cecil in
        # Ketamira's room six times over until the ground was called
        # taken (2026-09-27).
        if not step_on(s, db, ground, avoid):
            # Said: on 2026-09-26 the walk off an occupied room failed on
            # a map edge and the hunt ended without a word, the character
            # standing in the field.
            s.echo("hunt: could not walk on to another room of the ground — stopping")
            return False
    s.echo("hunt: every room of the ground has someone in it — leaving it to them")
    return False


def wait_for_prey(s, seconds):
    """Wait `seconds`, a second at a time, watching the room: True the
    moment a hostile shows. The 20-second pause used to sleep blind — a
    badger walked in, closed to melee and bit, and the loop walked out
    on it engaged (the operator, 2026-09-20)."""
    for _ in range(int(seconds)):
        if hostiles(s.state):
            return True
        s.sleep(1)
    return bool(hostiles(s.state))


def study_almanac(s):
    """The interludes due (client/game/interlude.py — the profile's
    almanac, a typed ;break) run in a room with nothing hostile in it,
    only with a hand already free: the weapon and shield stay."""
    if not hostiles(s.state):
        interlude.run_due(s, make_room=False)


# RETREAT's answers (flight.py; captured 2026-09-22): out a range, or
# already out; engaged past escape, "You are unable to retreat from...".
RETREATED = ("retreat back to pole range", "retreat from combat", "as far away")
ALMANAC_RETRY = 60  # seconds before a study refused a retreat tries again


def study_in_fight(s, profile, tally):
    """The almanac studied mid-fight when it is ready (the operator,
    2026-09-28: every ten minutes keeps a skill moving): RETREAT to pole
    range first, then the study's ten seconds, the creature closing in
    again meanwhile. Only standing, unstunned, with a hand free; a
    retreat refused waits a minute. True when a study went out."""
    noun = str(profile.get("almanac") or "").strip().lower()
    state = s.state
    if not almanac.ready(noun) or time.monotonic() < tally.almanac_retry:
        return False
    if getattr(state, "stunned", False) or not almanac.hand_free(state, noun):
        return False
    answer = ask(s, "retreat").lower()
    if not any(word in answer for word in RETREATED):
        tally.almanac_retry = time.monotonic() + ALMANAC_RETRY
        return False
    almanac.study(s, noun, ask, "hunt")
    return True


def next_room(s, db, ground, avoid, tally):
    """The room is empty: on to the next room of the ground, cyclically;
    a one-room ground waits and looks instead. Once the ground has
    been lapped EMPTY_LAPS times with nothing in it, a pause of
    EMPTY_ROOM_WAIT and the laps go on — an empty ground is waited
    out, never left (the operator, 2026-09-13). False only when a walk
    fails."""
    tally.room_clear = False
    tally.empty_moves += 1
    if tally.empty_moves > EMPTY_LAPS * max(len(ground), 1):
        s.echo(f"hunt: ground empty — waiting {EMPTY_ROOM_WAIT}s, then looking again")
        tally.empty_moves = 0
        if wait_for_prey(s, EMPTY_ROOM_WAIT):
            s.echo("hunt: something arrived — staying")
            return True
    here = locate(db, s.state)
    others = [room for room in ground if room != here]
    if not others:
        s.echo(
            f"hunt: room empty — waiting {EMPTY_ROOM_WAIT}s for something to turn up"
        )
        if wait_for_prey(s, EMPTY_ROOM_WAIT):
            s.echo("hunt: something arrived — staying")
            return True
        s.put("look")
        probe.collect(s, SETTLE_SECONDS)
        return True
    if hostiles(s.state):
        # A room that filled while the loop was deciding is a room to
        # fight in, never to walk out of engaged.
        s.echo("hunt: something arrived — staying")
        return True
    s.echo("hunt: room empty — moving on")
    return step_on(s, db, ground, avoid)


def step_on(s, db, ground, avoid):
    """The walk to the next room of the ground, cyclically; False only
    when the walk fails."""
    here = locate(db, s.state)
    others = [room for room in ground if room != here]
    if not others:
        return True
    later = [room for room in others if here is not None and room > here]
    target = (later or others)[0]
    if not travel.go(s, {target}, f"room {target}", db=db, walk=walk, avoid=avoid):
        return False
    probe.collect(s, SETTLE_SECONDS)
    return True


def track(s, profile, tally):
    """One HUNT for tracks when the room has emptied, for Perception: at
    most once per HUNT_INTERVAL while the skill sits below lock. The
    tracks are not followed. TRACK_MISSES answers outside the table in
    a row turn the step off for the run, said once (#194)."""
    if not profile.get("perception") or tally.tracking_off:
        return
    if locked(s.state, ["Perception"]):
        return
    last = tally.last_track
    if last is not None and hunting.clock() - last < HUNT_INTERVAL:
        return
    text = ask(s, "hunt")
    if any(word in text.lower() for word in _TRACKS_READ):
        tally.last_track = hunting.clock()
        tally.tracks += 1
        tally.track_misses = 0
        return
    tally.track_misses += 1
    unrecognized(s, tally, "hunt", text)
    if tally.track_misses >= TRACK_MISSES:
        tally.tracking_off = True
        s.echo(
            f"hunt: HUNT answered nothing known {TRACK_MISSES} times — "
            "tracking off for this run"
        )


def smite_allowed(s, tally):
    """SMITE CHECK before a smite (#217): True while a free blow remains.
    No free blows, or an answer the table does not know, means the next
    SMITE would draw on the soul pool, so this minute's smite is an
    ATTACK instead and the minute is spent; said once per run."""
    blows = free_smites(ask(s, "smite check"))
    if blows:
        return True
    hunting.note_smite(tally, s.state)
    if not tally.smite_warned:
        tally.smite_warned = True
        s.echo(
            "hunt: no free smites — a SMITE now would draw on the soul pool; "
            "attacking instead until Conviction gives one back (#217)"
        )
    return False


def wait_out_stun(s):
    """Sleep while the status indicator says stunned, STUN_WAIT seconds
    at most (#336). A handle without the status (a test's) waits none."""
    waited = 0.0
    while waited < STUN_WAIT and not s.dead:
        status = getattr(s, "status", None)
        if not getattr(status, "stunned", False):
            return
        s.sleep(STUN_POLL)
        waited += STUN_POLL


def aimed_swing(s, profile, tally, prey):
    """swing() at the prey aimed now, past any corpse listed before the
    live one (aim_at), the room logged with the aim."""
    target = aim_at(s, prey)
    log_room(s, "aim", target)
    return swing(s, profile, tally, target)


def swing(s, profile, tally, prey):
    """One swing — ATTACK, SMITE or a maneuver (swing_verb) — and what
    its answer means: a kill disposed of, a maneuver tallied, a corpse
    or an empty room noted, an advance waited out. True while the room
    still holds a live hostile (a cast's filler asks, #203)."""
    wait_out_stun(s)
    verb = swing_verb(profile, tally, s.state)
    if verb == "smite" and (tally.smite_off or not smite_allowed(s, tally)):
        verb = "attack"
    combo = False
    if verb == "attack":
        # A Barbarian's self-combo takes the place of ATTACK (#328).
        attack = barbarian.next_combo_attack(
            s,
            profile,
            tally.barb,
            ask,
            "hunt",
            lambda what, answer: unrecognized(s, tally, what, answer),
        )
        if attack:
            verb, combo = attack, True
    mark_room(s, tally)
    text = ask(s, f"{verb} {prey}" if prey else verb)
    if verb != "attack":
        # A maneuver's window closed on an earlier swing's line, an
        # arrival or a creature's own line (#483, #477): its answer follows.
        text = whole_answer(s, text, swings=True)
    lowered = text.lower()
    if word := getattr(s.state, "balance", None):
        tally.balances[word] = tally.balances.get(word, 0) + 1
    tally.stuns += sum(lowered.count(word) for word in _STUNNED)
    if any(word in lowered for word in _STILL_STUNNED):
        # Nothing went out (#336): the attack keeps its place in the
        # combo, the maneuver and the brawling attack their turn.
        if combo:
            tally.barb.combo.insert(0, verb)
        elif fists_turn(profile) and verb in brawling(profile):
            tally.brawl = max(0, tally.brawl - 1)
        elif not plain_swing(profile, verb):
            tally.tactic = max(0, tally.tactic - 1)
        tally.stunned_swings += 1
        wait_out_stun(s)
        return bool(hostiles(s.state))
    if verb == "smite" and any(word in lowered for word in _SMITE_WRATH):
        # The pool paid for that one: no more smites this run (#217).
        tally.smite_off = True
        s.echo("hunt: that SMITE drew on the soul pool — smiting off for this run")
    if verb == "smite" and any(word in lowered for word in _SMITE_STRUCK):
        hunting.note_smite(tally, s.state)  # spent only when it struck
    if verb == "smite" and any(word in lowered for word in _SMITE_NO_WEAPON):
        hunting.note_smite(tally, s.state)  # refused: not again this minute (#396)
    if combo or plain_swing(profile, verb):
        tally.since_maneuver += 1
    else:
        tally.since_maneuver = 0
        if any(word in lowered for word in _MANEUVER_DONE):
            tally.maneuvers += 1
            tally.tactic_misses = 0
        elif not any(
            word in lowered for word in _ADVANCING + NOT_FOUND + _NEED_MELEE + _ALL_DEAD
        ) and not _DEAD_NOUN.search(text):
            # A maneuver with no foe left ("There is nothing else to
            # face!", a BOB at the bobcats 2026-09-23) is the room
            # clearing, not a miss.
            tally.tactic_misses += 1
            unrecognized(s, tally, verb, text)
            if tally.tactic_misses >= TACTIC_MISSES:
                tally.tactics_off = True
                s.echo(
                    f"hunt: {verb} answered nothing known {TACTIC_MISSES} "
                    "times — tactics off for this run"
                )
    fallen = new_corpses(s, tally)
    if not fallen and is_kill(text):
        # A death line the table knows, the listing not yet re-sent: the
        # line is a hint to wait for it, and the kill if it never comes.
        probe.collect(s, LISTING_WAIT)
        fallen = new_corpses(s, tally) or [kill_noun(text) or prey or "corpse"]
    if fallen:
        tally.kills += len(fallen)
        tally.empty_moves = 0
        tally.corpse_swings = 0
        tally.stuns = 0  # a kill resets the fight's fuses (#236)
        tally.swings_at_kill = tally.swings
        corpse = noun_of(fallen[-1]) or prey or "corpse"
        s.echo(f"hunt: {corpse} down ({tally.kills})")
        if tally.coins or tally.boxes:
            s.echo(
                f"hunt: loot so far — {tally.coins} coin pile(s), {tally.boxes} box(es)"
            )
        dispose(s, profile, corpse, tally)
        tally.check_wounds = True
        if len(hostiles(s.state)) <= 1:
            # The kill line is the truth; the parser keeps the dead one
            # until a status frame it never sends (#244), and a cast at
            # it answered "already dead, so that's a bit pointless"
            # (#252). One hostile listed and it just fell: the room is
            # clear, as the game's own "nothing else to face" says.
            tally.room_clear = True
    elif any(word in lowered for word in _ALL_DEAD):
        tally.room_clear = True  # the game says so; the hostile state lags
    elif corpse := _DEAD_NOUN.search(text):
        log_room(s, "corpse answered", corpse.group(0))
        tally.corpse_swings += 1
        if tally.corpse_swings > CORPSE_SWINGS:
            s.echo("hunt: only a corpse answers — the room is clear")
            tally.room_clear = True
            tally.corpse_swings = 0
        else:
            dispose(s, profile, corpse.group(2), tally)
    elif missing(lowered):
        s.put("face next")
        probe.collect(s, act.TAIL_SECONDS)
    elif any(word in lowered for word in _ADVANCING):
        probe.collect(s, ADVANCE_WAIT, until="melee range")
    elif any(word in lowered for word in _NEED_MELEE):
        ask(s, f"advance {prey}" if prey else "advance")
        probe.collect(s, ADVANCE_WAIT, until="melee range")
    return not tally.room_clear and bool(hostiles(s.state))


_LOG = logging.getLogger("client.scripts.hunt")


def log_room(s, what, target=""):
    """The room as the parser holds it, into the session's debug log with
    the swing's aim (#325: an aim at a corpse the logged listing marked
    dead — the state at the swing is what the fix needs)."""
    state = s.state
    _LOG.debug(
        "%s %r: creatures %s dead %s hostiles %s",
        what,
        target,
        list(getattr(state, "room_creatures", None) or []),
        list(getattr(state, "room_creatures_dead", None) or []),
        dict(hostiles(state)),
    )


def aim_at(s, prey):
    """The prey phrase for the next swing: the first live one of the
    noun by ordinal when a corpse of it stands first in the room's
    listing — "second cougar" (#278; a swing at the plain noun landed
    on the corpse, "already quite dead", and was spent) — the plain
    noun otherwise, and "" when the profile names no prey — or when the
    room's listing holds live creatures but none of the prey while
    something hostile is on the character: a bare ATTACK fights what
    engages. On 2026-09-25 the last goblin died, two musk hogs kept
    at Lanival, and "attack goblin" answered "I could not find what
    you were referring to." sixty times — the hunt broke off on "60
    swings without a kill" among the hogs (#316)."""
    if not prey:
        return prey
    names = list(getattr(s.state, "room_creatures", None) or [])
    dead = list(getattr(s.state, "room_creatures_dead", None) or [])
    dead += [False] * (len(names) - len(dead))
    live = [name for name, flag in zip(names, dead) if not flag]
    if (
        live
        and hostiles(s.state)
        and not any(noun_of(name) == prey.lower() for name in live)
    ):
        return ""
    return aim(prey, names, dead)


def say_outgrown(s, profile, tally):
    """Once a hunt, with live creatures in the room: the weapon skills
    their MaxCap no longer teaches, said (#322: five hunts on cougars,
    MaxCap 49, taught Small Edged 58 and Brawling 57 nothing). A room
    of creatures the table does not know is looked at again next time."""
    if tally.caps_said:
        return
    names = list(getattr(s.state, "room_creatures", None) or [])
    dead = list(getattr(s.state, "room_creatures_dead", None) or [])
    dead += [False] * (len(names) - len(dead))
    live = [name for name, flag in zip(names, dead) if not flag]
    ranks = {
        entry["skill"]: buffs.rank_of(s.state, entry["skill"])
        for entry in weapon_plan(profile)
        if entry["skill"]
    }
    top, past = outgrown(live, ranks)
    if top is None:
        return
    tally.caps_said = True
    if past:
        skills = ", ".join(f"{skill} {rank}" for skill, rank in past)
        s.echo(
            f"hunt: the {top[0]} teaches to rank {top[1]} — {skills} past it; "
            "a harder ground trains them"
        )


def loop(s, profile, db, ground, avoid, tally):
    """Fight until something ends the hunt; returns why."""
    prey = profile["prey"]
    floor = profile["health_floor"]
    last_health = health(s.state)
    for _ in range(MAX_ITERATIONS):
        if tally.swings >= MAX_ACTIONS:
            break  # empty rooms and waits do not count against the swings
        if s.dead:
            return "dead — deathwatch has it"
        if (s.command(timeout=0) or "").strip().lower() == "return":
            return "returning on request"
        current = health(s.state)
        if current is not None and current < floor:
            escape(s, db)
            return f"health {current}% below the floor"
        if tally.stuns >= STUN_LIMIT:
            escape(s, db)
            return (
                f"stunned {tally.stuns} times in one fight — the ground is beyond you"
            )
        if stalled_turn(tally, profile) and pass_turn(s, profile, tally):
            continue
        if tally.swings - tally.swings_at_kill >= KILL_LESS_SWINGS:
            escape(s, db)
            return (
                f"{KILL_LESS_SWINGS} swings without a kill — the ground is beyond you"
            )
        if current is not None and last_health is not None and current < last_health:
            tally.check_wounds = True
        last_health = current
        if tally.check_wounds:
            tally.check_wounds = False
            if hit := wound_at_floor(s, profile):
                area, kind, lvl = hit
                escape(s, db)
                return f"{area} {kind.replace('_', ' ')} {SEVERITIES[lvl]} — at the wound floor"
        if locked(s.state, profile["train_skills"]):
            return "trained skills mind-locked"
        if profile["max_kills"] and tally.kills >= profile["max_kills"]:
            return "kill fuse reached"
        box_limit = int(profile.get("box_limit") or 0)
        if profile.get("until") == "boxes" and box_limit and tally.boxes >= box_limit:
            return f"{tally.boxes} box(es) in the {profile.get('loot_container') or 'pack'} — the farm is done"
        if farming(profile) and tally.boxes_full:
            return (
                f"the {profile.get('loot_container') or 'pack'} is full after "
                f"{tally.boxes} box(es) this run — the farm is done"
            )
        if tally.kills > tally.rotated_at and not rotate(s, profile, tally):
            return "every weapon skill mind-locked"
        if tally.room_clear or not hostiles(s.state):
            track(s, profile, tally)
            study_almanac(s)  # a clear room: the hands are the hunt's
            if not next_room(s, db, ground, avoid, tally):
                return "the walk to the next room failed"
            if not settle(s, db, ground, avoid, tally):
                return "ground taken"
            continue
        if study_in_fight(s, profile, tally):
            continue  # the checks again before the next swing
        say_outgrown(s, profile, tally)
        tally.swings += 1
        # A cast due before this swing wraps it: PREPARE, the swing while
        # the pattern forms, CAST (#203). Otherwise the swing alone. Each
        # swing is aimed as it goes out: a long pattern gets several, and
        # one aimed before the cast went on at the goblin listed first
        # after the filler killed it — "already quite dead", three times,
        # a live one behind it (#325).
        if not cast_buffs(
            s,
            profile,
            tally,
            fight=True,
            filler=lambda: aimed_swing(s, profile, tally, prey),
        ):
            aimed_swing(s, profile, tally, prey)
    return "action budget spent"


def hunt(s, profile, db, travel_first=True, avoid=()):
    ground_name = profile["hunting_ground"]
    # A map tag, else a bestiary zone, else a ;go2 target (#340).
    ground = hunting.ground_rooms(db, ground_name)
    tally = Tally()
    tally.turn_times = dict(
        load_stores(getattr(s.state, "name", None)).get("turns") or {}
    )
    set_stores(s, profile)
    if travel_first:
        if not ground:
            s.echo(
                f"hunt: nothing in the map matches ground {ground_name!r} — check the profile"
            )
            return
        # A wound already at the floor ends the hunt before the buffs and
        # the walk: the box farm set out with the chest wound the hunt
        # before it had stopped on, spent three minutes buffing and a
        # 33-step walk, and broke off after two kills (2026-09-27).
        if hit := wound_at_floor(s, profile):
            area, kind, lvl = hit
            s.echo(
                f"hunt: {area} {kind.replace('_', ' ')} {SEVERITIES[lvl]} — already "
                "at the wound floor; not setting out (;heal treats it)"
            )
            return
        # The buffs before the walk, not among the prey: four casts on
        # arrival were a minute spent standing in the badgers' room
        # (the operator, 2026-09-20), and a buff at minimum mana lasts
        # nine, so the walk costs it little. On arrival the Spells
        # window lists them and the second cast_buffs casts nothing.
        cast_buffs(s, profile, tally)
        if not travel.go(
            s, set(ground), repr(ground_name), db=db, walk=walk, avoid=avoid
        ):
            s.echo("hunt: could not reach the ground — stopping")
            return
        probe.collect(s, SETTLE_SECONDS)
    if travel_first and not settle(s, db, ground, avoid, tally):
        # Home, as any end (2026-09-27: the ground given up ended the
        # hunt in a taken room, among its goblins).
        go_home(s, profile, db, ground, avoid, "ground taken")
        return
    wear_bundle(s, profile, tally)
    cast_buffs(s, profile, tally)
    first = next_turn(s, profile, tally, from_current=True) if has_turns(profile) else 0
    if first is None and farming(profile):
        first = 0  # a farm fights on with its first turn, locked or not
    if first is None:
        s.echo("hunt: every weapon skill is mind-locked — nothing to train")
        return
    if not str(profile.get("wound_floor") or "").strip():
        s.echo(
            f"hunt: wound floor unset — {DEFAULT_WOUND_FLOOR} by default "
            "(profile wound_floor; off never asks HEALTH)"
        )
    ready(s, profile, tally, first)
    started = hunting.clock()
    reason = loop(s, profile, db, ground, avoid, tally)
    minutes = (hunting.clock() - started) / 60
    s.echo(
        f"hunt: {reason} — {tally.kills} kill(s), {tally.skins} skin(s)"
        + (f", {tally.maneuvers} maneuver(s)" if tally.maneuvers else "")
        + (f", {tally.barb.combos} self-combo(s)" if tally.barb.combos else "")
        + (f", {tally.barb.roars} roar(s)" if tally.barb.roars else "")
        + (f", {tally.tracks} HUNT(s)" if tally.tracks else "")
        + (
            f", {tally.unrecognized} unrecognized answer(s)"
            if tally.unrecognized
            else ""
        )
        + (
            "; balance "
            + ", ".join(f"{word} x{n}" for word, n in tally.balances.items())
            if tally.balances
            else ""
        )
    )
    if tally.kinds:
        s.echo(f"hunt: searched by creature — {hunting.kinds_said(tally.kinds)}")
    record_hunt(s, profile, tally, minutes, reason)
    if s.dead:
        return
    go_home(s, profile, db, ground, avoid, reason)
    if not s.dead:
        sell_and_bank(s, skinned=bool(tally.skins or tally.bundle))


def go_home(s, profile, db, ground, avoid, reason):
    """Every end of a hunt: home when the profile names one, else off
    the ground after a break-off, and never an end among hostiles."""
    # The weapon stays in hand at every end: a stowed weapon is no
    # parry (2026-09-12, three rats and an empty hand after a stop),
    # and nothing a hunt hands over to needs both hands. Its container
    # is only where the first swing fetches it from.
    if profile["home"]:
        if travel.go(
            s,
            profile["home"],
            f"home {profile['home']!r}",
            db=db,
            walk=walk,
            avoid=avoid,
        ):
            s.echo(f"hunt: home at {s.state.room_title}")
    elif any(word in reason for word in BROKE_OFF) and ground:
        leave_ground(s, db, ground, avoid)
    if hostiles(s.state) and not s.dead:
        # Never an end among them (#314): the walk home or off the
        # ground failed, or never ran — keep getting away.
        flight.react(s, "hunt")


# Copper of the province's coin the closing ;bank leaves in the purse:
# a hunt that banked everything sent the next one to the Faldesu ferry
# with nothing for its 35-Kronar fare, "You haven't got enough kronars
# to pay for your trip." (Cecil, 2026-10-04, #454) — two crossings and
# change.
TRAVEL_PURSE = 200


def sell_and_bank(s, skinned=True):
    """Every hunt that fought ends by selling the skins and banking the
    purse — ;skins bank, waited for — under ;train too (the operator,
    2026-09-28: the box farm ended at 20:59 with fifteen skins, and the
    plan went on to ;boxes; 2026-09-26 it was only after ;hunt return).
    A run that cut no skin and saw no bundle (the box farm skins
    nothing) banks with ;bank alone: ;skins walked to the tannery and
    back to say "no bundle worn or in your tote — nothing to sell"
    (2026-10-04). A ;stop of the hunt meanwhile stops the script it
    started (and ;skins its ;bank)."""
    running = getattr(s, "is_running", None)
    start = getattr(s, "run", None)
    if running is None or start is None:
        return
    if skinned:
        name, args = "skins", ["bank", f"keep={TRAVEL_PURSE}"]
        s.echo("hunt: selling the skins and banking (;skins bank)")
    else:
        name, args = "bank", [f"keep={TRAVEL_PURSE}"]
        s.echo("hunt: no skins this run — banking (;bank)")
    if not start(name, args):
        s.echo(f"hunt: could not start ;{name} — sell and bank by hand")
        return
    try:
        while running(name):
            s.sleep(1)
    except BaseException:
        s.kill(name)
        raise


def show_grounds(s, profile, db, words, avoid=()):
    """;hunt grounds [rank]: the bestiary's zones whose rank range holds
    the rank — the given one, else the weakest of the profile's weapon
    skills — nearest first from where the character stands (#340)."""
    rank = next((int(word) for word in words if word.isdigit()), None)
    if rank is None:
        rank = hunting.weapon_rank(profile, getattr(s.state, "experience", None))
    if rank is None:
        s.echo("hunt: no weapon skill to go by — ;hunt grounds <rank>")
        return
    here = locate(db, s.state)
    rows = hunting.grounds(db, here, rank, avoid=avoid)
    if not rows:
        s.echo(f"hunt: no hunting zone reachable from here suits rank {rank}")
        return
    s.echo(f"hunt: hunting zones for rank {rank}, nearest first:")
    current = str(profile.get("hunting_ground") or "").strip().lower()
    # The yield this character measured on each zone (#419): boxes per
    # search off the loot table, boxes an hour off the hunts table, the
    # copper Kronars a box held off the box_contents table (#423, #425).
    name = getattr(s.state, "name", None)
    measured = lootlog.measured(name)
    worth = boxlog.measured(name)
    for row in rows:
        mark = "  (your ground)" if row[0] == current else ""
        found = {**measured.get(row[0], {}), **worth.get(row[0], {})}
        s.echo(f"  {hunting.describe(row, found)}{mark}")


def record_hunt(s, profile, tally, minutes, reason):
    """The run's totals as a history.db `hunts` row (#419): the minutes
    on the ground beside the kills and what the searches found, so a
    ground's boxes an hour is measured, not guessed."""
    lootlog.log_hunt(
        s,
        ground=profile.get("hunting_ground") or "",
        style=profile.get("hunt_style") or "",
        minutes=round(minutes, 2),
        kills=tally.kills,
        searched=hunting.kinds_total(tally.kinds, "searched"),
        boxes=hunting.kinds_total(tally.kinds, "boxes"),
        coins=hunting.kinds_total(tally.kinds, "coins"),
        boxes_taken=tally.boxes,
        reason=reason,
    )


def main(s):
    from client.game.mapdb import MapDB, download, mapdb_path

    from client.game.profile import styled, styles

    name = getattr(s.state, "name", None) or ""
    profile = load_profile(name)
    words = [str(word).lower() for word in (s.args or [])]
    known = styles(profile)
    if words and words[0] == "styles":
        if not known:
            s.echo("hunt: no hunt styles — `hunts` in the profile file names them")
        for style, overlay in known.items():
            keys = ", ".join(f"{k}={v}" for k, v in overlay.items())
            s.echo(f"hunt: {style}: {keys}")
        return
    # A style word lays its overlay on the profile (#299): `;hunt boxes`,
    # or the plan task's args. The words `here` and `profile` stay.
    chosen = next((word for word in words if word in known), None)
    if chosen:
        profile = styled(profile, chosen)
        s.echo(f"hunt: the {chosen} style — until {profile['until']}")
    elif words and words[0] not in ("here", "profile", "grounds") and known:
        s.echo(f"hunt: no style named {words[0]!r} — styles: {', '.join(known)}")
        return
    if words and words[0] == "profile":
        s.echo(f"hunt: profile for {name or 'an unnamed character'}")
        for line in describe(profile):
            s.echo(f"  {line}")
        if not profile["home"]:
            s.echo(
                "hunt: home is empty — a break-off leaves you just off the ground; "
                "set it in the profile"
            )
        return
    if guild.is_empath(guild.character_guild(s)):
        # Harming a living creature brings an Empath empathic shock
        # (Elanthipedia, #444). A creature that is not living (a construct)
        # is the exception; ;hunt cannot tell one apart yet, so no hunt at all.
        s.echo(
            "hunt: an Empath does not hunt — attacking a living creature "
            "brings empathic shock"
        )
        return
    if not mapdb_path().is_file():
        s.echo("downloading map database (first use, ~13MB) ...")
        download()
    db = MapDB.load()
    words = [str(word).lower() for word in (s.args or [])]
    if words and words[0] == "grounds":
        show_grounds(s, profile, db, words[1:], travel.avoided(db))
        return
    try:
        hunt(
            s,
            profile,
            db,
            travel_first="here" not in words,
            avoid=travel.avoided(db),
        )
    finally:
        # The weapon stays in hand by design; the cambrinth piece does
        # not — a ;stop mid-cycle puts it back (2026-09-20, ;cast).
        buffs.put_back_if_held(s, profile, "hunt")
