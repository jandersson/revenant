# Revenant

_Python and DragonRealms — a monorepo of hobby projects for the [DragonRealms](https://www.play.net/dr/) MUD._

Most of the tooling around DragonRealms lives in the Ruby ecosystem (lich, dr-scripts, profanity, Genie plugins). Revenant is an excuse to rebuild some of that in Python, have fun, and see what sticks. None of these projects are polished or production-ready — they are prototypes, experiments, and works-in-progress.

Shout out to [Pylanthia](https://github.com/robbintt/pylanthia), a great related project.

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

Requires Python 3.6+. Install from [client/setup.py](client/setup.py) or `pip install -r client/requirements.txt`.

### beholder
A browser-based dashboard for character experience gains, built with Dash/Plotly on top of a SQLite database.

The pipeline:
1. [beholder/revenant.lic](beholder/revenant.lic) runs inside lich, polling `DRSkill` every 60s and writing rows into a SQLite database.
2. [beholder/app.py](beholder/app.py) reads from that database via SQLAlchemy and renders a Dash app with per-character, per-skill mindstate plots that refresh on an interval.

See [beholder/README.md](beholder/README.md) for setup. Note: the pinned dependencies in [beholder/requirements.txt](beholder/requirements.txt) are old — it hasn't been run in a while and may need a refresh before it flies again.

### chat
A minimal LNet client in pure Python. Connects over SSL to `lnet.lichproject.org`, handles the login XML handshake, answers pings, and parses incoming messages into a typed `LnetMessage`. See [chat/chat.py](chat/chat.py).

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

MIT (see [client/setup.py](client/setup.py)).
