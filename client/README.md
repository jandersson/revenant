# Revenant Client

A rough-draft Python client and engine for playing [DragonRealms](https://www.play.net/dr/). The goal is something [lich](https://lichproject.org/)-shaped — a middleman between the game server and whatever front end you want to attach — but written in Python, with Python scripting, and more modularity where that's easy to get.

This is a hobby project. It is not a drop-in lich replacement and it is not trying to be. If you want a polished TUI today, go use [Profanity](https://github.com/elanthia-online/profanity-fe). If you want a polished modern front end, go use [Frostbite](https://github.com/elanthia-online/frostbite). If you want to tinker with Python wrapping a MUD connection, stay.

Related reading: [Pylanthia](https://github.com/robbintt/pylanthia).

## Components

- **core** — the engine / middleman. Handles the telnet connection to Simutronics, feeds incoming bytes through an XML parser, strips game XML out of the text stream, and dispatches input/output. See [client/core.py](client/core.py) and [client/xml_data.py](client/xml_data.py).
- **login** — handles the SAL-style login handshake to get a game connection. See [client/login.py](client/login.py). Credentials come from the OS keychain and environment variables — see [Running](#running).
- **gui** — a PyQt6 front end. A main text output, a docked input line, a file/view menu. Reminiscent of the pre-Wizard/Stormfront AOL Gemstone clients. Currently the primary test bench for `core`. See [client/gui/client_gui.py](client/gui/client_gui.py).
- **tui** — a non-working draft of a terminal front end. Framework choice is still up in the air. See [client/tui/](client/tui/).

## Install

Requires Python 3.10+.

This project is a member of the root [uv](https://docs.astral.sh/uv/) workspace. From the repo root:

```sh
uv sync                      # installs revenant-client + dev tools into .venv
```

Dependencies are declared in [pyproject.toml](pyproject.toml) — currently `pyqt6`, `pyyaml`, and `keyring`, with `black`, `flake8`, `pre-commit`, and `pytest` in the `dev` dependency group.

## Running

One command:

```sh
uv run revenant
```

If a session is already listening it attaches the GUI to it instantly;
otherwise it spawns one in the background (which does the keychain login),
waits for it to come up, and attaches. Closing the GUI leaves the session —
and the game connection — running; `uv run revenant` again to reattach.
`revenant <Character>` picks the character for a newly spawned session,
and `revenant --direct` runs login + GUI in a single process.

The pieces are also runnable by hand:

```sh
uv run python -m client.session                    # terminal 1, stays running
uv run python -m client.gui.client_gui --attach    # terminal 2, relaunch at will
```

`--attach` takes an optional `HOST:PORT` (default `127.0.0.1:4242`; the
default port can also be set with `REVENANT_SESSION_PORT`). Killing the
session process ends the game connection; closing an attached GUI does not.

Credentials never live in the repo. Store your account password once in the OS
credential store (macOS Keychain, Secret Service on Linux, Credential Locker on
Windows) — you'll be prompted for it with hidden input:

```sh
uv run keyring set revenant YOURACCOUNT
```

Set the non-secret half in your environment (or answer the prompts at launch):

```sh
export REVENANT_ACCOUNT=YOURACCOUNT
export REVENANT_CHARACTER=Yourcharacter
```

A CLI wrapper is on the TODO list.

## Tests

From this directory:

```sh
uv run pytest
```

There is a small XML parser test suite in [tests/test_xml_parser.py](tests/test_xml_parser.py) backed by a captured login session in [tests/login-sample.log](tests/login-sample.log).

## Layout

```
client/
├── client/
│   ├── core.py            # Engine: connection, reactor loop, XML parsing
│   ├── login.py           # SAL login handshake
│   ├── xml_data.py        # Game XML parser / text stripper
│   ├── client_logger.py   # Logging mixin
│   ├── logging_config.yaml
│   ├── gui/               # PyQt6 front end
│   └── tui/               # (draft) terminal front end
├── notebooks/             # Scratch notebooks
├── tests/
└── pyproject.toml
```
