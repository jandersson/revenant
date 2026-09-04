# Running Revenant

`uv run revenant` starts a session for your character and opens the window; the Start Menu shortcut on Windows does the same through a character picker. This page is the operating manual: launching, closing without logging out, and which edits need what kind of restart.

## Launching

```sh
uv run revenant                  # the saved character, or a login prompt
uv run revenant Lanival          # a named character: attach if online, else spawn
uv run revenant --pick           # the picker: running sessions to attach, cached characters to launch
```

### First run

The first launch opens the login window: account, password, and a character picked from the roster the launcher fetches once the account and password are in. *Remember* stores the password in the OS keychain (service `revenant`) and the account and character names in `~/.revenant/login.json`; from then on the launch logs straight in. To log in as a different account later, use the picker's *Switch account…* or `uv run revenant --pick`.

A session is a detachable daemon that logs in and owns the game socket; the window attaches to it over localhost. Several characters play side by side, one session and one window each, on their own ports (`~/.revenant/sessions.json` is the registry).

### The Windows launcher

![The character picker: your roster in a list, Play, Switch account, Cancel](launcher.png)

`tools/install_shortcut.ps1` installs a Start Menu shortcut (pin it to the taskbar from there) that launches windowless: pick a character from your roster and play, or *Switch account…* to log in as a different account. `tools/make_icon.py` regenerates the icon from `revenant.svg`.

## Closing the window: quit or detach?

Closing the window (the X, File → Exit, Ctrl+Q) **logs your character out**: it sends `quit`, the character leaves cleanly instead of lingering into link-death, and the session ends. To close the window and *stay in the game*, use **File → Detach (Ctrl+D)**: the session keeps playing, and the next launch reattaches to it. If you'd rather every close behave like Detach, untick "Quit the game when the window closes" in File → Settings.

## Which edits take effect when?

You rarely need to restart anything. From cheapest to dearest:

| You edited | To pick it up |
| --- | --- |
| a script (`scripts/`), or a `client/` helper it imports (walker, mapdb, probe, …) | nothing: `;run` loads the script fresh from disk every time and reloads changed helpers with it (`;stop x`, then `;x`) |
| the GUI | **Detach** (Ctrl+D) the window and relaunch; it reattaches, no logout. A plain close would quit the game (see above) |
| the session or engine | `;reexec` (below), or on Windows, where reexec is unsupported, quit and relaunch |

A script that is already running keeps its old code until you `;stop` and rerun it. With developer mode on (File → Settings, or `REVENANT_DEV=1`), a script start that takes more than half a second to load says so, naming what it reloaded.

## Hot code reload: `;reexec`

Type `;reexec` in any attached frontend to **update the running session to the latest code without logging out**: your character never leaves the game, and the connection to the server stays open the whole time.

This exists because a running session loads its code once, at startup: edits on disk don't take effect until the process restarts, and restarting used to mean logging out and back in.

How it works:

1. The session stops running scripts, marks the game socket's file descriptor inheritable, and stashes any not-yet-parsed game bytes in an environment variable.
2. It then `exec`s a fresh `python -m client.session --game-fd N`. The exec closes the listener and every frontend connection (those are per-process); only the game socket survives, adopted by the new process via `SocketClient.from_fd`.
3. The new session restores the byte buffer, rebinds the localhost port, and sends a single `look` to reprime its cold parser state (room title, compass).
4. Frontends notice the drop and reattach automatically (retrying for up to ~10 s; in practice it's sub-second). In the GUI you'll see `session dropped — reattaching ...` followed by `reattached`.

Caveats: running scripts are stopped, not resumed (start them again with `;run`); a session older than this feature doesn't know `;reexec`, so the first upgrade still needs one old-fashioned quit-and-relaunch. On Windows `;reexec` is unsupported (WinSock handles can't survive the exec handoff, #129 tracks a port) and says so instead of trying: quit and relaunch there.

## Settings

File → Settings edits `~/.revenant/settings.json`: the game text's font and size (applied live; the Experience dock stays monospace), which scripts autostart, whether closing the window quits the game, the clocks dock's Earth-moon row, and developer mode. `REVENANT_NO_XP=1` and `REVENANT_NO_BEHOLDER=1` override the autostarts for one launch.

## Logs

Everything the game sends is archived, append-only, under `~/.revenant/logs/` (`REVENANT_LOG_DIR` to move it): `game-<stamp>.log` per session, `lnet-<stamp>.log` per LNet connection, and a size-capped, seven-day debug log per process.
