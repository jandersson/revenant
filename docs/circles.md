# The circle-requirements model

`;circle` computes what gates the next circle — the guildleader's
answer — locally from the latest `;sheet` snapshot, using the guild's
requirement table. This file records the encoded table, its evidence,
and the open questions, so a future discrepancy has a dated record of
what was believed and why. Canon lives on [Elanthipedia's Thief
page](https://elanthipedia.play.net/Thief) — this is not a mirror.
Only Thief is encoded so far
([client/client/circles.py](../client/client/circles.py)).

## The model

A requirement is either a **named skill** (Thievery, Stealth, Parry
Ability, Inner Magic) or a **slot** — "3rd Survival" is your
third-best survival skill, whatever it is. Ranks required to advance
TO circle C are the per-circle rates summed across the table's circle
bands (1-10, 11-30, 31-70, 71-100, 101-150, 150+) up to C; the
encoding is validated by re-deriving the wiki's own Cumulative column
in [test_circles.py](../client/tests/test_circles.py).

Slots fill best-first by (rank, percent). Thievery and Stealth are
*soft requirements* — the wiki's footnote — so they also count toward
survival slots; the captured guildleader answer below confirms it
(Stealth sat in a survival slot while its named requirement was met).

Assumptions not directly stated by the wiki:

- Parry Ability, Melee/Missile Mastery, and Inner Magic never fill
  Nth-Weapon/Magic slots (they are named or mastery skills).
- Armor slots draw from Light and Heavy Armor, not Defending or
  Shield Usage. Untestable at this circle — flagged for a future
  capture.
- Equal-rank ties: our order (percent, then name) can differ from the
  game's slot labels (the capture ordered Stealth before Locksmithing
  at 4 ranks / 0% both, and put Scholarship 3rd of the 1-rank lores).
  The *set* of unmet requirements is unaffected — only which tied
  skill wears which label.

## Evidence

- **Captured `ASK KALAG ABOUT CIRCLE`, 2026-08-22** (circle 1,
  advancing to 2), against the same day's captured `EXP ALL` roster:
  the computation reproduces the guildleader's list gate for gate —
  1st Armor, 1st Weapon + Parry, 1st Supernatural + Inner Magic, the
  2nd–8th Survival slots + named Thievery, 3rd Lore — including the
  fine points: named Stealth met at exactly 4 ranks while
  Stealth-as-survival-slot (needing 8) gated, and 8th Survival/Parry/
  Inner Magic each unmet by exactly one rank.
- **The wiki's Cumulative column** re-derives from the encoded rates
  at every checkpoint (circles 10/30/70/100/150/200) — with one wiki
  typo found: 2nd Magic at circle 100 reads 130 there, but the rates
  and the 150 value (340 = 140 + 4×50) prove 140.

## Open anomaly: 2nd Lore

The wiki's 2nd-Lore rate (1/circle → 2 ranks toward circle 2) says
the captured roster's second-best lore (1 rank) should have been
listed; the guildleader named only 3rd Lore. Either the wiki's
2nd-Lore rate is wrong at low circles or the game special-cases
something we can't see yet. `;circle` therefore may over-report a
lore gate by one slot around circle 2. The next few circles
discriminate: at circle 3 the model predicts 2nd Lore needs 3 ranks —
compare the guildleader's answer then and update the table (or this
note) with that capture.
