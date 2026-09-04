# Architecture, with its history

How the pieces fit and why each one is shaped the way it is: one pipeline, one parser, several processes, told module by module with the issue numbers of the decisions. This is the long-form companion to the module map in `.claude/CLAUDE.md`; read that for the shape and this for the reasons.

The text below accreted a sentence per change as features shipped, so it doubles as a record of what was learned in the field: the socket that would not wake on Linux, the map twins, the dock layout that aborted inside Qt. Where a `docs/*.md` model file exists, it holds the captured evidence; this page holds the plumbing.

One pipeline, one parser, several processes:

- `client/client/netsock.py` — minimal buffered TCP socket (telnetlib-shaped
  API: `read_until`, `read_very_eager`).
- `client/client/login.py` — eaccess handshake. Credentials: password lives in
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
- `client/client/xml_data.py` — XMLParser target holding parsed game state
  (indicators, compass, prompt, vitals, hostile creatures from
  `<crtrStatus>`) — docs/protocol.md is the wire-protocol reference it
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
  `scripts/xp.py` snapshots it to `~/.revenant/xp.db` for history.
- `client/client/core.py` — `Engine`: owns a connection, feeds lines through
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
- `client/client/session.py` — the detachable session daemon
  (`python -m client.session`): logs in, owns the game socket, serves
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
  **`;reexec` is POSIX-only**: on Windows it refuses with a note and
  changes nothing (WinSock handles aren't CRT fds and exec spawns
  rather than replaces, #38; a socket.share() port is #129). Scripts
  reload from disk on every start, and so do the client/ helper
  modules they lean on (`scripting.RELOADABLE_MODULES`: probe,
  walker, mapdb, inventory, circles, climbs, eltime, settings,
  textfont — pure logic, reloaded in dependency order when their
  file changed since import, #138), so a script or walker edit
  reaches a running session on any platform via `;stop <name>` and
  running it again; developer mode (settings `dev_mode` / File →
  Settings, or `REVENANT_DEV=1`) reports a start slower than
  `scripting.SLOW_LOAD_SECONDS` with what reloaded. Everything else — session, core, xml_data, the
  GUI — needs `;reexec`, or on Windows a new session: close the
  window (quit) and relaunch. File → Detach is the wrong move: it
  leaves the session running and a relaunch reattaches to the old
  code.
- `client/client/scripting.py` — script engine. Scripts are `main(s)` Python
  files in `scripts/` (repo root), run as threads in the session, controlled
  by `;`-commands typed in any frontend (`;list`, `;help [x]`, `;run x`,
  `;stop x`). `;help` renders module docstrings — write them as the user
  manual.
  Handle API: put/get/waitfor/waitrt/echo/emit/sleep/state/args — `emit`
  targets an arbitrary stream (e.g. "thoughts"). `scripts/lnet.py` uses it
  to mirror LNet chat into the Thoughts window (`;lnet`); the command
  grammar and dispatcher it shares with the standalone chat window live
  in the stdlib-only `chat/commands.py`, and `client/gui/chat_window.py`
  (`revenant-chat [name]`) is that window: one of the user's own
  characters (offered from the cached rosters and nothing else —
  LNet names are character names), no game session, password from
  the keychain via the Qt-free
  `client/lnet_login.py` (service "revenant-lnet"; a rejected login
  asks once with a remember checkbox), one worker thread owning the
  socket as the script does (#141). `;tend`
  bandages bleeders (watch mode wakes on soak-through); `;wealth`
  passively logs teller balance statements into xp.db.
  `client/client/probe.py` is the ask-and-classify helper the keyword
  scripts (;mechlore, ;favors) share: send a command, gather the answer
  through its roundtime, match it against an ordered outcome table.
  Sessions autostart the xp history logger, the beholder dashboard
  server in quiet mode, the character-sheet snapshotter (`;sheet`:
  INFO + EXP ALL into stats/sheet_skills/character tables every 3h;
  `;sheet inv` additionally asks INV LIST into the `inventory` table
  — on demand only, never scheduled, because INV LIST costs 4-5s of
  roundtime. The autostarted script waits on its command queue
  between snapshots, so `;sheet inv` typed at it takes one inventory
  snapshot and the schedule carries on; from cold it snapshots and
  exits (#122). `client/inventory.py` flattens the indented tree
  into rows naming each item's container, identical items collapsed to
  a quantity, #117. Scripts read answers through `probe.collect`,
  which glues the per-segment pieces the session delivers back into
  whole lines — the last piece of a line carries the newline — so
  <d>-linked item lines keep their indentation, #123),
  and the death watchdog (`;deathwatch`: departs an unattended corpse
  with the best variant the favors afford before it decays —
  docs/death.md holds the captured model)
  (`session.autostart_scripts`; `;stop <name>` opts
  a session out; the GUI's File → Settings dialog over
  `client/settings.py` / ~/.revenant/settings.json turns them off
  durably, and REVENANT_NO_XP=1 / REVENANT_NO_BEHOLDER=1 override
  everything for one launch — quit-on-close lives there too, and so
  does the game text's font: `font_family` / `font_size`, normalized
  by the Qt-free `client/textfont.py` and applied live to every text
  view and the input line, the Experience dock keeping its
  fixed-pitch family, #118);
  `;beholder` opens the dashboard in the browser, and the GUI embeds it
  via View → Experience History (QWebEngineView, lazy-created, browser
  fallback when QtWebEngine is missing).
- `client/client/mapdb.py` — the community DR map database (elanthia-online
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
  `client/client/walker.py` (locate/walk; model in docs/movement.md) is
  the shared travel engine; `scripts/go2.py` is the command on top, and
  `;favors` (scripts/favors.py) rides it for the favor-orb run — grotto
  ritual, attended puzzles, temple altar offer (docs/favors.md).
- `client/client/climbs.py` — climbing spots with Athletics rank
  bands and conditions, keyed to the community map's room ids
  (never written into the community db, which refreshes wholesale);
  `;athletics` derives its training ladder and its ;athletics-list
  advice from this one table (#87). Bands from Elanthipedia's
  Climbing and Swimming list; rank 100+ trains in town on the
  Crossing battlements.
- `client/client/circles.py` — circle requirements, Qt-free: every
  circled guild's Elanthipedia rate table + the slot/soft-requirement
  model; `;circle` (scripts/circle.py) and beholder's Circle-gates
  view report what gates the next circle from the latest ;sheet
  snapshot (which records guild). docs/circles.md holds the model,
  its captured guildleader validation, the wiki corrections, and the
  open anomalies.
- `client/client/eltime.py` — the Elanthian clock, Qt-free: date, anlas,
  and moon phases computed from real time (docs/eltime.md holds the
  model and its captured evidence). `scripts/clock.py` (`;clock`) is the
  ntpdate: TIME + OBSERVE MOONS, calibration stored in settings
  (`eltime_offset_seconds`, `eltime_moons`).
- `client/client/gui/client_gui.py` — PyQt6 frontend. GUI-thread safety via
  the `game_text` pyqtSignal; a sys.excepthook (`client/crashguard.py`,
  Qt-free) keeps the window alive when a Qt slot crashes, logging the
  traceback and surfacing it in the main window + status bar (#94);
  the reader thread runs `client/reader.py`'s Qt-free pump, which
  surfaces EOF and crashes in the status bar instead of dying
  silently (#96); stream docks route thoughts/spells/arrivals/deaths
  (the stream -> dock table and the rule that a "clear" wipes only
  that stream's own dock live in the Qt-free `client/streamroute.py`,
  so tests reach them headless — a clear for an undocked stream like
  `inv` must be dropped, never applied to the main window, #109);
  compass dock renders the `"compass"` stream; the Map dock draws
  the community map around the character from the `"room"` stream
  (grid layout in the Qt-free `client/maplayout.py`, drawing in
  `client/gui/map_dock.py`; click a room to ;go2 it; docked on the
  right with a 320px size hint, the scene padded by half a viewport
  so the current room always centres — alone on the left with no
  hint it opened as a clipped strip, #146); the clocks dock ticks
  Elanthian time, moons, Stockholm/Chicago, and (via a Settings toggle)
  Earth's moon; roundtime/casttime count down beside the input line
  under a row of vitals bars (health/fatigue/spirit/concentration,
  mana for casters), next to the status strip (posture + stunned/
  bleeding/hidden badges, DEAD in alert red); the input line has
  shell-style Up/Down history (client/command_history.py, Qt-free)
  and re-selects after send so Enter repeats; the title bar names the
  logged-in character, and each character's window keeps its own saved
  dock layout (`client/window_layout.py`, Qt-free; the unscoped legacy
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
  (`client/highlights.py`, ~/.revenant/highlights.json) color matched
  spans over any base style; View → Reload Highlights re-reads them.
- `client/client/launch.py` — the `revenant` console script: attaches
  the GUI to the right session, spawning one when needed. Characters
  run side by side, one session/window each on its own port: sessions
  register in ~/.revenant/sessions.json (client/session.py; pruned by
  connectability), `revenant <name>` attaches to that character's
  session or spawns on a free port, and `--pick` (the Start Menu
  shortcut) offers running sessions to attach plus every cached
  character on every account to launch (#58).
