# Writing scripts

A script is a Python file in `scripts/` defining `main(s)` — drop the
file in, type `;run <name>` in any frontend, and it runs. No restart,
no registration: every `;run` loads the file fresh from disk — and
reloads the `client/` helper modules scripts lean on (probe, walker,
mapdb, inventory, circles, climbs, eltime, settings, textfont) when
their files changed since import, announcing which. A walker fix
reaches a running session through `;stop go2` and `;go2`, the way
lich's common scripts do. The reload is a fresh copy of the module:
a script already running keeps the functions it imported (and their
globals), so an edit that changes a helper's shape cannot reach into
a running walk, and the announcement names the scripts that keep
their code (#181). The session, engine and parser never reload
that way; `;reexec` replaces those. With developer mode on (File →
Settings, or `REVENANT_DEV=1` for one launch) a start that takes more
than half a second to load says so — "go2 took 1.3s to load (reloaded
client.game.mapdb, client.game.walker)" — which is how an import that does work
it should defer gets noticed.

## Where scripts live

`scripts/` at the repo root (override with `REVENANT_SCRIPTS`). The
filename is the command name: `scripts/forage.py` becomes `;forage`.

## Anatomy

```python
"""Forage an item repeatedly, with a running count:  ;forage rock

Waits out roundtime between attempts. Stop with:  ;stop forage
"""


def main(s):
    item = " ".join(s.args) or "rock"
    found = 0
    while True:
        s.put(f"forage {item}")          # send to the game
        line = s.waitfor(r"You manage", r"discern nothing", timeout=30)
        if line and "manage" in line:
            found += 1
            s.echo(f"{found} so far")    # frontend-only message
        s.waitrt()                        # sleep out roundtime
        s.sleep(1)                        # stop-aware pause
```

Two rules: the module docstring is the user manual (`;help forage`
prints it verbatim — write it as one), and `main(s)` is the entry
point. The script runs as a thread inside the session, so it keeps
going if you close the GUI, and a crash echoes the file and line into
your frontend.

## The handle: everything `s` can do

| Call                          | What it does                                                             |
| ----------------------------- | ------------------------------------------------------------------------ |
| `s.put("look")`               | send a command to the game (echoed to frontends, DEBUG in the session's debug log) |
| `s.echo("hi")`                | show text in frontends — never sent to the game; kept in the session's debug log at INFO, so a report ("unrecognized ... answer") can be read back later (#241) |
| `s.emit(text, "thoughts")`    | frontend text on a chosen stream (lands in that dock)                     |
| `s.get(timeout=5)`            | next main-stream game line; `None` on timeout; `timeout=0` polls          |
| `s.get(streams=None)`         | every stream as `(stream, text)` — includes the synthetic ones below      |
| `s.waitfor(r"pattern", ...)`  | block until a line matches any regex; the line, or `None` on timeout      |
| `s.waitrt()`                  | sleep out any active roundtime; `s.waitrt(cast=True)` the pattern's cast time too — a forming pattern holds no command but the CAST (#249) |
| `s.sleep(2)`                  | sleep that wakes instantly when the script is stopped                     |
| `s.command(timeout=0)`        | the next line a user typed at you (`;forage <line>` while running)        |
| `s.state`                     | the parsed game state: `room_title`, `room_uid`, `compass`, `experience`, ... |
| `s.args`                      | the arguments from `;run forage rock` → `["rock"]`                        |
| `s.run("athletics", ["list"])` | start another script as `;run` would; `False` (reason echoed) when it can't |
| `s.is_running("athletics")`   | whether that script's thread is alive                                     |
| `s.tell("hunt", "return")`    | hand a running script a line, as typing `;hunt return` would              |
| `s.kill("athletics")`         | stop another script (safe from a `finally:` while you are being stopped)  |
| `s.crashed("hunt")`           | how that script's last run died (`"ValueError(...) (file:line)"`), or None |

The last five are what an orchestrator needs: `;train`
(`scripts/train.py`) starts a task's script, polls the exp window
until the task's skills reach their target, tells the script its
return word (`;hunt return` finishes the kill and walks home) and
kills it after a grace. The convention for every script: a typed
`return` is the graceful end, `;stop <name>` the abrupt one — and at
a script that is not running the word is nothing to do ("not running
— nothing to return from"), never a launch: on 2026-09-23 a
`;remedies return` sent after `;stop train` had already taken the
task down started a training run instead, and its leftover salve
broke the next order (#298). A script the user started by hand is theirs — `s.run`
refuses it rather than adopting it. Model: [training.md](training.md).

Synthetic streams worth knowing: `compass` (one frame per room, the
arrival signal), `exp` (the Experience dock's text), `room`
(`uid\ttitle` per room change), and `sent` (every outbound command —
pair it with `room` to observe movement, the way `;survey` does).

## Controlling scripts

```
;list                     what's running, what's available
;help <name>              the script's docstring
;run <name> [args]        start (or just  ;<name> [args])
;stop <name|all>          stop (;k and ;kill work too; a unique prefix
                          of a running script is enough: ;k mech)
;<name> <line>            deliver <line> to a running script
```

## Conventions for bundled scripts

Scripts shipped in the repo follow the house rules: tests in
`client/tests/` double as the manual (see `test_athletics.py`), pure
logic split from the `main(s)` loop so it tests headlessly, and no
real names or account identifiers anywhere. `scripts/hello.py` is the
minimal template; `scripts/athletics.py` is the full-featured example
(travel, state reading, pacing).
