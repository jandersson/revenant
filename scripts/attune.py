"""Train Attunement by power walking — perceive mana room after room:  ;attune

    ;attune              loop a chain of nearby streets, POWER in each, until mind-lock
    ;attune rooms=3      a shorter loop (default 4 rooms out and back)
    ;attune until=30     stop at that mindstate instead of 34
    ;attune here         perceive in place, once a minute (Moon Mages: lunar mana is everywhere)
    ;attune once         exit at mind-lock instead of holding for the drain
    ;attune return       (typed while it runs) finish the current perceive and end

Perceiving mana trains Attunement once per room per sixty seconds
(Elanthipedia: Attunement skill, Perceive command), so the script
builds a chain of rooms from where you stand — plain compass moves
in both directions, streets rather than shop doors — and walks it out
and back, POWERing on every arrival and waiting out any room that
paid within the minute. Captured 2026-09-12 on a circle-1 Paladin:
"You reach out with your weak senses and see glowing streams of
golden Holy mana radiating through the area.", 8-9 s of roundtime,
and the mindstate rising 4/34 → 6/34 on a room's first POWER. At
mind-lock it holds, polling until enough has drained to be worth the
walking, then resumes — a standalone run is a standing trainer, like
;athletics; `once` exits at the lock instead. ;train runs it as a
task (skills: ["Attunement"], return_word "return") and ends it
itself when the skill reaches the plan's target: the word lands within
a second, held or walking. It stops on death, on hostiles in the
room, when eight perceives in a row gain nothing (a guild that cannot
sense mana), and when the map has no street to loop.
Stop with:  ;stop attune (at once), or ;attune return for a clean finish.
"""

import re
import time

from client.game import probe
from client.game.attune import PERCEIVED, chain, circuit, wait_for
from client.game.mapdb import MapDB
from client.game.walker import avoided_rooms, locate, walk
from client.settings import load_settings

MIND_LOCK = 34
RESUME_BELOW = 28  # resume once enough has drained to be worth the laps
LOCK_POLL = 30  # seconds between mindstate checks while locked
ROOMS = 4  # rooms beyond the start in the loop
STALE_LIMIT = 8  # perceives in a row without gain before giving up
COLLECT_SECONDS = 2  # the perceive line lands before its roundtime
TAIL_SECONDS = 0.5
clock = time.monotonic  # tests replace it


def parse_args(args):
    options = {"rooms": ROOMS, "until": MIND_LOCK, "here": False, "once": False}
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key in ("rooms", "until") and value.isdigit():
            options[key] = int(value)
        elif key in ("here", "once"):
            options[key] = True
    return options


def mindstate(s):
    entry = (getattr(s.state, "experience", None) or {}).get("Attunement")
    return entry["mindstate"] if entry else None


# EXP ATTUNEMENT answers in the story — "Attunement:     18 97.08% clear
# (0/34)" (captured 2026-09-13) — while the exp window lists a skill
# only while it has experience in it, so a clear pool is absent from
# the window and read as "no such skill" until this line is parsed.
_EXP_ANSWER = re.compile(r"Attunement:\s+\d+\s+[\d.]+%\s+.*?\((\d+)/34\)")


def ensure_mindstate(s):
    """The mindstate: the exp window's, or EXP ATTUNEMENT's own answer
    when the window does not list the skill (a clear pool is 0/34, a
    guild without the skill gets no such line)."""
    value = mindstate(s)
    if value is None:
        answer = probe.ask(s, "exp attunement", COLLECT_SECONDS, TAIL_SECONDS)
        value = mindstate(s)
        if value is None:
            match = _EXP_ANSWER.search(answer or "")
            if match:
                value = int(match.group(1))
    return value


def danger(s):
    if s.dead:
        return "you are dead"
    if getattr(s.state, "hostiles", None):
        return "hostiles in the room"
    return None


def wants_stop(s):
    """True once "return" was typed at the script: finish the perceive
    in hand and end. (;stop <name> is the abrupt end for every script;
    a typed word is the graceful one, the operator's rule 2026-09-12.)"""
    while (line := s.command(timeout=0)) is not None:
        if "return" in line.lower():
            return True
    return False


def perceive(s):
    """POWER, its roundtime waited out; True when the game answered
    with a perceive line."""
    answer = probe.ask(s, "power", COLLECT_SECONDS, TAIL_SECONDS)
    return PERCEIVED in answer


def pause(s, seconds):
    """Sleep in one-second slices so a typed stop or danger is noticed
    at once; False when either arrived."""
    end = clock() + seconds
    while (left := end - clock()) > 0:
        s.sleep(min(1, left))
        if wants_stop(s) or danger(s):
            return False
    return True


def hold_at_lock(s, until):
    """Wait at mind-lock until the mindstate drains below RESUME_BELOW
    (or the target, when lower); False when the wait is interrupted."""
    s.echo(f"attune: Attunement mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        value = mindstate(s)
        if value is not None and value <= floor:
            s.echo(f"attune: drained to {value}/34 — walking again")
            return True


def run(s, options, mapdb=None, walk_fn=walk, avoid=()):
    value = ensure_mindstate(s)
    if value is None:
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
    last_seen, stale, count, position = {}, 0, 0, 0
    while True:
        if wants_stop(s):
            s.echo("attune: stopping as asked")
            return
        reason = danger(s)
        if reason:
            s.echo(f"attune: {reason} — stopping")
            return
        value = mindstate(s)
        if value is not None and value >= options["until"]:
            if options["once"]:
                s.echo(f"attune: Attunement at {value}/34 — done")
                return
            if not hold_at_lock(s, options["until"]):
                s.echo("attune: stopping")
                return
            continue
        room = order[position % len(order)]
        if not here and room != locate(mapdb, s.state):
            if not walk_fn(s, mapdb, {room}, describe="the next room"):
                s.echo("attune: the walk failed — stopping")
                return
        wait = wait_for(room, last_seen, clock())
        if wait and not pause(s, wait):
            s.echo("attune: stopping")
            return
        before = mindstate(s)
        if not perceive(s):
            s.echo("attune: POWER gave no perceive line — stopping")
            return
        last_seen[room] = clock()
        count += 1
        after = mindstate(s)
        if after is not None and before is not None and after > before:
            stale = 0
        else:
            stale += 1
        if stale >= STALE_LIMIT and (after or 0) < options["until"]:
            s.echo(f"attune: {STALE_LIMIT} perceives without gain — stopping")
            return
        if count % 5 == 0:
            s.echo(f"attune: Attunement {after}/34 after {count} perceives")
        position += 1


def main(s):
    options = parse_args(s.args or [])
    mapdb = None if options["here"] else MapDB.load()
    avoid = avoided_rooms(mapdb, load_settings().get("avoid_rooms")) if mapdb else ()
    run(s, options, mapdb=mapdb, avoid=avoid)
