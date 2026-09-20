# The Paladin, as measured

This page is the index of every Paladin fact the scripts rest on — the circles, the soul, the glyph quests, the smite, the spells, the guild's rooms — each with its capture date and a link to the model that holds the long version. It exists because a session asking "what does this Paladin need next" read five files to find out (#228). Canon is Elanthipedia ([Paladin](https://elanthipedia.play.net/Paladin)); the wiki cache (`uv run python tools/wiki.py "<Title>"`) holds the raw pages; this is what our code believes and why, never a mirror. The character is Lanival in the synthetic cast, a Dwarf Paladin of the Crossing guild.

## Where he stands (2026-09-20)

| | |
|---|---|
| Circle | 10 — nine "Your Light shines from within you, Lanival.  You have earned your next rank!" from Verika since 2026-09-05, every gate met when asked; at 10, "It is time for you to learn the true calling of the Paladin -- leadership!  The Gods now grant you the ability to LEAD" |
| Glyphs | Dueling (from the start) and Warding (the quest, 2026-09-19 05:41) — GLYPH lists them under "You have attained..." |
| Spells | Heroic Strength, Aspirant's Aegis, Stun Foe, Sentinel's Resolve, Courage, Footman's Strike; a 12-mana cambrinth anklet worn between casts. "There was an error with the number of your available spell slots, which has now been corrected to 3." came unasked on 2026-09-19 |
| Soul | pristine at the guild's arch (2026-09-20 04:3x); the deeds gated off while it reads so |
| Training | the plan and profile in [training.md](training.md#a-worked-example-a-circle-5-paladin): badgers with the fists for Brawling (Small Edged outgrew them on 2026-09-20 and left the rotation; the scimitar stays the profile's weapon for whatever else draws one), climbs, books, the zills, power walking, forage; TDPs on the guild's tiers |

## Circles

The model is [circles.md](circles.md): named skills and best-N slots summed over the wiki's circle bands, `;circle` reading the circle and guild from INFO (2026-09-20) and the ranks from the exp window. The Paladin's part of it:

1. **Soft named skills**: Shield Usage, Tactics and Scholarship are named requirements that may also fill a slot (the wiki's marking).
2. **Armor slots draw from the four armor skills only** — Light Armor, Chain Armor, Brigandine, Plate Armor — never Defending, Shield Usage or Conviction. Until 2026-09-13 the set read the pre-DR3 "Light and Heavy Armor", and this Paladin in plate with a leather cowl was told "2nd Armor 0/4" while Verika asked for nothing.
3. **Ties are the game's to break**: Verika named "4th Survival (Locksmithing)" where the sort named First Aid, both at rank 1 (2026-09-14, #195); a tied slot is reported with every skill on that rank.
4. **The circle-5 milestone** is the first glyph quest: "Congratulations Lanival, you have reached a milestone in your training.  When I deem a paladin ready, I will sometimes give the worthy knight in training a task to perform ..." (Verika, 2026-09-18), then "Find here the soulstone orb, and focus your mind on its powers."

No refused circle was captured: every ASK about a circle since 2026-09-05 met its gates, so the refusal wording and a Paladin gate that held are still to capture.

## The soul

[soul.md](soul.md) is the model; the numbers a Paladin lives by:

| Fact | Value | Captured |
|---|---|---|
| The state | seven levels, black and corrupted → pristine luminescence, read by RUB on an orb or by walking through a soulstone arch (the same words: "gleams brightly with a pristine luminescence" / "The archway gleams with a pristine luminescence in welcome!"); drifts down slowly, never below chalky grey on its own | 2026-09-18/20 |
| The pool | eleven levels by EXHALE on an orb; empty is "Nothing special seems to happen."; refills within hours | 2026-09-18/19 |
| The badge | PRAY BADGE, every 31 minutes, the most repeatable boost; grows with the attuned altars pushed onto it (four in the Crossing); 37,500 Kronars in Brother Durantine's storeroom (19073), a Cleric's to buy | 2026-09-20 |
| The prayer | PRAY CHADATRU knelt about 75 s at his altar or statue, every 2 hours from the attempt; "inappropriate so soon" backs off twenty minutes | 2026-09-19 |
| The tithe | PUT 5 silver of the province's coin in an almsbox, every 4 hours; the Crossing's guild box wants `box`, not `almsbox` | 2026-09-19/20 |
| What lowers it | fleeing combat (the walker's RETREAT burst) and SMITE with the pool empty — an evening of smites took it to chalky grey (#217) | 2026-09-18 |
| The gate | while a reading younger than four hours says pristine, no deed runs (`;soul keep`, `;train`'s rests) | 2026-09-20 |

## The glyph quests

Scripted scenes at a fixed room with one command to act on ([Glyph of Warding walkthrough](https://elanthipedia.play.net/Glyph_of_Warding_walkthrough); #212 for the rest). **Warding, circle 5, done** 2026-09-19 05:41 through `;soul quest` (#224): the orb in the Tower of Honor's Orb Room (8228) wants a pristine soul, a full pool and about an hour since the last failed FOCUS — "You attempt to focus on the orb, but you feel you need to rest and contemplate a bit first." is the wait, not the soul, and it came three times at pristine and full before the accepted FOCUS 65 minutes after the last; then the vision (a girl fleeing three swamp trolls), GUARD GIRL at "in a few brief moments she will be past you and beyond help", and "'Go now, and use my gift to preserve those who have fallen with honor.'" The scene is in [soul.md](soul.md#the-quest-scene). **Bonding (10), Light (15), Mana (20), Ease (25)** are unbuilt (#212); Lady Snow in the Tower of Honor explains the current quest on ASK ... ABOUT QUEST.

## Smite and Conviction

[hunting.md](hunting.md#smiting-for-conviction) has the captures. A SMITE is a swing that trains Conviction, one free blow a minute regenerating and the experience once a minute; past the free blows it draws on the soul pool, and with the pool empty it harms the soul. SMITE CHECK counts the blows ("Your conviction is enough to deliver three blows against your enemies before you must either rest or draw upon your spiritual strength to continue.", Conviction 49, 2026-09-20), and `;hunt` smites only while it counts one. The profile's `smite` is off for this Paladin since #217; RUSH with a shield is the other way and is unbuilt.

## The spells the scripts use

| Spell | Book | Used as | Model |
|---|---|---|---|
| Heroic Strength | Inspiration | a buff, and the Augmentation training cast through the anklet (the mana ramp) | [hunting.md](hunting.md), `client/game/buffs.py` |
| Aspirant's Aegis | Sacrifice | a buff | |
| Sentinel's Resolve | Inspiration | a buff (Defending, Shield Usage); Verika: "Before you can learn this spell, you must ..." — learned 2026-09-20 | |
| Courage | Inspiration | a buff, and the Warding spell that opens a fourth magic skill | |
| Stun Foe | Justice | the `debilitation` cast at the prey (Debilitation) | #192 |
| Footman's Strike | Justice | the `targeted` cast at the prey (Targeted Magic); wants the weapon in hand as its focus | #200, #202 |

Verika lists what the circle allows on ASK ... ABOUT MAGIC ("I see you are worthy to learn the Courage, Righteous Wrath, Divine Guidance, and Sentinel's Resolve spells from the Inspiration book, the Halt, Hands of Justice, Rutilor's Edge, and Footman's Strike spells from the Justice book ..."); a spell past the circle answers "However, Lanival, you are not yet ready to learn this spell.  Return later when you are more experienced." A Paladin's Holy Magic is "not a crutch upon which to lean" (her lecture on ASK ... ABOUT MAGIC, every time).

## TDPs

`;tdp` on `auto` follows the guild's tiers from Elanthipedia's Paladin new player guide (`client/game/tdp.py`): Strength and Stamina to about 15 (the plate's burden), then Reflex, Agility and Discipline to about 15, then the lowest of all eight. A plan's `tdps` task spends up to three points a cycle (#230); 402 to 571 points piled up in one day before it did.

## The guild's rooms, by map id

| Room | Id | Used for |
|---|---|---|
| The Crossing, Paladins' Guild, Library | 11716 | the profile's `home` and `library`; `;scholarship books` |
| The Crossing, Paladins' Guild, Chambers → Hallway | 7890 → 11712 | `go arch`: the soulstone arch that reads the state (#231) |
| The Crossing, Paladins' Guild, Guild Leader's Office | off the Meeting Hall with the guild register | Verika: circles, spells, the quest |
| The Crossing, Herald Street | 815 | "a steel tithe box" outside the guild (PUT ... KRONARS IN BOX) |
| The Crossing, Immortals' Approach | 741 | "the locked almsbox" outside the temple gate |
| The Crossing, Temple, Chadatru's Shrine | 5845 | the prayer; PUSH GRANITE ALTAR WITH BADGE is not attuned there |
| Shard, Xibar's Crescent Road → Tower of Honor | 2522 → 8219 | `go tower`: the arch that reads the state |
| Shard, Tower of Honor, Orb Room | 8228 | RUB / EXHALE / FOCUS the soulstone orb — the only pool reading |
| Shard, Tower of Honor, chapel | 13430 | PRAY CHADATRU |
| Shard, Tower of Honor, Guildleader's Office | | Lady Snow |
| Shard, Temple of Light, Alcove of Smaragdaus | 13143 | the tithe in Dokoras (map tag `tithe`) |
| Ratha, Paladins' Guild, Foyer | 12961 | an almsbox |

Getting between them: 243 steps from the Crossing library to the Orb Room under the Segoltha and over Obsidian Pass by the gondola (#211); the guild's `go trail` shortcut into the back promenade is closed below a circle ("You're not experienced enough to go there.", circle 2, #209) and the walker goes round; the Pass's Chasm branch is gated on Athletics 540 and the walker drops it (#214). Shard's gate is a bescort route with a night refusal, unwalked (#215). [movement.md](movement.md) has the model.

## Open

- #212 the four remaining glyph quests; #215 Shard's gate.
- A refused circle's wording, a SMITE CHECK with no free blows, RUSH.
- docs/cleric.md when the Cleric's scripts appear (Devotion, the badge's storeroom, the escort).
