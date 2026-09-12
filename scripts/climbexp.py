"""Measure a climb: attempt an obstacle, log every try with its context:  ;climbexp <obstacle>

    ;climbexp felled tree                     attempt it here until it goes, logging each try
    ;climbexp felled tree train=agility       first walk to the Agility trainer, TRAIN one
                                              point, walk back, then attempt
    ;climbexp felled tree before=3 cap=20     3 attempts before the train, at most 20 after
    ;climbexp show [tag]                      print the logged rows (the last experiment)

An experiment in the sense of docs/movement.md's felled tree: what
does it take for this character to make this climb? Each attempt is
one row in history.db's `climbs` table (client/game/climblog.py,
#159): the outcome (up, footing, vertigo, posture, other) with the
game's wording and the line naming what hindered, Athletics rank and
mindstate, the stats INFO gives, encumbrance, health, and APPRAISE's
read of the obstacle — the factors Elanthipedia's Athletics page
names (Athletics ranks, Agility and Strength, encumbrance, armor,
injuries). The load is left as it is between attempts, so the rows
compare; stow or remove things yourself before starting to test
another load.

Attempts stop at the first success (the far side of the obstacle is
where you end up), at `cap` (default 20), or for safety: dead,
hostiles, bleeding (;tend first), or health under `floor` (default
70%). A fall's roundtime is waited out and STAND precedes every try.

train=<stat> spends TDPs — one point, in the stat's training room,
which the map tags (Crossing's Academy of Agility, 38 steps from the
tree): TRAIN, then TRAIN again to confirm, per Elanthipedia's Time
Development Points page; an answer the script cannot classify stops
it before the confirming TRAIN, with the lines echoed. INFO before and
after records the stat and the TDPs. Stop with:  ;stop climbexp
"""

import re
from time import monotonic

from client.game import probe
from client.game.climblog import (
    hindering_line,
    open_history,
    record,
    refusal_kind,
    rows,
    summarize,
)
from client.game.history import database_path
from client.game.tdp import STATS, TRAIN_OUTCOMES
from client.game.walker import locate, walk

CAP = 20  # attempts after the train, a fuse
HEALTH_FLOOR = 70  # % — below it the experiment ends
ARRIVAL_TIMEOUT = 15  # seconds for the compass frame after a climb
BETWEEN = 2  # seconds between attempts, past the roundtime
COLLECT_SECONDS = 3  # a command's answer, opening window
TAIL_SECONDS = 1.5  # ... and the tail past its roundtime
_STAT = re.compile(rf"({'|'.join(STATS)})\s*:\s*(\d+)")
_TDPS = re.compile(r"TDPs\s*:\s*(\d+)")
_ENC = re.compile(r"Encumbrance\s*:\s*(.+)")


def parse_args(args):
    """The obstacle words and the key=value options."""
    options = {"train": "", "cap": CAP, "before": 0, "floor": HEALTH_FLOOR, "tag": ""}
    words = []
    for arg in args:
        key, sep, value = arg.partition("=")
        if sep and key in options:
            options[key] = int(value) if isinstance(options[key], int) else value
        else:
            words.append(arg)
    return " ".join(words), options


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def athletics(state):
    entry = (getattr(state, "experience", None) or {}).get("Athletics") or {}
    return entry.get("rank"), entry.get("mindstate")


def health(state):
    return (getattr(state, "vitals", None) or {}).get("health")


def indicator(state, name):
    return (getattr(state, "indicator", None) or {}).get(name) == "y"


def context(s, obstacle):
    """INFO, ENC, APPRAISE: the factors behind an attempt, read once
    per phase (they change only when the character does)."""
    info = ask(s, "info")
    stats = {name: int(value) for name, value in _STAT.findall(info)}
    tdps = _TDPS.search(info)
    enc = _ENC.search(ask(s, "encumbrance"))
    appraise = ask(s, f"appraise {obstacle}").strip()
    return {
        "agility": stats.get("Agility"),
        "strength": stats.get("Strength"),
        "stats": stats,
        "tdps": int(tdps.group(1)) if tdps else None,
        "encumbrance": enc.group(1).strip() if enc else None,
        "appraise": appraise.splitlines()[0] if appraise else "",
    }


def unsafe(s, floor):
    """Why the experiment must stop now, or None."""
    if s.dead:
        return "dead"
    if getattr(s.state, "hostiles", None):
        return "hostiles here"
    if indicator(s.state, "IconBLEEDING"):
        return "bleeding — ;tend first"
    current = health(s.state)
    if current is not None and current < floor:
        return f"health {current}% under the {floor}% floor"
    return None


def attempt(s, obstacle):
    """STAND, climb, and read what happened: ("up" | a refusal kind |
    "stalled", the story text)."""
    s.waitrt()
    s.put("stand")
    s.waitrt()
    while s.get(timeout=0, streams=("compass",)) is not None:
        pass
    s.put(f"climb {obstacle}")
    deadline = monotonic() + ARRIVAL_TIMEOUT
    story = []
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        item = s.get(timeout=remaining, streams=None)
        if item is None:
            break
        stream, text = item
        if stream == "compass":
            return "up", "".join(story)
        if stream:
            continue
        story.append(text)
        kind = refusal_kind(text)
        if kind:
            return kind, "".join(story)
    return "stalled", "".join(story)


def log_attempt(s, db, experiment, phase, number, obstacle, outcome, text, facts):
    rank, mindstate = athletics(s.state)
    record(
        db,
        character_name=getattr(s.state, "name", None) or "unknown",
        experiment=experiment,
        phase=phase,
        attempt=number,
        room=facts.get("room"),
        obstacle=obstacle,
        outcome=outcome,
        wording=text.strip(),
        hindering=hindering_line(text),
        athletics_rank=rank,
        athletics_mindstate=mindstate,
        agility=facts.get("agility"),
        strength=facts.get("strength"),
        tdps=facts.get("tdps"),
        encumbrance=facts.get("encumbrance"),
        health=health(s.state),
        appraise=facts.get("appraise"),
        stats=facts.get("stats"),
        # What the hands held at the attempt, from the parser's hand
        # state (#159): the item nouns, or None for an empty hand.
        left_hand=(getattr(s.state, "left_hand", None) or {}).get("name"),
        right_hand=(getattr(s.state, "right_hand", None) or {}).get("name"),
    )
    load = hindering_line(text)
    s.echo(
        f"climbexp: {phase} #{number} {outcome} — Ath {rank} Agi "
        f"{facts.get('agility')} enc {facts.get('encumbrance')} hp {health(s.state)}"
        + (f" [{load}]" if load else "")
    )


def attempts(s, db, experiment, phase, obstacle, facts, cap, floor):
    """Up to cap tries; "up" on success, else why it stopped."""
    for number in range(1, cap + 1):
        reason = unsafe(s, floor)
        if reason:
            s.echo(f"climbexp: stopping — {reason}")
            return reason
        outcome, text = attempt(s, obstacle)
        s.waitrt()
        log_attempt(s, db, experiment, phase, number, obstacle, outcome, text, facts)
        if outcome == "up":
            return "up"
        s.sleep(BETWEEN)
    return "cap"


def train(s, db, experiment, stat, obstacle, facts, mapdb, walk_fn):
    """Walk to the stat's training room (the map tags it), TRAIN twice,
    INFO to see it took. False when the experiment cannot go on."""
    rooms = mapdb.rooms_tagged(stat)
    if not rooms:
        s.echo(f"climbexp: the map has no room tagged {stat!r}")
        return False
    if not walk_fn(s, mapdb, set(rooms), describe=f"the {stat} trainer"):
        s.echo("climbexp: could not reach the trainer — stopping")
        return False
    first = ask(s, "train")
    outcome = probe.classify(first, TRAIN_OUTCOMES)
    second = ""
    if outcome == "confirm":
        second = ask(s, "train")
        outcome = probe.classify(second, TRAIN_OUTCOMES)
    if outcome != "done":
        for line in (first + "\n" + second).splitlines():
            if line.strip():
                s.echo(f"climbexp: TRAIN answered: {line.strip()}")
        s.echo(
            "climbexp: no point was trained — stopping before it spends anything blind"
        )
        record(
            db,
            character_name=getattr(s.state, "name", None) or "unknown",
            experiment=experiment,
            phase="train",
            attempt=0,
            obstacle=obstacle,
            outcome="refused" if outcome == "refused" else "unrecognized",
            wording=(first + "\n" + second).strip(),
            **{k: facts.get(k) for k in ("agility", "strength", "tdps", "encumbrance")},
        )
        return False
    after = context(s, obstacle)
    before_value = (facts.get("stats") or {}).get(stat.capitalize())
    after_value = (after.get("stats") or {}).get(stat.capitalize())
    s.echo(
        f"climbexp: trained {stat} — {before_value} → {after_value}, "
        f"TDPs {facts.get('tdps')} → {after.get('tdps')}"
    )
    record(
        db,
        character_name=getattr(s.state, "name", None) or "unknown",
        experiment=experiment,
        phase="train",
        attempt=0,
        obstacle=obstacle,
        outcome="done",
        wording=(first + "\n" + second).strip(),
        agility=after.get("agility"),
        strength=after.get("strength"),
        tdps=after.get("tdps"),
        encumbrance=after.get("encumbrance"),
        stats=after.get("stats"),
    )
    facts.update(after)
    return True


def run(s, obstacle, options, db, mapdb=None, walk_fn=walk):
    experiment = options["tag"] or f"{obstacle}-{monotonic():.0f}"
    start = locate(mapdb, s.state) if mapdb is not None else None
    facts = context(s, obstacle)
    facts["room"] = start
    s.echo(
        f"climbexp: {obstacle!r} at room {start} — Ath {athletics(s.state)[0]}, "
        f"Agi {facts['agility']}, Str {facts['strength']}, enc {facts['encumbrance']}, "
        f"appraise: {facts['appraise'] or '(nothing)'}"
    )
    if options["before"]:
        result = attempts(
            s,
            db,
            experiment,
            "before",
            obstacle,
            facts,
            options["before"],
            options["floor"],
        )
        if result == "up":
            s.echo("climbexp: it went before any training — experiment over")
            return
        if result != "cap":
            return
    if options["train"]:
        if mapdb is None:
            s.echo("climbexp: training needs the map — none loaded")
            return
        if not train(
            s, db, experiment, options["train"], obstacle, facts, mapdb, walk_fn
        ):
            return
        if start is not None and not walk_fn(
            s, mapdb, {start}, describe="the obstacle"
        ):
            s.echo("climbexp: could not walk back to the obstacle — stopping")
            return
    result = attempts(
        s, db, experiment, "after", obstacle, facts, options["cap"], options["floor"]
    )
    if result == "up":
        s.echo(
            f"climbexp: up — experiment {experiment!r} done, ;climbexp show {experiment}"
        )
    elif result == "cap":
        s.echo(
            f"climbexp: {options['cap']} attempts without success — ;climbexp show {experiment}"
        )


def show(s, db, tag):
    entries = rows(db, experiment=tag or None)
    if not tag and entries:
        last = entries[-1]["experiment"]
        entries = [e for e in entries if e["experiment"] == last]
    if not entries:
        s.echo("climbexp: nothing logged yet")
        return
    s.echo(f"climbexp: {entries[0]['experiment']} — {len(entries)} row(s)")
    for line in summarize(entries):
        s.echo(f"  {line}")


def main(s):
    db = open_history(database_path())
    try:
        if s.args and s.args[0] == "show":
            show(s, db, " ".join(s.args[1:]))
            return
        obstacle, options = parse_args(s.args)
        if not obstacle:
            s.echo(
                "usage: ;climbexp <obstacle> [train=agility] [before=N] [cap=N] [floor=N]"
            )
            return
        from client.game.mapdb import MapDB, mapdb_path

        mapdb = MapDB.load() if mapdb_path().is_file() else None
        run(s, obstacle, options, db, mapdb=mapdb)
    finally:
        db.close()
