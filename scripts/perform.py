"""Train Performance by playing the profile's instrument:  ;perform

    ;perform                    play the rank's song off-key on the profile's instrument until mind-lock
    ;perform instrument=zills   another instrument (the profile's `instrument` otherwise)
                                a room that refuses a song (a bank's teller: "now isn't the best time to be playing") sends it home once, the profile's `home`, to play there
                                an instrument the game calls dirty at PLAY is cleaned once per run with the profile's `instrument_cloth` (REMOVE, WIPE when wet, CLEAN, WEAR), then played again; no cloth is said once and the song plays dirty
    ;perform song=ballad        a song of your own instead of the rank's band
    ;perform mood=halting       another style (off-key by default; mood= alone for the plain style)
    ;perform until=30           stop at that mindstate instead of 34
    ;perform once               exit at mind-lock instead of holding for the drain
    ;perform return             (typed while it runs) stop the song and end

PLAY starts a song that runs on its own, and Performance learns while
it plays (Elanthipedia: Performance skill, Play command; the song per
rank band and the wordings are client/game/perform.py's). The script
PLAYs the band's song — scales to rank 39, arpeggios to 49, and so on
— off-key, the easiest style, watches the mindstate, starts the song
again when the story says it ended, and at mind-lock STOPs PLAY and
holds until enough has drained to be worth playing again; `once`
exits at the lock instead. ;train runs it as a task (skills:
["Performance"], return_word "return") and ends it at the plan's
target: the word lands within a second, playing or held, and the song
is stopped first. It stops on death, on hostiles in the room (or the
game's own "You cannot use the copper zills while in combat!" when the
parser has not seen them yet, #243), when the instrument is not on
you, and when EXP shows no Performance.
Captured 2026-09-18 on copper zills worn on a finger (bought from
Riverhaven's peddler): "You fumble slightly as you begin an off-key
ruff on your copper zills." / "You continue playing on your copper
zills." / "You're already playing a song!  You'll need to stop that
one first." / "You stop playing your song." — and a RETREAT ends a
song too: "You stop your performance."
An instrument gathers dirt as it plays, and the game says so at PLAY
("Your zills's dirtiness may affect your performance.", 2026-09-20 —
every song of an evening, the ranks paying for it). The first such
warning of a run has the script GET the profile's `instrument_cloth`
(a cotton rag), STOP PLAY and CLEAN <instrument> WITH MY <cloth>
(Elanthipedia: Clean command; client/game/perform.py's wordings):
CLEAN wants the instrument in hand, so a worn one is REMOVEd and worn
again after; a wet one ("so wet that they are still dripping") is
WIPEd with the cloth first; the cloth is stowed and the song starts
over (#233). No cloth in the profile, or none on you, is said once
and the song plays dirty; nothing is ever dropped.
Stop with:  ;stop perform (the song plays on — STOP PLAY yourself), or ;perform return.
"""

import re
import time

from client.engine.xml_data import LEARNING_RATES
from client.game import probe
from client.game.perform import (
    ALREADY,
    CLEANED,
    DIRTY,
    ENDED,
    IN_COMBAT,
    MUST_HOLD,
    NO_CLOTH,
    NO_INSTRUMENT,
    NOT_HERE,
    STARTED,
    STOPPED,
    WET,
    parse_args,
    play_command,
    song_for,
)

MIND_LOCK = 34
RESUME_BELOW = 28  # resume once enough has drained to be worth a song
POLL = 15  # seconds between looks at the story and the mindstate
LOCK_POLL = 30
COLLECT_SECONDS = 2
TAIL_SECONDS = 0.5
clock = time.monotonic  # tests replace it

_EXP_ANSWER = re.compile(r"Performance:\s+(\d+)\s+[\d.]+%\s+.*?\((\d+)/34\)")


def instrument_of(s):
    """The profile's instrument, or ""."""
    return _profile_field(s, "instrument")


def cloth_of(s):
    """The profile's cleaning cloth (`instrument_cloth`), or "" (#233)."""
    return _profile_field(s, "instrument_cloth")


def _profile_field(s, key):
    name = getattr(s.state, "name", None)
    if not name:
        return ""
    from client.game.profile import load_profile

    return str(load_profile(name).get(key) or "").strip()


def ask(s, command):
    """The game's answer to one command, lower-cased."""
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS).lower()


def fetch_cloth(s, instrument, cloth):
    """The cleaning cloth into a hand: whatever else a hand holds is
    STOWed first (never dropped), then GET. False, said once, when the
    game finds no such cloth on you."""
    for side in ("left", "right"):
        held = getattr(s.state, f"{side}_hand", None)
        noun = held.get("noun") if isinstance(held, dict) else None
        if noun and noun.lower() not in (instrument.lower(), cloth.lower()):
            ask(s, f"stow my {noun}")
    answer = ask(s, f"get my {cloth}")
    if any(word in answer for word in NO_CLOTH):
        s.echo(f"perform: no {cloth} on you — the {instrument} plays dirty")
        return False
    return True


def clean_instrument(s, instrument, cloth):
    """CLEAN the instrument with the cloth in hand (#233): REMOVE it when
    the game wants it held, WIPE it when wet, then CLEAN; worn again if
    removed, the cloth stowed. True when the game said it was cleaned."""
    removed = cleaned = False
    for _ in range(4):
        answer = ask(s, f"clean my {instrument} with my {cloth}")
        if any(word in answer for word in CLEANED):
            cleaned = True
            break
        if any(word in answer for word in MUST_HOLD):
            ask(s, f"remove my {instrument}")
            removed = True
        elif any(word in answer for word in WET):
            ask(s, f"wipe my {instrument} with my {cloth}")
        else:
            s.echo("perform: CLEAN answered nothing known — please report it")
            break
    if removed:
        ask(s, f"wear my {instrument}")
    ask(s, f"stow my {cloth}")
    if cleaned:
        s.echo(f"perform: {instrument} cleaned with the {cloth}")
    return cleaned


def entry(s):
    return (getattr(s.state, "experience", None) or {}).get("Performance")


def mindstate(s):
    value = entry(s)
    return value["mindstate"] if value else None


def rank(s):
    value = entry(s)
    return value.get("rank") if value else None


def ensure_mindstate(s):
    """The mindstate: the exp window's, or EXP PERFORMANCE's own answer
    when the window does not list the skill (a clear pool is absent
    from it; a guild without the skill gets no line at all)."""
    value = mindstate(s)
    if value is None:
        answer = probe.ask(s, "exp performance", COLLECT_SECONDS, TAIL_SECONDS)
        value = mindstate(s)
        if value is None:
            match = _EXP_ANSWER.search(answer or "")
            if match:
                value = int(match.group(2))
                # A whole entry, the parser's shape (rank, percent,
                # mindstate, rate): the engine renders every entry of
                # the state, and a seed without a rate took the session
                # down (2026-09-20, #239).
                s.state.experience = dict(getattr(s.state, "experience", None) or {})
                s.state.experience["Performance"] = {
                    "rank": int(match.group(1)),
                    "percent": 0,
                    "mindstate": value,
                    "rate": LEARNING_RATES[min(value, 34)],
                }
    return value


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


def start_song(s, options):
    """PLAY; ("playing", dirty) when the song started (or was already
    running) — dirty True when the game said the instrument's dirt
    weighs on it (#233) — ("no instrument", False) when the game found
    none, ("not here", False) for a room that refuses a song,
    ("unknown", False) otherwise."""
    song = options["song"] or song_for(rank(s))
    answer = ask(s, play_command(song, options["mood"], options["instrument"]))
    dirty = any(word in answer for word in DIRTY)
    if any(word in answer for word in STARTED + ALREADY):
        return "playing", dirty
    if any(word in answer for word in NO_INSTRUMENT):
        return "no instrument", False
    if any(word in answer for word in NOT_HERE):
        return "not here", False
    if any(word in answer for word in IN_COMBAT):
        return "in combat", False
    return "unknown", False


def home_of(s):
    """The profile's home — a ;go2 target — or ""."""
    name = getattr(s.state, "name", None)
    if not name:
        return ""
    from client.game.profile import load_profile

    return str(load_profile(name).get("home") or "").strip()


def walk_home(s, home):
    """Walk to the profile's home for a room that allows a song; False
    when the map has no such room or the walk failed."""
    from client.game.mapdb import MapDB
    from client.game.walker import walk

    mapdb = MapDB.load()
    goals = mapdb.resolve(home)
    if not goals:
        s.echo(f"perform: nothing in the map matches home {home!r}")
        return False
    return walk(s, mapdb, set(goals), describe=repr(home))


def stop_song(s):
    probe.ask(s, "stop play", COLLECT_SECONDS, TAIL_SECONDS)


def watch(s, seconds, until=None):
    """Read the story for `seconds`, a second at a time: "ended" when
    the song ran out or was stopped (a RETREAT does it too), "stop" on
    a typed return or danger, "target" the second the mindstate
    reaches `until`, None when the time passed with the song playing."""
    end = clock() + seconds
    while (left := end - clock()) > 0:
        text = probe.collect(s, min(1, left)).lower()
        if any(word in text for word in ENDED + STOPPED):
            return "ended"
        if wants_stop(s) or danger(s):
            return "stop"
        value = mindstate(s)
        if until is not None and value is not None and value >= until:
            return "target"
    return None


def hold_at_lock(s, until):
    s.echo(f"perform: Performance mind-locked ({until}/34) — holding until it drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if watch(s, LOCK_POLL) == "stop":
            return False
        value = mindstate(s)
        if value is not None and value <= floor:
            s.echo(f"perform: drained to {value}/34 — playing again")
            return True


def run(s, options, walker=walk_home):
    if not options["instrument"]:
        options["instrument"] = instrument_of(s)
    if not options["instrument"]:
        s.echo("perform: no instrument — instrument=<noun>, or the profile's")
        return
    value = ensure_mindstate(s)
    if value is None:
        s.echo("perform: EXP shows no Performance — nothing to train")
        return
    playing = False
    songs = 0
    moved = False  # walked home once for a room that refuses a song
    cleaned = False  # the instrument cleaned once for a dirt warning (#233)
    while True:
        reason = danger(s)
        if reason:
            if playing:
                stop_song(s)
            s.echo(f"perform: {reason} — stopping")
            return
        value = mindstate(s)
        if value is not None and value >= options["until"]:
            if playing:
                stop_song(s)
                playing = False
            if options["once"]:
                s.echo(f"perform: Performance at {value}/34 — done")
                return
            if not hold_at_lock(s, options["until"]):
                s.echo("perform: stopping")
                return
            continue
        if not playing:
            outcome, dirty = start_song(s, options)
            if outcome == "no instrument":
                s.echo(f"perform: no {options['instrument']} on you — stopping")
                return
            if outcome == "not here":
                # A bank's teller refused the song (2026-09-20): once,
                # walk to the profile's home and play there.
                home = home_of(s)
                if moved or not home:
                    s.echo(
                        "perform: the game refuses a song here"
                        + (
                            " and at home too"
                            if moved
                            else " and the profile names no home"
                        )
                        + " — stopping"
                    )
                    return
                s.echo(f"perform: the game refuses a song here — walking home ({home})")
                moved = True
                if not walker(s, home):
                    s.echo("perform: could not walk home — stopping")
                    return
                continue
            if outcome == "in combat":
                # The game refused the song for a fight the parser had
                # not shown yet (2026-09-20, right after a ;reexec, #243).
                s.echo("perform: in combat — stopping")
                return
            if outcome == "unknown":
                s.echo(
                    "perform: PLAY answered nothing known — please report it — stopping"
                )
                return
            if dirty and not cleaned:
                # The game says the dirt weighs on the song (#233): once
                # per run, the profile's cloth cleans the instrument and
                # the song starts over; no cloth means playing dirty.
                cleaned = True
                cloth = cloth_of(s)
                if not cloth:
                    s.echo(
                        f"perform: the {options['instrument']} is dirty and the "
                        "profile names no cloth (instrument_cloth) — playing on"
                    )
                elif fetch_cloth(s, options["instrument"], cloth):
                    stop_song(s)
                    clean_instrument(s, options["instrument"], cloth)
                    continue
            playing = True
            songs += 1
            s.echo(
                f"perform: playing {options['song'] or song_for(rank(s))} "
                f"{options['mood']} on the {options['instrument']} "
                f"(Performance {value}/34)"
            )
        outcome = watch(s, POLL, until=options["until"])
        if outcome == "stop":
            stop_song(s)
            s.echo("perform: stopping as asked")
            return
        if outcome == "ended":
            playing = False


def main(s):
    options = parse_args(s.args or [])
    run(s, options)
