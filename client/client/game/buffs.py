"""Self-cast buffs kept up by a trainer, and the training casts that
climb a magic skill — the cast helpers ;hunt grew on 2026-09-12,
shared so ;athletics can fill its award-timer waits the same way
(dr-scripts casts buffs around its climbs, #177).

cast_buffs() casts every profile buff that is not running (PREPARE,
wait for the pattern, CAST) and, when the profile names a magic skill
in `train_casting`, recasts the first buff between actions while that
skill sits below mind-lock and mana holds, feeding more mana each time
until the game warns of strain or a cast fails, then holding one step
under — at most one cast per the profile's `cast_gap` seconds (60 by
default: at 20 the first badger fight was seven swings to the badger's
42 in four minutes, a cambrinth cycle being eight commands, 2026-09-14,
#189). The Spells window (state.active_spells, client/engine/xml_data.py)
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

Cambrinth rides the training cast when the profile names a piece
(`cambrinth`, a held noun such as "flake", and `cambrinth_mana`, the
mana per charge — the piece's capacity): GET it, CHARGE it (the charge
is what trains Arcana: Elanthipedia's Cambrinth and Arcana pages, and
one mana on a 1-capacity flake moved Arcana 1.00 to 1.36 on
2026-09-14), PREPARE, INVOKE it so the stored mana feeds the cast
instead of decaying, CAST, stow it. Captured on Cecil's round
cambrinth flake, 2026-09-14: "You are able to channel all the energy
into the flake. / The cambrinth flake absorbs all of the energy."; a
full piece "is already holding as much power as you could possibly
charge it with. / Your harnessed energy dissipates uselessly."; a piece
that outranks the skill (the 32-capacity armband at Arcana 1) "You
fail to channel any of the energy into the armband."; a worn piece
"Try though you may, you find it too clumsy to charge the cambrinth
armband while wearing it."; INVOKE "You reach for its center and forge
a magical link to it, readying all of its mana for your use."; the cast
"Your cambrinth flake emits a loud *snap* as it discharges all its
power to aid your spell." Herilo's Artifacts sells the pieces by
capacity; only the 1- and 5-mana ones work at 0 ranks.

A debilitation spell (the profile's `debilitation`, "Stun Foe" for a
Paladin) is cast at the prey the same way — cast_debilitation(), with
a mana ramp of its own — and takes turns with the training cast when
both are due, so a swing never carries two casts; the caller passes
the target. Debilitation "is trained in combat, by casting spells on
enemies" (Elanthipedia: Debilitation skill), and Stun Foe's cast line
is the wiki's until captured (#192).
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
    ("ok", ("takes effect", "renewed", "you gesture", "slams into")),
)
# Training casts: Elanthipedia's magic category — "fewer but larger
# spellcasts are more efficient in terms of experience" — so the mana
# fed grows by MANA_STEP each cast until the strain warning or a
# failed cast, then holds one step under.
MANA_STEP = 2  # 5 backfired on a circle-1 Paladin (2026-09-12)
# Cambrinth answers, failures before successes: a full piece's answer
# still says "channel all the energy" on its first line.
GET_OUTCOMES = (
    ("missing", ("what were you referring", "could not find", "referring to")),
    ("ok", ("you get", "already holding", "in your hand")),
)
CHARGE_OUTCOMES = (
    ("worn", ("too clumsy",)),
    ("full", ("already holding as much power", "dissipates uselessly")),
    ("failed", ("fail to channel any",)),
    ("ok", ("absorbs all of the energy", "channel all the energy", "absorbs")),
)
MANA_FLOOR = 40  # % of mana under which no training cast goes out
CAST_GAP_SECONDS = 60  # between training casts, for a profile without cast_gap


class BuffState:
    """What one run remembers about its casts."""

    def __init__(self):
        self.cast_at = {}  # buff -> monotonic() of its last cast
        self.buffs_off = set()  # buffs that refused this run
        self.mana = 0  # the next training cast's mana; 0 is the minimum
        self.mana_cap = None  # one step under the strain, once met
        self.training_off = False  # even the minimum failed this run
        self.cambrinth_off = False  # the piece refused this run, said once
        self.debilitation_mana = 0  # the next debilitation cast's mana (#192)
        self.debilitation_cap = None  # one step under its strain, once met
        self.debilitation_off = False  # the spell refused this run, said once
        self.last_training = None  # "buff" or "debilitation": whose turn it was


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


def charge_cambrinth(s, profile, state, ask, prefix, report):
    """GET the profile's cambrinth piece and CHARGE it for Arcana;
    True when it holds mana for the coming cast (charged now, or
    already full). A piece the game will not charge — missing, worn,
    or outranking the skill — is off for the run, said once; a locked
    Arcana skips the charge. The piece stays in hand for INVOKE."""
    noun = profile.get("cambrinth") or ""
    if not noun or state.cambrinth_off or locked(s.state, ["Arcana"]):
        return False
    answer = ask(s, f"get my {noun}")
    if classify(answer, GET_OUTCOMES) == "missing":
        s.echo(f"{prefix}: no {noun} to charge — cambrinth off for this run")
        state.cambrinth_off = True
        return False
    mana = int(profile.get("cambrinth_mana") or 1)
    answer = ask(s, f"charge my {noun} {mana}")
    outcome = classify(answer, CHARGE_OUTCOMES)
    if outcome == "worn":
        s.echo(
            f"{prefix}: the {noun} cannot be charged while worn — cambrinth off for this run"
        )
    elif outcome == "failed":
        s.echo(
            f"{prefix}: the {noun} outranks Arcana (nothing channelled) — cambrinth off for this run"
        )
    elif outcome == "full":
        return True
    elif outcome == "ok":
        s.echo(f"{prefix}: charged the {noun} with {mana} mana for Arcana")
        return True
    else:
        report("charge", answer)
        return True
    state.cambrinth_off = True
    ask(s, f"stow my {noun}")
    return False


def cast_once(s, spell, mana, state, ask, report, invoke=None, target=""):
    """PREPARE (with a mana amount when given), wait for the pattern,
    INVOKE the cambrinth piece when one is charged (`invoke`, its
    noun), CAST (at `target` when one is named), and stow the piece.
    "refused" (the spell cannot be
    prepared), "collapsed" (the cast failed), "strained" (cast, but the
    mana asked was too much) or "ok"."""
    answer = ask(s, f"prepare {spell} {mana}" if mana else f"prepare {spell}")
    outcome = classify(answer, PREPARE_OUTCOMES)
    if outcome == "failed":
        if invoke:
            ask(s, f"stow my {invoke}")
        return "refused"
    probe.collect(s, PREPARE_SECONDS, until="fully prepared")
    if invoke:
        ask(s, f"invoke my {invoke}")
    answer = ask(s, f"cast {target}" if target else "cast")
    cast = classify(answer, CAST_OUTCOMES)
    if invoke:
        ask(s, f"stow my {invoke}")
    if cast == "failed":
        return "collapsed"
    if cast is None:
        report("cast", answer)
    state.cast_at[spell] = monotonic()
    return "strained" if outcome == "strain" else "ok"


def training_cast_due(s, profile, state):
    """True when the first buff should be recast for the skill named
    in train_casting: the skill is below lock, mana is above the floor,
    and the last cast is the profile's cast_gap seconds old
    (CAST_GAP_SECONDS for a profile without the key, #189)."""
    skill = profile["train_casting"]
    piece = profile.get("cambrinth") and not state.cambrinth_off
    if not (skill or piece) or not profile["buffs"] or state.training_off:
        return False
    if skill and locked(s.state, [skill]):
        return False
    if not skill and locked(s.state, ["Arcana"]):
        return False  # the cambrinth was the only reason to recast
    mana = (getattr(s.state, "vitals", None) or {}).get("mana")
    if mana is not None and mana < MANA_FLOOR:
        return False
    last = state.cast_at.get(profile["buffs"][0])
    return last is None or monotonic() - last >= cast_gap(profile)


def cast_gap(profile):
    """Seconds between training casts: the profile's cast_gap, or
    CAST_GAP_SECONDS for a profile without the key (#189)."""
    gap = profile.get("cast_gap")
    return CAST_GAP_SECONDS if gap is None else float(gap)


def debilitation_due(s, profile, state):
    """True when the profile's debilitation spell should go out at the
    prey: one is named and has not refused this run, Debilitation sits
    below lock, mana is above the floor, and its last cast is the
    cast gap old (#192)."""
    spell = profile.get("debilitation") or ""
    if not spell or state.debilitation_off or locked(s.state, ["Debilitation"]):
        return False
    mana = (getattr(s.state, "vitals", None) or {}).get("mana")
    if mana is not None and mana < MANA_FLOOR:
        return False
    last = state.cast_at.get(spell)
    return last is None or monotonic() - last >= cast_gap(profile)


def cast_debilitation(s, profile, state, ask, prefix, report, target=""):
    """PREPARE the profile's debilitation spell with its ramp's mana and
    CAST it at the target (the prey's noun; "" casts at whatever is
    engaged). The mana climbs by MANA_STEP per cast that took until the
    strain warning or a collapse, then holds one step under; a collapse
    at the minimum turns the spell off for the run, said once (#192)."""
    spell = profile["debilitation"]
    mana = state.debilitation_mana
    result = cast_once(s, spell, mana, state, ask, report, target=target)
    state.last_training = "debilitation"
    if result == "refused":
        s.echo(f"{prefix}: cannot prepare {spell} — off for this run")
        state.debilitation_off = True
    elif result == "ok":
        s.echo(
            f"{prefix}: cast {spell} at {target or 'the foe'} with "
            f"{mana or 'minimum'} mana for Debilitation"
        )
        if state.debilitation_cap is None:
            state.debilitation_mana += MANA_STEP
    elif mana == 0:
        state.debilitation_off = True
        s.echo(f"{prefix}: {spell} fails at minimum mana — off for this run")
    else:
        state.debilitation_mana = state.debilitation_cap = mana - MANA_STEP
        s.echo(
            f"{prefix}: {spell} at {mana} mana was too much ({result}) — "
            f"holding at {state.debilitation_mana or 'minimum'}"
        )


def cast_buffs(s, profile, state, ask, prefix="buffs", report=None, train=True):
    """Every profile buff not running: PREPARE it, wait for the pattern,
    CAST. A refusal takes that buff off for the run, said once. The
    first buff is cast again for training when training_cast_due says
    so (and `train` allows it — a caller whose debilitation cast took
    this turn passes False), feeding state.mana, which climbs a step
    per cast until the strain warning or a collapsed cast and then
    holds one step under. True when any cast went out."""
    if report is None:

        def report(what, answer):
            first = (answer.strip().splitlines() or ["(silence)"])[0]
            s.echo(f"{prefix}: unrecognized {what} answer {first!r} — please report it")

    cast = False
    for index, spell in enumerate(profile["buffs"]):
        if spell in state.buffs_off:
            continue
        training = train and index == 0 and training_cast_due(s, profile, state)
        if not training and buff_running(s, spell, state):
            continue
        mana = state.mana if training else 0
        invoke = None
        if training and charge_cambrinth(s, profile, state, ask, prefix, report):
            invoke = profile["cambrinth"]
        result = cast_once(s, spell, mana, state, ask, report, invoke=invoke)
        cast = True
        if training:
            state.last_training = "buff"
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
                f"for {profile['train_casting'] or 'Arcana'}"
                + (f" (+{profile['cambrinth']})" if invoke else "")
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
    return cast
