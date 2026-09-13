"""Log out safely if you die unattended, keeping the body for a raise:  ;deathwatch  (autostarted)

    ;deathwatch            quit after a 10-minute rescue grace (the default)
    ;deathwatch 5          a five-minute grace
    ;deathwatch depart     depart at the grace instead (the old behaviour)
    ;deathwatch 5 depart   both

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


def handle_death(s, grace_minutes, mode="quit"):
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
    while True:
        if is_dead(s.state):
            if handle_death(s, grace_minutes, mode) == "left":
                return  # the connection ends with the QUIT; nothing to watch
        else:
            # Keep the queue drained so a death scans only fresh lines.
            while s.get(timeout=0) is not None:
                pass
        s.sleep(POLL)
