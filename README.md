<p align="center">
  <img src="client/client/gui/revenant.svg" width="128" alt="The revenant icon: Elanthia's three moons — black Katamba ringed in miasma, crimson Yavash, blue Xibar, and the shards of Grazhir">
</p>

# Revenant

A Python client for [DragonRealms](https://www.play.net/dr/): a detachable game session with a script engine, a PyQt6 window, an experience-history dashboard, and an LNet chat client. Hobby-grade, built for fun, and not a replacement for anything.

## Install and first run

The quickest way is a packaged build from the [Releases](https://github.com/jandersson/revenant/releases) page: a Windows installer or a macOS disk image, no Python needed ([running.md](docs/running.md) has the details). From source you need [git](https://git-scm.com/), [uv](https://docs.astral.sh/uv/getting-started/installation/), and a DragonRealms account. uv fetches a Python of its own if the machine has none.

```sh
git clone https://github.com/jandersson/revenant.git
cd revenant
uv sync          # creates .venv and installs everything, Python included if needed
uv run revenant  # first run: a login window
```

The login window asks for your account, password, and character (the roster is fetched from the server once the account and password are in). Tick *remember* and the password goes to your OS keychain and the names to `~/.revenant/login.json`; the next `uv run revenant` logs straight in. Nothing is ever written to a file in plain text. The game window appears with "Connected" in the status bar, and the community map downloads on first use of `;go2` (or any script that walks) and again once it is a week old.

Run the commands from the repository root; that is where `uv` finds the workspace and the session finds its scripts.

**Windows:** a Start Menu shortcut that opens the character picker, pinnable to the taskbar (the button's right-click menu then launches another character):

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_shortcut.ps1
```

**macOS:** `uv run python tools/build_app.py` builds `~/Applications/Revenant.app`.

[docs/running.md](docs/running.md) is the operating manual from here: launching a named character, several at once, quitting versus detaching, and which edits need which restart.

## The client

![The game window, live: a Moon Mage in the Observatory's third level, the guild register scrolled past, three attempts to find a burp command (burp, brap, belch: please rephrase), the map drawn around the room, the compass lit with the exits, Thoughts, Arrivals and Deaths in their docks, the Elanthian clocks, and the vitals bars above the input line](docs/screenshot.png)

One session per character, any number of windows attached to it, lich-style. The session logs in, owns the game socket, serves parsed text to every attached frontend over localhost, and hosts the script engine: `;list`, `;run <name>`, `;stop <name>`, `;help <name>`. A script is a `main(s)` in [scripts/](scripts/), reloaded from disk every time it starts; [docs/scripting.md](docs/scripting.md) is the guide.

The window shows the game's own styling and clickable links, puts the map's room id after each room name (`[The Crossing, Town Green] (1420)`, the id `;go2` takes), and keeps the rest in docks:

- **Experience** — rank, percent and mindstate of each learning skill.
- **Map** — the community map around you; click a room to walk there.
- **Injuries** — wounds and scars on a body diagram, live.
- **Spells** — the active spells with their time left, and the one prepared.
- **Compass, Clocks, Thoughts, Arrivals, Deaths, Group, Talk** — clickable exits, the Elanthian calendar, the game's side streams.
- **Input line** — roundtime and casttime countdowns, vitals, posture and status, command history.

A dock folds to its title bar with its ▾ button. File → Settings covers the font, the autostarts and the room ids. Scripts stow items, never drop them.

`;help` lists every bundled script with its manual. The main ones:

| Script | What it does |
|---|---|
| `;go2` | walks to a room on the community map |
| `;train` | runs the trainers a per-character plan names, then rests while the skills drain |
| `;hunt` | hunts from a per-character profile (File → Character Profile…) |
| `;heal`, `;tend`, `;empath` | treats wounds and bleeding; an Empath's healing |
| `;deathwatch` | watches for a death while you are away |
| `;trade`, `;commodities`, `;kiosk` | a Trader's caravans, commodity pits and kiosk |
| `;xp`, `;sheet`, `;wealth` | log experience, the character sheet and money to history.db |

## Driven by an LLM

![The game window, live, while Claude buys a Paladin a weapon for a new skill: ;go2 walking him north through the Crossing to Milgrym's Weapons, then dim ">> [claude] look on rack", ">> [claude] appraise sledgehammer on rack" (it trains the large blunt skill, though it sits on the two-handed rack), ">> [claude] buy sledgehammer" and ">> [claude] put my sledgehammer in my backpack" lines, each followed by the game's answer; the Experience dock beside the story; the Thoughts dock's LNet chat rewritten among the synthetic cast and other players' deaths blanked](docs/claude-driven.png)

An AI agent can play alongside you. `revenant-send` puts one command into a running session from outside and prints what the game answered, and every line it sends shows in every window as `>> [claude] …`, so you can always tell the agent's commands from your own. `--state` reads what the parser already knows (room, vitals, hands, the exp window, who and what is in the room) as JSON without typing anything at the game, and `--wait-for` waits for a line instead of polling. [running.md](docs/running.md) has the details.

The agent is kept on a short leash. Read-only commands (INFO, EXP, WEALTH, HEALTH) always pass; anything that acts on the character needs the send gate opened for that one call; and the session itself refuses an outside GIVE, SELL, WITHDRAW, TRAIN or DROP whatever the gate says, unless a per-character file allows that verb. Scripts do the long work: the agent starts `;train` or `;hunt`, watches the session log, and fixes what breaks.

It is set up for [Claude Code](https://claude.com/claude-code): [.claude/CLAUDE.md](.claude/CLAUDE.md) holds the project's conventions, the `drive` skill is the procedure for acting on a character and the `experiment` skill the method for testing a game mechanic live, and [.claude/learnings.md](.claude/learnings.md) records what went wrong before. Any agent that can run a shell command can use `revenant-send`. The screenshot is a live session: Claude checking what the sledgehammer trains before spending the coin.

## Beholder

![The beholder dashboard over a Trader's day and a half: the character dropdown; the skills-moving chart, three skills overnight, nine or ten through the morning's research and trading, then Trading alone; the skills multi-select with ten chosen; and the mindstate-over-time plot of those ten, the rested-experience windows shaded and named once in the legend, Trading filling and draining on its own at the end](docs/beholder.png?v=3)

A browser dashboard over the history every session logs to `~/.revenant/history.db`: mindstate and rank over time per character and skill, plus the sheet snapshots (stats, circle, wealth, inventory) and the circle gates. View → Experience History embeds it in the client, `;beholder` opens it in a browser, `uv run beholder` runs it by hand. See [beholder/README.md](beholder/README.md).

## Chat

![The standalone chat window: LNet's welcome, then Lanival's whole circle on the DRPrime channel — Sable, Glacis, Uthmor, Arhat, Ka'len, Nissa, Eerayn, Sildua, and Teiro getting untuned by the operator — a private exchange with Sable, and a ;chat on command being typed; the status bar reads Connected as Lanival](docs/chat-troop.png?v=3)

`uv run revenant-chat` opens a window on LNet, the Lich project's chat server, as one of your characters; `;lnet` brings the same chat into the game window's Thoughts dock. Both share the [chat/](chat/) library and the classic commands (`chat to <name> <msg>`, `reply`, `who`, `channels`, `tune`).

> **LNet's rule: only log in as a character who is in the game right now.** Being on LNet as a character who is not logged into DragonRealms is a bannable offence there. The window makes that easy to forget, so open it only while that character is playing, and close it when they log out.

Passwords, logging, and the protocol: [docs/chat.md](docs/chat.md).

## Docs

- [running.md](docs/running.md) — launching, quit versus detach, which edits need which restart, `;reexec`, settings, logs
- [scripting.md](docs/scripting.md) — writing a script
- [chat.md](docs/chat.md) — LNet: the window, `;lnet`, passwords, logs, protocol
- [movement.md](docs/movement.md), [death.md](docs/death.md), [favors.md](docs/favors.md), [circles.md](docs/circles.md), [experience.md](docs/experience.md), [training.md](docs/training.md), [healing.md](docs/healing.md), [social.md](docs/social.md), [encumbrance.md](docs/encumbrance.md), [eltime.md](docs/eltime.md), [combat.md](docs/combat.md), [soul.md](docs/soul.md), [wounds.md](docs/wounds.md), [kiosk.md](docs/kiosk.md), [caravans.md](docs/caravans.md), [shops.md](docs/shops.md) — the game models the scripts implement, each with its captured evidence; [paladin.md](docs/paladin.md) and [barbarian.md](docs/barbarian.md) — a guild's measured facts indexed in one place, the model per fact linked
- [architecture.md](docs/architecture.md) — how the pieces fit, on one page
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
- [elanthia-online/mapdb-backup-dr](https://github.com/elanthia-online/mapdb-backup-dr) — the community map. Downloaded on first use of `;go2` and refreshed weekly, never vendored.
- [elanthia-online/ProfanityFE](https://github.com/elanthia-online/ProfanityFE) — the terminal frontend. The terminal frontend [launcher/](launcher/) pairs with Lich; revenant's own is `revenant-tui`, which attaches to a running session (docs/running.md).
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
