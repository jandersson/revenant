# Encumbrance

The game shows a burden level, not a weight; `;enc` turns the level into a weight band and says how many Strength or Stamina points would lighten it. The rule is Elanthipedia's [Encumbrance](https://elanthipedia.play.net/Encumbrance) page, and it held when tested.

## Using it

```
;enc                    the level, its weight band, the points that would lighten it
;enc log <note>         log a reading with a note
;enc ballast [step=50]  at a teller: pin the load's weight with coins
;enc show               the logged readings
```

## The rule

Levels run 1 (None) to 12 ("It's amazing you aren't squashed!"). At level *L* a character carries up to

    10 × ceil(0.4 × (L + 5) × (Strength + Stamina)) stones

- Strength and Stamina count the same; each point widens every band.
- A coin of any metal weighs 0.2 stones.
- Because the load's place inside its band is unknown, `;enc` gives the points needed as a range.

## Ballast

`;enc ballast` withdraws copper in steps (50 stones by default), reads ENCUMBRANCE after each, and stops when the level rises. The load is then known to one step, so the points needed are exact. The coins go back with DEPOSIT; every step is logged to history.db's `encumbrance` table. A smaller `step=` narrows the band.

## Armor

- **Wear armor, never carry it.** Worn full plate counted about half its 500 stones; the same plate in hand or in a sack counted in full.
- **A container adds nothing.** An item reads the same in hand or in a sack.

## Weighing one item

MAMAS shops weigh items for a fee: PUT <item> ON COUNTER, or ASK CLERK ABOUT WEIGHT for your 25 heaviest. The Crossing has a branch.
