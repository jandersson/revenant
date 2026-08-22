# Revenant

A pure-Python client stack for DragonRealms (a Simutronics MUD). uv workspace
monorepo; members: `client` (the game client), `chat` (LNet chat client), and
`beholder` (Dash dashboard over the experience history the bundled xp
script — `;xp` in any frontend — logs to
~/.revenant/xp.db; stdlib sqlite3 data layer in `beholder/beholder/data.py`,
app + tests beside it; run with `uv run beholder`).
`launcher/launch.py` is a separate bridge that starts the external
lich/ProfanityFE Ruby toolchain — revenant itself must never grow Ruby
dependencies.

## Commands

```sh
uv run revenant                  # launch: spawn/attach a session + GUI
uv run pytest client/tests -q    # test suite (threaded/socket tests included)
uv run pytest beholder/tests -q  # beholder test suite
uv run pytest chat/tests -q      # chat / Marshal-reader test suite
uv run ruff check client chat beholder    # lint — CI enforces this
uv run ruff format client chat beholder   # format — CI enforces --check
uv run python tools/build_app.py # (re)build ~/Applications/Revenant.app (macOS)
```

CI (`.github/workflows/python-package.yml`) runs ruff (check + format) and
pytest on Python 3.10–3.12, ubuntu. Ruff config lives in the root
pyproject.toml (notebooks excluded). Always run the commands above before
pushing.

## Architecture

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
  (indicators, compass, prompt), plus `route(line)` which splits each line
  into `(stream, text, style)` segments via pushStream/popStream markers
  and the styling markers (pushBold, presets, style spans). style is ""
  for plain text, a style name the GUI maps to colors/bold, the control
  value "clear" (<clearStream/>: wipe that stream's window), or
  "link:<command>" for <d> command links (clickable in the GUI: a click
  sends the command).
  Segments carry their own newlines — the engine appends "\n" to the last
  piece of each line per stream; frontends never add line breaks. Also
  parses the exp window (`<component id='exp Skill'>`) into
  `experience` (rank/percent/mindstate per learning skill); the engine
  rewrites a synthetic "exp" stream on change (Experience dock), and
  `scripts/xp.py` snapshots it to `~/.revenant/xp.db` for history.
- `client/client/core.py` — `Engine`: owns a connection, feeds lines through
  XMLData, invokes `output_callback(text, stream)` per segment. Emits a
  synthetic `"compass"` stream when the room's exits change.
- `client/client/session.py` — the detachable session daemon
  (`python -m client.session`): logs in, owns the game socket, serves
  `(stream, text)` frames as JSON lines on 127.0.0.1:4242 to any number of
  attached frontends, and hosts the script engine. `AttachedEngine` is the
  client side; it presents the same surface as `Engine`. Typing `;reexec`
  in any frontend re-execs the session with the code currently on disk,
  handing the live game socket across (`--game-fd`) — no logout, no
  re-login; frontends drop and auto-reattach within ~10s. Remember: a
  running session does NOT see code edits until it re-execs or restarts.
- `client/client/scripting.py` — script engine. Scripts are `main(s)` Python
  files in `scripts/` (repo root), run as threads in the session, controlled
  by `;`-commands typed in any frontend (`;list`, `;help [x]`, `;run x`,
  `;stop x`). `;help` renders module docstrings — write them as the user
  manual.
  Handle API: put/get/waitfor/waitrt/echo/emit/sleep/state/args — `emit`
  targets an arbitrary stream (e.g. "thoughts"). `scripts/lnet.py` uses it
  to mirror LNet chat into the Thoughts window, read-only (`;lnet`).
  Sessions autostart the xp history logger and the beholder dashboard
  server in quiet mode (`session.autostart_scripts`; `;stop <name>` opts
  a session out; the GUI's File → Settings dialog over
  `client/settings.py` / ~/.revenant/settings.json turns them off
  durably, and REVENANT_NO_XP=1 / REVENANT_NO_BEHOLDER=1 override
  everything for one launch — quit-on-close lives there too);
  `;beholder` opens the dashboard in the browser, and the GUI embeds it
  via View → Experience History (QWebEngineView, lazy-created, browser
  fallback when QtWebEngine is missing).
- `client/client/mapdb.py` — the community DR map database (elanthia-online
  mapdb-backup-dr), downloaded to `~/.revenant/mapdb/` on first use, never
  vendored. BFS pathfinding; wayto commands starting with ";e" are embedded
  Ruby and treated as unwalkable. `scripts/go2.py` is the walker on top.
- `client/client/gui/client_gui.py` — PyQt6 frontend. GUI-thread safety via
  the `game_text` pyqtSignal; stream docks route thoughts/spells/arrivals;
  compass dock renders the `"compass"` stream. Direct mode logs in itself;
  `--attach` connects to a session. User highlight patterns
  (`client/highlights.py`, ~/.revenant/highlights.json) color matched
  spans over any base style; View → Reload Highlights re-reads them.
- `client/client/launch.py` — the `revenant` console script: ensures a
  session is running, then execs the GUI.

## Conventions and gotchas

- House rule: all agents shall respond with kaomojis — chat replies only,
  never in code, commits, docs, or anything committed to the repo.
  ᕕ( ᐛ )ᕗ

- Every behavior change ships with unit tests in `client/tests/` — bug fixes
  get a regression test (ideally built from captured game traffic, like the
  compass tests), new features get coverage. No test, no merge.
- Every change freshens the documentation it staled, in the same commit:
  the module docstring (it is the ;help manual), the READMEs' claims about
  behavior, CLAUDE.md's architecture notes, and docs/ files whose
  assumptions moved. A doc that says the old thing is a bug like any
  other — grep for the feature's old wording before shipping.
- Tests are documentation: a reader learns how a command or feature behaves
  from its tests, without sifting through implementation. Business rules
  and user-facing behavior — command grammar, responses, output formats,
  error messages — are encoded as plainly-named tests showing input →
  expected response ("how does this command answer? look at its test").
  Game-server behavior can't be exercised directly (there is no interface
  to the game besides the frontend), but it is still in scope as
  assumptions: captured-traffic fixtures pin down what we believe the
  server sends. Some responses are static, some vary — when they vary,
  capture the variants as fixtures too. A fixture that turns out wrong is
  an assumption to correct, not a test to delete.
- Documentation is written bottom-line-up-front (BLUF): the first two
  sentences carry the most vital information — what the feature does and
  why you'd want it — and the first sentence must stand alone for a
  skimmer. Rationale, limitations, and mechanics come after, never first.
  The same goes for a direct ask: state it upfront, context second.
- No PII in the repo, ever: no real names, email addresses, Simutronics
  account names, or anything that identifies the operator — in code, tests,
  docs, commit messages, or captured fixtures. Use synthetic values
  (TESTACCT / Testchar) in tests, and scrub captured game traffic before
  committing it. Real identity lives outside the repo: the OS credential
  store for the password, the local login-defaults file for the
  account/character names (see `client/client/login.py` for both).
- Commit messages follow Conventional Commits: `type(scope): summary`
  (e.g. `feat(login): fetch the character roster in the login dialog`,
  `fix(session): shutdown sockets before close`). Common types:
  feat, fix, docs, test, refactor, chore, ci.
- Every feature gets a GitHub issue — create one when you start building
  it (or at latest when it ships), so the work is tracked and closeable.
- File a GitHub issue for every defect or gap detected while working on
  something else — always, even for small ones, instead of relying on
  memory or TODO comments. An issue is easily closed; an undetected bug
  is not. Include the evidence (log lines, screenshots) while it's fresh.
  Unless it directly impacts the feature being built, file it and leave
  it alone — don't fix drive-by findings inside an unrelated change.
- Everything written to be read later — issues, comments, commit
  messages, documentation — is written for a human skimming it: a first
  line that stands alone (BLUF), then structure, never one dense
  paragraph. Issues/comments use bold section labels (What happened /
  Symptom / Impact / Fix sketch), numbered steps for event sequences,
  bullets for lists, backticks around code; draft bodies in a file and
  pass --body-file to gh, since inline quoting mangles them. Commit
  bodies use short paragraphs or bullets, one topic each, cause before
  fix. Documentation additionally follows the BLUF convention above.
- Threads + locks, not asyncio — keep new concurrency in the existing style.
- Closing a socket does NOT wake a thread blocked in recv()/accept() on
  Linux (it does on macOS, so local runs won't catch it) — always
  `socket.shutdown(SHUT_RDWR)` before `close()`; see `session.close_socket`.
- Tests use real sockets on ephemeral ports and threaded servers; make them
  hermetic (never assume a released ephemeral port stays closed — hold a
  bound, non-listening socket instead) and generous with timeouts (CI
  runners are slow).
- Don't import PyQt6 in `client/tests` — CI is headless (no libEGL).
- macOS specifics: the filesystem is case-insensitive (`.venv/bin/Revenant`
  collides with the `revenant` console script); CPython only detects a venv
  when `pyvenv.cfg` is in the parent of the executable's directory (that's
  why the branded interpreter symlink lives in `.venv/branded/`).
- Logging config in `client/client/logging_config.yaml`; raw game protocol
  lines append to a per-session `game-<timestamp>.log` under
  `~/.revenant/logs/` (override with `REVENANT_LOG_DIR`; tests isolate via
  conftest) — an append-only archive, never rotated away. Only the
  disposable `revenant_client.log` debug log is size-capped.
- No secrets anywhere in the repo — see the credentials note above. The
  gitignore keeps `secrets.py` blocked for stragglers, but keychain is the
  only supported path.
