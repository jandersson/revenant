"""Tell whatever script is running to take a break for a chore.

  ;break            the chores and the requests not yet honored
  ;break almanac    study the almanac at the next safe point
  ;break sweep      the loot sweep's dry run: name what it would trash, move nothing
  ;break gems       loose gems from the loot and default containers into the gem pouch

- The request is honored by the first running script to reach a safe
  point (between two of its steps): ;perform, ;remedies, ;athletics,
  ;train between tasks, ;hunt in a clear room, and the rest.
- With both hands full the left hand's item is stowed for the chore
  and got back after it; ;boxes and ;perform wait for a free hand.
- With no script running, ;break does the chore itself, at once.
- Never with something hostile in the room or while stunned; never in
  ;favors. The almanac also runs on its own timer (the profile's
  `almanac`); ;break is for sooner.
- The sweep itself runs on its own once the profile's `loot_sweep` is
  on: beside a bin, the `loot_ignore` items out of the loot container
  and into the trash, each named.
- The gems chore runs on its own once a session and after a gem goes
  loose (a full pouch); a full pouch stops it until the pouch takes one.

Model: client/game/interlude.py. Doc: docs/training.md.
"""

from client.game import interlude


def main(s):
    words = [word.lower() for word in s.args]
    if not words:
        s.echo(
            f"break: chores {', '.join(sorted(interlude.REGISTRY))}; "
            f"requested {', '.join(interlude.pending()) or 'none'}"
        )
        return
    chore = words[0]
    if not interlude.post(chore):
        s.echo(f"break: no chore {chore!r} — {', '.join(sorted(interlude.REGISTRY))}")
        return
    busy = [name for name in s.running_scripts() if name not in interlude.BACKGROUND]
    if busy:
        s.echo(f"break: {chore} at the next safe point of ;{', ;'.join(busy)}")
        return
    interlude.run_due(s)
    if chore in interlude.pending():
        s.echo(
            f"break: not now (hostiles, a stun, or no hand) — {chore} waits for a safe point"
        )
