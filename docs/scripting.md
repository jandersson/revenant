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

## Asking the game

`client/game/act.py` is how a script asks and reads the answer; a script never writes its own copy of these.

| Call | Does |
| --- | --- |
| `act.ask(s, cmd)` | the answer as the game wrote it, roundtime tail included (`probe.ask` with one pair of windows) |
| `act.missing(answer)` | true for either not-found wording ("What were you referring to?", "I could not find...") |
| `act.said(answer, needles)` | the line to quote: the one holding a needle, never a bystander's that landed first |
| `act.unknown(s, prefix, what, answer)` | the one "please report it" echo, the line returned |

`probe.classify(answer, table)` names the first outcome whose wording the answer holds.

## Hands and items

| Call | Does |
| --- | --- |
| `hands.held(s)` / `hands.holding(s, noun)` / `hands.full(s)` | what the hands hold, off the parser's tags |
| `hands.mark(s)`, then `hands.passed_through(s, since, noun)` | an item's tag after a STOW that took it straight off the ground, though the hand emptied on the same line |
| `hands.free(s, keep=(...), ask=ask)` | STOW what is not kept (never DROP); `free_one` frees a hand only when both are full |
| `hands.stow(s, noun, ask=ask)` | one STOW, the answer judged; a STORE container with no room refuses and the game does not fall back, so the item goes into the default container (STORE DEFAULT) by PUT instead |
| `hands.at_end(s, nouns)` | a `finally`'s put-backs: STOW each still held, as cleanup puts |
| `items.name(s, "dried red flowers")` | the held item's `#id`, else the name whole — what a command takes (a bare noun takes the first item of that noun) |
| `items.containers(possessions, holding=word)` | the containers INV LIST shows, in listing order |
| `items.listed(answer)` / `items.count(answer)` | a LOOK IN listing; COUNT's pieces |
| `money.carried(s, "Kronars", ask)` | the purse, off WEALTH |
| `shop.afford(s, ask, prefix, copper)` / `shop.buy(s, ask, prefix, "order 7", expect="nugget")` | the shortfall fetched at the teller; one purchase, the quote checked and the sale closed the shop's way |

## Training and walking

| Call | Does |
| --- | --- |
| `trainer.train(s, prefix, skill, step)` | the trainer loop: `step(s)` until the skill locks (then holds until it drains, or ends with `once=True`), a typed return, death or hostiles (the shared escape); `finish(s, why)` at every end |
| `trainer.hold_at_lock(s, prefix, skill, until)` | the hold alone, for a loop of the script's own |
| `travel.go(s, target, describe)` | walk to a ;go2 target (an id, a tag, a title, or ids), `avoid_rooms` routed around; `db=` and `walk=` for a test's fakes |
| `travel.here(s)` | the map id of the room, or `None` |

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
