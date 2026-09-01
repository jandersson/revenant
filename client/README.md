# Revenant Client

A rough-draft Python client and engine for playing [DragonRealms](https://www.play.net/dr/). The goal is something [lich](https://lichproject.org/)-shaped — a middleman between the game server and whatever front end you want to attach — but written in Python, with Python scripting, and more modularity where that's easy to get.

This is a hobby project. It is not a drop-in lich replacement and it is not trying to be. If you want a polished TUI today, go use [Profanity](https://github.com/elanthia-online/profanity-fe). If you want a polished modern front end, go use [Frostbite](https://github.com/elanthia-online/frostbite). If you want to tinker with Python wrapping a MUD connection, stay.

Related reading: [Pylanthia](https://github.com/robbintt/pylanthia).

## Components

- **core** — the engine / middleman. Handles the telnet connection to Simutronics, feeds incoming bytes through an XML parser, strips game XML out of the text stream, and dispatches input/output. See [client/core.py](client/core.py) and [client/xml_data.py](client/xml_data.py).
- **login** — handles the SAL-style login handshake to get a game connection. See [client/login.py](client/login.py). Credentials come from the OS keychain and environment variables — see [Running](#running).
- **gui** — a PyQt6 front end. A main text output, a docked input line with a roundtime countdown beside it, a file/view menu, and dock windows: streams, the compass, and clocks (Elanthian date, anlas, and moon phases beside Stockholm and Chicago — computed in [client/eltime.py](client/eltime.py), calibrated by `;clock`). Reminiscent of the pre-Wizard/Stormfront AOL Gemstone clients. Currently the primary test bench for `core`. See [client/gui/client_gui.py](client/gui/client_gui.py).

## Install

Requires Python 3.10+.

This project is a member of the root [uv](https://docs.astral.sh/uv/) workspace. From the repo root:

```sh
uv sync                      # installs revenant-client + dev tools into .venv
```

Dependencies are declared in [pyproject.toml](pyproject.toml) — currently `pyqt6`, `pyyaml`, and `keyring`, with `ruff`, `pre-commit`, and `pytest` in the `dev` dependency group.

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

The keychain is optional: with no stored entry, `revenant` asks for the
password at launch — in the terminal when there is one, otherwise via a
login window (with a "remember me" that writes the keychain) — and uses it
exactly once for the login handshake. Only the resulting single-use launch
key is handed to the session (over stdin), the same temporary-use model as
the official SGE launchers.

A CLI wrapper is on the TODO list.

## Scripts

Player scripts are Python files in the repo's `scripts/` directory (override
with `REVENANT_SCRIPTS`), each defining `main(s)`. They run inside the
session, so they keep running even with no front end attached. Control them
by typing `;`-commands in any front end:

    ;list               running + available scripts
    ;run hello [args]   start one (;hello works as shorthand)
    ;stop hello         stop one (;stop all for everything)

The `s` handle: `s.put(cmd)` sends to the game (echoed to front ends),
`s.get(timeout=)` returns the next main-stream line, `s.waitfor(*regexes,
timeout=)` blocks for a match, `s.echo(text)` prints to front ends only,
`s.sleep(secs)` is stop-aware, `s.state` is the session's parsed game state
(indicators, compass, prompt), `s.args` are the `;run` arguments. See
[../scripts/hello.py](../scripts/hello.py) for a worked example.

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
│   ├── core.py            # Engine: connection, XML parsing, synthetic streams
│   ├── login.py           # SAL login handshake
│   ├── xml_data.py        # Game XML parser / text stripper
│   ├── client_logger.py   # Logging mixin
│   ├── logging_config.yaml
│   └── gui/               # PyQt6 front end
├── notebooks/             # Scratch notebooks
├── tests/
└── pyproject.toml
```
