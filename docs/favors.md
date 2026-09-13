# The favor model automation assumes

`;favors` (scripts/favors.py) automates the favor-orb run so a death is
never a zero-favor DEPART — the 2026-08-22 death (10% health, nothing
to spend, #82) is the motivating capture. Canon lives on
[Elanthipedia's Favors page](https://elanthipedia.play.net/Favors) and
[Immortals page](https://elanthipedia.play.net/Immortals) — this is not
a mirror, it is what our code believes and why.

## The run (Zoluren)

0. **An orb already yours comes first.** The script checks the
   parser's hand state for an orb (nothing sent) and, once the pool is
   worth a run and a hand is free, tries GET MY ORB for one in a
   container; with an orb in hand it skips the prayer
   and finishes that orb — the puzzles if it cannot locate a mapped
   room, then the creche — since beyond two orbs fed experience is
   wasted and a second prayer would only add one (the operator,
   2026-09-13). "What were you referring to?" means none.
1. **The Stone Grotto** at the Siergelde ruins west of Crossing — map
   room 1420, `[Siergelde, Stone Grotto]`. The game's own `DIR FAVOR`
   gives step-by-step directions; we walk with the shared walker
   (docs/movement.md) instead.
2. **The ritual**: KNEEL → PRAY ×3 → SAY a *neutral* aspect of the
   Thirteen → STAND → GET ORB ON ALTAR. The thirteen neutral names
   (aspect table read from the raw wiki HTML 2026-08-22, after two
   summarized fetches garbled the columns): Chadatru, Damaris, Eluned,
   Everild, Faenella, Glythtide, Hav'roth, Hodierna, Kertigen, Meraud,
   Tamsine, Truffenyi, Urrem'tier. Light and dark aspects are not part
   of the general-altar ritual; the script validates its argument
   against this list (default Truffenyi, patron of the common folk).
3. **The puzzles**: taking the orb opens an arch and trees. GO ARCH is
   the easier series, GO TREES the harder. Rooms pose small tasks —
   the two documented spoilers: GET SPONGE / CLEAN ALTAR WITH SPONGE,
   and GET TINDER / LIGHT CANDLE, each followed by GO STAIR and GO
   DOOR. Puzzle count grows with favors already held (near zero for
   our audience); solving them returns you to the grotto. DROP MY ORB
   abandons: the orb is destroyed and you are teleported out. The
   script solves the rooms it knows from the room's LOOK — captured
   2026-09-13 at zero favors, one room: `[Siergelde, Labyrinth]`, "a
   plant upon the table looks as though it is slowly choking to death
   in the heat", solved by OPEN WINDOW three times ("you shimmy the
   frame ... a thin crack", "loosen it even further", "hoist it upward
   ... slides open", then "That is already open.") and GO WINDOW ("You
   hoist yourself off the floor and manage to swing yourself through
   the open window." / "You feel giddy all over and you grin widely as
   everything about you disappears and you suddenly find yourself
   transported to..." — the grotto), and the empty vase (the second
   favor: "A peaceful grotto ... swathed in hedges of oleander and
   nutflower ... a simple white altar hewn of shimmering marble ...
   a vase on top of the altar", solved by GET NUTFLOWER alone — "You
   carefully pick some of the nutflower blossoms and arrange them
   neatly in the vase.", again "You have already filled the vase to
   overflowing." — and GO PATH: "Having filled the vase with flowers,
   you stride along the branching path toward the copse of juniper
   trees." then the teleport; with the orb and a weapon in hand the
   game says "You must clear one of your hands first.", so the script
   stows whatever is not the orb before a puzzle), and the empty font
   (the third favor: "Two fiery braziers stand astride a steep stone
   stairway which leads to a massive iron door ... a granite altar
   with several candles and a water jug on it, and a granite font";
   the font "is empty. Something in the back of your mind tells you
   this doesn't seem right."; GET JUG "You reverently take the jug
   from the altar.", POUR JUG IN FONT "You carefully carry the earthen
   jug to the font and pour the water out. The soft scent of lilac
   rises from the filled basin ..." and the jug is gone, GO STAIR "You
   reach the top of the stairway, and notice that the door has swung
   open of its own accord!", GO DOOR "You step gleefully through the
   door ..." then the teleport); the sponge and tinder rooms are the
   wiki's spoilers, uncaptured — and hands a room it does not
   know (levers) to the human, resuming when it can locate a mapped
   room with a path to the temple.
4. **Filling**: the orb's sacrifice is the unabsorbed experience pool
   (favors held plus circles size the requirement; favors dominate).
   RUB MY ORB drains a little per rub; HUG MY ORB dumps the whole
   unabsorbed pool at once — the script rubs, so nothing beyond the
   orb's need is spent. Fill stages read on LOOK: "glows faintly and
   wavers slightly" → "glows faintly" → "glows a pale (color),
   wavering slightly" → "glows a steady pale (color)" → "glows strong
   (color), wavering slightly" → "glows a strong and steady (color)";
   a Thief's orb is violet. The full signal on RUB/HUG is wiki-quoted:
   **"You sense that your sacrifice is properly prepared"**.
5. **The offer**: Crossing's resurrection altar, map room 5865,
   `[Resurrection Creche, Li Stil rae Kwego ia Kweld]`. Resurrection
   altars accept any Immortal's orb (immortal-specific altars accept
   only their own). PUT MY ORB ON ALTAR; success is wiki-quoted: "the
   multicolored lights gather around you ... the light fades and you
   feel somehow changed." FAVOR then reports the count.

## Orb handling rules (Elanthipedia)

- Carry at most two unfilled orbs; experience fed into a third is
  wasted outright.
- Orbs left off your person shatter (after a glow, then an
  accelerating pulse, warning) — the script never stows the orb, and
  its failure guidance says keep it on you.
- Orbs never leak experience; perceived "leakage" is the orb resizing
  when the favor count changes between rubs.

## Unknowns an attended run must capture (#82)

Everything the classifier trusts beyond the wiki-quoted lines is a
keyword guess; unrecognized answers echo as `favors: unrecognized ...`
and become fixtures:

- The grotto prayer wordings (kneel/pray/say/stand responses) and the
  get-orb success line.
- The arch/trees appearance line, and the sponge and tinder rooms'
  wordings (the choking plant's are captured above).
- Rub progress wordings as RUB reports them (the staged wordings above
  are LOOK's), and the empty-pool refusal, if the game words one.
- The altar's refusal of an unfilled orb, and the FAVOR count line.
