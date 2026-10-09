"""Keep a Paladin's soul up and read it:  ;soul

    ;soul [read]            read the soul: RUB and EXHALE the orb here, else walk through the nearest soulstone arch
    ;soul keep              run the deeds on their timers while the soul reads below pristine
    ;soul tithe             one tithe of 5 silver at the nearest almsbox, then back
    ;soul pray              one prayer at the nearest Chadatru altar, knelt until it completes
    ;soul badge             one PRAY BADGE on the pilgrim's badge, wherever you stand
    ;soul song              one song FOR CHADATRU at the nearest Chadatru shrine
    ;soul quest             the Glyph of Warding scene at the guild orb, once the readings say ready
    ;soul quest force       FOCUS the orb whatever the readings say
    ;soul ... almsbox=<id>  an almsbox room the map has not tagged (altar=<id> likewise)
    ;soul ... currency=<c>  tithe in another coin than the town's (lirums, ...)
    ;soul ... instrument=<noun>  sing on another instrument than the profile's
    ;soul return            (typed during keep) finish the deed in hand and end
    ;stop soul              quit at once

What it does
  - Reads the state (RUB, or the arch) and the pool (EXHALE, at an orb); a reading holds 4 hours.
  - Runs no deed while the soul reads pristine: the deeds restore a soul, not keep one.
  - keep: the badge every 31 min, the tithe every 4 h, the prayer every 2 h, the song
    every hour (unmeasured); a refusal backs off 20 min; an altar that answers with the
    plain prayer turns praying off until ;soul pray is typed. The timers live in
    ~/.revenant/soul/<name>.json.
  - song: the rank's song in the first style that plays "with only the slightest hint
    of difficulty" (never off-key or halting), heard out to its end.
  - quest: FOCUS ORB, GUARD GIRL, every line of the scene echoed.

What it never does
  - withdraw coins: a short purse or a debt to the province is reported, the teller is yours
  - walk to a deed's room over 80 steps away (the other town's almsbox)
  - drop anything: the hands are emptied with STOW

It stops on death, on hostiles in the room (it flees), and on ;soul return.
client/game/soul.py is the model and docs/soul.md the guide, after Elanthipedia's
Soul system page and dr-scripts' tithe.lic.
"""

import time

from client.game import flight, hands, probe, travel
from client.game.act import ask, unknown
from client.game.loop import danger, wants_stop
from client.game.mapdb import MapDB
from client.game.money import parse_wealth
from client.game.perform import (
    ALREADY,
    ENDED,
    IN_COMBAT,
    NO_INSTRUMENT,
    NOT_HERE,
    STARTED,
    STOPPED,
    STYLES,
    TIERS,
    difficulty,
    play_command,
    song_for,
)
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
    PRAYER_GENERIC,
    PRAYER_DONE,
    PRAYER_SOON,
    PRAYER_WAIT,
    QUEST_DONE,
    SCENE_SECONDS,
    SONG_BARRED,
    SONG_DONE,
    SONG_FOR,
    SONG_WAIT,
    TITHE_DEBT,
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

# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Keep a Paladin's soul up and read it:  ;soul

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
teller are yours; a debt to the province, which the box refuses a
tithe for, is said once and costs no walk until WEALTH shows it
paid, #304), never drops, and stops on death or hostiles.
The song (#435, 2026-10-03): a lament played FOR CHADATRU at the
Crossing temple's shrine, "with only the slightest hint of
difficulty", ended with the prayer's soul line; Elanthipedia's
Performance skill page bars off-key and halting. `song` plays the
rank's song in every other style until one starts "slightest" and
keeps that one (remembered as `song_style`), hears it out to "You
finish playing", and reads the soul line after it. The timer is
unmeasured: an hour until the misses' minutes say otherwise.
Stop with:  ;stop soul, or ;soul return.
"""

FOCUS_SECONDS = 4  # the orb's answer to FOCUS
GUARD_SECONDS = 4  # the answer to GUARD GIRL
BADGE_SECONDS_ANSWER = 4  # PRAY BADGE's answer past its 10 s roundtime
SOUL_LINE_SECONDS = 3  # the soul's line after the song's end (the same prompt)
KEEP_POLL = 60  # seconds between looks at the timers while keeping
# A deed's room farther than this is skipped, not walked to: the map
# tags Shard's and Ratha's almsboxes, ALMSBOXES adds the Crossing's
# two, and a keep in one town must not set off for the other's box
# (2026-09-20).
MAX_STEPS = 80
clock = time.time  # tests replace it


def echo_lines(s, text):
    for line in (text or "").splitlines():
        if line.strip():
            s.echo(f"  {line.strip()}")


def character(s):
    return getattr(s.state, "name", None) or "unknown"


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
    if not travel.go(
        s, rooms, "the soulstone arch", db=mapdb, walk=walk_fn, max_steps=MAX_STEPS
    ):
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


def owes(s, timers, currency, wealth):
    """True (said once, the tithe backed off) while WEALTH shows a debt
    in the almsbox's coin: the box refuses a donation from a character
    who owes the province (#304). A debt paid clears the mark."""
    owed = wealth["debt"].get(currency.capitalize(), 0)
    if not owed:
        timers.pop("tithe_debt", None)
        return False
    if timers.get("tithe_debt") != currency:
        s.echo(
            f"soul: you owe the province {owed} copper {currency} — the almsbox "
            "takes no tithe until it is paid (;debt pays it)"
        )
    timers["tithe_debt"] = currency
    mark(timers, "tithe", False, clock())
    return True


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
    wealth = None
    if timers.get("tithe_debt"):
        # The box refused for this province's debt before: WEALTH
        # (no roundtime) says whether it stands, and a standing debt
        # costs no walk (#304: 38 steps every rest).
        wealth = parse_wealth(ask(s, "wealth"))
        if owes(s, timers, timers["tithe_debt"], wealth):
            return False
    if not travel.go(
        s, rooms, "the almsbox", db=mapdb, walk=walk_fn, max_steps=MAX_STEPS
    ):
        s.echo("soul: could not reach an almsbox")
        mark(timers, "tithe", False, clock())
        return False
    here = locate(mapdb, s.state)
    title = (mapdb.rooms.get(here) or {}).get("title", [""])[0] if here else ""
    currency = options["currency"] or currency_for(title)
    wealth = wealth or parse_wealth(ask(s, "wealth"))
    if owes(s, timers, currency, wealth):
        return False
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
        answer,
        ("done", TITHED),
        ("short", TITHE_SHORT),
        ("refused", TITHE_REFUSED),
        ("debt", TITHE_DEBT),
    )
    if outcome == "debt":
        # WEALTH showed no debt, yet the box names one: trust the box.
        owes(s, timers, currency, {"debt": {currency.capitalize(): 1}})
        return False
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
    if not travel.go(
        s, rooms, "Chadatru's altar", db=mapdb, walk=walk_fn, max_steps=MAX_STEPS
    ):
        s.echo("soul: could not reach an altar")
        mark(timers, "pray", False, clock())
        return False
    hands.free(s, ask=ask)  # the prayer wants them empty: STOW, never DROP
    answer = ask(s, "pray chadatru")
    echo_lines(s, answer)
    outcome = classify(
        answer,
        ("done", PRAYER_DONE),
        ("begun", PRAYER_BEGUN),
        ("soon", PRAYER_SOON),
        ("generic", PRAYER_GENERIC),
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
    elif outcome == "generic":
        # The plain prayer, not the soul's (#305): no point walking here
        # every rest. Off for ;train until ;soul pray is run by hand.
        timers["pray_off"] = True
        s.echo(
            "soul: this altar answered PRAY CHADATRU with the plain prayer, not the "
            "soul's — prayers off for ;train until ;soul pray is run by hand (#305)"
        )
    else:
        s.echo(f"soul: the prayer did not complete ({outcome})")
    return False


def pray_badge(s, timers):
    """REMOVE the worn pilgrim's badge (GET it from a container when it
    is not worn), PRAY on it, WEAR it again. True when the prayer gave
    the soul line; a missing badge turns the deed off for the run
    (timers["badge_off"]), an empty or unbonded one is said."""
    held = hands.holding(s, "badge")
    if not held:
        # REMOVE wants a hand: a hunt ends armed and the interlude put a
        # gem back — "You need a free hand for that." (2026-10-07, #484).
        hands.free_one(s, ask=ask)
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
        unknown(s, "soul", "PRAY BADGE", answer)
    return False


def instrument_of(s):
    """The profile's `instrument`, or ""."""
    name = getattr(s.state, "name", None)
    if not name:
        return ""
    from client.game.profile import load_profile

    return str(load_profile(name).get("instrument") or "").strip()


def performance_rank(s):
    entry = (getattr(s.state, "experience", None) or {}).get("Performance")
    return entry.get("rank") if entry else None


def song_command(song, style, instrument):
    return f"{play_command(song, style, instrument)} for {SONG_FOR}"


def start_song(s, song, instrument, timers):
    """PLAY the song FOR CHADATRU in every style but off-key and halting,
    the one that last played "slightest" first; the first that plays
    "slightest" plays on, the rest are STOPped. (style, tier) of the
    song left playing — the best tier seen when none reached slightest
    — or (None, why): "no instrument", "not here", "in combat",
    "unknown"."""
    styles = [style for style in STYLES if style not in SONG_BARRED]
    remembered = timers.get("song_style")
    if remembered in styles:
        styles.remove(remembered)
        styles.insert(0, remembered)
    best = None  # (tier index, style)
    for style in styles:
        answer = ask(s, song_command(song, style, instrument))
        if any(word in answer.lower() for word in ALREADY):
            ask(s, "stop play")
            answer = ask(s, song_command(song, style, instrument))
        lowered = answer.lower()
        for why, words in (
            ("no instrument", NO_INSTRUMENT),
            ("not here", NOT_HERE),
            ("in combat", IN_COMBAT),
        ):
            if any(word in lowered for word in words):
                return None, why
        tier = difficulty(answer)
        if tier == "slightest":
            timers["song_style"] = style
            return style, tier
        if any(word in lowered for word in STARTED):
            ask(s, "stop play")
        if tier is not None and (best is None or TIERS.index(tier) < best[0]):
            best = (TIERS.index(tier), style)
    if best is None:
        return None, "unknown"
    ask(s, song_command(song, best[1], instrument))
    return best[1], TIERS[best[0]]


def hear_out(s):
    """The story until the song ends, the soul's line after it
    included: (text, ended). Danger ends the wait (ended False)."""
    deadline = probe.clock() + SONG_WAIT
    heard = []
    while probe.clock() < deadline:
        text = probe.collect(s, 1)
        heard.append(text)
        if any(word in text.lower() for word in ENDED + STOPPED):
            if SONG_DONE[0] not in text.lower():
                heard.append(probe.collect(s, SOUL_LINE_SECONDS, until=SONG_DONE[0]))
            return "\n".join(heard), True
        if danger(s):
            break
    return "\n".join(heard), False


def sing(s, mapdb, timers, options, walk_fn=walk):
    """Walk to a Chadatru shrine and play the rank's song FOR CHADATRU
    to its end (#435). True when the soul's line followed it; no
    instrument, or a shrine that refuses a song, turns the deed off
    (timers["song_off"]) until ;soul song is typed."""
    instrument = options["instrument"] or instrument_of(s)
    if not instrument:
        s.echo(
            "soul: no instrument — the profile's `instrument`, or instrument=<noun>; "
            "the song deed is off until ;soul song"
        )
        timers["song_off"] = True
        return False
    rooms = rooms_for(mapdb, "chadatru", ALTARS, options["altar"])
    if not rooms:
        s.echo("soul: no Chadatru shrine known on the map — altar=<room id>")
        mark(timers, "song", False, clock())
        return False
    if too_far(s, mapdb, rooms, "altar"):
        mark(timers, "song", False, clock())
        return False
    if not travel.go(
        s, rooms, "Chadatru's shrine", db=mapdb, walk=walk_fn, max_steps=MAX_STEPS
    ):
        s.echo("soul: could not reach a Chadatru shrine")
        mark(timers, "song", False, clock())
        return False
    song = song_for(performance_rank(s))
    style, tier = start_song(s, song, instrument, timers)
    last = timers.get("song")
    since = f"{(clock() - last) / 60:.0f} min since the last" if last else "the first"
    if style is None:
        mark(timers, "song", False, clock())
        if tier in ("no instrument", "not here"):
            timers["song_off"] = True
            s.echo(
                f"soul: {'no ' + instrument + ' on you' if tier == 'no instrument' else 'the shrine refuses a song'}"
                " — the song deed is off until ;soul song"
            )
        elif tier == "in combat":
            s.echo("soul: in combat — no song")
        else:
            s.echo(
                f"soul: no style of the {song} started — PLAY answered nothing known"
            )
        return False
    s.echo(
        f"soul: a {song} {style or 'in the plain style'} for Chadatru ({tier}) — "
        "heard out to its end"
    )
    text, ended = hear_out(s)
    if not ended:
        ask(s, "stop play")
    if classify(text, ("done", SONG_DONE)):
        mark(timers, "song", True, clock())
        s.echo(f"soul: sang for Chadatru ({since})")
        return True
    mark(timers, "song", False, clock())
    s.echo(
        f"soul: the song {'ended' if ended else 'was cut short'} without the soul's "
        f"line ({tier}; {since}) — backing off twenty minutes"
    )
    return False


def quest(s, mapdb, options, walk_fn=walk):
    """The Glyph of Warding scene at the orb. True when the gift came."""
    if not travel.go(s, {ORB_ROOM}, "the Orb Room", db=mapdb, walk=walk_fn):
        s.echo("soul: could not reach the Orb Room")
        return False
    state, pool = read_soul(s)
    if not options["force"] and not ready_for_quest(state, pool):
        s.echo(
            "soul: the orb wants a pristine soul and a full pool — "
            "keep the deeds running (;soul keep), or `quest force` to try anyway"
        )
        return False
    hands.free(s, ask=ask)
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
        unknown(s, "soul", "FOCUS", answer)
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
            if "hostiles" in reason:
                flight.react(s, "soul")
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
        if not timers.get("song_off") and due(timers, "song", clock()) == 0:
            sing(s, mapdb, timers, options, walk_fn)
            save_timers(character(s), timers)
            did = True
        if did and locate(mapdb, s.state) == ORB_ROOM:
            read_soul(s, mapdb, walk_fn, timers)
        deeds = (
            ("tithe", "pray")
            + (() if timers.get("badge_off") else ("badge",))
            + (() if timers.get("song_off") else ("song",))
        )
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
    if verb == "pray":
        timers.pop("pray_off", None)  # typed by hand: try the altar again
    if verb in ("song", "keep"):
        timers.pop("song_off", None)  # look for the instrument again
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
    elif verb == "song":
        sing(s, mapdb, timers, options, walk_fn)
    elif verb == "quest":
        quest(s, mapdb, options, walk_fn)
        return
    elif verb == "keep":
        keep(s, mapdb, timers, options, walk_fn)
    save_timers(character(s), timers)


def main(s):
    run(s, list(s.args or []), mapdb=MapDB.load())
