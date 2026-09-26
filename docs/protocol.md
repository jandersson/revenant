# The wire protocol the parser reads

DragonRealms speaks the Simutronics XML-ish frontend protocol, and this
file is the reference `client/engine/xml_data.py` implements against: what each
tag means, which stream ids DR actually sends, and where our parser
stops. The authority for the tag grammar is the GemStone IV wiki's
[Wrayth protocol](https://gswiki.play.net/Wrayth_protocol) page —
Wrayth is the frontend both games share, which is why the DR login
handshake reports `FULLGAMENAME=Wrayth`. Elanthipedia does not document
it at all.

The catch: that page is written for GemStone, and the two games do not
send the same streams. Everything below marked *(captured)* is derived
from our own logs in `~/.revenant/logs/`, not from the wiki, and where
the two disagree the captured traffic wins.

The stream is not well-formed XML — tags arrive unclosed, interleaved
with plain text, and split across lines. Treat it as a line protocol
with tags in it, never as a document.

## Two passes over every line

Reading the stream is split in two, and the split matters when you go
looking for a bug:

- **`XMLData.start`/`end`/`data`** — the XMLParser target that
  accumulates *game state*: indicators, compass, prompt, vitals,
  hostiles, the exp components. Fed the raw stream.
- **`XMLData.route(line)`** — *display* segmentation, independent of the
  parser target. It splits one line into `(stream, text, style)` pieces
  by the pushStream/popStream markers and the styling markers, then
  strips whatever tags remain (`re.sub(r"<[^>]+>", "", piece)`).

A tag can therefore be understood by one pass and invisible to the
other. `component` is parsed for state *and* stripped from display;
`resource` is stripped by both.

## Streams

`pushStream id="x"` routes following text to stream `x` until
`popStream`. Text outside any push belongs to `main`. Stream ids are
case-sensitive (`percWindow`, not `percwindow`).

`streamWindow` declares or re-titles a stream's window.
`resident='true'` means the client persists it across sessions.
`ifClosed` decides where the text goes when the window is closed:
absent with `styleIfClosed` set falls through to main wrapped in that
style; `ifClosed='<other id>'` reroutes to another window;
`ifClosed=''` means the server also sends the content to main, so the
closed window's copy can be dropped harmlessly; both absent falls
through to main unstyled.

`clearStream id="x"` empties stream `x`'s window before fresh content
lands. **The `id` is the whole point** — a clear names one stream and
may only wipe that stream's own window. A clear for a stream the
frontend gives no window must be *dropped*, never applied to the main
window; doing the latter blanked the story pane on every GET/PUT/STOW
(#109, `client/ui/streamroute.py`).

### Stream ids in DR *(captured)*

Declared by `streamWindow`, across every log we have:

`assess` `atmospherics` `combat` `conversation` `death` `experience`
`familiar` `group` `inv` `logons` `main` `ooc` `percWindow` `room`
`talk` `thoughts` `whispers`

`percWindow` is **not** in the gswiki list — it is DR's own. Do not
treat that page's stream table as complete for this game.

Actually used, by `pushStream` volume:

| stream | pushes | what it carries |
| --- | ---: | --- |
| `combat` | 1189 | combat messaging — by far the loudest stream |
| `logons` | 63 | arrivals and departures |
| `death` | 44 | death announcements |
| `atmospherics` | 40 | ambient room flavor |
| `inv` | 34 | the worn-items rewrite |
| `talk` | 26 | conversation |
| `room` | 16 | room content |
| `experience` | 16 | the EXP window |

Only four streams ever issue a clear: `experience`, `inv`, `percWindow`,
`room`. Of those the GUI docks exactly one (`percWindow` → Spells), so
the other three must be no-ops — that is the whole of #109.

Note `room` collides with the engine's *synthetic* `"room"` frame
(`uid<TAB>title`, emitted by `core.py` per room change, which the map
dock follows). They are different things sharing a name: the game's
`room` stream carries room text, ours carries a room identity. The
dispatch answers a clear before the synthetic-stream branches so the
game's clear never reaches the map dock as an empty room.

## Text styling

Segments come out of `route` carrying a style string: `""` for plain,
a style name the GUI maps to colors, the control value `"clear"`, or
`"link:<command>"` for a command link.

- `pushBold` / `popBold` — bracket emphasized text (monster names,
  alerts). No attributes.
- `preset id="x"` — user-configurable color for a category. *(captured:
  `roomDesc`, `speech`, `whisper`.)*
- `style id="x"` — opens a named style; an empty `id` closes it.
  *(captured: `roomName` only.)*
- `output class="mono"` — switches to monospace, empty class switches
  back. *(captured: 295 occurrences; we ignore it.)*
- `<d cmd="...">text</d>` — a clickable command link. With no `cmd`,
  the tag's own contents are the command. The GUI renders these as
  links that send on click.

## State tags

- `prompt time="<epoch>"` — the prompt. Its `time` is the server clock,
  and the basis of the `timesync` frame that keeps Elanthian time
  immune to local drift (#102, docs/eltime.md).
- `roundTime value="<epoch>"` / `castTime` — timer **end times**, not
  durations. Remaining = `value − prompt time`. Both absolute.
- `indicator id="..." visible="y|n"` — boolean status. *(captured:
  `IconBLEEDING` `IconDEAD` `IconHIDDEN` `IconINVISIBLE` `IconJOINED`
  `IconKNEELING` `IconPRONE` `IconSITTING` `IconSTANDING` `IconSTUNNED`
  `IconWEBBED`.)* The game announces these only on **change**, which is
  why a standing fact like DEAD has to ride across `;reexec` (#92).
- `app char="..." game="..." title="..."` — names the logged-in
  character. Sent **once**, at login, never repeated (#95).
- `nav rm="<uid>"` — the room's unique id, and the exact fix for
  locating on the community map. Titles collide; uids do not
  (docs/movement.md).
- `dialogData` / `progressBar` — dialog controls merged by control id.
  We read only the `minivitals` dialog, whose bars are `health`,
  `mana`, `spirit`, `stamina` (DR labels stamina as "fatigue").
- `crtrStatus` — creature status; `hostile="1"` is what the hostiles
  list keys on.
- `compass` / `dir` — the room's exits, the basis of the synthetic
  `compass` frame scripts treat as the room-arrival signal.
- `mode id="GAME|LOGIN|CMGR"` — announced at login.

## Components

`compDef id="x"` replaces a named part wholesale; `component id="x"`
updates it incrementally. Both are heavily used *(captured: 1008
compDefs)*.

Room parts: `room desc`, `room exits`, `room extra`, `room objs`,
`room players`, and `room creatures` — the last appears **only** as a
`compDef`, never as a `component`.

The exp window is delivered the same way, one component per learning
skill: `exp <Skill>` (`exp Lunar Magic`, `exp Athletics`, …), plus
`exp favor`, `exp rexp`, `exp sleep`, `exp tdp`. *(captured: 57
distinct skill components across our logs — that is what these
characters have seen, not a guarantee of DR's full skill list.)* `xml_data.py` parses these into `experience`
(rank/percent/mindstate); `core.py` rewrites the synthetic `exp` stream
on change, and `scripts/xp.py` snapshots it to `~/.revenant/history.db`
(docs/experience.md).

## What DR sends that we ignore

Present in captured traffic, parsed by neither pass — listed so the next
feature knows the data is already on the wire:

| tag | count | what it offers |
| --- | ---: | --- |
| `resource picture="..."` | 3517 | room artwork selection |
| `output class="mono"` | 295 | monospace switching |
| `mode` | 32 | login/game mode transitions |
| `clearContainer` / `exposeContainer` | 2 each | container windows — `exposeContainer` fires on OPEN |

`compDef`, `right`, `left`, `spell`, `inv` and `prompt` are stripped as
paired tags in `route` rather than parsed for display. `right` and
`left` carry what each hand holds — `<left exist="45793296"
noun="handaxe">oak-hafted handaxe</left>`, `<left>Empty</left>` —
one tag per hand as that hand changes, a pair at login (captured
2026-09-11); the parser keeps them as `left_hand` / `right_hand`
(`{noun, exist, name}` or None) with a `hands_updated` flag, so scripts
can read what is held (the climb log, #159) — no hands indicator draws
them yet.

`<dialogData id="injuries">` is the injuries panel: one `<image
id="<part>" name="...">` per body part — head, neck, rightArm,
leftArm, rightLeg, leftLeg, rightHand, leftHand, chest, abdomen, back,
rightEye, leftEye, rightFoot, nsys (the nervous system) — plus a
`health2` progress bar and two skins. The name is the gauge: the
part's own id when clean (`name="head"`), `Injury<N>` when wounded
(captured 2026-09-11: every limb and the trunk at `Injury1` after two
falls, all back to their own names in the pulse the Empath's touch
sent — #163); `Scar<N>` is the pattern's assumption for scars. The
parser keeps it as `injuries` ({part: (kind, level)}), the engine
emits an `injuries` frame ("head wound 1 chest wound 1", "" when
clean) on every change and states it fresh to late attachers, and
the Injuries dock draws it. It is coarser than HEALTH's wording
(docs/wounds.md) and never needs asking.

## Gotchas

- **Absolute, not relative.** Every timer is an epoch end time. Never
  treat `roundTime value` as seconds remaining.
- **Change-only.** Indicators and the `app` tag are announced on change
  or once; a parser started mid-session cannot learn them by waiting.
  This is why `;reexec` hands state across (`REVENANT_GAME_STATE`).
- **A clear is stream-exclusive.** See #109 above. Text falls back to
  main; the clear control does not.
- **Case-sensitive ids.** `percWindow`.
- **Not XML.** Tags arrive unclosed and interleaved with prose. Both
  passes are regex- and target-based for this reason, and a change that
  assumes well-formedness will break on live traffic.

Fixtures live in `client/tests/` — captured traffic is how this file's
claims stay checkable. A fixture that turns out wrong is an assumption
to correct, not a test to delete.

## The state in words

Scripts do not read the tags: `client/game/status.py` wraps the
parser's fields as a live view — `status(s.state)` or `s.status` —
with the posture as one word (standing, kneeling, sitting, prone), the
badges as booleans (dead, stunned, bleeding, webbed, hidden, invisible,
joined), the hands as nouns, the vitals and injuries as dicts, the
roundtime and casttime as seconds left by the game's own clock, the
exp window as mindstates, and a one-line `summary()` that `;status`
prints. It is Lich's `stunned?` / `hidden?` / `checkprone` idiom over
this parser's state; every value is derived on access, so a view taken
once stays current.

## Spell tags

`<spell>Heroic Strength</spell>` names the prepared spell and
`<spell>None</spell>` follows the cast; the parser keeps it as
`prepared_spell`. The Spells window is rewritten on every pulse:
`<clearStream id="percWindow"/>` on its own line, then
`<pushStream id="percWindow"/>Heroic Strength  (10 roisaen)` — one
line per running spell, the time left in parentheses, a roisan being
a real minute — and `<popStream/>` on the next line, often followed by
`<castTime .../>`. A clear with no push after it means nothing is
running. The parser keeps the window as `active_spells`
({name: minutes left, or None for a count it cannot read}). Captured
2026-09-12.

## The room's players

`<component id='room players'>Also here: Sky Knight Kaldean who is
darkened by an unnatural shadow, Sand Flower Cyranth, Cecil and
Penello.</component>` comes with every room and on every change, empty
(`<component id='room players'></component>`) when nobody else is
there. Entries are split on commas and a final "and"; a title stands
before the name and a " who is ..." state after it, so the name is the
last word before that. The parser keeps the names as `room_players`.
Captured 2026-09-12.

## Inventory links carry the exist ids

INV LIST answers in the main stream with one command link per item:
`<d cmd='remove #53174575'>a lumpy bundle</d>` for a worn item,
`     -<d cmd='get #50886622 in #53174575'>a rat tail</d>` for a
container's content (the indentation before the link is the tree's
depth, as in the plain text), closed by `[Use <d cmd='inventory
help'>INVENTORY HELP</d> for more options.]`. The ids are the same
exist ids the hand tags carry, and `#<id>` works as a noun in a
command. The parser collects the links as the listing streams and
builds `possessions` at the footer (client/game/possessions.py, #184).
Story lines ("You put your handaxe in your canvas sack") and the
room's objects carry no ids in our stream. Captured 2026-09-13.

## The room's creatures

`<component id='room objs'>You also see <pushBold/>a town guard<popBold/>,
<pushBold/>Forest Warden Hengwild<popBold/>, a large parchment and a big
orange sign with a picture of a smiling Dwarf.</component>` — the same
"You also see" line the story shows, with every creature and NPC in a
bold run and the scenery plain; a repeated creature is listed once per
head ("a musk hog and a musk hog"). It comes with every room and on
every change, and empty when the room lists nothing. The parser keeps
the bold names, in order, as `room_creatures` (dr-scripts' `DRRoom.npcs`),
cleared on `<nav>` until the new room's listing lands. The hostile
status tags (`<crtrStatus>`, above) are the fight's view; this is the
head count on arrival, before anything engages (#178). Captured
2026-09-12.

## Corpses, balance, the shutdown and exp mods, after DRInfomon

Four things lich-5's DRInfomon (`lib/dragonrealms/drinfomon/`) reads
that the parser keeps too, added 2026-09-22:

- **Corpses in the room's listing** (#278). The text right after a bold
  creature says whether it is one: `<pushBold/>a cougar<popBold/> which
  appears dead, a rise in the cliff, <pushBold/>a cougar<popBold/> and
  <pushBold/>a cougar<popBold/>` (captured 2026-09-22 in the Northeast
  Vineyards); with the game's short post strings it reads `(dead)`
  (lich-5 drdefs.rb). `room_creatures_dead` is the parallel list of
  booleans, and `client/game/creatures.py` turns the pair into the
  game's own ordinals — the corpse is "cougar", the live ones "second
  cougar" and "third cougar" — so `;hunt` aims past the corpse.
- **The balance word** (#280). Elanthipedia's Combat page lists twelve
  levels, "completely imbalanced" to "incredibly balanced", "solidly
  balanced" the base; the game states it as "You are solidly
  balanced", in the status line "[You're badly balanced and in good
  position.]" or the ASSESS line "You (off balance) are facing a ship
  rat (1) at melee range." `balance` holds the last word stated (no
  capture in the logs yet; the forms are the wiki's and lich-5's
  `BalanceValue`). Position, the other half of that line, is not read.
- **The maintenance announcement** (#277). "Announcement: DragonRealms
  will be shutting down in 15 minutes for routine maintenance." — the
  count drops with every notice down to "1 minute", the trailing text
  varies, so the stem is matched anchored at the line's start (quoted
  text cannot trigger it) and `shutdown_at` is the server clock plus
  the minutes, recomputed each time. The engine emits a `shutdown`
  frame ("end<TAB>server now", the roundtime frames' shape, transient
  like them and restated to a late attacher against the current clock);
  the strip counts it down and `;train` winds down. No capture yet:
  lich-5 drparser.rb's `GameShutdown` is the pattern.
- **The exp window's modifiers** (#281). `<component id='exp mods'>`
  carries a header and one `+5 Evasion` / `--3 Perception` per line
  (lich-5's `ExpModLine`; uncaptured here — no rank-modifying buff has
  been up while logging). `exp_mods` is `{skill: +-n}` and a change
  rewrites the exp stream, whose last line reads "mods: Evasion +5".
