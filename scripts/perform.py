"""Train Performance by playing the profile's instrument:  ;perform

    ;perform                    play the rank's song off-key on the profile's instrument until mind-lock
    ;perform instrument=zills   another instrument (the profile's `instrument` otherwise)
                                a room that refuses a song (a bank's teller: "now isn't the best time to be playing") sends it home once, the profile's `home`, to play there
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
is stopped first. It stops on death, on hostiles in the room, when
the instrument is not on you, and when EXP shows no Performance.
Captured 2026-09-18 on copper zills worn on a finger (bought from
Riverhaven's peddler): "You fumble slightly as you begin an off-key
ruff on your copper zills." / "You continue playing on your copper
zills." / "You're already playing a song!  You'll need to stop that
one first." / "You stop playing your song." — and a RETREAT ends a
song too: "You stop your performance."
Stop with:  ;stop perform (the song plays on — STOP PLAY yourself), or ;perform return.
"""

import re
import time

from client.engine.xml_data import LEARNING_RATES
from client.game import probe
from client.game.perform import (
    ALREADY,
    ENDED,
    NO_INSTRUMENT,
    NOT_HERE,
    STARTED,
    STOPPED,
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
    name = getattr(s.state, "name", None)
    if not name:
        return ""
    from client.game.profile import load_profile

    return str(load_profile(name).get("instrument") or "").strip()


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
    """PLAY; "playing" when the song started (or was already running),
    "no instrument" when the game found none, "unknown" otherwise."""
    song = options["song"] or song_for(rank(s))
    answer = probe.ask(
        s,
        play_command(song, options["mood"], options["instrument"]),
        COLLECT_SECONDS,
        TAIL_SECONDS,
    ).lower()
    if any(word in answer for word in STARTED + ALREADY):
        return "playing"
    if any(word in answer for word in NO_INSTRUMENT):
        return "no instrument"
    if any(word in answer for word in NOT_HERE):
        return "not here"
    return "unknown"


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
            outcome = start_song(s, options)
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
            if outcome == "unknown":
                s.echo(
                    "perform: PLAY answered nothing known — please report it — stopping"
                )
                return
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
