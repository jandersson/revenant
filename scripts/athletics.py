"""Walk to the best Athletics spot for your rank and train there:  ;athletics

With no arguments the script reads your rank (asking the game with EXP
ATHLETICS when the exp window is empty), walks to the hardest ladder
rung in reach — the community map knows the rooms — and climbs its
loop, pausing at mind-lock and moving up the ladder when gains go
stale. The ladder is Zoluren spots per Elanthipedia's climbing and
swimming list. Also:

    ;athletics list                     show the ladder for your rank
    ;athletics climb x | climb back     train a manual loop right here

Progress is echoed every ten laps; pair with ;xp for history. The mine
ladder rung is near beisswurms — mind your health there. Stop with:
;stop athletics
"""

import re

MIND_LOCK = 34  # mindstate 34/34: nothing more fits
RESUME_BELOW = 28  # resume once enough has drained to be worth the laps
LOCK_POLL = 30  # seconds between mindstate checks while locked
PAUSE = 1  # breather between commands
LAPS_PER_REPORT = 10
STALE_MINDSTATE = 12  # reports at or below this look like a too-easy spot
STALE_REPORTS = 3  # ... after this many in a row without improvement

# The Zoluren rank ladder the script can walk to: (from_rank, to_rank or
# None, label, bottom room id, top room id). Ordered easiest to hardest;
# the loop commands are read from the map's own climb edges at runtime.
AUTO_LADDER = [
    (0, 19, "felled tree, Wilderness Deep Forest (west of Crossing)", 5705, 6153),
    (0, 34, "moonstone trellis, Jadewater Mansion East Lawn", 13527, 13529),
    (5, 60, "oak tree, Arthe Dale Greensward", 1068, 14134),
    (10, None, "apple tree, Midton Circle", 19349, 7214),
    (20, None, "rise, Siergelde Cliffs High Path", 1429, 1430),
    (30, None, "mine ladder, Abandoned Mine crevice (beisswurms!)", 7233, 7234),
]

# Practice-only spots the map has no climb edge for — advice, not travel.
PRACTICE_SPOTS = [
    (0, 80, "pear tree in the grassland west of Crossing — climb practice"),
    (0, 80, "Crossing sewers (mind the thugs) — swim the channels"),
    (0, 110, "Goblin Brook (slows after 80) — swim across and back"),
]


def parse_commands(args):
    """The |-separated movement commands from the ;athletics arguments."""
    commands = [part.strip() for part in " ".join(args).split("|")]
    return [command for command in commands if command]


def skill_entry(state):
    experience = getattr(state, "experience", None) or {}
    return experience.get("Athletics")


def mindstate(state):
    """Athletics mindstate 0-34, or None when the exp window doesn't
    show it (not learning yet, or no parsed state at all)."""
    entry = skill_entry(state)
    return entry["mindstate"] if entry else None


def current_rank(state):
    entry = skill_entry(state)
    return entry["rank"] if entry else None


# "       Athletics:      3 00.00% clear          (0/34)"
EXP_LINE = re.compile(r"Athletics:\s+(\d+)\s+[\d.]+%")


def probe_rank(s):
    """Ask the game for the rank (EXP ATHLETICS) — the fallback when the
    exp window has no Athletics entry because nothing is learning yet."""
    s.put("exp athletics")
    line = s.waitfor(r"Athletics:\s+\d+", timeout=5)
    match = EXP_LINE.search(line) if line else None
    return int(match.group(1)) if match else None


def in_band(rung, rank):
    low, high = rung[0], rung[1]
    return low <= rank and (high is None or rank < high)


def optimal_rung(rank):
    """The hardest walkable rung in reach: greatest entry rank the
    character clears, later ladder entries winning ties. None only when
    the rank somehow exceeds every band (the ladder tops out open)."""
    candidates = [rung for rung in AUTO_LADDER if in_band(rung, rank or 0)]
    if not candidates:
        return None
    best_low = max(rung[0] for rung in candidates)
    return [rung for rung in candidates if rung[0] == best_low][-1]


def next_rung(rung, rank):
    """The next ladder entry above a rung that the rank can attempt."""
    index = AUTO_LADDER.index(rung)
    for candidate in AUTO_LADDER[index + 1 :]:
        if in_band(candidate, rank or 0):
            return candidate
    return None


def climb_loop(db, bottom, top):
    """The up/down commands for a rung, read from the map's own edges;
    None when the community map no longer has them."""
    up = (db.rooms.get(bottom, {}).get("wayto") or {}).get(str(top))
    down = (db.rooms.get(top, {}).get("wayto") or {}).get(str(bottom))
    if isinstance(up, str) and isinstance(down, str):
        return [up, down]
    return None


def recommendations(rank):
    """Ladder advice lines for a rank: the rungs in reach now, plus the
    next one coming up. An unknown rank gets the starting rungs."""
    ladder = [rung[:3] for rung in AUTO_LADDER] + PRACTICE_SPOTS
    ladder.sort(key=lambda rung: (rung[0], rung[1] is None, rung[1] or 0))
    if rank is None:
        lines = ["Athletics rank unknown — starting rungs of the ladder:"]
        current = [rung for rung in ladder if rung[0] == 0]
        upcoming = []
    else:
        lines = [f"ladder rungs for rank {rank}:"]
        current = [rung for rung in ladder if in_band(rung, rank)]
        upcoming = [rung for rung in ladder if rung[0] > rank]
    for low, high, where in current:
        band = f"{low}+" if high is None else f"{low}-{high}"
        lines.append(f"  [{band}] {where}")
    if upcoming:
        low, _, where = upcoming[0]
        lines.append(f"  next up at rank {low}: {where}")
    return lines


def going_stale(report_mindstates):
    """True when the last few lap reports all sat at a low mindstate
    without improving — the signature of a spot outgrown."""
    if len(report_mindstates) < STALE_REPORTS:
        return False
    recent = [m for m in report_mindstates[-STALE_REPORTS:] if m is not None]
    if len(recent) < STALE_REPORTS:
        return False
    return max(recent) <= STALE_MINDSTATE and recent[-1] <= recent[0]


def train(s, commands, stop_when_stale=False):
    """Cycle the movement commands, pausing at mind-lock. Runs forever
    in manual mode (echoing ladder advice when gains stall); with
    stop_when_stale, returns "stale" so auto mode can advance."""
    laps = 0
    reports = []
    while True:
        current = mindstate(s.state)
        if current is not None and current >= MIND_LOCK:
            s.echo(
                f"Athletics is mind-locked — pausing until it drains "
                f"below {RESUME_BELOW}/34"
            )
            while current is not None and current > RESUME_BELOW:
                s.sleep(LOCK_POLL)
                current = mindstate(s.state)
            s.echo("resuming")
            reports.clear()  # a lock is the opposite of stale
        for command in commands:
            s.put(command)
            s.waitrt()
            s.sleep(PAUSE)
        laps += 1
        if laps % LAPS_PER_REPORT == 0:
            current = mindstate(s.state)
            shown = f"{current}/34" if current is not None else "not learning yet"
            s.echo(f"{laps} laps — Athletics mindstate {shown}")
            reports.append(current)
            if going_stale(reports):
                if stop_when_stale:
                    return "stale"
                s.echo("gains look stale here — this spot may be outgrown:")
                for line in recommendations(current_rank(s.state)):
                    s.echo(line)
                reports.clear()


def auto_train(s, db=None, walk=None):
    """The no-arguments mode: walk to the optimal rung and climb it,
    moving up the ladder when a rung goes stale."""
    if db is None or walk is None:
        from client.mapdb import MapDB, download, mapdb_path
        from client.walker import walk as real_walk

        if not mapdb_path().is_file():
            s.echo("downloading map database (first use, ~13MB) ...")
            download()
        db = db or MapDB.load()
        walk = walk or real_walk

    rank = current_rank(s.state)
    if rank is None:
        rank = probe_rank(s)
    rung = optimal_rung(rank)
    if rung is None:
        s.echo(f"no ladder rung fits rank {rank} — train manually (;help athletics)")
        return
    while True:
        low, high, label, bottom, top = rung
        band = f"{low}+" if high is None else f"{low}-{high}"
        s.echo(f"rank {rank}: heading to [{band}] {label}")
        commands = climb_loop(db, bottom, top)
        if commands is None:
            s.echo(f"the map lost the climb edge for {label} — try ;go2 update")
            return
        if not walk(s, db, [bottom], describe=label):
            s.echo(
                "could not reach the spot — stopping (;go2 there and use manual mode?)"
            )
            return
        s.echo(f"training: {' | '.join(commands)}")
        train(s, commands, stop_when_stale=True)
        rank = current_rank(s.state) or rank
        advanced = next_rung(rung, rank)
        if advanced is None:
            s.echo("gains are stale but no harder rung is in reach yet — carrying on")
            train(s, commands, stop_when_stale=False)
            return
        s.echo("this rung is outgrown — moving up the ladder")
        rung = advanced


def main(s):
    if s.args and s.args[0] == "list":
        rank = current_rank(s.state)
        if rank is None:
            rank = probe_rank(s)
        for line in recommendations(rank):
            s.echo(line)
        return
    commands = parse_commands(s.args)
    if commands:
        train(s, commands)
        return
    auto_train(s)
