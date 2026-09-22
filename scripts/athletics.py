"""Walk to the best Athletics spot for your rank and train there:  ;athletics

With no arguments the script reads your rank (asking the game with EXP
ATHLETICS when the exp window is empty), walks to the hardest ladder
rung in reach — the community map knows the rooms — and trains it,
pausing at mind-lock and moving up the ladder when gains go stale.
Below rank 50 the rung is a swim: the Arthe Dale swimming hole's four
rooms looped by plain moves, no roll to lose (dr-scripts' athletics.lic
and its base-athletics.yaml, whose Crossing rotation of walls,
embrasures and trees for 50-290 is the ladder's next kind: each stop
walked to and climbed once per pass, no timer wait between rooms).
Standard travel climbs award xp at most once per random 45–60s window
(docs/experience.md), so climb loops are paced to that timer instead
of spammed; `climb practice` rungs are timer-exempt continuous
activities — started once and watched, never spammed (#89).
The ladder is Zoluren spots per Elanthipedia, encoded with their
map rooms, rank bands, and conditions in client/game/climbs.py; rank 100+
trains in town on the Crossing battlements. Before the first climb the
script STOWs whatever the hands hold (a held item makes every climb
harder; nothing is ever dropped), and auto mode checks ENCUMBRANCE
once and warns when a load would blunt every climb. Also:

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
A rung or rotation stop with another player already in it on arrival
is theirs, and one listing three or more creatures is a crowd
(dr-scripts' climb? rule): the next-best rung, or the stop skipped,
said either way (#178).
Stop with:  ;stop athletics
"""

import re
import time

from client.game import buffs, climbs, probe
from client.game import flight
from client.game.status import counted

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
CROWDED = 3  # creatures listed in the room on arrival = a crowd (dr-scripts' climb?)
COLLECT_SECONDS = 3  # a cast's answer window (client/game/probe.py)
TAIL_SECONDS = 1.5

# The rank ladder and its advice rows live in client/game/climbs.py,
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


def occupants(s):
    """The other players in the room, as the parser read "Also here"."""
    return list(getattr(s.state, "room_players", None) or [])


def crowd(s):
    """The room's listed creatures when they make a crowd, else []."""
    names = list(getattr(s.state, "room_creatures", None) or [])
    return names if len(names) >= CROWDED else []


def taken_by(s, doing):
    """Why the room is not ours on arrival — "<names> <doing> — theirs"
    for a player already in it, "<n> creatures here (...) — a crowd" for
    CROWDED or more creatures listed — or None for a room of our own (#178)."""
    if names := occupants(s):
        return f"{', '.join(names)} {doing} — their"
    if beasts := crowd(s):
        return f"{len(beasts)} creatures here ({counted(beasts)}) — a crowd, not our"
    return None


def empty_hands(s):
    """Whatever the hands hold goes into a container before the first
    climb: a held item makes every climb harder ("Your oak-hafted
    handaxe makes the climb more difficult", client/game/walker.py),
    and a hunt now ends with the weapon in hand. STOW, never DROP — a
    dropped item is a lost item (the operator, 2026-09-12). A handle
    without hand state is left alone."""
    stowed = []
    for side in ("left", "right"):
        held = getattr(s.state, f"{side}_hand", None)
        noun = held.get("noun") if isinstance(held, dict) else None
        if noun:
            s.put(f"stow my {noun}")
            s.waitrt()
            stowed.append(noun)
    if stowed:
        s.echo(
            f"ATHLETICS: stowed your {' and '.join(stowed)} — a held item "
            "makes every climb harder"
        )


def check_burden(s):
    """ENC once at auto-mode start: encumbrance penalizes every climb
    (Elanthipedia, client/game/climbs.py's conditions note), so a loaded
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
            "climb; stow the load in a container or bank the coins for "
            "cleaner gains (never drop it)"
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
    # A swim in band beats every climb: no roll to lose, no fall, no
    # refusal (dr-scripts' Crossing rule below rank 50, #177).
    swims = [rung for rung in candidates if rung["kind"] == "swim"]
    if swims:
        return swims[-1]
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


def swim_loop(db, rooms):
    """The moves round a swim rung's rooms, read from the map's own
    edges, the last room leading back to the first; None when an edge
    is missing."""
    moves = []
    for here, there in zip(rooms, rooms[1:] + rooms[:1]):
        move = (db.rooms.get(here, {}).get("wayto") or {}).get(str(there))
        if not isinstance(move, str):
            return None
        moves.append(move)
    return moves


def rotation_steps(rung):
    """A rotation rung's stops as {room, command} steps, the justice
    stops left out when settings.json's avoid_justice_climbs is on."""
    from client.settings import setting

    avoid = bool(setting("avoid_justice_climbs"))
    return [
        {"room": room, "command": command}
        for room, command, justice in rung["stops"]
        if not (avoid and justice)
    ]


def rung_plan(db, rung):
    """(commands, pace) for a rung. Practice rungs spam their obstacle
    (award-timer-exempt); travel rungs pace each climb past the timer;
    a swim loops its rooms and a rotation walks its stops, each room's
    timer being its own (no pacing). commands is None when the map lost
    a travel or swim rung's edges. A rotation's commands are {room,
    command} steps — train() walks to the room first."""
    if "practice" in rung:
        return [f"climb practice {rung['practice']}"], PAUSE
    if rung.get("kind") == "swim":
        return swim_loop(db, rung["rooms"]), PAUSE
    if rung.get("kind") == "rotation":
        return rotation_steps(rung), PAUSE
    return climb_loop(db, rung["bottom"], rung["top"]), CLIMB_TIMER_PACE


def rung_goal(rung):
    if rung.get("kind") == "swim":
        return rung["rooms"][0]
    if rung.get("kind") == "rotation":
        return rung["stops"][0][0]
    return rung.get("bottom") or rung["room"]


def step_command(step):
    """The game command of a plain or a {room, command} step."""
    return step["command"] if isinstance(step, dict) else step


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
    """The burst-escape (docs/combat.md, field-proven), shared with every
    trainer since #285 (client/game/flight.py): STAND when seated, then
    retreat/retreat/move back to back through the type-ahead, judged by
    the ROOM changing, not by the answer. The climb along the training
    edge is tried first — two retreats reach missile range, where
    climbing is legal with the creature still present, and the
    cave-bear stalemate (#86) is escaped that way — and a compass exit
    next: a climb that fails for footing never changes the room, and
    the goblin outside the western gate re-advanced through eight of
    them while the trainer sat (#286, 2026-09-22)."""
    return flight.flee(
        s, preferred=[step_command(step) for step in commands], attempts=ESCAPE_ATTEMPTS
    )


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
# The game's own verdict on a practice obstacle (dr-scripts' flags,
# #177; wordings as its Flags name them, unobserved here): too hard
# means one rung down, no challenge means the next rung up — at once,
# not after minutes of stale reports.
PRACTICE_TOO_HARD = ("climb is too difficult",)
PRACTICE_TOO_EASY = ("no challenge at all",)


def practice_seen(s, practicing):
    """Scan queued game lines for the practice activity's state (#89):
    (practicing, verdict) — the verdict "too_hard" or "too_easy" when
    the game passed one on the obstacle, else None."""
    verdict = None
    while True:
        line = s.get(timeout=0)
        if line is None:
            return practicing, verdict
        lowered = line.lower()
        if any(needle in lowered for needle in PRACTICE_TOO_HARD):
            verdict = "too_hard"
        elif any(needle in lowered for needle in PRACTICE_TOO_EASY):
            verdict = "too_easy"
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


def train(
    s,
    commands,
    stop_when_stale=False,
    pace=PAUSE,
    practice=False,
    db=None,
    walk=None,
    filler=None,
):
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
                practicing, verdict = practice_seen(s, practicing)
                if verdict == "too_hard":
                    s.echo("ATHLETICS: the game calls this climb too difficult")
                    return "too_hard"
                if verdict == "too_easy":
                    s.echo("ATHLETICS: the game calls this climb no challenge")
                    if stop_when_stale:
                        return "stale"
                    for line in recommendations(current_rank(s.state)):
                        s.echo(line)
                now = time.monotonic()
                if not practicing or now - last_assert >= PRACTICE_REASSERT:
                    s.put(command)
                    last_assert = now
                    practicing = True  # optimistic; the next scan corrects
                s.waitrt()
                s.sleep(PAUSE)
                continue
            if isinstance(command, dict):
                # A rotation stop (#177): walk there, then climb.
                if walk is None or not walk(
                    s, db, [command["room"]], describe=command["command"]
                ):
                    s.echo(
                        f"ATHLETICS: could not reach room {command['room']} — skipping it"
                    )
                    continue
                s.sleep(1)  # the room's players arrive with the room
                if why := taken_by(s, "at this stop"):
                    s.echo(f"ATHLETICS: {why}s, skipping it")
                    continue
                command = command["command"]
            s.put(command)
            s.waitrt()
            s.sleep(PAUSE)
        else:
            # The award-timer wait, at the lap's start room, reacting
            # to trouble within a poll instead of a full window.
            remaining = pace - PAUSE
            if remaining > 0 and filler is not None:
                filler(s)  # buffs and training casts ride the wait (#177)
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


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def wait_filler(s):
    """What the award-timer wait does instead of idling: the profile's
    buffs kept up and its training casts (client/game/buffs.py, the
    hunt's helpers), or None when the profile names no buff."""
    from client.game.profile import load_profile

    profile = load_profile(getattr(s.state, "name", None) or "")
    if not profile["buffs"]:
        return None
    state = buffs.BuffState()

    def report(what, answer):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"ATHLETICS: unrecognized {what} answer {first!r} — please report it")

    def fill(s):
        # DISCERN once before the first cast, as the hunt does: the
        # ramp's ceiling is the game's own estimate (#264: heroic
        # strength at 18 mana here, the hunt's cap 16, a backfire).
        buffs.discern_slots(s, profile, state, ask, "ATHLETICS", report)
        buffs.cast_buffs(s, profile, state, ask, "ATHLETICS", report)

    return fill


def auto_train(s, db=None, walk=None):
    """The no-arguments mode: walk to the optimal rung and train it,
    moving up the ladder when a rung goes stale."""
    if db is None or walk is None:
        from client.game.mapdb import MapDB, download, mapdb_path
        from client.game.walker import walk as real_walk

        if not mapdb_path().is_file():
            s.echo("downloading map database (first use, ~13MB) ...")
            download()
        db = db or MapDB.load()
        walk = walk or real_walk

    rank = current_rank(s.state)
    if rank is None:
        rank = probe_rank(s)
    empty_hands(s)
    check_burden(s)
    filler = wait_filler(s)
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
        s.sleep(1)  # the room's players arrive with the room
        if why := taken_by(s, "training here"):
            # Their spot, or a crowd (#178): the next-best rung, no laps here.
            s.echo(f"ATHLETICS: {why} spot")
            contested.add(rung["label"])
            rung = fall_back(s, rank, contested)
            if rung is None:
                return
            continue
        style = (
            "timer-exempt practice"
            if pace == PAUSE
            else f"paced {pace}s to the award timer"
        )
        shown = " | ".join(
            f"{c['command']} @{c['room']}" if isinstance(c, dict) else c
            for c in commands
        )
        s.echo(f"training: {shown} ({style})")
        practice_rung = "practice" in rung
        result = train(
            s,
            commands,
            stop_when_stale=True,
            pace=pace,
            practice=practice_rung,
            db=db,
            walk=walk,
            filler=filler,
        )
        if result == "danger":
            return
        rank = current_rank(s.state) or rank
        if result in ("contested", "too_hard"):
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
        empty_hands(s)
        if train(s, commands) == "contested":
            s.echo(
                "ATHLETICS: stopping — spawn areas never empty on their "
                "own; clear the spot or pick another (;athletics list)"
            )
        return
    auto_train(s)
