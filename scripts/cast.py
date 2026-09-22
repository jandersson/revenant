"""Train magic on the spot — cast, charge the cambrinth, perceive:  ;cast

    ;cast                     cast the profile's first buff on the mana ramp with the cambrinth, POWER once a minute, until the skills lock
    ;cast spell=<name>        another spell than the profile's first buff (a self-cast buff)
    ;cast skill=<Skill>       the skill the casts train (the profile's train_casting otherwise)
    ;cast until=30            stop at that mindstate instead of 34
    ;cast once                exit at the lock instead of holding for the drain
    ;cast nopower             no POWER between casts
    ;cast return              (typed while it runs) finish the cast in hand and end

The hunt's cast loop without the hunt (#225): what a gondola ride, a
ferry crossing or a wait at an altar can train while the character
stands still. Every `cast_gap` seconds (the profile's, 60 by default)
it does what ;hunt does between swings through client/game/buffs.py
— GET and CHARGE the profile's `cambrinth` piece with `cambrinth_mana`
(the charge trains Arcana), PREPARE the spell at the ramped mana,
INVOKE the piece, CAST, stow it — and once a minute POWERs, which
trains Attunement (Elanthipedia: Attunement skill, Perceive command:
once per room per minute, so standing still it pays at most once a
minute; whether a room pays again without leaving it is measured on
the first run). The mana fed rises by two per cast until the game
warns of strain or a cast fails, then holds one step under
(Elanthipedia's magic category: fewer, larger casts teach more). It
watches the skills in the exp window — the profile's `train_casting`
(the spell's book: Augmentation for Heroic Strength), Arcana when a
piece is named, Attunement when it POWERs — and at mind-lock of all
of them holds until enough drains to be worth casting again; `once`
exits at the lock. Stops on death, on hostiles in the room, when mana
sits under the floor for ten minutes, and when the profile names no
buff and no spell= is given. Never a targeted spell: those want a prey
(;hunt). Stopped between the GET and the stow, it puts the piece back
(WEAR or STOW) on its way out, so nothing stays in hand. A song
refuses it all — "You are a bit too busy performing to
do that.", "You should stop playing before you do that." (captured
2026-09-20 with ;perform on the gondola) — so it stops and says to end
the song first. Wordings are the hunt's captures (client/game/buffs.py).
Stop with:  ;stop cast, or ;cast return.
"""

import time

from client.game import buffs, probe
from client.game.loop import danger, pause, wants_stop

MIND_LOCK = 34
RESUME_BELOW = 28  # resume once enough has drained to be worth a cast
POLL = 5  # seconds between looks while waiting for the gap
LOCK_POLL = 30
POWER_GAP = 60  # seconds between POWERs: a room pays once a minute
MANA_WAIT = 600  # seconds of mana under the floor before giving up
COLLECT_SECONDS = 3
TAIL_SECONDS = 1.5
PERCEIVED = "reach out with your"  # captured 2026-09-12: "You reach out with your weak senses ..."
# The game refuses spellwork while a song plays (captured 2026-09-20 on
# the gondola with ;perform running): POWER "You are a bit too busy
# performing to do that.", CHARGE and PREPARE "You should stop playing
# before you do that." — so the song and the casts cannot share a ride.
PERFORMING = ("too busy performing", "stop playing before you do that")
clock = time.monotonic  # tests replace it


def parse_args(args):
    options = {
        "spell": "",
        "skill": "",
        "until": MIND_LOCK,
        "once": False,
        "power": True,
    }
    for arg in args or []:
        key, sep, value = str(arg).partition("=")
        key = key.lower()
        if sep and key == "until" and value.isdigit():
            options["until"] = int(value)
        elif sep and key in ("spell", "skill") and value.strip():
            options[key] = value.strip()
        elif key == "once":
            options["once"] = True
        elif key == "nopower":
            options["power"] = False
    return options


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def skills_watched(profile, options):
    """The skills whose mindstates decide the lock: the training skill,
    Arcana for a cambrinth piece, Attunement when POWERing."""
    watched = []
    if profile["train_casting"]:
        watched.append(profile["train_casting"])
    if profile.get("cambrinth"):
        watched.append("Arcana")
    if options["power"]:
        watched.append("Attunement")
    return watched


def mindstates(s, skills):
    experience = getattr(s.state, "experience", None) or {}
    return {
        skill: experience[skill].get("mindstate")
        for skill in skills
        if isinstance(experience.get(skill), dict)
    }


def all_locked(s, skills, until):
    """True when every watched skill the window lists sits at `until`
    or above (a skill the window has not listed does not hold it up)."""
    values = mindstates(s, skills)
    return bool(values) and all(value >= until for value in values.values())


def any_drained(s, skills, floor):
    values = mindstates(s, skills)
    return any(value <= floor for value in values.values())


def cast_profile(profile, options):
    """The profile as the cast loop sees it: the spell as the only buff,
    the skill as train_casting."""
    shaped = dict(profile)
    shaped["buffs"] = (
        [options["spell"]] if options["spell"] else list(profile["buffs"][:1])
    )
    if options["skill"]:
        shaped["train_casting"] = options["skill"]
    return shaped


def performing(answer):
    """True when the game refused because a song is playing."""
    return any(phrase in (answer or "").lower() for phrase in PERFORMING)


def hold_at_lock(s, skills, until):
    s.echo(f"cast: {', '.join(skills)} mind-locked — holding until one drains")
    floor = min(RESUME_BELOW, until - 1)
    while True:
        if not pause(s, LOCK_POLL):
            return False
        if any_drained(s, skills, floor):
            s.echo("cast: drained — casting again")
            return True


def run(s, words, profile):
    options = parse_args(words)
    shaped = cast_profile(profile, options)
    if not shaped["buffs"]:
        s.echo(
            "cast: the profile names no buff and no spell= was given — nothing to cast"
        )
        return
    try:
        loop(s, options, shaped)
    finally:
        # A ;stop between the GET and the stow left the anklet in hand
        # (2026-09-20): the put-back goes out even after the stop.
        buffs.put_back_if_held(s, shaped, "cast")


def loop(s, options, shaped):
    skills = skills_watched(shaped, options)
    state = buffs.BuffState()
    state.cast_at[shaped["buffs"][0]] = clock() - buffs.cast_gap(
        shaped
    )  # first cast at once

    busy = {"song": False}

    def report(what, answer):
        if performing(answer):
            busy["song"] = True
            return
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(f"cast: unrecognized {what} answer {first!r} — please report it")

    s.echo(
        f"cast: {shaped['buffs'][0]} for {shaped['train_casting'] or 'Arcana'}"
        + (f" with the {shaped['cambrinth']}" if shaped.get("cambrinth") else "")
        + (", POWER between casts" if options["power"] else "")
        + f" — watching {', '.join(skills) or 'nothing'}"
    )
    last_power = None
    low_since = None
    while True:
        reason = danger(s)
        if reason:
            s.echo(f"cast: {reason} — stopping")
            return
        if wants_stop(s):
            s.echo("cast: stopping as asked")
            return
        if all_locked(s, skills, options["until"]):
            if options["once"]:
                s.echo(f"cast: {', '.join(skills)} at {options['until']}/34 — done")
                return
            if not hold_at_lock(s, skills, options["until"]):
                s.echo("cast: stopping")
                return
            continue
        if state.training_off:
            s.echo("cast: the training casts are off for this run — stopping")
            return
        mana = (getattr(s.state, "vitals", None) or {}).get("mana")
        if mana is not None and mana < buffs.MANA_FLOOR:
            low_since = low_since or clock()
            if clock() - low_since >= MANA_WAIT:
                s.echo(
                    f"cast: mana under {buffs.MANA_FLOOR}% for ten minutes — stopping"
                )
                return
        else:
            low_since = None
        if options["power"] and (
            last_power is None or clock() - last_power >= POWER_GAP
        ):
            answer = ask(s, "power")
            if performing(answer):
                busy["song"] = True
            elif PERCEIVED not in answer:
                s.echo("cast: POWER answered no perceive line — no more POWER this run")
                options["power"] = False
                skills = skills_watched(shaped, options)
            last_power = clock()
        if not busy["song"]:
            # DISCERN once, before the first cast: the game's estimate of
            # the most mana this caster can weave is the ramp's ceiling —
            # the hunt's ramp climbed past it and backfired five times in
            # one evening, each a nerve wound (2026-09-20).
            buffs.discern_slots(s, shaped, state, ask, "cast", report)
            buffs.cast_buffs(s, shaped, state, ask, "cast", report)
        if busy["song"]:
            s.echo(
                "cast: the game refuses spellwork while a song plays — "
                "stop it first (;perform return) — stopping"
            )
            return
        if not pause(s, POLL):
            s.echo("cast: stopping")
            return


def main(s):
    from client.game.profile import load_profile

    profile = load_profile(getattr(s.state, "name", None) or "")
    run(s, list(s.args or []), profile)
