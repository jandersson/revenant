"""Hunt a ground in a loop, the way your character does it:  ;hunt

Walks to your profile's hunting ground (;go2's map), readies the weapon
and stance, and fights whatever engages you until you say stop: attack,
retarget past corpses, skin the kill if the profile says so, search the
corpse, pouch any gems, and move on to the next room of the ground when
this one runs empty. Breaks off and walks home below the health floor
or at a wound at the profile's wound floor (HEALTH after each kill and
whenever health drops), when the trained skills mind-lock, at the kill
fuse, or when you type
;hunt return  (the current kill is finished first, then the walk home).
;stop hunt  quits where it stands.  ;hunt here  skips the walk;  ;hunt profile  prints the profile it would use.

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
`buffs` are self-cast spells kept up through the hunt (PREPARE, CAST
before the first swing and whenever the Spells window drops one), and
`train_casting` names a magic skill to train by recasting the first
buff between swings, feeding more mana each time until the game warns
of strain, until the skill locks.
The weapon stays in hand when the hunt ends — stowed, it parries
nothing — and its container is only where the first swing fetches it
from.
The game's answers are classified by keyword (the tables below, model
in docs/hunting.md); a skin or search answer the script cannot place is
echoed as "hunt: unrecognized ..." — report those and they become
fixtures. The skinning and gem-pouch commands follow Elanthipedia's
Skinning and Gem pouch pages; the fight follows docs/combat.md. First
cut: melee, one opponent at a time, no offensive magic or ranged (#149).
"""

import re

from client.game import buffs, probe
from client.game.probe import classify
from client.game.profile import describe, load_profile
from client.game.walker import locate, walk
from client.game.wounds import SEVERITIES, level, parse_health

MAX_ACTIONS = 600  # a session, not forever — the fuse under every loop
COLLECT_SECONDS = 3  # the swing's own lines
TAIL_SECONDS = 1.5  # what lands once the roundtime runs out
SETTLE_SECONDS = 1.0  # after arriving: the room's creature enumeration
EMPTY_ROOM_WAIT = 20  # seconds between looks when the whole ground is empty
EMPTY_LAPS = 2  # laps of the ground with nothing in it before giving up
MIND_LOCK = 34

# Captured kill lines: "The cougar slowly tips over and falls down."
# (2026-08-22) and "The ship's rat falls to the ground and lies still."
# (2026-09-05 — the first ;hunt missed it and kept swinging). The
# other wordings are assumptions until captured.
_KILL_WORDS = (
    "tips over",
    "goes still",
    "falls down",
    "falls to the ground",
    "lies still",
    " dies",
    "collapses",
    "keels over",
)
_KILL_NOUN = re.compile(
    r"\b(?:the|a|an) ((?:[\w'-]+ )*?)([\w'-]+) (?:slowly |suddenly )?"
    r"(?:tips over|goes still|falls down|falls to the ground|lies still|dies|"
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
    # "is dead first": the corpse noun found a live one (captured
    # 2026-09-12) — the corpse is gone, the next swing gets the live one.
    (
        "gone",
        (
            "what were you referring",
            "nothing to skin",
            "already been skinned",
            "is dead first",
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


def hostiles(state):
    return dict(getattr(state, "hostiles", None) or {})


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
    """The noun of whatever a hand holds besides the weapon — the skin
    SKIN just cut — or None when nothing did land. Only asked of a
    handle with hand state (hasattr left_hand); a bare one never
    reaches here."""
    for side in ("left", "right"):
        noun = hand(s, side)
        if noun and noun != profile["weapon"]:
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


def cast_buffs(s, profile, tally):
    """The profile's buffs, cast and kept up by client/game/buffs.py
    with the hunt's answer windows and its unrecognized-answer tally."""
    buffs.cast_buffs(
        s,
        profile,
        tally.buffs,
        ask,
        "hunt",
        lambda what, answer: unrecognized(s, tally, what, answer),
    )


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


def next_room(s, db, ground, avoid, tally):
    """The room is empty: on to the next room of the ground, cyclically;
    a one-room ground waits and looks instead. False once the ground
    has been lapped EMPTY_LAPS times with nothing in it."""
    tally.room_clear = False
    tally.empty_moves += 1
    if tally.empty_moves > EMPTY_LAPS * max(len(ground), 1):
        return False
    here = locate(db, s.state)
    others = [room for room in ground if room != here]
    if not others:
        s.echo(
            f"hunt: room empty — waiting {EMPTY_ROOM_WAIT}s for something to turn up"
        )
        s.sleep(EMPTY_ROOM_WAIT)
        s.put("look")
        probe.collect(s, SETTLE_SECONDS)
        return True
    later = [room for room in others if here is not None and room > here]
    target = (later or others)[0]
    s.echo("hunt: room empty — moving on")
    if not walk(s, db, {target}, describe=f"room {target}", avoid=avoid):
        return False
    probe.collect(s, SETTLE_SECONDS)
    return True


def loop(s, profile, db, ground, avoid, tally):
    """Fight until something ends the hunt; returns why."""
    prey = profile["prey"]
    floor = profile["health_floor"]
    last_health = health(s.state)
    check_wounds = False
    for _ in range(MAX_ACTIONS):
        if s.dead:
            return "dead — deathwatch has it"
        if (s.command(timeout=0) or "").strip().lower() == "return":
            return "returning on request"
        current = health(s.state)
        if current is not None and current < floor:
            escape(s)
            return f"health {current}% below the floor"
        if current is not None and last_health is not None and current < last_health:
            check_wounds = True
        last_health = current
        if check_wounds:
            check_wounds = False
            if hit := wound_at_floor(s, profile):
                area, kind, lvl = hit
                escape(s)
                return f"{area} {kind.replace('_', ' ')} {SEVERITIES[lvl]} — at the wound floor"
        if locked(s.state, profile["train_skills"]):
            return "trained skills mind-locked"
        if profile["max_kills"] and tally.kills >= profile["max_kills"]:
            return "kill fuse reached"
        if tally.room_clear or not hostiles(s.state):
            if not next_room(s, db, ground, avoid, tally):
                return "ground empty"
            if not settle(s, db, ground, avoid, tally):
                return "ground taken"
            continue
        cast_buffs(s, profile, tally)  # a buff that ran out, before the swing
        text = ask(s, f"attack {prey}" if prey else "attack")
        lowered = text.lower()
        if any(word in lowered for word in _KILL_WORDS):
            tally.kills += 1
            tally.empty_moves = 0
            tally.corpse_swings = 0
            corpse = kill_noun(text) or prey or "corpse"
            s.echo(f"hunt: {corpse} down ({tally.kills})")
            dispose(s, profile, corpse, tally)
            check_wounds = True
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
    return "action budget spent"


def hunt(s, profile, db, travel=True, avoid=()):
    ground_name = profile["hunting_ground"]
    ground = sorted(db.resolve(ground_name)) if ground_name else []
    if travel:
        if not ground:
            s.echo(
                f"hunt: nothing in the map matches ground {ground_name!r} — check the profile"
            )
            return
        if not walk(s, db, set(ground), describe=repr(ground_name), avoid=avoid):
            s.echo("hunt: could not reach the ground — stopping")
            return
        probe.collect(s, SETTLE_SECONDS)
    tally = Tally()
    if travel and not settle(s, db, ground, avoid, tally):
        return
    wear_bundle(s, profile, tally)
    cast_buffs(s, profile, tally)
    ready(s, profile)
    reason = loop(s, profile, db, ground, avoid, tally)
    s.echo(
        f"hunt: {reason} — {tally.kills} kill(s), {tally.skins} skin(s)"
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
        return
    if not mapdb_path().is_file():
        s.echo("downloading map database (first use, ~13MB) ...")
        download()
    db = MapDB.load()
    travel = not (s.args and s.args[0] == "here")
    hunt(s, profile, db, travel=travel, avoid=avoided_rooms(db, setting("avoid_rooms")))
