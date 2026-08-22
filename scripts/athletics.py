"""Walk to the best Athletics spot for your rank and train there:  ;athletics

With no arguments the script reads your rank (asking the game with EXP
ATHLETICS when the exp window is empty), walks to the hardest ladder
rung in reach — the community map knows the rooms — and trains it,
pausing at mind-lock and moving up the ladder when gains go stale.
Standard travel climbs award xp at most once per random 45–60s window
(docs/experience.md), so climb loops are paced to that timer instead
of spammed; `climb practice` rungs are timer-exempt continuous
activities — started once and watched, never spammed (#89).
The ladder is Zoluren spots per Elanthipedia, encoded with their
map rooms, rank bands, and conditions in client/climbs.py; rank 100+
trains in town on the Crossing battlements. Auto mode checks
ENCUMBRANCE once at start and warns when a load would blunt every
climb. Also:

    ;athletics list                     show the ladder for your rank
    ;athletics climb x | climb back     train a manual loop right here

Progress is echoed about every five minutes; pair with ;xp for
history. Danger interrupts training (#72): hostiles in the room mean
break off and climb away until clear, low health means hold until it
recovers, and death stops the script — it never keeps feeding climbs
into an engagement. A spot that keeps re-engaging is contested (#86):
after three hostile break-offs in ten minutes the script gives it up —
spawn areas never empty on their own, so waiting is futile; auto mode
falls back to the next-best rung and manual mode stops with advice.
Stop with:  ;stop athletics
"""

import re
import time

from client import climbs

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
CONTESTED_LIMIT = 3  # hostile break-offs inside the window = contested
CONTESTED_WINDOW = 600  # seconds the break-off count looks back over

# The rank ladder and its advice rows live in client/climbs.py,
# keyed to the community map (#87) — one table for every map-aware
# consumer. Travel rungs carry bottom/top rooms (loop commands are
# read from the map's own edges at runtime, paced to the award
# timer); practice rungs carry the room and the obstacle
# (timer-exempt, tight loop).
AUTO_LADDER = climbs.rungs()

# Real spots the trainer cannot walk a loop for (swims, unmapped).
PRACTICE_SPOTS = climbs.advice()


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

# "   Encumbrance : Heavily Burdened" — the ENC command's level line.
ENC_LINE = re.compile(r"Encumbrance\s*:\s*(.+)")


def check_burden(s):
    """ENC once at auto-mode start: encumbrance penalizes every climb
    (Elanthipedia, client/climbs.py's conditions note), so a loaded
    character gets told before laps are wasted on it. Levels from
    "Somewhat Burdened" up warn; None/Light pass silently."""
    s.put("encumbrance")
    line = s.waitfor(r"Encumbrance\s*:", timeout=5)
    match = ENC_LINE.search(line) if line else None
    if match is None:
        return
    level = match.group(1).strip()
    if "burdened" in level.lower():
        s.echo(
            f"ATHLETICS: you are {level} — encumbrance penalizes every "
            "climb; stow or drop the load for cleaner gains"
        )


def probe_rank(s):
    """Ask the game for the rank (EXP ATHLETICS) — the fallback when the
    exp window has no Athletics entry because nothing is learning yet."""
    s.put("exp athletics")
    line = s.waitfor(r"Athletics:\s+\d+", timeout=5)
    match = EXP_LINE.search(line) if line else None
    return int(match.group(1)) if match else None


def in_band(rung, rank):
    return rung["low"] <= rank and (rung["high"] is None or rank < rung["high"])


def optimal_rung(rank, exclude=()):
    """The hardest walkable rung in reach: greatest entry rank the
    character clears, later ladder entries winning ties. exclude names
    rungs (by label) found contested this run (#86)."""
    candidates = [
        rung
        for rung in AUTO_LADDER
        if in_band(rung, rank or 0) and rung["label"] not in exclude
    ]
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
    """The burst-escape (docs/combat.md, field-proven): two retreats
    step melee -> pole -> missile range, and climbing is legal again
    from missile range even while the creature stays in the room — so
    burst retreat/retreat/move through the type-ahead and judge
    success by whether the ROOM changed, not by whether it emptied
    (a bear that won't leave must not pin the trainer, captured
    2026-08-22). Spaced commands lose the race to re-advances
    (captured twice: the #72 death, four failed single-retreat
    exits)."""
    for attempt in range(ESCAPE_ATTEMPTS):
        before = getattr(s.state, "room_uid", None)
        s.put("retreat")
        s.put("retreat")
        s.put(commands[attempt % len(commands)])
        s.waitrt()
        s.sleep(1)
        if getattr(s.state, "room_uid", None) != before:
            return True
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


def fall_back(s, rank, contested):
    """The next-best uncontested rung for auto mode, or None after
    saying so — a contested spot is left, never waited out (#86)."""
    rung = optimal_rung(rank, exclude=contested)
    if rung is None:
        s.echo(
            "ATHLETICS: every rung in reach is contested — clear one "
            "yourself or train manually (;help athletics)"
        )
        return None
    s.echo("abandoning the contested spot for the next-best rung")
    return rung


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
    lap_seconds = len(commands) * (PAUSE + EST_ROUNDTIME) + pace
    return max(1, round(REPORT_EVERY_SECONDS / lap_seconds))


# Practice-activity wordings: climb practice is a CONTINUOUS activity,
# not a per-command action — captured 2026-08-22 at the NE gate
# embrasure (#89), where the old per-second re-send earned a refusal
# per second. The refusal means it is already running; the end
# wordings are assumptions until captured.
PRACTICE_ACTIVE = (
    "begin to practice",  # captured
    "continue to practice",  # captured
    "should stop practicing",  # captured: refused — already running
)
PRACTICE_ENDED = ("you stop practicing", "no longer practicing")
PRACTICE_REASSERT = 120  # seconds between re-sends while it looks active


def practice_seen(s, practicing):
    """Scan queued game lines for the practice activity's state (#89)."""
    while True:
        line = s.get(timeout=0)
        if line is None:
            return practicing
        lowered = line.lower()
        if any(needle in lowered for needle in PRACTICE_ACTIVE):
            practicing = True
        elif any(needle in lowered for needle in PRACTICE_ENDED):
            practicing = False


def stale_result(s, reports, stop_when_stale):
    """The shared going-stale reaction: "stale" for auto mode, ladder
    advice (and a fresh count) for manual mode, None otherwise."""
    if not going_stale(reports):
        return None
    if stop_when_stale:
        return "stale"
    s.echo("gains look stale here — this spot may be outgrown:")
    for line in recommendations(current_rank(s.state)):
        s.echo(line)
    reports.clear()
    return None


def train(s, commands, stop_when_stale=False, pace=PAUSE, practice=False):
    """Cycle the movement commands, pausing at mind-lock. Returns
    "contested" when hostiles keep breaking the training (#86); with
    stop_when_stale, returns "stale" so auto mode can advance; manual
    mode otherwise runs until stopped (echoing ladder advice when
    gains stall). pace is the award-timer wait (CLIMB_TIMER_PACE for
    travel climbs, PAUSE for timer-exempt practice and manual loops),
    slept once per lap back at the loop's start room with danger
    polls — repeat climbs inside the window grant nothing but cost
    nothing, so closing the loop early loses no experience and never
    leaves the trainer idling deep in a spawn room. With practice, the
    command starts a continuous activity (#89): it is sent once,
    watched through the game's own lines, and re-asserted only when
    the activity ends or every PRACTICE_REASSERT seconds."""
    laps = 0
    reports = []
    breaks = []  # monotonic stamps of hostile break-offs (#86)
    practicing = False
    last_assert = 0.0
    started = last_report = time.monotonic()
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
                if reason == "hostiles":
                    now = time.monotonic()
                    breaks = [t for t in breaks if now - t < CONTESTED_WINDOW]
                    breaks.append(now)
                    if len(breaks) >= CONTESTED_LIMIT:
                        s.echo(
                            "ATHLETICS: this spot is contested — "
                            f"{CONTESTED_LIMIT} hostile break-offs in "
                            f"{CONTESTED_WINDOW // 60} minutes, and spawn "
                            "areas never empty on their own"
                        )
                        return "contested"
                practicing = False  # the escape moved us; practice ended
                break  # start the lap over with fresh state
            if practice:
                practicing = practice_seen(s, practicing)
                now = time.monotonic()
                if not practicing or now - last_assert >= PRACTICE_REASSERT:
                    s.put(command)
                    last_assert = now
                    practicing = True  # optimistic; the next scan corrects
                s.waitrt()
                s.sleep(PAUSE)
                continue
            s.put(command)
            s.waitrt()
            s.sleep(PAUSE)
        else:
            # The award-timer wait, at the lap's start room, reacting
            # to trouble within a poll instead of a full window.
            remaining = pace - PAUSE
            while remaining > 0:
                s.sleep(min(DANGER_POLL, remaining))
                remaining -= DANGER_POLL
                if danger(s.state):
                    break  # the next lap's check handles it now
        laps += 1
        if practice:
            # A practice "lap" is one one-second watch-poll, not a
            # climb — report by clock, worded as what it is (#89).
            now = time.monotonic()
            if now - last_report < REPORT_EVERY_SECONDS:
                continue
            last_report = now
            current = mindstate(s.state)
            shown = f"{current}/34" if current is not None else "not learning yet"
            minutes = max(1, round((now - started) / 60))
            s.echo(f"practicing {minutes}m — Athletics mindstate {shown}")
            reports.append(current)
            result = stale_result(s, reports, stop_when_stale)
            if result:
                return result
        elif laps % report_every == 0:
            current = mindstate(s.state)
            shown = f"{current}/34" if current is not None else "not learning yet"
            s.echo(f"{laps} laps — Athletics mindstate {shown}")
            reports.append(current)
            result = stale_result(s, reports, stop_when_stale)
            if result:
                return result


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
    check_burden(s)
    rung = optimal_rung(rank)
    if rung is None:
        s.echo(f"no ladder rung fits rank {rank} — train manually (;help athletics)")
        return
    contested = set()  # rung labels given up this run (#86)
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
        practice_rung = "practice" in rung
        result = train(
            s, commands, stop_when_stale=True, pace=pace, practice=practice_rung
        )
        if result == "danger":
            return
        rank = current_rank(s.state) or rank
        if result == "contested":
            contested.add(rung["label"])
            rung = fall_back(s, rank, contested)
            if rung is None:
                return
            continue
        advanced = next_rung(rung, rank)
        if advanced is None:
            s.echo("gains are stale but no harder rung is in reach yet — carrying on")
            if (
                train(
                    s,
                    commands,
                    stop_when_stale=False,
                    pace=pace,
                    practice=practice_rung,
                )
                == "contested"
            ):
                contested.add(rung["label"])
                rung = fall_back(s, rank, contested)
                if rung is not None:
                    continue
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
        if train(s, commands) == "contested":
            s.echo(
                "ATHLETICS: stopping — spawn areas never empty on their "
                "own; clear the spot or pick another (;athletics list)"
            )
        return
    auto_train(s)
