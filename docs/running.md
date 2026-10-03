# Running Revenant

`uv run revenant` starts a session for your character and opens the window.

## Launching

```sh
uv run revenant                  # the saved character, or a login prompt
uv run revenant Lanival          # a named character: attach if online, else start
uv run revenant --pick           # the character picker
uv run revenant-tui [character]  # a terminal instead of the window
```

A session is a background process that owns the game connection; windows attach to it. Each character gets its own session.

- **First run:** a login window. *Remember* keeps the password in the OS keychain, never in a file.
- **Windows:** `tools/install_shortcut.ps1` adds a Start Menu shortcut to the picker.
- **No Python?** Use the installer or disk image from [Releases](https://github.com/jandersson/revenant/releases).

## Quit or detach

- Closing the window **logs the character out**.
- File → **Detach** (Ctrl+D) closes the window and **keeps the character in the game**; the next launch reattaches.

## After editing code

| You edited | Do |
| --- | --- |
| a script or a helper it imports | `;stop x`, then `;x` |
| the GUI | Detach and relaunch |
| the session or engine | `;reexec` — reloads the code without logging out |

## Sending commands from outside

`revenant-send` puts one command into a running session, for tools and AI agents. Every window shows it as `>> [external] …` (or `>> [claude] …`).

```sh
revenant-send exp all
revenant-send --origin claude --answer 4 "tdp"     # print the game's answer
revenant-send --state room,vitals                  # read the parser's state, send nothing
REVENANT_ALLOW_SEND=1 revenant-send "stance set 100 80 0"
```

- Read-only commands (INFO, EXP, WEALTH, HEALTH, LOOK...) always pass.
- Anything else needs `REVENANT_ALLOW_SEND=1` or the setting in File → Settings.
- The session refuses GIVE, SELL, WITHDRAW, TRAIN, DROP and similar from outside regardless; QUIT passes, behind the gate. `~/.revenant/policy/<name>.json` can allow one (`{"allow": ["exchange"]}`).

## Unattended: `;sentinel`

Autostarted. It rings the bell and echoes `SENTINEL:` when someone talks to you, a word is spelled to trick scripts ("J_u_M_p"), staff post a notice, or the same line spams. New lines collect in the Attention dock.

- `;sentinel ok` — answer an alert.
- `;sentinel quiet N` — silence it for N minutes.
- `sentinel_logout` (off by default) ends the session if an alert goes unanswered for 10 minutes while a script runs.

It never replies for you.

## Settings and logs

File → Settings: fonts, autostarted scripts, whether closing quits, the idle-warning answer.

Logs are under `~/.revenant/logs/`: `game-<Name>-*.log` has what the game sent, `revenant_client-<Name>-*.log` what the scripts did.
