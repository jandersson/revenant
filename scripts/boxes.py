"""Train Locksmithing on the boxes the hunt brought home:  ;boxes

    ;boxes                      every box in the loot container: disarmed, picked, opened, emptied
    ;boxes source=backpack      the boxes wait in that container instead of the profile's loot_container
    ;boxes careful              every DISARM and PICK careful, whatever the reading says
    ;boxes stand                stay standing (the script sits, which helps)
    ;boxes limit=3              stop after that many boxes opened
    ;boxes until=30             stop at that mindstate instead of 34
    ;boxes once                 exit at mind-lock instead of holding for the drain
    ;boxes safe                 put back every box past "longshot", nuisance traps and locks included
    ;boxes return               (typed while it runs) finish the box in hand and end

Every DISARM and PICK teaches Locksmithing (Elanthipedia: Locksmithing
skill, Disarm command, Pick command; client/game/boxes.py is the model,
after dr-scripts' pick.lic, which pops boxes the same way). A box at a
time out of the container (GET <box> FROM MY <container>, the next of
its noun by ordinal when one was put back): DISARM MY <box> IDENTIFY
reads the trap's difficulty, and a reading of "longshot" or worse is a
box for a better locksmith, back into the container at once — an
identify of a trap already read comes back with no roundtime and
teaches nothing (2026-09-23: eighty of them in forty seconds left
Locksmithing at 0/34; the 0/34 to 2/34 of the first run was the one
careful DISARM), so the boxes a low rank trains on are boxes it can
read as its own, from lower creatures — unless the trap's look is a
nuisance trap (Elanthipedia: Box traps: frog, laughing gas, mime,
shadowling, sleeper, mana sucker, bouncing box — a toad or a joke,
never a wound), which gets a careful try whatever it reads: at rank 3
every box from the Crossing's grendels read 11 and up (2026-09-25),
so the risk is the only way in. A deadly trap or a look not recognized
goes back; the laughing gas catches the whole room, so it waits for a
room with no other player in it; `safe` puts back every box past the
threshold. Else DISARM MY <box> <caution> —
quick, plain or careful by the reading, pick.lic's thresholds — until
the trap is down, up to five tries; then PICK MY <box> IDENTIFY and
PICK MY <box> <caution> the same way — a lock past the threshold
tried careful anyway, since a failed pick risks the pick, not the
locksmith — with the profile's `lockpick` in
the free hand (GOT from wherever it is kept, STOWed after) or the
worn `lockpick_ring`, whose top pick the game takes by itself; OPEN,
LOOK IN, and every item out — coins to the purse, a gem into the
profile's `gem_pouch`, the rest into the loot container — and the empty
box into the room's bucket through client/game/discard.py, which only
takes a noun settings.json's `droppable` lists (box, coffer, chest...);
a box not on the list goes back into the container and is said. It sits
first (the wiki: kneeling or sitting helps) and stands at the end.
Armor and brawling gear on the hands hinder every attempt ("Your brass
knuckles hinders your attempt.", captured 2026-09-23): each noun in the
profile's `hindering_gear` (knuckles, gauntlets) is REMOVEd and stowed
before the first box — judged by the piece landing in a hand, whatever
the game says — and GOT and worn back when the run ends, however it
ends; a piece that would not come off or go back on is said. Whatever
still hinders after that is said once.

A sprung trap is said with its line; the stun is waited out (up to
five minutes; "You are still stunned." to any step meanwhile is a
wait, not a try — the laughing gas outlasted the old thirty seconds
and the run skipped every box, 2026-09-25), a box knocked to the floor
is picked back up and a prone character sits up again, and a
health below the profile's `health_floor` or a wound at its
`wound_floor` (HEALTH, the hunt's floor) ends the run so ;heal can
run. "You're in no shape to be disarming anything" ends it too. A
broken lockpick is said; with a ring the next pick is the game's to
take, without one the script GETs another and stops when there is none.
The mindstate is the exp window's; at mind-lock the script holds until
Locksmithing drains below 28, then goes on (`once` exits at the lock);
an empty container ends the run. ;train runs it as a task (skills:
["Locksmithing"], script "boxes", return_word "return") after the hunt
and the skins. It stops on death and on hostiles in the room.
The wordings are pick.lic's and the wiki's until captured (2026-09-23):
the first answer of each kind in a run is echoed as
"boxes: <command> answered ..." so they become fixtures — report them.
Stop with:  ;stop boxes, or ;boxes return.
"""

from client.engine.scripting import ScriptStopped
from client.game import discard, flight, probe
from client.game import boxes as boxes_model
from client.game.boxes import (
    DISARM_OUTCOMES,
    LOCK_CAUTION,
    LOCK_READINGS,
    OPEN_OUTCOMES,
    PICK_OUTCOMES,
    SKILL,
    TAKE_OUTCOMES,
    TOO_HARD,
    TRAP_CAUTION,
    TRAP_READINGS,
    boxes_in,
    caution,
    listed,
    parse_args,
    reading,
)
from client.game.creatures import noun_of, phrase
from client.game.loop import danger, ensure_mindstate, mindstate, pause, wants_stop
from client.game.loot import GEM_NOUNS
from client.game.probe import classify
from client.game.wounds import level, parse_health

# A session started before client/game/boxes.py joined RELOADABLE_MODULES
# keeps the copy it first imported (2026-09-23: the loop's first boxes
# task failed on "cannot import name 'HINDERED'" until the relaunch);
# the constants added since are read with a fallback.
HINDERED = getattr(boxes_model, "HINDERED", ("hinders your attempt",))
WORN = getattr(boxes_model, "WORN", ("onto your hands", "you slip", "you slide"))


NUISANCE_TRAPS = getattr(boxes_model, "NUISANCE_TRAPS", ())


def nuisance_trap(answer):
    reader = getattr(boxes_model, "nuisance_trap", None)
    return reader(answer) if reader is not None else None


def hindering_gear(profile):
    reader = getattr(boxes_model, "hindering_gear", None)
    if reader is not None:
        return reader(profile)
    return [str(item).strip().lower() for item in profile.get("hindering_gear") or []]


MIND_LOCK = 34
RESUME_BELOW = 28
LOCK_POLL = 30
COLLECT_SECONDS = 3
TAIL_SECONDS = 0.5
IDENTIFY_TRIES = 3
WORK_TRIES = 5
MAX_BOXES = 200  # the fuse under the loop
DEFAULT_WOUND_FLOOR = "harmful"


def ask(s, command):
    """The game's answer to one command, raw (the parser cares about
    case for HEALTH)."""
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


class Run:
    """One run's state: the profile, the container, the boxes put back,
    the answers echoed once."""

    def __init__(self, s, profile, options):
        self.s = s
        self.profile = profile
        self.options = options
        self.container = options["source"] or profile.get("loot_container") or ""
        self.kept = {}  # noun -> boxes put back into the container
        self.reported = set()
        self.opened = 0
        self.pick_in_hand = False
        self.doffed = []  # the hindering gear taken off, in order

    def say(self, text):
        self.s.echo(f"boxes: {text}")

    def report(self, kind, command, answer):
        """Echo a run's first answer of each kind, for the fixtures."""
        if kind in self.reported:
            return
        self.reported.add(kind)
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        self.say(f"{command} answered {first!r}")


def hindrance(run, answer):
    """The gear hindering the attempt, said once a run: "Your armor
    hinders your attempt." / "Your brass knuckles hinders your attempt."
    (captured 2026-09-23) — the operator can take it off."""
    if "hindered" in run.reported:
        return
    lines = [
        line.strip()
        for line in answer.splitlines()
        if any(word in line.lower() for word in HINDERED)
    ]
    if lines:
        run.reported.add("hindered")
        run.say(f"{' '.join(lines)} — remove it for better odds")


def in_hand(s, noun):
    """Whether the parser's hand state shows the noun in either hand."""
    return any(
        (getattr(s.state, side, None) or {}).get("noun") == noun
        for side in ("left_hand", "right_hand")
    )


def doff(run):
    """The profile's hindering gear off and stowed before the first box:
    REMOVE MY <noun>, judged by the piece landing in a hand (REMOVE's
    wordings are uncaptured, 2026-09-23), then STOW; a piece that stays
    on is said with the game's line and left."""
    s = run.s
    for noun in hindering_gear(run.profile):
        free_other_hand(run, "")
        answer = ask(s, f"remove my {noun}")
        s.waitrt()
        if not in_hand(s, noun):
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            run.say(f"the {noun} did not come off — {first!r}")
            continue
        ask(s, f"stow my {noun}")
        run.doffed.append(noun)
    if run.doffed:
        run.say(f"off and stowed: {', '.join(run.doffed)} — worn back at the end")


def don(run):
    """The gear taken off worn back, last off first: GET MY <noun>, WEAR
    MY <noun>; a piece that will not go on is stowed and said. After a
    `;stop boxes` every read raises, so the rest goes out blind as
    cleanup puts — the gear is never left in the sack."""
    s = run.s
    run.donning = None
    try:
        don_reading(run)
    except ScriptStopped:
        # The piece in flight too (2026-09-23: the gauntlets stayed in
        # the backpack after a `;stop` caught the read on their GET).
        pending = ([run.donning] if run.donning else []) + list(reversed(run.doffed))
        for noun in pending:
            s.put(f"get my {noun}", cleanup=True)
            s.put(f"wear my {noun}", cleanup=True)
        run.doffed = []
        raise


def don_reading(run):
    s = run.s
    worn = []
    while run.doffed:
        noun = run.doffed.pop()
        run.donning = noun
        free_other_hand(run, "")
        ask(s, f"get my {noun}")
        if not in_hand(s, noun):
            run.say(f"the {noun} is nowhere to be worn back — please look for it")
            continue
        answer = ask(s, f"wear my {noun}")
        s.waitrt()
        if in_hand(s, noun):
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            run.say(f"the {noun} would not go back on — {first!r} — stowed instead")
            ask(s, f"stow my {noun}")
            continue
        if not any(word in answer.lower() for word in WORN):
            run.report("wear", f"wear my {noun}", answer)  # a new wording
        worn.append(noun)
    run.donning = None
    if worn:
        run.say(f"worn back: {', '.join(worn)}")


def wound_floor(profile):
    floor = str(profile.get("wound_floor") or "").strip().lower()
    if floor == "off":
        return ""
    return floor or DEFAULT_WOUND_FLOOR


def hurt(run):
    """Why the character should stop after a sprung trap, or None: the
    health below the profile's floor, or HEALTH showing a wound at the
    profile's wound floor."""
    s = run.s
    floor = int(run.profile.get("health_floor") or 0)
    health = getattr(getattr(s, "status", None), "health", None)
    if floor and health is not None and health < floor:
        return f"health {health}% below the floor of {floor}%"
    name = wound_floor(run.profile)
    if not name:
        return None
    try:
        wanted = level(name)
    except ValueError:
        return None
    panel = getattr(s.state, "injuries", None)
    if isinstance(panel, dict) and not panel:
        return None
    health_answer = parse_health(ask(s, "health"))
    hits = health_answer.at_least(wanted)
    if hits:
        area, kind, severity = max(hits, key=lambda hit: hit[2])
        return f"{kind} {area} wound at {severity} — the wound floor is {name}"
    return None


STUN_WAIT = 300  # seconds a sprung trap's stun is waited out at most


def wait_stun(run):
    """A sprung trap's stun waited out, a second at a time — up to five
    minutes: the laughing gas held Lanival past the thirty seconds this
    once waited, and every DISARM after answered "You are still
    stunned." until the boxes were all skipped (2026-09-25)."""
    s = run.s
    for _ in range(STUN_WAIT):
        if not getattr(getattr(s, "status", None), "stunned", False):
            return
        s.sleep(1)


def recover(run, noun):
    """After a sprung trap: the box back in hand if it left it — the
    laughing gas put the skippet on the floor (2026-09-25: "You also see
    a cracked ironwood skippet", and the put-back that followed left it
    there) — and the character back off the floor."""
    s = run.s
    if noun and not in_hand(s, noun):
        objs = str(getattr(s.state, "room_objs", "") or "").lower()
        if noun.lower() in objs:
            ask(s, f"get {noun}")
            s.waitrt()
            run.say(f"the {noun} was knocked to the floor — picked back up")
    posture = getattr(getattr(s, "status", None), "posture", None)
    if posture == "prone":
        ask(s, "stand" if run.options.get("stand") else "sit")
        s.waitrt()


def sprung(run, answer, noun=""):
    """A trap went off: said, the stun waited out, the roundtime too,
    the box picked back up; the reason to stop, or None."""
    first = (answer.strip().splitlines() or ["(silence)"])[0]
    run.say(f"a trap sprung — {first!r}")
    run.s.waitrt()
    wait_stun(run)
    recover(run, noun)
    return hurt(run)


def sit(run):
    if run.options["stand"]:
        return
    ask(run.s, "sit")


def stand(run):
    ask(run.s, "stand")


def ready_pick(run):
    """A lockpick in hand when the profile keeps no ring; True when the
    game has one to pick with."""
    profile = run.profile
    if profile.get("lockpick_ring"):
        return True
    if run.pick_in_hand:
        return True
    noun = profile.get("lockpick") or "lockpick"
    answer = ask(run.s, f"get my {noun}")
    lowered = answer.lower()
    if "referring" in lowered or "get what" in lowered:
        run.say(
            f"no {noun} to pick with — Ragge's Locksmithing in the Crossing sells them"
        )
        return False
    run.pick_in_hand = True
    return True


def put_pick_away(run):
    if run.pick_in_hand:
        ask(run.s, f"stow my {run.profile.get('lockpick') or 'lockpick'}")
        run.pick_in_hand = False


def free_other_hand(run, noun):
    """PICK wants the box in one hand and the other empty (or the pick
    in it): whatever else a hand holds, as the parser knows it, is
    stowed by side."""
    s = run.s
    pick_noun = run.profile.get("lockpick") or "lockpick"
    for side in ("left", "right"):
        held = getattr(s.state, f"{side}_hand", None)
        thing = held.get("noun") if isinstance(held, dict) else None
        if thing and thing not in (noun, pick_noun):
            ask(s, f"stow {side}")


def take_box(run, noun):
    """GET the next box of a noun out of the container — past the ones
    put back this run — True when it landed in a hand."""
    which = phrase(noun, run.kept.get(noun, 0) + 1)
    answer = ask(run.s, f"get {which} from my {run.container}")
    run.report("get", f"get {which}", answer)
    lowered = answer.lower()
    return not any(word in lowered for word in ("referring", "get what", "can't"))


def put_back(run, noun, why):
    """The box in hand back into the container, remembered so the next
    GET passes it."""
    ask(run.s, f"put my {noun} in my {run.container}")
    run.kept[noun] = run.kept.get(noun, 0) + 1
    run.say(f"the {noun} goes back into the {run.container} — {why}")


def risk_trap(run, noun, rank, answer):
    """The caution for a trap past TOO_HARD: "careful" when its look is
    a nuisance trap (a toad, jokes, a nap) and the run takes the risk,
    else None, said — a deadly or unknown trap, `safe`, or a trap that
    hits the whole room while another player stands in it."""
    trap = None if run.options.get("safe") else nuisance_trap(answer)
    if trap is None:
        run.say(f"the {noun}'s trap reads {rank}/17 — past {TOO_HARD}, too hard")
        return None
    name, area = trap
    players = list(getattr(run.s.state, "room_players", None) or [])
    if area and players:
        run.say(
            f"the {noun}'s {name} trap would catch {', '.join(players)} too — "
            "left for an empty room"
        )
        return None
    run.say(
        f"the {noun}'s trap reads {rank}/17 — a {name} trap, a nuisance at worst: "
        "trying careful"
    )
    return "careful"


def disarm(run, noun):
    """The traps off a box: "clear", "too hard", "stop:<why>" or
    "lost"."""
    s = run.s
    for _round in range(WORK_TRIES):
        rank = None
        for _ in range(IDENTIFY_TRIES):
            answer = ask(s, f"disarm my {noun} identify")
            s.waitrt()
            run.report("disarm identify", "disarm identify", answer)
            hindrance(run, answer)
            outcome = classify(answer, DISARM_OUTCOMES)
            if outcome == "sprung":
                why = sprung(run, answer, noun)
                if why:
                    return f"stop:{why}"
                continue
            if outcome == "stunned":
                wait_stun(run)  # nothing was tried: wait, take the step again
                recover(run, noun)
                continue
            if outcome == "injured":
                return "stop:too hurt to disarm anything"
            if outcome == "lost":
                return "lost"
            if outcome == "no trap":
                return "clear"
            rank = reading(answer, TRAP_READINGS)
            if rank is not None:
                break
            if outcome != "identify failed":
                run.report("disarm identify?", "disarm identify (unrecognized)", answer)
        if rank is None:
            run.say(f"the {noun}'s trap would not identify — treating it as careful")
            word = "careful"
        else:
            word = caution(rank, TRAP_CAUTION)
            if word is None:
                word = risk_trap(run, noun, rank, answer)
                if word is None:
                    return "too hard"
        if run.options["careful"]:
            word = "careful"
        command = f"disarm my {noun} {word}".strip()
        answer = ask(s, command)
        s.waitrt()
        run.report("disarm", "disarm", answer)
        hindrance(run, answer)
        outcome = classify(answer, DISARM_OUTCOMES)
        if outcome == "sprung":
            why = sprung(run, answer, noun)
            if why:
                return f"stop:{why}"
            continue
        if outcome == "stunned":
            wait_stun(run)  # nothing was tried: wait, take the step again
            recover(run, noun)
            continue
        if outcome == "injured":
            return "stop:too hurt to disarm anything"
        if outcome == "lost":
            return "lost"
        if outcome in ("disarmed", "no trap"):
            run.say(f"the {noun}'s trap is down ({word or 'plain'}, read {rank}/17)")
            continue  # IDENTIFY again: another trap, or none
        if outcome in ("retry", "identify failed"):
            # "identify failed" here is the shift line after a failed
            # attempt ("your manipulation caused something to shift",
            # 2026-09-23) — the trap moved, and the next IDENTIFY reads
            # it again, harder (10/17 to 11/17 that night).
            continue
        run.report("disarm?", "disarm (unrecognized)", answer)
    return "too hard"


def pick(run, noun):
    """The locks off a box: "open", "too hard", "stop:<why>" or
    "lost"."""
    s = run.s
    for _round in range(WORK_TRIES):
        if not ready_pick(run):
            return "stop:no lockpick"
        rank = None
        for _ in range(IDENTIFY_TRIES):
            answer = ask(s, f"pick my {noun} identify")
            s.waitrt()
            run.report("pick identify", "pick identify", answer)
            hindrance(run, answer)
            outcome = classify(answer, PICK_OUTCOMES)
            if outcome == "sprung":
                why = sprung(run, answer, noun)
                if why:
                    return f"stop:{why}"
                continue
            if outcome == "stunned":
                wait_stun(run)  # nothing was tried: wait, take the step again
                recover(run, noun)
                continue
            if outcome == "injured":
                return "stop:too hurt to pick anything"
            if outcome == "lost":
                return "lost"
            if outcome == "not locked":
                return "open"
            if outcome == "wrong pick":
                run.say(f"the {noun}'s lock wants another kind of lockpick — left")
                return "too hard"
            if outcome == "free hand":
                free_other_hand(run, noun)
                continue
            rank = reading(answer, LOCK_READINGS)
            if rank is not None:
                break
        if rank is None:
            run.say(f"the {noun}'s lock would not identify — treating it as careful")
            word = "careful"
        else:
            word = caution(rank, LOCK_CAUTION)
            if word is None:
                if run.options.get("safe"):
                    run.say(
                        f"the {noun}'s lock reads {rank}/17 — past {TOO_HARD}, too hard"
                    )
                    return "too hard"
                # A lock has no trap: a failed pick costs roundtime and
                # now and then the pick, never a wound.
                run.say(
                    f"the {noun}'s lock reads {rank}/17 — past {TOO_HARD}, "
                    "trying careful anyway (a lock only risks the pick)"
                )
                word = "careful"
        if run.options["careful"]:
            word = "careful"
        command = f"pick my {noun} {word}".strip()
        answer = ask(s, command)
        s.waitrt()
        run.report("pick", "pick", answer)
        hindrance(run, answer)
        outcome = classify(answer, PICK_OUTCOMES)
        if outcome == "sprung":
            why = sprung(run, answer, noun)
            if why:
                return f"stop:{why}"
            continue
        if outcome == "stunned":
            wait_stun(run)  # nothing was tried: wait, take the step again
            recover(run, noun)
            continue
        if outcome == "injured":
            return "stop:too hurt to pick anything"
        if outcome == "lost":
            return "lost"
        if outcome in ("unlocked", "not locked"):
            run.say(f"the {noun} is unlocked ({word or 'plain'}, read {rank}/17)")
            return "open"
        if outcome == "more locks":
            continue
        if outcome == "wrong pick":
            run.say(f"the {noun}'s lock wants another kind of lockpick — left")
            return "too hard"
        if outcome == "broken pick":
            run.pick_in_hand = False
            run.say("the lockpick broke")
            continue
        if outcome == "no pick":
            run.pick_in_hand = False
            if not ready_pick(run):
                return "stop:no lockpick"
            continue
        if outcome == "retry":
            continue
        run.report("pick?", "pick (unrecognized)", answer)
    return "too hard"


def stow_loot(run, item):
    """An item out of the box into the pouch (a gem) or the container."""
    s = run.s
    noun = noun_of(item)
    pouch = run.profile.get("gem_pouch")
    if pouch and noun in GEM_NOUNS:
        answer = ask(s, f"put my {noun} in my {pouch}")
        if "can't" not in answer.lower() and "cannot" not in answer.lower():
            return
    if run.container:
        answer = ask(s, f"put my {noun} in my {run.container}")
        if "room" not in answer.lower() and "can't" not in answer.lower():
            return
    ask(s, f"stow my {noun}")


def empty(run, noun):
    """OPEN the box, LOOK IN it, GET everything out; the count taken."""
    s = run.s
    answer = ask(s, f"open my {noun}")
    run.report("open", "open", answer)
    outcome = classify(answer, OPEN_OUTCOMES)
    if outcome == "locked":
        run.say(f"the {noun} is still locked — left as it is")
        return None
    if outcome == "lost":
        return None
    items = listed(answer)
    if items is None:
        answer = ask(s, f"look in my {noun}")
        run.report("look in", "look in", answer)
        items = listed(answer) or []
    taken = 0
    for item in items:
        thing = noun_of(item)
        if thing in ("stuff",):
            continue
        answer = ask(s, f"get {thing} from my {noun}")
        run.report("take", "get from box", answer)
        outcome = classify(answer, TAKE_OUTCOMES)
        if outcome == "free hand":
            put_pick_away(run)
            answer = ask(s, f"get {thing} from my {noun}")
            outcome = classify(answer, TAKE_OUTCOMES)
        if outcome == "coins":
            taken += 1
            continue
        if outcome == "taken":
            stow_loot(run, item)
            taken += 1
            continue
        if outcome == "no room":
            run.say(f"no room for the {thing} — it stays in the {noun}")
            ask(s, f"put my {thing} in my {noun}")
            continue
    return taken


def dispose(run, noun):
    """The emptied box into the room's bucket through discard.drop —
    only a noun on the droppable list — else back into the container."""
    s = run.s
    if discard.droppable(noun):
        answer = discard.drop(s, noun, lambda handle, command: ask(handle, command))
        if answer is not None:
            return True
    put_back(run, noun, "empty, but not on settings.json's droppable list")
    return False


def hold_at_lock(run, until):
    s = run.s
    run.say(f"{SKILL} mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        value = mindstate(s, SKILL)
        if value is not None and value <= floor:
            run.say(f"drained to {value}/34 — picking again")
            return True


def kept(run, noun):
    """A box past the reading, back into the container: "kept". No
    practising on it — an identify of a trap already read is free of
    roundtime and of experience (2026-09-23: eighty in forty seconds,
    Locksmithing unmoved), and a DISARM past the reading is the trap
    sprung, not the skill trained."""
    put_back(run, noun, "for a better locksmith")
    return "kept"


def one_box(run, noun):
    """One box out, worked and away: "done", "kept", "lost" or
    "stop:<why>"."""
    if not take_box(run, noun):
        return "lost"
    outcome = disarm(run, noun)
    if outcome.startswith("stop:"):
        put_back(run, noun, "the run ends")
        return outcome
    if outcome == "lost":
        return "lost"
    if outcome == "too hard":
        return kept(run, noun)
    outcome = pick(run, noun)
    if outcome.startswith("stop:"):
        put_back(run, noun, "the run ends")
        return outcome
    if outcome == "lost":
        return "lost"
    if outcome == "too hard":
        return kept(run, noun)
    put_pick_away(run)
    taken = empty(run, noun)
    if taken is None:
        put_back(run, noun, "it would not open")
        return "kept"
    run.opened += 1
    run.say(f"the {noun} opened — {taken} item(s) out ({run.opened} box(es) so far)")
    dispose(run, noun)
    return "done"


def run_loop(s, profile, options):
    run = Run(s, profile, options)
    if not run.container:
        run.say("no container — source=<container>, or the profile's loot_container")
        return
    value = ensure_mindstate(s, SKILL, lambda handle, command: ask(handle, command))
    if value is None:
        run.say(f"EXP shows no {SKILL} — nothing to train")
        return
    answer = ask(s, f"look in my {run.container}")
    run.report("look in container", f"look in my {run.container}", answer)
    nouns = boxes_in(answer)
    if nouns is None:
        run.say(f"cannot read the {run.container} — is it worn or held, and open?")
        return
    if not nouns:
        run.say(f"no boxes in the {run.container} — nothing to pick")
        return
    run.say(f"{len(nouns)} box(es) in the {run.container} — {SKILL} {value}/34")
    try:
        doff(run)
        sit(run)
        for noun in nouns[:MAX_BOXES]:
            reason = danger(s)
            if reason:
                run.say(f"{reason} — stopping")
                if "hostiles" in reason:
                    stand(run)
                    flight.react(s, "boxes")
                return
            if wants_stop(s):
                run.say("stopping as asked")
                return
            value = mindstate(s, SKILL)
            if value is not None and value >= options["until"]:
                if options["once"]:
                    run.say(f"{SKILL} at {value}/34 — done")
                    return
                if not hold_at_lock(run, options["until"]):
                    run.say("stopping")
                    return
            outcome = one_box(run, noun)
            if outcome.startswith("stop:"):
                why = outcome[5:]
                run.say(f"{why} — stopping")
                if "hostiles" in why:
                    stand(run)
                    flight.react(s, "boxes")
                return
            if outcome == "lost":
                run.say(f"the {noun} is nowhere — on to the next")
            if options["limit"] and run.opened >= options["limit"]:
                run.say(f"{run.opened} box(es) opened — the limit")
                return
        run.say(
            f"every box tried — {run.opened} opened, "
            f"{sum(run.kept.values())} kept for a better locksmith"
        )
    finally:
        put_pick_away(run)
        don(run)
        stand(run)


def main(s):
    name = getattr(s.state, "name", None)
    from client.game.profile import load_profile

    profile = load_profile(name) if name else {}
    run_loop(s, profile, parse_args(s.args or []))
