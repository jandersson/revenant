# Revenant

A pure-Python client stack for DragonRealms (a Simutronics MUD). uv workspace
monorepo; members: `client` (the game client) and `chat` (LNet chat client).
`launcher/launch.py` is a separate bridge that starts the external
lich/ProfanityFE Ruby toolchain — revenant itself must never grow Ruby
dependencies.

## Commands

```sh
uv run revenant                  # launch: spawn/attach a session + GUI
uv run pytest client/tests -q    # test suite (threaded/socket tests included)
uv run ruff check client chat    # lint — CI enforces this
uv run ruff format client chat   # format — CI enforces --check
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
  `REVENANT_ACCOUNT` / `REVENANT_CHARACTER` env vars. With no keychain entry
  the launcher prompts once — terminal getpass with a tty, the Qt login
  dialog (`client/client/gui/login_dialog.py`, with remember-me → keychain)
  without one — and exchanges the password for a single-use launch key,
  passing only the key to the session over stdin (never argv or env).
  **Never store credentials in files, even gitignored ones.**
- `client/client/xml_data.py` — XMLParser target holding parsed game state
  (indicators, compass, prompt), plus `route(line)` which splits each line
  into `(stream, text)` segments via pushStream/popStream markers.
- `client/client/core.py` — `Engine`: owns a connection, feeds lines through
  XMLData, invokes `output_callback(text, stream)` per segment. Emits a
  synthetic `"compass"` stream when the room's exits change.
- `client/client/session.py` — the detachable session daemon
  (`python -m client.session`): logs in, owns the game socket, serves
  `(stream, text)` frames as JSON lines on 127.0.0.1:4242 to any number of
  attached front ends, and hosts the script engine. `AttachedEngine` is the
  client side; it presents the same surface as `Engine`.
- `client/client/scripting.py` — script engine. Scripts are `main(s)` Python
  files in `scripts/` (repo root), run as threads in the session, controlled
  by `;`-commands typed in any front end (`;list`, `;run x`, `;stop x`).
  Handle API: put/get/waitfor/waitrt/echo/sleep/state/args.
- `client/client/mapdb.py` — the community DR map database (elanthia-online
  mapdb-backup-dr), downloaded to `~/.revenant/mapdb/` on first use, never
  vendored. BFS pathfinding; wayto commands starting with ";e" are embedded
  Ruby and treated as unwalkable. `scripts/go2.py` is the walker on top.
- `client/client/gui/client_gui.py` — PyQt6 front end. GUI-thread safety via
  the `game_text` pyqtSignal; stream docks route thoughts/spells/arrivals;
  compass dock renders the `"compass"` stream. Direct mode logs in itself;
  `--attach` connects to a session.
- `client/client/launch.py` — the `revenant` console script: ensures a
  session is running, then execs the GUI.

## Conventions and gotchas

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
