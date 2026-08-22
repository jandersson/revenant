# The circle-requirements model

`;circle` and beholder's Circle-gates view compute what gates the next
circle — the guildleader's answer — locally from the latest `;sheet`
snapshot, using the character's guild requirement table. All eleven
circled guilds are encoded in
[client/client/circles.py](../client/client/circles.py); Commoners
don't circle. This file records the model, the evidence, the wiki
corrections applied, and the open questions, so a future discrepancy
has a dated record of what was believed and why. Canon lives on each
guild's Elanthipedia page (e.g.
[Thief](https://elanthipedia.play.net/Thief)) — this is not a mirror.

## The model

A requirement is either a **named skill** (Thievery, Parry Ability,
Inner Fire, Trading, ...) or a **slot** — "3rd Survival" is your
third-best survival skill, whatever it is. Ranks required to advance
TO circle C are the per-circle rates summed across the tables' circle
bands (1-10, 11-30, 31-70, 71-100, 101-150, 151+) up to C; every
encoding is validated by re-deriving the wiki's own Cumulative column
in [test_circles.py](../client/tests/test_circles.py) (checkpoints
10/30/70/100; Thief through 200).

Slots fill best-first by (rank, percent). A guild's named skills stay
out of its slots unless the wiki marks them **soft**: Thief (Thievery,
Stealth), Bard (Tactics), Cleric (Attunement), Empath
(Outdoorsmanship), Necromancer (Targeted Magic), Paladin (Shield
Usage, Tactics, Scholarship), Ranger (Instinct). The captured Thief
guildleader answer confirms the mechanic (Stealth sat in a survival
slot while its named requirement was met). Barbarian's Primary Mastery
is a slot over the two Mastery skills.

Assumptions not directly stated by the wiki:

- Parry Ability, Expertise, and the Masteries never fill Nth-Weapon
  slots; armor slots draw from Light and Heavy Armor, never Defending,
  Shield Usage, or Conviction (those appear only as named rows in
  every guild's table).
- Equal-rank ties: our order (percent, then name) can differ from the
  game's slot labels; the *set* of unmet requirements is unaffected.
- Barbarian's single lore slot is labeled "2nd Lore" in the wiki's
  rate table but "1st Lore" in its cumulative table; encoded as the
  best-other-lore slot ("1st Lore").

## Evidence

- **Captured `ASK KALAG ABOUT CIRCLE`, 2026-08-22** (Thief, circle 1
  → 2), against the same day's captured `EXP ALL` roster: the
  computation reproduces the guildleader's list gate for gate,
  including named-Stealth met at exactly 4 ranks while
  Stealth-as-survival-slot gated, and three requirements each unmet
  by exactly one rank.
- **Each guild's Cumulative column** re-derives from the encoded
  rates. Necromancer and Ranger publish no cumulative table — their
  transcriptions carry no cross-check.

## Wiki corrections applied

Where a guild's rate table and its cumulative column disagree, the
value consistent across the most checkpoints wins:

- **Thief**: 2nd Magic cumulative at circle 100 reads 130; the rates
  and the 150 value (340 = 140 + 4×50) prove 140.
- **Barbarian**: 2nd Armor band 11-30 reads 2/circle; three
  checkpoints prove 1. 3rd and 4th Survival band 31-70 read 2/circle;
  the checkpoints prove 1.5. The "Total Magic" cumulative row
  miscounts its own rows by 10.
- **Cleric**: 3rd Magic band 31-70 reads 4/circle; three checkpoints
  prove 3.

## Open questions

- **2nd Lore at Thief circle 2**: the wiki rate (1/circle → 2 ranks)
  says the captured roster's second-best lore should have been
  listed; the guildleader named only 3rd Lore. `;circle` may
  over-report that one slot around circle 2. The next few circles
  discriminate — compare the guildleader's answer at circle 3.
- **High-band incoherencies**: a few rows admit no per-circle rate
  between the wiki's own checkpoints — Barbarian Expertise and Bard
  4th Magic across 71-100, Bard 2nd Lore across 101-150. Rates are
  encoded as printed and validation stops before the incoherent
  band for those rows; expect small errors there until a capture
  settles them.
