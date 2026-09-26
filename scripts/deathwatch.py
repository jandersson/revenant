"""Log out safely if you die unattended, keeping the body for a raise:  ;deathwatch  (autostarted)

    ;deathwatch            quit after a 10-minute rescue grace (the default)
    ;deathwatch 5          a five-minute grace
    ;deathwatch depart     depart at the grace instead (the old behaviour)
    ;deathwatch 5 depart   both
    ;deathwatch young      depart at once on a death at circle 1 with fewer than 6 deaths (setting: deathwatch_young_depart)

Watches the DEAD indicator; while you live it costs nothing. On death
it alerts loudly, keeps the connection alive through the game's idle
check, and waits a rescue grace — default 10 minutes — capped inside
the body's announced decay window ("Your body will decay beyond its
ability to hold your soul in N minutes"). If nobody resurrects you in
time it QUITs: the game accepts QUIT while dead (the operator,
2026-09-13), and a logged-out body does not decay — the 2026-08-22
capture found the character still a ghost two and a half hours after
a 21-minute window (docs/death.md) — so the body waits for a raise at
the next login, and no favors or items are spent. `depart` asks for
the old ending instead: DEPART with the best variant your favors
afford, trying DEPART FULL (keeps items and coins, 3 favors), then
ITEMS, then GRAVE, then bare DEPART, judging each attempt by the DEAD
indicator actually clearing. `;stop deathwatch` holds either off while
a rescue is underway. A death that predates the watch — a restart or
;reexec mid-death — counts as freshly observed: the countdown starts
the moment the script does.

A young character's death costs next to nothing to leave, so with the
setting `deathwatch_young_depart` on (off by default; File → Settings,
or `young` in the arguments for one run) a death at circle 1 with
fewer than 6 deaths departs at once, no grace, no logout (the
operator, 2026-09-26, after a circle-1 Barbarian's first death). The
circle and the death count are read off the lines the watch drains
while you live — INFO's "Circle: 1" and EXP's "Deaths: 2", both in
;sheet's login snapshot — and asked (INFO, EXP) at the death when none
was seen; a count or circle still unknown keeps the usual ending.
"""

import re
import time

POLL = 2  # seconds between DEAD-indicator checks
DEFAULT_GRACE_MINUTES = 10  # rescue window before the ending
DECAY_SAFETY_MINUTES = 5  # end this long before the announced decay
KEEPALIVE_SECONDS = 120  # a harmless command per this, against idle-out
COUNTDOWN_SECONDS = 60  # progress echo cadence while dead
DEPART_WAIT = 12  # seconds to give each depart attempt to take
DECAY_SCAN_SECONDS = 6  # how long to wait for the decay announcement
# Best variant first (Elanthipedia "Depart command": FULL keeps items
# and coins at 3 favors, ITEMS at 2, GRAVE at 1); an unaffordable
# variant leaves you dead, and the next one steps in.
DEPART_LADDER = ("depart full", "depart items", "depart grave", "depart")

# Captured 2026-08-22 (the Uthmor death log, docs/death.md).
DECAY_LINE = re.compile(r"decay beyond its ability to hold your soul in (\d+) minute")
# A young character departs at once when the setting says so: circle
# at most YOUNG_CIRCLE, deaths below YOUNG_DEATHS (the operator's rule).
YOUNG_CIRCLE = 1
YOUNG_DEATHS = 6
ASK_SECONDS = 3  # how long an INFO / EXP answer is collected at a death
# INFO's "Name: ... Circle: 1" and EXP's footer "... Favors: 0  Deaths: 2"
# (captured 2026-09-26).
CIRCLE_LINE = re.compile(r"\bCircle:\s*(\d+)")
DEATHS_LINE = re.compile(r"\bDeaths:\s*(\d+)")


def is_dead(state):
    indicators = getattr(state, "indicator", None) or {}
    return indicators.get("IconDEAD") == "y"


def grace_minutes_from(args):
    """The rescue grace from the arguments, or the default."""
    for arg in args:
        try:
            return max(0.0, float(arg))
        except ValueError:
            continue
    return float(DEFAULT_GRACE_MINUTES)


def note(line, seen):
    """Keep the circle and the death count a passing line states."""
    if match := CIRCLE_LINE.search(line or ""):
        seen["circle"] = int(match.group(1))
    if match := DEATHS_LINE.search(line or ""):
        seen["deaths"] = int(match.group(1))


def young_wanted(args, settings=None):
    """True when `young` is in the arguments or the setting is on."""
    if "young" in {str(arg).lower() for arg in args}:
        return True
    if settings is None:
        try:
            from client.settings import load_settings

            settings = load_settings() or {}
        except Exception:  # noqa: BLE001 — no settings, no young ending
            settings = {}
    return bool(settings.get("deathwatch_young_depart"))


def is_young(seen):
    """Circle 1 and fewer than 6 deaths, both known."""
    circle, deaths = seen.get("circle"), seen.get("deaths")
    return (
        circle is not None
        and deaths is not None
        and circle <= YOUNG_CIRCLE
        and deaths < YOUNG_DEATHS
    )


def ask_for(s, command, seen):
    """Send a read-only command and note what its answer states."""
    s.put(command)
    deadline = time.monotonic() + ASK_SECONDS
    while time.monotonic() < deadline:
        line = s.get(timeout=0.5)
        if line is not None:
            note(line, seen)


def mode_from(args):
    """ "quit" (the default) or "depart", from the word in the arguments."""
    words = {str(arg).lower() for arg in args}
    return "depart" if "depart" in words else "quit"


def leave(s):
    """QUIT while dead: the body keeps for a raise at the next login
    (docs/death.md). Said first, since the connection ends with it."""
    s.echo(
        "DEATHWATCH: still dead — logging out to keep the body for a raise "
        "(QUIT); log back in when someone can resurrect you"
    )
    s.put("quit")


def scan_decay_minutes(s):
    """The announced decay window ("...hold your soul in N minutes"),
    or None. The line lands a beat after the DEAD indicator flips, so
    the scan waits briefly instead of trusting one queue drain."""
    deadline = time.monotonic() + DECAY_SCAN_SECONDS
    while time.monotonic() < deadline:
        line = s.get(timeout=0.5)
        if line is None:
            continue
        match = DECAY_LINE.search(line)
        if match:
            return int(match.group(1))
    return None


def wait_for_rescue(s, grace_seconds):
    """Hold through the grace, keeping the connection alive; True when
    a resurrection cleared the DEAD indicator."""
    deadline = time.monotonic() + grace_seconds
    last_keepalive = time.monotonic()
    last_countdown = time.monotonic()
    while time.monotonic() < deadline:
        if not is_dead(s.state):
            return True
        now = time.monotonic()
        if now - last_keepalive >= KEEPALIVE_SECONDS:
            last_keepalive = now
            # The ghost refusal this earns still counts as activity —
            # the idle check is what disconnected the captured death.
            s.put("look")
        if now - last_countdown >= COUNTDOWN_SECONDS:
            last_countdown = now
            remaining = max(0, round((deadline - now) / 60))
            s.echo(
                f"DEATHWATCH: still dead — the grace ends in about {remaining} "
                "minute(s) unless rescued (;stop deathwatch to hold)"
            )
        s.sleep(POLL)
    return not is_dead(s.state)


def depart(s):
    """Walk the depart ladder; True once the DEAD indicator clears."""
    for command in DEPART_LADDER:
        s.echo(f"DEATHWATCH: {command}")
        s.put(command)
        waited = 0
        while waited < DEPART_WAIT:
            s.sleep(POLL)
            waited += POLL
            if not is_dead(s.state):
                s.echo(f"DEATHWATCH: departed ({command}) — you are back")
                return True
    s.echo("DEATHWATCH: still dead after every depart variant — intervene!")
    return False


def handle_death(s, grace_minutes, mode="quit", young=False, seen=None):
    seen = {} if seen is None else seen
    if young:
        if seen.get("circle") is None:
            ask_for(s, "info", seen)
        if seen.get("deaths") is None:
            ask_for(s, "exp", seen)
        if is_young(seen):
            s.echo(
                f"DEATHWATCH: you are DEAD at circle {seen['circle']} with "
                f"{seen['deaths']} death(s) — a young character departs at once "
                "(deathwatch_young_depart)"
            )
            depart(s)
            return "departed"
    decay = scan_decay_minutes(s)
    grace = grace_minutes
    if decay is not None:
        grace = min(grace, max(decay - DECAY_SAFETY_MINUTES, 1))
    window = f"{decay} minute decay window" if decay else "decay window unknown"
    ending = "departing" if mode == "depart" else "logging out"
    s.echo(
        f"DEATHWATCH: you are DEAD ({window}) — {ending} in "
        f"{grace:.0f} minute(s) unless rescued. ;stop deathwatch holds it."
    )
    if wait_for_rescue(s, grace * 60):
        s.echo("DEATHWATCH: alive again — standing down to watch")
        return "rescued"
    if mode == "depart":
        depart(s)
        return "departed"
    leave(s)
    return "left"


def main(s):
    grace_minutes = grace_minutes_from(s.args)
    mode = mode_from(s.args)
    ending = (
        "departing (best variant your favors afford)"
        if mode == "depart"
        else "logging out to keep the body for a raise"
    )
    s.echo(
        f"deathwatch: watching — on an unattended death, {ending} after "
        f"{grace_minutes:.0f} minute(s)"
    )
    young = young_wanted(s.args)
    if young:
        s.echo(
            f"deathwatch: a death at circle {YOUNG_CIRCLE} with fewer than "
            f"{YOUNG_DEATHS} deaths departs at once"
        )
    seen = {}
    while True:
        if is_dead(s.state):
            if handle_death(s, grace_minutes, mode, young, seen) == "left":
                return  # the connection ends with the QUIT; nothing to watch
        else:
            # Keep the queue drained so a death scans only fresh lines,
            # noting the circle and the death count as they pass.
            while (line := s.get(timeout=0)) is not None:
                note(line, seen)
        s.sleep(POLL)
