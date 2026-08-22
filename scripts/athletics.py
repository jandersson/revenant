"""Walk to the best Athletics spot for your rank and train there:  ;athletics

With no arguments the script reads your rank (asking the game with EXP
ATHLETICS when the exp window is empty), walks to the hardest ladder
rung in reach — the community map knows the rooms — and trains it,
pausing at mind-lock and moving up the ladder when gains go stale.
Standard travel climbs award xp at most once per random 45–60s window
(docs/experience.md), so climb loops are paced to that timer instead
of spammed; `climb practice` rungs are timer-exempt and loop tightly.
The ladder is Zoluren spots per Elanthipedia. Also:

    ;athletics list                     show the ladder for your rank
    ;athletics climb x | climb back     train a manual loop right here

Progress is echoed about every five minutes; pair with ;xp for
history. Danger interrupts training (#72): hostiles in the room mean
break off and climb away until clear, low health means hold until it
recovers, and death stops the script — it never keeps feeding climbs
into an engagement. Stop with:  ;stop athletics
"""

import re

MIND_LOCK = 34  # mindstate 34/34: nothing more fits
RESUME_BELOW = 28  # resume once enough has drained to be worth the laps
LOCK_POLL = 30  # seconds between mindstate checks while locked
PAUSE = 1  # breather between commands (practice + manual loops)
CLIMB_TIMER_PACE = 61  # travel-climb xp awards at most once per random
# 45-60s; landing each climb just past the window makes every climb count
REPORT_EVERY_SECONDS = 300  # progress/staleness cadence, roughly
EST_ROUNDTIME = 4  # rough per-command cost for the cadence estimate
STALE_MINDSTATE = 12  # reports at or below this look like a too-easy spot
STALE_REPORTS = 3  # ... after this many in a row without improvement
HEALTH_FLOOR = 65  # % health: below this, hold training until recovered
ESCAPE_ATTEMPTS = 8  # moves per burst while hostiles hold the room
DANGER_POLL = 5  # seconds between checks while holding
CLEAR_HOLD = 15  # breather after hostiles clear, before resuming

# The Zoluren rank ladder the script can walk to, easiest to hardest.
# Travel-climb rungs carry bottom/top rooms (loop commands are read from
# the map's own edges at runtime, paced to the award timer); practice
# rungs carry the room and the obstacle (timer-exempt, tight loop).
AUTO_LADDER = [
    {
        "low": 0,
        "high": 19,
        "label": "felled tree, Wilderness Deep Forest (west of Crossing)",
        "bottom": 5705,
        "top": 6153,
    },
    {
        "low": 0,
        "high": 34,
        "label": "moonstone trellis, Jadewater Mansion East Lawn",
        "bottom": 13527,
        "top": 13529,
    },
    {
        "low": 0,
        "high": 80,
        "label": "pear tree practice, Grassland Road Meadow (timer-exempt)",
        "room": 1455,
        "practice": "pear tree",
    },
    {
        "low": 5,
        "high": 60,
        "label": "oak tree, Arthe Dale Greensward",
        "bottom": 1068,
        "top": 14134,
    },
    {
        "low": 10,
        "high": None,
        "label": "apple tree, Midton Circle",
        "bottom": 19349,
        "top": 7214,
    },
    {
        "low": 20,
        "high": None,
        "label": "rise, Siergelde Cliffs High Path",
        "bottom": 1429,
        "top": 1430,
    },
    {
        "low": 30,
        "high": None,
        "label": "mine ladder, Abandoned Mine crevice (beisswurms!)",
        "bottom": 7233,
        "top": 7234,
    },
]

# Advice-only spots the script cannot walk a loop for (swims).
PRACTICE_SPOTS = [
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
    return rung["low"] <= rank and (rung["high"] is None or rank < rung["high"])


def optimal_rung(rank):
    """The hardest walkable rung in reach: greatest entry rank the
    character clears, later ladder entries winning ties."""
    candidates = [rung for rung in AUTO_LADDER if in_band(rung, rank or 0)]
    if not candidates:
        return None
    best_low = max(rung["low"] for rung in candidates)
    return [rung for rung in candidates if rung["low"] == best_low][-1]


def next_rung(rung, rank):
    """The next ladder entry above a rung that the rank can attempt."""
    index = AUTO_LADDER.index(rung)
    for candidate in AUTO_LADDER[index + 1 :]:
        if in_band(candidate, rank or 0):
            return candidate
    return None


def climb_loop(db, bottom, top):
    """The up/down commands for a travel rung, read from the map's own
    edges; None when the community map no longer has them."""
    up = (db.rooms.get(bottom, {}).get("wayto") or {}).get(str(top))
    down = (db.rooms.get(top, {}).get("wayto") or {}).get(str(bottom))
    if isinstance(up, str) and isinstance(down, str):
        return [up, down]
    return None


def rung_plan(db, rung):
    """(commands, pace) for a rung. Practice rungs spam their obstacle
    (award-timer-exempt); travel rungs pace each climb past the timer.
    commands is None when the map lost a travel rung's edges."""
    if "practice" in rung:
        return [f"climb practice {rung['practice']}"], PAUSE
    return climb_loop(db, rung["bottom"], rung["top"]), CLIMB_TIMER_PACE


def rung_goal(rung):
    return rung.get("bottom") or rung["room"]


def recommendations(rank):
    """Ladder advice lines for a rank: the rungs in reach now, plus the
    next one coming up. An unknown rank gets the starting rungs."""
    ladder = [(r["low"], r["high"], r["label"]) for r in AUTO_LADDER] + PRACTICE_SPOTS
    ladder.sort(key=lambda rung: (rung[0], rung[1] is None, rung[1] or 0))
    if rank is None:
        lines = ["Athletics rank unknown — starting rungs of the ladder:"]
        current = [rung for rung in ladder if rung[0] == 0]
        upcoming = []
    else:
        lines = [f"ladder rungs for rank {rank}:"]
        current = [
            rung
            for rung in ladder
            if rung[0] <= rank and (rung[1] is None or rank < rung[1])
        ]
        upcoming = [rung for rung in ladder if rung[0] > rank]
    for low, high, where in current:
        band = f"{low}+" if high is None else f"{low}-{high}"
        lines.append(f"  [{band}] {where}")
    if upcoming:
        low, _, where = upcoming[0]
        lines.append(f"  next up at rank {low}: {where}")
    return lines


def hostiles_present(state):
    return bool(getattr(state, "hostiles", None))


def health_percent(state):
    vitals = getattr(state, "vitals", None) or {}
    return vitals.get("health")


def is_dead(state):
    indicators = getattr(state, "indicator", None) or {}
    return indicators.get("IconDEAD") == "y"


def danger(state):
    """Why training must stop right now, or None. Checked before every
    climb — the cougar death (#72) happened because nothing was."""
    if is_dead(state):
        return "dead"
    if hostiles_present(state):
        return "hostiles"
    health = health_percent(state)
    if health is not None and health < HEALTH_FLOOR:
        return "hurt"
    return None


def escape(s, commands):
    """Leave along the training edge, alternating directions. Movement
    auto-retreats and can fail once engaged (captured in #72: eight
    straight failures while two cougars closed), so keep trying; True
    once the room has no hostiles."""
    for attempt in range(ESCAPE_ATTEMPTS):
        s.put(commands[attempt % len(commands)])
        s.waitrt()
        s.sleep(1)
        if not hostiles_present(s.state):
            return True
    return False


def handle_danger(s, reason, commands):
    """React to danger; "stop" when training must end (death), None
    once it has passed."""
    if reason == "dead":
        s.echo("ATHLETICS: you are dead — stopping the trainer")
        return "stop"
    if reason == "hostiles":
        s.echo("ATHLETICS: hostiles here — breaking off to get away!")
        while hostiles_present(s.state):
            if is_dead(s.state):
                s.echo("ATHLETICS: you are dead — stopping the trainer")
                return "stop"
            if not escape(s, commands):
                s.echo(
                    "ATHLETICS: can't get clear — still trying (intervene if you can!)"
                )
        s.echo("clear of hostiles — resuming after a breather")
        s.sleep(CLEAR_HOLD)
        return None
    s.echo(f"ATHLETICS: health below {HEALTH_FLOOR}% — holding until it recovers")
    while True:
        if is_dead(s.state):
            s.echo("ATHLETICS: you are dead — stopping the trainer")
            return "stop"
        if hostiles_present(s.state):
            return None  # the caller re-checks and handles the hostiles
        health = health_percent(s.state)
        if health is None or health >= HEALTH_FLOOR:
            s.echo("health recovered — resuming")
            return None
        s.sleep(DANGER_POLL)


def going_stale(report_mindstates):
    """True when the last few reports all sat at a low mindstate without
    improving — the signature of a spot outgrown."""
    if len(report_mindstates) < STALE_REPORTS:
        return False
    recent = [m for m in report_mindstates[-STALE_REPORTS:] if m is not None]
    if len(recent) < STALE_REPORTS:
        return False
    return max(recent) <= STALE_MINDSTATE and recent[-1] <= recent[0]


def report_cadence(commands, pace):
    """Laps between progress reports, aiming at REPORT_EVERY_SECONDS."""
    lap_seconds = len(commands) * (pace + EST_ROUNDTIME)
    return max(1, round(REPORT_EVERY_SECONDS / lap_seconds))


def train(s, commands, stop_when_stale=False, pace=PAUSE):
    """Cycle the movement commands, pausing at mind-lock. Runs forever
    in manual mode (echoing ladder advice when gains stall); with
    stop_when_stale, returns "stale" so auto mode can advance. pace is
    the sleep after each command — CLIMB_TIMER_PACE for travel climbs,
    PAUSE for timer-exempt practice and manual loops."""
    laps = 0
    reports = []
    report_every = report_cadence(commands, pace)
    while True:
        current = mindstate(s.state)
        if current is not None and current >= MIND_LOCK:
            s.echo(
                f"Athletics is mind-locked — pausing until it drains "
                f"below {RESUME_BELOW}/34"
            )
            while current is not None and current > RESUME_BELOW:
                s.sleep(LOCK_POLL)
                if danger(s.state):
                    break  # dealt with below, before any climb
                current = mindstate(s.state)
            s.echo("resuming")
            reports.clear()  # a lock is the opposite of stale
        for command in commands:
            reason = danger(s.state)
            if reason:
                if handle_danger(s, reason, commands) == "stop":
                    return "danger"
                break  # start the lap over with fresh state
            s.put(command)
            s.waitrt()
            s.sleep(pace)
        laps += 1
        if laps % report_every == 0:
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
    """The no-arguments mode: walk to the optimal rung and train it,
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
        band = (
            f"{rung['low']}+"
            if rung["high"] is None
            else f"{rung['low']}-{rung['high']}"
        )
        s.echo(f"rank {rank}: heading to [{band}] {rung['label']}")
        commands, pace = rung_plan(db, rung)
        if commands is None:
            s.echo(f"the map lost the climb edge for {rung['label']} — try ;go2 update")
            return
        if not walk(s, db, [rung_goal(rung)], describe=rung["label"]):
            s.echo(
                "could not reach the spot — stopping (;go2 there and use manual mode?)"
            )
            return
        style = (
            "timer-exempt practice"
            if pace == PAUSE
            else f"paced {pace}s to the award timer"
        )
        s.echo(f"training: {' | '.join(commands)} ({style})")
        if train(s, commands, stop_when_stale=True, pace=pace) == "danger":
            return
        rank = current_rank(s.state) or rank
        advanced = next_rung(rung, rank)
        if advanced is None:
            s.echo("gains are stale but no harder rung is in reach yet — carrying on")
            train(s, commands, stop_when_stale=False, pace=pace)
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
