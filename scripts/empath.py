"""Heal another as an Empath, then yourself:  ;empath <patient>

    ;empath <patient>          TOUCH them, TAKE every wound most urgent first, touch again for what that bared, then heal yourself
    ;empath <patient> take     the transfers only, no self-heal after
    ;empath <patient> parts    one TAKE per wound instead of TAKE EVERYTHING
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
below a fifth. Each round opens with TAKE <patient> EVERYTHING, every wound and scar
in one transfer (Elanthipedia: Empath healing, a skilled Empath's
form), read until the lines stop coming; whatever the next TOUCH
still lists, or all of it when EVERYTHING brings nothing over (its
answer is said, uncaptured until then), is taken one part at a time.
The game's warning that a transfer would kill the Empath ("You
realize that you are taking a wound that will kill you if you finish
the transfer", the wiki's wording) ends the heal at once.
Poison and disease go first (TOUCH's lines read with lich-5's
common-healing.rb patterns): TAKE <patient> POISON and TAKE
<patient> DISEASE, and only when the Empath's own spell list (as
;sheet recorded it) has Flush Poisons or Cure Disease to cure himself
after — the self-heal casts those before any wound.
Nothing is ever taken without the patient in the room:
a TOUCH that finds nobody, or is avoided (a cold demeanor), ends it.
Stop with:  ;stop empath, or ;empath return.
"""

import time

from client.game import buffs, probe
from client.game.empathy import (
    AVOIDED,
    CURES,
    HEALED,
    LINKED,
    NO_LINK,
    PREPARED,
    TAKEN,
    afflictions,
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
EVERYTHING_QUIET = 45  # seconds without a line that end TAKE EVERYTHING's reading
EVERYTHING_SECONDS = 600  # the whole transfer, however many parts
# The link broken because the transfer would kill the Empath
# (Elanthipedia: Empath healing), uncaptured.
FATAL = ("will kill you if you finish",)
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
    """TOUCH the patient: (the Injury list, the afflictions), or None
    (said) when there was no link — nobody by that name, or a touch
    avoided."""
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
    return injuries, afflictions(answer)


def take_everything(s, patient):
    """TAKE <patient> EVERYTHING, read until EVERYTHING_QUIET seconds pass
    without a line: the number of parts that came over ("...fully
    healed"), "fatal" on the death warning, or 0 (its answer said) when
    nothing did."""
    while s.get(timeout=0, streams=STREAMS) is not None:
        pass
    s.put(f"take {patient} everything")
    lines, healed = [], 0
    now = time.monotonic()
    deadline, quiet = now + EVERYTHING_SECONDS, now + EVERYTHING_QUIET
    while time.monotonic() < min(deadline, quiet):
        piece = s.get(timeout=0.5, streams=STREAMS)
        if piece is None:
            continue
        text = piece[1] if isinstance(piece, tuple) else piece
        lines.append(text)
        quiet = time.monotonic() + EVERYTHING_QUIET
        lowered = text.lower()
        if any(word in lowered for word in FATAL):
            s.echo(f"empath: {text.strip()} — the heal stops here")
            return "fatal"
        healed += sum(lowered.count(word) for word in TAKEN)
    if not healed:
        first = ("".join(lines).strip().splitlines() or ["(silence)"])[-1]
        s.echo(f"empath: TAKE EVERYTHING answered {first!r} — one part at a time")
    return healed


def take(s, patient, injury):
    """One transfer, the link renewed once if it had lapsed. True when
    the wound came over, "fatal" on the death warning."""
    command = take_command(patient, injury)
    for attempt in range(2):
        answer = exchange(
            s, command, TAKEN + NO_LINK + FATAL + ("cannot",), TAKE_SECONDS
        )
        lowered = answer.lower()
        if any(word in lowered for word in FATAL):
            s.echo(f"empath: {command} would kill you — the heal stops here")
            return "fatal"
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


def take_affliction(s, patient, kind):
    """TAKE <patient> POISON or DISEASE, when the Empath knows the spell
    that cures it after; True when sent, "fatal" on the death warning."""
    spell, _, _ = CURES[kind]
    if not buffs.abbreviation(getattr(s.state, "name", None), spell):
        s.echo(
            f"empath: {patient.capitalize()} has {kind} — {spell} is not among "
            "your recorded spells (;sheet records them), so it is left"
        )
        return False
    answer = exchange(
        s,
        f"take {patient} {kind}",
        TAKEN + NO_LINK + FATAL + ("cannot",),
        TAKE_SECONDS,
    )
    if any(word in answer.lower() for word in FATAL):
        s.echo(f"empath: TAKE {kind.upper()} would kill you — the heal stops here")
        return "fatal"
    last = (answer.strip().splitlines() or ["(silence)"])[-1]
    s.echo(f"empath: TAKE {kind.upper()} answered {last!r}")
    return True


def heal_other(s, patient, everything=True):
    """The rounds of TOUCH and TAKE until the patient reads clean: TAKE
    EVERYTHING first in each round (unless `everything` is off), one
    part at a time when it brought nothing. True when clean."""
    for round_ in range(1, ROUNDS + 1):
        listing = touch(s, patient)
        if listing is None:
            return False
        injuries, ails = listing
        for kind in ails:
            if take_affliction(s, patient, kind) == "fatal":
                return False
        if not injuries and not ails:
            s.echo(f"empath: {patient.capitalize()} has no injuries left")
            return True
        if not injuries:
            continue  # the afflictions taken: the next TOUCH checks them
        order = transfer_order(injuries)
        worst = order[0]
        s.echo(
            f"empath: round {round_} — {len(order)} wound(s) on {patient.capitalize()}, "
            f"worst {worst.part} {worst.kind.replace('_', ' ')} (level {worst.level})"
        )
        if everything:
            moved = take_everything(s, patient)
            if moved == "fatal":
                return False
            if moved:
                s.echo(f"empath: TAKE EVERYTHING brought {moved} part(s) over")
                continue  # the next TOUCH says what is left
        for injury in order:
            if s.dead or wants_stop(s):
                s.echo("empath: stopping as asked")
                return False
            if take(s, patient, injury) == "fatal":
                return False
    # The last round's transfers checked too: it may have cleared them.
    if touch(s, patient) == ([], []):
        s.echo(f"empath: {patient.capitalize()} has no injuries left")
        return True
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
    answer = ask(s, f"cast {target}".rstrip())
    s.waitrt()
    return answer


def cure(s, kind, amount):
    """Flush Poisons or Cure Disease cast on yourself; True when the
    answer says it took."""
    spell, abbrev, done = CURES[kind]
    answer = cast(s, abbrev, "", amount)
    if any(word in answer.lower() for word in done):
        s.echo(f"empath: {spell} cast — the {kind} is gone")
        return True
    last = (answer.strip().splitlines() or ["(silence)"])[-1]
    s.echo(f"empath: {spell} answered {last!r}")
    return False


def heal_self(s, amount):
    """Heal Wounds and Heal Scars, worst first, until HEALTH reads clean.
    True when it does."""
    cured = set()
    for count in range(MAX_CASTS):
        if s.dead or wants_stop(s):
            s.echo("empath: stopping as asked")
            return False
        answer = ask(s, "health")
        ails = [kind for kind in afflictions(answer, own=True) if kind not in cured]
        if ails:
            if mana(s) < MANA_FLOOR:
                s.echo(f"empath: mana below {MANA_FLOOR}% — {', '.join(ails)} left")
                return False
            cure(s, ails[0], amount)
            cured.add(ails[0])  # one cast each: a second is the operator's call
            continue
        casts = heal_casts(parse_health(answer))
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
    """(patient, take_only, amount, everything) from ;empath's words."""
    patient, take_only, amount, everything = "", False, DEFAULT_MANA, True
    for word in words:
        lowered = word.lower()
        if lowered.startswith("mana=") and lowered[5:].isdigit():
            amount = int(lowered[5:])
        elif lowered == "take":
            take_only = True
        elif lowered == "parts":
            everything = False
        elif not patient:
            patient = lowered
    return patient, take_only, amount, everything


def run(s, words):
    patient, take_only, amount, everything = parse_words(words)
    if not patient:
        s.echo("empath: whom? — ;empath <patient>, or ;empath self")
        return
    if patient != "self":
        heal_other(s, patient, everything)
        if take_only or s.dead or wants_stop(s):
            return
    heal_self(s, amount)


def main(s):
    run(s, list(s.args))
