# The soul

A Paladin's soul has a state and a pool. `;soul` reads them and runs the deeds that raise them; `;train` runs the deeds in its rests. The model is `client/game/soul.py`; the canon is [Elanthipedia's Soul system](https://elanthipedia.play.net/Soul_system).

## The readings

| | Levels | Read by |
| --- | --- | --- |
| State | 7, black and corrupted to pristine luminescence | RUB an orb, or walk through a soulstone arch |
| Pool | 11, empty to full | EXHALE on an orb |

- The state drifts down, but never below chalky grey (4) on its own.
- A better state makes the pool read emptier until it refills, within hours.
- The only orb is in Shard's Tower of Honor; elsewhere `;soul` reads the state at the nearest arch, and the pool goes unread.
- Fleeing combat and SMITE with an empty pool lower it; `;hunt` smites only with a free blow.

## The deeds

| Deed | Command | Timer | Where |
| --- | --- | --- | --- |
| Pilgrim's badge | `;soul badge` | 31 min | anywhere |
| Tithe | `;soul tithe` | 4 h | nearest almsbox, 5 silver |
| Prayer | `;soul pray` | 2 h | nearest Chadatru altar, knelt ~75 s |
| Song | by hand: `play <song> <style> on <instrument> for chadatru` | over 2 min, not yet measured | the Crossing temple's Chadatru shrine |

- The badge needs attuned altars pushed onto it (PUSH <altar> WITH BADGE).
- The song needs "only the slightest hint of difficulty", not off-key or halting; any song counts (a lament did, 2026-10-03). The soul line comes after "You finish playing ...": "A warm, soothing sensation washes over your soul." The same song again at once ended without it.
- A refused deed backs off 20 minutes; a room over 80 rooms away is skipped.
- A debt to the province blocks the tithe; `;debt` pays it. `;soul` never withdraws coins.
- Timers live in `~/.revenant/soul/<name>.json`, shared with `;train`.

**The pristine gate:** while a reading under four hours old says pristine, no deed runs. The deeds restore a soul; they do not maintain one. With no fresh reading, the reading comes first.

## Commands

```
;soul                        read the state (and the pool at an orb)
;soul keep                   run the deeds on their timers while below pristine
;soul badge | tithe | pray   one deed
;soul quest [force]          the Glyph of Warding scene at the orb
;soul return                 finish the deed in hand and end
```

`almsbox=ID`, `altar=ID` and `currency=lirums` override the map's rooms and the coin.

With the plan's `soul: on`, `;train` does the same in its rests, never mid-task, and stops a hand-started `;soul keep`.

## The quest scene

`;soul quest` runs the circle-5 Glyph of Warding quest at the Tower of Honor's orb: pristine state and full pool, FOCUS ORB, GUARD GIRL as the fleeing girl passes, and the glyph is granted within a minute.

- **Caveat:** "rest and contemplate a bit first" is a wait timer, not the soul. The FOCUS that worked came an hour after the last refusal.
