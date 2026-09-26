# Paladin

An index of the Paladin facts the scripts rely on, each pointing to the page or script that holds the details. Canon is Elanthipedia's [Paladin](https://elanthipedia.play.net/Paladin) page.

## Test character: Lanival, circle 10

Lanival is the synthetic test Paladin, a Dwarf of the Crossing guild; these facts were measured playing Lanival.

- Glyphs: Dueling and Warding.
- Spells: Heroic Strength, Aspirant's Aegis, Stun Foe, Sentinel's Resolve, Courage, Footman's Strike, Hands of Justice.
- Training: badgers barehanded for Brawling, climbs, books, zills, power walking, forage.

## Index

| Topic | In one line | Details |
| --- | --- | --- |
| Circles | `;circle` checks the requirements; armor slots count only the four armor skills | [circles.md](circles.md) |
| Soul | read at an orb or soulstone arch; badge, prayer and tithe raise it; `;soul keep` runs them only below pristine | [soul.md](soul.md) |
| Soul pool | EXHALE on an orb reads it; SMITE on an empty pool lowers the soul | [soul.md](soul.md) |
| Glyph quests | Warding (circle 5) is `;soul quest`; the later four are not scripted | [soul.md](soul.md) |
| Smite | trains Conviction; `;hunt` smites only while SMITE CHECK counts a free blow; the profile's `smite` is off by default | [hunting.md](hunting.md) |
| Spells | the profile's `buffs`; Stun Foe is the `debilitation` cast, Footman's Strike the `targeted` one | [hunting.md](hunting.md) |
| TDPs | `;tdp` on `auto`: Strength and Stamina to 15, then Reflex, Agility, Discipline to 15, then the lowest stat | [training.md](training.md) |
| Travel | the walker rides the gondola to Shard | [movement.md](movement.md) |

## The guild's rooms

| Room | Map id | Used for |
| --- | --- | --- |
| Crossing, Paladins' Guild, Library | 11716 | `home`, `library`, a Paladin's safe room |
| Crossing, Paladins' Guild, Chambers → Hallway | 7890 → 11712 | the soulstone arch (only a Paladin passes) |
| Crossing, Guild Leader's Office | | Verika: circles, spells |
| Crossing, Herald Street | 815 | tithe box (`box`, not `almsbox`) |
| Crossing, Immortals' Approach | 741 | almsbox |
| Crossing, Temple, Chadatru's Shrine | 5845 | the prayer |
| Shard, Tower of Honor | 8219 | the arch |
| Shard, Tower of Honor, Orb Room | 8228 | RUB / EXHALE / FOCUS the orb |
| Shard, Tower of Honor, chapel | 13430 | the prayer |
| Shard, Temple of Light | 13143 | tithe in Dokoras |
| Ratha, Paladins' Guild, Foyer | 12961 | almsbox |

The soul's pool can be read only at an orb; the nearest to the Crossing is in Shard.
