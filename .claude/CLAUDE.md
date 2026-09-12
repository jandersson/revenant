# Revenant

A pure-Python client stack for DragonRealms (a Simutronics MUD). uv workspace
monorepo: `client` (game client), `chat` (LNet chat), `beholder` (Dash
dashboard over the history the `;xp` script logs to ~/.revenant/history.db).
`launcher/` bridges to the external Ruby toolchain; revenant itself never
grows Ruby dependencies (docs/why-python.md). docs/architecture.md tells the
long version of everything below, with the issue history.

## Commands

```sh
uv run revenant                      # launch: spawn/attach a session + GUI
uv run revenant-chat [name]          # the standalone LNet window
uv run pytest client/tests -q        # client suite (real sockets, threads)
uv run pytest client/tests_gui -q    # the window and docks, offscreen PyQt6
uv run pytest beholder/tests -q
uv run pytest chat/tests -q
uv run ruff check client chat beholder scripts    # CI enforces
uv run ruff format client chat beholder scripts   # CI enforces --check
uv run python tools/docker_tests.py  # CI's Linux battery (--all: 3.10-3.12);
                                     # catches Linux-only socket hangs
uv run python tools/roster_sweep.py  # ;sheet every cached character (--list)
```

CI runs ruff and pytest on 3.10–3.12 on ubuntu plus 3.12 on macOS. Run
every check above — ruff check, ruff format --check, and all four
suites — before every push, never only the suite a change touched; a
green remote run is expected, not hoped for.

## Architecture

One pipeline, one parser, several processes. Session and GUI are separate
processes; the session owns the game socket and hosts scripts.

The `client` package is three subpackages and two shared modules:
`engine/` (the connection and the session process: socket, login,
parser, engine, session, scripting, spawning), `game/` (the Qt-free
models scripts lean on — what `RELOADABLE_MODULES` reloads, plus
wounds, circles, eltime, history), `ui/` (toolkit-free frontend logic
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
  the engine's exp rewrite ends with that footer as a line.
- `client/engine/core.py` — `Engine`: feeds lines, emits synthetic streams
  (compass = room-arrival signal, room, vitals, indicators, character,
  timesync, roundtime/casttime, bell). It appends "\n" only to the last
  piece of a line per stream; frontends never add line breaks.
- `client/engine/session.py` — the detachable daemon: JSON frames on
  127.0.0.1:4242, backlog replay for late attachers (transient streams
  excluded), the script engine, `;reexec` (exec on POSIX; on Windows a
  spawned child adopts the game socket via socket.share over stdin, #129;
  the child's stderr goes to `logs/reexec-<stamp>.err`, and a handoff
  that fails keeps the old process serving, #162).
- `client/engine/scripting.py` — scripts are `main(s)` files in `scripts/`,
  loaded fresh from disk on every start; the pure-logic helpers in
  `RELOADABLE_MODULES` reload with them — as fresh module objects, so
  a running script keeps the functions it imported and their globals
  while the next start gets the new code (#181). Handle API:
  put/get/waitfor/waitrt/echo/emit/sleep/command/state/args, plus
  run/is_running/tell/kill/crashed for a script that drives other
  scripts (`;train`). `;help` renders docstrings.
- `client/game/probe.py` — ask-and-classify shared by keyword scripts;
  `collect` glues per-segment pieces into whole lines and reads the
  story and the `combat` stream both (every swing and kill line
  arrives in `<pushStream id="combat"/>`; a story-only read sees no
  kill, 2026-09-12).
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
  Use it instead of ad-hoc socket drivers; the `drive` skill
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
  NPC healer are captured there. Model: docs/healing.md.
- `client/game/profile.py` — per-character profiles
  (`~/.revenant/profiles/<name>.json`): the quirks `;hunt` must not
  hard-code (weapon, stance, skin, pouch, bundle, buffs, the magic
  skill to train by recasting, floors, ground, home). FIELDS is the
  schema; the GUI's Character Profile dialog builds itself from it.
  `scripts/skins.py` sells the worn bundle at the nearest tannery.
  `client/game/buffs.py` is the profile's buffs kept up and the
  training casts (the mana ramp), shared by `;hunt` and `;athletics`'
  wait filler. Model and assumptions: docs/hunting.md.
- `client/game/training.py` — per-character training plans
  (`~/.revenant/training/<name>.json`, File → Training Plan… in the
  GUI or hand-edited, `;train init`
  writes a starter): tasks tying skills to the script or command loop
  that trains them, the target mindstate, the safe rooms, the rest
  floor. The pure decisions (next task, satisfied, rested, safe-room
  rotation) live here; `scripts/train.py` is the loop, orchestrating
  other scripts through the handle's `run`/`is_running`/`tell`/`kill`.
  Model: docs/training.md. `client/game/tdp.py` is the stat side:
  the game's TDP quotes parsed, the wiki's cost formula, ;tdp's
  goals; `scripts/tdp.py` walks to the tagged trainer and buys one
  confirmed point at a time. `client/game/money.py` is coins both ways
  (denomination lists, copper, INFO's carried and owed), shared by
  `;sheet`, `;wealth` and `;debt` (`scripts/debt.py`: fetch the
  shortfall from the teller, PAY ALL at the debt office); `;skins`
  (`scripts/skins.py`) sells the skin bundle `;hunt` wears at the
  nearest tannery and keeps the rope.
  `client/game/attune.py` is power walking: a loop of street rooms
  joined by two-way compass moves and the sixty-second timer per
  room; `scripts/attune.py` POWERs round it until mind-lock, or in
  place with `here` for Moon Mages. `client/game/encumbrance.py` is the
  wiki's capacity rule (a burden level is a band of weights for the
  character's Strength + Stamina) and the readings' log; `scripts/enc.py`
  reads it and `;enc ballast` pins the load with coins. Model:
  docs/encumbrance.md. `client/game/status.py` is the parser's state in
  words — `s.status.stunned`, `.posture`, `.hands_empty`, `.roundtime`,
  `.mindstate(skill)`, `.summary()`, derived on every access; scripts
  read it rather than spelling indicator ids, and `;status` prints it.
- `client/game/walker.py` + `client/game/mapdb.py` — travel on the community map
  (downloaded, never vendored). Twins: the map lists some rooms twice,
  one uid-less; `same_place` handles it. A climb turned back for
  footing gets one retry standing with the named items stowed, then
  a stop that says so (#157). Model: docs/movement.md.
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
  status strip, RT/CT timers), `map_dock.py`, `injuries_dock.py` (the
  game's injuries panel as badges, from the `injuries` stream, #163),
  `spells_dock.py` (the running spells with countdowns and the
  prepared one, from the `spells` stream the engine emits on any
  change of `active_spells`/`prepared_spell`; the raw `percWindow`
  text is dropped by the GUI, #175), `text_views.py` (the
  story/stream views and per-view fonts).
  `chat_window.py` — the
  standalone LNet window; `settings_dialog.py`, `profile_dialog.py`,
  `plan_dialog.py` (the ;train plan: plan form, ordered task list,
  task form, built from training.PLAN_FIELDS / TASK_FIELDS),
  `login_dialog.py`, `highlights_dialog.py`.
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

Traps that cost time before:
- A running session does not see edits to `client/` modules outside
  `RELOADABLE_MODULES` until it re-execs or restarts. On Windows only a new
  session does it: close the window (quit) and relaunch. Detach leaves the
  old process running.
- Restoring a saved dock layout onto a shown window can abort inside Qt;
  the GUI learns its character before building the window and restores
  first (#124, #140).
- INV LIST costs roundtime: never scheduled, `;sheet inv` only. SPELL
  costs none and rides the 3-hourly snapshot (`spells` table, `spell_slots`).

## Conventions

- **Bottom line up front, everywhere.** Chat replies, issues, commits,
  docstrings, docs: the first sentence is the answer, the outcome, or the
  ask, and stands alone. Reasoning and caveats follow, never lead.
- `.claude/learnings.md` holds what tripped agents up before (edit
  scripts, formatting, Windows restarts, evidence gathering). Read it
  once per session; add a line when something new bites.
- Every behavior change ships with tests in `client/tests/`; bug fixes get
  a regression test, ideally from captured game traffic. Tests are the
  manual: plainly named, input → expected response. Captured fixtures pin
  what we believe the server sends; a fixture that turns out wrong is an
  assumption to correct, not a test to delete.
- Every script's module docstring is its manual, and the engine serves
  it two ways: `;help <name>` and `;<name> help` (the latter answered
  before the script is started or, when it runs, handed the word). So
  a script never parses "help" itself, and its docstring opens with
  the usage lines — every verb and option, one per line — before the
  story. Two ways to end a script, the same for all of them: `;stop
  <name>` quits at once, wherever the character stands; a typed
  `;<name> return` is the graceful end (finish the kill or the
  perceive, walk home). Never a `stop` word of a script's own.
- Every change freshens the documentation it staled, in the same commit:
  the module docstring (it is the `;help` manual), README claims, this
  file, docs/architecture.md, and any docs/ model whose assumptions moved.
  Documentation is BLUF: the first two sentences carry what it does and why.
- **Credit every source in docs/bibliography.md.** A feature that drew on a
  Lich script, the lich-5 commons, dr-scripts, a Genie plugin, a wiki page,
  another client, or someone's protocol notes gets a row (source linked,
  path verified) in the same commit, and the docstring names the source.
  `client/tests/test_bibliography.py` fails a script that cites one without
  a row. General resemblance is not an entry.
- No PII in the repo, ever: no real names, accounts, or anything that
  identifies the operator, in code, tests, docs, commits, or fixtures. The
  synthetic cast is Lanival, with Sable (his twin) and Uthmor; accounts are
  TESTACCT. Scrub captured traffic before committing it. No exceptions.
- Never store credentials in files, even gitignored ones; the keychain is
  the only path.
- Research a game mechanic on Elanthipedia before automating it.
- **Another player's room is theirs.** A room someone else is already
  hunting or training in ("Also here: …") is left, not shared: a
  script arriving in one moves on to the next room or rung and never
  starts a fight there (`;hunt` and `;athletics` read the parser's
  `room_players` on every arrival), and Claude driving by hand checks
  the room's players before any action that takes a kill (#178,
  2026-09-12). A crowd of creatures is not that rule: `;athletics`
  skips a rung or stop listing three (`room_creatures`, a climb gets
  interrupted), `;hunt` fights them — a full room is what a hunt farms.
- **Never DROP.** A dropped item is a lost item. A script drops only
  through `client/game/discard.py`'s `drop()`, which allows the
  built-in foraged junk (grass, grass rope) plus settings.json's
  `droppable` list and refuses everything else with an echo; a hand
  is freed with STOW from the parser's hand state, a load lightened
  by stowing or banking coins. No echo suggests dropping.
- **Claude drives a session only through `revenant-send --origin claude`**,
  so every line it sends shows in the window as `>> [claude] ...` and
  the operator can tell its commands from their own and from other
  tools. Never a bare send (that reads `[external]`), never an ad-hoc
  socket driver. Read-only commands (INFO, EXP, the stat and TDP
  quotes, VAULT TIME) may go out to answer a question; anything that
  acts on the character — moving, spending, training, wearing,
  dropping — needs the operator's say-so first, and stays in the
  allowlist gate (`REVENANT_ALLOW_SEND=1`) rather than a settings
  change. Say what was sent and what the game answered.
- Every feature gets a GitHub issue; every defect or gap found in passing
  gets one too, with the evidence, and is left alone unless it blocks the
  work. Every issue carries a label at creation: bug, enhancement, or
  question. Draft issue bodies in a file and pass `--body-file`.
- Written for a skimmer: issues and comments use bold section labels and
  numbered steps; commits are Conventional Commits (`type(scope): summary`)
  with short paragraphs, cause before fix.
- Threads + locks, not asyncio. Closing a socket does NOT wake a thread
  blocked in recv()/accept() on Linux (it does on macOS, so local runs
  miss it): always `shutdown(SHUT_RDWR)` before `close()`.
- Tests use real sockets on ephemeral ports; keep them hermetic (hold a
  bound socket rather than assuming a released port stays closed) and
  generous with timeouts. Don't import PyQt6 in `client/tests`; GUI
  behavior is tested in `client/tests_gui`, which runs real widgets on
  Qt's offscreen platform (its conftest sets `QT_QPA_PLATFORM` and
  points every file the window touches, QSettings included, at a temp
  dir). Test what pure tests cannot reach — a frame landing in its
  widget, a dock layout round trip — never Qt's own painting.
- macOS: the filesystem is case-insensitive (`.venv/bin/Revenant` collides
  with the `revenant` script); CPython finds a venv only when `pyvenv.cfg`
  sits beside the interpreter's parent, hence `.venv/branded/`.
- Logs: raw game lines append to `~/.revenant/logs/game-<stamp>.log`, LNet
  traffic to `lnet-<stamp>.log` (password redacted); both append-only,
  never rotated. The debug log is per process, size-capped, pruned at 7
  days. `REVENANT_LOG_DIR` moves all of it; tests isolate via conftest.
