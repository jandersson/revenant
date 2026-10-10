"""Astral travel from the Grazhir shard you stand at to another:  ;astral <shard>

    ;astral besoge          Moongate in through this room's shard, to Besoge's conduit, Moongate out in Mer'Kresh
    ;astral besoge round    there and back: ends at the shard it started from (a ;train task for Astrology, Attunement)
    ;astral besoge from=8302   walk to that ;go2 target (a shard's room) first
    ;astral besoge harness=200   harness that much mana before entering (100 by default) and when the plane presses
    ;astral list            RECALL HEAVENS GRAZHIR: the shards you have learned
    ;astral return          (typed while it runs) nothing early: a trip, or a round, always finishes
    ;stop astral            quit at once — inside the plane that leaves you there; finish by hand

What it does
  - PREPAREs Moongate, FOCUSes the shard here, HARNESSes the mana, CASTs into the plane.
  - Follows PERCEIVE to the centre of the microcosm, walks the ring of pillars to the
    destination's, FOCUSes the destination to enter its conduit, follows PERCEIVE to its end.
  - PREPAREs, FOCUSes and CASTs Moongate out at the destination shard, then RELEASEs the mana.
  - Harnesses again whenever the plane says you only carefully or struggling maintain your place.

What stops it: no shard in the room, a shard you have not learned, the Grey Expanse,
an answer it does not know, or too many rooms without arriving.

The model and its wordings are client/game/astral.py's (Elanthipedia: Astral Travel).
"""

from client.game import astral, probe, travel
from client.game.act import ask, said

_NOTES = """
Built from the first trip by hand, 2026-10-10: Vellano to Besoge in four
minutes, a circle-200 Moon Mage holding 100 harnessed mana and never
leaving "effortlessly". Entry is Moongate, not Teleport: the wiki
prefers it because the harnessed mana is kept going in. The pillars
are a ring joined east-west (Unity -> west -> Secrets, captured), with
Convergence up and the Broken Pillar down; the 2008 StormFront script
on the wiki walks a layout the plane no longer has.

The trip trains: Astrology 0 -> 30/34 and Attunement 0 -> 28/34 in those
four minutes, nothing else moving — so `round` exists for ;train, which
starts the task wherever the character stands (hence `from=`) and types
the return word at its target. A kill in the plane strands the mage,
so the return word ends nothing early and the task's return_grace must
outlast a round (ten minutes is safe at those ranks).
"""

HARNESS = 100  # mana harnessed going in, and again when the plane presses
PREPARE_SECONDS = 30  # the Moongate's preparation, after FOCUS's 20 s
MAX_ROOMS = 40  # rooms followed toward the centre or a conduit's end


def parse_args(args):
    options = {"shard": "", "harness": HARNESS, "round": False, "from": ""}
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key == "harness" and value.isdigit():
            options["harness"] = int(value)
        elif sep and key == "from" and value:
            options["from"] = value
        elif key == "round":
            options["round"] = True
        elif not sep and key != "return":
            options["shard"] = key
    return options


def title(s):
    return str(getattr(s.state, "room_title", "") or "")


def moongate(s, shard, mana):
    """PREPARE Moongate, FOCUS `shard`, HARNESS, CAST: True once the cast
    has moved the character (into the plane or out of it)."""
    before = title(s)
    s.waitrt()
    heard = ask(s, "prepare moongate")
    focus = ask(s, f"focus {shard}")
    heard += focus
    if astral.UNKNOWN_SHARD in focus.lower():
        s.echo(f"astral: you have not learned {shard} — ;astral list")
        return False
    if astral.CONNECTED not in focus:
        s.echo(f"astral: FOCUS {shard} answered {said(focus)!r} — stopping")
        return False
    s.waitrt()
    heard += ask(s, f"harness {mana}")
    if astral.PREPARED not in heard:
        probe.collect(s, PREPARE_SECONDS, until=astral.PREPARED)
    s.waitrt()
    ask(s, f"cast {shard}")
    if title(s) == before:
        s.echo(f"astral: the Moongate through {shard} did not take you — stopping")
        return False
    return True


def pressed(s, answer, mana):
    """React to the plane's verdict in an answer; False when lost."""
    if astral.lost(answer):
        s.echo("astral: in the Grey Expanse — nothing a script can do; ;stop astral")
        return False
    verdict = astral.standing(answer)
    if verdict in ("careful", "struggling"):
        s.echo(f"astral: the plane presses ({verdict}) — harnessing {mana} more")
        s.waitrt()
        ask(s, f"harness {mana}")
    return True


def follow(s, goal, mana):
    """PERCEIVE and step until at a pillar (goal "centre") or at the
    conduit's end (goal "end"): True on arrival."""
    for _ in range(MAX_ROOMS):
        if goal == "centre" and astral.pillar_of(title(s)):
            return True
        s.waitrt()
        answer = ask(s, "perceive")
        if not pressed(s, answer, mana):
            return False
        centre, end = astral.perceived(answer)
        if goal == "end" and end == "here":
            return True
        way = centre if goal == "centre" else end
        if way is None or way == "here":
            s.echo(f"astral: PERCEIVE said no way to the {goal}: {said(answer)!r}")
            return False
        s.waitrt()
        if not pressed(s, ask(s, way), mana):
            return False
    s.echo(f"astral: {MAX_ROOMS} rooms without reaching the {goal} — stopping")
    return False


def run(s, options, go=None):
    """`go(s, target)` walks to a ;go2 target (travel.go in the script,
    a fake in tests)."""
    dest = options["shard"]
    mana = options["harness"]
    if dest == "list":
        s.echo(said(ask(s, "recall heavens grazhir")))
        return "list"
    if dest not in astral.SHARDS:
        s.echo(f"astral: which shard? one of {', '.join(sorted(astral.SHARDS))}")
        return "no shard"
    if options["from"] and not (go or travel.go)(s, options["from"]):
        s.echo(f"astral: could not reach {options['from']} — stopping")
        return "walk"
    start = astral.shard_here(getattr(s.state, "room_objs", ""))
    if start is None:
        s.echo(
            "astral: no Grazhir shard here — stand at one (;astral list names yours)"
        )
        return "no start"
    if start == dest:
        s.echo(f"astral: you are at {dest} already")
        return "here"
    outcome = trip(s, start, dest, mana)
    if outcome != "arrived" or not options["round"]:
        return outcome
    outcome = trip(s, dest, start, mana)
    return "round" if outcome == "arrived" else outcome


def trip(s, start, dest, mana):
    """One crossing, `start`'s shard (stood at) to `dest`'s: "arrived",
    or why not."""
    pillar, town = astral.SHARDS[dest]
    s.echo(f"astral: {start} to {dest} ({town}) by the Pillar of {pillar}")
    if not moongate(s, start, mana):
        return "entry"
    if not follow(s, "centre", mana):
        return "lost"
    for move in astral.ring_moves(astral.pillar_of(title(s)), pillar):
        s.waitrt()
        ask(s, move)
    if astral.pillar_of(title(s)) != pillar:
        s.echo(f"astral: expected the Pillar of {pillar}, in {title(s)} — stopping")
        return "lost"
    s.waitrt()
    focus = ask(s, f"focus {dest}")
    if astral.CONDUIT_FOUND not in focus:
        s.echo(
            f"astral: FOCUS {dest} at the pillar answered {said(focus)!r} — stopping"
        )
        return "lost"
    if not follow(s, "end", mana):
        return "lost"
    if not moongate(s, dest, mana):
        return "exit"
    ask(s, "release mana")
    s.echo(f"astral: arrived at {dest} — {title(s)}")
    return "arrived"


def main(s):
    run(s, parse_args(s.args or []))
