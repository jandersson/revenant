# Writing scripts

A script is a Python file in `scripts/` that defines `main(s)`; `scripts/forage.py` becomes `;forage`. Drop it in and type `;forage` — no restart, no registration.

## A script

```python
"""Forage an item repeatedly, with a running count:  ;forage rock

    ;forage [item]    forage until stopped (default: rock)
"""


def main(s):
    item = " ".join(s.args) or "rock"
    found = 0
    while True:
        s.put(f"forage {item}")
        line = s.waitfor(r"You manage", r"discern nothing", timeout=30)
        if line and "manage" in line:
            found += 1
            s.echo(f"{found} so far")
        s.waitrt()
        s.sleep(1)
```

- The module docstring is the manual: `;help forage` and `;forage help` print it. Open it with the usage lines.
- The script runs as a thread in the session, so it keeps going with no window open. A crash echoes the file and line.
- `scripts/hello.py` is the minimal template.

## The handle

| Call | Does |
| --- | --- |
| `s.put(cmd)` | send a command; `cleanup=True` still goes out after a `;stop` (for a `finally:`) |
| `s.echo(text)` | show text in the windows, never sent |
| `s.emit(text, stream)` | text on a chosen stream, e.g. `"thoughts"` |
| `s.get(timeout)` | next story line, or `None`; `streams=None` gives every `(stream, text)` |
| `s.waitfor(*regex, timeout=)` | the first line matching any pattern, or `None` |
| `s.waitrt()` | sleep out roundtime; `cast=True` the cast time too |
| `s.sleep(n)` | a sleep that ends at once on `;stop` |
| `s.flag(name, *regex)` / `s.flagged(name)` / `s.unflag(name)` | watch for a line while doing other things |
| `s.command(timeout)` | the next line typed as `;<name> <line>` |
| `s.args` | the arguments |
| `s.state` / `s.status` | the parser's state; the same in words (`.stunned`, `.mindstate("Athletics")`) |
| `s.dead` | true while the character is dead |
| `s.run(name, args)` / `s.is_running` / `s.tell` / `s.kill` / `s.crashed` | drive other scripts, as `;train` does |

## Controlling scripts

```
;list                  what runs, what exists
;<name> [args]         start (or ;run <name>)
;stop <name|all>       stop at once (;k; a unique prefix works)
;<name> <line>         hand a line to a running script
;<name> return         the graceful end: finish up, walk home
```

## Caveats

- Every start loads the script fresh and reloads the changed helper modules (walker, probe, profile...). A script already running keeps the code it imported; restart it to get the new code.
- The session, parser and engine never reload that way — use `;reexec`.
- Keep the logic out of `main(s)` so it tests headlessly; tests in `client/tests/` are the manual.
