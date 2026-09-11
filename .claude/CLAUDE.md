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

CI runs ruff and pytest on 3.10–3.12 on ubuntu plus 3.12 on macOS. Run the
checks above before every push.

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
  characters are stripped; a BEL becomes a "bell" segment.
- `client/engine/core.py` — `Engine`: feeds lines, emits synthetic streams
  (compass = room-arrival signal, room, vitals, indicators, character,
  timesync, roundtime/casttime, bell). It appends "\n" only to the last
  piece of a line per stream; frontends never add line breaks.
- `client/engine/session.py` — the detachable daemon: JSON frames on
  127.0.0.1:4242, backlog replay for late attachers (transient streams
  excluded), the script engine, `;reexec` (exec on POSIX; on Windows a
  spawned child adopts the game socket via socket.share over stdin, #129).
- `client/engine/scripting.py` — scripts are `main(s)` files in `scripts/`,
  loaded fresh from disk on every start; the pure-logic helpers in
  `RELOADABLE_MODULES` reload with them. Handle API: put/get/waitfor/
  waitrt/echo/emit/sleep/command/state/args, plus run/is_running/tell/
  kill for a script that drives other scripts (`;train`). `;help`
  renders docstrings.
- `client/game/probe.py` — ask-and-classify shared by keyword scripts;
  `collect` glues per-segment pieces into whole lines.
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
  every window (#135). Use it instead of ad-hoc socket drivers.
- `client/game/wounds.py` — HEALTH parsed into wounds by area, severity
  (1-8) and kind; `wounds_data.py` is generated from the wiki by
  `tools/wound_tables.py`, never hand-edited. `;tend` and `;hunt`'s
  wound floor read it. Model: docs/wounds.md.
- `client/game/profile.py` — per-character profiles
  (`~/.revenant/profiles/<name>.json`): the quirks `;hunt` must not
  hard-code (weapon, stance, skin, pouch, floor, ground, home). FIELDS
  is the schema; the GUI's Character Profile dialog builds itself from
  it. Model and assumptions: docs/hunting.md.
- `client/game/training.py` — per-character training plans
  (`~/.revenant/training/<name>.json`, hand-edited, `;train init`
  writes a starter): tasks tying skills to the script or command loop
  that trains them, the target mindstate, the safe rooms, the rest
  floor. The pure decisions (next task, satisfied, rested, safe-room
  rotation) live here; `scripts/train.py` is the loop, orchestrating
  other scripts through the handle's `run`/`is_running`/`tell`/`kill`.
  Model: docs/training.md.
- `client/game/walker.py` + `client/game/mapdb.py` — travel on the community map
  (downloaded, never vendored). Twins: the map lists some rooms twice,
  one uid-less; `same_place` handles it. Model: docs/movement.md.
- `client/game/climbs.py`, `circles.py`, `eltime.py`, `inventory.py`,
  `history.py`; `client/ui/textfont.py`, `window_layout.py`,
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
  status strip, RT/CT timers), `map_dock.py`, `text_views.py` (the
  story/stream views and per-view fonts). `chat_window.py` — the
  standalone LNet window; `settings_dialog.py`, `profile_dialog.py`,
  `login_dialog.py`, `highlights_dialog.py`.
- `client/engine/launch.py` — the `revenant` console script and the picker; one
  session per character on its own port, registry in
  ~/.revenant/sessions.json. It exec's `client/engine/guiboot.py`, which arms
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
