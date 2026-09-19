# The soul model automation assumes

`;soul` (scripts/soul.py, model in client/game/soul.py) keeps a Paladin's soul up and reads it, because the circle-5 glyph quest's orb refuses a soul below pristine and a pool below full, and `;hunt`'s SMITE with an empty pool is what drained it (#217). Canon is [Elanthipedia's Soul system](https://elanthipedia.play.net/Soul_system); this is what our code believes and why, from the readings of 2026-09-18 and 2026-09-19.

## The two numbers

1. **The state**, seven levels read by RUB on a soulstone or the guild's orb, or by walking through a soulstone arch: black and corrupted, cold and lifeless grey, pallid grey, chalky grey, steady white hue, pure white light, pristine luminescence. It drifts down with time but never below chalky grey on its own. `soul.parse_state` reads the level off the phrase; the orb and the tower's arch use the same words ("It fades to a dull, chalky color." / "The archway emits a warm, steady white hue!").
2. **The pool**, eleven levels read by EXHALE, sized by circle, Charisma and the state — so every boost of the state makes the pool read emptier until it refills. Empty is "Nothing special seems to happen." (captured, not on the wiki's list); the second level "You catch the faintest flicker of light." `soul.parse_pool` matches the most specific phrase first because the wiki's lines nest ("briefly flickers" inside "flickers with an inner light").

## The orb's refusal

FOCUS ORB in the Tower of Honor's Orb Room (map 8228) answered "You attempt to focus on the orb, but you feel you need to rest and contemplate a bit first." at chalky grey with the pool empty (2026-09-18) and again at steady white with the pool at 2/11 (2026-09-19). The walkthrough wants "a Pristine Luminescent Soul"; the players' reports add a full pool and a wait after a failure. dr-scripts' paladin-quests.lic knows only "You focus your magical senses" as a refusal and "You clear your mind of all thoughts" as the start, so "rest and contemplate" is read as the pool gate: `ready_for_quest` is pristine and full, and `;soul quest` reads both before it FOCUSes (`force` skips the check, to learn the orb's other answers).

## The deeds and their timers

1. **The tithe**: PUT 5 silver of the town's coin in the almsbox — Dokoras in Shard's Temple of Light, Alcove of Smaragdaus (map 13143, tagged `tithe`); the box's inscription says so and more coins give no more. Captured: "You drop 5 silver dokoras into the almsbox and say a soft prayer as the coins clink in." / "A warm, soothing sensation washes over your soul." One tithe moved the state from chalky grey to steady white hue and the pool from empty to the second level. Timer: four hours (the wiki). The map tags two almsbox rooms; the Crossing's two (outside the temple gate, outside the Paladins' guild) are not tagged, so `almsbox=ID` names one.
2. **The prayer**: PRAY CHADATRU at his altar or statue — the Tower of Honor's chapel (13430), the Crossing temple's Chadatru's Shrine (5845), the rooms the map tags `chadatru`. The first answer, "As you kneel down to pray, you feel your head is not cleared enough to pay proper respect to Chadatru.", is the prayer beginning: stay knelt about 75 seconds for "After clearing your thoughts, you pray deeply toward Chadatru.  A warm, soothing sensation washes over your soul." (captured 2026-09-19 02:34 through `;soul pray`). Hands must be empty. A second try answers "You start to pay respect to Chadatru again when you decide it would be inappropriate so soon.  You decide to wait awhile longer." — at 6, 10 and 74 minutes after the first attempt, and the prayer went through at 120 minutes, so the timer is two hours from the attempt, not dr-scripts' hour; a refusal backs off twenty minutes. The plain prayer (without the circle-50 Glyph of Renewal) is a full step: the orb read "It hums softly and emits a pure white light!" right after it (6/7, from steady white) and the pool "It pulses with an inner light." (6/11, from 2/11 two hours earlier) — so the pool refills within hours, not days.
3. **Not automated**: tending a non-Paladin's wounds and guarding one against a creature (hourly, need a second character), undead kills (random), the instrument and altar rituals that want ranks a circle-5 Paladin lacks.

The timers live in `~/.revenant/soul/<name>.json` (the last acceptance and the last refusal per deed), so a restarted `;soul keep` does not tithe twice.

## What lowers it

The wiki's list, and `;hunt`'s part of it: fleeing combat (the walker's RETREAT burst on the mudflats), and SMITE with an empty pool — one evening of it took the soul from wherever it was to chalky grey and the pool to nothing (#217). A pool reading before each smite is the fix there.

## The quest scene

Unaccepted so far, so the scene's lines are dr-scripts' paladin-quests.lic's: the vision on a wilderness dirt road, the girl's "in a few brief moments she will be past you and beyond help", GUARD GIRL answered "Despite the hopelessness of the situation", and "and use my gift" at the end. `;soul quest` echoes every line so the first accepted run captures them; the other glyph quests are #212's.
