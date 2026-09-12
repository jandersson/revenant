"""Self-cast buffs kept up by a trainer, and the training casts that
climb a magic skill — the cast helpers ;hunt grew on 2026-09-12,
shared so ;athletics can fill its award-timer waits the same way
(dr-scripts casts buffs around its climbs, #177).

cast_buffs() casts every profile buff that is not running (PREPARE,
wait for the pattern, CAST) and, when the profile names a magic skill
in `train_casting`, recasts the first buff between actions while that
skill sits below mind-lock and mana holds, feeding more mana each time
until the game warns of strain or a cast fails, then holding one step
under. The Spells window (state.active_spells, client/engine/xml_data.py)
says when a buff has run out; a session whose parser predates that
state recasts on BUFF_MINUTES instead.

Captured 2026-09-12 with Heroic Strength on a circle-1 Paladin: "You
begin chanting a prayer to invoke the Heroic Strength spell." / "You
gesture." / "The spell takes effect, the invisible flame of your soul
intertwining with your flesh." — and, recast while running, "Your
soul and body intertwine tighter, the bond renewed by the spell."; 5
mana "barely backfires" at that circle, so the ramp starts at the
minimum and climbs by MANA_STEP. The failure wordings are assumptions
until captured. Callers pass their own ask() (client/game/probe.py
with their collection windows) and a report(what, answer) for an
answer outside the tables.
"""

from time import monotonic

from client.game import probe
from client.game.probe import classify

MIND_LOCK = 34
PREPARE_SECONDS = 8  # from "begin chanting" to a castable pattern
BUFF_MINUTES = 10  # the wiki's shortest duration for the intro buffs
PREPARE_OUTCOMES = (
    (
        "failed",
        ("don't know", "unable to", "can't prepare", "cannot prepare", "no such"),
    ),
    # Too much mana asked for (the wiki's Prepare page wording; not
    # yet observed here): the pattern is prepared but may not cast.
    ("strain", ("have to strain",)),
    ("ok", ("you begin", "gathering energy", "prepar")),
)
CAST_OUTCOMES = (
    ("failed", ("pattern collapses", "backfire", "not enough mana", "nothing to cast")),
    ("ok", ("takes effect", "renewed", "you gesture")),
)
# Training casts: Elanthipedia's magic category — "fewer but larger
# spellcasts are more efficient in terms of experience" — so the mana
# fed grows by MANA_STEP each cast until the strain warning or a
# failed cast, then holds one step under.
MANA_STEP = 2  # 5 backfired on a circle-1 Paladin (2026-09-12)
MANA_FLOOR = 40  # % of mana under which no training cast goes out
CAST_GAP_SECONDS = 20  # between training casts, so the fight goes on


class BuffState:
    """What one run remembers about its casts."""

    def __init__(self):
        self.cast_at = {}  # buff -> monotonic() of its last cast
        self.buffs_off = set()  # buffs that refused this run
        self.mana = 0  # the next training cast's mana; 0 is the minimum
        self.mana_cap = None  # one step under the strain, once met
        self.training_off = False  # even the minimum failed this run


def locked(state, skills):
    """True when every named skill sits at mind-lock in the exp window;
    a skill the window has not shown yet counts as unlocked."""
    if not skills:
        return False
    experience = getattr(state, "experience", None) or {}
    return all(
        (experience.get(skill) or {}).get("mindstate", 0) >= MIND_LOCK
        for skill in skills
    )


def buff_running(s, spell, state):
    """True while the buff needs no cast: the Spells window lists it,
    or — for a parser without that window — its last cast is younger
    than BUFF_MINUTES."""
    active = getattr(s.state, "active_spells", None)
    if isinstance(active, dict):
        return spell.lower() in {name.lower() for name in active}
    cast = state.cast_at.get(spell)
    return cast is not None and monotonic() - cast < BUFF_MINUTES * 60


def cast_once(s, spell, mana, state, ask, report):
    """PREPARE (with a mana amount when given), wait for the pattern,
    CAST. "refused" (the spell cannot be prepared), "collapsed" (the
    cast failed), "strained" (cast, but the mana asked was too much) or
    "ok"."""
    answer = ask(s, f"prepare {spell} {mana}" if mana else f"prepare {spell}")
    outcome = classify(answer, PREPARE_OUTCOMES)
    if outcome == "failed":
        return "refused"
    probe.collect(s, PREPARE_SECONDS, until="fully prepared")
    answer = ask(s, "cast")
    cast = classify(answer, CAST_OUTCOMES)
    if cast == "failed":
        return "collapsed"
    if cast is None:
        report("cast", answer)
    state.cast_at[spell] = monotonic()
    return "strained" if outcome == "strain" else "ok"


def training_cast_due(s, profile, state):
    """True when the first buff should be recast for the skill named
    in train_casting: the skill is below lock, mana is above the floor,
    and the last cast is CAST_GAP_SECONDS old."""
    skill = profile["train_casting"]
    if not skill or not profile["buffs"] or state.training_off:
        return False
    if locked(s.state, [skill]):
        return False
    mana = (getattr(s.state, "vitals", None) or {}).get("mana")
    if mana is not None and mana < MANA_FLOOR:
        return False
    last = state.cast_at.get(profile["buffs"][0])
    return last is None or monotonic() - last >= CAST_GAP_SECONDS


def cast_buffs(s, profile, state, ask, prefix="buffs", report=None):
    """Every profile buff not running: PREPARE it, wait for the pattern,
    CAST. A refusal takes that buff off for the run, said once. The
    first buff is cast again for training when training_cast_due says
    so, feeding state.mana, which climbs a step per cast until the
    strain warning or a collapsed cast and then holds one step under."""
    if report is None:

        def report(what, answer):
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"{prefix}: unrecognized {what} answer {first!r} — please report it")

    for index, spell in enumerate(profile["buffs"]):
        if spell in state.buffs_off:
            continue
        training = index == 0 and training_cast_due(s, profile, state)
        if not training and buff_running(s, spell, state):
            continue
        mana = state.mana if training else 0
        result = cast_once(s, spell, mana, state, ask, report)
        if result == "refused":
            s.echo(f"{prefix}: cannot prepare {spell} — off for this run")
            state.buffs_off.add(spell)
        elif not training:
            if result == "collapsed":
                s.echo(f"{prefix}: {spell} did not cast — off for this run")
                state.buffs_off.add(spell)
            else:
                s.echo(f"{prefix}: cast {spell}")
        elif result == "ok":
            s.echo(
                f"{prefix}: cast {spell} at {mana or 'minimum'} mana "
                f"for {profile['train_casting']}"
            )
            if state.mana_cap is None:
                state.mana += MANA_STEP
        elif mana == 0:
            # Even the minimum failed (a circle-1 Paladin's 5 mana
            # "barely backfires", 2026-09-12): no more training casts.
            state.training_off = True
            s.echo(f"{prefix}: {spell} fails at minimum mana — training casts off")
        else:
            state.mana = state.mana_cap = mana - MANA_STEP
            s.echo(
                f"{prefix}: {spell} at {mana} mana was too much ({result}) — "
                f"holding at {state.mana or 'minimum'}"
            )
