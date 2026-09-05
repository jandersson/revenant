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
  Cycle Refreshes: 21 hours`. Times are H:MM; the sheet script's
  3-hourly EXP ALL already receives this line (currently unparsed).

What it means for the tooling: rank-per-hour numbers in beholder are
meaningless without knowing whether the 3x window was open. The sheet
snapshot stores the footer's three durations (`rexp_stored`,
`rexp_usable`, `rexp_refresh`, minutes), beholder charts stored and
usable hours on the character sheet, and its mindstate plot shades the
stretches where a snapshot had usable hours — from that snapshot until
the next one or until the hours would have burnt out, whichever comes
first (#106). Coarse, since snapshots are three hours apart and burning
needs a draining skill, but enough to tell a rested run from an
ordinary one. Trainers might also prefer draining few skill groups
while rested, per the burn rule.

## What the code assumes, and where

- **`;athletics` pauses at mind-lock** — inflow to a full pool is
  wasted, so the trainer idles until the pool drains below 28/34.
- **`;athletics` advances the ladder on staleness** — an outgrown
  spot's inflow decays toward zero (the challenge gate), so a low, flat
  mindstate across consecutive reports means "move up", not "wait".
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
