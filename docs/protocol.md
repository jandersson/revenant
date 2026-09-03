# The wire protocol the parser reads

DragonRealms speaks the Simutronics XML-ish frontend protocol, and this
file is the reference `client/xml_data.py` implements against: what each
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
(#109, `client/streamroute.py`).

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
on change, and `scripts/xp.py` snapshots it to `~/.revenant/xp.db`
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
`left` carry what each hand holds and are a ready source for a hands
indicator that does not exist yet.

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
