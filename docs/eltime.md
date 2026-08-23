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

The clock anchors to the *server's* time, not the machine's (#102):
every `<prompt time="...">` states the server's Unix clock (captured
prompts sit within a second of real UTC), the engine broadcasts the
server-minus-local delta as a `timesync` frame when it first appears
or moves, and both the clocks dock and `;clock`'s calibration compute
from it. A drifting local clock therefore cannot skew the calendar —
the stored offset is a pure server-epoch mapping.

TIME's anlas sentence is phrased *relative* to a named anlas, and the
phrasing sets the calibration precision (#101): "N roisaen before the
Anlas of X" pins the moment to the roisan (X has not started — the
sharpest variant the game offers), "past the Anlas of X" states no
count and is anchored mid-X (±15 real minutes). Misreading "before"
as "within" cost ~29 real minutes of drift when it was live
(2026-08-23) — the wordings are load-bearing, capture any new one.

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
- **Captured `TIME`, 2026-08-23, Elanthian mid-afternoon** (fixture
  `TIME_TEXT_BEFORE`): "457 years, 179 days", "14 roisaen before the
  Anlas of Meraud's Cloak" — the roisaen-count phrasing, 17:04 to the
  minute. The #101 regression capture.
- **A character's `INFO`**: "born … in the year of the Emerald
  Dolphin, 341 years after the victory of Lanival the Redeemer" —
  341 % 7 = 5 → Emerald Dolphin, an independent pin on the year-name
  cycle.
- **Captured `OBSERVE MOONS`, 2026-08-22 12:29:37 UTC**: "The black
  moon Katamba has waned to a narrow crescent of light", Xibar and
  Yavash "nowhere to be seen". Anchors Katamba (waning crescent).
- **Captured `OBSERVE MOONS`, 2026-08-23 18:39:18 UTC (server
  clock)**: "The blue moon Xibar, beginning to wane, travels slowly
  through the sky." — and Yavash likewise. A phase wording with no
  shape word at all ("beginning to wane" = just past full, waning
  gibbous); the classifier learned it that night, anchoring Xibar
  for the first time and closing #64. The anticipated "beginning to
  wax" symmetric is classified but not yet captured.
- **Captured `OBSERVE MOONS`, 2026-08-22 12:42:26 UTC**: "The moon
  Yavash forms a perfect circle in the heavens" — the full-moon
  wording, anchoring Yavash. Xibar ships unanchored until a sync
  catches it risen (issue #64).
- **Elanthipedia**: [Time](https://elanthipedia.play.net/Time) for the
  units and names; [Xibar](https://elanthipedia.play.net/Xibar),
  [Yavash](https://elanthipedia.play.net/Yavash), and
  [Katamba](https://elanthipedia.play.net/Katamba) for the phase
  cycle lengths (given per-phase in roisaen, eight phases per cycle).
