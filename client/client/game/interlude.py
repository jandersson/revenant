"""Interludes — short chores any running script does at its next safe
point: the almanac on its timer, and the loot sweep beside a bin
(client/game/sweep.py; `;break sweep` is its dry run). `loop.wants_stop()` (every trainer
calls it between steps) and `pause()`'s slices run them, so every
script with a safe point gives them time without code of its own;
;train runs them between tasks and in rests, ;hunt in a clear room.

due(s)          the names run_due would run now, nothing sent — a climb
                practice sends STOP CLIMB first for one (#417)
run_due(s)      every interlude due now, run on `s`'s thread; quiet when
                none is. A hand is made for it when both are full: the
                left hand's item STOWed, the chore run, the item got back.
post(name)      a one-shot request — `;break almanac` — honored at the
                next safe point of whichever script reaches one.
pending()       the requests not yet honored.

Never with the character dead, stunned or something hostile in the
room; never while a script started after this one runs (the child a
script waits on — ;remedies' ;forage — has the safe points); never in ;favors (the orb is in hand through the puzzles); a
script in NO_MAKE_ROOM waits for a free hand instead (;boxes: a box and
lockpick are not stowed blind). Each run echoes under the script it
interrupted: "[perform] interlude: almanac studied — Bow".
"""

import threading
import time

from client.game import almanac, hands
from client.game.act import ask  # the chores' ask; a test patches the name here

NEVER = {"favors"}
# A box and a lockpick are not stowed and got back blind (GET MY BOX may
# fetch another box); a two-handed instrument stowed ends the song.
NO_MAKE_ROOM = {"boxes", "perform"}
# The monitors never reach a safe point: with only these running, ;break
# runs the chore itself (the same set ;sentinel reads as idle).
BACKGROUND = frozenset(
    ("deathwatch", "xp", "wealth", "sheet", "beholder", "lnet")
    + ("sentinel", "antiidle", "clock", "break")
)
PROFILE_TTL = 30  # seconds a profile read serves the safe points

_NOTES = """
The operator, 2026-09-28 (#372): the almanac starts a skill every ten
minutes, and only ;train and ;hunt gave it time; seven more trainers
would each have needed a hook. Every trainer already calls
wants_stop() where "the step in hand" has just finished, so the
interludes ride that. "There's not really any interludes in some of
these like workorders?" — so a due chore makes room: ;remedies calls
wants_stop after every crush with the remedy in the mortar, and a
stowed mortar or pestle keeps its contents, as its restocks rely on.

The pending requests and the lock live in this module: a reload after
an edit gives the next script a fresh copy, so a `;break` posted into
the new copy is honored only by scripts started after the edit (the
almanac's own timer has the same caveat).
"""

_PENDING = set()
_LOCK = threading.Lock()
_PROFILE = {}  # profile file -> (read at, profile)
clock = time.monotonic  # tests replace it


def profile(character):
    from client.game.profile import load_profile, profile_path

    key = str(profile_path(character))
    read_at, stored = _PROFILE.get(key, (None, None))
    if read_at is None or clock() - read_at > PROFILE_TTL:
        stored = load_profile(character)
        _PROFILE[key] = (clock(), stored)
    return stored


def almanac_noun(s):
    character = getattr(getattr(s, "state", None), "name", None)
    if not character:
        return ""
    return str(profile(character).get("almanac") or "").strip().lower()


def _study(s, forced):
    noun = almanac_noun(s)
    if not noun:
        if forced:
            s.echo("interlude: no almanac in the profile — nothing to study")
        return None
    if forced:
        almanac._NEXT.pop(noun, None)  # asked for: the game's countdown decides
    return almanac.study(s, noun, ask, "interlude")


def _almanac_due(s):
    noun = almanac_noun(s)
    return bool(noun) and almanac.ready(noun)


def _almanac_in_hand(s):
    return almanac.hand_free(s.state, almanac_noun(s))


def _loot_profile(s):
    character = getattr(getattr(s, "state", None), "name", None)
    return profile(character) if character else {}


def _sweep_due(s):
    """The loot sweep (client/game/sweep.py, #378): on in the profile,
    the container may hold a `loot_ignore` item, and a bin stands here."""
    from client.game import discard, sweep

    loot = _loot_profile(s)
    if not loot.get("loot_sweep") or not loot.get("loot_container"):
        return False
    if not sweep.dirty():
        return False
    return bool(discard.receptacle(getattr(s.state, "room_objs", "") or ""))


def _sweep(s, forced):
    """`;break sweep` is the dry run: it names what the sweep would trash
    and moves nothing, whether the sweep is on or not."""
    from client.game import sweep

    return sweep.run(s, _loot_profile(s), ask, "sweep", dry=forced)


def _sweep_hand(s):
    if "sweep" in _PENDING:
        return True  # the dry run takes nothing in hand
    return not hands.full(s)


# name -> (due(s), run(s, forced), fits(s): True when its needs are met)
REGISTRY = {
    "almanac": (_almanac_due, _study, _almanac_in_hand),
    "sweep": (_sweep_due, _sweep, _sweep_hand),
}


def post(name):
    """A one-shot request, honored at the next safe point. False for a
    name the registry does not know."""
    name = str(name or "").strip().lower()
    if name not in REGISTRY:
        return False
    _PENDING.add(name)
    return True


def pending():
    return sorted(_PENDING)


def _safe(s):
    state = getattr(s, "state", None)
    if getattr(s, "dead", False) or state is None:
        return False
    if getattr(state, "stunned", False) or getattr(state, "hostiles", None):
        return False
    return True


def _make_room(s):
    """The left hand's item STOWed so a chore has a hand (hands.stow, the
    answer the judge): its noun, to get back, or None when the STOW was
    refused."""
    held = hands.held(s)["left"]
    if not held:
        return None
    s.waitrt()
    if not hands.stow(s, held, ask=ask):
        s.echo(f"interlude: could not stow the {held} — the chore waits")
        return None
    return held


def _restore(s, noun):
    try:
        s.waitrt()
        answer = ask(s, f"get my {noun}").lower()
    except Exception:
        # ;stop mid-chore: the item goes back to the hand all the same.
        hands.cleanup(s, f"get my {noun}")
        raise
    if not any(word in answer for word in ("you get", "you pick", "you remove")):
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"interlude: the {noun} did not come back ({first!r}) — get it by hand")


def _child_acting(s):
    """True when a script started after this one runs still, a monitor
    aside: the child it waits on is acting on the character, and a
    chore's commands would cross the child's (2026-09-28: ;remedies
    studied mid-forage, ;forage's "...wait 4 seconds." read as the
    STUDY's answer and the STUDY sent three times). The child's own
    safe points run the chores instead. A session whose handle predates
    younger_scripts() runs them as before."""
    younger = getattr(s, "younger_scripts", None)
    if younger is None:
        return False
    return any(other not in BACKGROUND for other in younger())


def due(s):
    """The interludes due at this safe point, in registry order — what
    run_due would run now, nothing sent; [] when none is, or the moment
    is not safe. A climb practice ends the activity first only for a
    chore that will run (#417)."""
    name = str(getattr(s, "name", "") or "")
    if name in NEVER or not _safe(s) or _child_acting(s):
        return []
    return [n for n in REGISTRY if n in _PENDING or REGISTRY[n][0](s)]


def run_due(s, make_room=True):
    """Every interlude due now, run on this script's thread. `make_room`
    False: only when a hand is already free (;hunt's clear room keeps
    its weapon and shield)."""
    name = str(getattr(s, "name", "") or "")
    chores = due(s)
    if not chores or not _LOCK.acquire(blocking=False):
        return  # another script's thread is in one
    try:
        for chore in chores:
            if not _safe(s):
                return
            _due, run, fits = REGISTRY[chore]
            forced = chore in _PENDING
            stowed = None
            if not fits(s):
                if not make_room or name in NO_MAKE_ROOM:
                    continue  # the next safe point
                stowed = _make_room(s)
                if stowed is None:
                    continue
            try:
                _PENDING.discard(chore)
                run(s, forced)
            finally:
                if stowed:
                    _restore(s, stowed)
    finally:
        _LOCK.release()
