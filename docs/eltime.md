# The Elanthian clock model

The clocks dock computes Elanthia's date, time, and moon phases from
real time alone; `;clock` calibrates the computation against the game
the way ntpdate trues a computer clock. This file records the calendar
constants the code assumes and the captured evidence behind them, so a
future discrepancy has a dated record of what was believed and why.
Canon lives on [Elanthipedia's Time
page](https://elanthipedia.play.net/Time) — this is not a mirror.

## The model

Elanthia's calendar is a fixed function of real time:

| unit  | game length | real length |
|-------|-------------|-------------|
| roisan | the minute | 1 minute |
| anlas | 2 game hours (30 roisaen) | 30 minutes |
| day   | 12 anlaen (also spoken of as 24 hours) | 6 hours |
| andu (week) | 4 days | 1 day |
| month | 10 andaen (40 days) | 10 days |
| year  | 10 months (400 days) | 100 days |

Years count up from the Victory of Lanival, exactly as `TIME` reports
them, and are named on a seven-year cycle indexed by `year % 7`
(Silver Unicorn first). Months, anlaen, and weeks have fixed names —
the tuples in [client/client/eltime.py](../client/client/eltime.py)
list them in order.

The epoch (`VICTORY_EPOCH`) is derived from a captured `TIME`, placing
the capture mid-anlas: uncalibrated error is at most ±15 real minutes.
`;clock` stores a correcting offset in settings
(`eltime_offset_seconds`); the dock re-reads it once a minute.

## The moons

Xibar, Yavash, and Katamba each cycle through eight phases (new →
waxing crescent → first quarter → waxing gibbous → full → and back).
Elanthipedia documents mean cycle lengths — Xibar ≈ 6.5, Katamba ≈
9.4, Yavash ≈ 10.1 real days — but no alignment with the calendar, so
phase anchors can only come from observation: `OBSERVE MOONS` works
for any guild, needs open sky, costs ~10s of roundtime, and only
describes moons above the horizon. `;clock` parses whatever it can see
and stores per-moon new-moon instants in settings (`eltime_moons`);
moons never yet observed show `?` in the dock.

Two caveats, both by design:

- The in-game orbits wobble around the documented means (rise-to-rise
  intervals alternate), so an anchor drifts slowly — a phase lasts
  19–28 real hours and the mean-cycle error is under 1%, so an
  occasional `;clock` keeps the display right.
- A phase observation places the moon mid-phase (±1/16 cycle, under a
  real day); good enough for a phase display, never for an ephemeris.

Earth's moon (the optional for-fun row) uses the standard mean synodic
month of 29.530589 days anchored on the new moon of 2000-01-06 18:14
UTC.

## Evidence

- **Captured `TIME`, 2026-08-22 12:21:56 UTC** (the fixture in
  [client/tests/test_eltime.py](../client/tests/test_eltime.py)):
  "457 years, 174 days since the Victory", "5th month of Uthmor the
  Giant in the year of the Golden Panther", "past the Anlas of
  Meraud's Cloak". Validates the unit math three ways: 457 % 7 = 2 →
  Golden Panther; 174 // 40 = month 5 → Uthmor; and dusk falling in
  the 10th anlas. `VICTORY_EPOCH` is derived from this capture.
- **A character's `INFO`**: "born … in the year of the Emerald
  Dolphin, 341 years after the victory of Lanival the Redeemer" —
  341 % 7 = 5 → Emerald Dolphin, an independent pin on the year-name
  cycle.
- **Captured `OBSERVE MOONS`, 2026-08-22 12:29:37 UTC**: "The black
  moon Katamba has waned to a narrow crescent of light", Xibar and
  Yavash "nowhere to be seen". Anchors Katamba (waning crescent).
- **Captured `OBSERVE MOONS`, 2026-08-22 12:42:26 UTC**: "The moon
  Yavash forms a perfect circle in the heavens" — the full-moon
  wording, anchoring Yavash. Xibar ships unanchored until a sync
  catches it risen (issue #64).
- **Elanthipedia**: [Time](https://elanthipedia.play.net/Time) for the
  units and names; [Xibar](https://elanthipedia.play.net/Xibar),
  [Yavash](https://elanthipedia.play.net/Yavash), and
  [Katamba](https://elanthipedia.play.net/Katamba) for the phase
  cycle lengths (given per-phase in roisaen, eight phases per cycle).
