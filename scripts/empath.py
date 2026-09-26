"""Heal another as an Empath, then yourself:  ;empath <patient>

    ;empath <patient>          TOUCH them, TAKE every wound most urgent first, touch again for what that bared, then heal yourself
    ;empath <patient> take     the transfers only, no self-heal after
    ;empath self               heal your own wounds (Heal Wounds) and scars (Heal Scars), worst first
    ;empath ... mana=15        the mana each Heal Wounds / Heal Scars is prepared with (15 by default)
    ;empath return             (typed while it runs) finish the transfer or cast in hand and end

An Empath heals by moving a patient's wounds onto himself and healing
his own body with spells (Elanthipedia: Empath healing, Take command,
Heal Wounds, Heal Scars; client/game/empathy.py is the model, with the
wordings captured on 2026-09-26). TOUCH <patient> forges the link and
lists every wound by part on the familiar stream; the transfers go in
the operator's order — anything bleeding, then the severest, the head
and torso before the limbs, fresh wounds before scars — each TAKE
waited out until "...wounds are fully healed". The link holds while
the TAKEs follow each other; when it lapses ("You have no empathic
link"), one TOUCH renews it and the transfer is sent again — the
patient sees "<you> touches you" at every TOUCH, so there is one per
round, not one per wound. Taking fresh wounds bares scars the first
listing hid, so the patient is touched again after a round and the
rest taken, up to three rounds.

The self-heal reads HEALTH (client/game/wounds.py), casts the worst
first — PREPARE HW for fresh wounds or HS for scars, CAST <part> (outside
then inside) or CAST <part> INTERNAL — and reads HEALTH again, until
"no significant injuries" or forty casts. It stops when the mana runs
below a fifth. Nothing is ever taken without the patient in the room:
a TOUCH that finds nobody, or is avoided (a cold demeanor), ends it.
Stop with:  ;stop empath, or ;empath return.
"""

import time

from client.game import probe
from client.game.empathy import (
    AVOIDED,
    HEALED,
    LINKED,
    NO_LINK,
    PREPARED,
    TAKEN,
    parse_touch,
    take_command,
    transfer_order,
    heal_casts,
)
from client.game.loop import wants_stop
from client.game.wounds import parse_health

COLLECT_SECONDS = 4
TAIL_SECONDS = 1
TOUCH_SECONDS = 6  # the listing arrives on the familiar stream
TAKE_SECONDS = 45  # a transfer runs while the wound moves
PREPARE_SECONDS = 25
ROUNDS = 3
MAX_CASTS = 40
MANA_FLOOR = 20  # percent
DEFAULT_MANA = 15
STREAMS = ("", "familiar", "combat")


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def exchange(s, command, until, seconds):
    """PUT `command` and read the story and familiar streams until a line
    holds one of `until` (lowercased) or `seconds` pass; the text read."""
    while s.get(timeout=0, streams=STREAMS) is not None:
        pass  # what arrived before the command is not its answer
    s.put(command)
    lines = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        piece = s.get(timeout=0.5, streams=STREAMS)
        if piece is None:
            continue
        text = piece[1] if isinstance(piece, tuple) else piece
        lines.append(text)
        if any(word in text.lower() for word in until):
            break
    return "".join(lines)


def touch(s, patient):
    """TOUCH the patient: the Injury list, or None (said) when there was
    no link — nobody by that name, or a touch avoided."""
    answer = exchange(
        s, f"touch {patient}", ("vitality", "nothing wrong with"), TOUCH_SECONDS
    )
    lowered = answer.lower()
    if any(word in lowered for word in AVOIDED):
        s.echo(
            f"empath: {patient.capitalize()} avoids the touch — their demeanor is cold"
        )
        return None
    injuries = parse_touch(answer)
    if injuries is None:
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        linked = any(word in lowered for word in LINKED)
        s.echo(
            f"empath: TOUCH {patient} answered {first!r}"
            + ("" if linked else f" — is {patient} here?")
        )
        return None
    return injuries


def take(s, patient, injury):
    """One transfer, the link renewed once if it had lapsed. True when
    the wound came over."""
    command = take_command(patient, injury)
    for attempt in range(2):
        answer = exchange(s, command, TAKEN + NO_LINK + ("cannot",), TAKE_SECONDS)
        lowered = answer.lower()
        if any(word in lowered for word in TAKEN):
            return True
        if any(word in lowered for word in NO_LINK) and attempt == 0:
            exchange(
                s, f"touch {patient}", ("vitality", "nothing wrong"), TOUCH_SECONDS
            )
            continue
        first = (answer.strip().splitlines() or ["(silence)"])[-1]
        s.echo(f"empath: {command} answered {first!r} — on to the next")
        return False
    return False


def heal_other(s, patient):
    """The rounds of TOUCH and TAKE until the patient reads clean. True
    when they do."""
    for round_ in range(1, ROUNDS + 1):
        injuries = touch(s, patient)
        if injuries is None:
            return False
        if not injuries:
            s.echo(f"empath: {patient.capitalize()} has no injuries left")
            return True
        order = transfer_order(injuries)
        worst = order[0]
        s.echo(
            f"empath: round {round_} — {len(order)} wound(s) on {patient.capitalize()}, "
            f"worst {worst.part} {worst.kind.replace('_', ' ')} (level {worst.level})"
        )
        for injury in order:
            if s.dead or wants_stop(s):
                s.echo("empath: stopping as asked")
                return False
            take(s, patient, injury)
    s.echo(
        f"empath: {ROUNDS} rounds and {patient} still reads hurt — TOUCH them to see"
    )
    return False


def mana(s):
    vitals = getattr(s.state, "vitals", None) or {}
    value = vitals.get("mana") if isinstance(vitals, dict) else None
    return 100 if value is None else value


def cast(s, spell, target, amount):
    """PREPARE the spell, wait for the pattern, CAST at the target; the
    answer."""
    exchange(s, f"prepare {spell} {amount}", PREPARED, PREPARE_SECONDS)
    answer = ask(s, f"cast {target}")
    s.waitrt()
    return answer


def heal_self(s, amount):
    """Heal Wounds and Heal Scars, worst first, until HEALTH reads clean.
    True when it does."""
    for count in range(MAX_CASTS):
        if s.dead or wants_stop(s):
            s.echo("empath: stopping as asked")
            return False
        casts = heal_casts(parse_health(ask(s, "health")))
        if not casts:
            s.echo(f"empath: healed — {count} cast(s)")
            return True
        if mana(s) < MANA_FLOOR:
            s.echo(
                f"empath: mana below {MANA_FLOOR}% — {len(casts)} cast(s) still owed"
            )
            return False
        spell, target = casts[0]
        answer = cast(s, spell, target, amount)
        if not any(word in answer.lower() for word in HEALED + ("improved", "better")):
            first = (answer.strip().splitlines() or ["(silence)"])[-1]
            s.echo(f"empath: CAST {target} answered {first!r}")
    s.echo(f"empath: {MAX_CASTS} casts and still hurt — HEALTH shows what is left")
    return False


def parse_words(words):
    """(patient, take_only, amount) from ;empath's words."""
    patient, take_only, amount = "", False, DEFAULT_MANA
    for word in words:
        lowered = word.lower()
        if lowered.startswith("mana=") and lowered[5:].isdigit():
            amount = int(lowered[5:])
        elif lowered == "take":
            take_only = True
        elif not patient:
            patient = lowered
    return patient, take_only, amount


def run(s, words):
    patient, take_only, amount = parse_words(words)
    if not patient:
        s.echo("empath: whom? — ;empath <patient>, or ;empath self")
        return
    if patient != "self":
        heal_other(s, patient)
        if take_only or s.dead or wants_stop(s):
            return
    heal_self(s, amount)


def main(s):
    run(s, list(s.args))
