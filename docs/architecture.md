# Architecture, with its history

How the pieces fit and why each one is shaped the way it is: one pipeline, one parser, several processes, told module by module with the issue numbers of the decisions. This is the long-form companion to the module map in `.claude/CLAUDE.md`; read that for the shape and this for the reasons.

The text below accreted a sentence per change as features shipped, so it doubles as a record of what was learned in the field: the socket that would not wake on Linux, the map twins, the dock layout that aborted inside Qt. Where a `docs/*.md` model file exists, it holds the captured evidence; this page holds the plumbing.

One pipeline, one parser, several processes. The `client` package
groups its modules by that shape: `engine/` is the connection and the
session process (socket, login, parser, engine, the daemon and its
script engine, spawning and attaching), `game/` is the Qt-free models
scripts lean on (the map and walker, climbs, circles, the clock,
inventory, wounds, profiles, training plans, the history database),
`ui/` is frontend logic without a toolkit (text styling and fonts,
stream routing, window layout, highlights, focus, the crash guard,
and the Textual `tui.py`), and `gui/` is the PyQt6 window; `settings`
and `client_logger` sit at the top because every package reads them.
The grouping followed the seams the paragraphs below had already
drawn, forty flat modules later: a training-plan module had landed two
entries from a dock-layout module.

- `client/client/engine/netsock.py` — minimal buffered TCP socket (telnetlib-shaped
  API: `read_until`, `read_very_eager`).
- `client/client/engine/login.py` — eaccess handshake. Credentials: password lives in
  the OS keychain (`keyring`, service "revenant"); account/character come from
  `REVENANT_ACCOUNT` / `REVENANT_CHARACTER` env vars, falling back to the
  names saved in `~/.revenant/login.json` (override: `REVENANT_LOGIN_DEFAULTS`)
  by the login dialog's remember checkbox — names only, never the password.
  With no keychain entry
  the launcher prompts once — terminal getpass with a tty, the Qt login
  dialog (`client/client/gui/login_dialog.py`, with remember-me → keychain)
  without one — and exchanges the password for a single-use launch key,
  passing only the key to the session over stdin (never argv or env).
  **Never store credentials in files, even gitignored ones.**
- `client/client/engine/xml_data.py` — XMLParser target holding parsed game state
  (indicators, compass, prompt, vitals, hostile creatures from
  `<crtrStatus>`, what each hand holds from `<left>`/`<right>` — a
  pair at login, then one tag per hand as it changes, carried across
  `;reexec` like the name, #159; the prepared spell from `<spell>` and
  the running spells with minutes left from the Spells window's
  `percWindow` pulses, 2026-09-12) — docs/protocol.md is the wire-protocol reference it
  implements against (tag grammar cited to the GemStone wiki's Wrayth
  protocol page, DR's own stream/component/indicator ids derived from
  captured traffic) — plus `route(line)` which splits each line
  into `(stream, text, style)` segments via pushStream/popStream markers
  and the styling markers (pushBold, presets, style spans). style is ""
  for plain text, a style name the GUI maps to colors/bold, the control
  value "clear" (<clearStream/>: wipe that stream's window), or
  "link:<command>" for <d> command links (clickable in the GUI: a click
  sends the command). C0 control characters are stripped from every
  piece — the game wraps its idle warning in BEL, which a font draws
  as a box — and a line that rang the bell yields a synthetic
  `"bell"` segment first (#131).
  Segments carry their own newlines — the engine appends "\n" to the last
  piece of each line per stream; frontends never add line breaks. Also
  parses the exp window (`<component id='exp Skill'>`) into
  `experience` (rank/percent/mindstate per learning skill); the engine
  rewrites a synthetic "exp" stream on change (Experience dock), and
  `scripts/xp.py` snapshots it to `~/.revenant/history.db` for history.
- `client/client/engine/core.py` — `Engine`: owns a connection, feeds lines through
  XMLData, invokes `output_callback(text, stream)` per segment. Emits a
  synthetic `"compass"` stream (one frame per room, identical exits
  included — scripts treat it as the room-arrival signal), a `"room"`
  frame (`"uid<TAB>title"`, per room change) that the map dock and
  surveyor follow,
  `"roundtime"`/`"casttime"` frames (`"end<TAB>server now"`, both server
  epoch) when a timer starts — moment-bound, so the session excludes
  them from the reattach backlog (`TRANSIENT_STREAMS`) — a
  `"character"` frame when the login `<app char=.../>` tag names who's
  playing, a full-state `"vitals"` frame (`"health 100 stamina
  95 ..."`) whenever the game's minivitals dialog changes (partial
  game updates accumulate in xml_data.vitals), a full-state
  `"indicators"` frame (the active indicator ids, sorted) when
  posture/stunned/bleeding/dead flip, and a `"timesync"` frame
  (server-minus-local clock seconds, from the prompt's server time)
  when the delta first appears or moves >1s — the clocks dock and
  ;clock compute Elanthian time from it, immune to local clock
  drift (#102), and a `"bell"` frame when a line carried BEL — the
  GUI sounds QApplication.beep(), the official frontend's behaviour
  for the idle warning; transient like the timers (#131).
  session.attach replays
  character, vitals, indicators, timesync, and the room to late
  attachers, like the compass.
- `client/client/engine/session.py` — the detachable session daemon
  (`python -m client.engine.session`): logs in, owns the game socket, serves
  `(stream, text)` frames as JSON lines on 127.0.0.1:4242 to any number of
  attached frontends, and hosts the script engine. `AttachedEngine` is the
  client side; it presents the same surface as `Engine`. Typing `;reexec`
  in any frontend re-execs the session with the code currently on disk,
  handing the live game socket across (`--game-fd`) — no logout, no
  re-login; frontends drop and auto-reattach within ~10s. Indicator
  state and the character name ride along (`REVENANT_GAME_STATE`):
  the game only announces indicators on change and the login <app>
  tag never repeats, so a fresh parser could otherwise never learn
  a standing fact like DEAD (#92) or who is playing (#95).
  **`;reexec` on Windows is a handoff**: exec would spawn and a WinSock
  handle is no CRT fd, so a spawned child adopts the game socket from
  socket.share() bytes over stdin and the old process exits once the
  child listens (#129). The child's stderr goes to
  `logs/reexec-<stamp>.err` — pythonw has none of its own — and a
  handoff that fails (a child that never listens, an exception in the
  share) re-binds the port, restarts the reader and keeps serving the
  old code, telling every window why; twice before that it took the
  session down silently (#162). Scripts
  reload from disk on every start, and so do the client/ helper
  modules they lean on (`scripting.RELOADABLE_MODULES`: probe,
  walker, mapdb, inventory, circles, climbs, eltime, settings,
  textfont — pure logic, reloaded in dependency order when their
  file changed since import, #138), so a script or walker edit
  reaches a running session on any platform via `;stop <name>` and
  running it again. A reload is a fresh module object, never a
  re-execution in place: a script already running keeps the
  functions it imported and the globals they were written against,
  the next start gets the new code, and the log names the running
  scripts that kept theirs (#181 — an in-place reload once left
  `;hunt`'s old `walk` unpacking the walker's new three-value
  helper). A crash is remembered on the manager (`s.crashed(name)`)
  so `;train` can tell it from a clean exit. Developer mode (settings `dev_mode` / File →
  Settings, or `REVENANT_DEV=1`) reports a start slower than
  `scripting.SLOW_LOAD_SECONDS` with what reloaded. Everything else — session, core, xml_data, the
  GUI — needs `;reexec`, or on Windows a new session: close the
  window (quit) and relaunch. File → Detach is the wrong move: it
  leaves the session running and a relaunch reattaches to the old
  code.
- `client/client/engine/scripting.py` — script engine. Scripts are `main(s)` Python
  files in `scripts/` (repo root), run as threads in the session, controlled
  by `;`-commands typed in any frontend (`;list`, `;help [x]`, `;run x`,
  `;stop x`, and `;x help` for the same page as `;help x`, running or
  not). `;help` renders module docstrings — write them as the user
  manual.
  Handle API: put/get/waitfor/waitrt/echo/emit/sleep/state/args — `emit`
  targets an arbitrary stream (e.g. "thoughts") — and run/is_running/
  tell/kill, through which one script drives others: `;train`
  (scripts/train.py) is the training orchestrator, a loop over the
  per-character plan in `client/game/training.py`
  (~/.revenant/training/<name>.json) that starts each task's script
  (;athletics, ;hunt) or cycles its commands until the task's skills
  reach the target mindstate, then rests in a safe room until they
  drain (docs/training.md). `scripts/lnet.py` uses it
  to mirror LNet chat into the Thoughts window (`;lnet`); the command
  grammar and dispatcher it shares with the standalone chat window live
  in the stdlib-only `chat/commands.py`, and `client/gui/chat_window.py`
  (`revenant-chat [name]`) is that window: one of the user's own
  characters (offered from the cached rosters and nothing else —
  LNet names are character names), no game session, password from
  the keychain via the Qt-free
  `client/engine/lnet_login.py` (service "revenant-lnet"; a rejected login
  asks once with a remember checkbox), one worker thread owning the
  socket as the script does (#141). `;tend`
  bandages bleeders (watch mode wakes on soak-through); `;wealth`
  (an autostart, `autostart_wealth` / `REVENANT_NO_WEALTH`) asks BANK
  ACCOUNT after login and every three hours — it works from anywhere,
  free on a Premium account — logs one `bank` row per branch (the
  branch in the `bank` column, captured 2026-09-12) into history.db,
  follows with INFO (carried coin and debt as `carried`/`debt` rows,
  the shape `;sheet` writes) and echoes a per-currency summary of
  both, and still overhears teller balance lines; `;wealth now` asks
  again. beholder's Wealth view shows the
  newest figure per item, since INFO, a teller and the report land at
  different moments.
  `client/client/game/probe.py` is the ask-and-classify helper the keyword
  scripts (;mechlore, ;favors, ;hunt) share: send a command, gather the
  answer through its roundtime, match it against an ordered outcome
  table. It reads the story and the `combat` stream both
  (`STORY_STREAMS`): the game pushes every swing and kill line through
  `<pushStream id="combat"/>`, which the main window shows but a
  handle's default `get()` does not deliver — two hunts ended "ground
  empty" among live rats before that was seen (2026-09-12).
  `scripts/hunt.py` is the hunting loop over the per-character profile
  (`client/game/profile.py`, docs/hunting.md): weapon and stance,
  attack until the room empties, skin each kill onto a worn bundle
  (a bundling rope from any tannery) or into the loot container,
  search it, keep the profile's buffs cast and recast the first to
  train a magic skill, move along the ground, break off on the health
  or wound floor. `scripts/skins.py` sells the worn bundle at the
  nearest tannery and keeps the rope. `client/game/buffs.py` is the
  casting the hunt grew — the profile's buffs kept up, the first one
  recast between actions to train a magic skill with a mana ramp that
  backs off at the strain warning, and the profile's spells cast at
  the prey between swings for Debilitation and Targeted Magic, the
  three taking turns (#192, #200) — shared with `;athletics`, which
  fills its award-timer waits with it (#177). `client/game/discard.py` is the
  only way a script drops anything: an allowlist of the foraged junk
  ;mechlore braids (grass, grass rope) plus settings.json's
  `droppable`, and a `drop()` that refuses the rest with an echo — a
  dropped item is a lost item, so hands are freed with STOW.
  Sessions autostart the xp history logger, the beholder dashboard
  server in quiet mode, the character-sheet snapshotter (`;sheet`:
  INFO + EXP ALL into stats/sheet_skills/character tables every 3h;
  `;sheet inv` additionally asks INV LIST into the `inventory` table
  — on demand only, never scheduled, because INV LIST costs 4-5s of
  roundtime. The autostarted script waits on its command queue
  between snapshots, so `;sheet inv` typed at it takes one inventory
  snapshot and the schedule carries on; from cold it snapshots and
  exits (#122). `client/game/inventory.py` flattens the indented tree
  into rows naming each item's container, identical items collapsed to
  a quantity, #117. Scripts read answers through `probe.collect`,
  which glues the per-segment pieces the session delivers back into
  whole lines — the last piece of a line carries the newline — so
  <d>-linked item lines keep their indentation, #123),
  and the death watchdog (`;deathwatch`: logs an unattended corpse out
  after a rescue grace so the body keeps for a raise, or departs it
  with the best variant the favors afford before it decays —
  docs/death.md holds the captured model)
  (`session.autostart_scripts`; `;stop <name>` opts
  a session out; the GUI's File → Settings dialog over
  `client/settings.py` / ~/.revenant/settings.json turns them off
  durably, and REVENANT_NO_XP=1 / REVENANT_NO_BEHOLDER=1 override
  everything for one launch — quit-on-close lives there too, and so
  does the game text's font: `font_family` / `font_size`, normalized
  by the Qt-free `client/ui/textfont.py` and applied live to every text
  view and the input line, #118 — every view but the status docks:
  Experience keeps the fixed-pitch font and Spells the platform font,
  each at its own size, following only its own `dock_fonts` row
  (`textfont.STATUS_VIEWS`, #173, #179));
  `;beholder` opens the dashboard in the browser, and the GUI embeds it
  via View → Experience History (QWebEngineView, lazy-created, browser
  fallback when QtWebEngine is missing).
- `client/client/game/mapdb.py` — the community DR map database (elanthia-online
  mapdb-backup-dr), downloaded to `~/.revenant/mapdb/` on first use, never
  vendored. Pathfinding on a networkx DiGraph of the walkable edges
  (#79): Dijkstra over the map's timeto travel times, detouring
  around the settings avoid list (`avoid_rooms`, cougar grounds by
  default; forced crossings warn; `;go2 direct` bypasses once).
  wayto commands starting with ";e" are embedded
  Ruby, walked only when they translate to plain fput/move commands —
  and those translatable ;e edges stay in the graph (dropping them
  partitions whole areas off). The map lists some rooms twice with
  only one entry carrying the game's uid (39 such twins, #137):
  `same_place` recognizes twins (shared uid, or same title and
  identical exits), the walker accepts arrival in a twin of the
  planned room, and the graph plans through the uid-bearing twin
  when a room links to both.
  `client/client/game/walker.py` (locate/walk; model in docs/movement.md;
  a climb turned back for footing is retried once standing with the
  named items stowed, then reported as beyond the character's
  Athletics rather than as a stall, #157; the Faldesu ferry between
  the Crossing and Riverhaven ridden after bescort's routine, #205) is
  the shared travel engine; `scripts/go2.py` is the command on top, and
  `;favors` (scripts/favors.py) rides it for the favor-orb run — grotto
  ritual, attended puzzles, temple altar offer (docs/favors.md).
- `client/client/game/climbs.py` — climbing spots with Athletics rank
  bands and conditions, keyed to the community map's room ids
  (never written into the community db, which refreshes wholesale);
  `;athletics` derives its training ladder and its ;athletics-list
  advice from this one table (#87). Bands from Elanthipedia's
  Climbing and Swimming list; rank 100+ trains in town on the
  Crossing battlements.
- `client/client/game/circles.py` — circle requirements, Qt-free: every
  circled guild's Elanthipedia rate table + the slot/soft-requirement
  model; `;circle` (scripts/circle.py) and beholder's Circle-gates
  view report what gates the next circle from the latest ;sheet
  snapshot (which records guild). docs/circles.md holds the model,
  its captured guildleader validation, the wiki corrections, and the
  open anomalies.
- `client/client/game/eltime.py` — the Elanthian clock, Qt-free: date, anlas,
  and moon phases computed from real time (docs/eltime.md holds the
  model and its captured evidence). `scripts/clock.py` (`;clock`) is the
  ntpdate: TIME + OBSERVE MOONS, calibration stored in settings
  (`eltime_offset_seconds`, `eltime_moons`).
- `client/client/gui/client_gui.py` — PyQt6 frontend: the window,
  its menus, layout restore, the dispatch of each stream to the
  widget it belongs to, styled text, and the connection. The docks'
  widgets are modules of their own beside it — `compass_dock.py`,
  `clocks_dock.py`, `input_strip.py` (the command line with its
  vitals bars, status strip and RT/CT timers), `map_dock.py`,
  `text_views.py` (the story and stream views, per-view fonts) — each
  fed by dispatch and ignorant of the window; dock creation order and
  object names stay in client_gui.py because a saved layout restores
  onto them. `client/tests_gui/` exercises all of it headless on Qt's
  offscreen platform (a stub engine, every stream's frame through
  dispatch, the layout round trip), in CI on every leg. GUI-thread safety via
  the `game_text` pyqtSignal; a sys.excepthook (`client/ui/crashguard.py`,
  Qt-free) keeps the window alive when a Qt slot crashes, logging the
  traceback and surfacing it in the main window + status bar (#94);
  the reader thread runs `client/engine/reader.py`'s Qt-free pump, which
  surfaces EOF and crashes in the status bar instead of dying
  silently (#96); stream docks route thoughts/spells/arrivals/deaths
  (the stream -> dock table and the rule that a "clear" wipes only
  that stream's own dock live in the Qt-free `client/ui/streamroute.py`,
  so tests reach them headless — a clear for an undocked stream like
  `inv` must be dropped, never applied to the main window, #109);
  compass dock renders the `"compass"` stream; the Map dock draws
  the community map around the character from the `"room"` stream
  (grid layout in the Qt-free `client/ui/maplayout.py`, drawing in
  `client/gui/map_dock.py`; click a room to ;go2 it; docked on the
  right with a 320px size hint, the scene padded by half a viewport
  so the current room always centres — alone on the left with no
  hint it opened as a clipped strip, #146); the room the dock resolves
  is also appended, dim, to the story's room-title line — "[Town
  Green] (1420)", the id ;go2 takes, Lich's roomnumbers idea — when
  `show_room_ids` is on, the Qt-free `client/ui/roomids.py` pairing
  the title line with the "room" frame in either arrival order since
  the <nav> uid can land a line before the title (#156); the Injuries
  dock (`client/gui/injuries_dock.py`) draws the game's injuries panel
  from the `injuries` stream — one badge per body part, amber for a
  wound, purple for a scar, the panel's level beside the name — which
  the engine emits on every push of `<dialogData id="injuries">` and
  the session states fresh on attach like vitals (#163); the Spells
  dock (`client/gui/spells_dock.py`) draws the running spells with a
  countdown ticking between the window's pulses and the prepared
  spell above them, from the `spells` stream the engine emits on any
  change of the parser's `active_spells` / `prepared_spell` and the
  session replays on attach — it took over the "Spells" dock name from
  the raw text view, which the GUI no longer shows (#175); every
  dock folds to its title bar and back (`client/gui/dock_collapse.py`:
  our own title bar with fold, float and close buttons, a double-click
  on the title, or View → Collapse/Expand Dock, Ctrl+Shift+D, on the
  focused dock; the content hides and the dock's height pins to the
  bar, keeping its place; the folded names are saved beside the
  layout keys and applied after each restore, #180); the clocks dock ticks
  Elanthian time, moons, Stockholm/Chicago, and (via a Settings toggle)
  Earth's moon; roundtime/casttime count down beside the input line
  under a row of vitals bars (health/fatigue/spirit/concentration,
  mana for casters), next to the status strip (posture + stunned/
  bleeding/hidden badges, DEAD in alert red); the input line has
  shell-style Up/Down history (client/ui/command_history.py, Qt-free)
  and re-selects after send so Enter repeats; the title bar names the
  logged-in character, and each character's window keeps its own saved
  dock layout (`client/ui/window_layout.py`, Qt-free; the unscoped legacy
  pair seeds characters without one, #74). The GUI learns its
  character before building the window — from the session registry
  (`session.character_for_port`) on attach, `REVENANT_CHARACTER` in
  direct mode — and restores that layout before the first show:
  restoring saved dock state onto a shown window aborted the process
  inside Qt (#124), and for one saved state even hidden-restore-show
  did (#140), while every state restored fine before the first show.
  The hidden-restore-show path remains only for a character learned
  from the "character" frame. Direct mode logs in itself;
  `--attach` connects to a session. User highlight patterns
  (`client/ui/highlights.py`, ~/.revenant/highlights.json) color matched
  spans over any base style; View → Reload Highlights re-reads them.
  Three named defaults ship in code (`DEFAULT_RULES`: the balance
  line, the roundtime line, the spell-ready lines, soft colours) under
  the file's own rules; a file entry `{"disable": "<name>"}` turns one
  off and a file rule with that name replaces it (2026-09-13).
- `client/client/game/possessions.py` — possessions by the game's exist
  ids (#184): INV LIST wraps each item in a command link (`remove #id`
  worn, `get #id in #container` a content), the parser collects the
  links as the listing streams and builds `possessions` at the
  footer, `;sheet inv` stores the ids beside the names (twins no
  longer collapse), and a script can name an item exactly (`;favors`
  fetches a listed orb with `get #<id>`). Only INV LIST and the hand
  tags carry ids, so the model is exact as of the last listing.
- `client/client/engine/policy.py` — the session's command policy for
  outside senders (#161): every line tagged with an origin is decided
  before the game sees it — read-only verbs pass, the giving,
  dropping, spending and leaving verbs (and `;reexec`) are refused
  with a reason echoed to every window in the alert style, DROP
  allows the junk list only, PUT only into the character's own
  container, a listed valuable is refused whatever the verb — with
  `~/.revenant/policy/<name>.json` adjusting the built-ins. The
  player's typing is never policed, and nothing on the sending side
  lifts it.
- `client/client/engine/launch.py` — the `revenant` console script: attaches
  the GUI to the right session, spawning one when needed. Characters
  run side by side, one session/window each on its own port: sessions
  register in ~/.revenant/sessions.json (client/engine/session.py: rows
  written atomically, a failed read never rewritten, a row pruned only
  when its port refuses twice, and the session re-asserting its own
  row every thirty seconds, #160), `revenant <name>` attaches to that character's
  session or spawns on a free port, and `--pick` (the Start Menu
  shortcut) offers running sessions to attach plus every cached
  character on every account to launch (#58). The session keeps an
  `attached` window count in its registry row (updated on every
  attach and drop), so the picker's online rows read "no window" or
  "1 window", sit under their own header in amber and bold, and the
  picker opens on the detached session rather than the saved login
  character — an attach row at the top of an alphabetical roster
  scrolled out of view once (#158).
