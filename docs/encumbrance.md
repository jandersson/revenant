# Encumbrance: what a burden level says about the load

The game shows a burden level, not a weight, and Elanthipedia's
[Encumbrance](https://elanthipedia.play.net/Encumbrance) page gives
the rule that ties the two, so a level plus Strength and Stamina is a
band of weights and the points that would lighten it are a small
range. `;enc` does that arithmetic, and `;enc ballast` pins the load
by adding coins of known weight until the level rises. The formula
is the wiki's, from a pre-DR3 page, and it held when tested on
2026-09-12: two ballast runs pinned a load, the rule said two points
would lighten it, and two points did.

## The rule

Number the levels 1 to 12 — None, Light Burden, Somewhat Burdened,
Burdened, Heavy Burden, Very Heavy Burden, Overburdened, Very
Overburdened, Extremely Overburdened, Tottering Under Burden, "Are
you even able to move?", "It's amazing you aren't squashed!". At
level *L* a character carries up to

    10 × ceil(0.4 × (L + 5) × (Strength + Stamina)) stones

(the wiki's example: 10 Strength and 10 Stamina carry 480 stones with
none). Strength and Stamina count alike, there are no racial terms,
and a coin of any metal weighs 0.2 stones. The wiki also notes the
"armor anomaly": worn armor burdens less than the same armor carried
in a container.

## The captured case

2026-09-12, a circle-1 Dwarf Paladin at Strength 10 and Stamina 11,
wearing light full plate, gauntlets and an armet with the greaves in
hand and a sack holding a mask, vambraces, a leather jacket and a
handaxe: `Encumbrance : Very Heavy Burden`. By the rule that is a
load over 840 and up to 930 stones, and Heavy Burden holds up to
40 × (Strength + Stamina): 880 at 22, 920 at 23, 960 at 24. So one
to three points of either stat would lighten him, and which depends
on where in the band the load sits. Stamina was the cheaper point
for him (28 TDPs against 30, the Dwarf's discount), and each point
widens every band the same.

## The ballast result

Two runs the same day, at the Crossing teller. With 50-stone steps,
250 copper coins tipped him from Very Heavy Burden to Overburdened at
once: a load over 880 and up to 930 stones. With 10-stone steps, 10,
20 and 30 stones changed nothing and 40 stones (200 coins) tipped him:
a load over 890 and up to 900 stones. The runs agree, the teller
hands over and takes back exactly the count named, and ENCUMBRANCE
answered each time within seconds. By the rule, Heavy Burden holds
880 stones at 22 combined points and 920 at 23, so the prediction was
that two points of Strength or Stamina make him Heavy Burden. `;tdp
train stamina +2` took Stamina 11 → 13, and `;enc` read Heavy Burden:
the rule holds. That one point alone would not have done it was not
observed (both were bought in one run); the arithmetic says so.

## The vault readings: what a stowed jacket costs

Later the same day, at Strength 10 + Stamina 13 (bands: None to 560,
Light 561-650, Somewhat 651-740, Burdened 741-830, Heavy 831-920), the
character walked into his vault carrying the boiled leather jacket in
one hand and the light plate greaves in the other, the sack holding a
map, a tunic and a handaxe. The last reading before that, with the
jacket still in the sack, was Heavy Burden pinned to 870-920 stones.

```
You put your jacket on the wire rack which is inside a secure vault.
  Encumbrance : Light Burden
You put your greaves on the wire rack which is inside a secure vault.
  Encumbrance : None
```

By the rule the jacket's departure took at least 221 stones off the
load (from over 870 to at most 650), and the greaves' at least one
(the wiki gives light plate greaves 101 stones, light full plate 500).
A plain leather jacket is 150 stones on the wiki; a boiled one has no
page. So either this jacket weighs over 220 stones, or a piece of
armor carried rather than worn burdens more than its weight — the
"armor anomaly" the wiki describes without numbers. The two are not
separable from these readings: between the pinned reading and the
vault the jacket moved from the sack to the hand with no reading in
between. The experiment that separates them is one item read in three
states — in hand, worn, in the sack — with the level after each, and
ballast at the teller if the levels alone do not settle it.

## The experiment

`;enc ballast` at a teller withdraws coins in steps (50 stones, 250
coins, by default), asks ENCUMBRANCE after each, and stops at the
first step that lifts the level. The load then weighs over
`ceiling − ballast` and up to `ceiling − ballast + step`, where the
ceiling is the band's upper edge; a smaller `step=` narrows it. Every
step is a row in history.db's `encumbrance` table, the coins are
copper so the count drawn is the count carried, they go back with
DEPOSIT step by step, and the script says exactly
how many points would drop the level at each end of the pinned range.
Training that many (`;tdp train stamina +2`) and reading `;enc` again
is the check on the formula, and the first case passed it.
