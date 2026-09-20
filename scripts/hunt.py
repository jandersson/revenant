"""Hunt a ground in a loop, the way your character does it:  ;hunt

Walks to your profile's hunting ground (;go2's map), readies the weapon
and stance, and fights whatever engages you until you say stop: attack,
retarget past corpses, skin the kill if the profile says so, search the
corpse, pouch any gems, and move on to the next room of the ground when
this one runs empty — and when the whole ground is empty, wait a
while and lap it again, as long as it takes (the operator, 2026-09-13:
an empty ground is not a reason to go home). Breaks off and walks home below the health floor
(with no home set, a break-off still leaves the ground for the nearest
room off it — a character left standing among what hurt it died there,
2026-09-13, #185)
or at a wound at the profile's wound floor (HEALTH after each kill and
whenever health drops), when the trained skills mind-lock, at the kill
fuse, or when you type
;hunt return  (the current kill is finished first, then the walk home).
;stop hunt  quits where it stands.  ;hunt here  skips the walk;  ;hunt profile  prints the profile it would use.
;hunt brawl [here]  the same hunt with the profile's brawling attacks in rotation instead of ATTACK and the parry stick in hand instead of the weapon (Brawling, Parry Ability).

Everything character-specific comes from the profile
(~/.revenant/profiles/<name>.json — File → Character Profile… in the
GUI): weapon and its container, stance, skin or not and with what,
loot container, gem pouch, bundle or not, health floor, ground, home,
skills to train. With `bundle` on, skins go onto a bundling rope worn
as a lumpy bundle (free at any tannery: ASK <tanner> FOR ROPE, kept in
the loot container): a bundle you already have is worn before the
first swing, the first skin of a run starts one when there is none,
and every later skin goes straight into it as it is cut — one item to
sell with ;skins. No rope means skins are stowed loose, said once.
A room of the ground with another player already in it on arrival is
theirs: the loop says so and moves on without a swing, and a ground
with someone in every room is left to them (#178). A room full of
creatures is the point, not a reason to leave: the loop fights them
one at a time (the health and wound floors are the guard).
With `smite` on (a Paladin), one swing a minute is SMITE instead of
ATTACK: it is what trains Conviction, a free smite regenerates every
minute and the experience comes at most once a minute (Elanthipedia:
Smite command), so the rest of the swings stay ATTACK. A SMITE the
game answered with the advance from range or a roundtime is not
spent; the next swing tries again. SMITE CHECK goes out before each
smite, and with no free blow left ("Your conviction is enough to
deliver three blows ..." counts them) the swing is an ATTACK instead:
a smite past the free ones draws on the soul pool, and one with the
pool empty harms the soul (#217; docs/soul.md). A smite the game
answers "Drawing upon holy wrath" turns smiting off for the run.
`tactics` lists tactical maneuvers in rotation ("bob", "circle",
"weave"): every third swing is the next one instead of ATTACK while
Tactics sits below mind-lock in the exp window — a maneuver is what
trains Tactics (Elanthipedia: Tactics skill; Bob, Circle and Weave
commands), it is non-damaging and takes a swing's roundtime, so the
rest stay ATTACK and SMITE keeps its minute; a maneuver answered with
nothing the table knows three times is off for the run (#190).
`buffs` are self-cast spells kept up through the hunt (PREPARE, CAST
before the walk to the ground — not among the prey, where four casts
were a minute standing in the badgers' room, 2026-09-20 — and whenever
the Spells window drops one), and
`train_casting` names a magic skill to train by recasting the first
buff between swings, feeding more mana each time until the game warns
of strain, until the skill locks — one cast per the profile's
`cast_gap` seconds (60 by default: at 20 a badger got six bites per
swing, #189).
`debilitation` names a targeted spell ("Stun Foe") cast at the prey
between swings while Debilitation sits below lock — the same cast gap
and mana ramp, taking turns with the buff training cast so a swing
never carries two casts; a stunned foe bites nothing (#192).
`targeted` names an attack spell ("Footman's Strike") cast at the prey
the same way while Targeted Magic sits below lock — it takes the
weapon in hand as its focus, which the fight already holds; the buff
training cast, the debilitation cast and this one take turns, one
cast per swing at most (#200). Each of the two is DISCERNed once
before the weapon is drawn, and a spell the character's ranks cannot
carry — DISCERN's "You don't think you are able to cast this spell",
or a cast that "fails completely" for lack of skill — is off for the
run, the rank named, and the ranks the spell wants when DISCERN says
("reach the rank of a promising novice": 10) (#202, #203).
A cast never idles: the spell is PREPAREd (and a targeted one
TARGETed at the prey, as DISCERN says it must be), the swing goes out
while the pattern forms — PREPARE is answered during weapon roundtime,
so the swing's own roundtime covers the wait — and CAST follows the
swing; a foe that went down under that swing has the pattern RELEASEd
rather than cast at nothing (#203, after dr-scripts' combat-trainer).
`brawl` (the word on the command line) fights the same ground with
the profile's `brawling` attacks in rotation — PUNCH, KICK, ELBOW
(Elanthipedia: Brawling skill, Punch command, Elbow command) — in
place of ATTACK, the `parry_stick` GOT into the weapon hand instead
of the weapon so the parries train Parry Ability (Elanthipedia: Parry
Ability skill — the weapon in the right hand parries), the knife, the
skins, the casts and the maneuvers as ever; SMITE keeps its minute
when the profile smites (#238). No brawling attacks in the profile
is nothing to swing, said so.
`perception` on: when a room of the ground has emptied, and on every
lap of an empty ground, one HUNT for tracks before moving on, at most
once per 75 seconds while Perception sits below lock — HUNT teaches
Perception on a 75-second timer (Elanthipedia: Hunt command); the
tracks are not followed, the ground's rooms are the map's (#194).
The weapon stays in hand when the hunt ends — stowed, it parries
nothing — and its container is only where the first swing fetches it
from.
The game's answers are classified by keyword (the tables below, model
in docs/hunting.md); a skin or search answer the script cannot place is
echoed as "hunt: unrecognized ..." — report those and they become
fixtures. The skinning and gem-pouch commands follow Elanthipedia's
Skinning and Gem pouch pages; the fight follows docs/combat.md. First
cut: melee, one opponent at a time, no ranged; the only offensive
magic is the profile's targeted spell (#149, #200).
"""

import re
import time

from client.game import buffs, probe
from client.game.probe import classify
from client.game.profile import describe, load_profile
from client.game.walker import locate, walk
from client.game.wounds import SEVERITIES, level, parse_health

MAX_ACTIONS = 600  # swings per run, not forever — the fuse under the loop
# The outer fuse, moves and waits included: an empty ground laps for
# hours (a pause every EMPTY_LAPS laps), never for ever.
MAX_ITERATIONS = 5000
COLLECT_SECONDS = 3  # the swing's own lines
TAIL_SECONDS = 1.5  # what lands once the roundtime runs out
SETTLE_SECONDS = 1.0  # after arriving: the room's creature enumeration
EMPTY_ROOM_WAIT = 20  # seconds between looks when the whole ground is empty
EMPTY_LAPS = 2  # laps of the ground with nothing in it before the pause
MIND_LOCK = 34

# The captured kill line: "The ship's rat falls to the ground and lies
# still." (2026-09-05 — the first ;hunt missed it and kept swinging),
# the badger's the same (2026-09-14). "The cougar slowly tips over and
# falls down." (2026-08-22) was read as a kill until 2026-09-14: every
# capture of it — the cougar, the rats, a badger — is a KNOCKDOWN, the
# creature stunned and prone ("lying down", then "leaps to its feet"),
# and the badger hunt skinned and searched one that stood back up
# (#197). A knockdown is nothing to act on. The other wordings are
# assumptions until captured.
_KILL_WORDS = (
    "goes still",
    "falls to the ground",
    "lies still",
    " dies",
    "collapses",
    "keels over",
)
_KILL_NOUN = re.compile(
    r"\b(?:the|a|an) ((?:[\w'-]+ )*?)([\w'-]+) (?:slowly |suddenly )?"
    r"(?:goes still|falls to the ground|lies still|dies|"
    r"collapses|keels over)",
    re.IGNORECASE,
)
# Bare ATTACK with every attacker dead (captured 2026-08-22).
_ALL_DEAD = ("nothing else to face", "what are you trying to attack")
# A corpse soaking swings (captured 2026-08-22, docs/combat.md); the
# noun can be several words — "The ship's rat is already quite dead."
_DEAD_NOUN = re.compile(r"The ((?:[\w'-]+ )*?)([\w'-]+) is already quite dead")
# Swings a corpse soaked after being disposed of before the room is
# declared clear anyway — the hostile state lagged for a whole hunt
# once (2026-09-05, before the parser learned dead="1").
CORPSE_SWINGS = 2
_NOTHING_THERE = ("what were you referring",)
# ATTACK from pole or missile range advances first (docs/combat.md;
# captured 2026-09-12): "You aren't close enough to attack." / "You
# begin to advance on a ship's rat." / "You are already advancing on a
# ship's rat." The swing comes once "melee range" is reached, so the
# loop waits for that line rather than asking again.
_ADVANCING = ("aren't close enough", "begin to advance", "already advancing")
ADVANCE_WAIT = 10  # seconds for "melee range" before the next ATTACK
# A maneuver from range does not advance on its own (captured 2026-09-20
# on a badger closing from pole range): "You must be closer to use
# tactical abilities on your opponent." — the loop ADVANCEs on the prey
# and waits for melee range, as ATTACK's own advance would.
_NEED_MELEE = ("must be closer",)
# SMITE (captured 2026-09-13 on a rat): "Drawing strength from your
# conviction, you execute a divinely inspired strike!" then the swing
# line as ATTACK would give it, 6 s roundtime. From range it answers
# like ATTACK ("aren't close enough", advancing). One free smite a
# minute, Conviction experience once a minute (Elanthipedia: Smite
# command), so the loop smites once a minute at most (#183).
_SMITE_STRUCK = ("divinely inspired strike",)
SMITE_INTERVAL = 60  # seconds between smites
# A smite is fueled by Conviction's free blows first and the soul pool
# after (Elanthipedia: Smite command): a free one says "Drawing
# strength from your conviction, ...", a soul-pool one "Drawing upon
# holy wrath, ...", and a smite with the pool empty harms the soul —
# an evening of it took a Paladin to chalky grey (#217). So SMITE CHECK
# goes out first (captured 2026-09-20: "You contemplate the strength of
# your conviction. / Your conviction is enough to deliver three blows
# against your enemies before you must either rest or draw upon your
# spiritual strength to continue.") and the swing smites only while it
# counts a blow; a wrath strike, should one slip through, turns
# smiting off for the run.
_SMITE_WRATH = ("upon holy wrath",)
_SMITE_CHECK_BLOWS = re.compile(r"enough to deliver (\w+) blows?", re.IGNORECASE)
_NUMBER_WORDS = {
    word: number
    for number, word in enumerate(
        (
            "no",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        )
    )
}
# Tactical maneuvers (captured 2026-09-14 on a striped badger, #190):
# BOB "You bob suddenly, lowering yourself into a smaller target.",
# CIRCLE "You sidestep a striped badger suddenly, moving in a short
# circle around it.", WEAVE "You weave back and forth, trying to
# distract your opponent." — each followed by a balance line and
# "Roundtime: 3 sec.", and Tactics entered the exp window at rank 3 on
# the first BOB. From range they do not advance like ATTACK: "You must
# be closer to use tactical abilities on your opponent." (2026-09-20),
# so the loop ADVANCEs on the prey itself (_NEED_MELEE). Anything else is
# reported, and after TACTIC_MISSES of them the maneuvers are off.
_MANEUVER_DONE = ("you bob", "you sidestep", "you weave")
TACTICS_EVERY = 3  # every third swing is a maneuver while Tactics is unlocked
TACTIC_MISSES = 3  # unrecognized maneuver answers before tactics go off
# HUNT for tracks (captured 2026-09-14 in a guild office, #194): "You
# take note of all the tracks in the area, so that you can hunt
# anything nearby down.", a numbered list, "Roundtime: 8 sec."; "You
# were unable to locate any followable tracks." is the empty answer
# (the wiki's, captured on an empty Brambles room the same night).
# Perception learns from it once per 75 seconds.
_TRACKS_READ = ("take note of all the tracks", "unable to locate any followable tracks")
HUNT_INTERVAL = 75  # seconds between HUNTs: the skill's learning timer
TRACK_MISSES = 3  # unrecognized HUNT answers before the step goes off
clock = time.monotonic  # tests replace it

# Failures before successes: a failure wording can contain a success
# needle ("you skin" inside "you can't skin"). Assumptions pending
# capture except where noted.
SKIN_OUTCOMES = (
    # "nothing to skin with" carries "nothing to skin": the knife
    # wording is checked first.
    (
        "no_knife",
        ("nothing to skin with", "bare hands", "need a knife", "need something sharp"),
    ),
    # Both hands full — the last skin still in the off hand (captured
    # 2026-09-12, three kills running): stowed, then skinned again.
    ("hands_full", ("one hand free",)),
    # "is dead first" (a rat, 2026-09-12) and "You can't skin something
    # that's not dead!" (a badger, 2026-09-14): the corpse noun found a
    # live one — the corpse is gone, the next swing gets the live one.
    (
        "gone",
        (
            "what were you referring",
            "nothing to skin",
            "already been skinned",
            "is dead first",
            "not dead",
        ),
    ),
    ("ruined", ("ruin", "botch", "worthless", "useless")),
    # Captured 2026-09-12: "you work loose a sterling example of a rat
    # pelt from the rat carcass" and "you skillfully remove a rat tail
    # from the remains of a ship's rat".
    (
        "ok",
        (
            "obtain",
            "you skin",
            "skinning",
            "you manage to skin",
            "work loose",
            "you skillfully remove",
            "from the remains",
        ),
    ),
)
SEARCH_OUTCOMES = (
    # "already been searched" and "is dead first" captured 2026-09-12.
    ("gone", ("what were you referring", "already been searched", "is dead first")),
    (
        "nothing",
        ("find nothing", "nothing of value", "nothing of interest", "nothing else"),
    ),
    ("found", ("you find", "you search", "you get", "you pick up")),
)
# The item a skin or a search produced: "... obtaining a rat pelt.",
# "work loose a sterling example of a rat pelt from the rat carcass",
# "remove a rat tail from the remains of a ship's rat" (the last two
# captured 2026-09-12). The noun is the last word before the period
# or the "from".
_ITEM = re.compile(
    r"(?:obtain(?:ing)?|yielding|you find|you get|you pick up|and get) "
    r"(?:a|an|some|the) ((?:[\w'-]+ )*?)([\w'-]+)[.,!]"
    r"|(?:work loose|remove) (?:a|an|some|the) "
    r"(?:[\w'-]+ example of (?:a|an|some|the) )?((?:[\w'-]+ )*?)([\w'-]+) from",
    re.IGNORECASE,
)


# Bundling (Elanthipedia: Bundle command; captured 2026-09-12 at
# Falken's Tannery): "You bundle up your rat pelt with your bundling
# rope." starts a bundle, "You carefully fit a rat tail into your
# bundle." adds to one. A worn lumpy bundle takes skins straight from
# SKIN (BUNDLE help: auto-bundling, on by default), so the skinning
# hand stays empty and the hand tags are the judge, not a wording.
BUNDLE_OUTCOMES = (
    ("none", ("what were you referring",)),
    ("ok", ("you bundle up", "into your bundle")),
)
_MISSING = ("what were you referring",)


class Tally:
    def __init__(self):
        self.kills = 0
        self.skins = 0
        self.unrecognized = 0
        self.empty_moves = 0
        self.room_clear = False
        self.corpse_swings = 0
        # None: no bundle yet, the first skin starts one; True: a bundle
        # is worn; False: no rope (or the bundle refused), skins stowed loose.
        self.bundle = None
        self.buffs = buffs.BuffState()  # the casts (client/game/buffs.py)
        self.last_smite = None  # clock() of the last smite that struck (#183)
        self.smite_off = False  # a smite drew on the soul pool: no more (#217)
        self.smite_warned = False  # "no free smites" said once per run
        self.maneuvers = 0  # tactical maneuvers the game answered (#190)
        self.since_maneuver = 0  # plain swings since the last maneuver
        self.tactic = 0  # the rotation index
        self.tactic_misses = 0  # unrecognized maneuver answers in a row
        self.tactics_off = False  # the maneuvers refused this run, said once
        self.last_track = None  # clock() of the last HUNT that read tracks (#194)
        self.tracks = 0  # HUNTs the game answered
        self.track_misses = 0  # unrecognized HUNT answers in a row
        self.tracking_off = False  # HUNT refused this run, said once
        self.swings = 0  # swings this run, against MAX_ACTIONS
        self.check_wounds = False  # HEALTH before the next swing (a kill, a hit)
        self.brawl = 0  # the brawling rotation index (;hunt brawl, #238)


def hostiles(state):
    return dict(getattr(state, "hostiles", None) or {})


def maneuvers(profile):
    """The profile's tactical maneuvers, lower-case, blanks dropped."""
    return [m.strip().lower() for m in profile.get("tactics") or [] if m.strip()]


def brawling(profile):
    """The profile's brawling attacks, lower-case, blanks dropped."""
    return [m.strip().lower() for m in profile.get("brawling") or [] if m.strip()]


def brawling_profile(profile):
    """The profile as `;hunt brawl` fights it (#238): the parry stick as
    the thing in the weapon hand (GET my <stick>, from wherever it
    lives; "" is bare-handed), the brawling attacks in rotation instead
    of ATTACK; the knife, the skins, the casts and the maneuvers as
    they are."""
    shaped = dict(profile)
    shaped["weapon"] = profile.get("parry_stick") or ""
    shaped["weapon_container"] = ""
    shaped["_brawl"] = True
    return shaped


def plain_swing(profile, verb):
    """True for a swing that is not a tactical maneuver: ATTACK, SMITE,
    or a brawling attack under `;hunt brawl`."""
    return verb in ("attack", "smite") or (
        bool(profile.get("_brawl")) and verb in brawling(profile)
    )


def swing_verb(profile, tally, state=None):
    """SMITE when the profile smites and a minute has passed since the
    last one that struck (#183); else the next tactical maneuver when
    the profile lists them, Tactics is unlocked and TACTICS_EVERY - 1
    plain swings have gone since the last (#190); ATTACK otherwise."""
    if profile.get("smite"):
        last = tally.last_smite
        if last is None or clock() - last >= SMITE_INTERVAL:
            return "smite"
    rotation = maneuvers(profile)
    if (
        rotation
        and not tally.tactics_off
        and tally.since_maneuver >= TACTICS_EVERY - 1
        and not locked(state, ["Tactics"])
    ):
        verb = rotation[tally.tactic % len(rotation)]
        tally.tactic += 1
        return verb
    if profile.get("_brawl"):
        attacks = brawling(profile)
        verb = attacks[tally.brawl % len(attacks)]
        tally.brawl += 1
        return verb
    return "attack"


def health(state):
    vitals = getattr(state, "vitals", None) or {}
    return vitals.get("health")


def locked(state, skills):
    """True when every named skill sits at mind-lock in the exp window.
    A skill the window hasn't shown yet counts as unlocked."""
    if not skills:
        return False
    experience = getattr(state, "experience", None) or {}
    return all(
        (experience.get(skill) or {}).get("mindstate", 0) >= MIND_LOCK
        for skill in skills
    )


def kill_noun(text):
    match = _KILL_NOUN.search(text)
    return match.group(2).lower() if match else None


def items_in(text):
    """The item nouns a skin or search answer names, in order."""
    return [
        (match.group(2) or match.group(4)).lower() for match in _ITEM.finditer(text)
    ]


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def unrecognized(s, tally, what, answer):
    tally.unrecognized += 1
    first = (answer.strip().splitlines() or ["(silence)"])[0]
    s.echo(f"hunt: unrecognized {what} answer {first!r} — please report it")


def wound_at_floor(s, profile):
    """HEALTH, read against the profile's wound floor: the (area, kind,
    level) that meets it, or None. "" never asks."""
    floor = profile.get("wound_floor") or ""
    if not floor:
        return None
    try:
        wanted = level(floor)
    except ValueError:
        s.echo(f"hunt: wound floor {floor!r} is not a severity — ignoring it")
        profile["wound_floor"] = ""
        return None
    # The injuries panel the game pushes on every change (#163) says
    # whether anything is hurt at all: a clean panel means no HEALTH
    # to ask; a lit one means HEALTH decides how bad.
    panel = getattr(s.state, "injuries", None)
    if isinstance(panel, dict) and not panel:
        return None
    health = parse_health(ask(s, "health"))
    for fragment in health.unknown:
        s.echo(f"hunt: unrecognized wound {fragment!r} — please report it")
    hits = health.at_least(wanted)
    return max(hits, key=lambda hit: hit[2]) if hits else None


BROKE_OFF = ("below the floor", "at the wound floor")  # a break-off's reasons


def off_ground(db, ground):
    """The mapped rooms one move outside the ground: where a break-off
    with no home goes (#185)."""
    inside = set(ground)
    outside = set()
    for room in ground:
        for dest in db.rooms.get(room, {}).get("wayto") or {}:
            try:
                dest = int(dest)
            except (TypeError, ValueError):
                continue
            if dest not in inside and dest in db.rooms:
                outside.add(dest)
    return outside


def leave_ground(s, db, ground, avoid):
    """No home to walk to after a break-off: the nearest room off the
    ground, said so — never the ground itself (Cecil stood on it two
    and a half hours and died there, 2026-09-13, #185)."""
    goals = off_ground(db, ground)
    if goals and walk(s, db, goals, describe="off the ground", avoid=avoid):
        s.echo(
            f"hunt: no home in the profile — left the ground for "
            f"{s.state.room_title}; set home so a break-off walks somewhere safe"
        )
        return True
    s.echo(
        "hunt: no home in the profile and no room off the ground to reach — "
        "you are still on the ground; move, and set home"
    )
    return False


def escape(s):
    """The burst: retreat, retreat, first exit (docs/combat.md)."""
    exits = list(getattr(s.state, "compass", None) or [])
    direction = exits[0] if exits else "out"
    s.put("retreat")
    s.put("retreat")
    s.put(direction)
    s.echo(f"hunt: breaking off — retreating {direction}")


def draw(s, profile):
    """The weapon into a hand."""
    weapon = profile["weapon"]
    if weapon:
        container = profile["weapon_container"]
        command = (
            f"get my {weapon} from my {container}" if container else f"get my {weapon}"
        )
        ask(s, command)


def ready(s, profile):
    """Weapon in hand and stance set before the first swing."""
    draw(s, profile)
    if profile["stance"]:
        ask(s, f"stance set {profile['stance']}")


def unready(s, profile):
    """The weapon back where it lives, when the profile says where."""
    if profile["weapon"] and profile["weapon_container"]:
        ask(s, f"put my {profile['weapon']} in my {profile['weapon_container']}")


def free_hand(s, profile):
    """The weapon out of the hand for a moment: its container, or STOW."""
    weapon = profile["weapon"]
    if weapon and profile["weapon_container"]:
        unready(s, profile)
    elif weapon:
        ask(s, f"stow my {weapon}")


def hand(s, side):
    """The noun in a hand as the parser knows it — None for an empty
    hand, and None for a handle that has no hand state at all."""
    held = getattr(s.state, f"{side}_hand", None)
    return held.get("noun") if isinstance(held, dict) else None


def held_skin(s, profile):
    """The noun of whatever a hand holds besides the weapon and the
    profile's skinning knife — the skin SKIN just cut — or None when
    nothing did land. Only asked of a handle with hand state (hasattr
    left_hand); a bare one never reaches here. (A held skinning knife,
    Grek's, bought 2026-09-14, sat in the off hand after every cut and
    would have been taken for the skin.)"""
    tools = {profile["weapon"], profile.get("skin_knife") or ""}
    for side in ("left", "right"):
        noun = hand(s, side)
        if noun and noun not in tools:
            return noun
    return None


# TAP says where a thing is without moving it (captured 2026-09-12:
# "You tap a lumpy bundle that you are wearing." and, for nothing by
# that name, "I could not find what you were referring to."). Any other
# answer — in a hand, in a container — means fetch it and wear it.
TAP_OUTCOMES = (
    ("worn", ("that you are wearing",)),
    ("none", ("could not find", "what were you referring")),
)


def wear_bundle(s, profile, tally):
    """Before the weapon is drawn: a bundle the character already has
    goes on, so the run's skins land in it — TAP finds it worn from
    the last run, in hand, or in the loot container (a GET from the
    container missed a worn one, 2026-09-12). None anywhere leaves
    tally.bundle None and the first skin starts one."""
    if not profile["bundle"]:
        return
    where = classify(ask(s, "tap my bundle"), TAP_OUTCOMES)
    if where == "none":
        return
    if where != "worn":
        container = profile["loot_container"]
        ask(s, f"get my bundle from my {container}" if container else "get my bundle")
        ask(s, "wear my bundle")
    tally.bundle = True
    s.echo("hunt: bundle worn — skins go straight into it")


def make_bundle(s, profile, tally):
    """The first skin of the run, in hand, starts the bundle: the weapon
    goes back to free a hand, the rope comes out of the loot container,
    BUNDLE ties the skin to it, the bundle goes on, the weapon comes
    back. True with the bundle worn. No rope: said once, and the run's
    skins are stowed loose."""
    free_hand(s, profile)
    container = profile["loot_container"]
    answer = ask(s, f"get my rope from my {container}" if container else "get my rope")
    if any(word in answer.lower() for word in _MISSING):
        s.echo(
            "hunt: no bundling rope — ASK a tanner FOR ROPE (it is free); "
            "skins are stowed loose this run"
        )
        tally.bundle = False
        draw(s, profile)
        return False
    answer = ask(s, "bundle")
    if classify(answer, BUNDLE_OUTCOMES) == "ok":
        ask(s, "wear my bundle")
        tally.bundle = True
        s.echo("hunt: bundle started and worn — skins go straight into it")
        draw(s, profile)
        return True
    unrecognized(s, tally, "bundle", answer)
    tally.bundle = False
    stow(s, profile, "rope")
    draw(s, profile)
    return False


def cast_buffs(s, profile, tally, fight=False, filler=None):
    """The profile's buffs, cast and kept up by client/game/buffs.py
    with the hunt's answer windows and its unrecognized-answer tally.
    In the fight (`fight`) the targeted spells — the profile's
    `debilitation` and `targeted` — go out at the prey too, taking
    turns with the buff training cast (buffs.next_cast), so a swing
    never carries two casts (#192, #200). Outside the fight, each
    targeted spell is DISCERNed once per run first, so one the ranks
    cannot carry never costs a PREPARE (#202). In the fight the
    iteration's swing (`filler`) goes out while the first pattern
    forms, and the roundtime is waited before the cast; True when it
    did, so the loop does not swing again (#203)."""
    state = tally.buffs
    taken = {"alive": None}

    def report(what, answer):
        unrecognized(s, tally, what, answer)

    def fill():
        if taken["alive"] is None:
            taken["alive"] = filler()
            s.waitrt()
        return taken["alive"]

    swing_first = fill if fight and filler is not None else None
    if not fight:
        buffs.discern_slots(s, profile, state, ask, "hunt", report)
    turn = buffs.next_cast(s, profile, state) if fight else None
    if turn in buffs.TARGETED_SLOTS:
        buffs.cast_targeted(
            s,
            profile,
            state,
            ask,
            "hunt",
            report,
            turn,
            target=profile["prey"],
            filler=swing_first,
        )
        buffs.cast_buffs(
            s, profile, state, ask, "hunt", report, train=False, filler=swing_first
        )
    else:
        buffs.cast_buffs(s, profile, state, ask, "hunt", report, filler=swing_first)
    return taken["alive"] is not None


def bundled(s, profile, tally):
    """True when the skin just cut is in a worn bundle: it went there on
    its own (the skinning hand is empty), BUNDLE moved it there, or
    make_bundle started one around it. False leaves it to be stowed."""
    if not profile["bundle"] or tally.bundle is False:
        return False
    if not hasattr(s.state, "left_hand"):
        return False  # no hand state to judge by
    if held_skin(s, profile) is None:
        return True
    if tally.bundle:
        ask(s, "bundle")
        if held_skin(s, profile) is None:
            return True
        s.echo("hunt: the bundle took no more — skins are stowed loose from here")
        tally.bundle = False
        return False
    return make_bundle(s, profile, tally)


def stow(s, profile, item):
    """An item in hand into the loot container, or the STOW default."""
    container = profile["loot_container"]
    if container:
        ask(s, f"put my {item} in my {container}")
    else:
        ask(s, f"stow my {item}")


def pocket(s, profile, item):
    """Something a search turned up: picked up, then into the gem pouch
    when the profile keeps one (the game refuses non-gems, which then
    get stowed like loot), else stowed."""
    ask(s, f"get {item}")
    pouch = profile["gem_pouch"]
    if pouch:
        answer = ask(s, f"put my {item} in my {pouch}")
        if "can't" not in answer.lower() and "cannot" not in answer.lower():
            return
    stow(s, profile, item)


def skin(s, profile, corpse, tally):
    knife = profile["skin_knife"]
    if knife:
        ask(s, f"get my {knife}")
    answer = ask(s, f"skin {corpse}")
    outcome = classify(answer, SKIN_OUTCOMES)
    if outcome == "hands_full":
        # The last skin never left the off hand (2026-09-12: a rat
        # tail whose success line landed after the roundtime): stow
        # what the parser says is there, or the hand itself, and once more.
        held = (getattr(s.state, "left_hand", None) or {}).get("noun")
        if held:
            stow(s, profile, held)
        else:
            ask(s, "stow left")
        answer = ask(s, f"skin {corpse}")
        outcome = classify(answer, SKIN_OUTCOMES)
    if outcome == "ok":
        tally.skins += 1
        if bundled(s, profile, tally):
            pass  # in the worn bundle, nothing in hand to stow
        elif found := items_in(answer):
            stow(s, profile, found[-1])
        else:
            ask(s, "stow left")  # the skin's hand, by convention (assumption)
    elif outcome == "no_knife":
        s.echo("hunt: nothing to skin with — skinning is off for this run")
        profile["skin"] = False
    elif outcome is None:
        unrecognized(s, tally, "skin", answer)
    if knife:
        stow(s, profile, knife)


def dispose(s, profile, corpse, tally):
    """A kill: skin it when profiled, then SEARCH it away — the corpse
    keeps its noun and soaks swings until searched (docs/combat.md)."""
    if profile["skin"]:
        skin(s, profile, corpse, tally)
    answer = ask(s, f"search {corpse}")
    outcome = classify(answer, SEARCH_OUTCOMES)
    if outcome == "found":
        for item in items_in(answer):
            pocket(s, profile, item)
    elif outcome is None:
        unrecognized(s, tally, "search", answer)


def occupants(s):
    """The other players in the room, as the parser read "Also here"."""
    return list(getattr(s.state, "room_players", None) or [])


def settle(s, db, ground, avoid, tally):
    """Arrived in a room of the ground: it is someone else's if a player
    is already in it — the community's rule, the operator's (#178,
    2026-09-12) — so move on until an empty room, and give up once the
    whole ground has been tried. True in a room of our own. A crowd of
    creatures is never a reason to move on: farming them is the point
    (the operator, 2026-09-12)."""
    for _ in range(max(len(ground), 1)):
        names = occupants(s)
        if not names:
            return True
        s.echo(f"hunt: {', '.join(names)} hunting here — their room, moving on")
        if not next_room(s, db, ground, avoid, tally):
            return False
    s.echo("hunt: every room of the ground has someone in it — leaving it to them")
    return False


def wait_for_prey(s, seconds):
    """Wait `seconds`, a second at a time, watching the room: True the
    moment a hostile shows. The 20-second pause used to sleep blind — a
    badger walked in, closed to melee and bit, and the loop walked out
    on it engaged (the operator, 2026-09-20)."""
    for _ in range(int(seconds)):
        if hostiles(s.state):
            return True
        s.sleep(1)
    return bool(hostiles(s.state))


def next_room(s, db, ground, avoid, tally):
    """The room is empty: on to the next room of the ground, cyclically;
    a one-room ground waits and looks instead. Once the ground has
    been lapped EMPTY_LAPS times with nothing in it, a pause of
    EMPTY_ROOM_WAIT and the laps go on — an empty ground is waited
    out, never left (the operator, 2026-09-13). False only when a walk
    fails."""
    tally.room_clear = False
    tally.empty_moves += 1
    if tally.empty_moves > EMPTY_LAPS * max(len(ground), 1):
        s.echo(f"hunt: ground empty — waiting {EMPTY_ROOM_WAIT}s, then looking again")
        tally.empty_moves = 0
        if wait_for_prey(s, EMPTY_ROOM_WAIT):
            s.echo("hunt: something arrived — staying")
            return True
    here = locate(db, s.state)
    others = [room for room in ground if room != here]
    if not others:
        s.echo(
            f"hunt: room empty — waiting {EMPTY_ROOM_WAIT}s for something to turn up"
        )
        if wait_for_prey(s, EMPTY_ROOM_WAIT):
            s.echo("hunt: something arrived — staying")
            return True
        s.put("look")
        probe.collect(s, SETTLE_SECONDS)
        return True
    if hostiles(s.state):
        # A room that filled while the loop was deciding is a room to
        # fight in, never to walk out of engaged.
        s.echo("hunt: something arrived — staying")
        return True
    later = [room for room in others if here is not None and room > here]
    target = (later or others)[0]
    s.echo("hunt: room empty — moving on")
    if not walk(s, db, {target}, describe=f"room {target}", avoid=avoid):
        return False
    probe.collect(s, SETTLE_SECONDS)
    return True


def track(s, profile, tally):
    """One HUNT for tracks when the room has emptied, for Perception: at
    most once per HUNT_INTERVAL while the skill sits below lock. The
    tracks are not followed. TRACK_MISSES answers outside the table in
    a row turn the step off for the run, said once (#194)."""
    if not profile.get("perception") or tally.tracking_off:
        return
    if locked(s.state, ["Perception"]):
        return
    last = tally.last_track
    if last is not None and clock() - last < HUNT_INTERVAL:
        return
    text = ask(s, "hunt")
    if any(word in text.lower() for word in _TRACKS_READ):
        tally.last_track = clock()
        tally.tracks += 1
        tally.track_misses = 0
        return
    tally.track_misses += 1
    unrecognized(s, tally, "hunt", text)
    if tally.track_misses >= TRACK_MISSES:
        tally.tracking_off = True
        s.echo(
            f"hunt: HUNT answered nothing known {TRACK_MISSES} times — "
            "tracking off for this run"
        )


def free_smites(text):
    """The free blows SMITE CHECK counts — "three blows" is 3, "a blow"
    or "one blow" 1 — or None when the answer says nothing known."""
    match = _SMITE_CHECK_BLOWS.search(text or "")
    if not match:
        return None
    word = match.group(1).lower()
    if word.isdigit():
        return int(word)
    if word in ("a", "an"):
        return 1
    return _NUMBER_WORDS.get(word)


def smite_allowed(s, tally):
    """SMITE CHECK before a smite (#217): True while a free blow remains.
    No free blows, or an answer the table does not know, means the next
    SMITE would draw on the soul pool, so this minute's smite is an
    ATTACK instead and the minute is spent; said once per run."""
    blows = free_smites(ask(s, "smite check"))
    if blows:
        return True
    tally.last_smite = clock()
    if not tally.smite_warned:
        tally.smite_warned = True
        s.echo(
            "hunt: no free smites — a SMITE now would draw on the soul pool; "
            "attacking instead until Conviction gives one back (#217)"
        )
    return False


def swing(s, profile, tally, prey):
    """One swing — ATTACK, SMITE or a maneuver (swing_verb) — and what
    its answer means: a kill disposed of, a maneuver tallied, a corpse
    or an empty room noted, an advance waited out. True while the room
    still holds a live hostile (a cast's filler asks, #203)."""
    verb = swing_verb(profile, tally, s.state)
    if verb == "smite" and (tally.smite_off or not smite_allowed(s, tally)):
        verb = "attack"
    text = ask(s, f"{verb} {prey}" if prey else verb)
    lowered = text.lower()
    if verb == "smite" and any(word in lowered for word in _SMITE_WRATH):
        # The pool paid for that one: no more smites this run (#217).
        tally.smite_off = True
        s.echo("hunt: that SMITE drew on the soul pool — smiting off for this run")
    if verb == "smite" and any(word in lowered for word in _SMITE_STRUCK):
        tally.last_smite = clock()  # spent only when it struck
    if plain_swing(profile, verb):
        tally.since_maneuver += 1
    else:
        tally.since_maneuver = 0
        if any(word in lowered for word in _MANEUVER_DONE):
            tally.maneuvers += 1
            tally.tactic_misses = 0
        elif not any(
            word in lowered for word in _ADVANCING + _NOTHING_THERE + _NEED_MELEE
        ):
            tally.tactic_misses += 1
            unrecognized(s, tally, verb, text)
            if tally.tactic_misses >= TACTIC_MISSES:
                tally.tactics_off = True
                s.echo(
                    f"hunt: {verb} answered nothing known {TACTIC_MISSES} "
                    "times — tactics off for this run"
                )
    if any(word in lowered for word in _KILL_WORDS):
        tally.kills += 1
        tally.empty_moves = 0
        tally.corpse_swings = 0
        corpse = kill_noun(text) or prey or "corpse"
        s.echo(f"hunt: {corpse} down ({tally.kills})")
        dispose(s, profile, corpse, tally)
        tally.check_wounds = True
    elif any(word in lowered for word in _ALL_DEAD):
        tally.room_clear = True  # the game says so; the hostile state lags
    elif corpse := _DEAD_NOUN.search(text):
        tally.corpse_swings += 1
        if tally.corpse_swings > CORPSE_SWINGS:
            s.echo("hunt: only a corpse answers — the room is clear")
            tally.room_clear = True
            tally.corpse_swings = 0
        else:
            dispose(s, profile, corpse.group(2), tally)
    elif any(word in lowered for word in _NOTHING_THERE):
        s.put("face next")
        probe.collect(s, TAIL_SECONDS)
    elif any(word in lowered for word in _ADVANCING):
        probe.collect(s, ADVANCE_WAIT, until="melee range")
    elif any(word in lowered for word in _NEED_MELEE):
        ask(s, f"advance {prey}" if prey else "advance")
        probe.collect(s, ADVANCE_WAIT, until="melee range")
    return not tally.room_clear and bool(hostiles(s.state))


def loop(s, profile, db, ground, avoid, tally):
    """Fight until something ends the hunt; returns why."""
    prey = profile["prey"]
    floor = profile["health_floor"]
    last_health = health(s.state)
    for _ in range(MAX_ITERATIONS):
        if tally.swings >= MAX_ACTIONS:
            break  # empty rooms and waits do not count against the swings
        if s.dead:
            return "dead — deathwatch has it"
        if (s.command(timeout=0) or "").strip().lower() == "return":
            return "returning on request"
        current = health(s.state)
        if current is not None and current < floor:
            escape(s)
            return f"health {current}% below the floor"
        if current is not None and last_health is not None and current < last_health:
            tally.check_wounds = True
        last_health = current
        if tally.check_wounds:
            tally.check_wounds = False
            if hit := wound_at_floor(s, profile):
                area, kind, lvl = hit
                escape(s)
                return f"{area} {kind.replace('_', ' ')} {SEVERITIES[lvl]} — at the wound floor"
        if locked(s.state, profile["train_skills"]):
            return "trained skills mind-locked"
        if profile["max_kills"] and tally.kills >= profile["max_kills"]:
            return "kill fuse reached"
        if tally.room_clear or not hostiles(s.state):
            track(s, profile, tally)
            if not next_room(s, db, ground, avoid, tally):
                return "the walk to the next room failed"
            if not settle(s, db, ground, avoid, tally):
                return "ground taken"
            continue
        tally.swings += 1
        # A cast due before this swing wraps it: PREPARE, the swing while
        # the pattern forms, CAST (#203). Otherwise the swing alone.
        if not cast_buffs(
            s, profile, tally, fight=True, filler=lambda: swing(s, profile, tally, prey)
        ):
            swing(s, profile, tally, prey)
    return "action budget spent"


def hunt(s, profile, db, travel=True, avoid=()):
    ground_name = profile["hunting_ground"]
    ground = sorted(db.resolve(ground_name)) if ground_name else []
    tally = Tally()
    if travel:
        if not ground:
            s.echo(
                f"hunt: nothing in the map matches ground {ground_name!r} — check the profile"
            )
            return
        # The buffs before the walk, not among the prey: four casts on
        # arrival were a minute spent standing in the badgers' room
        # (the operator, 2026-09-20), and a buff at minimum mana lasts
        # nine, so the walk costs it little. On arrival the Spells
        # window lists them and the second cast_buffs casts nothing.
        cast_buffs(s, profile, tally)
        if not walk(s, db, set(ground), describe=repr(ground_name), avoid=avoid):
            s.echo("hunt: could not reach the ground — stopping")
            return
        probe.collect(s, SETTLE_SECONDS)
    if travel and not settle(s, db, ground, avoid, tally):
        return
    wear_bundle(s, profile, tally)
    cast_buffs(s, profile, tally)
    ready(s, profile)
    reason = loop(s, profile, db, ground, avoid, tally)
    s.echo(
        f"hunt: {reason} — {tally.kills} kill(s), {tally.skins} skin(s)"
        + (f", {tally.maneuvers} maneuver(s)" if tally.maneuvers else "")
        + (f", {tally.tracks} HUNT(s)" if tally.tracks else "")
        + (
            f", {tally.unrecognized} unrecognized answer(s)"
            if tally.unrecognized
            else ""
        )
    )
    if s.dead:
        return
    # The weapon stays in hand at every end: a stowed weapon is no
    # parry (2026-09-12, three rats and an empty hand after a stop),
    # and nothing a hunt hands over to needs both hands. Its container
    # is only where the first swing fetches it from.
    if profile["home"]:
        goals = db.resolve(profile["home"])
        if goals and walk(s, db, goals, describe=repr(profile["home"]), avoid=avoid):
            s.echo(f"hunt: home at {s.state.room_title}")
        elif not goals:
            s.echo(f"hunt: nothing in the map matches home {profile['home']!r}")
    elif any(word in reason for word in BROKE_OFF) and ground:
        leave_ground(s, db, ground, avoid)


def main(s):
    from client.game.mapdb import MapDB, download, mapdb_path
    from client.settings import setting
    from client.game.walker import avoided_rooms

    name = getattr(s.state, "name", None) or ""
    profile = load_profile(name)
    if s.args and s.args[0] == "profile":
        s.echo(f"hunt: profile for {name or 'an unnamed character'}")
        for line in describe(profile):
            s.echo(f"  {line}")
        if not profile["home"]:
            s.echo(
                "hunt: home is empty — a break-off leaves you just off the ground; "
                "set it in the profile"
            )
        return
    if not mapdb_path().is_file():
        s.echo("downloading map database (first use, ~13MB) ...")
        download()
    db = MapDB.load()
    words = [str(word).lower() for word in (s.args or [])]
    travel = "here" not in words
    if "brawl" in words:
        if not brawling(profile):
            s.echo(
                "hunt: the profile lists no brawling attacks (brawling: punch, "
                "kick, elbow) — nothing to swing"
            )
            return
        profile = brawling_profile(profile)
    try:
        hunt(
            s,
            profile,
            db,
            travel=travel,
            avoid=avoided_rooms(db, setting("avoid_rooms")),
        )
    finally:
        # The weapon stays in hand by design; the cambrinth piece does
        # not — a ;stop mid-cycle puts it back (2026-09-20, ;cast).
        buffs.put_back_if_held(s, profile, "hunt")
