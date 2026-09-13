# The death model automation assumes

`;deathwatch` (scripts/deathwatch.py) logs an unattended corpse out
after a rescue grace, before it decays, so the body keeps for a raise
at the next login (`;deathwatch depart` departs instead) — dying AFK
must never again cost a character their belongings. Canon lives on
Elanthipedia's Death and Depart command
pages; the sharpest facts here are captured from a real death
(2026-08-22, the 16:04 session log).

## The clock

- Death announces its own deadline: *"Your body will decay beyond its
  ability to hold your soul in 21 minutes."* (captured; the wiki ties
  the window's length to spirit and charisma). ;deathwatch parses
  this line and keeps its rescue grace inside the window, with a
  five-minute safety margin.
- **The clock does NOT run offline.** This file said the opposite
  until 2026-09-13, misreading its own capture: the 2026-08-22 death
  (a 21-minute window announced at 16:04) ended in an idle disconnect,
  and the *same character's* next login at 18:52 — two and a half
  hours later — opened with "[You are dead.]" and "You are a ghost!",
  the body still there, before a DEPART ("You feel yourself lifted
  gently, cradled as if by a mother's hand."). The 17:07 login in
  between was another character. A dead character who logs out keeps
  the body until the next login, as the operator remembers the game
  always working. ;deathwatch's "depart rather than quit" rationale
  rested on the misreading. Decided 2026-09-13 (#186): the watch QUITs
  at the grace — the game accepts QUIT while dead — and the body waits
  for a raise at the next login; `;deathwatch depart` keeps the old
  ending for whoever wants it.

## The DEAD indicator

- The game states an indicator only when it flips — nothing ever
  re-announces DEAD to a process that missed the death, and a ghost's
  LOOK earns only the ghost refusal, no XML. Captured 2026-08-23
  (#92): a `;reexec` mid-death armed a fresh deathwatch that stayed
  blind while the decay clock ran. The session therefore hands its
  indicator state across the exec (`REVENANT_GAME_STATE`), and a
  watch that starts against an already-dead state begins its
  countdown immediately.
- Fresh logins need no handoff: the login stream states every
  indicator (`client/tests/login-sample.log`).

## While dead

- Commands answer: *"You are a ghost!  You must wait until someone
  resurrects you, or you decay.  Either way, it won't be long now!"*
  (captured). The refusal still counts as activity for the idle
  check.
- Spirit drains audibly: *"A chill crosses the surface of your soul
  as your remaining spiritual strength bleeds away steadily."* — and
  at zero favors: *"You feel the eyes of the gods upon you and
  realize that none look upon you with favor."* (both captured).

## Departing (Elanthipedia "Depart command")

| variant      | favors | keeps                       |
| ------------ | ------ | --------------------------- |
| DEPART FULL  | 3      | items and coins             |
| DEPART ITEMS | 2      | items (coins lost)          |
| DEPART COINS | 2      | coins (items to a grave)    |
| DEPART GRAVE | 1      | items go to a grave         |
| DEPART       | 0      | maximum penalties           |

`;deathwatch depart` walks the ladder best-variant-first and judges
each attempt by the DEAD indicator actually clearing — no refusal
wording ever needs to be known; the default ending is a QUIT, which
spends nothing. Favors are the fuel: ;favors (docs/favors.md)
is how a character keeps at least three banked.

## Open anomaly

The captured zero-favor decay-depart came back with **inventory
intact and no grave**, where the wiki promises maximum penalties.
Either the wiki is stale or departing-by-decay differs from a
voluntary DEPART. Until a capture settles it, the code assumes the
wiki's pessimistic model and always prefers the best affordable
variant.

## Bleeding

`;tend` bandages every tendable bleeder, worst first, and its watch
mode re-tends the moment bandages soak through ("The bandages
binding your neck soak through with blood..." — captured live).
Internal bleeders need hundreds of First Aid ranks and are left for
magic; the tests in `client/tests/test_tend.py` are the manual.
