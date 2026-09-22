"""Getting away from hostiles — the one escape every trainer shares (#285).

The Crossing's auto invasion of 2026-09-22 found Cecil sitting between
climbs outside the western gate: `;athletics` retreated and climbed,
the climb failed for footing, the goblin re-advanced every cycle, and
RETREAT from a seated character does nothing (#286); every other
trainer just stops and leaves the character standing among the
hostiles. This module is the answer they all give now:

1. STAND when the posture is known and not standing (the indicator).
2. The burst — RETREAT, RETREAT, a move — back to back through the
   game's type-ahead (docs/combat.md, field-proven since #72: spaced
   commands lose the race to a re-advance). Two retreats step melee →
   pole → out of combat ("You retreat back to pole range." / "You
   retreat from combat." / "You are already as far away as you can
   get!", Elanthipedia: Retreat command); the move is one of the
   caller's preferred steps first (a climb along the training edge:
   the cave-bear stalemate of #86 is escaped by climbing), then the
   room's compass exits, then OUT.
3. Success is the ROOM changing, or no hostile left — never the
   answer's wording; a failed climb leaves the room the same and the
   next attempt takes the next move.

lich-5's `DRC.retreat` loops RETREAT with `fix_standing` until an
escape line; dr-scripts' `gosafe` and `safe-room` walk to a configured
safe room (docs/bibliography.md). `react` is the whole ladder with the
echoes and the bell; `flee` the burst loop; `to_safety` the walk.
Nothing is ever dropped.
"""

from client.game.status import status

ATTEMPTS = 8  # bursts before the caller is told it did not get clear
SETTLE = 1  # seconds after a burst for the room frame to land


def hostiles_present(state):
    return bool(getattr(state, "hostiles", None))


def moves(state, preferred=()):
    """The moves to try, in order: the caller's preferred steps, the
    room's compass exits, OUT — each once."""
    exits = list(getattr(state, "compass", None) or [])
    seen = []
    for move in [*preferred, *exits, "out"]:
        if move and move not in seen:
            seen.append(move)
    return seen


def burst(s, move):
    """STAND if seated or prone, then RETREAT, RETREAT, the move, all
    through the type-ahead; the roundtime waited out and a second for
    the room frame."""
    view = status(s.state)
    if view.posture and not view.standing:
        s.put("stand")
    s.put("retreat")
    s.put("retreat")
    s.put(move)
    s.waitrt()
    s.sleep(SETTLE)


def flee(s, preferred=(), attempts=ATTEMPTS):
    """Bursts until the room changes or no hostile is left; True then,
    False after `attempts` bursts with the character still held."""
    for attempt in range(attempts):
        before = getattr(s.state, "room_uid", None)
        candidates = moves(s.state, preferred)
        burst(s, candidates[attempt % len(candidates)])
        if getattr(s.state, "room_uid", None) != before:
            return True
        if not hostiles_present(s.state):
            return True
    return False


def to_safety(s, mapdb, walk, goals, avoid=()):
    """The walk to a safe room (a plan's safe_rooms, a profile's home)
    with the rooms in `avoid` routed around; False when the map has
    no such room or the walk failed."""
    if not goals:
        return False
    return bool(walk(s, mapdb, set(goals), describe="safety", avoid=avoid))


def react(s, prefix, preferred=(), attempts=ATTEMPTS):
    """A trainer's answer to hostiles in the room: said, the bell rung,
    the burst loop run, the outcome said. True when clear of them."""
    s.echo(f"{prefix}: hostiles here — getting away")
    emit = getattr(s, "emit", None)
    if callable(emit):
        try:
            emit("", "bell")
        except Exception:  # a fake without the stream, a stopped script
            pass
    fled = flee(s, preferred, attempts)
    if fled:
        room = getattr(s.state, "room_title", None) or "the next room"
        s.echo(f"{prefix}: clear of them — {room}")
    else:
        s.echo(
            f"{prefix}: could not get clear in {attempts} tries — intervene if you can"
        )
    return fled
