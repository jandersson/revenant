# Revenant

_Python and DragonRealms — a monorepo of hobby projects for the [DragonRealms](https://www.play.net/dr/) MUD._

Most of the tooling around DragonRealms lives in the Ruby ecosystem (lich, dr-scripts, profanity, Genie plugins). Revenant is an excuse to rebuild some of that in Python, have fun, and see what sticks. None of these projects are polished or production-ready — they are prototypes, experiments, and works-in-progress.

Shout out to [Pylanthia](https://github.com/robbintt/pylanthia), a great related project.

## Getting started

The repo is a [uv](https://docs.astral.sh/uv/) workspace. `client/` and `chat/` are workspace members with their own `pyproject.toml`; `beholder/` is deliberately outside the workspace because its pinned deps are incompatible with modern Python (see [beholder/README.md](beholder/README.md)).

```sh
# Install uv: https://docs.astral.sh/uv/getting-started/installation/
uv sync                       # create the workspace venv + install everything
uv run pytest --rootdir client   # run the client test suite
uv run -- python -m client.gui.client_gui   # launch the PyQt6 client
```

Python 3.10–3.12 is required. Python 3.13+ is not yet supported because [client/client/login.py](client/client/login.py) depends on the `telnetlib` module that was removed in 3.13.

## Projects

| Directory | What it is |
|---|---|
| [client/](client/) | A Python MUD client and engine — aims to be a [lich](https://lichproject.org/)-style middleman with a PyQt6 front end and a (WIP) terminal front end. |
| [beholder/](beholder/) | A [Dash](https://plotly.com/dash/) web dashboard for visualizing character experience gains in real time, fed by a lich script writing to SQLite. |
| [chat/](chat/) | A standalone LNet chat client, roughly a Python port of rcuhljr's [Genie LNet plugin](https://github.com/rcuhljr/genie-lnet-plugin/). |
| [launcher/](launcher/) | Small helper scripts for spinning up a headless lich instance alongside [ProfanityFE](https://github.com/elanthia-online/profanity-fe). |

### client
A rough-draft engine + front ends for playing DragonRealms with Python in the loop.

- **core** — the engine/middleman between the game and whichever front end is attached. See [client/client/core.py](client/client/core.py).
- **gui** — a PyQt6 front end reminiscent of the old AOL-era Gemstone clients. See [client/client/gui/client_gui.py](client/client/gui/client_gui.py).
- **tui** — a non-working draft of a terminal front end. [Profanity](https://github.com/elanthia-online/profanity-fe) is what you actually want for a TUI today; this is just a sketch.

Python 3.10–3.12. Packaged via [client/pyproject.toml](client/pyproject.toml) as a member of the root uv workspace.

### beholder
A browser-based dashboard for character experience gains, built with Dash/Plotly on top of a SQLite database.

The pipeline:
1. [beholder/revenant.lic](beholder/revenant.lic) runs inside lich, polling `DRSkill` every 60s and writing rows into a SQLite database.
2. [beholder/app.py](beholder/app.py) reads from that database via SQLAlchemy and renders a Dash app with per-character, per-skill mindstate plots that refresh on an interval.

See [beholder/README.md](beholder/README.md) for setup. Note: the pinned dependencies in [beholder/requirements.txt](beholder/requirements.txt) are old — Dash 0.22, Flask 1.0, pandas 0.23 — and the code uses the deprecated `dash_core_components` / `dash_html_components` / `dash_table_experiments` imports, so it won't run under a modern Dash without porting. That's why beholder is **not** part of the uv workspace yet.

### chat
A minimal LNet client in pure Python (stdlib `ssl` only, no dependencies). Connects to `lnet.lichproject.org:7155`, verifies the server against the pinned CA in [chat/LnetCert.txt](chat/LnetCert.txt) plus the `lichproject.org`/`LichNet` CN check the reference client uses, handles the login XML handshake, answers pings, and parses the incoming XML stream into typed `LnetMessage`s. See [chat/chat.py](chat/chat.py). Run with `uv run python chat/chat.py`.

LNet names can be password-protected on the server (protocol per `lnet.lic` 1.15): if a name is protected, login must carry a `password` attribute or the server answers `password required` and disconnects. Configure via environment:

- `LNET_NAME` — the name to log in as (defaults to `Wabbajack`, which is currently password-protected — set your own).
- `LNET_PASSWORD` — the password for that name; alternatively put it in the git-ignored `chat/lnet_password.txt`. Never commit it.
- `LNET_DEBUG` — set to anything for raw protocol dumps.

To password-protect a name (or change it), log in and call `Server.register_password("...")`; pass the literal string `"nil"` to remove protection. Forgotten passwords are reset at <https://lnet.lichproject.org>.

### launcher
[launcher/launch.py](launcher/launch.py) picks a free port, starts lich headless with `--detachable-client`, and attaches a Profanity front end to it. Paths are currently hard-coded for the author's machine — treat it as a template rather than a turnkey tool.

## Layout

```
revenant/
├── beholder/   # Dash/Plotly XP dashboard + lich data-logging script
├── chat/       # LNet chat client
├── client/     # PyQt6 client + engine (core/gui/tui)
└── launcher/   # Helpers for launching lich + profanity together
```

## Status

Hobby-grade. Things are in varying states of disrepair — the client is the most actively poked at, beholder is dormant but fun, chat works, and launcher is a convenience script. Expect to read code before running anything.

## License

MIT (see [client/pyproject.toml](client/pyproject.toml)).
