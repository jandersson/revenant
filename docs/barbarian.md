# Barbarians

A Barbarian casts no spells: Inner Fire powers abilities, roars debilitate, and Expertise gates every circle. These are the pieces of Revenant built for that.

## Inner Fire

- The mana bar is Inner Fire.
- It refills slowly on its own (to about 30% at circle 1) and fast in combat: kills and `ANALYZE FLAME`.

## Abilities

| Kind | Command | At once |
| --- | --- | --- |
| Berserk | `BERSERK <name>` | no limit |
| Form | `FORM <name>` | 5 |
| Meditation | `MEDITATE <name>` (sitting, out of combat) | 3 |
| Roar | `ROAR <name> [at <foe>]` | no limit (voice pool) |

- `ABILITY LIST` shows what you know and the training sessions left.
- `;hunt` keeps the profile's `abilities` up: before the walk, and again when one ends. Meditations only outside the fight.

## Training the magic skills: `;research`

```
;research                       Augmentation, Warding and Utility in turn, emptiest first
;research augmentation=buffalo  research another ability for that skill
;research once                  stop when all three lock
;research return                finish the research in hand and end
```

- `MEDITATE RESEARCH` teaches an ability's skill whether you know the ability or not, and Inner Fire with it.
- One research a minute. Debilitation can't be researched; roars train it.

## Expertise: `ANALYZE` in `;hunt`

- Set the profile's `analyze` to `flame` (from 0 Expertise), `accuracy` (50) or `damage` (125).
- While Expertise is below lock, `;hunt` starts a combo and swings its attacks in place of ATTACK.

## Profile keys

| Key | Example | Does |
| --- | --- | --- |
| `analyze` | `flame` | self-combos for Expertise |
| `abilities` | `Avalanche, Buffalo` | kept up through the hunt |
| `roar` | `anger` | a roar at the prey once a minute, for Debilitation |

Set them in File → Character Profile. `buffs`, `train_casting` and the other spell keys don't apply.

## Circles

`;circle` lists what gates your next circle. See [circles.md](circles.md).

## The test character: Uthmor, circle 1

These scripts' wordings and figures were measured on Uthmor's play, a Rakash Barbarian of Riverhaven (a synthetic name). Uthmor knows no abilities yet, so the ability and roar wordings are dr-scripts' and untested.
