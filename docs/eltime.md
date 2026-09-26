# The Elanthian clock

The clocks dock computes Elanthia's date, time and moons from the server's clock alone; `;clock` corrects that computation against the game. Canon is Elanthipedia's [Time](https://elanthipedia.play.net/Time) page.

## Using it

```
;clock          send TIME and OBSERVE MOONS, store the correction; again every six hours
;clock once     sync once and exit
;clock watch    send nothing; correct the clock from sun and moon lines as they arrive
;clock moons    each moon up or down, and when it next rises or sets
```

- The correction is saved in settings (`eltime_offset_seconds`); the dock re-reads it every minute.
- OBSERVE MOONS needs open sky and costs a few seconds of roundtime; indoors it is skipped.
- A moon never observed shows `?` in the dock.

## The calendar

| Unit | Game | Real |
| --- | --- | --- |
| roisan | 1 minute | 1 minute |
| anlas | 30 roisaen | 30 minutes |
| day | 12 anlaen | 6 hours |
| andu (week) | 4 days | 1 day |
| month | 40 days | 10 days |
| year | 10 months | 100 days |

Years count from the Victory of Lanival; their names cycle every seven years. The names are in `client/client/game/eltime.py`.

## How it stays right

- **Server time.** Every game prompt carries the server's clock, so a drifting local clock does not skew the calendar.
- **TIME.** "N roisaen before the Anlas of X" pins the minute; "past the Anlas of X" is only good to ±15 minutes.
- **Day-phase check.** `;clock` refuses a correction when TIME's word ("dawn", "dusk"...) disagrees with the computed hour (`DAY_PHASES`).
- **Sun lines.** "The sun rises..." and three others fire at fixed hours (`SUN_BOUNDARIES`); `;clock watch` corrects the clock when it is over 90 seconds out.

## The moons

Xibar, Yavash and Katamba each have two separate models:

- **Orbit** (in the sky or not): fixed rise-to-rise periods of about 348, 353 and 352 minutes. Each rise or set line `;clock watch` hears re-anchors it.
- **Phase** (its shape): mean cycles of about 6.5, 10.1 and 9.4 Earth days, anchored only by OBSERVE MOONS, which sees only the moons above the horizon.

## Caveat

A phase reading places the moon mid-phase and the cycles wobble around their means, so a phase drifts slowly between observations; run `;clock` now and then to keep the dock right.
