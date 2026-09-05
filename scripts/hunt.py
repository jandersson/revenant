"""Hunt a ground in a loop, the way your character does it:  ;hunt

Walks to your profile's hunting ground (;go2's map), readies the weapon
and stance, and fights whatever engages you until you say stop: attack,
retarget past corpses, skin the kill if the profile says so, search the
corpse, pouch any gems, and move on to the next room of the ground when
this one runs empty. Breaks off and walks home below the health floor,
when the trained skills mind-lock, at the kill fuse, or when you type
;hunt stop  (the current kill is finished first).  ;hunt here  skips
the walk;  ;hunt profile  prints the profile it would use.

Everything character-specific comes from the profile
(~/.revenant/profiles/<name>.json — File → Character Profile… in the
GUI): weapon and its container, stance, skin or not and with what,
loot container, gem pouch, health floor, ground, home, skills to train.
The game's answers are classified by keyword (the tables below, model
in docs/hunting.md); a skin or search answer the script cannot place is
echoed as "hunt: unrecognized ..." — report those and they become
fixtures. The skinning and gem-pouch commands follow Elanthipedia's
Skinning and Gem pouch pages; the fight follows docs/combat.md. First
cut: melee, one opponent at a time, no magic or ranged (#149).
"""

import re

from client import probe
from client.probe import classify
from client.profile import describe, load_profile
from client.walker import locate, walk

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
    ("gone", ("what were you referring", "nothing to skin", "already been skinned")),
    ("ruined", ("ruin", "botch", "worthless", "useless")),
    ("ok", ("obtain", "you skin", "skinning", "you manage to skin")),
)
SEARCH_OUTCOMES = (
    ("gone", ("what were you referring",)),
    (
        "nothing",
        ("find nothing", "nothing of value", "nothing of interest", "nothing else"),
    ),
    ("found", ("you find", "you search", "you get", "you pick up")),
)
# The item a skin or a search produced: "... obtaining a rat pelt."
# The noun is the last word.
_ITEM = re.compile(
    r"(?:obtain(?:ing)?|yielding|you find|you get|you pick up|and get) "
    r"(?:a|an|some|the) ((?:[\w'-]+ )*?)([\w'-]+)[.,!]",
    re.IGNORECASE,
)


class Tally:
    def __init__(self):
        self.kills = 0
        self.skins = 0
        self.unrecognized = 0
        self.empty_moves = 0
        self.room_clear = False
        self.corpse_swings = 0


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
    return [match.group(2).lower() for match in _ITEM.finditer(text)]


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def unrecognized(s, tally, what, answer):
    tally.unrecognized += 1
    first = (answer.strip().splitlines() or ["(silence)"])[0]
    s.echo(f"hunt: unrecognized {what} answer {first!r} — please report it")


def escape(s):
    """The burst: retreat, retreat, first exit (docs/combat.md)."""
    exits = list(getattr(s.state, "compass", None) or [])
    direction = exits[0] if exits else "out"
    s.put("retreat")
    s.put("retreat")
    s.put(direction)
    s.echo(f"hunt: breaking off — retreating {direction}")


def ready(s, profile):
    """Weapon in hand and stance set before the first swing."""
    weapon = profile["weapon"]
    if weapon:
        container = profile["weapon_container"]
        command = (
            f"get my {weapon} from my {container}" if container else f"get my {weapon}"
        )
        ask(s, command)
    if profile["stance"]:
        ask(s, f"stance set {profile['stance']}")


def unready(s, profile):
    """The weapon back where it lives, when the profile says where."""
    if profile["weapon"] and profile["weapon_container"]:
        ask(s, f"put my {profile['weapon']} in my {profile['weapon_container']}")


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
    if outcome == "ok":
        tally.skins += 1
        found = items_in(answer)
        if found:
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
    for _ in range(MAX_ACTIONS):
        if s.dead:
            return "dead — deathwatch has it"
        if (s.command(timeout=0) or "").strip().lower() == "stop":
            return "stopped on request"
        current = health(s.state)
        if current is not None and current < floor:
            escape(s)
            return f"health {current}% below the floor"
        if locked(s.state, profile["train_skills"]):
            return "trained skills mind-locked"
        if profile["max_kills"] and tally.kills >= profile["max_kills"]:
            return "kill fuse reached"
        if tally.room_clear or not hostiles(s.state):
            if not next_room(s, db, ground, avoid, tally):
                return "ground empty"
            continue
        text = ask(s, f"attack {prey}" if prey else "attack")
        lowered = text.lower()
        if any(word in lowered for word in _KILL_WORDS):
            tally.kills += 1
            tally.empty_moves = 0
            tally.corpse_swings = 0
            corpse = kill_noun(text) or prey or "corpse"
            s.echo(f"hunt: {corpse} down ({tally.kills})")
            dispose(s, profile, corpse, tally)
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
    ready(s, profile)
    tally = Tally()
    reason = loop(s, profile, db, ground, avoid, tally)
    s.echo(
        f"hunt: {reason} — {tally.kills} kill(s), {tally.skins} skin(s)"
        + (
            f", {tally.unrecognized} unrecognized answer(s)"
            if tally.unrecognized
            else ""
        )
    )
    if profile["home"] and not s.dead:
        goals = db.resolve(profile["home"])
        if goals and walk(s, db, goals, describe=repr(profile["home"]), avoid=avoid):
            s.echo(f"hunt: home at {s.state.room_title}")
            unready(s, profile)
        elif not goals:
            s.echo(f"hunt: nothing in the map matches home {profile['home']!r}")


def main(s):
    from client.mapdb import MapDB, download, mapdb_path
    from client.settings import setting
    from client.walker import avoided_rooms

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
