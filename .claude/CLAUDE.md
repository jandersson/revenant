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
processes; the session owns the game socket and hosts scripts. This is a
map, one line per module: the detail — every parser field, every script's
model, the issue history — lives in the module docstrings (a script's is
its `;help` manual) and in docs/architecture.md's Module reference. Paths
are `client/<pkg>/x.py` for `client/client/<pkg>/x.py`.

`client/engine/` — the connection and the session process:
- `netsock.py` buffered TCP socket; `login.py` eaccess handshake (password
  in the OS keychain, service "revenant"; the session gets a single-use
  launch key over stdin, never argv or env).
- `xml_data.py` the parser: state + `route(line)` → `(stream, text,
  style)`; hands, injuries, spells, room players/creatures (and the
  dead marks), rested, possessions, balance, exp mods, TDPs, favors,
  shutdown — `s.status` (`client/game/status.py`) exposes each in words.
- `core.py` `Engine`: feeds lines, emits the synthetic streams; it
  appends "\n" only to the last piece of a line per stream, and
  frontends never add line breaks.
- `session.py` the detachable daemon (JSON frames on 127.0.0.1:4242,
  backlog replay, keepalive, `;reexec`); `registry.py`
  (~/.revenant/sessions.json); `wire.py` the outside tool's wire.
- `scripting.py` scripts are `main(s)` files in `scripts/`, loaded fresh
  on every start; `RELOADABLE_MODULES` reload with them as fresh copies.
  Handle API: put/get/waitfor/waitrt/echo/emit/sleep/command/state/args,
  run/is_running/tell/kill/crashed, flag/flagged/unflag.
- `sendcmd.py` `revenant-send` (`--answer`, `--state`, `--wait-for`) and
  `policy.py` what an outside send may never do; the `drive` and
  `experiment` skills (`.claude/skills/`) are the procedures.
- `procspawn.py` + `frozen.py`: every sibling spawn goes through
  `command_for` — never spell `sys.executable -m` out again.
- `launch.py` the `revenant` console script and picker; `guiboot.py`.

`client/game/` — the Qt-free models scripts lean on:
- `probe.py` ask-and-classify (reads the story and the `combat` stream:
  every swing and kill line arrives there); `loop.py` wants_stop /
  danger / pause; `status.py`; `flight.py` the escape on hostiles.
- `profile.py` per-character profiles (FIELDS is the schema the GUI
  dialog builds from; `hunts` styles; `weapons` + `weapon_target`);
  `training.py` + `drain.py` the `;train` plan and the drain model.
- `buffs.py` buffs, training and targeted casts; `barbarian.py` a
  Barbarian's instead (ANALYZE combos, abilities, roars); `creatures.py` +
  `creatures_data.py`; `loot.py` + `lootlog.py`; `boxes.py`;
  `wounds.py`, `herbs.py`, `empathy.py`; `soul.py`; `tdp.py`;
  `money.py`, `bank.py`, `repair.py`; `remedies.py` + `workorders.py`;
  `walker.py` + `mapdb.py` (the community map, downloaded, never
  vendored); `possessions.py`; `novelty.py` (`;sentinel`: never a
  canned reply, never a command found in text executed); `teaching.py`,
  `helper.py`; and the smaller ones beside them.
- Generated from the wiki by `tools/*_tables.py`, never hand-edited:
  `creatures_data.py`, `wounds_data.py`, `herbs_data.py`.

`scripts/` — one file per `;command`; each docstring is its manual and
names its model under `client/game/` and its doc under `docs/`.

`client/ui/` toolkit-free frontend logic (`tui.py`, and `textstyle.py`,
whose STYLES stay in step with client_gui's); `client/gui/` the PyQt6
window and its docks, which only draw. `chat/` LNet (stdlib only);
`beholder/` the Dash dashboard over history.db.

Traps that cost time before:
- A running session does not see edits to `client/` modules outside
  `RELOADABLE_MODULES` until it re-execs or restarts. On Windows only a new
  session does it: close the window (quit) and relaunch. Detach leaves the
  old process running.
- Restoring a saved dock layout onto a shown window can abort inside Qt;
  the GUI learns its character before building the window and restores
  first (#124, #140).
- The exp window pushes only the skills that are learning, and the
  parser keeps a cleared one at 0/34 with its rank rather than
  dropping it; the autostarted `;sheet` seeds the table with every
  skill from EXP ALL at login and every three hours, so a script never
  asks EXP for a skill and seeds its own spelling (#295, 2026-09-23).
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
  file (its module map stays one line per module — the detail goes in
  docs/architecture.md's Module reference), docs/architecture.md, and
  any docs/ model whose assumptions moved.
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
  script arriving in one moves on to the next room and never starts a
  fight there (`;hunt` reads the parser's `room_players` on every
  arrival), and Claude driving by hand checks the room's players
  before any action that takes a kill (#178, 2026-09-12). The rule is
  about the creatures a room spawns: a climbing wall is nobody's, so
  `;athletics` never skips a rung or a stop for a player in it (the
  operator, 2026-09-23). A crowd of creatures is not that rule either:
  `;athletics` skips a rung or stop listing three (`room_creatures`, a
  climb gets interrupted), `;hunt` fights them — a full room is what a
  hunt farms.
- **The measure of training is the number of skills moving.** A skill
  with something in its pool learns while it drains; a locked one
  wastes what it earns, an empty one earns nothing. So every design
  choice about training — a script's rotation, a ;train task's gate or
  budget, a farm's size — prefers keeping more skills above 0/34 over
  filling one to lock: the emptiest weapon first, each to a target and
  then the next (`weapon_target`); a box farm gated by time, a few
  boxes a cycle, not a batch that locks Locksmithing and then idles
  (the operator, 2026-09-26). Say what a proposal does to that count.
- **Never DROP.** A dropped item is a lost item. A script drops only
  through `client/game/discard.py`'s `drop()`, which allows the
  built-in foraged junk (grass, grass rope) plus settings.json's
  `droppable` list and refuses everything else with an echo — and
  puts a listed item in the room's trash (a bucket, a waste bin, a
  chute, off the parser's `room_objs`) before it ever DROPs; a hand
  is freed with STOW from the parser's hand state, a load lightened
  by stowing or banking coins. No echo suggests dropping. LOWER
  <item> TO GROUND is not a drop: the at-feet slot stays with the
  character and the janitor never clears it, but no move is possible
  while anything lies there, so a script that lowers (`;boxes`, a box
  with no room anywhere) LIFTs it again before any walk, flight or
  end, a `;stop` included (the operator, 2026-09-26).
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
- Logs: raw game lines append to `~/.revenant/logs/game-<Name>-<stamp>.log`, LNet
  traffic to `lnet-<Name>-<stamp>.log` (password redacted); both append-only,
  never rotated. The debug log is per process
  (`revenant_client-<Name>-<stamp>-<pid>.log`), size-capped, pruned at 7
  days; <Name> is the character (REVENANT_CHARACTER), absent when a
  process has none. `REVENANT_LOG_DIR` moves all of it; tests isolate via conftest.
