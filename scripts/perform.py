"""Train Performance by playing the profile's instrument to mind-lock:  ;perform

    ;perform                    play the rank's song in its best style until Performance mind-locks
    ;perform instrument=<noun>  another instrument (the profile's `instrument` otherwise)
    ;perform song=<song>        a song of your own instead of the rank's
    ;perform mood=<style>       one style, no search (mood= alone for the game's own style)
    ;perform until=30           stop at that mindstate instead of 34
    ;perform once               exit at mind-lock instead of holding for the drain
    ;perform return             (typed while it runs) stop the song and end
    ;stop perform               quit at once, the song stopped

What it does
  - Tries every style of the song for your rank band (PLAY, STOP PLAY: no roundtime) and keeps
    the one the game rates nearest "with only the slightest hint of difficulty"; again after each lock.
  - PLAYs it, starts it again when it ends, watches the mindstate.
  - At mind-lock STOPs PLAY and holds until the pool drains, then plays again
    (client/game/trainer.py, the loop every trainer runs).
  - A room that refuses a song sends it to the profile's `home` once, to play there.
  - An instrument the game calls dirty is cleaned once a run with `instrument_cloth`
    (removed and worn again, wiped when wet); with no cloth it plays dirty.
  - Nothing is ever dropped: whatever else is in hand is stowed for the cloth.

When it stops
  - death, or hostiles in the room (the shared escape)
  - the instrument not on you, or EXP showing no Performance
  - a song refused at home too, or a PLAY answer it does not know
  - mind-lock with `once`, or ;perform return

;train runs it as a Performance task. The profile is ~/.revenant/profiles/<name>.json
(File > Character Profile...); the songs and wordings are client/game/perform.py's.
"""

import time
from types import SimpleNamespace

from client.game import hands, probe, trainer, travel
from client.game.act import ask
from client.game.loop import danger, wants_stop
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
    STYLES,
    TIERS,
    difficulty,
    parse_args,
    play_command,
    song_for,
)

# The design notes the manual above leaves out: what each rule came
# from, with its issue — read by people, never served as ;help.
_NOTES = """Train Performance by playing the profile's instrument:  ;perform

    ;perform                    play the rank's song in its best style on the profile's instrument until mind-lock
    ;perform instrument=zills   another instrument (the profile's `instrument` otherwise)
                                a room that refuses a song (a bank's teller: "now isn't the best time to be playing") sends it home once, the profile's `home`, to play there
                                an instrument the game calls dirty at PLAY is cleaned once per run with the profile's `instrument_cloth` (REMOVE, WIPE when wet, CLEAN, WEAR), then played again; no cloth is said once and the song plays dirty
    ;perform song=ballad        a song of your own instead of the rank's band
    ;perform mood=halting       one style, no search (every style tried by default; mood= alone for the plain style)
    ;perform until=30           stop at that mindstate instead of 34
    ;perform once               exit at mind-lock instead of holding for the drain
    ;perform return             (typed while it runs) stop the song and end

PLAY starts a song that runs on its own, and Performance learns while
it plays (Elanthipedia: Performance skill, Play command; the song per
rank band and the wordings are client/game/perform.py's). The script
PLAYs the band's song — scales to rank 39, arpeggios to 49, and so on
— in the style the game rates nearest "with only the slightest hint
of difficulty": with no mood= a run's first start is followed by a pass
over all nineteen styles (PLAY, the start line's tier, STOP PLAY — no
roundtime, the operator's "it costs nothing to step through each
style", 2026-09-28, #381), again after each lock; off-key, the fixed
default until then, was effortless for Crannach's concerto at 1180 and
taught a sixth of masterful's rate — watches the mindstate, starts the song
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
Stop with:  ;stop perform (the song stopped, a cleanup put), or ;perform return.
"""

# CLEAN passes per cleaning: one took "a very large amount of dirt and
# grime" off and the next PLAY still called the zills dirty (2026-09-20).
CLEAN_PASSES = 3
POLL = 15  # seconds between looks at the story and the mindstate
clock = time.monotonic  # tests replace it

SKILL = "Performance"


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


def fetch_cloth(s, instrument, cloth):
    """The cleaning cloth into a hand: whatever else a hand holds is
    STOWed first (never dropped), then GET. False, said once, when the
    game finds no such cloth on you."""
    hands.free(s, keep=(instrument, cloth), ask=ask)
    answer = ask(s, f"get my {cloth}")
    if any(word in answer.lower() for word in NO_CLOTH):
        s.echo(f"perform: no {cloth} on you — the {instrument} plays dirty")
        return False
    return True


def clean_instrument(s, instrument, cloth):
    """CLEAN the instrument with the cloth in hand (#233): REMOVE it when
    the game wants it held, WIPE it when wet, then CLEAN; worn again if
    removed, the cloth stowed. True when the game said it was cleaned."""
    removed = cleaned = False
    passes = 0
    for _ in range(4 + CLEAN_PASSES):
        answer = ask(s, f"clean my {instrument} with my {cloth}")
        lowered = answer.lower()
        if any(word in lowered for word in CLEANED):
            # One pass took "a very large amount of dirt and grime" off
            # and the next PLAY still called the zills dirty (2026-09-20,
            # the operator's watch): CLEAN again while dirt comes off, up
            # to CLEAN_PASSES, the last line echoed so the wording of a
            # clean instrument gets captured.
            cleaned = True
            passes += 1
            if passes >= CLEAN_PASSES:
                break
            continue
        if cleaned:
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"perform: CLEAN after {passes} pass(es) answered {first!r}")
            break
        if any(word in lowered for word in MUST_HOLD):
            ask(s, f"remove my {instrument}")
            removed = True
        elif any(word in lowered for word in WET):
            ask(s, f"wipe my {instrument} with my {cloth}")
        else:
            s.echo("perform: CLEAN answered nothing known — please report it")
            break
    if removed:
        ask(s, f"wear my {instrument}")
    ask(s, f"stow my {cloth}")
    if cleaned:
        s.echo(f"perform: {instrument} cleaned with the {cloth} ({passes} pass(es))")
    return cleaned


def entry(s):
    return (getattr(s.state, "experience", None) or {}).get("Performance")


def mindstate(s):
    value = entry(s)
    return value["mindstate"] if value else None


def rank(s):
    value = entry(s)
    return value.get("rank") if value else None


def start_song(s, options):
    """PLAY; ("playing", dirty) when the song started (or was already
    running) — dirty True when the game said the instrument's dirt
    weighs on it (#233) — ("no instrument", False) when the game found
    none, ("not here", False) for a room that refuses a song,
    ("unknown", False) otherwise."""
    song = options["song"] or song_for(rank(s))
    answer = ask(s, play_command(song, options["mood"], options["instrument"]))
    lowered = answer.lower()
    dirty = any(word in lowered for word in DIRTY)
    if any(word in lowered for word in STARTED + ALREADY):
        return "playing", dirty
    if any(word in lowered for word in NO_INSTRUMENT):
        return "no instrument", False
    if any(word in lowered for word in NOT_HERE):
        return "not here", False
    if any(word in lowered for word in IN_COMBAT):
        return "in combat", False
    return "unknown", False


def pick_style(s, options):
    """Every style of the song, hardest known first: PLAY, read the
    start line's tier, STOP PLAY — no roundtime either way (#381). The
    first "slightest hint" ends the pass; else the best tier seen wins,
    the harder style on a tie. (style, tier) — (None, None) when no
    style started, the regular start then saying why — and every
    style's tier echoed on one line."""
    song = options["song"] or song_for(rank(s))
    best = None  # (tier index, style)
    seen = []
    for style in STYLES:
        answer = ask(s, play_command(song, style, options["instrument"]))
        if any(word in answer.lower() for word in ALREADY):
            stop_song(s)
            answer = ask(s, play_command(song, style, options["instrument"]))
        lowered = answer.lower()
        if any(word in lowered for word in NO_INSTRUMENT + NOT_HERE + IN_COMBAT):
            return None, None
        tier = difficulty(answer)
        if any(word in lowered for word in STARTED):
            stop_song(s)
        seen.append(f"{style or 'plain'} {tier or '?'}")
        if tier is not None and (best is None or TIERS.index(tier) < best[0]):
            best = (TIERS.index(tier), style)
        if tier == "slightest":
            break
    s.echo(f"perform: the {song}'s styles — {', '.join(seen)}")
    if best is None:
        return None, None
    return best[1], TIERS[best[0]]


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
    return travel.go(s, home, repr(home))


def stop_song(s):
    ask(s, "stop play")


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


def run(s, options, walker=walk_home):
    """The trainer loop with one step: the song started when none plays,
    then one POLL of the story and the mindstate; STOP PLAY at every end."""
    if not options["instrument"]:
        options["instrument"] = instrument_of(s)
    if not options["instrument"]:
        s.echo("perform: no instrument — instrument=<noun>, or the profile's")
        return
    # No mood= given: every style tried after the first start (and the
    # cleaning it may call for), and again after each lock (#381).
    search = options["mood"] is None
    if search:
        options["mood"] = ""
    song = SimpleNamespace(
        playing=False,
        moved=False,  # walked home once for a room that refuses a song
        cleaned=False,  # the instrument cleaned once for a dirt warning (#233)
        search_due=search,
        sent=False,  # a PLAY went out: the end stops it, whatever came after
    )

    def step(s):
        if not song.playing:
            song.sent = True
            outcome, dirty = start_song(s, options)
            song.sent = outcome == "playing"  # a refused PLAY plays nothing
            if outcome == "no instrument":
                return f"no {options['instrument']} on you"
            if outcome == "not here":
                # A bank's teller refused the song (2026-09-20): once,
                # walk to the profile's home and play there.
                home = home_of(s)
                if song.moved or not home:
                    return "the game refuses a song here" + (
                        " and at home too"
                        if song.moved
                        else " and the profile names no home"
                    )
                s.echo(f"perform: the game refuses a song here — walking home ({home})")
                song.moved = True
                if not walker(s, home):
                    return "could not walk home"
                return None
            if outcome == "in combat":
                # The game refused the song for a fight the parser had
                # not shown yet (2026-09-20, right after a ;reexec, #243).
                return "in combat"
            if outcome == "unknown":
                return "PLAY answered nothing known — please report it"
            if dirty and not song.cleaned:
                # The game says the dirt weighs on the song (#233): once
                # per run, the profile's cloth cleans the instrument and
                # the song starts over; no cloth means playing dirty.
                song.cleaned = True
                cloth = cloth_of(s)
                if not cloth:
                    s.echo(
                        f"perform: the {options['instrument']} is dirty and the "
                        "profile names no cloth (instrument_cloth) — playing on"
                    )
                elif fetch_cloth(s, options["instrument"], cloth):
                    stop_song(s)
                    clean_instrument(s, options["instrument"], cloth)
                    return None
            if song.search_due:
                song.search_due = False
                stop_song(s)
                style, tier = pick_style(s, options)
                if style is not None:
                    options["mood"] = style
                    s.echo(f"perform: {style or 'the plain style'} plays {tier}")
                return None
            song.playing = True
            s.echo(
                f"perform: playing {options['song'] or song_for(rank(s))} "
                f"{options['mood'] or 'in the plain style'} on the "
                f"{options['instrument']} (Performance {mindstate(s)}/34)"
            )
        outcome = watch(s, POLL, until=options["until"])
        if outcome == "stop":
            return None  # the loop says why: the return, or the danger
        if outcome == "ended":
            song.playing = False
        elif trainer.locked(s, SKILL, options["until"]):
            # The watch's "target" (or a lock landed in its gap): the song
            # stopped before the loop holds or ends at it, the styles
            # tried again after the hold — the rank may have moved.
            stop_song(s)
            song.playing = False
            song.search_due = search
        return None

    def finish(s, why):
        # A PLAY sent and the run ended before it was counted playing —
        # ;train killed ;perform in the same second (2026-10-05 00:10) —
        # left the song going and refused the next PREPARE.
        if not (song.playing or song.sent):
            return
        if why is None:  # a ;stop (or a crash): the one put that still goes out
            s.put("stop play", cleanup=True)
        else:
            stop_song(s)

    return trainer.train(
        s,
        "perform",
        SKILL,
        step,
        until=options["until"],
        once=options["once"],
        again="playing again",
        finish=finish,
        ask=ask,
    )


def main(s):
    options = parse_args(s.args or [])
    run(s, options)
