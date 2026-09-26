# The Barbarian, as measured

This page is the index of every Barbarian fact the scripts rest on — Inner Fire, the abilities and their verbs, research, Expertise, the circles — and what the code does with each so far. It exists because the scripts grew around a Paladin: ;hunt's buffs are spells (PREPARE, CAST, a mana ramp), and a Barbarian casts nothing. Canon is Elanthipedia ([Barbarian](https://elanthipedia.play.net/Barbarian), [Barbarian new player guide](https://elanthipedia.play.net/Barbarian_new_player_guide)); the wiki cache (`uv run python tools/wiki.py "<Title>"`) holds the raw pages; this is what our code believes and why, never a mirror. The character is Uthmor in the synthetic cast, a Rakash Barbarian of the Crossing guild.

## Where he stands (2026-09-26)

| | |
|---|---|
| Circle | 1. The gates to 2 (`;circle`, [circles.md](circles.md)): Expertise, Melee Mastery and 2nd Weapon 4/8, 1st Weapon 5/8, Parry 6/8, Evasion 4/6, Augmentation and Inner Fire 1/2, 2nd Armor 1/2; Inner Fire ranked to 2 on ;research's first run the same evening |
| Abilities | none: ABILITY LIST answers "You have not been trained in any Berserks." for each of the five kinds, then "You recall that you have 3 training sessions remaining with the Guild." (captured 2026-09-26). The login banner said the guild "has gained access to the Utility skill" and "your abilities have been reset" |
| Inner Fire | the vitals' mana bar is the game's own Inner Fire gauge — its progressBar reads `text='inner fire 33%'` — at 33% out of combat with no abilities, the guide's "passive cap of around 30%" for a circle-one Barbarian |
| Profile | `hunting_ground` rats, the short sword and broadsword from the scabbard and fists in turn, `buffs` empty — ;hunt fights with it unchanged |

## Inner Fire

Inner Fire is the Barbarian's mana: it fuels berserks, forms and meditations (roars draw on a voice pool instead). The pool never grows; the Inner Fire skill makes each ability cheaper. It regenerates passively up to a cap (about 30% at circle one; the Duelist mastery roughly doubles it) and actively in combat: every kill, most for kills 120 s apart, and the ANALYZE FLAME combo ([Inner Fire](https://elanthipedia.play.net/Inner_Fire)). The guide says the front ends show it on the mana bar once POWER meditation is known; the game labels the bar "inner fire" with no meditation learned, so the parser's mana vital is Inner Fire for a Barbarian either way. The Spells window lists the running abilities after POWER meditation (the guide's claim, uncaptured).

## Abilities

Four kinds, each its own verb (ABILITY LIST, BERSERK LIST, FORM LIST, ROAR LIST, MEDITATE LIST, MASTERY LIST recall what is known):

| Kind | Verb | Cost | Limit | Notes |
|---|---|---|---|---|
| Berserk | `BERSERK <name>`, `BERSERK STOP` | moderate start, small drain | none | instant, full strength, no roundtime; up to 10 minutes |
| Form | `FORM <name>` | no start, moderate drain; lowers the passive cap | 5 | 2 s roundtime, ~30 s to full strength; up to 90 minutes |
| Meditation | `MEDITATE <name>`, `MEDITATE STOP` | large start, no drain | 3 | sitting or kneeling, out of combat (Yogi mastery lifts it); ~8 s roundtime |
| Roar | `ROAR <name> [at <foe>]` | voice pool | none | debilitations; the only way to train Debilitation |

Masteries are passive, bought from the Pit Masters with a slot. Slots come at one per even circle to 100 (the wiki; circle 1 showed three sessions after the reset). The guild is permanently "on preview": CHOOSE FORGET ALL at a guild leader, or ASK about forgetting one, is free (the guide, 2026-09).

Nothing in the code keeps an ability up yet: `client/game/buffs.py` is PREPARE and CAST, and none of it applies. An ability layer beside it — a profile list such as `berserk:avalanche`, `form:buffalo`, a roar at the prey for Debilitation — is the next piece, and it touches ;hunt (#328).

## Research: ;research

`MEDITATE RESEARCH <ability>` teaches the skill of that ability, learned or not, with a moderate roundtime (5-8 s) and a cooldown of about a minute — the Barbarian's magic research, and the way to train Augmentation, Warding and Utility with no slot spent ([Barbarian new player guide](https://elanthipedia.play.net/Barbarian_new_player_guide), [Meditations](https://elanthipedia.play.net/Meditations)). A Debilitation ability researched teaches nothing. `;research` (scripts/research.py, client/game/research.py) researches the emptiest of the three skills each round, 60 s apart, until they lock, with dr-scripts' combat-trainer.lic's abilities: MONKEY (Augmentation), TURTLE (Warding), PREDICTION (Utility). Its answer table is combat-trainer's two patterns — "You clear your mind and begin to meditate", "What did you want to research" — and the wiki's non-Barbarian line (#327).

The first run (2026-09-26, circle 1, no abilities learned) captured the begun answer: "You clear your mind and begin to meditate upon the training you have received." with 6 to 10 s of roundtime, then a few seconds on "You recall that Monkey Form is a Basic ability in the Path of the Flame. ..." ("Turtle Form is an Expert ability" for TURTLE). Each research put its skill at dabbling — Augmentation 1.00 to 1.04, Warding 0.00 to 0.07 — and taught Inner Fire beside it: Inner Fire went from learning to attentive and ranked 1 to 2 within two minutes, which met that circle-2 gate. The pool had drained clear before the next research a minute on, so all three skills kept tying at 0; with a tie going to the first named, the run alternated MONKEY and TURTLE and never reached PREDICTION, and a tie now goes to the skill researched longest ago. Researches 61 s apart drew no cooldown answer. Still uncaptured: the unknown-name and non-Barbarian answers, the cooldown's wording, and whether the cooldown is per skill or shared.

## Expertise

Expertise is the Barbarian-only weapon skill and a hard gate every circle. It trains from Advanced Combat Maneuvers (the weapon class's maneuvers, a 90 s cooldown that an Expertise check halves) and from the self-only ANALYZE combos — FLAME from 0 ranks (a little Inner Fire back), ACCURACY at 50, DAMAGE at 125 and on up ([Expertise](https://elanthipedia.play.net/Expertise)). A combo advances on a miss too and carries over between kills. ;hunt runs neither yet; ANALYZE FLAME in rotation, the way `tactics` rotates BOB and CIRCLE, is the cheapest step, and it touches ;hunt (#328).

## Circles

The requirement table is in `client/game/circles.py` with the other guilds' ([circles.md](circles.md)): Expertise, Primary Mastery (Melee Mastery), Parry, four weapons, two armors, Evasion and four survivals, Tactics and one lore, Inner Fire and two supernaturals (Augmentation, Debilitation, Warding, Utility).
