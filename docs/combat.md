# Combat

What the scripts that fight or flee (`;hunt`, `;fight`, `;athletics`, `;train`) believe about DragonRealms combat. Canon is Elanthipedia's [Combat 101](https://elanthipedia.play.net/Combat_101) and [Stance](https://elanthipedia.play.net/Stance).

## Range

- Three ranges: missile (outdoor fights start here), pole, melee. A hostile advances one step at a time.
- The parser's `hostiles` comes from the `crtrStatus` tags, which may arrive only once per sighting; it is cleared on a room change, never on an empty listing.
- `RETREAT` steps out one range and **can fail** while engaged ("You are unable to retreat from...").
- At missile range you can move or climb again, even with the creature still in the room.

## Getting away

Every script flees the same way (`client/game/flight.py`):

1. STAND if sitting or prone (RETREAT from a seat does nothing).
2. RETREAT, RETREAT and a move, sent back to back so the creature has no gap to close in.
3. The move is the script's own next step first, then each compass exit, then OUT; up to eight bursts.
4. Success is **the room changing**, not the hostiles leaving.

Spawn areas never empty on their own: a script leaves a contested spot rather than wait.

## Attacking

- `ATTACK <noun>` picks the maneuver; barehanded trains Brawling.
- **Corpses keep their noun.** "The cougar is already quite dead." means the swing hit the body; `;hunt` aims with an ordinal ("attack second cougar") past it.
- **A kill is counted by the room listing:** a new "which appears dead" creature. Death lines vary too much to trust; a knockdown ("falls to the ground grasping its...") is not a kill.
- A bare `LOOT` searches the last creature fought and disposes of the corpse.
- "What were you referring to?" means nothing by that noun is left.

## Stance and balance

- `STANCE SET <evasion> <parry> <shield> [<attack>]`: 180 base points plus some from Defending ranks. `;hunt` sets the profile's `stance` before it fights.
- The balance word ("solidly balanced", 0 to 11) is `s.status.balance` / `balance_level`; `;hunt` tallies it and reports it at the end, but acts on nothing yet.

## Caveat

Every swing, hit and kill line arrives on the **`combat` stream**, not the story. `probe.collect` reads both; a script reading `get()` by hand must ask for `combat` too or it never sees a kill.
