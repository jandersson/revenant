"""Walk a saved route:  ;go <destination>     (;go alone lists them)

A route is a plain list of movement commands. After each step the script
waits for the next room's compass (the arrival signal) and sleeps out any
roundtime before continuing, so climbs and swims pace themselves. If a
step produces no room change within 10 seconds it stops where it stands.

Add your own routes to ROUTES below, e.g.:
    "bank": ["n", "n", "w", "go bridge", "nw"],
"""

ROUTES = {
    # Three looks in place: exercises the walker without moving a step.
    "selftest": ["look", "look", "look"],
}


def main(s):
    if not s.args:
        s.echo("destinations: " + (", ".join(sorted(ROUTES)) or "(none yet)"))
        return
    name = s.args[0].lower()
    route = ROUTES.get(name)
    if route is None:
        s.echo(
            f"no route named {name!r} — destinations: "
            + (", ".join(sorted(ROUTES)) or "(none yet)")
        )
        return
    s.echo(f"walking {name} ({len(route)} steps)")
    for number, step in enumerate(route, 1):
        s.waitrt()
        s.put(step)
        if s.get(timeout=10, streams=("compass",)) is None:
            s.echo(f"stalled at step {number} ({step!r}): no room in 10s, stopping")
            return
    s.waitrt()
    s.echo(f"arrived: {name}")
