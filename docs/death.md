# Death

`;deathwatch` (autostarted) logs a dead, unattended character out before the body decays, so it waits for a raise at the next login and nothing is lost.

```
;deathwatch            quit after a 10-minute rescue grace
;deathwatch 5          a five-minute grace
;deathwatch depart     DEPART at the grace instead of quitting
;deathwatch young      depart at once on a death at circle 1 with fewer than 6 deaths
```

`;stop deathwatch` holds it off while a rescue is underway.

## The clock

- Death announces its deadline: "Your body will decay ... in 21 minutes." The grace is kept inside that window with a five-minute margin.
- **The clock stops while logged out.** A dead character who quits is still a ghost with a body at the next login. That is why the default ending is QUIT, which the game accepts while dead and which spends nothing.

## Departing

| Variant | Favors | Keeps |
| --- | --- | --- |
| DEPART FULL | 3 | items and coins |
| DEPART ITEMS | 2 | items (coins lost) |
| DEPART COINS | 2 | coins (items to a grave) |
| DEPART GRAVE | 1 | items go to a grave |
| DEPART | 0 | maximum penalties |

`;deathwatch depart` tries the best variant first and judges each by the DEAD indicator clearing. Keep three favors banked with `;favors` ([favors.md](favors.md)).

## A young character

With `deathwatch_young_depart` on (File → Settings; off by default), a death at circle 1 with fewer than 6 deaths departs at once: a new character loses next to nothing, and waiting as a ghost gains nothing. The circle and death count come from INFO and EXP; if either is unknown, the usual ending applies.

## Caveats

- The game announces DEAD only when it flips. The session carries the indicator across `;reexec`, and a watch started on an already-dead character starts its countdown at once.
- One zero-favor decay-depart came back with inventory intact, against the wiki's maximum penalties. The code assumes the wiki.
- While dead, commands answer "You are a ghost!" — that still counts as activity for the idle check.
