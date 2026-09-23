# The experience model the scripts assume

The training scripts encode assumptions about DragonRealms' experience
system. This file records those assumptions with their evidence, so a
future game change has a dated record of what the code believed and why.
Canon lives on [Elanthipedia's Experience
page](https://elanthipedia.play.net/Experience) — this is not a mirror.

## The model

Experience is a two-stage pool system, per skill:

1. **Inflow** — accepted actions push *field experience* into the
   skill's pool. Inflow is gated three ways: by action type (Athletics
   accepts climbs, swims, and `climb practice` — not ordinary
   movement); by challenge — an action that has become trivial for
   your ranks grants **zero**, not "a little"; and by a **per-award
   timer** on standard climbing travel actions — a random 45–60s
   window in which repeat climbs grant nothing (Elanthipedia,
   community-tested). `climb practice` and special climbs are exempt
   from the timer.
2. **The pool** — capacity depends on skillset placement, ranks,
   Intelligence, and Discipline. The mindstate shown in the exp window
   (0–34, "clear" through "mind lock") is purely the pool's fill gauge.
3. **Outflow** — the pool drains into permanent ranks in periodic
   pulses regardless of activity. Wisdom sizes the pulse; rested
   experience (REXP) triples the conversion while it lasts.

## Rested experience (REXP)

Researched 2026-08-23 (Elanthipedia "Experience"; the status line
captured live the same day). REXP is banked time that **triples the
pool-to-ranks conversion** while it burns — outflow's pulse converts
3x the ranks, which is why a rested session ran Athletics 4 → 12 in
one evening (the 2026-08-21 evidence below).

- **Accrual**: 2 minutes of not draining experience banks 1 minute of
  REXP, starting after 5 consecutive minutes without drain — offline,
  online with empty pools, or in deep sleep alike.
- **Banked cap by subscription**: F2P none (2h with a Brain Boost
  purchase), Standard 4h, Premium 6h, Platinum-instance 8h.
- **Usage cap and cycle**: a personal 23:30h cycle starts when you
  first touch the system and caps how much banked time can burn per
  cycle (the tier amount); the cap refreshes when the cycle ends.
- **Burn**: each of the ten skill groups that pulses **with
  experience in it** deducts 20 seconds of REXP; a group pulsing
  empty deducts nothing — training few skill groups stretches the
  banked hours further.
- **Sleep**: SLEEP once (light) stops inflow but the pool keeps
  draining and burning REXP; SLEEP twice (deep) stops both, banks
  instead of burns.
- **Status** — the EXP footer, captured live 2026-08-23:
  `Rested EXP Stored: 5:42 hours  Usable This Cycle: 5:42 hours
  Cycle Refreshes: 21 hours`. Times are H:MM. The same line comes
  as `<component id='exp rexp'>` on every exp pulse (1535 times in
  one 2026-09-12 session): the parser keeps it as `rested` (stored,
  usable, refresh in minutes, `client/game/rested.py`), the
  Experience dock shows it as its last line, and `;sheet`'s 3-hourly
  EXP ALL stores it too (#106, #176).

What it means for the tooling: rank-per-hour numbers in beholder are
meaningless without knowing whether the 3x window was open. Read live
from the footer (2026-09-12): the bank fell one minute at a time from
5:45 to 4:46 over an afternoon of hunting, and the 23:30 h cycle
turned over mid-session (usable 5:35 back to 5:42, refresh 1:51 to
23:01). So burning is the usable figure falling between two readings
(`rested.burning`), and `;xp` flags every mindstate row it takes with
`is_rexp` — 1 when the figure fell since the previous minute, 0 when
it held or grew, NULL the first minute or before the footer has been
seen — and logs the footer to the `rested` table on every change
(#176). Beholder shades each run of flagged minutes exactly, a minute
past its last row, and charts the bank's slope from the rested rows
merged with the sheet's three-hourly `rexp_stored` / `rexp_usable` /
`rexp_refresh`. Rows from before the flag keep the older guess: a
window from a snapshot with usable hours until the next snapshot or
the burn-out, whichever comes first (#106). Trainers might also
prefer draining few skill groups
while rested, per the burn rule.

## How fast a pool drains

A pool drains linearly: each 200-second pulse removes a fixed number
of mindstate buckets, set by the skill's drain tier, until it clears.
Fitted 2026-09-24 from ;xp's per-minute rows of one Paladin (#300),
this is what `client/game/drain.py` computes a rest's length from.

| Drain tier | Buckets per pulse | 34 to 0 | 34 to 10 | Runs |
| ---------- | ----------------- | ------- | -------- | ---- |
| primary    | 1.14              | 99 min  | 70 min   | 47   |
| secondary  | 0.91              | 125 min | 88 min   | 186  |
| tertiary   | 0.65              | 174 min | 123 min  | 285  |

- **Method.** history.db's `mindstate` rows (about 84,000, 2026-09-04 to
  2026-09-23) cut per skill into drain-only runs: consecutive minutes,
  mindstate never rising, ended at the first 0, a reading unchanged
  for eight minutes above 0 dropped as stale (a pool above 0 always
  drains), at least ten samples and five buckets. 519 runs; the rate is
  the buckets lost over the run's pulses.
- **Linear, not proportional.** The time spent at each level is flat
  from 34 down to 1 (primary about 1.0 pulses a bucket, secondary 1.1,
  tertiary 1.5, the same in every band of five). The Experience page's
  "the pulse is a fraction of your total pool size" reads the same
  way: a fraction of the pool, not of what is in it.
- **Tiers.** Placement is the guild's skillset table (Elanthipedia,
  Skillsets). A tertiary skill under 25 ranks drains as secondary
  (0.89, 67 runs), as the Experience page says. **A secondary skill
  under 50 ranks does not drain as primary**, which contradicts that page:
  104 runs of a Paladin's weapon and lore skills at ranks 18-49
  drained at 0.93, beside 0.91 above 50 and 1.14 for the armor.
  Conviction, the Paladin's guild skill, drains with the armor
  (1.13), its skillset in the circle tables.
- **What does not move it.** Rank within a tier (−0.0004 a rank,
  not significant over ranks 3-75), rested experience (+0.02 in a
  robust fit: REXP triples the ranks a pulse buys — tertiary 2.2 to
  5.5 % a pulse — not the buckets it drains, as the page says). The
  rates held day by day from 2026-09-12 to 09-23 (tertiary
  0.63-0.67).
- **The mental stats.** Intelligence, and Discipline mostly, size the
  pool. A bucket is a share of the pool and so is a pulse, so a
  bigger pool holds more per bucket but does not drain faster in
  buckets. Intelligence drops out of a rest's length and is no
  input. Wisdom sizes the pulse, but these rows cannot measure it:
  secondary drains at 0.91 at Wisdom 10 (35 runs) and 0.90 at 15
  (147). The GM's table predicts only about +3 % between those
  values. `drain.py` scales the rates by that table (Wisdom 10: 100 %,
  30: 112 %, 60: 121 %, 90: 125 %, 120: 130 %), normalized to the
  fitted Wisdom of 15. That is an assumption from the page, not a
  measurement. Discipline's share of the pulse ("10 % efficiency")
  is left out.
- **Against the page's clear times.** Primary 40-60, secondary 50-80,
  tertiary 70-100 minutes on the page; about twice that here. The
  ratios agree (1 : 0.80 : 0.57 measured, 1 : 0.77 : 0.59 at the
  page's midpoints). Wisdom is not the gap: the GM's table puts
  Wisdom 15 within 3 % of 10. The page's times may be for a different
  era of the system, or its mindstate buckets may not be the pool
  fractions assumed here.
- **Back-test.** Predicted against the fitted runs: median error
  −0.5 %, 86 % of runs within 15 %; on runs of 15 buckets or more the
  median absolute error is 4.4 % and the 90th percentile 12.7 %. A
  pulse lands up to 200 s after any moment, so a single estimate can
  run about three minutes short.
- **Open.** Only one guild measured: other guilds' tiers are the
  Skillsets table read through the Paladin's rates. A Moon Mage's
  rows (magic primary) are the next test.

## What the code assumes, and where

- **`;athletics` pauses at mind-lock** — inflow to a full pool is
  wasted, so the trainer idles until the pool drains below 28/34.
- **`;athletics` advances the ladder on staleness** — an outgrown
  spot's inflow decays toward zero (the challenge gate), so a low, flat
  mindstate across consecutive reports means "move up", not "wait".
- **`;train` guesses a rest's length** from the drain table above
  (`client/game/drain.py`): the slowest tracked skill's buckets over
  its tier's rate, scaled by Wisdom. The rest itself still ends on
  the exp window.
- **`;xp` snapshots rank/percent/mindstate per minute** — meaningful
  because mindstate is a real gauge of pending experience, not
  cosmetic.

## Evidence

Controlled A/B, 2026-08-21, rank-12 Athletics, Midton Circle
(trainer paused for the test):

| Phase                    | Duration | Mindstate     | Upward pulses |
| ------------------------ | -------- | ------------- | ------------- |
| 16 plain west/east moves | 20s      | 19/34 → 19/34 | 0             |
| 3 apple-tree climb laps  | 38s      | 19/34 → 20/34 | 2             |

Plain movement contributed nothing; only climbs produced inflow. The
same evening also showed pure outflow (mindstate falling while rank
rose during idle time) and REXP's speed (rank 4 → 12 in one session
with rested hours banked).

Interleaved interval experiment, 2026-08-21, rank-14 Athletics, Midton
apple tree (upticks = upward mindstate transitions on the exp stream;
intervals containing a drain tick discarded):

| Block   | Climbs | Mindstate | Upticks (drains) |
| ------- | ------ | --------- | ---------------- |
| tight-1 | 40     | 26 → 28   | 2 (1)            |
| paced-1 | 4      | 28 → 28   | 1 (1)            |
| tight-2 | 40     | 28 → 30   | 2 (1)            |
| paced-2 | 4      | 30 → 31   | 1 (1)            |

Ten times the climbs bought the same awards per block — the per-climb
model is refuted; the one clean inter-award interval measured 58s,
inside the documented 45–60s window. Caveats: six upticks total, and
bucket quantization hides sub-bucket awards in both conditions alike.
