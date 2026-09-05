"""Tend your bleeding wounds automatically:  ;tend

;tend         watch: whenever bleeding starts, check HEALTH and tend
              every tendable bleeder, worst first
;tend once    a single check-and-tend pass, then exit

Tending stops the bleeding that kills low-circle characters and trains
First Aid while it does. Internal bleeders ("inside ...") take hundreds
of First Aid ranks to bind and are left for magic; clotted and
already-tended wounds are left alone. A dislodged object (a bolt, a
parasite) is tended again after it pops free. Dead means defer —
deathwatch owns death. Stop with:  ;stop tend

Bleed rates and responses follow lich's healing data (DRCH), rates per
https://elanthipedia.play.net/Damage#Bleeding_Levels; the HEALTH answer
is read by client/wounds.py, shared with ;hunt's wound floor.
"""

import re

from client.wounds import expand_area  # noqa: F401 — TEND's area spelling
from client.wounds import parse_health as parse_health_answer

CHECK_INTERVAL = 5  # seconds between bleeding-indicator polls
UNTENDABLE_HOLD = 60  # back off when only untendable bleeders remain


TEND_OK = (
    r"You work carefully at tending",
    r"You work carefully at binding",
    r"That area has already been tended",
    r"That area is not bleeding",
)
TEND_FAIL = (
    r"You fumble",
    r"too injured for you to do that",
    r"You must have a hand free",
)
TEND_DISLODGE = (r"You \w+ remove (?:a|the|some) (?P<item>.+?) from",)

# Bandage failure wakes the watch instantly, mid-sleep (captured live:
# "The bandages binding your neck soak through with blood, becoming
# useless, and you begin bleeding again.")
SOAK_PATTERNS = (
    r"soak through with blood",
    r"begins? bleeding again",
    r"bandages .* (?:loosen|slip|come loose)",
)


def triage(bleeders):
    """What to tend, worst first: external, still-bleeding, untended.
    Internals are magic's job at any First Aid a bandager will have."""
    queue = [b for b in bleeders if b["tendable"] and not b["inside"]]
    return sorted(queue, key=lambda b: b["severity"], reverse=True)


def check_health(s):
    """Send HEALTH and collect its answer lines."""
    s.put("health")
    lines = []
    while (line := s.get(timeout=2)) is not None:
        lines.append(line)
        if "no significant injuries" in line:
            break
    return lines


def tend(s, area, retried=False):
    """One TEND, with the response telling us what happened."""
    s.put(f"tend my {area}")
    answer = s.waitfor(*TEND_OK, *TEND_FAIL, *TEND_DISLODGE, timeout=15)
    s.waitrt()
    if answer is None:
        s.echo(f"tend {area}: no answer — moving on")
        return False
    if any(re.search(pattern, answer) for pattern in TEND_DISLODGE):
        s.echo(f"tend {area}: dislodged something — check your hands; re-tending")
        if not retried:
            return tend(s, area, retried=True)
        return False
    if any(re.search(pattern, answer) for pattern in TEND_FAIL):
        s.echo(f"tend {area}: {answer.strip()}")
        return False
    return True


def tend_pass(s):
    """One HEALTH check and tend sweep; how many bleeders remain
    untended (internal or failed)."""
    bleeders = parse_health(s)
    remaining = 0
    queue = triage(bleeders)
    internals = [b for b in bleeders if b["tendable"] and b["inside"]]
    if internals:
        worst = max(internals, key=lambda b: b["severity"])
        s.echo(
            f"{len(internals)} internal bleeder(s) — bandages can't reach "
            f"(worst: inside {worst['area']}, {worst['rate']}); magic or a healer"
        )
        remaining += len(internals)
    if not queue and not internals:
        s.echo("no bleeding wounds")
    for bleeder in queue:
        if s.dead:
            return remaining + 1
        if not tend(s, bleeder["area"]):
            remaining += 1
    return remaining


def parse_health(s_or_lines):
    """Bleeder rows out of HEALTH output: [{area, inside, rate,
    severity, tendable}]. Accepts either a script handle (asks the
    game) or already-collected lines (the tests' path)."""
    if isinstance(s_or_lines, list):
        lines = s_or_lines
    else:
        lines = check_health(s_or_lines)
    return _parse_health_lines(lines)


def _parse_health_lines(lines):
    """The bleeding table's rows, via the shared HEALTH parser
    (client/wounds.py, #151) — the wound list rides along unused here."""
    return parse_health_answer(lines).bleeders()


def bleeding(state):
    indicators = getattr(state, "indicator", None) or {}
    return indicators.get("IconBLEEDING") == "y"


def main(s):
    once = bool(s.args) and s.args[0] == "once"
    if once:
        if s.dead:
            s.echo("you are dead — that is beyond bandages")
            return
        tend_pass(s)
        return
    s.echo("watching for bleeding — ;stop tend to stop")
    force = False
    while True:
        if s.dead:
            s.sleep(CHECK_INTERVAL)
            continue
        if force or bleeding(s.state):
            force = False
            remaining = tend_pass(s)
            # Only untendable bleeders left: the icon stays lit, so a
            # short poll would re-sweep forever. Hold back.
            hold = UNTENDABLE_HOLD if remaining else CHECK_INTERVAL
        else:
            hold = CHECK_INTERVAL
        # The sleep doubles as a listener: a soak-through wakes the
        # watch immediately instead of waiting out the hold.
        force = s.waitfor(*SOAK_PATTERNS, timeout=hold) is not None
