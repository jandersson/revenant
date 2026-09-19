"""Keep a Paladin's soul up and read it:  ;soul

    ;soul                     read the soul: RUB and EXHALE the orb here (or your soulstone), say the state and pool
    ;soul keep                keep the boosts running on their timers — tithe every 4 h, pray to Chadatru every 2 h — until ;soul return
    ;soul tithe               one tithe of 5 silver at the nearest almsbox (the map's `tithe` rooms), then back
    ;soul pray                one prayer at the nearest Chadatru altar, knelt until it completes
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
the town's coin in it, walk to the altar, PRAY CHADATRU and stay
knelt until "A warm, soothing sensation washes over your soul" — and
the readings the scripts there never take: RUB for the state, EXHALE
for the pool. `keep` does both deeds whenever their timers allow and
waits at the altar between, reading the orb when it stands in the Orb
Room; the timers live in ~/.revenant/soul/<name>.json across runs, a
refusal ("inappropriate so soon") backs off twenty minutes. `quest`
is paladin-quests.lic's warding scene with the readings in front of
it: FOCUS ORB, wait for the girl's line, GUARD GIRL, wait for the
gift, every line echoed so the first accepted run captures the scene.
It never withdraws coins (a short purse is reported, ;debt and the
teller are yours), never drops, and stops on death or hostiles.
Stop with:  ;stop soul, or ;soul return.
"""

import time

from client.game import probe
from client.game.mapdb import MapDB
from client.game.money import parse_wealth
from client.game.soul import (
    ALMSBOXES,
    ALTARS,
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
    classify,
    currency_for,
    describe,
    due,
    load_timers,
    mark,
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
KEEP_POLL = 60  # seconds between looks at the timers while keeping
clock = time.time  # tests replace it


def ask(s, command, seconds=COLLECT_SECONDS):
    return probe.ask(s, command, seconds, TAIL_SECONDS)


def echo_lines(s, text):
    for line in (text or "").splitlines():
        if line.strip():
            s.echo(f"  {line.strip()}")


def danger(s):
    if s.dead:
        return "you are dead"
    if getattr(s.state, "hostiles", None):
        return "hostiles in the room"
    return None


def wants_stop(s):
    while (line := s.command(timeout=0)) is not None:
        if "return" in line.lower():
            return True
    return False


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


def read_soul(s):
    """RUB and EXHALE: (state, pool), either None when unread."""
    noun = reading_noun(s)
    rub = ask(s, f"rub {noun}")
    state = parse_state(rub)
    exhale = ask(s, f"exhale {noun}")
    pool = parse_pool(exhale)
    if state is None and pool is None:
        s.echo(f"soul: nothing to read here — RUB {noun} answered:")
        echo_lines(s, rub)
        return None, None
    s.echo(f"soul: {describe(state, pool)}")
    return state, pool


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


def tithe(s, mapdb, timers, options, walk_fn=walk):
    """Walk to an almsbox and tithe. True when the box took the coins."""
    rooms = rooms_for(mapdb, "tithe", ALMSBOXES, options["almsbox"])
    if not rooms:
        s.echo("soul: no almsbox known on the map — almsbox=<room id>")
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
    answer = ask(s, tithe_command(currency))
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
    while True:
        reason = danger(s)
        if reason:
            s.echo(f"soul: {reason} — stopping")
            return
        if wants_stop(s):
            s.echo("soul: stopping as asked")
            return
        did = False
        if due(timers, "tithe", clock()) == 0:
            tithe(s, mapdb, timers, options, walk_fn)
            save_timers(character(s), timers)
            did = True
        if due(timers, "pray", clock()) == 0:
            pray(s, mapdb, timers, options, walk_fn)
            save_timers(character(s), timers)
            did = True
        if did and locate(mapdb, s.state) == ORB_ROOM:
            read_soul(s)
        waits = {deed: due(timers, deed, clock()) for deed in ("tithe", "pray")}
        soonest = min(waits.values())
        if did:
            s.echo(
                "soul: next tithe in "
                f"{waits['tithe'] / 60:.0f} min, next prayer in {waits['pray'] / 60:.0f} min"
            )
        # Never faster than the poll: a deed that failed without a
        # timer mark would otherwise be tried every second.
        s.sleep(max(KEEP_POLL, min(soonest, KEEP_POLL * 10)))


def run(s, words, mapdb=None, walk_fn=walk):
    options = parse_args(words)
    verb = options["verb"]
    if verb == "read":
        read_soul(s)
        return
    if mapdb is None:
        s.echo("soul: the deeds need the map — none loaded")
        return
    timers = load_timers(character(s))
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
    words = list(s.args or [])
    options = parse_args(words)
    run(s, words, mapdb=None if options["verb"] == "read" else MapDB.load())
