# The game protocol

The game sends Simutronics' Wrayth frontend protocol: lines of text with XML-like tags in them. `client/engine/xml_data.py` reads it into state and styled text; `client/engine/core.py` turns state changes into frames for windows and scripts.

- **Grammar:** the GemStone wiki's [Wrayth protocol](https://gswiki.play.net/Wrayth_protocol). DragonRealms sends other streams than GemStone; captured traffic wins.
- **Not XML.** Tags arrive unclosed, mixed with prose, split across lines. The parser keeps state from the tags (`start`/`end`/`data`); `route(line)` separately splits each line into `(stream, text, style)` segments and strips the rest.

## Display

| Tag | Segment |
| --- | --- |
| `pushStream id="x"` … `popStream` | text in stream `x`; otherwise main (`""`) |
| `clearStream id="x"` | style `"clear"`: wipe `x`'s window, never main |
| `pushBold`, `preset id`, `style id` | a style name |
| `<d cmd="...">` | style `link:<cmd>` |
| BEL | a `bell` segment |

Stream ids are case-sensitive (`percWindow`). `combat` carries every swing and kill. `talk`, `whispers`, `inv` and a few others are dropped; main has the same lines.

## State the parser keeps

| Tag or component | Field |
| --- | --- |
| `prompt time=` | `server_time` |
| `roundTime`, `castTime` | `roundtime`, `casttime` (epoch end times) |
| `indicator` | `indicator` (`IconSTUNNED`, `IconDEAD`...) |
| `app char=` | `name` |
| `nav rm=` | `room_uid`, the map's key |
| `compass` / `dir` | `compass` |
| `dialogData` minivitals, injuries | `vitals`, `injuries` |
| `crtrStatus hostile="1"` | `hostiles` |
| `left`, `right` | `left_hand`, `right_hand` |
| `spell`, the `percWindow` stream | `prepared_spell`, `active_spells` |
| INV LIST's `<d cmd>` links | `possessions` |
| `exp <Skill>` | `experience` (rank, percent, mindstate) |
| `exp rexp`, `exp mods`, `exp tdp`, `exp favor` | `rested`, `exp_mods`, `tdps`, `favors` |
| `room players`, `room objs` | `room_players`, `room_creatures` |
| the maintenance announcement | `shutdown_at` |

Scripts read these through `s.status` (`client/game/status.py`).

## Frames the engine emits

| Stream | Text |
| --- | --- |
| `compass` | the exits; one per room, the arrival signal |
| `room` | `uid<TAB>title` (not the game's `room` stream) |
| `exp` | the whole window rewritten |
| `vitals` | `health 100 mana 95 ...` |
| `indicators` | the active ids |
| `injuries` | `head wound 1 chest scar 2` |
| `spells` | `prepared<TAB>name`, then `name<TAB>minutes` |
| `hands` | `left<TAB>right` |
| `roundtime`, `casttime`, `shutdown` | `end<TAB>server now` |
| `character` | the name, once |
| `timesync` | server minus local clock |

Each frame is the full state, sent on change and restated to a late attacher.

## Caveats

- **Timers are end times.** Seconds left is `roundTime value` minus the prompt's `time`.
- **Change-only.** Indicators come on change and `app` once at login; a parser started mid-session cannot learn them, so `;reexec` hands the state across.
