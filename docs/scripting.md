# Writing scripts

A script is a Python file in `scripts/` defining `main(s)` — drop the
file in, type `;run <name>` in any frontend, and it runs. No restart,
no registration: every `;run` loads the file fresh from disk — and
reloads the `client/` helper modules scripts lean on (probe, walker,
mapdb, inventory, circles, climbs, eltime, settings, textfont) when
their files changed since import, announcing which. A walker fix
reaches a running session through `;stop go2` and `;go2`, the way
lich's common scripts do. The session, engine and parser never reload
that way; `;reexec` replaces those. With developer mode on (File →
Settings, or `REVENANT_DEV=1` for one launch) a start that takes more
than half a second to load says so — "go2 took 1.3s to load (reloaded
client.mapdb, client.walker)" — which is how an import that does work
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
| `s.put("look")`               | send a command to the game (echoed to frontends)                          |
| `s.echo("hi")`                | show text in frontends only — never sent to the game                      |
| `s.emit(text, "thoughts")`    | frontend text on a chosen stream (lands in that dock)                     |
| `s.get(timeout=5)`            | next main-stream game line; `None` on timeout; `timeout=0` polls          |
| `s.get(streams=None)`         | every stream as `(stream, text)` — includes the synthetic ones below      |
| `s.waitfor(r"pattern", ...)`  | block until a line matches any regex; the line, or `None` on timeout      |
| `s.waitrt()`                  | sleep out any active roundtime or cast time                               |
| `s.sleep(2)`                  | sleep that wakes instantly when the script is stopped                     |
| `s.command(timeout=0)`        | the next line a user typed at you (`;forage <line>` while running)        |
| `s.state`                     | the parsed game state: `room_title`, `room_uid`, `compass`, `experience`, ... |
| `s.args`                      | the arguments from `;run forage rock` → `["rock"]`                        |

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
