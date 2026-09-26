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
  API: `read_until`, `read_very_eager`), with TCP keepalive on every
  game socket it makes or adopts and a clock of the last byte received
  (`silent_for`): a link dead without a FIN went 52 minutes unnoticed
  on 2026-09-19, found only on the next write (#221). The session's
  heartbeat adds one TIME after ten silent minutes — a living link
  answers, a dead one fails on the write and the session ends saying so.
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
  `;reexec` like the name, #159, and like the hostile set, whose
  frames come only with the creatures' next attacks, #244; the
  prepared spell from `<spell>` and
  the running spells with minutes left from the Spells window's
  `percWindow` pulses, 2026-09-12; after lich-5's DRInfomon, the
  maintenance shutdown's target time from its announcement, the
  balance word from the combat lines, the exp window's modifiers and
  the corpse marks beside the room's creatures, #277-#281) — docs/protocol.md is the wire-protocol reference it
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
  `experience` (rank/percent/mindstate per skill, a cleared one kept at
  0/34, #295); the engine rewrites a synthetic "exp" stream on change
  (Experience dock) listing only the skills not at clear, and
  `scripts/xp.py` snapshots it to `~/.revenant/history.db` for history.
- `client/client/engine/core.py` — `Engine`: owns a connection, feeds lines through
  XMLData, invokes `output_callback(text, stream)` per segment. Emits a
  synthetic `"compass"` stream (one frame per room, identical exits
  included — scripts treat it as the room-arrival signal), a `"room"`
  frame (`"uid<TAB>title"`, per room change) that the map dock and
  surveyor follow,
  `"roundtime"`/`"casttime"` frames (`"end<TAB>server now"`, both server
  epoch) when a timer starts — moment-bound, so the session excludes
  them from the reattach backlog (`TRANSIENT_STREAMS`; the replay ends
  with an empty `"attached"` frame the frontends drop and an outside
  `--wait-for` counts from, #287) — a
  `"character"` frame when the login `<app char=.../>` tag names who's
  playing, a full-state `"vitals"` frame (`"health 100 stamina
  95 ..."`) whenever the game's minivitals dialog changes (partial
  game updates accumulate in xml_data.vitals), a full-state
  `"indicators"` frame (the active indicator ids, sorted) when
  posture/stunned/bleeding/dead flip, a `"hands"` frame ("left
  name<TAB>right name", a half empty for an empty hand) when either
  hand changes — the input strip's L/R and the TUI's status line,
  stated fresh on attach — and a `"timesync"` frame
  (server-minus-local clock seconds, from the prompt's server time)
  when the delta first appears or moves >1s — the clocks dock and
  ;clock compute Elanthian time from it, immune to local clock
  drift (#102), and a `"bell"` frame when a line carried BEL — the
  GUI sounds QApplication.beep(), the official frontend's behaviour
  for the idle warning; transient like the timers (#131).
  session.attach replays
  character, vitals, indicators, timesync, and the room to late
  attachers, like the compass, and the injuries and spells frames
  whether or not anything is hurt or running — a state that is only
  stated when non-empty leaves a late attacher's dock showing what
  healed or expired while it was away (#213).
- `client/client/engine/registry.py` — the session registry,
  ~/.revenant/sessions.json: a row per running session ({port,
  character, pid, attached}) written atomically, a failed read never
  rewritten as empty, a row pruned only when its port refuses twice,
  the session re-asserting its own row every thirty seconds (#58,
  #158, #160). The launcher's picker and the GUI's
  `character_for_port` read it.
- `client/client/engine/wire.py` — the wire an outside tool speaks to a
  session: the JSON frame codec, the EXTERNAL and STATE marks a
  tagged line leads with, and `send_line`, `send_and_read`,
  `request_state` — the client side `revenant-send` and the roster
  sweep use (#135, #216). The GUI and the TUI attach through
  `session.AttachedEngine` instead.
- `client/client/engine/session.py` — the detachable session daemon
  (`python -m client.engine.session`): logs in, owns the game socket, serves
  `(stream, text)` frames as JSON lines on 127.0.0.1:4242 to any number of
  attached frontends, and hosts the script engine. `AttachedEngine` is the
  client side; it presents the same surface as `Engine`. Typing `;reexec`
  in any frontend re-execs the session with the code currently on disk,
  handing the live game socket across (`--game-fd`) — no logout, no
  re-login; frontends drop and auto-reattach within ~10s. File →
  Reconnect in a window whose session is gone starts a new one for the
  window's own character on the account that owns it (the saved login
  default logged the account's other character in, 2026-09-19). Indicator
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
  modules they lean on (`scripting.RELOADABLE_MODULES`: every
  `client/game/` module but history and balance, which the GUI and
  the parser hold, plus settings and textfont — wounds and herbs
  joined late, after a wounds fix sat unseen in a running session
  for an afternoon — pure logic, reloaded in dependency order when their
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
  drain (docs/training.md) — a rest opening with
  `client/game/drain.py`'s guess at its length, the pulse rates
  fitted from ;xp's mindstate rows (docs/experience.md, #300). `scripts/cast.py` (`;cast`, #225) runs
  the hunt's cast loop standing still — the first buff on the mana
  ramp with the cambrinth, a POWER a minute — for the idle stretches
  (docs/training.md). `scripts/soul.py` (`;soul`) keeps a
  Paladin's soul up on the deeds' timers and reads it through
  `client/game/soul.py` (docs/soul.md, #224). `scripts/lnet.py` uses it
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
  table. A command the game answers "...wait N seconds." did not run,
  and `ask` sends it again after those seconds, up to three times,
  before any classifier sees the answer (#251: the parser's clock is
  whole seconds, so a roundtime ending in the current second still
  has a fraction to run that no prompt stamp shows). It reads the story and the `combat` stream both
  (`STORY_STREAMS`): the game pushes every swing and kill line through
  `<pushStream id="combat"/>`, which the main window shows but a
  handle's default `get()` does not deliver — two hunts ended "ground
  empty" among live rats before that was seen (2026-09-12).
  `client/client/game/loop.py` holds the loop idioms the trainer
  scripts (attune, cast, forage, heal, perform, scholarship, seek,
  soul) used to copy: `wants_stop` — True once "return" was typed at
  the script, the graceful end beside `;stop` — `danger` (dead, or
  hostiles in the room) and `pause`, a sleep in one-second slices
  that ends early on either. Reloadable like probe.
  `scripts/hunt.py` is the hunting loop over the per-character profile
  (`client/game/profile.py`, docs/hunting.md): weapon and stance,
  attack until the room empties, skin each kill onto a worn bundle
  (a bundling rope from any tannery) or into the loot container,
  search it, keep the profile's buffs cast and recast the first to
  train a magic skill, move along the ground, break off on the health
  or wound floor. `scripts/skins.py` sells the worn bundle at the
  nearest tannery and keeps the rope. `scripts/repair.py` APPRAISEs
  the gear worn and held and takes every piece at or below the
  profile's `repair_floor` to the nearest repair shop — GIVE for the
  estimate, GIVE again to pay, the ticket waited out and handed back,
  the piece worn again (`client/game/repair.py`, #307).
  `client/game/buffs.py` is the
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
  — once at login (the autostart's first snapshot, the character
  being safe then) and on demand after, never on the schedule,
  because INV LIST costs 4-5s of roundtime. The autostarted script
  waits on its command queue
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
  docs/death.md holds the captured model), and the attention monitor
  (`;sentinel`, #276: every line through `client/game/novelty.py` —
  a stranger's whisper, speech or gesture at the character, a word
  spelled to slip past a script, status-monitor.lic's two spam shapes
  ring the bell and start a grace; a staff notice on `ooc` and a
  player arriving ring once; every line never seen before lands in
  the Attention dock and is remembered in
  `~/.revenant/sentinel/<name>.json`; unanswered by `;sentinel ok`,
  it gives `;train` its return word and QUITs — docs/running.md)
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
  default; forced crossings warn; `;go2 direct` bypasses once). A
  timeto written in Ruby is a gate (`gate_of`: the skill and its least
  rank, the guild, the circle) that the router judges against the exp
  window's ranks before the first step; one it cannot judge closes
  the edge (#214).
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
- `client/client/gui/jumplist.py` — the taskbar button's jump list on
  Windows (#226): a right-click on the pinned or running Revenant
  button offers "Pick a character..." and every character with a
  history.db snapshot (the roster when none has one), each a task
  running the launcher (`--pick`, or the name) — from source the
  shortcut's windowless pythonw on tools/desktop.py, in the packaged
  build the executable itself. Registered once at GUI start through
  the shell's ICustomDestinationList under the window's
  AppUserModelID by a ctypes COM shim (PyQt6 has no jump-list API);
  a failure is logged and ignored. `tasks()` is the pure half the
  tests cover.
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
  the session states fresh on attach like vitals (#163), an empty
  set included (#213); the Spells
  dock (`client/gui/spells_dock.py`) draws the running spells with a
  countdown ticking between the window's pulses and the prepared
  spell above them, from the `spells` stream the engine emits on any
  change of the parser's `active_spells` / `prepared_spell` and the
  session replays on attach — it took over the "Spells" dock name from
  the raw text view, which the GUI no longer shows (#175); every
  dock folds to its title bar and back (`client/gui/dock_collapse.py`:
  our own title bar with fold, float and close buttons, a double-click
  on the title, or View → Collapse/Expand Dock, Ctrl+Shift+D, on the
  focused dock; the content squeezes to zero height — hidden, it
  took the dock's width limits with it and the whole dock column
  stopped resizing until the dock was expanded, #201 — and the dock's
  height pins to the
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
  (`registry.character_for_port`) on attach, `REVENANT_CHARACTER` in
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
  with a reason echoed to every window in the alert style (an OFFER
  of an amount alone, a catalog merchant's bid, passes, #234), DROP
  allows the junk list only, PUT only into the character's own
  container, a listed valuable is refused whatever the verb — with
  `~/.revenant/policy/<name>.json` adjusting the built-ins: "allow"
  lifts a denied verb or, for `put`, the own-container rule (the
  almsbox tithe, #219); DROP of a non-junk item and a valuable never
  lift. The
  player's typing is never policed, and nothing on the sending side
  lifts it.
- `client/client/engine/launch.py` — the `revenant` console script: attaches
  the GUI to the right session, spawning one when needed. Characters
  run side by side, one session/window each on its own port: sessions
  register in ~/.revenant/sessions.json (client/engine/registry.py: rows
  written atomically, a failed read never rewritten, a row pruned only
  when its port refuses twice, and the session re-asserting its own
  row every thirty seconds, #160; a session `;train` spawned for a
  task carries `spawned_by` and `parent_port` and logs itself out
  once the parent's port has refused two heartbeats, #296), `revenant <name>` attaches to that character's
  session or spawns on a free port, and `--pick` (the Start Menu
  shortcut) offers running sessions to attach plus every cached
  character on every account to launch (#58). The session keeps an
  `attached` window count in its registry row (updated on every
  attach and drop), so the picker's online rows read "no window" or
  "1 window", sit under their own header in amber and bold, and the
  picker opens on the detached session rather than the saved login
  character — an attach row at the top of an alphabetical roster
  scrolled out of view once (#158).

## Module reference

Every module and script in one place, with the parser's fields and the
issue history — the long form of the one-line map in .claude/CLAUDE.md,
moved here on 2026-09-26 so the file every Claude session loads stays
short. Keep it current with the code, as the map is.

One pipeline, one parser, several processes. Session and GUI are separate
processes; the session owns the game socket and hosts scripts.

The `client` package is three subpackages and two shared modules:
`engine/` (the connection and the session process: socket, login,
parser, engine, session, scripting, spawning), `game/` (the Qt-free
models scripts lean on — what `RELOADABLE_MODULES` reloads, all but
history and balance, which the GUI and the parser hold), `ui/` (toolkit-free frontend logic
the PyQt6 `gui/` and the Textual `tui.py` share), with `settings.py`
and `client_logger.py` at the top. Paths below are `client/<pkg>/x.py`
for `client/client/<pkg>/x.py`.

- `client/engine/netsock.py` — buffered TCP socket, telnetlib-shaped.
- `client/engine/login.py` — eaccess handshake. Password in the OS keychain
  (service "revenant"); names in ~/.revenant/login.json. The session gets
  a single-use launch key over stdin, never argv or env.
- `client/engine/xml_data.py` — parser state + `route(line)` → `(stream, text,
  style)` segments. Styles: "" / a name / "clear" / "link:<cmd>". Control
  characters are stripped; a BEL becomes a "bell" segment. State includes
  `left_hand`/`right_hand` (`{noun, exist, name}` or None) from the
  `<left>`/`<right>` tags, one per hand as it changes, `injuries`
  ({part: (kind, level)}) from the injuries panel the game pushes,
  `prepared_spell` from the `<spell>` tag and `active_spells`
  ({name: minutes left or None}) from the Spells window's pulses, and
  `room_players` (names) from the `room players` component and
  `room_creatures` (the bolded names of `room objs`, in order, repeats
  kept) (#178), and `rested` ({stored, usable, refresh} minutes) from
  the `exp rexp` footer the exp window pushes on every pulse (#176);
  the engine's exp rewrite ends with that footer as a line. `possessions`
  ([{exist, name, noun, container_exist, worn, depth}]) from the
  command links INV LIST wraps each item in (`remove #id`, `get #id in
  #container`), built at the listing's footer whoever asked (#184).
  After lich-5's DRInfomon (2026-09-22): `shutdown_at` (server
  seconds) from the maintenance announcement, emitted as a
  "shutdown" frame the strip counts down and `;train` winds down
  before (#277); `balance` from the combat lines' twelve words
  (#280); `exp_mods` ({skill: +-n}) from the exp window's modifiers
  component, on the window's last line (#281); `room_creatures_dead`
  beside `room_creatures`, the listing's "which appears dead" marks
  (#278); `tdps` and `favors` from the window's footer components,
  so `;train`'s rest asks INFO once, not every poll (#282). `s.status`
  exposes each.
- `client/engine/core.py` — `Engine`: feeds lines, emits synthetic streams
  (compass = room-arrival signal, room, vitals, indicators, hands,
  character, timesync, roundtime/casttime, bell). It appends "\n" only to the last
  piece of a line per stream; frontends never add line breaks.
- `client/engine/session.py` — the detachable daemon: JSON frames on
  127.0.0.1:4242, backlog replay for late attachers (transient streams
  excluded, ended by an empty `attached` frame the frontends drop and
  `--wait-for` counts from, #287), the script engine, a TCP keepalive on the game socket
  and one TIME after ten silent minutes so a link dead without a FIN
  ends the session within minutes, not on the next command (#221),
  `;reexec` (exec on POSIX; on Windows a
  spawned child adopts the game socket via socket.share over stdin, #129;
  the child's stderr goes to `logs/reexec-<stamp>.err`, and a handoff
  that fails keeps the old process serving, #162). Beside it,
  `client/engine/registry.py` is the session registry
  (~/.revenant/sessions.json: register, heartbeat, prune on two
  refused probes, `character_for_port`) and `client/engine/wire.py`
  the outside tool's wire (the JSON frame codec, the EXTERNAL and
  STATE marks, `send_line` / `send_and_read` / `request_state`).
- `client/engine/scripting.py` — scripts are `main(s)` files in `scripts/`,
  loaded fresh from disk on every start; the pure-logic helpers in
  `RELOADABLE_MODULES` reload with them — as fresh module objects, so
  a running script keeps the functions it imported and their globals
  while the next start gets the new code (#181). Handle API:
  put/get/waitfor/waitrt/echo/emit/sleep/command/state/args (every
  call raises ScriptStopped after a `;stop`, except `put(cmd,
  cleanup=True)` — for a `finally:` that puts an item back; the
  manager holds one while the character is stunned or in roundtime
  and sends it after, #318), plus
  run/is_running/tell/kill/crashed for a script that drives other
  scripts (`;train`), and flag/flagged/unflag — a regex watched on
  every story line while the script does other things, the match
  kept until read (#279, lich-5's Flags). `;help` renders docstrings.
- `client/game/probe.py` — ask-and-classify shared by keyword scripts;
  `collect` glues per-segment pieces into whole lines and reads the
  story and the `combat` stream both (every swing and kill line
  arrives in `<pushStream id="combat"/>`; a story-only read sees no
  kill, 2026-09-12). `ask`'s windows are ceilings: each ends once the
  game's prompt has closed the answer and the stream has gone quiet a
  quarter second, and a command with no roundtime gets no tail (#248:
  the fixed windows held every command 4.5 s in the hunt). A command
  answered "...wait N seconds." did not run and is sent again after
  those seconds, up to three times (#251). `client/game/loop.py` is
  the loop idioms the trainer scripts share — `wants_stop` (the
  typed return), `danger` (dead, or hostiles in the room), `pause`
  (one-second slices that notice both) — one home instead of a copy
  per script (2026-09-22). `client/game/creatures.py` counts the
  room's creatures the way the game names them ("second cougar")
  and `aim(noun, names, dead)` gives the phrase that reaches the
  first live one past a corpse; `;hunt` swings at it (#278).
  `outgrown(names, ranks)` answers what the room's creatures can no
  longer teach, off `creatures_data.py` (every Elanthipedia Critter
  page's level, MinCap and MaxCap, generated by
  `tools/creature_tables.py`, never hand-edited); `;hunt` says the
  weapon skills past the MaxCap once a hunt (#322).
  `client/game/loot.py` reads what a SEARCH left on the ground off
  the room listing's difference (coins, a box, an item), so `;hunt`
  grabs its loot whatever the game called it (2026-09-23).
  `client/game/lootlog.py` writes every LOOT's outcome (box,
  treasure, nothing) per creature and ground to history.db's `loot`
  table — the box drop rate, which the game does not publish (#329).
  `client/game/flight.py` is the escape every trainer runs on
  hostiles — STAND, RETREAT twice and a move through the type-ahead,
  the caller's step then the compass exits, judged by the room
  changing — and `;train` runs it after a task ended among
  hostiles; `;stop all` keeps the background monitors running (#285).
- `client/engine/procspawn.py` + `client/engine/frozen.py` — every sibling spawn
  (session, dashboard, reexec child) goes through `command_for`, which
  is `python -m module` from source and `<exe> --role module` in the
  PyInstaller build (`packaging/revenant.spec`, `tools/build_installer.py`,
  the release workflow on `v*` tags, #60). Never spell `sys.executable -m`
  out again.
- `client/ui/tui.py` — `revenant-tui`, the Textual terminal frontend: attach-only,
  renders through the toolkit-free `client/ui/textstyle.py` (style table,
  highlight runs, status line — the tested half; keep its STYLES in step
  with client_gui's). Ctrl+Q detaches (#57).
- `client/engine/sendcmd.py` — `revenant-send`: one command into a running
  session from outside, tagged with its origin; read-only allowlist
  always passes, the rest needs `allow_external_send` or
  `REVENANT_ALLOW_SEND=1`. The session echoes `>> [origin] cmd` to
  every window (#135); `--answer SECONDS` prints the game's reply.
  `--state [fields]` prints the parser's state as JSON (room, vitals,
  exp window, hands, status words, injuries, spells, room players
  and creatures, possessions — `client/engine/snapshot.py`) and
  `--wait-for TEXT [--timeout N]` stays attached until a story line
  holds it; both read-only, nothing typed at the game, nothing echoed
  (#216). Use it instead of ad-hoc socket drivers; the `drive` skill
  (`.claude/skills/drive/SKILL.md`) is the procedure for Claude, and
  the `experiment` skill (`.claude/skills/experiment/SKILL.md`) the
  method for testing a mechanic on a live session — results go to the
  docs, the issue and the fixtures, never to the skill.
- `client/game/wounds.py` — HEALTH parsed into wounds by area, severity
  (1-8) and kind; `wounds_data.py` is generated from the wiki by
  `tools/wound_tables.py`, never hand-edited. `;tend` and `;hunt`'s
  wound floor read it. Model: docs/wounds.md. `client/game/herbs.py`
  answers a parsed wound with the herbs that treat it and the shops
  that stock them (`herbs_data.py`, generated from the wiki by
  `tools/herb_tables.py`); Knife Clan's remedy cookies and the retired
  NPC healer are captured there. `scripts/heal.py` eats them and
  buys the missing ones at the herbalist (#198); `;heal npc` walks
  to the nearest NPC healer instead (Shard's Quentin: DEMEANOR
  FRIENDLY EMPATH, LIE DOWN, Dokoras per part, #218) — what heals
  nerve damage and internal scars no herb touches. Model: docs/healing.md.
  `client/game/empathy.py` + `;empath` (`scripts/empath.py`) are the
  Empath's side: TOUCH <patient> (the listing arrives on the familiar
  stream), TAKE every wound most urgent first (bleeding, severity,
  torso before limbs, fresh before scars) on one TOUCH per round,
  another round for the scars that bared, then Heal Wounds / Heal
  Scars on himself worst first off HEALTH (2026-09-26).
- `client/game/profile.py` — per-character profiles
  (`~/.revenant/profiles/<name>.json`): the quirks `;hunt` must not
  hard-code (weapon, stance, skin, pouch, bundle, buffs, the magic
  skill to train by recasting, floors, ground, home; `weapons` — the
  turns one hunt trains, the emptiest pool first and each kept until
  its skill reaches `weapon_target` (30), "handaxe:Small Edged:sack",
  "fists:Brawling", a locked skill's turn sat out — and `brawling`,
  the fists turn's PUNCH/KICK/ELBOW, #238). FIELDS is the
  schema; the GUI's Character Profile dialog builds itself from it.
  `hunts` (hand-edited, kept by the dialog) names hunt styles — a
  partial profile plus `until` (lock / boxes / kills) — that `;hunt
  <style>` or a plan task's args lay over the profile: one hunt to
  train, one to farm boxes for `;boxes` (#299).
  `scripts/skins.py` sells the worn bundle at the nearest tannery.
  `scripts/cast.py` (`;cast`, #225) is that cast loop on its own —
  the first buff on the mana ramp with the cambrinth and a POWER a
  minute, for a gondola ride or a wait at an altar, until the skills
  lock. `client/game/buffs.py` is the profile's buffs kept up, the
  training casts (the mana ramp, capped at DISCERN's estimate of the
  caster's most since 2026-09-20) and the targeted casts at the prey
  (`debilitation`, `targeted`: Debilitation and Targeted Magic, in
  turn with the training cast), shared by `;hunt` and `;athletics`'
  wait filler. Model and assumptions: docs/hunting.md.
- `client/game/training.py` — per-character training plans
  (`~/.revenant/training/<name>.json`, File → Training Plan… in the
  GUI or hand-edited, `;train init`
  writes a starter): tasks tying skills to the script or command loop
  that trains them, the target mindstate, the safe rooms, the rest
  floor. The pure decisions (next task, satisfied, rested, safe-room
  rotation) live here; `client/game/drain.py` is how fast a pool
  drains — linear, 1.14 / 0.91 / 0.65 buckets a 200 s pulse for a
  primary / secondary / tertiary skill, fitted from ;xp's rows, the
  guilds' skillset table beside it — and a rest opens with its guess
  at the rest's length (#300); it also values a bucket: 8.35 / rank
  of the wiki's pool / 34, a rank costing 200 + n bits, fitted over
  ranks 10-100 (`ranks_from`, `tools/experience_fit.py`, #332); `scripts/train.py` is the loop, orchestrating
  other scripts through the handle's `run`/`is_running`/`tell`/`kill`,
  and with the plan's `soul: on` runs the soul deeds (`;soul badge`,
  `tithe`, `pray`) in its rests, taking a hand-started `;soul keep`
  over — never a prayer mid-hunt (#227) — and with a `tdp` list spends
  TDPs through `;tdp`, by the plan's stat targets or the guild's tiers
  on `auto` (#230): a `tdps` task (`;tdp plan`, up to three points)
  wherever the order puts it, and in the rests. Model: docs/training.md. `client/game/tdp.py` is the stat side:
  the game's TDP quotes parsed, the wiki's cost formula, ;tdp's
  goals; `scripts/tdp.py` walks to the tagged trainer and buys one
  confirmed point at a time, and a run that bought one ends with
  `;sheet info` so the new stat is on record at once (#303). `client/game/money.py` is coins both ways
  (denomination lists, copper, INFO's carried and owed), shared by
  `;sheet`, `;wealth` and `;debt` (`scripts/debt.py`: fetch the
  shortfall from the teller, PAY ALL at the debt office); `;skins`
  (`scripts/skins.py`) sells the skin bundle `;hunt` wears at the
  nearest tannery, then every loose skin in a hand or the loot
  container one at a time (#261), and keeps the rope.
  `client/game/repair.py` + `;repair` (`scripts/repair.py`, #307): the
  gear APPRAISEd QUICK, the wiki's condition phrase read as a health
  band, every piece at or below the profile's `repair_floor` (80) given
  twice to the nearest `repair` room's repairman (the estimate lapses
  in ~20 s; the second GIVE pays), the ticket STOWed, waited out and
  handed back, the piece worn again; a short purse fetched from the
  teller; `;repair tools` ANALYZEs the profile's `repair_tools`
  (APPRAISE names no condition for a tool) and takes the worn ones
  to the Engineering Society's Rangu, the Crossing's crafting-tool
  repairman (2026-09-26). `client/game/bank.py` + `;bank`
  (`scripts/bank.py`, #235): the purse banked — every foreign coin
  EXCHANGEd at the map's `exchange` room into the province's own,
  DEPOSIT ALL at the `bank` room, `keep=N` copper withdrawn back;
  a skill-less `;train` task runs it once a cycle, coins weigh.
  Selling and banking are distinct tasks (the operator, 2026-09-20),
  and `;skins bank` runs `;bank` rather than a deposit of its own.
  `client/game/attune.py` is power walking: a loop of street rooms
  joined by two-way compass moves and the sixty-second timer per
  room; `scripts/attune.py` POWERs round it until mind-lock, or in
  place with `here` for Moon Mages. `client/game/seek.py` walks the
  same loop reading each room's listing (the parser's `room_objs`)
  for a wandering NPC; `scripts/seek.py` stops in the room that has
  it (#207). `client/game/perform.py` is the song per rank band and
  PLAY's wordings; `scripts/perform.py` plays the profile's
  `instrument` until mind-lock (#208), cleaning it once with the
  profile's `instrument_cloth` when PLAY calls it dirty (#233).
  `client/game/appraisal.py` is the APPRAISE rotation — the
  profile's `appraisal_items`, else everything worn or held per the
  parser's `possessions`, a pouch and a bundle first — and
  `scripts/appraise.py` APPRAISEs them QUICK until Appraisal
  mind-locks, dropping what the game cannot find (#275).
  `client/game/research.py` + `;research` (`scripts/research.py`,
  #327) are a Barbarian's MEDITATE RESEARCH — the emptiest of
  Augmentation, Warding and Utility researched a minute apart, by
  combat-trainer's MONKEY / TURTLE / PREDICTION, until they lock;
  docs/barbarian.md indexes the Barbarian facts (Inner Fire, the
  ability verbs, Expertise) and what ;hunt still lacks for one (#328).
  `client/game/boxes.py` is a box picked open in words — the wiki's
  seventeen IDENTIFY readings, the caution per reading, DISARM /
  PICK / OPEN's outcomes after dr-scripts' pick.lic, none captured
  yet — and `scripts/boxes.py` (`;boxes`, #293) works the loot
  container's boxes for Locksmithing: identify, disarm, identify,
  pick (the profile's `lockpick` in hand or the worn
  `lockpick_ring`, refilled at Ragge's when it runs empty —
  `lockpick_refill` picks of `lockpick_kind`), open, loot out, the empty box DISMANTLEd (binned through
  discard.py when that fails, so `droppable` lists the box nouns), a frog
  trap's toad waited out, a longshot
  reading put back unless its trap is a nuisance one (frog, laughing
  gas, mime...: tried careful; a deadly or unknown trap never; a lock
  past the reading tried careful too; `safe` puts every one back), a sprung trap judged by the health and wound
  floors, the profile's `hindering_gear` (knuckles, gauntlets) off
  before the first box and worn back after, even after a `;stop`.
  `client/game/remedies.py` is the Remedies craft — the chapter-3
  salves and their herbs, CRUSH's captured answers — and
  `scripts/remedies.py` crushes a salve step by step for Alchemy,
  putting in the water, the page's second herb and the profile's
  `catalyst` (a coal nugget) as the game asks, re-studying a spent
  page; `;remedies work` runs the society's orders as a living —
  the logbook's open order resumed or the master asked wherever he
  wandered to in the building (`building_rooms`, 2026-09-23; again, for
  an item the book or the Supplies lacks), each stack crafted and
  bundled, the herbs, water and coal bought as they run out with
  the coins fetched from the teller, the logbook handed in for the
  pay, the next order asked, the crushes going on at mind-lock
  (#284). `client/game/workorders.py` ledgers every order handed
  in — history.db's `work_orders`: pay, materials at catalog
  prices, coin spent, crushes and their roundtime, minutes, ranks —
  the order in progress kept in `~/.revenant/workorders/<name>.json`
  across runs (#288) — and `;remedies ledger`
  prints the totals and the profit per item.
  `client/game/soul.py` is a
  Paladin's soul: the seven states and eleven pool levels parsed off
  RUB, EXHALE and the arch, the deeds that raise it (the 5-silver
  tithe every 4 h, the Chadatru prayer knelt until "soothing
  sensation") and their timers in `~/.revenant/soul/<name>.json`;
  `scripts/soul.py` reads it (an orb, else the nearest soulstone arch
  for the state, #231), `keep`s the deeds running while the reading
  says below pristine — a fresh pristine reading gates every deed,
  in `;train`'s rests too — and runs the
  Glyph of Warding scene at the guild orb once pristine and full
  (#224). Model: docs/soul.md; docs/paladin.md indexes every
  Paladin fact the scripts rest on — circles, soul, glyphs, smite,
  spells, the guild's rooms — with the model per fact linked (#228).
  `client/game/scholarship.py`
  is the Lorethew library's grammar and the reader's page loop;
  `scripts/scholarship.py books` reads every book on the profile's
  `library` shelves and returns each with STOW (#210); the read
  times persist in `~/.revenant/scholarship/<name>.json`, and a run
  with every book within its timer ends rather than idling the
  `;train` slot (#255). `client/game/encumbrance.py` is the
  wiki's capacity rule (a burden level is a band of weights for the
  character's Strength + Stamina) and the readings' log; `scripts/enc.py`
  reads it and `;enc ballast` pins the load with coins. Model:
  docs/encumbrance.md. `client/game/status.py` is the parser's state in
  words — `s.status.stunned`, `.posture`, `.hands_empty`, `.roundtime`,
  `.mindstate(skill)`, `.summary()`, derived on every access; scripts
  read it rather than spelling indicator ids, and `;status` prints it.
  `client/game/justice.py` reads RECALL WARRANT (clean captured, wanted
  by shape) and `;warrant` prints it — the free check before a walk
  into a town (2026-09-22).
  `client/game/novelty.py` is what is new or addressed at the
  character, after dr-scripts' status-monitor.lic: `address` (a
  bare-named player or GM whispering, speaking, thinking or gesturing
  to you — never an NPC with an article or one the room's title,
  listing or creatures name (a shopkeeper, #310), never the
  operator's own characters), `hidden_command` ("J_u_M_p", an emote verb),
  `broadcast` (an `ooc` staff notice with `#drprime`), and the
  `Novelty` store (numerals and currency scrubbed, a line flagged once
  and remembered in `~/.revenant/sentinel/<name>.json`, the same line
  more than 4 times in 20 or 6 near-duplicates in 90 s as spam);
  `scripts/sentinel.py` (`;sentinel`, autostarted, #276) runs every
  line through it, rings the bell and echoes `SENTINEL:` on an
  address, a hidden command or spam, runs settings' `alert_command`,
  and — only while a script acts on the character (`s.running_scripts()`
  minus the background monitors), unanswered by `;sentinel ok` within
  `sentinel_grace_minutes`, with `sentinel_logout` on (off by default,
  2026-09-26) — gives `;train` its return word and QUITs; new lines and arrivals go
  to the Attention dock. Never a canned reply, never a command found
  in text executed.
  `client/game/teaching.py` is a class between two characters —
  TEACH's and LISTEN's captured lines, the commands, the args —
  `scripts/teach.py` keeps a class offered (again when the students
  leave) and `scripts/listen.py` joins one and holds on the taught
  skill's mindstate, rejoining when it ends; `;train` runs `listen`
  as a task, `;teach` runs on the teacher's side (2026-09-22).
  `client/game/helper.py` is the task's helper character: the
  teacher's session found in the registry or spawned off the
  keychain without a window, walked to the room, started on its
  script through the wire tagged `train`, returned and logged out
  (`scripts/logout.py`, QUIT from inside) when the loop moves on;
  the task's `helper*` keys name it (2026-09-22). The spawn marks
  the session (`REVENANT_SPAWNED_BY`, `REVENANT_PARENT_PORT` → the
  registry row's `spawned_by`, `parent_port`): a later loop adopts a
  marked session as its own to log out, and the session logs itself
  out once its parent's port has refused two heartbeats (#296).
- `client/game/walker.py` + `client/game/mapdb.py` — travel on the community map
  (downloaded, never vendored). Twins: the map lists some rooms twice,
  one uid-less; `same_place` handles it. A climb turned back for
  footing gets one retry standing with the named items stowed, then
  a stop that says so (#157). The Faldesu ferry between the Crossing
  and Riverhaven and the Obsidian Pass gondola are ridden (the
  map's bescort edges, #205, #211); other bescort routes stay
  unwalkable. A way the game closes to the character ("not
  experienced enough to go there") and a climb turned back twice are
  routed around, never retreated from (#209, #211), and the skill
  gates the map writes as Ruby timeto values are honored against
  the exp window's ranks before the first step (#214). A room the
  map lists without exits is left by the compass, OUT first, and
  the way that landed is written to `~/.revenant/mapdb/local.json`
  for the next plan (#229). Model: docs/movement.md.
- `client/game/possessions.py` — possessions by exist id: the parser's
  listing built into items, `find(items, noun)` for a script that
  wants exactly this orb (`get #<id>`), `rows()` for `;sheet inv`'s
  table, which stores `exist` / `container_exist` beside the names
  (#184). Exact as of the last INV LIST, which costs roundtime.
- `client/game/rested.py` — the rested-experience footer parsed
  (shared by the parser, `;sheet` and `;xp`) and `burning(previous,
  current)`, the per-minute flag `;xp` writes as `is_rexp` on every
  mindstate row and beholder shades the 3x windows from (#176).
- `client/game/climbs.py`, `circles.py`, `eltime.py`, `inventory.py`,
  `history.py`, `climblog.py` (the `climbs` table `;climbexp` fills:
  one row per climb attempt with rank, stats, load and outcome, #159);
  `client/ui/textfont.py`, `window_layout.py`,
  `streamroute.py`, `maplayout.py`, `command_history.py`,
  `crashguard.py`, `highlights.py`, `inputfocus.py`, `roomids.py`
  (the map id after the room title, paired with the "room" frame in
  either arrival order; setting `show_room_ids`);
  `client/engine/reader.py`, `roster.py`, `lnet_login.py`;
  `client/settings.py` — Qt-free logic with the tests; the GUI only
  draws.
- `client/gui/client_gui.py` — the PyQt6 window: menus, layout
  restore, dispatch of each stream to its widget, styled text,
  reconnect. The docks' widgets sit beside it: `compass_dock.py`,
  `clocks_dock.py`, `input_strip.py` (command line, vitals bars,
  status strip, what each hand holds, RT/CT timers), `map_dock.py`, `injuries_dock.py` (the
  game's injuries panel as badges, from the `injuries` stream, #163),
  `spells_dock.py` (the running spells with countdowns and the
  prepared one, from the `spells` stream the engine emits on any
  change of `active_spells`/`prepared_spell`; the raw `percWindow`
  text is dropped by the GUI, #175), `dock_collapse.py` (every dock's
  title bar with its fold button; the folded set saved beside the
  layout keys, #180; a dock in a tab group never folds — a folded tab
  capped the whole group's height), `text_views.py` (the story/stream views and
  per-view fonts).
  `chat_window.py` — the
  standalone LNet window; `settings_dialog.py`, `profile_dialog.py`,
  `plan_dialog.py` (the ;train plan: plan form, ordered task list,
  task form, built from training.PLAN_FIELDS / TASK_FIELDS),
  `login_dialog.py`, `highlights_dialog.py`. `jumplist.py` is the
  taskbar button's right-click menu on Windows — "Pick a
  character..." and every played character as launcher tasks,
  registered at GUI start by a ctypes COM shim, failures logged and
  ignored (#226).
- `client/engine/launch.py` — the `revenant` console script and the picker; one
  session per character on its own port, registry in
  ~/.revenant/sessions.json (each row carries `attached`, the window
  count the session keeps current, so the picker shows online rows
  highlighted under their own header and opens on a detached one,
  #158; the file is written atomically, a failed read is never
  rewritten, a row is pruned only on two refused probes, and the
  session re-asserts its row every thirty seconds, #160). It exec's `client/engine/guiboot.py`, which arms
  faulthandler and reports a GUI that cannot start (startup-/faults-
  logs, a message box on Windows) before importing the GUI.
- `chat/chat.py` — LNet protocol (stdlib only); `chat/commands.py` — the
  `;chat` grammar the script and the window share.
- `beholder/beholder/data.py` — stdlib sqlite3 over history.db; `app.py` — Dash.
