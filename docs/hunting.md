# The hunting model ;hunt assumes

`;hunt` fights a ground in a loop from a per-character profile: walk
there, ready weapon and stance, attack until the room empties, skin and
search each kill, move along the ground, come home on a limit. This
file records what the script believes about the game and which of it
is captured versus assumed — the fixtures in `client/tests/test_hunt.py`
pin the same wordings. The fight itself follows [combat.md](combat.md).

## The profile

One JSON file per character, `~/.revenant/profiles/<name>.json`, edited
from File → Character Profile… (the dialog builds itself from
`client/profile.py`'s FIELDS, so the file and the form never disagree).
It holds what no script should hard-code:

| setting | what the loop does with it |
| --- | --- |
| hunting_ground | a `;go2` target; every room it resolves to is the ground, walked to at the start and cycled when a room runs empty |
| prey | the noun ATTACK gets; empty swings at whatever engages you |
| home | a `;go2` target walked to when the hunt ends |
| weapon, weapon_container | `GET my <weapon> [FROM my <container>]` before the first swing, `PUT` it back on coming home |
| stance | `STANCE SET <args>` once, before the first swing |
| skin, skin_knife | `SKIN <corpse>` after each kill; a named knife is fetched before and stowed after |
| loot_container | where skins and non-gem finds go (`PUT my <item> IN my <container>`, else `STOW my <item>`) |
| gem_pouch | finds are tried into the pouch first; what the pouch refuses is stowed like loot |
| health_floor | below it: the burst escape (retreat, retreat, first exit), then home |
| wound_floor | a severity name; HEALTH is asked after each kill and whenever the health bar drops, and a wound that bad or worse anywhere (external, scar, internal, internal scar) breaks off like the health floor. Empty never asks. Model: [wounds.md](wounds.md) |
| train_skills | the hunt ends when every one of them sits at mindstate 34 in the exp window |
| max_kills | a fuse; 0 hunts until stopped, locked or the ground empties |

`;hunt stop` (typed while it runs) ends the loop before the next swing.
`;hunt here` skips the walk to the ground; `;hunt profile` prints the
profile it would use.

## What is captured and what is assumed

Captured (the 2026-08-22 traffic behind combat.md, and the first live
`;hunt` on 2026-09-05 — a circle-1 Paladin against ship's rats at
Barana's Shipyard):

- the kill lines "The cougar slowly tips over and falls down." and
  "The ship's rat falls to the ground and lies still." — the corpse
  noun is the word before the kill phrase ("rat"). The first run knew
  only the cougar wording, missed the rat's kill and never skinned;
- "The ship's rat is already quite dead." — a corpse soaking swings,
  which the loop disposes of (skin, search) like a fresh kill, and
  after two more such answers declares the room clear; the noun can
  be several words;
- the corpse's `<crtrStatus>` keeps `hostile="1"` and adds `dead="1"`
  — the parser now drops it from the hostile set, which is what let
  the first run swing at the body five times;
- "There is nothing else to face!  What are you trying to attack?" —
  the room is clear even while the hostile state lags;
- SEARCH <corpse> removes it and clears the noun.

Assumed, pending capture (each one is a keyword table in the script,
and any answer outside the table is echoed as
`hunt: unrecognized ...` so it can be reported and pinned):

- the other kill wordings ("goes still", "collapses", "keels over");
- the skinning answers — success is read as "obtain…" / "you skin",
  and the produced item's noun is the last word of "obtaining a rat
  pelt"; "nothing to skin with" / "bare hands" turns skinning off for
  the run; "ruin" / "botch" counts as a failed skin;
- the search answers — "You find …" names what turned up, "find
  nothing" / "nothing of value" is an empty corpse;
- that a searched-up item must be picked up (`GET <item>`) before it
  can be pouched or stowed, and that a pouch refuses non-gems with a
  "can't" wording;
- that the skin lands in the free hand, so `STOW LEFT` is the fallback
  when the answer names no item.

Rats at Barana's Shipyard (the first-cut ground, map tag `rats`, rooms
6046–6054) are level-1 creatures with no loot; their skins are a rat
pelt, tail or bones (Elanthipedia: Rat). SKIN wants an edged weapon in
hand or a worn belt knife (Elanthipedia: Skinning) — a handaxe does.
The gem pouch page describes `FILL POUCH WITH <container>` for bulk
moves; the loop pouches one find at a time instead.

## Out of scope in the first cut

Magic and ranged attacks, a policy for several opponents at once,
selling skins and gems, and buying arrows or ammunition. Each is a
profile setting and a branch away, once captures show the wordings.
