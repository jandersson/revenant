"""Train magic on the spot — cast, charge the cambrinth, perceive:  ;cast

    ;cast                     train the profile's train_casting skills with its buffs on the mana ramp, the cambrinth charged, POWER once a minute, until the skills lock
    ;cast spell=<name>        cast that spell alone (a self-cast buff), for the skill it uses
    ;cast skill=<Skill>       train that skill alone, with the first buff that uses it
    ;cast until=30            stop at that mindstate instead of 34
    ;cast once                exit at the lock instead of holding for the drain
    ;cast nopower             no POWER between casts
    ;cast return              (typed while it runs) finish the cast in hand and end

The hunt's cast loop without the hunt (#225): what a gondola ride, a
ferry crossing or a wait at an altar can train while the character
stands still. Every `cast_gap` seconds (the profile's, 60 by default)
it does what ;hunt does between swings through client/game/buffs.py
— picks the named skill with the emptiest pool and the first buff
DISCERN says uses it (#374), GETs and CHARGEs the profile's
`cambrinth` piece with `cambrinth_mana` (the charge trains Arcana),
PREPAREs the buff at its ramped mana, INVOKEs the piece, CASTs, stows
it — and once a minute POWERs, which
trains Attunement (Elanthipedia: Attunement skill, Perceive command:
once per room per minute, so standing still it pays at most once a
minute; whether a room pays again without leaving it is measured on
the first run). The mana fed starts two under DISCERN's estimate
(the piece's charge counted) and rises by two per cast up to it until
the game warns of strain or a cast fails, then holds one step under
(Elanthipedia's magic category: fewer, larger casts teach more). Only
training casts go out: a buff that lapses is not kept up. A profile
naming no skill in `train_casting` trains every skill its buffs use.
It watches the skills in the exp window — the skills trained, Arcana
when a piece is named, Attunement when it POWERs — and at mind-lock of all
of them holds until enough drains to be worth casting again; `once`
exits at the lock (client/game/trainer.py, the loop every trainer
runs). Stops on death, on hostiles in the room, when mana
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

from client.game import buffs
from client.game import trainer
from client.game.act import ask, unknown
from client.game.loop import pause

MIND_LOCK = 34
POLL = 5  # seconds between looks while waiting for the gap
POWER_GAP = 60  # seconds between POWERs: a room pays once a minute
MANA_WAIT = 600  # seconds of mana under the floor before giving up
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


def skills_watched(profile, options, state):
    """The skills whose mindstates decide the lock: the skills trained
    (as DISCERN spells them once it has named each buff's, the names
    the profile gives before), Arcana for a cambrinth piece, Attunement
    when POWERing."""
    watched = list(buffs.training_buffs(profile, state)) or [
        name for name in buffs.training_skills(profile) if name.lower() != "all"
    ]
    if profile.get("cambrinth"):
        watched.append("Arcana")
    if options["power"]:
        watched.append("Attunement")
    return watched


def cast_profile(profile, options):
    """The profile as the cast loop sees it: spell= as the only buff,
    skill= as the only skill trained; with neither named, the profile's
    `train_casting`, or every skill of the buffs when it names none —
    and so the skill spell= uses, when that is all that is given."""
    shaped = dict(profile)
    if options["spell"]:
        shaped["buffs"] = [options["spell"]]
    if options["skill"]:
        shaped["train_casting"] = [options["skill"]]
    elif options["spell"] or not buffs.training_skills(profile):
        shaped["train_casting"] = ["all"]
    return shaped


def performing(answer):
    """True when the game refused because a song is playing."""
    return any(phrase in (answer or "").lower() for phrase in PERFORMING)


def run(s, words, profile):
    options = parse_args(words)
    shaped = cast_profile(profile, options)
    if not shaped["buffs"]:
        s.echo(
            "cast: the profile names no buff and no spell= was given — nothing to cast"
        )
        return
    return loop(s, options, shaped)


def loop(s, options, shaped):
    """The trainer loop with one step: the casts due, then the POLL gap.
    The watched skills are read afresh every round (they grow after the
    first DISCERN and shrink when a buff or POWER is dropped for the
    run), and the window need not list them yet (ensure=False): a
    skill it has not listed never held the lock up."""
    state = buffs.BuffState()
    skills = skills_watched(shaped, options, state)

    busy = {"song": False}
    last_power = None
    low_since = None

    def report(what, answer):
        if performing(answer):
            busy["song"] = True
            return
        unknown(s, "cast", what, answer)

    def step(s):
        nonlocal last_power, low_since
        if state.training_off:
            return "the training casts are off for this run"
        mana = (getattr(s.state, "vitals", None) or {}).get("mana")
        if mana is not None and mana < buffs.MANA_FLOOR:
            low_since = low_since or clock()
            if clock() - low_since >= MANA_WAIT:
                return f"mana under {buffs.MANA_FLOOR}% for ten minutes"
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
            last_power = clock()
        if not busy["song"]:
            # DISCERN once, before the first cast: the game's estimate of
            # the most mana this caster can weave is the ramp's ceiling —
            # the hunt's ramp climbed past it and backfired five times in
            # one evening, each a nerve wound (2026-09-20).
            buffs.discern_slots(s, shaped, state, ask, "cast", report)
            buffs.cast_buffs(s, shaped, state, ask, "cast", report, upkeep=False)
        if busy["song"]:
            return (
                "the game refuses spellwork while a song plays — "
                "stop it first (;perform return)"
            )
        pause(s, POLL)  # a return or a danger in it: the loop says why
        return None

    def finish(s, why):
        # A ;stop between the GET and the stow left the anklet in hand
        # (2026-09-20): the put-back goes out even after the stop.
        buffs.put_back_if_held(s, shaped, "cast")

    s.echo(
        f"cast: {', '.join(shaped['buffs'])} for "
        f"{', '.join(buffs.training_skills(shaped))}"
        + (f" with the {shaped['cambrinth']}" if shaped.get("cambrinth") else "")
        + (", POWER between casts" if options["power"] else "")
        + f" — watching {', '.join(skills) or 'nothing'}"
    )
    return trainer.train(
        s,
        "cast",
        lambda: skills_watched(shaped, options, state),
        step,
        until=options["until"],
        once=options["once"],
        again="casting again",
        finish=finish,
        ensure=False,
    )


def main(s):
    from client.game.profile import load_profile

    profile = load_profile(getattr(s.state, "name", None) or "")
    run(s, list(s.args or []), profile)
