"""Keep an Empath's vela'tohr plant up in a room:  ;plant

    ;plant <room>        walk there (a ;go2 target), take the old plant's wounds, cast a new one
    ;plant               the same where you stand
    ;plant mana=500      the mana prepared (500 by default)
    ;plant focus=phial   the ritual focus (phial by default)
    ;plant return        (typed while it runs) end before the next step; a cast in hand finishes
    ;stop plant          quit at once

What it does
  - An old plant in the room is TOUCHed: its wounds move to you (Empathy), and ;empath self
    heals them.
  - Casts Embrace of the Vela'Tohr: GET the focus, PREPARE EV, INVOKE the focus, CAST, STOW
    the focus, STAND.
  - PERCEIVE reads how long the plant lasts; ;train's `keep_plant` recasts 10 minutes before
    it ends.

When it stops
  - the cast done, or any guild but Empath
  - mana under 50%, the focus not found, the ritual or the cast failing (said)
  - death, a typed return, or ;stop plant

The model and the wordings are client/game/plant.py's; docs/healing.md.
"""

import os

from client.game import guild, hands, plant, travel
from client.game.act import ask, missing, said
from client.game.loop import wants_stop

_NOTES = """
Built from Riphik's casts of 2026-10-03 and 2026-10-04 in the Paladins'
Guild Chambers (map 7890). A first cast waited for a "fully prepared"
line after the INVOKE and lost the spell to the attar burning away;
the second CAST right after the ritual's "Your ritual directs the
energy up into your spell pattern" and the plant formed. PERCEIVE
then said "...will last for about sixty-two roisaen" at 500 mana, and
the cast took mana from 100% to 66%. The operator's rule (#472, #473):
severe wounds page the Empath, lighter ones wait for this plant.
"""

EMPATH_MINUTES = 15  # ;empath self after taking the plant's wounds
READY_POLLS = 30  # one-second looks for the ritual's lines after the INVOKE
PERCEIVE_SECONDS = 4


def parse_args(args):
    options = {"room": "", "mana": plant.MANA, "focus": plant.FOCUS}
    words = []
    for arg in args or []:
        key, sep, value = str(arg).partition("=")
        if sep and key.lower() == "mana" and value.isdigit():
            options["mana"] = int(value)
        elif sep and key.lower() == "focus" and value:
            options["focus"] = value.lower()
        else:
            words.append(str(arg))
    options["room"] = " ".join(words).strip()
    return options


def heal_self(s):
    """;empath self run and waited for, at most EMPATH_MINUTES."""
    if not s.run("empath", ["self"]):
        return
    try:
        waited = 0
        while s.is_running("empath") and waited < EMPATH_MINUTES * 60:
            if s.dead:
                return
            s.sleep(5)
            waited += 5
    finally:
        if s.is_running("empath"):
            s.kill("empath")


def touch(s):
    """The old plant's wounds taken (TOUCH PLANT) and healed with
    ;empath self: "took", "clean" (no wounds on it), or "none" (no
    plant in the room)."""
    if plant.PLANT not in str(getattr(s.state, "room_objs", "") or "").lower():
        return "none"
    answer = ask(s, "touch plant")
    if plant.said(answer, plant.TOOK):
        s.echo("plant: took the plant's wounds — ;empath self")
        heal_self(s)
        return "took"
    if not plant.said(answer, plant.NO_NEED):
        s.echo(f"plant: TOUCH PLANT answered {said(answer)!r}")
    return "clean"


def ritual_done(s, answer):
    """True once the ritual's energy reached the pattern — in the INVOKE's
    own answer or the lines after its roundtime; False when the spell
    was lost or nothing came."""
    if plant.said(answer, plant.LOST):
        return False
    if plant.said(answer, plant.RITUAL):
        return True
    quiet = 0
    while quiet < READY_POLLS:
        line = s.get(timeout=1)
        if line is None:
            quiet += 1
            continue
        if plant.said(line, plant.LOST):
            return False
        if plant.said(line, plant.RITUAL):
            return True
    return False


def cast(s, options):
    """GET the focus, PREPARE, INVOKE, CAST, then STOW the focus and
    STAND: the plant's minutes (PERCEIVE's, else the spell's least), or
    None, said, when it did not form."""
    mana = (getattr(s.state, "vitals", None) or {}).get("mana")
    if mana is not None and mana < plant.MANA_FLOOR:
        s.echo(f"plant: mana {mana}% — the cast waits for {plant.MANA_FLOOR}%")
        return None
    focus = options["focus"]
    if hands.full(s):
        hands.free_one(s)
    answer = ask(s, f"get my {focus}")
    if missing(answer) and not hands.holding(s, focus):
        s.echo(f"plant: no {focus} on you — the ritual needs its focus")
        return None
    formed = False
    try:
        answer = ask(s, f"prepare {plant.SPELL} {options['mana']}")
        if not plant.said(answer, plant.PREPARED):
            s.echo(f"plant: PREPARE answered {said(answer)!r}")
            return None
        answer = ask(s, f"invoke my {focus}")
        if not plant.said(answer, plant.INVOKED):
            s.echo(f"plant: INVOKE answered {said(answer)!r}")
            ask(s, "release spell")
            return None
        s.waitrt()
        if not ritual_done(s, answer):
            s.echo("plant: the ritual never reached the pattern — the spell is lost")
            ask(s, "release spell")
            return None
        answer = ask(s, "cast")
        formed = plant.said(answer, plant.FORMED)
        if not formed:
            s.echo(f"plant: CAST answered {said(answer)!r}")
            return None
    finally:
        ask(s, f"stow my {focus}")
        ask(s, "stand")
    minutes = plant.lasts(ask(s, "perceive", PERCEIVE_SECONDS))
    if minutes is None:
        s.echo(
            f"plant: PERCEIVE gave no roisaen — counting the spell's least, "
            f"{plant.DEFAULT_MINUTES}"
        )
        minutes = plant.DEFAULT_MINUTES
    return minutes


def run(s, options, db=None, walk=None):
    """Why the run ended: "cast", "not an empath", "no walk", "return",
    "dead" or "failed"."""
    if not guild.is_empath(guild.character_guild(s)):
        s.echo("plant: Embrace of the Vela'Tohr is an Empath's spell")
        return "not an empath"
    room = options["room"]
    if room and not travel.go(s, room, repr(room), db=db, walk=walk):
        return "no walk"
    if wants_stop(s):
        return "return"
    touch(s)
    if s.dead:
        return "dead"
    if wants_stop(s):
        return "return"
    minutes = cast(s, options)
    if minutes is None:
        return "failed"
    where = room or str(travel.here(s, db) or "")
    name = getattr(s.state, "name", None) or ""
    plant.record(name, where, minutes, os.getpid())
    s.echo(
        f"plant: a vela'tohr plant stands at {where or 'here'} for about {minutes} min"
    )
    return "cast"


def main(s):
    run(s, parse_args(s.args))
