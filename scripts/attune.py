"""Train Attunement by perceiving mana, room after room:  ;attune

    ;attune              loop a chain of nearby streets, POWER in each, until mind-lock
    ;attune rooms=4      a shorter loop (default 8 rooms out and back)
    ;attune until=30     stop at that mindstate instead of 34
    ;attune from=1420    walk to that ;go2 target first (the profile's attune_start otherwise)
    ;attune here         perceive in place, once a minute (a Moon Mage's way)
    ;attune once         exit at mind-lock instead of holding for the drain
    ;attune return       (typed while it runs) finish the current perceive and end

What it does:
- A room pays Attunement once a minute, so it walks a chain of plain
  compass streets out and back, POWERs on every arrival, and waits
  out a room that paid within the minute.
- A Moon Mage's POWER reads the moons: the run says so once and
  switches to PERCEIVE MANA in place, once a minute.
- At mind-lock it holds until the pool drains, then resumes
  (client/game/trainer.py, the loop every trainer runs); ;train runs
  it as a task and ends it at the plan's target.

What stops it: death, hostiles in the room, eight perceives in a row
without gain, no street to loop, a failed walk.
Stop with:  ;stop attune (at once), or ;attune return for a clean finish.
"""

import time

from client.game import act, probe, trainer, travel
from client.game.loop import ensure_mindstate, mindstate, pause
from client.game.attune import (
    LUNAR_PERCEIVE,
    PERCEIVED,
    chain,
    circuit,
    reads_moons,
    wait_for,
)
from client.game.mapdb import MapDB
from client.game.walker import locate, walk

_NOTES = """
Perceiving mana trains Attunement once per room per sixty seconds
(Elanthipedia: Attunement skill, Perceive command). The start room is
the profile's `attune_start` (a ;go2 target) or the run's `from=`, so
a hunting ground or a shop with no street is no reason to give up.
Captured 2026-09-12 on a circle-1 Paladin: "You reach out with your
weak senses and see glowing streams of golden Holy mana radiating
through the area.", 8-9 s of roundtime, the mindstate 4/34 -> 6/34 on
a room's first POWER. A Moon Mage's POWER answered with the moons and
taught nothing; PERCEIVE MANA taught, about a minute apart (#384,
2026-09-28; client/game/attune.py has the wordings). ;train's stop
word lands within a second, held or walking.
"""

MIND_LOCK = 34
SKILL = "Attunement"
ROOMS = 8  # rooms beyond the start in the loop: a room pays once a minute,
# and four out and back came round in ~35 s, so the loop waited out the
# rest each lap (2026-09-13); eight puts every revisit past the minute
STALE_LIMIT = 8  # perceives in a row without gain before giving up
COLLECT_SECONDS = 2  # the perceive line lands before its roundtime
TAIL_SECONDS = 0.5
clock = time.monotonic  # tests replace it


def parse_args(args):
    options = {
        "rooms": ROOMS,
        "until": MIND_LOCK,
        "here": False,
        "once": False,
        "from": "",
    }
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key in ("rooms", "until") and value.isdigit():
            options[key] = int(value)
        elif sep and key == "from" and value:
            options["from"] = value
        elif key in ("here", "once"):
            options[key] = True
    return options


def start_room(s):
    """The profile's attune_start, a ;go2 target, or "" for the
    character without a profile or a name."""
    name = getattr(s.state, "name", None)
    if not name:
        return ""
    from client.game.profile import load_profile

    return str(load_profile(name).get("attune_start") or "").strip()


def perceive(s, command="power"):
    """POWER (or a Moon Mage's PERCEIVE MANA), its roundtime waited
    out; the game's answer."""
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS) or ""


def run(s, options, mapdb=None, walk_fn=walk, avoid=()):
    """The setup — the start room, the street chain — then the trainer
    loop with one step: the next room of the circuit, a POWER there."""
    # Asked before any walk: a guild without the skill is told so where
    # it stands (the loop's own check finds the window seeded then).
    if ensure_mindstate(s, SKILL, act.ask) is None:
        s.echo(
            "attune: EXP shows no Attunement — a guild without magic cannot train it"
        )
        return
    here = options["here"]
    rooms = [None]
    if not here:
        if mapdb is None:
            s.echo(
                "attune: power walking needs the map — none loaded; ;attune here perceives in place"
            )
            return
        target = options["from"] or start_room(s)
        if target:
            if not travel.go(
                s,
                target,
                f"start room {target!r}",
                db=mapdb,
                walk=walk_fn,
                avoid=avoid,
            ):
                s.echo("attune: could not reach the start room — stopping")
                return
        start = locate(mapdb, s.state)
        if start is None:
            s.echo("attune: current room unknown — 'look' once and retry")
            return
        rooms = chain(mapdb, start, options["rooms"], avoid=avoid)
        if len(rooms) < 2:
            s.echo(
                "attune: no street to loop from here — try elsewhere, or ;attune here"
            )
            return
        titles = [(mapdb.rooms[r].get("title") or ["?"])[0] for r in rooms]
        s.echo(
            f"attune: looping {len(rooms) - 1} rooms out and back: {' → '.join(titles)}"
        )
    order = circuit(rooms)
    command = "power"
    last_seen, stale, count, position = {}, 0, 0, 0

    def step(s):
        nonlocal command, here, order, position, stale, count
        room = order[position % len(order)]
        if not here and room != locate(mapdb, s.state):
            if not travel.go(
                s, room, "the next room", db=mapdb, walk=walk_fn, avoid=avoid
            ):
                return "the walk failed"
        wait = wait_for(room, last_seen, clock())
        if wait and not pause(s, wait):
            return None  # the loop says why
        before = mindstate(s, SKILL)
        answer = perceive(s, command)
        if PERCEIVED not in answer:
            if command == "power" and reads_moons(answer):
                s.echo(
                    "attune: POWER reads the moons (a Moon Mage) — "
                    "PERCEIVE MANA in place from here, once a minute"
                )
                command, here, order, position = LUNAR_PERCEIVE, True, [None], 0
                return None
            return f"{command.upper()} gave no perceive line"
        last_seen[room] = clock()
        count += 1
        after = mindstate(s, SKILL)
        if after is not None and before is not None and after > before:
            stale = 0
        else:
            stale += 1
        if stale >= STALE_LIMIT and (after or 0) < options["until"]:
            return f"{STALE_LIMIT} perceives without gain"
        if count % 5 == 0:
            s.echo(f"attune: Attunement {after}/34 after {count} perceives")
        position += 1
        return None

    return trainer.train(
        s,
        "attune",
        SKILL,
        step,
        until=options["until"],
        once=options["once"],
        again="walking again",
    )


def main(s):
    options = parse_args(s.args or [])
    mapdb = None if options["here"] else MapDB.load()
    avoid = travel.avoided(mapdb) if mapdb else ()
    run(s, options, mapdb=mapdb, avoid=avoid)
