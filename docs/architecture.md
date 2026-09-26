# Architecture

Revenant is one game connection shared by several processes: a **session** owns the socket and runs the scripts, and any number of **windows** attach to it over localhost.

## The processes

```
DragonRealms ── socket ── session (one per character, 127.0.0.1:4242…)
                            ├── parser + engine
                            ├── scripts (;hunt, ;train, ...)
                            └── JSON frames ──┬── PyQt6 window
                                              ├── terminal (revenant-tui)
                                              └── revenant-send (tools, AI agents)
```

- The **session** logs in, keeps the connection alive while windows come and go, and survives `;reexec` without logging out.
- A **window** only draws what the session sends; closing it can detach instead of quitting.
- **Scripts** run inside the session, so they keep running with no window open.
- **`revenant-send`** is how anything outside the session acts on it; the session's policy decides what it may do.

## The path of a game line

1. The socket reads the game's XML-tagged text.
2. The **parser** (`client/engine/xml_data.py`) keeps the state (room, vitals, hands, exp, who is here) and splits each line into streams with styles.
3. The **engine** (`client/engine/core.py`) adds the synthetic streams (compass, vitals, roundtime...).
4. The session sends every frame to the attached windows and to the running scripts.

## Where things live

| Path | Holds |
| --- | --- |
| `client/client/engine/` | the connection, login, parser, engine, session, script engine, `revenant-send` |
| `client/client/game/` | Qt-free game models scripts use: travel, hunting, training, healing, money, ... |
| `client/client/ui/` | frontend logic shared by the window and the terminal |
| `client/client/gui/` | the PyQt6 window and its docks |
| `scripts/` | one file per `;command`; its docstring is its manual |
| `chat/` | the LNet chat client |
| `beholder/` | the dashboard over `~/.revenant/history.db` |

Each module's docstring explains it; `git log` and the issues hold the history.
