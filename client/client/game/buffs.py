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
Paladin) is cast at the prey the same way — cast_targeted(), with a
mana ramp of its own — and takes turns with the training cast when
both are due, so a swing never carries two casts; the caller passes
the target. Debilitation "is trained in combat, by casting spells on
enemies" (Elanthipedia: Debilitation skill). Captured 2026-09-14 at
minimum mana on a striped badger: "You gesture at a striped badger. /
A stream of dull golden light jumps from you to a striped badger,
which warps into a spiraling force as it slams into it! / You also
see a striped badger that appears stunned." — the wiki's "brilliant
stream of pure white light" is the line at more mana; the resist and
failure wordings are still to capture (#192).

The profile's `targeted` slot is the same cast for Targeted Magic:
an attack spell ("Footman's Strike" for a Paladin, which "draws on the
caster's melee weapon in hand as a focus for the spell ... Holding a
missile weapon or being unarmed causes the spell to fail" —
Elanthipedia: Footman's Strike) cast at the prey while Targeted Magic
sits below lock, so only in the fight with the weapon drawn.
TARGETED_SLOTS maps each slot to the skill it trains, targeted_due()
and cast_targeted() serve both, and next_cast() says whose turn it is
before a swing — the buff training cast and the targeted slots in
rotation, one cast per swing at most. Footman's Strike's cast line is
the wiki's "You gesture at <target> with your <weapon>." until
captured; the hit, resist and unarmed wordings are still to capture
(#200). A spell the character lacks the ranks for answers the cast
with "Currently lacking the skill to complete the pattern, your spell
fails completely." (captured 2026-09-18: Footman's Strike, a basic
spell, at Targeted Magic 1 — the wiki puts a basic spell at around 20
ranks to cast at minimum mana), which cast_once() returns as
"lacking": the spell is off for the run, its rank named, no mana
step. Before a run's first cast of each targeted slot, discern_slots()
DISCERNs the spell (8 seconds of roundtime, no mana; Elanthipedia:
Discern command) and turns the slot off on "You don't think you are
able to cast this spell" before any PREPARE is spent, and reads the
estimate — "The spell requires at minimum 1 mana streams and you
think you can reinforce it with 2 more, for a total of 3 streams."
(captured 2026-09-20) — as the ramp's ceiling: no cast climbs past
the game's own idea of this caster's most, the training buff's ramp
included (it is DISCERNed too), after five backfires in one evening
had each left a nerve wound (#202). Captured 2026-09-18
on Footman's Strike at Targeted Magic 1: the spell's description, then
"This is a targeted spell, which must be TARGETed at a specific
opponent. ... To begin to be able to cast this spell, you will need to
reach the rank of a promising novice. ... It requires the Targeted
Magic skill to cast effectively.", then "You don't think you are able
to cast this spell." and "Roundtime: 13 sec." — rank_floor() reads the
title (a promising novice is ranks 10 to 19, Elanthipedia: Experience)
so the echo names the ranks the spell wants.

A cast never idles (#203). PREPARE is answered during weapon roundtime
(every chant in the 2026-09-18 log landed one to nine seconds before
the swing's roundtime ended), so cast_once() takes a `filler`: after
PREPARE (and, for the `targeted` slot, TARGET <prey>) the caller's
swing goes out while the pattern forms, then what is left of
PREPARE_SECONDS is collected for the ready line, then CAST — the way
dr-scripts' combat-trainer runs its spell process beside its attacks.
A filler that reports the foe down RELEASEs a pattern aimed at it
instead of casting at nothing ("released"). The targeted slot's flow
is DISCERN's: PREPARE, TARGET (the wiki's "You begin to weave mana
lines into a target pattern around <target>." / "Your formation of a
targeting pattern around <target> has completed." until captured),
CAST with no argument (Elanthipedia: Target command).
"""

import re
from time import monotonic

from client.game import probe
from client.game.probe import classify

MIND_LOCK = 34
PREPARE_SECONDS = 8  # from "begin chanting" to a castable pattern
# A swing's roundtime: a pattern with less than this left is not swung
# into again (the badger fights' PUNCH/KICK/ELBOW and BOB run 3-5 s).
SWING_SECONDS = 4
BUFF_MINUTES = 10  # the wiki's shortest duration for the intro buffs
PREPARE_OUTCOMES = (
    (
        "failed",
        ("don't know", "unable to", "can't prepare", "cannot prepare", "no such"),
    ),
    # Too much mana asked for (the wiki's Prepare page wording; not
    # yet observed here): the pattern is prepared but may not cast.
    ("strain", ("have to strain",)),
    # A pattern from an earlier PREPARE is still held ("You have already
    # fully prepared the Stun Foe spell!", captured 2026-09-20 after a
    # cast at a corpse, #252): RELEASE it and prepare again.
    ("held", ("already fully prepared",)),
    ("ok", ("you begin", "gathering energy", "prepar")),
)
CAST_OUTCOMES = (
    # The foe died under the filler swing ("The striped badger is already
    # dead, so that's a bit pointless.", captured 2026-09-20, #252; "Your
    # target pattern dissipates because the small grendel is dead, but
    # the main spell remains intact.", captured 2026-09-23 at the
    # vineyard): the spell stays held, so it is RELEASEd.
    ("corpse", ("already dead", "target pattern dissipates")),
    # The spell's own skill is short of the spell (captured 2026-09-18,
    # Footman's Strike at Targeted Magic 1, #202): no mana will help.
    ("lacking", ("lacking the skill to complete the pattern",)),
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
# REMOVE of a piece that is not worn — it was in the sack after a death
# and a raising (captured 2026-09-20 in the badgers' room): "Remove
# what?" — so the piece is GOT instead, and worn back afterwards as
# the profile says.
NOT_WORN = ("remove what",)
CHARGE_OUTCOMES = (
    ("worn", ("too clumsy",)),
    # The piece is neither held nor worn — in a container (captured
    # 2026-09-20): "You'll have to hold it, set it on the ground, or
    # put it on something first."
    ("unheld", ("have to hold it",)),
    ("full", ("already holding as much power", "dissipates uselessly")),
    ("failed", ("fail to channel any",)),
    ("ok", ("absorbs all of the energy", "channel all the energy", "absorbs")),
)
# DISCERN <spell> before a targeted slot's first cast of a run (#202):
# the refusal is the wiki's (Talk:Regenerate), the estimate the Discern
# command page's, both until captured.
DISCERN_OUTCOMES = (
    ("unable", ("don't think you are able",)),
    ("unknown", ("don't know", "no such spell", "what spell")),
    ("ok", ("mana streams", "weave at most")),
)
# TARGET <prey> after PREPARE for a targeted-magic spell (#203): the
# wiki's wordings until captured; a missing target is guessed from the
# game's usual "referring to" refusal.
TARGET_OUTCOMES = (
    ("missing", ("what were you referring", "could not find", "nothing to target")),
    # The held spell is not the targeted one ("This spell cannot be
    # targeted.", captured 2026-09-20 with Stun Foe still held, #252).
    ("untargetable", ("cannot be targeted",)),
    ("ok", ("weave mana lines", "target pattern", "targeting pattern")),
)
# DISCERN's "you will need to reach the rank of a <title>": the title's
# first rank (Elanthipedia: Experience). The novice tier is split by
# tens; the other tiers' sub-titles vary, so their base rank stands.
TIER_RANKS = {
    "novice": 1,
    "practitioner": 50,
    "dilettante": 100,
    "aficionado": 150,
    "adept": 200,
    "expert": 300,
    "professional": 400,
    "authority": 500,
    "genius": 600,
    "savant": 700,
    "master": 800,
}
NOVICE_STEPS = {"lowly": 1, "promising": 10, "able": 20, "trained": 30, "full": 40}
_RANK_OF = re.compile(r"rank of an? ([a-z]+(?: [a-z]+)?)")
MANA_FLOOR = 40  # % of mana under which no training cast goes out
CAST_GAP_SECONDS = 60  # between training casts, for a profile without cast_gap
# The targeted casts: profile slot -> the skill it trains. Each is cast
# at the prey between swings while that skill sits below lock, on the
# profile's cast gap and a mana ramp of its own (#192, #200).
TARGETED_SLOTS = {"debilitation": "Debilitation", "targeted": "Targeted Magic"}
# Whose turn it can be before a swing, in rotation after the last cast
# that went out: the buff training cast, then each targeted slot.
CAST_TURNS = ("buff",) + tuple(TARGETED_SLOTS)


class BuffState:
    """What one run remembers about its casts."""

    def __init__(self):
        self.cast_at = {}  # buff -> monotonic() of its last cast
        self.buffs_off = set()  # buffs that refused this run
        self.mana = 0  # the next training cast's mana; 0 is the minimum
        self.mana_cap = None  # one step under the strain, once met
        self.training_off = False  # even the minimum failed this run
        self.cambrinth_off = False  # the piece refused this run, said once
        self.slot_mana = {}  # targeted slot -> its next cast's mana (#192, #200)
        self.slot_cap = {}  # targeted slot -> one step under its strain, once met
        self.slot_limit = {}  # targeted slot -> DISCERN's total, the ramp's ceiling
        self.mana_limit = None  # the training buff's DISCERN total, likewise
        self.slots_off = set()  # targeted slots whose spell refused this run
        self.discerned = set()  # targeted slots (and "buff") DISCERNed this run (#202)
        self.last_training = None  # "buff" or a targeted slot: whose turn it was


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


def rank_of(state, skill):
    """The skill's rank in the exp window, or None before it has shown."""
    experience = getattr(state, "experience", None) or {}
    return (experience.get(skill) or {}).get("rank")


# DISCERN's estimate, captured 2026-09-20 (Stun Foe at Debilitation 15,
# Footman's Strike at Targeted Magic 11): "The spell requires at minimum
# 1 mana streams and you think you can reinforce it with 2 more, for a
# total of 3 streams." — the game's own ceiling for this caster. The
# ramp climbed past it to 4 and 6 and backfired five times in one
# evening, each "A tingling sensation spreads through your body." a
# nerve wound that dampens the casting after it (the operator), so no
# ramp climbs above the estimate now.
_MANA_LIMIT = re.compile(
    r"requires at minimum (\d+) mana streams? and you think you can "
    r"reinforce it with (\d+) more, for a total of (\d+) streams?"
)


def mana_limit(text):
    """(minimum, total) from DISCERN's estimate, or None."""
    match = _MANA_LIMIT.search(text)
    return (int(match.group(1)), int(match.group(3))) if match else None


def climb(mana, limit):
    """The ramp's next mana: a step up, never past DISCERN's limit; the
    same mana when the limit is reached (0 is the spell's minimum)."""
    step = mana + MANA_STEP
    if limit is not None:
        step = min(step, limit)
    return step if step > mana else mana


def rank_floor(text):
    """(rank, title) from DISCERN's "reach the rank of a <title>", or
    None when the answer names none (#203)."""
    match = _RANK_OF.search(text.lower())
    if not match:
        return None
    title = match.group(1)
    words = title.split()
    base = TIER_RANKS.get(words[-1])
    if base is None:
        return None
    if words[-1] == "novice" and len(words) == 2:
        base = NOVICE_STEPS.get(words[0], base)
    return base, title


def buff_running(s, spell, state):
    """True while the buff needs no cast: the Spells window lists it,
    or — for a parser without that window — its last cast is younger
    than BUFF_MINUTES."""
    active = getattr(s.state, "active_spells", None)
    if isinstance(active, dict):
        return spell.lower() in {name.lower() for name in active}
    cast = state.cast_at.get(spell)
    return cast is not None and monotonic() - cast < BUFF_MINUTES * 60


def fetch_command(profile):
    """How the cambrinth piece comes to hand: REMOVE for a worn piece
    (profile `cambrinth_worn`), GET from a container otherwise."""
    verb = "remove" if profile.get("cambrinth_worn") else "get"
    return f"{verb} my {profile.get('cambrinth') or ''}"


def put_back_command(profile):
    """How the piece goes back: WEAR for a worn piece, STOW otherwise.
    A worn piece refuses a charge — "Try though you may, you find it
    too clumsy to charge the cambrinth anklet while wearing it."
    (captured 2026-09-20 on the anklet, 2026-09-14 on the armband) —
    so a piece the character wears is taken off for the cycle."""
    verb = "wear" if profile.get("cambrinth_worn") else "stow"
    return f"{verb} my {profile.get('cambrinth') or ''}"


def held_piece(state, profile):
    """The cambrinth noun when either hand holds the profile's piece
    (the parser's `left_hand`/`right_hand`), else None."""
    noun = (profile.get("cambrinth") or "").lower()
    if not noun:
        return None
    for hand in ("left_hand", "right_hand"):
        held = getattr(state, hand, None) or {}
        words = f"{held.get('noun') or ''} {held.get('name') or ''}".lower().split()
        if noun in words:
            return noun
    return None


def put_back_if_held(s, profile, prefix):
    """The piece back where it lives — WEAR or STOW — when a hand still
    holds it, for a script's finally: clause: a ;stop between the GET
    and the stow left the anklet in hand (2026-09-20, ;cast). Sent
    with cleanup=True, which the handle allows after a stop. True when
    a put-back went out; nothing for a dead character."""
    if getattr(s, "dead", False):
        return False
    noun = held_piece(getattr(s, "state", None), profile)
    if noun is None:
        return False
    s.put(put_back_command(profile), cleanup=True)
    s.echo(f"{prefix}: the {noun} was still in hand — put back")
    return True


def charge_cambrinth(s, profile, state, ask, prefix, report):
    """Bring the profile's cambrinth piece to hand (GET, or REMOVE when
    it is worn) and CHARGE it for Arcana; True when it holds mana for
    the coming cast (charged now, or already full). A piece the game
    will not charge — missing, worn, or outranking the skill — is off
    for the run, said once; a locked Arcana skips the charge. The
    piece stays in hand for INVOKE."""
    noun = profile.get("cambrinth") or ""
    if not noun or state.cambrinth_off or locked(s.state, ["Arcana"]):
        return False
    answer = ask(s, fetch_command(profile))
    if profile.get("cambrinth_worn") and any(
        phrase in answer.lower() for phrase in NOT_WORN
    ):
        # Not on the ankle after all (a death, a raising, a hand-stow):
        # out of the container it went to, and WEAR puts it back after.
        answer = ask(s, f"get my {noun}")
    if classify(answer, GET_OUTCOMES) == "missing":
        s.echo(f"{prefix}: no {noun} to charge — cambrinth off for this run")
        state.cambrinth_off = True
        return False
    mana = int(profile.get("cambrinth_mana") or 1)
    answer = ask(s, f"charge my {noun} {mana}")
    outcome = classify(answer, CHARGE_OUTCOMES)
    if outcome == "unheld":
        # The fetch did not land it in a hand (a full hand, a piece in
        # a closed container): once more from the container, then the
        # charge again; still not in hand, off for the run.
        ask(s, f"get my {noun}")
        answer = ask(s, f"charge my {noun} {mana}")
        outcome = classify(answer, CHARGE_OUTCOMES)
    if outcome == "unheld":
        s.echo(
            f"{prefix}: the {noun} is not in hand to charge — cambrinth off for this run"
        )
    elif outcome == "worn":
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
    ask(s, put_back_command(profile))
    return False


def cast_left(s):
    """Seconds the pattern PREPARE opened has still to form, by the
    parser's cast time against the last prompt's server time; 0 when
    the state cannot say (a fake) or the pattern is ready. The clock is
    whole seconds, so a cast time equal to the last prompt's second is
    still forming for a fraction no stamp shows: one second is added
    while the cast time has not passed (#263: the CAST went out on that
    second, read the ready line as its answer, and missed "Your spell
    barely backfires.")."""
    state = getattr(s, "state", None)
    seen = getattr(state, "server_time", None) if state is not None else None
    if seen is None:
        return 0
    casttime = getattr(state, "casttime", 0) or 0
    return casttime - seen + 1 if casttime >= seen else 0


def cast_once(
    s,
    spell,
    mana,
    state,
    ask,
    report,
    invoke=None,
    target="",
    filler=None,
    targeted=False,
    put_back=None,
    aimed=False,
):
    """PREPARE (with a mana amount when given), TARGET the prey when the
    spell is targeted magic (`targeted`), run the caller's `filler` (a
    swing) while the pattern forms, wait out the rest of the prepare
    time, INVOKE the cambrinth piece when one is charged (`invoke`,
    its noun), CAST (at `target` when one is named and the spell is not
    targeted — a targeted one casts at its pattern), and stow the
    piece. "refused" (the spell cannot be prepared), "lacking" (the
    character's ranks cannot carry the spell at all, #202), "released"
    (the target was gone before the cast, or died under it — the
    pattern is let go, #203, #252), "held" (the pattern held was
    another spell's and TARGET refused it — released, #252),
    "collapsed" (the cast failed), "strained" (cast, but the mana
    asked was too much) or "ok"."""
    prepare = f"prepare {spell} {mana}" if mana else f"prepare {spell}"
    answer = ask(s, prepare)
    outcome = classify(answer, PREPARE_OUTCOMES)
    if outcome == "held":
        # An earlier pattern is still held (a cast at a corpse leaves
        # it, #252): let it go and prepare once more.
        ask(s, "release")
        answer = ask(s, prepare)
        outcome = classify(answer, PREPARE_OUTCOMES)
    if outcome in ("failed", "held"):
        if invoke:
            ask(s, put_back or f"stow my {invoke}")
        return "refused"
    started = monotonic()
    ready = "fully prepared"
    if targeted:
        answer = ask(s, f"target {target}" if target else "target")
        aim = classify(answer, TARGET_OUTCOMES)
        if aim == "missing":
            ask(s, "release")
            return "released"
        if aim == "untargetable":
            ask(s, "release")
            return "held"
        if aim is None:
            report("target", answer)
        ready = "has completed"
    if filler is not None:
        # The swing goes out while the pattern forms (#249): a forming
        # pattern holds no command but the CAST. A non-battle spell's
        # pattern forms for twenty-odd seconds at a low Holy Magic
        # (Heroic Strength: 26 s captured 2026-09-20) and one swing fills
        # four of them, so the filler swings again while a swing's
        # roundtime still fits before the ready line (#250). A filler
        # that finds no live foe ends the swinging: a pattern aimed at
        # the foe is released, a self-cast waits for its ready line.
        while True:
            if not filler():
                # A pattern meant for the foe (`aimed`: the prey slots,
                # whatever the prey noun — with none, a Stun Foe outlived
                # the foe and was cast at nothing, #271) is let go.
                if aimed or target or targeted:
                    ask(s, "release")
                    return "released"
                break
            if cast_left(s) <= SWING_SECONDS:
                break
    # The pattern's own time, read off the state the PREPARE set, is the
    # ceiling — far past PREPARE_SECONDS — and the ready line ends the
    # wait early.
    remaining = max(PREPARE_SECONDS - (monotonic() - started), cast_left(s))
    if remaining > 0:
        probe.collect(s, remaining, until=ready)
    if invoke:
        ask(s, f"invoke my {invoke}")
    answer = ask(s, f"cast {target}" if target and not targeted else "cast")
    cast = classify(answer, CAST_OUTCOMES)
    if invoke:
        ask(s, put_back or f"stow my {invoke}")
    if cast == "corpse":
        ask(s, "release")
        return "released"
    if cast == "lacking":
        return "lacking"
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


def targeted_due(s, profile, state, slot):
    """True when the profile's spell in `slot` ("debilitation",
    "targeted") should go out at the prey: one is named and has not
    refused this run, the skill the slot trains (TARGETED_SLOTS) sits
    below lock, mana is above the floor, and its last cast is the cast
    gap old (#192, #200)."""
    spell = profile.get(slot) or ""
    if not spell or slot in state.slots_off:
        return False
    if locked(s.state, [TARGETED_SLOTS[slot]]):
        return False
    mana = (getattr(s.state, "vitals", None) or {}).get("mana")
    if mana is not None and mana < MANA_FLOOR:
        return False
    last = state.cast_at.get(spell)
    return last is None or monotonic() - last >= cast_gap(profile)


def next_cast(s, profile, state):
    """Whose turn it is before this swing: "buff" when the training
    cast is due, or a targeted slot whose spell is due — the first due
    one in CAST_TURNS after the last cast that went out, so the casts
    take turns and a swing never carries two. None when nothing is
    due (#192, #200)."""
    due = {
        turn
        for turn in CAST_TURNS
        if (
            training_cast_due(s, profile, state)
            if turn == "buff"
            else targeted_due(s, profile, state, turn)
        )
    }
    if not due:
        return None
    order = CAST_TURNS
    if state.last_training in CAST_TURNS:
        after = CAST_TURNS.index(state.last_training) + 1
        order = CAST_TURNS[after:] + CAST_TURNS[:after]
    return next(turn for turn in order if turn in due)


def discern_slots(s, profile, state, ask, prefix, report):
    """DISCERN each targeted slot's spell once per run, before its
    first cast: "You don't think you are able to cast this spell" (or a
    spell the character does not know) turns the slot off, its skill's
    rank named — and the rank the spell wants, when the answer says
    "reach the rank of a <title>" — before a PREPARE is spent on it.
    Thirteen seconds of roundtime per spell (captured 2026-09-18),
    waited out; an answer outside the table is reported and the slot
    cast anyway (#202, #203)."""
    for slot, skill in TARGETED_SLOTS.items():
        spell = profile.get(slot) or ""
        if not spell or slot in state.slots_off or slot in state.discerned:
            continue
        state.discerned.add(slot)
        answer = ask(s, f"discern {spell}")
        s.waitrt()
        outcome = classify(answer, DISCERN_OUTCOMES)
        # The estimate is the ramp's ceiling (2026-09-20): "The spell
        # requires at minimum 1 mana streams and you think you can
        # reinforce it with 2 more, for a total of 3 streams."
        if outcome == "unable":
            state.slots_off.add(slot)
            floor = rank_floor(answer)
            wants = f"needs {skill} {floor[0]} ({floor[1]})" if floor else "is beyond"
            s.echo(
                f"{prefix}: DISCERN says {spell} {wants}; "
                f"{skill} is {rank_of(s.state, skill)} — off for this run"
            )
        elif outcome == "unknown":
            state.slots_off.add(slot)
            s.echo(f"{prefix}: {spell} is not a spell you know — off for this run")
        elif outcome is None:
            report("discern", answer)
        else:
            _cap_by_discern(s, prefix, spell, answer, state.slot_limit, slot)
    # The training buff too: its ramp climbed the same way, with no
    # estimate to stop it (2026-09-20).
    spell = profile.get("buffs") or []
    spell = spell[0] if profile.get("train_casting") and spell else ""
    if spell and "buff" not in state.discerned and not state.training_off:
        state.discerned.add("buff")
        answer = ask(s, f"discern {spell}")
        s.waitrt()
        limits = {}
        _cap_by_discern(s, prefix, spell, answer, limits, "buff")
        state.mana_limit = limits.get("buff")


def _cap_by_discern(s, prefix, spell, answer, limits, key):
    """DISCERN's estimate as the ramp's ceiling for `key`, said once;
    an answer without the estimate leaves the ramp uncapped, as before."""
    limit = mana_limit(answer)
    if limit is None:
        return
    minimum, total = limit
    # 0 is "the minimum" to the ramp (a bare PREPARE): an estimate that
    # allows nothing past it pins the ramp there.
    limits[key] = 0 if total <= minimum else total
    s.echo(
        f"{prefix}: DISCERN caps {spell} at {total} mana"
        + (" — the minimum, no ramp" if total <= minimum else f" (minimum {minimum})")
    )


def cast_targeted(s, profile, state, ask, prefix, report, slot, target="", filler=None):
    """PREPARE the profile's spell in `slot` with its ramp's mana and
    CAST it at the target (the prey's noun; "" casts at whatever is
    engaged) — the `targeted` slot TARGETs it first, the way targeted
    magic must be, and casts at the pattern. The caller's `filler` (a
    swing) runs while the pattern forms (#203). The mana climbs by
    MANA_STEP per cast that took until the strain warning or a
    collapse, then holds one step under; a collapse at the minimum, or
    a cast the ranks cannot carry, turns the spell off for the run,
    said once (#192, #200, #202)."""
    spell = profile[slot]
    skill = TARGETED_SLOTS[slot]
    mana = state.slot_mana.get(slot, 0)
    result = cast_once(
        s,
        spell,
        mana,
        state,
        ask,
        report,
        target=target,
        filler=filler,
        targeted=slot == "targeted",
        aimed=True,
    )
    state.last_training = slot
    if result == "released":
        s.echo(f"{prefix}: {spell} released — the foe was down before the cast")
    elif result == "held":
        s.echo(f"{prefix}: the pattern held was not {spell} — released")
    elif result == "refused":
        s.echo(f"{prefix}: cannot prepare {spell} — off for this run")
        state.slots_off.add(slot)
    elif result == "lacking":
        s.echo(
            f"{prefix}: {spell} fails for lack of {skill} ranks "
            f"({rank_of(s.state, skill)}) — off for this run"
        )
        state.slots_off.add(slot)
    elif result == "ok":
        s.echo(
            f"{prefix}: cast {spell} at {target or 'the foe'} with "
            f"{mana or 'minimum'} mana for {skill}"
        )
        if slot not in state.slot_cap:
            state.slot_mana[slot] = climb(mana, state.slot_limit.get(slot))
    elif mana == 0:
        state.slots_off.add(slot)
        s.echo(f"{prefix}: {spell} fails at minimum mana — off for this run")
    else:
        state.slot_mana[slot] = state.slot_cap[slot] = mana - MANA_STEP
        s.echo(
            f"{prefix}: {spell} at {mana} mana was too much ({result}) — "
            f"holding at {state.slot_mana[slot] or 'minimum'}"
        )


def cast_buffs(
    s, profile, state, ask, prefix="buffs", report=None, train=True, filler=None
):
    """Every profile buff not running: PREPARE it, wait for the pattern,
    CAST. A refusal takes that buff off for the run, said once. The
    first buff is cast again for training when training_cast_due says
    so (and `train` allows it — a caller whose targeted cast took
    this turn passes False), feeding state.mana, which climbs a step
    per cast until the strain warning or a collapsed cast and then
    holds one step under. The caller's `filler` (a swing) runs while
    each pattern forms (#203). True when any cast went out."""
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
        result = cast_once(
            s,
            spell,
            mana,
            state,
            ask,
            report,
            invoke=invoke,
            filler=filler,
            put_back=put_back_command(profile) if invoke else None,
        )
        cast = True
        if training:
            state.last_training = "buff"
        if result == "refused":
            s.echo(f"{prefix}: cannot prepare {spell} — off for this run")
            state.buffs_off.add(spell)
        elif result == "lacking":
            s.echo(f"{prefix}: {spell} fails for lack of ranks — off for this run")
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
                state.mana = climb(mana, state.mana_limit)
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
