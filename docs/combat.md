# The combat model automation assumes

Anything in revenant that fights, flees, or watches a fight — the
;athletics danger handling today, hunting scripts tomorrow — leans on
the mechanics recorded here, with their evidence. Canon lives on
[Elanthipedia's Combat 101](https://elanthipedia.play.net/Combat_101)
and [Stance](https://elanthipedia.play.net/Stance) pages — this is not
a mirror, it is what our code believes and why.

## Engagement and range

Three ranges: missile (farthest; outdoor encounters start here), pole
(~8-16 ft), melee (~2-6 ft; all weapon types). Hostiles advance
through them — captured 2026-08-22 (the #72 death log): "The cougar
begins to advance on you!" → "closes to pole weapon range" → "closes
to melee range". The `<crtrStatus hostile disengaged>` tags
(state.hostiles) announce presence *before* the advance — nine
seconds of clean escape window in that capture.

`RETREAT` backs out one range at a time and **can fail**: engaged
opponents hinder it — "You are unable to retreat from a cougar!"
eight times in a row in the death capture, each with ~2s roundtime.
Movement out of the room auto-retreats first and fails the same way.

**The escape recipe** (captured working, 2026-08-22): burst
`retreat` → `retreat` → `<direction>` back to back, riding the game's
type-ahead — "You retreat back to pole range." → "You retreat from
combat." → "You go north." Each retreat steps one range outward
(melee → pole → missile), and **movement and climbing become legal
again at missile range even while the creature stays in the room** —
so success is *the room changing*, not the room emptying (a cave bear
that wouldn't leave pinned the old empty-room check). Full
disengagement, when it happens, announces itself as *"You retreat
from combat"*. Anything slower loses the race: critters re-advance in
the gaps between spaced commands (four single-retreat-then-move
attempts failed against the same cougars minutes earlier). ;athletics
and the shared walker both encode the burst.

## Attacking

`ATTACK <noun>` picks the balance-regaining maneuver automatically;
roundtime scales with the weapon and maneuver. Barehanded works
(brawling). Captured kill line (cougar, 2026-08-22): "The cougar
slowly tips over and falls down." — with a stun beforehand: "A cougar
shakes its head back and forth, its dark eyes befuddled."

**Corpses keep their noun**: after a kill, `ATTACK cougar` resolves
to the body — "The cougar is already quite dead." — while a second,
living cougar closes unmolested (captured: ten wasted swings).
**`SEARCH <corpse>` disposes of it** (confirmed 2026-08-22),
clearing the noun so the next ATTACK finds the living one — the
retarget move for automation. `FACE NEXT` remains an unverified
alternative. "What were you referring to?" means nothing by that
noun remains (searched or decayed).

## Defense

`STANCE SET <evasion> <parry> <shield> (<attack>)`: 180 base
defensive points, conventionally 100/80 in primary and secondary
defenses; Defending ranks add points (1 per 50/60/70 ranks for
armor-primary/secondary/tertiary guilds); attack sacrifices 5:1 into
defense. Parry points auto-convert to shield when a blow can't be
parried. Automation should set a defensive stance before wading in —
not yet encoded anywhere.

## What the scripts do with this

- **;athletics** (#72): hostiles present → break off and escape along
  the training edge, repeatedly; low health → hold; dead → stop.
- **Driving a fight** (session probes, not yet a script): attack
  loop, watch vitals, treat "already quite dead" as a retarget
  signal, stop on the kill line or "What were you referring to?",
  break off under a health floor.
- A proper hunting script would add stance, facing, loot/skinning,
  and multi-opponent policy — none of that exists yet.
