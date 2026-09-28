# Hunting

`;hunt` walks to your hunting ground, fights whatever is there, skins and loots each kill, and moves room to room until a limit sends it home. Everything character-specific comes from your profile, so the same script hunts for any character.

## Running it

```
;hunt                 # hunt with the profile
;hunt <style>         # hunt one of the profile's hunt styles
;hunt here            # skip the walk; hunt where you stand
;hunt grounds [rank]  # hunting zones that suit your weakest weapon, nearest first
;hunt profile [style] # print the profile it would use
;hunt styles          # list the hunt styles
;hunt return          # finish the kill, walk home, sell skins and bank
;stop hunt            # quit where you stand
```

- Under `;train`, `;hunt return` skips the selling and banking; the plan has its own tasks for those ([training.md](training.md)).
- The weapon stays in hand when the hunt ends.
- A room another player is already in is theirs: the hunt moves on without a swing, whatever creatures are in it. With every room taken, it goes home. A room full of creatures is fought, one at a time.

## The profile

File → Character Profile, or `~/.revenant/profiles/<name>.json`. The keys a hunt reads:

| Key | What it does |
| --- | --- |
| `hunting_ground` | a map tag, a bestiary zone (`;hunt grounds`) or a `;go2` target |
| `prey` | the noun to attack; empty fights whatever engages you |
| `home` | a `;go2` target walked to when the hunt ends |
| `weapon`, `weapon_container` | the weapon WIELDed at the start, and where it is kept |
| `stance` | `STANCE SET` arguments, sent once |
| `skin`, `skin_knife` | skin each kill; a knife noun, or empty for a worn knife or the weapon |
| `bundle` | put skins on a worn bundling rope (free at any tannery) |
| `loot_container`, `gem_pouch` | where loot and skins go; where gems go |
| `loot_additions`, `loot_subtractions` | nouns also picked up; nouns never picked up |
| `loot_ignore` | loot not worth keeping: never picked up, trashed from boxes (default: the common metals) |
| `box_limit` | boxes carried at most (0: no limit) |
| `almanac` | an almanac's noun: studied whenever its 10-minute timer allows, by any running script at its next safe point ([training.md](training.md)); `;hunt` studies it in a clear room, or mid-fight after a RETREAT to pole range |
| `health_floor` | break off below this health % (60) |
| `wound_floor` | break off at a wound this bad; empty is `harmful`, `off` never checks |
| `train_skills` | end when all of these mind-lock |
| `max_kills` | end after this many kills (0: no limit) |
| `weapons`, `weapon_target`, `brawling` | the weapon rotation, below |
| `buffs`, `train_casting`, `cambrinth*`, `cast_gap`, `debilitation`, `targeted` | spells, below |
| `smite` | Paladin: one swing a minute is SMITE, for Conviction |
| `tactics` | maneuvers (`bob`, `circle`, `weave`) every third swing, for Tactics |
| `perception` | HUNT for tracks when a room empties, for Perception |
| `analyze`, `abilities`, `roar` | Barbarian: a self-combo, berserks/forms, a roar at the prey |

Each training key works only while its skill is below mind-lock.

## Hunt styles

One character hunts for different reasons: to train, or to farm boxes for `;boxes`. `hunts` in the profile file (hand-edited; the dialog keeps it) names styles, each a few keys laid over the profile:

```json
"hunts": {
  "boxes": {"hunting_ground": "goblins", "skin": false, "bundle": false,
            "train_skills": [], "box_limit": 8, "until": "boxes"}
}
```

`until` decides what ends the run:

| `until` | Ends when |
| --- | --- |
| `lock` (default) | every `train_skills` skill mind-locks |
| `boxes` | the loot container holds `box_limit` boxes, or refuses the next |
| `kills` | `max_kills` is reached |

A `;train` task passes the style in its args: `"script": "hunt", "args": ["boxes"]`.

## Weapon rotation

`weapons` lists `noun:Skill[:container]` entries, e.g. `handaxe:Small Edged:sack`, `fists:Brawling`.

- The weapon whose skill has the emptiest pool fights first, and keeps fighting until its skill reaches `weapon_target` (30). Then the next emptiest takes over. Equally empty pools go to the skill trained longest ago, then the lowest rank.
- Once every weapon is past the target, the emptiest unlocked one fights on to lock.
- A locked skill's weapon sits out until it drains. All locked ends the hunt.
- A weapon that goes 20 swings without a kill hands over to the next.
- `fists:Brawling` swings the `brawling` attacks (`punch`, `kick`, `elbow`) with empty hands; worn knuckles and a parry stick still work. With `brawling` empty, the fists turn is skipped.
- With `weapons` empty, the hunt uses `weapon` alone.

## What ends a hunt

- **Health** below `health_floor`, or a **wound** at `wound_floor`: retreat, then walk home (or to the nearest room off the ground if no `home`). A wound already at the floor keeps the hunt from setting out; `;heal` treats it.
- **A losing fight**: 60 swings without a kill, or three stuns in one fight, break off the same way.
- **Locks**: every `train_skills` skill mind-locked, or every weapon in the rotation locked.
- **The style's `until`**: boxes, or `max_kills`.
- **You**: `;hunt return` or `;stop hunt`.

An empty ground is not an end: the hunt waits and laps it again.

## Loot and skins

- Each kill is skinned (with `skin`) and LOOTed. Coins, gems and boxes are picked up, plus `loot_additions`, minus `loot_subtractions` and `loot_ignore`.
- `loot_ignore` holds phrases that end an item's name (`embroidery needle`) or a lone metal (`copper` for any copper nugget or bar). The default is the common metals (copper, covellite, iron, lead, nickel, oravir, silver, tin, zinc); rare ones are kept. `;boxes` puts these in the room's trash, or keeps them where there is none.
- Gems go to `gem_pouch`; gems are kept for `;appraise`, never sold.
- A full loot container stops skinning or box pickups for the run, and says so. `;skins` sells skins; `;boxes` opens boxes.
- With `bundle`, the first skin starts a bundle from the rope in the loot container and later skins go straight into it. `;skins` sells the bundle and keeps the rope.
- Nothing is ever dropped.

## Spells and abilities

- **`buffs`** are cast before the walk and recast whenever the Spells window drops one.
- **`train_casting`** (e.g. `Augmentation, Warding, Utility`, or `all`) recasts a buff every `cast_gap` seconds (60) for the named skill with the emptiest pool. Its mana starts a step under what DISCERN says you can hold and climbs to it; a cambrinth charge counts toward that. Each skill is trained by the first buff DISCERN says uses it; a skill no buff uses is named once.
- **`cambrinth`** charges a piece with `cambrinth_mana` before each training cast, for Arcana. Set `cambrinth_worn` for an anklet or armband; a worn piece is removed to charge. The piece must not outrank your Arcana (a 1- or 5-mana piece at 0 ranks).
- **`debilitation`** (e.g. `Stun Foe`) and **`targeted`** (e.g. `Footman's Strike`) are cast at the prey on the same gap. The training casts take turns, so a swing never carries two.
- Mana never ramps past what DISCERN says you can hold; a cast that strains or backfires holds a step under for the rest of the run. A spell your ranks cannot cast is turned off for the run, with the rank it needs.
- Barbarians cast nothing: `analyze`, `abilities` and `roar` fill the same roles.

## Caveats

- Answers the script cannot place are echoed as `hunt: unrecognized ...`. Report them; they become test fixtures.
- Once a hunt, it names the weapon skills the room's creatures are too weak to teach. When it does, pick a harder ground.
- Melee only, one opponent at a time; no ranged combat. The fight itself is in [combat.md](combat.md), wounds in [wounds.md](wounds.md).
