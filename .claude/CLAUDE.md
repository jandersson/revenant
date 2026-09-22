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
uv run python tools/wiki.py "Soul system" [--grep WORD]  # an Elanthipedia page's raw
                                     # wikitext, cached under ~/.revenant/wiki (--list)
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
  (compass = room-arrival signal, room, vitals, indicators, character,
  timesync, roundtime/casttime, bell). It appends "\n" only to the last
  piece of a line per stream; frontends never add line breaks.
- `client/engine/session.py` — the detachable daemon: JSON frames on
  127.0.0.1:4242, backlog replay for late attachers (transient streams
  excluded), the script engine, a TCP keepalive on the game socket
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
  cleanup=True)` — for a `finally:` that puts an item back), plus
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
- `client/game/profile.py` — per-character profiles
  (`~/.revenant/profiles/<name>.json`): the quirks `;hunt` must not
  hard-code (weapon, stance, skin, pouch, bundle, buffs, the magic
  skill to train by recasting, floors, ground, home; `weapons` — the
  turns one hunt cycles per kill, "handaxe:Small Edged:sack",
  "fists:Brawling", a locked skill's turn sat out — and `brawling`,
  the fists turn's PUNCH/KICK/ELBOW, #238). FIELDS is the
  schema; the GUI's Character Profile dialog builds itself from it.
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
  rotation) live here; `scripts/train.py` is the loop, orchestrating
  other scripts through the handle's `run`/`is_running`/`tell`/`kill`,
  and with the plan's `soul: on` runs the soul deeds (`;soul badge`,
  `tithe`, `pray`) in its rests, taking a hand-started `;soul keep`
  over — never a prayer mid-hunt (#227) — and with a `tdp` list spends
  TDPs through `;tdp`, by the plan's stat targets or the guild's tiers
  on `auto` (#230): a `tdps` task (`;tdp plan`, up to three points)
  wherever the order puts it, and in the rests. Model: docs/training.md. `client/game/tdp.py` is the stat side:
  the game's TDP quotes parsed, the wiki's cost formula, ;tdp's
  goals; `scripts/tdp.py` walks to the tagged trainer and buys one
  confirmed point at a time. `client/game/money.py` is coins both ways
  (denomination lists, copper, INFO's carried and owed), shared by
  `;sheet`, `;wealth` and `;debt` (`scripts/debt.py`: fetch the
  shortfall from the teller, PAY ALL at the debt office); `;skins`
  (`scripts/skins.py`) sells the skin bundle `;hunt` wears at the
  nearest tannery, then every loose skin in a hand or the loot
  container one at a time (#261), and keeps the rope. `client/game/bank.py` + `;bank`
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
  `client/game/remedies.py` is the Remedies craft — the chapter-3
  salves and their herbs, CRUSH's captured answers — and
  `scripts/remedies.py` crushes a salve step by step for Alchemy,
  putting in the water, the page's second herb and the profile's
  `catalyst` (a coal nugget) as the game asks, re-studying a spent
  page; `;remedies work` runs the society's orders as a living —
  the logbook's open order resumed or the master asked (again, for
  an item the book or the Supplies lacks), each stack crafted and
  bundled, the herbs, water and coal bought as they run out with
  the coins fetched from the teller, the logbook handed in for the
  pay, the next order asked, the crushes going on at mind-lock
  (#284). `client/game/workorders.py` ledgers every order handed
  in — history.db's `work_orders`: pay, materials at catalog
  prices, coin spent, crushes and their roundtime, minutes, ranks —
  and `;remedies ledger`
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
  `client/game/teaching.py` is a class between two characters —
  TEACH's and LISTEN's captured lines, the commands, the args —
  `scripts/teach.py` keeps a class offered (again when the students
  leave) and `scripts/listen.py` joins one and holds on the taught
  skill's mindstate, rejoining when it ends; `;train` runs `listen`
  as a task, `;teach` runs on the teacher's side (2026-09-22).
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
  status strip, RT/CT timers), `map_dock.py`, `injuries_dock.py` (the
  game's injuries panel as badges, from the `injuries` stream, #163),
  `spells_dock.py` (the running spells with countdowns and the
  prepared one, from the `spells` stream the engine emits on any
  change of `active_spells`/`prepared_spell`; the raw `percWindow`
  text is dropped by the GUI, #175), `dock_collapse.py` (every dock's
  title bar with its fold button; the folded set saved beside the
  layout keys, #180), `text_views.py` (the story/stream views and
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

Traps that cost time before:
- A running session does not see edits to `client/` modules outside
  `RELOADABLE_MODULES` until it re-execs or restarts. On Windows only a new
  session does it: close the window (quit) and relaunch. Detach leaves the
  old process running.
- Restoring a saved dock layout onto a shown window can abort inside Qt;
  the GUI learns its character before building the window and restores
  first (#124, #140).
- INV LIST costs roundtime: the autostarted `;sheet` takes it once at
  login (the character is safe then) and never on the schedule after;
  `;sheet inv` on demand otherwise. SPELL
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
- Research a game mechanic on Elanthipedia before automating it,
  through `uv run python tools/wiki.py "<Title>"`: the page's raw
  wikitext (tables intact), cached under `~/.revenant/wiki/` for 30
  days — mechanics pages change rarely, a shop's stock now and then,
  and the game's own answers correct a stale page anyway — with
  `--refresh` for a page known to have moved and `--grep WORD` for
  the lines that matter. Never a summarizing fetch of a table.
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
  `droppable` list and refuses everything else with an echo — and
  puts a listed item in the room's trash (a bucket, a waste bin, a
  chute, off the parser's `room_objs`) before it ever DROPs; a hand
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
  change. Say what was sent and what the game answered. The session's
  own policy (`client/engine/policy.py`, #161) refuses an outside
  GIVE, SELL, WITHDRAW, TRAIN, QUIT, DROP of a non-junk item and the
  like whatever the gate says; a refusal reads "session: refused
  [claude] ..." in every window, and is the operator's to send.
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
