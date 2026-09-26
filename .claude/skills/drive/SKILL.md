---
name: drive
description: Drive a running DragonRealms session from Claude — send a command, read the game's answer, act on the operator's character with their say-so. Use whenever the operator asks to try, test, check, capture or do something in the game ("try it on X", "run ;script and check", "what does INFO say", "capture the wording"), or when a script's assumption needs a live reading.
---

# Driving a session

Claude reaches the game only through `revenant-send`, tagged as itself,
and reads the answer through the same command. Everything sent shows in
the operator's window as `>> [claude] ...`.

## The rules

1. **Say-so first for anything that acts.** Moving, spending TDPs or
   coins, TRAIN, wearing, removing, dropping, stowing, giving, attacking:
   only when the operator asked for that in this conversation. A request
   to "try" or "test" a script is say-so for what that script does.
2. **Read the session before asking the game.** `revenant-send
   --state` (all of it, or `--state room,vitals,hands`) prints what
   the parser already holds — the room and compass, vitals, the exp
   window's ranks and mindstates, hands, posture and badges, injuries,
   spells, who and what is in the room — with nothing typed at the
   character and nothing echoed (#216); `--wait-for TEXT` waits for a
   story line instead of polling the log. Read-only commands may go
   out for what the parser does not hold: INFO, the stat words
   (AGILITY, STRENGTH, ...), TDP, TDP PROJECT, ENCUMBRANCE, VAULT
   TIME, BANK ACCOUNT, WEALTH, TIME, HEALTH, ABILITY LIST. They cost no roundtime
   and change nothing. INFO prints a long block in the window; ask
   once and keep the answer.
3. **The session refuses what an outsider must not do** (#161): GIVE,
   HAND, OFFER of an item (an OFFER of an amount alone is a catalog
   merchant's bid and passes, #234), SELL, TRADE, EXCHANGE, ACCEPT,
   WITHDRAW, TRAIN, STUDY of a stat (STUDY MY BOOK, a crafting page, passes),
   DEPART, QUIT, EXIT, DISCARD, DROP of anything but the junk list,
   PUT into anything but the character's own container, `;reexec`,
   and any noun in the character's `~/.revenant/policy/<name>.json`
   valuables. A refusal echoes "session: refused [claude] ... — <why>"
   in every window; ask the operator to send it themselves, or to add
   the verb to the file's `allow` list (a denied verb, or `put` for
   the own-container rule — an almsbox tithe, #219; the session
   re-reads the file on change, but the rule itself is engine code, so
   a session started before #219 needs a `;reexec` or a relaunch),
   never look for a way round.
4. **Never a bare send** (it reads `[external]`), never an ad-hoc socket
   driver, never a change to the "allow external sends" setting. A gated
   command opens the gate for that one call with `REVENANT_ALLOW_SEND=1`.
5. **Report what was sent and what the game answered**, verbatim where
   the wording matters; a captured wording goes into the script's fixture
   and the docs in the same change (CLAUDE.md: fixtures pin what we
   believe the server sends).
6. **Never a name in the repo.** Logs and answers carry the operator's
   character and account names; the synthetic cast replaces them in
   anything committed (Lanival, Sable, Uthmor, TESTACCT).

## The procedure

```sh
# which sessions run, and on which port
cat ~/.revenant/sessions.json

# the parser's state, no command sent (all fields, or a comma list)
uv run revenant-send --origin claude --character NAME --state
uv run revenant-send --origin claude --character NAME --state room,status,hands

# a command, then wait up to 60 s for the story line that answers it
REVENANT_ALLOW_SEND=1 uv run revenant-send --origin claude --character NAME --wait-for "ragged pants" --timeout 60 "focus orb"

# a read-only command, with the answer printed (stay attached 4 s)
uv run revenant-send --origin claude --answer 4 --character NAME "tdp"

# a command that acts, with the operator's say-so, one call of the gate
REVENANT_ALLOW_SEND=1 uv run revenant-send --origin claude --answer 6 --character NAME "stand"

# a script, and a word typed at it while it runs
REVENANT_ALLOW_SEND=1 uv run revenant-send --origin claude --character NAME ";tdp train stamina +2"
uv run revenant-send --origin claude --character NAME ";tdp help"
```

- Use `--port N` when the registry has lost the row (#160); the port is
  in the sessions file or the launcher's log.
- `--answer` prints the story lines that followed the line's own echo
  and the scripts' own echoes (`[soul] walking 20 steps ...`, a
  refusal's reason — since 2026-09-20; before that a script's answer
  was invisible here); a command with roundtime (POWER 8-12 s, CLIMB,
  INV LIST) needs a window longer than it, and a long walk or a
  script's whole run needs the log
  instead: `~/.revenant/logs/game-<Name>-<stamp>.log`, the newest with the character's name,
  read with the XML stripped (`sed 's/<[^>]*>//g'`). Scripts' echoes go
  to the windows, not the game log; the session's debug log
  (`revenant_client-*.log`) has script starts and external sends.
- A script typed with `help` prints its manual without running it.
- Between dependent commands, wait the roundtime (the answer's
  "Roundtime: N sec." line) before the next; the engine's own scripts
  do this with `s.waitrt()`, a sender has to sleep.
- After the run, INFO or the relevant read-only command confirms the
  state the script claimed; the game's own figures are the judge, not
  the script's echo.

## Things that bit before

- **DIR STAT starts a hint that repeats every few lines until DIR STOP**
  — never use it; the map's tags know the rooms.
- **A registry row can vanish** (#160): a send by `--character` then
  fails; `--port` still works.
- **A running session cannot see an edit** to a `client/` module it
  first imported before that module joined the reload list; a script
  importing a new name from it fails to load until the session is
  restarted. Scripts themselves always load fresh.
- **A busy town room buries an answer** under arrivals and departures:
  filter those lines out when reading the log, or use `--answer`.
- **The parser's state lags the story line** (posture, hands): read the
  answer text, not the indicator, right after a command.
- **Every session change today needed a note somewhere durable**: an
  issue for a gap, a doc section for a mechanic, a fixture for a wording.
