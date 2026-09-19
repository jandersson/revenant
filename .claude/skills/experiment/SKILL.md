---
name: experiment
description: Run a game-mechanic experiment on a live DragonRealms session the way this repo does it — wiki first (`uv run python tools/wiki.py "<Title>"` reads and caches a page's raw text), a hypothesis with its falsifier, one variable per step, the prediction written before the reading, every reading logged, the result recorded where the code will find it. Use whenever the operator asks to test, verify, measure, pin down or "set up an experiment" for a mechanic (a threshold, a formula, a cost, a wording), or when a script rests on an assumption a live reading could settle.
---

# Running an experiment

An experiment here is a question about a game rule answered with the
game's own figures, recorded so nobody has to ask it again. The
`drive` skill is how commands go out; this is what to do with them.

## Before the first command

1. **Elanthipedia first.** Read the page for the mechanic and the forum
   posts it cites; DR3 (January 2013) changed stats, TDPs, skills and
   combat, so a page flagged for DR3 update is a hypothesis, not a
   fact. Write down the rule as the wiki gives it, with its worked
   example if there is one.
2. **State the hypothesis and what would falsify it**, in one sentence
   each, before anything is sent. "Heavy Burden holds 920 stones at 23
   combined points; if two Stamina points do not drop the level, the
   rule is wrong."
3. **Pick the instrument.** The repo has these; reuse before building:
   - `;enc ballast` — coins as a known weight, 0.2 stones each, to find
     a burden threshold (client/game/encumbrance.py).
   - `;climbexp` — one row per climb attempt with rank, stats, load,
     outcome (client/game/climblog.py).
   - `;tdp <stat> [goal]` and TDP PROJECT — the game's own cost quotes,
     no spend.
   - `;enc`, `;tdp`, INFO, EXP, the stat words — free readings.
   - history.db tables (`climbs`, `encumbrance`, `wealth`, `stats`) for
     anything already logged; a new experiment gets its own table with
     a module in client/game/ and a script that fills it.
4. **Say-so.** Every step that spends, trains, moves or drops needs the
   operator's word for that step (the `drive` rules). Spending a stat
   point for an experiment is a real cost; say what it will cost first.

## While it runs

5. **One variable per step, and the smallest step that answers.** Two
   points bought in one run answered "two suffice" and lost "one does
   not"; a 50-stone step found a band, the 10-stone step pinned it.
6. **Write the prediction before reading the answer**, in the chat,
   with the number: "TDP should read 399, not 459". A prediction written
   after the reading is a description.
7. **Log every reading**, not just the interesting ones: the row with
   the stats, the level, the step, a note. The rows are the evidence;
   the echo is not.
8. **The game's figure is the judge.** A script's summary is derived;
   INFO, EXP, the stat command or the report line decides. Read it
   fresh after every step (the sheet's snapshot can be hours old).
9. **Stop when a reading contradicts the hypothesis.** Do not spend
   the next step trying to rescue it; record the contradiction and
   re-fit.

## Afterwards

10. **Record in three places, in the same change:**
    - the docs page for the mechanic (docs/*.md): the rule, the
      captured exchange verbatim, the readings, what held and what is
      still assumed — dated;
    - the issue: a table of every step with the prediction and the
      reading, then close it or re-title it as the open question;
    - the fixture: any wording captured for the first time goes into
      the script's test as the real line, replacing the guess.
11. **Name what was not observed.** "That one point alone would not
    have done it was not observed; the arithmetic says so."
12. **Say where the assumption now stands** in the module docstring:
    "held its first test on <date>", never "verified" for a single case.

## Things that bit before

- **Something else moved during the run.** TDPs rose while stats were
  being trained and looked like a training effect; it was a
  recalculation with its own trigger. When a number moves that the
  step should not touch, stop and explain that first.
- **The wiki's formula and the game's arithmetic differ in rounding**:
  compute in integers (10 × ceil(0.4 × …) floated the wiki's own
  example to 490).
- **A quote is cheaper than a trial.** TDP PROJECT, the stat words and
  APPRAISE answer without spending; ask before doing.
- **Names.** Readings carry the operator's characters; the docs and
  fixtures carry the synthetic cast.
