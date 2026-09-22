"""Keep a Paladin's soul up and read it:  ;soul

    ;soul                     read the soul: RUB and EXHALE the orb here, else walk through the nearest soulstone arch for the state; say it
    ;soul keep                keep the boosts running on their timers — badge every 31 min, tithe every 4 h, Chadatru every 2 h — while the soul reads below pristine, until ;soul return
    ;soul tithe               one tithe of 5 silver at the nearest almsbox (the map's `tithe` rooms and the Crossing's two), then back
    ;soul pray                one prayer at the nearest Chadatru altar, knelt until it completes
    ;soul badge               one PRAY BADGE on the pilgrim's badge (REMOVE it, pray, WEAR it), wherever you stand
    ;soul quest               the Glyph of Warding scene at the guild orb once the readings say ready (FOCUS ORB, GUARD GIRL)
    ;soul quest force         FOCUS the orb whatever the readings say
    ;soul ... almsbox=ID      an almsbox room the map has not tagged;  altar=ID likewise;  currency=lirums to override the coin
    ;soul return              (typed while it runs) finish the deed in hand and end

The circle-5 glyph quest's orb wants a pristine luminescent soul and,
by the players' reports, a full soul pool; what raises the soul is on
timers (Elanthipedia: Soul system, Glyph of Warding walkthrough;
client/game/soul.py is the model). This script is those deeds, the
way dr-scripts' tithe.lic and crossing-training.lic's check_chadatru
run them inside a training loop: walk to the almsbox, PUT 5 silver of
the town's coin in it (IN BOX at the Crossing guild's steel tithe box,
whose inscription says so, IN ALMSBOX elsewhere — the noun is read off
the room's listing), walk to the altar, PRAY CHADATRU and stay
knelt until "A warm, soothing sensation washes over your soul" — and
the readings the scripts there never take: RUB for the state, EXHALE
for the pool at an orb, and where there is none — the Crossing guild
has no orb — a walk through the nearest soulstone arch (the guild's
Chambers, Shard's tower door) for the state alone, in the RUB's words
(#231). A reading is kept four hours in the timers file, and while
it says pristine no deed runs: the deeds restore a soul, they do not
maintain one, and the soul drifts slowly and never below chalky grey
on its own (Elanthipedia: Soul system; the operator, 2026-09-20). A
stale reading is taken again first. The pilgrim's badge is the third deed (2026-09-20):
REMOVE MY BADGE (it is worn; GET it when it is not), PRAY BADGE, WEAR
it again, every thirty-one minutes wherever
the character stands — "A warm, soothing sensation washes over your
soul. / You feel a strengthening of your faith and bolstering of your
soul." with sites on it, "It doesn't do anything though." with none,
and no badge at all turns the deed off for the run. `keep` does every
deed whenever its timer allows and waits between, reading the orb when
it stands in the Orb Room; the timers live in
~/.revenant/soul/<name>.json across runs, a refusal ("inappropriate so
soon") backs off twenty minutes. `quest`
is paladin-quests.lic's warding scene with the readings in front of
it: FOCUS ORB, wait for the girl's line, GUARD GIRL, wait for the
gift, every line echoed so the first accepted run captures the scene.
It never withdraws coins (a short purse is reported, ;debt and the
teller are yours), never drops, and stops on death or hostiles.
Stop with:  ;stop soul, or ;soul return.
"""

import time

from client.game import probe
from client.game.loop import danger, wants_stop
from client.game.mapdb import MapDB
from client.game.money import parse_wealth
from client.game.soul import (
    ALMSBOXES,
    ALTARS,
    ARCHES,
    BADGE_DONE,
    BADGE_EMPTY,
    BADGE_NONE,
    BADGE_NOT_YOURS,
    BADGE_SOON,
    FOCUS_BEGUN,
    FOCUS_REFUSED,
    FOCUS_REST,
    GIRL,
    GUARDED,
    ORB_ROOM,
    PRAYER_BEGUN,
    PRAYER_DONE,
    PRAYER_SOON,
    PRAYER_WAIT,
    QUEST_DONE,
    SCENE_SECONDS,
    TITHE_REFUSED,
    TITHE_SHORT,
    TITHE_SILVER,
    TITHED,
    box_noun,
    classify,
    currency_for,
    deeds_needed,
    describe,
    due,
    load_timers,
    mark,
    mark_state,
    parse_args,
    parse_pool,
    parse_state,
    ready_for_quest,
    save_timers,
    tithe_command,
)
from client.game.walker import locate, walk

COLLECT_SECONDS = 2
TAIL_SECONDS = 0.5
FOCUS_SECONDS = 4  # the orb's answer to FOCUS
GUARD_SECONDS = 4  # the answer to GUARD GIRL
BADGE_SECONDS_ANSWER = 4  # PRAY BADGE's answer past its 10 s roundtime
KEEP_POLL = 60  # seconds between looks at the timers while keeping
# A deed's room farther than this is skipped, not walked to: the map
# tags Shard's and Ratha's almsboxes, ALMSBOXES adds the Crossing's
# two, and a keep in one town must not set off for the other's box
# (2026-09-20).
MAX_STEPS = 80
clock = time.time  # tests replace it


def ask(s, command, seconds=None):
    # The window is read at call time, not bound as a default: the tests
    # set COLLECT_SECONDS to a hundredth and every soul test still waited
    # two real seconds per ask (2026-09-20, the suite's slowest file).
    return probe.ask(
        s, command, COLLECT_SECONDS if seconds is None else seconds, TAIL_SECONDS
    )


def echo_lines(s, text):
    for line in (text or "").splitlines():
        if line.strip():
            s.echo(f"  {line.strip()}")


def character(s):
    return getattr(s.state, "name", None) or "unknown"


def stow_hands(s):
    """Empty the hands with STOW (never DROP): the prayer wants them empty."""
    for side in ("left_hand", "right_hand"):
        held = getattr(s.state, side, None)
        if held and held.get("noun"):
            echo_lines(s, ask(s, f"stow my {held['noun']}"))


def stand(s):
    posture = getattr(getattr(s, "status", None), "posture", None)
    if posture and posture != "standing":
        ask(s, "stand")


# --- readings ---------------------------------------------------------------
def reading_noun(s):
    """ "orb" in the guild's Orb Room, else "my soulstone"."""
    objs = (getattr(s.state, "room_objs", "") or "").lower()
    title = (getattr(s.state, "room_title", "") or "").lower()
    if "orb" in objs or "orb room" in title:
        return "orb"
    return "my soulstone"


def read_soul(s, mapdb=None, walk_fn=walk, timers=None):
    """The readings: RUB and EXHALE the orb here (or a carried soulstone
    when no map is given), else a walk through the nearest soulstone
    arch for the state alone (#231). (state, pool), either None when
    unread; a state read is recorded in `timers` when given."""
    noun = reading_noun(s)
    if noun == "orb" or mapdb is None:
        rub = ask(s, f"rub {noun}")
        state = parse_state(rub)
        exhale = ask(s, f"exhale {noun}")
        pool = parse_pool(exhale)
        if state is None and pool is None:
            s.echo(f"soul: nothing to read here — RUB {noun} answered:")
            echo_lines(s, rub)
            if timers is not None:
                mark(timers, "read", False, clock())
            return None, None
        s.echo(f"soul: {describe(state, pool)}")
    else:
        state, pool = read_arch(s, mapdb, walk_fn), None
    if timers is not None:
        if state is not None:
            mark_state(timers, state, clock())
        else:
            mark(timers, "read", False, clock())
    return state, pool


def read_arch(s, mapdb, walk_fn=walk):
    """Walk to the nearest soulstone arch and step through it; the
    state its line carries, or None (no arch near, or an answer the
    table does not know). The pool has no reading here."""
    rooms = {room for room in ARCHES if room in mapdb.rooms}
    if not rooms:
        s.echo("soul: no soulstone arch on the map — read the orb (Shard's Orb Room)")
        return None
    if too_far(s, mapdb, rooms, "soulstone arch"):
        return None
    if not walk_fn(s, mapdb, rooms, describe="the soulstone arch"):
        s.echo("soul: could not reach a soulstone arch")
        return None
    here = locate(mapdb, s.state)
    command = ARCHES.get(here, ("go arch", None, ""))[0]
    answer = ask(s, command)
    state = parse_state(answer)
    if state is None:
        s.echo(f"soul: the arch answered nothing the table knows to {command.upper()}:")
        echo_lines(s, answer)
        return None
    s.echo(
        f"soul: {describe(state, None)} (the arch; the pool wants an orb — "
        "Shard's Orb Room)"
    )
    return state


# --- the deeds --------------------------------------------------------------
def rooms_for(mapdb, tag, known, override):
    """The rooms a deed happens in: an override, else the map's tagged
    rooms plus the known ones."""
    if override:
        return {override}
    rooms = set(mapdb.rooms_tagged(tag)) | {
        room for room in known if room in mapdb.rooms
    }
    return rooms


def too_far(s, mapdb, rooms, what):
    """True (said) when the nearest of `rooms` is more than MAX_STEPS
    away — or unreachable — so a deed never walks across the world."""
    here = locate(mapdb, s.state)
    if here is None:
        return False  # the walker will say what it cannot do
    from client.game.walker import character_ranks

    route = mapdb.path(here, set(rooms), ranks=character_ranks(s.state))
    if route is None or len(route) > MAX_STEPS:
        s.echo(
            f"soul: the nearest {what} is "
            f"{'unreachable' if route is None else f'{len(route)} rooms away'} — "
            f"skipping it (an {what} room id as almsbox=/altar= names a nearer one)"
        )
        return True
    return False


def tithe(s, mapdb, timers, options, walk_fn=walk):
    """Walk to an almsbox and tithe. True when the box took the coins."""
    rooms = rooms_for(mapdb, "tithe", ALMSBOXES, options["almsbox"])
    if not rooms:
        s.echo("soul: no almsbox known on the map — almsbox=<room id>")
        mark(timers, "tithe", False, clock())
        return False
    if too_far(s, mapdb, rooms, "almsbox"):
        mark(timers, "tithe", False, clock())
        return False
    if not walk_fn(s, mapdb, rooms, describe="the almsbox"):
        s.echo("soul: could not reach an almsbox")
        mark(timers, "tithe", False, clock())
        return False
    here = locate(mapdb, s.state)
    title = (mapdb.rooms.get(here) or {}).get("title", [""])[0] if here else ""
    currency = options["currency"] or currency_for(title)
    wealth = parse_wealth(ask(s, "wealth"))
    carried = wealth["carried"].get(currency.capitalize(), 0)
    if carried < TITHE_SILVER * 100:
        s.echo(
            f"soul: {carried} copper {currency} on you — the tithe is "
            f"{TITHE_SILVER} silver; fetch coins (;debt, the teller) and try again"
        )
        # A short purse is a refusal for the timers: the next look is
        # twenty minutes off, not the next second (2026-09-19, when a
        # keep asked WEALTH once a second at the box).
        mark(timers, "tithe", False, clock())
        return False
    noun = box_noun(getattr(s.state, "room_objs", ""))
    answer = ask(s, tithe_command(currency, noun))
    echo_lines(s, answer)
    outcome = classify(
        answer, ("done", TITHED), ("short", TITHE_SHORT), ("refused", TITHE_REFUSED)
    )
    if outcome == "done":
        mark(timers, "tithe", True, clock())
        s.echo(f"soul: tithed {TITHE_SILVER} silver {currency}")
        return True
    mark(timers, "tithe", False, clock())
    s.echo(f"soul: the almsbox did not take it ({outcome or 'an unknown answer'})")
    return False


def pray(s, mapdb, timers, options, walk_fn=walk):
    """Walk to a Chadatru altar and pray, knelt until it completes.
    True when the prayer completed."""
    rooms = rooms_for(mapdb, "chadatru", ALTARS, options["altar"])
    if not rooms:
        s.echo("soul: no Chadatru altar known on the map — altar=<room id>")
        mark(timers, "pray", False, clock())
        return False
    if too_far(s, mapdb, rooms, "altar"):
        mark(timers, "pray", False, clock())
        return False
    if not walk_fn(s, mapdb, rooms, describe="Chadatru's altar"):
        s.echo("soul: could not reach an altar")
        mark(timers, "pray", False, clock())
        return False
    stow_hands(s)
    answer = ask(s, "pray chadatru")
    echo_lines(s, answer)
    outcome = classify(
        answer, ("done", PRAYER_DONE), ("begun", PRAYER_BEGUN), ("soon", PRAYER_SOON)
    )
    if outcome == "begun":
        s.echo(f"soul: the prayer has begun — staying knelt up to {PRAYER_WAIT} s")
        text = probe.collect(s, PRAYER_WAIT, until=PRAYER_DONE[0])
        echo_lines(s, text)
        outcome = "done" if classify(text, ("done", PRAYER_DONE)) else "silent"
    stand(s)
    if outcome == "done":
        mark(timers, "pray", True, clock())
        s.echo("soul: prayed to Chadatru")
        return True
    mark(timers, "pray", False, clock())
    if outcome == "soon":
        s.echo("soul: too soon since the last prayer — backing off twenty minutes")
    else:
        s.echo(f"soul: the prayer did not complete ({outcome})")
    return False


def pray_badge(s, timers):
    """REMOVE the worn pilgrim's badge (GET it from a container when it
    is not worn), PRAY on it, WEAR it again. True when the prayer gave
    the soul line; a missing badge turns the deed off for the run
    (timers["badge_off"]), an empty or unbonded one is said."""
    held = any(
        (getattr(s.state, side, None) or {}).get("noun") == "badge"
        for side in ("left_hand", "right_hand")
    )
    if not held:
        answer = ask(s, "remove my badge")
        if classify(answer, ("none", BADGE_NONE)):
            answer = ask(s, "get my badge")
            if classify(answer, ("none", BADGE_NONE)):
                s.echo(
                    "soul: no pilgrim's badge on you — the badge deed is off for this run"
                )
                timers["badge_off"] = True
                return False
    answer = ask(s, "pray badge", BADGE_SECONDS_ANSWER)
    echo_lines(s, answer)
    outcome = classify(
        answer,
        ("done", BADGE_DONE),
        ("soon", BADGE_SOON),
        ("empty", BADGE_EMPTY),
        ("not yours", BADGE_NOT_YOURS),
        ("none", BADGE_NONE),
    )
    if not held:
        ask(s, "wear my badge")
    if outcome == "done":
        mark(timers, "badge", True, clock())
        s.echo("soul: prayed on the badge")
        return True
    mark(timers, "badge", False, clock())
    if outcome == "soon":
        s.echo(
            "soul: the badge's timer has not cleared — no boost this time, backing off"
        )
    elif outcome == "empty":
        s.echo(
            "soul: the badge has no sites on it — PUSH an attuned altar WITH BADGE first"
        )
    elif outcome == "not yours":
        s.echo("soul: the badge is not bonded to you — KISS it first")
    elif outcome == "none":
        s.echo("soul: no pilgrim's badge on you — the badge deed is off for this run")
        timers["badge_off"] = True
    else:
        s.echo(
            "soul: PRAY BADGE answered nothing known — please report the lines above"
        )
    return False


def quest(s, mapdb, options, walk_fn=walk):
    """The Glyph of Warding scene at the orb. True when the gift came."""
    if not walk_fn(s, mapdb, {ORB_ROOM}, describe="the Orb Room"):
        s.echo("soul: could not reach the Orb Room")
        return False
    state, pool = read_soul(s)
    if not options["force"] and not ready_for_quest(state, pool):
        s.echo(
            "soul: the orb wants a pristine soul and a full pool — "
            "keep the deeds running (;soul keep), or `quest force` to try anyway"
        )
        return False
    stow_hands(s)
    answer = ask(s, "focus orb", FOCUS_SECONDS)
    echo_lines(s, answer)
    outcome = classify(
        answer,
        ("begun", FOCUS_BEGUN),
        ("rest", FOCUS_REST),
        ("refused", FOCUS_REFUSED),
    )
    if outcome == "rest":
        s.echo("soul: the orb says rest and contemplate — the pool is not full yet")
        return False
    if outcome == "refused":
        s.echo("soul: the orb refused — the requirements are not met")
        return False
    if outcome != "begun":
        s.echo("soul: FOCUS answered nothing known — please report the lines above")
        return False
    s.echo("soul: the vision has begun — waiting for the girl (this takes a while)")
    text = probe.collect(s, SCENE_SECONDS, until=GIRL)
    echo_lines(s, text)
    if GIRL not in text.lower():
        s.echo("soul: the girl never came — stopping")
        return False
    answer = ask(s, "guard girl", GUARD_SECONDS)
    echo_lines(s, answer)
    if not classify(answer, ("guarded", GUARDED)):
        s.echo("soul: GUARD GIRL answered nothing known — the scene may still run")
    text = probe.collect(s, SCENE_SECONDS, until=QUEST_DONE[0])
    echo_lines(s, text)
    if classify(text, ("done", QUEST_DONE)):
        s.echo("soul: the Glyph of Warding is yours")
        return True
    s.echo("soul: the scene ended without the gift line — read the lines above")
    return False


def keep(s, mapdb, timers, options, walk_fn=walk):
    """The deeds whenever their timers allow, forever."""
    s.echo("soul: keeping the boosts running — ;soul return ends it")
    said_pristine = False
    while True:
        reason = danger(s)
        if reason:
            s.echo(f"soul: {reason} — stopping")
            return
        if wants_stop(s):
            s.echo("soul: stopping as asked")
            return
        did = False
        if due(timers, "read", clock()) == 0:
            # No fresh reading (or the last one aged out): the state
            # first, since a pristine soul wants no deed.
            read_soul(s, mapdb, walk_fn, timers)
            save_timers(character(s), timers)
            said_pristine = False
        if not deeds_needed(timers, clock()):
            if not said_pristine:
                s.echo(
                    "soul: pristine — no deeds needed; the arch is read again in "
                    f"{due(timers, 'read', clock()) / 60:.0f} min"
                )
                said_pristine = True
            s.sleep(max(KEEP_POLL, min(due(timers, "read", clock()), KEEP_POLL * 10)))
            continue
        if not timers.get("badge_off") and due(timers, "badge", clock()) == 0:
            pray_badge(s, timers)
            save_timers(character(s), timers)
            did = True
        if due(timers, "tithe", clock()) == 0:
            tithe(s, mapdb, timers, options, walk_fn)
            save_timers(character(s), timers)
            did = True
        if due(timers, "pray", clock()) == 0:
            pray(s, mapdb, timers, options, walk_fn)
            save_timers(character(s), timers)
            did = True
        if did and locate(mapdb, s.state) == ORB_ROOM:
            read_soul(s, mapdb, walk_fn, timers)
        deeds = ("tithe", "pray") + (() if timers.get("badge_off") else ("badge",))
        waits = {deed: due(timers, deed, clock()) for deed in deeds}
        soonest = min(waits.values())
        if did:
            s.echo(
                "soul: next "
                + ", ".join(
                    f"{deed} in {wait / 60:.0f} min" for deed, wait in waits.items()
                )
            )
        # Never faster than the poll: a deed that failed without a
        # timer mark would otherwise be tried every second.
        s.sleep(max(KEEP_POLL, min(soonest, KEEP_POLL * 10)))


def run(s, words, mapdb=None, walk_fn=walk):
    options = parse_args(words)
    verb = options["verb"]
    timers = load_timers(character(s))
    if verb == "read":
        read_soul(s, mapdb, walk_fn, timers)
        save_timers(character(s), timers)
        return
    timers.pop("badge_off", None)  # a new run looks for the badge again
    if verb == "badge":
        pray_badge(s, timers)
        save_timers(character(s), timers)
        return
    if mapdb is None:
        s.echo("soul: the deeds need the map — none loaded")
        return
    if verb == "tithe":
        tithe(s, mapdb, timers, options, walk_fn)
    elif verb == "pray":
        pray(s, mapdb, timers, options, walk_fn)
    elif verb == "quest":
        quest(s, mapdb, options, walk_fn)
        return
    elif verb == "keep":
        keep(s, mapdb, timers, options, walk_fn)
    save_timers(character(s), timers)


def main(s):
    run(s, list(s.args or []), mapdb=MapDB.load())
