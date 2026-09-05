<p align="center">
  <img src="client/client/gui/revenant.svg" width="128" alt="The revenant icon: Elanthia's three moons — black Katamba ringed in miasma, crimson Yavash, blue Xibar, and the shards of Grazhir">
</p>

# Revenant

A Python client for [DragonRealms](https://www.play.net/dr/): a detachable game session with a script engine, a PyQt6 window, an experience-history dashboard, and an LNet chat client. Hobby-grade, built for fun, and not a replacement for anything.

## Install and first run

You need [git](https://git-scm.com/), [uv](https://docs.astral.sh/uv/getting-started/installation/), and a DragonRealms account. uv fetches a Python of its own if the machine has none.

```sh
git clone https://github.com/jandersson/revenant.git
cd revenant
uv sync          # creates .venv and installs everything, Python included if needed
uv run revenant  # first run: a login window
```

The login window asks for your account, password, and character (the roster is fetched from the server once the account and password are in). Tick *remember* and the password goes to your OS keychain and the names to `~/.revenant/login.json`; the next `uv run revenant` logs straight in. Nothing is ever written to a file in plain text. The game window appears with "Connected" in the status bar, and the community map downloads on first use of `;go2` or the Map dock.

Run the commands from the repository root; that is where `uv` finds the workspace and the session finds its scripts.

**Windows:** a Start Menu shortcut that opens the character picker, pinnable to the taskbar:

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_shortcut.ps1
```

**macOS:** `uv run python tools/build_app.py` builds `~/Applications/Revenant.app`.

[docs/running.md](docs/running.md) is the operating manual from here: launching a named character, several at once, quitting versus detaching, and which edits need which restart.

## The client

![The game window, live: a Moon Mage in the Observatory's third level, the guild register scrolled past, three attempts to find a burp command (burp, brap, belch: please rephrase), the map drawn around the room, the compass lit with the exits, Thoughts, Arrivals and Deaths in their docks, the Elanthian clocks, and the vitals bars above the input line](docs/screenshot.png)

One session per character, any number of windows attached to it, lich-style. The session logs in, owns the game socket, serves parsed text to every attached frontend over localhost, and hosts the script engine: `;list`, `;run <name>`, `;stop <name>`, `;help <name>`. A script is a `main(s)` in [scripts/](scripts/), reloaded from disk every time it starts; [docs/scripting.md](docs/scripting.md) is the guide.

The window shows the game's own styling (amber room names, blue speech, bold alerts, clickable command links) and keeps the rest in docks:

- **Experience** — a live skill dashboard, rank and percent and mindstate per learning skill.
- **Map** — the community map drawn around you as you move; click a room to walk there with `;go2`.
- **Compass, Clocks, Thoughts, Arrivals, Deaths** — exits you can click, Elanthian date and moons beside Stockholm and Chicago, and the game's side streams each in a window of their own.
- **Around the input line** — roundtime and casttime counting down from the game's own timestamps, vitals bars, a status strip with posture, stunned, bleeding, hidden and a red DEAD, and shell-style command history.

File → Settings covers the font, the autostarts, and whether closing the window quits the game. Highlight patterns of your own live in `~/.revenant/highlights.json`.

Bundled scripts: `;go2` travel on the community map, `;xp` and `;sheet` history logging, `;deathwatch` for unattended deaths, `;tend` for bleeders, `;clock` for the Elanthian calendar, `;circle` for what gates your next circle, `;athletics`, `;favors`, `;mechlore`, `;wealth`, `;survey`, and `;lnet`. `;help` lists them with their manuals.

## Beholder

![The beholder dashboard: a character dropdown and a multi-select of skills, a mindstate-over-time plot for one day showing two training sessions filling to 34 and draining between pulses, a range slider beneath it, and a table of each skill's current rank, percent and mindstate](docs/beholder.png)

A browser dashboard over the history every session logs to `~/.revenant/xp.db`: mindstate and rank over time per character and skill, plus the sheet snapshots (stats, circle, wealth, inventory) and the circle gates. View → Experience History embeds it in the client, `;beholder` opens it in a browser, `uv run beholder` runs it by hand. See [beholder/README.md](beholder/README.md).

## Chat

![The standalone chat window: LNet's welcome, then Lanival's whole circle on the DRPrime channel — Sable, Glacis, Uthmor, Arhat, Ka'len, Nissa, Eerayn, Sildua, and Teiro getting untuned by the operator — a private exchange with Sable, and a ;chat on command being typed; the status bar reads Connected as Lanival](docs/chat-troop.png?v=3)

`uv run revenant-chat` opens a window on LNet, the Lich project's chat server, as one of your characters; `;lnet` brings the same chat into the game window's Thoughts dock. Both share the [chat/](chat/) library and the classic commands (`chat to <name> <msg>`, `reply`, `who`, `channels`, `tune`).

> **LNet's rule: only log in as a character who is in the game right now.** Being on LNet as a character who is not logged into DragonRealms is a bannable offence there. The window makes that easy to forget, so open it only while that character is playing, and close it when they log out.

Passwords, logging, and the protocol: [docs/chat.md](docs/chat.md).

## Docs

- [running.md](docs/running.md) — launching, quit versus detach, which edits need which restart, `;reexec`, settings, logs
- [scripting.md](docs/scripting.md) — writing a script
- [chat.md](docs/chat.md) — LNet: the window, `;lnet`, passwords, logs, protocol
- [movement.md](docs/movement.md), [death.md](docs/death.md), [favors.md](docs/favors.md), [circles.md](docs/circles.md), [experience.md](docs/experience.md), [eltime.md](docs/eltime.md), [combat.md](docs/combat.md) — the game models the scripts implement, each with its captured evidence
- [architecture.md](docs/architecture.md) — how the pieces fit, module by module, with the history of why
- [protocol.md](docs/protocol.md) — the wire protocol the parser implements
- [why-python.md](docs/why-python.md) — what leaving the Ruby toolchain buys and costs

The other directories: [launcher/](launcher/) starts the external Lich and ProfanityFE toolchain side by side, a template rather than a tool.

## About

Revenant is a hobby, built for fun and for the author's own play. It is inspired by Lich and the community's scripts, and exists because nothing like them existed for Python; [docs/why-python.md](docs/why-python.md) records the trade. The client, GUI, chat client and beholder were hand-written and working years before any AI was involved (the history runs from 2018). Since spring 2026 much of the new code is written with Claude Code, and the commit history says which; it speeds up delivery, and the direction is the author's.

Expect to read code before running anything. Shout out to [Pylanthia](https://github.com/robbintt/pylanthia), a great related project.

## Friends

Revenant stands on the DragonRealms community's open work, and credit belongs where the work was done. These are the repositories worth knowing; several are direct dependencies.

- [robbintt/pylanthia](https://github.com/robbintt/pylanthia) — a threaded Python DragonRealms client for headless use: the other Python take on this game, and an early inspiration.
- [elanthia-online/lich-5](https://github.com/elanthia-online/lich-5) — Lich, the scripting engine most of the DR world runs on. Revenant's session-and-scripts split is modeled on it, and `;lnet` is a 1:1 port of `lnet.lic`.
- [elanthia-online/dr-scripts](https://github.com/elanthia-online/dr-scripts) — the community's Lich scripts for DragonRealms: the reference for what a script ecosystem grows into, and where the `;`-command habits come from.
- [elanthia-online/mapdb-backup-dr](https://github.com/elanthia-online/mapdb-backup-dr) — the community map. Downloaded on first use for the Map dock and `;go2`, never vendored.
- [elanthia-online/ProfanityFE](https://github.com/elanthia-online/ProfanityFE) — the terminal frontend. What to use for a TUI today, and what [launcher/](launcher/) pairs with Lich.
- [elanthia-online/illthorn](https://github.com/elanthia-online/illthorn) — an Electron frontend for Lich.
- [elanthia-online/Lichborne](https://github.com/elanthia-online/Lichborne) — a community-driven DragonRealms client for Lich users.
- [GenieClient/Genie4](https://github.com/GenieClient/Genie4) — Genie, the .NET frontend, with its own script language and plugin scene.
- [elanthia-online/dr-spell-trees](https://github.com/elanthia-online/dr-spell-trees) — Graphviz spell trees, one per guild.
- [elanthia-online/simu-rewards](https://github.com/elanthia-online/simu-rewards) — a GitHub Action that claims the daily Simutronics rewards.
- [Elanthipedia](https://elanthipedia.play.net/) — not a repository, but every mechanic Revenant automates was read up there first.

Shout out to Atanamir, who helped get `;reply` working on LNet.

[docs/bibliography.md](docs/bibliography.md) credits each feature's sources individually.

## License

MIT (see [client/pyproject.toml](client/pyproject.toml)).
