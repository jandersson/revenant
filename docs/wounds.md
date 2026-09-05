# The wound model HEALTH is parsed against

`client/wounds.py` turns a HEALTH answer into wounds by body area, each
with four severities (fresh external, external scar, fresh internal,
internal scar) on a 1–8 scale, plus the bleeding table. Scripts compare
numbers instead of reading the health percentage: `;tend` takes its
bleeders from it, `;hunt` breaks off at the profile's wound floor
(#151). This file records where the wordings come from and what the
captured answers confirmed.

## The scale

| level | name | note |
| --- | --- | --- |
| 1 | insignificant | "faint scuffing", "minor abrasions" |
| 2 | negligible | "tiny scratches", "some tiny scars" |
| 3 | minor | "cuts and bruises", "occasional twitching" |
| 4 | harmful | bleeding starts here; "deep cuts", "constant twitching" |
| 5 | damaging | "deep slashes", "ugly gashes" |
| 6 | severe | "gaping holes", "chunks of flesh missing", "partially paralyzed" |
| 7 | devastating | "shattered", "mangled and malformed" |
| 8 | useless | "a stump", "completely paralyzed" |

Elanthipedia lists thirteen levels for Empaths (the "very harmful",
"very severe" and similar steps) but HEALTH uses one wording for each
pair, so the parser cannot tell "harmful" from "very harmful" and
collapses to the eight levels non-Empaths see. A wording the wiki lists
at two levels ("a constant twitching in the neck" sits at harmful and
damaging) is read as the lower one.

## Where the wordings come from

`client/wounds_data.py` holds every phrase from the wiki's Damage page
tables — head, eyes, neck, chest, abdomen, back, limbs, skin/nerve —
generated verbatim by `tools/wound_tables.py`, 240 rows, placeholders
(`[right/left]`, `[hand/arm/leg/tail]`) expanded by the parser into the
area name ("right arm"). The "(touch)" rows are left out: they carry no
body area and HEALTH never shows them. Regenerate the file when the
wiki changes; never edit it by hand.

The parser matches phrases longest-first anywhere in the "You have …"
sentence, so wordings that contain commas ("a bruised, swollen and
bleeding right eye") survive, and what matches nothing is kept in
`Health.unknown` for `;hunt` to echo as unrecognized.

## What the captures confirmed

Four HEALTH answers from the 2026-08 and 2026-09 sessions are the
fixtures in `client/tests/test_wounds.py`:

- a twelve-wound veteran: every phrase matched a table row, on the
  area and level the wiki gives — external neck at harmful, scars from
  negligible to severe, internal scars from minor to severe, an eye and
  the skin/nerve line included; nothing was left unknown;
- the same character after tending: the bleeding row reads
  `clotted(tended)` and the bleeder rows mark it untendable;
- light scuffs ("some minor abrasions to the head, cuts and bruises
  about the neck …"): HEALTH prefixes "some" where the wiki does not;
  the parser ignores it;
- "You have no significant injuries.": no wounds, no bleeders.

The vitality line ("Your body feels slightly battered") and the spirit
line are kept as text; the wiki gives no table for them.

## Bleeding

The table under "Bleeding" is unchanged from what `;tend` always read:
`[inside] <area>  <rate>`, sides abbreviated (`r. leg`) and spelled out
by the parser, rates ordered as Lich's healing data orders them, with
`(tended)` and `clotted` rows at severity 0. An internal bleeder is a
separate field (`inside_bleeding`) on the same area.
