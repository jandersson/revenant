# Revenant Client

A rough-draft Python client and engine for playing [DragonRealms](https://www.play.net/dr/). The goal is something [lich](https://lichproject.org/)-shaped — a middleman between the game server and whatever front end you want to attach — but written in Python, with Python scripting, and more modularity where that's easy to get.

This is a hobby project. It is not a drop-in lich replacement and it is not trying to be. If you want a polished TUI today, go use [Profanity](https://github.com/elanthia-online/profanity-fe). If you want a polished modern front end, go use [Frostbite](https://github.com/elanthia-online/frostbite). If you want to tinker with Python wrapping a MUD connection, stay.

Related reading: [Pylanthia](https://github.com/robbintt/pylanthia).

## Components

- **core** — the engine / middleman. Handles the telnet connection to Simutronics, feeds incoming bytes through an XML parser, strips game XML out of the text stream, and dispatches input/output. See [client/core.py](client/core.py) and [client/xml_data.py](client/xml_data.py).
- **login** — handles the SAL-style login handshake to get a game connection. See [client/login.py](client/login.py). Drop a `secrets.py` next to [client/secrets-example.py](client/secrets-example.py) to supply credentials.
- **gui** — a PyQt6 front end. A main text output, a docked input line, a file/view menu. Reminiscent of the pre-Wizard/Stormfront AOL Gemstone clients. Currently the primary test bench for `core`. See [client/gui/client_gui.py](client/gui/client_gui.py).
- **tui** — a non-working draft of a terminal front end. Framework choice is still up in the air. See [client/tui/](client/tui/).

## Install

Requires Python 3.6+.

```sh
pip install -r requirements.txt
# or, for development extras (black, pytest, flake8, pre-commit):
pip install -e .[development]
```

Dependencies are intentionally thin — currently just `pyqt6` and `pyyaml` (see [requirements.txt](requirements.txt) and [setup.py](setup.py)).

## Running

There is no CLI entry point yet — the GUI is started via `if __name__ == "__main__"` at the bottom of [client/gui/client_gui.py](client/gui/client_gui.py):

```sh
python -m client.gui.client_gui
```

You will need a working `secrets.py` (or equivalent) for login to succeed. A CLI wrapper is on the TODO list.

## Tests

```sh
pytest
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
├── requirements.txt
├── requirements-dev.txt
└── setup.py
```
