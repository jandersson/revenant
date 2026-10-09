"""The hunting bestiary: dr-scripts' hunting zones as ;hunt's grounds
(#340).

hunting_data.py is generated from dr-scripts' data/base-hunting.yaml by
tools/hunting_tables.py: every zone's map rooms, its province, its
creatures with the rank range each suits ("Rat 0-30", from the
Elanthipedia-linked comment above the zone) and each town's zones
weakest first. The map's tags were ;hunt's only way to name a ground,
and they are sparse: Riverhaven's weakest zones, heggarangi frogs
(0-26) and zombie goblins (5-35), carry none, so a circle-1 Barbarian
was sent across the river toward the Crossing's rats, then to grass
eels (25-50) that beat him in a minute (2026-09-26).

ground_rooms() resolves a profile's `hunting_ground`: an exact map tag
first — 293 of the 320 zone names that are also tags list the same
rooms and 27 differ by a room or a few, so a ground that worked keeps
its rooms — then a zone name, then the ;go2 target (a room id, a title)
as before. grounds() lists the zones whose rank range holds a rank,
nearest first by the map's travel time from a room; weapon_rank() is
the rank to ask with: the lowest of the profile's weapon skills, so a
listing never suggests what the weakest weapon cannot handle.
describe() adds the box yield measured on a zone (lootlog.yields:
boxes per search, boxes an hour; boxlog.measured: copper Kronars per box),
since the wiki leaves most drop rates blank (#419, #423); where
nothing is measured, what the wiki does say (wiki_boxes: the Critter
pages' Has Boxes, the Locksmithing page's ranks and drop rate, #422).

;hunt's pure half lives here too (#274, #407): what the script reads
and never sends — the kill sentence (is_kill, kill_noun), the answer
tables (SKIN_OUTCOMES, SEARCH_OUTCOMES, BUNDLE_OUTCOMES, TAP_OUTCOMES)
and the items an answer names (items_in, named), SMITE CHECK's count
(free_smites), the Tally a run keeps, the weapon plan (parse_weapon,
weapon_plan, turn_target, stalled_turn, swing_verb, with the exp-window
readers locked, mindstate_of and rank_of) and wound_floor. Everything
takes text, a profile or the parser's state and returns a value; no
handle. scripts/hunt.py keeps the loop and every command sent, binds
these names as its own (hunt.X) and reads the clock through
hunting.clock, so a test patches this module.
Qt-free, reloadable.
"""

import re
import time
from collections import Counter

from client.game import barbarian, buffs, creatures, hunting_data
from client.game.act import NOT_FOUND

ZONES = hunting_data.ZONES
TOWNS = hunting_data.TOWNS
LISTED = 8  # zones a listing shows


def zone(name):
    """(province, rooms, creatures, notes) for a zone name, or None."""
    return ZONES.get(str(name or "").strip().lower())


def zone_range(name):
    """(low, high) over the zone's creatures, either None when unknown;
    None for a zone without a ranked creature."""
    entry = zone(name)
    if not entry or not entry[2]:
        return None
    lows = [low for _, low, _ in entry[2] if low is not None]
    highs = [high for _, _, high in entry[2] if high is not None]
    return (min(lows) if lows else None, max(highs) if highs else None)


def fits(name, rank):
    """True when the rank lies in the zone's range (an unknown end is
    open); False for a zone with no ranked creature."""
    span = zone_range(name)
    if span is None:
        return False
    low, high = span
    return (low is None or low <= rank) and (high is None or rank <= high)


def ground_rooms(db, name):
    """The map rooms of a `hunting_ground`: an exact map tag, else a
    zone name, else whatever ;go2 resolves it to (sorted)."""
    name = str(name or "").strip()
    if not name:
        return []
    tagged = db.rooms_tagged(name)
    if tagged:
        return sorted(tagged)
    entry = zone(name)
    if entry:
        return sorted(room for room in entry[1] if room in db.rooms)
    return sorted(db.resolve(name))


def weapon_rank(profile, experience):
    """The lowest rank among the profile's weapon skills ("noun:Skill"
    turns in `weapons`), from the exp window's {skill: {rank}}; None
    when the profile names no weapon skill the window knows."""
    wanted = set()
    for turn in profile.get("weapons") or []:
        parts = [part.strip() for part in str(turn).split(":")]
        if len(parts) >= 2 and parts[1]:
            wanted.add(parts[1].lower())
    ranks = [
        entry.get("rank", 0)
        for skill, entry in (experience or {}).items()
        if str(skill).lower() in wanted and isinstance(entry, dict)
    ]
    return min(ranks) if ranks else None


def grounds(db, here, rank, limit=LISTED, avoid=()):
    """[(zone, (low, high), creatures, steps)] for the zones whose range
    holds `rank`, nearest first by the map's travel time from `here`,
    the unreachable left out; at most `limit`."""
    found = []
    for name in ZONES:
        if not fits(name, rank):
            continue
        rooms = [room for room in ZONES[name][1] if room in db.rooms]
        if not rooms:
            continue
        if here in rooms:
            found.append((0.0, name, 0))
            continue
        route = db.path(here, rooms, avoid=avoid) if here is not None else None
        if route is None:
            continue
        seconds = 0.0
        previous = here
        for room, _command in route:
            seconds += _seconds(db, previous, room)
            previous = room
        found.append((seconds, name, len(route)))
    found.sort()
    return [
        (name, zone_range(name), ZONES[name][2], steps)
        for _seconds_, name, steps in found[:limit]
    ]


def _seconds(db, room, dest):
    """The map's travel time for one step (0.2 s when it names none)."""
    timeto = (db.rooms.get(room) or {}).get("timeto") or {}
    value = timeto.get(str(dest), timeto.get(dest))
    return value if isinstance(value, (int, float)) else 0.2


def describe(entry, measured=None):
    """One line for a listed zone: name, range, creatures, steps, and
    the yield measured there when there is one (lootlog.yields), else
    what the wiki says of its creatures' boxes (wiki_boxes, #422)."""
    name, span, zone_creatures, steps = entry
    low, high = span
    where = "here" if steps == 0 else f"{steps} step(s)"
    who = ", ".join(creature for creature, _, _ in zone_creatures)
    line = f"{name} ({low if low is not None else '?'}-{high if high is not None else '?'}: {who}) — {where}"
    clause = yield_said(measured)
    if clause:
        return f"{line}; measured {clause}"
    wiki = wiki_boxes(zone_creatures)
    return f"{line}; {wiki}" if wiki else line


def wiki_boxes(zone_creatures):
    """What the wiki says of a zone's creatures and boxes, "" when it
    says nothing: "wiki: boxes from Forager goblin, Scavenger goblin
    (Locksmithing 0-40+, drop high)" — each creature whose page has
    boxes or whose name the Locksmithing table lists, those sharing the
    table's ranks, cap and drop rate named together (" / " between
    groups) — else "wiki: no boxes" when every page that says says no
    (#422)."""
    groups, without = {}, 0
    for creature, _low, _high in zone_creatures:
        has = creatures.has_boxes(creature)
        locks = creatures.box_locks(creature)
        if has is False:
            without += 1
            continue
        if not (has or locks):
            continue
        detail = []
        if locks:
            ranks, cap, drop = locks
            detail.append(f"Locksmithing {ranks or '?'}-{cap or '?'}")
            if drop:
                detail.append(f"drop {drop.lower()}")
        groups.setdefault(", ".join(detail), []).append(creature)
    if groups:
        return "wiki: boxes from " + " / ".join(
            ", ".join(names) + (f" ({detail})" if detail else "")
            for detail, names in groups.items()
        )
    return "wiki: no boxes" if without else ""


def yield_said(measured):
    """A ground's measured yield in words, "" with nothing measured:
    "26 box(es) in 180 search(es), 14%; 2.1 box(es) an hour over 6
    hunt(s), ~2,604 copper Kronars; 1,240 copper Kronars a box over 12
    opened" — the
    hour only once a minute of hunting is logged (#419), the copper
    once a box told to the ground is opened (boxlog, #423)."""
    measured = measured or {}
    parts = []
    searched, boxes = measured.get("searched") or 0, measured.get("boxes") or 0
    if searched:
        parts.append(
            f"{boxes} box(es) in {searched} search(es), {round(100 * boxes / searched)}%"
        )
    opened = measured.get("opened") or 0
    per_box = (measured.get("coins") or 0) / opened if opened else None
    minutes = measured.get("minutes") or 0
    if minutes >= 1:
        hourly = (measured.get("hunt_boxes") or 0) * 60 / minutes
        worth = (
            f", ~{round(hourly * per_box):,} copper Kronars"
            if per_box is not None
            else ""
        )
        parts.append(
            f"{hourly:.1f} box(es) an hour over {measured.get('hunts') or 0} hunt(s)"
            + worth
        )
    if per_box is not None:
        parts.append(f"{round(per_box):,} copper Kronars a box over {opened} opened")
    return "; ".join(parts)


# --- ;hunt's pure half (#274, #407) ----------------------------------------
# What scripts/hunt.py reads and never sends: the kill sentence, the
# answer tables, the Tally, the weapon plan, the fuses they read. The
# script binds every public name below as its own (hunt.X); the comments
# and captured wordings came over verbatim.


# The captured kill line: "The ship's rat falls to the ground and lies
# still." (2026-09-05 — the first ;hunt missed it and kept swinging),
# the badger's the same (2026-09-14). "The cougar slowly tips over and
# falls down." (2026-08-22) was read as a kill until 2026-09-14: every
# capture of it — the cougar, the rats, a badger — is a KNOCKDOWN, the
# creature stunned and prone ("lying down", then "leaps to its feet"),
# and the badger hunt skinned and searched one that stood back up
# (#197). A knockdown is nothing to act on. "A striped badger screams
# and falls to the ground grasping its mangled left leg!" (2026-09-20)
# is a knockdown too — the badger "grimaces as it stands back up" — so
# the needle is the whole phrase, "falls to the ground and lies
# still", never "falls to the ground" alone (#240). "Twisting in
# agony, the cougar falls to the ground lifeless." (2026-08-22, eight
# times, "a cougar which appears dead" after it) is the other captured
# kill. The rest are assumptions until captured. A kill phrase ends its
# sentence: "The scimitar lands a very heavy hit that collapses the
# ribcage and bursts the diaphragm ..." (2026-09-23, a bobcat) is the
# swing, not the death — it read as a kill of "that" and the search
# went at the room — so the phrase must be followed by the sentence's
# end, and a pronoun is never the noun. The goblins' death runs on
# past "collapses": "A dour forager goblin collapses to the ground,
# shuddering and moaning until it ceases all movement." (2026-09-25,
# the Crossing farmland) — missed, every kill uncounted, and the hunt
# broke off on "60 swings without a kill" (#314).
_KILL_PHRASE = (
    r"(?:goes still|falls to the ground(?: and lies still| lifeless)|dies|"
    r"collapses(?: to the ground,[^.!\n]*? ceases all movement)?|keels over)"
    r"(?=[.!]|\s*$)"
)
_KILL_SENTENCE = re.compile(_KILL_PHRASE, re.IGNORECASE | re.MULTILINE)
_KILL_NOUN = re.compile(
    r"\b(?:the|a|an) ((?:[\w'-]+ )*?)([\w'-]+) (?:slowly |suddenly )?" + _KILL_PHRASE,
    re.IGNORECASE | re.MULTILINE,
)
_PRONOUNS = frozenset({"that", "which", "it", "who", "this"})


def is_kill(text):
    """True when the answer holds a kill sentence — the phrase at its
    sentence's end, never mid-sentence ("a hit that collapses the
    ribcage")."""
    return _KILL_SENTENCE.search(text or "") is not None


# Words that end the creature's noun phrase in a kill line: "A small
# grendel grunts and collapses." read as a kill of "and" until
# 2026-09-21 (#270) — the word before the verb is not always the noun.
_NOUN_STOPS = {
    "and", "then", "slowly", "suddenly", "grunts", "gives", "lets", "screams",
    "shrieks", "howls", "gasps", "shudders", "staggers", "twitches", "sighs",
    "moans", "groans", "wails", "hisses", "roars", "snarls", "whimpers",
}  # fmt: skip


def kill_noun(text):
    """The corpse's noun from the kill sentence, or None: the first kill
    sentence whose noun is a thing, not a pronoun."""
    for match in _KILL_NOUN.finditer(text or ""):
        phrase = (match.group(1) + match.group(2)).split()
        for index, word in enumerate(phrase):
            if word.lower() in _NOUN_STOPS:
                phrase = phrase[:index]
                break
        noun = phrase[-1].lower() if phrase else match.group(2).lower()
        if noun not in _PRONOUNS:
            return noun
    return None


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
    # "is dead first" (a rat, 2026-09-12), "You can't skin something
    # that's not dead!" (a badger, 2026-09-14) and "The striped badger
    # grimaces as it stands back up. / Skin what?" (2026-09-20, #240):
    # the corpse noun found a live one — the corpse is gone, the next
    # swing gets the live one.
    (
        "gone",
        (
            *NOT_FOUND,
            "nothing to skin",
            "already been skinned",
            "is dead first",
            "not dead",
            "stands back up",
            "skin what",
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
    (
        "gone",
        (
            *NOT_FOUND,
            "already been searched",
            "is dead first",
        ),
    ),
    (
        "nothing",
        ("find nothing", "nothing of value", "nothing of interest", "nothing else"),
    ),
    ("found", ("you find", "you search", "you loot", "you get", "you pick up")),
)
# LOOT with no target loots the last creature fought with the goods
# option, "the same effect as the SEARCH command" (Elanthipedia: Loot
# command) — so the corpse noun the kill line yields is only SKIN's
# concern. Its answers are read with SEARCH's table until captured.
# The item a skin or a search produced: "... obtaining a rat pelt.",
# "work loose a sterling example of a rat pelt from the rat carcass",
# "remove a rat tail from the remains of a ship's rat" (the last two
# captured 2026-09-12). The noun is the last word before the period
# or the "from".
# A search's yield: "You find a small ruby.", and the corpse's pockets —
# "The grendel was carrying some waermodi stones, 7 copper coins
# (Kronars), and 1 bronze coin (Dokora)!" (captured 2026-09-21; three
# gems went unpicked before the wording was known, #292). The coins
# carry no article and are not an item here (GET COINS is #291).
_ITEM = re.compile(
    r"(?:obtain(?:ing)?|yielding|you find|you get|you pick up|and get|was carrying) "
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
    ("none", NOT_FOUND),
    # The worn bundle is full (captured 2026-09-20, the fourth badger
    # skin): "Where did you intend to put that?  You don't have any
    # bundles or they're all full or too tightly packed!" — the skin
    # stays in hand and is stowed loose (bundled()).
    ("full", ("all full", "don't have any bundles")),
    ("ok", ("you bundle up", "into your bundle")),
)


def items_in(text):
    """The item nouns a skin or search answer names, in order."""
    return [
        (match.group(2) or match.group(4)).lower() for match in _ITEM.finditer(text)
    ]


def named(text, noun):
    """The words the answer names the item with, article off: "embroidery
    needle" out of "The scout was carrying an embroidery needle!" — the
    noun alone when the answer has no article before it."""
    match = re.search(
        rf"\b(?:an?|some)\s+([^,!.]*?\b{re.escape(noun)})\b", text, re.IGNORECASE
    )
    return match.group(1) if match else noun


# TAP says where a thing is without moving it (captured 2026-09-12:
# "You tap a lumpy bundle that you are wearing." and, for nothing by
# that name, "I could not find what you were referring to."). Any other
# answer — in a hand, in a container — means fetch it and wear it.
TAP_OUTCOMES = (
    ("worn", ("that you are wearing",)),
    ("none", NOT_FOUND),
)


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


class Tally:
    def __init__(self):
        self.kills = 0
        self.skins = 0
        self.coins = 0  # coin piles STOWed after a search that left some
        self.boxes = 0  # boxes into the loot container
        self.unlootable = set()  # nouns the game found no room for this run
        self.boxes_full = False  # the loot container refused a box: no more boxes
        self.unrecognized = 0
        self.empty_moves = 0
        self.room_clear = False
        self.corpse_swings = 0
        # None: no bundle yet, the first skin starts one; True: a bundle
        # is worn; False: no rope (or the bundle refused), skins stowed loose.
        self.bundle = None
        self.bundle_refusals = 0  # skins in a row BUNDLE would not start on
        self.unskinnable = set()  # creatures with no skin, said once (#494)
        self.boxes_left = set()  # creatures whose boxes are past you, said once (#495)
        self.buffs = buffs.BuffState()  # the casts (client/game/buffs.py)
        self.barb = barbarian.BarbState()  # a Barbarian's pieces (#328)
        self.last_smite = None  # clock() of the last smite that struck (#183)
        # The parser's conviction_returns at that smite: the game's own
        # "fully returned" line moves it (#191).
        self.conviction_mark = None
        self.smite_off = False  # a smite drew on the soul pool: no more (#217)
        self.smite_warned = False  # "no free smites" said once per run
        self.maneuvers = 0  # tactical maneuvers the game answered (#190)
        self.almanac_retry = 0.0  # a refused retreat puts the next study off
        self.since_maneuver = 0  # plain swings since the last maneuver
        self.tactic = 0  # the rotation index
        self.tactic_misses = 0  # unrecognized maneuver answers in a row
        self.tactics_off = False  # the maneuvers refused this run, said once
        self.loot_reported = False  # LOOT's first answer echoed for the fixtures
        self.disposed = set()  # the corpse ids skinned and looted (#456)
        self.caps_said = False  # the ground's teaching caps looked at once (#322)
        self.last_track = None  # clock() of the last HUNT that read tracks (#194)
        self.tracks = 0  # HUNTs the game answered
        self.track_misses = 0  # unrecognized HUNT answers in a row
        self.stuns = 0  # stuns taken since the last kill (#236)
        self.stunned_swings = 0  # swings answered "You are still stunned." (#336)
        self.swings_at_kill = 0  # tally.swings at the last kill (#236)
        self.tracking_off = False  # HUNT refused this run, said once
        self.swings = 0  # swings this run, against MAX_ACTIONS
        self.check_wounds = False  # HEALTH before the next swing (a kill, a hit)
        self.fists_warned = False  # "no brawling attacks" said once
        self.armed = None  # the weapon the turn in hand drew ("" for the fists)
        self.brawl = 0  # the brawling attacks' rotation index (#238)
        self.weapon = 0  # the weapons' rotation index: the turn in hand (#238)
        self.rotated_at = 0  # the kill count the weapon last turned on
        self.turn_started = 0  # tally.swings when the turn in hand began
        self.turn_clock = 0.0  # clock() when it began (weapon_minutes)
        self.balances = {}  # balance word -> swings taken at it (#280)
        # The corpses the room's listing marked when this room's fight
        # began, by name: a kill is a corpse more than this (#315).
        self.dead_room = None
        self.dead_seen = Counter()
        # creature -> Counter(searched, boxes, coins): every LOOT of the
        # run against the creature it searched (#419).
        self.kinds = {}
        # The search in hand: {"creature", "seq" of its loot row}, for
        # the box_drops row of a box it turned up (#423).
        self.search = None


def note_search(tally, parsed, corpse):
    """One LOOT counted against its creature in tally.kinds: the name
    the answer gives ("You search the s'lai scout."), else the corpse's
    noun; a box it carried, and coins among what it carried (#419).
    `parsed` is lootlog.parse's reading, None when it read nothing."""
    parsed = parsed or {}
    creature = parsed.get("creature") or corpse or "creature"
    kind = tally.kinds.setdefault(creature, Counter())
    kind["searched"] += 1
    if parsed.get("outcome") == "box":
        kind["boxes"] += 1
    if "coin" in str(parsed.get("carried") or "").lower():
        kind["coins"] += 1


def kinds_said(kinds):
    """The run's searches by creature, most searched first: "s'lai scout
    x15: 1 box(es), 6 with coins; musk hog x2: 0 box(es), 0 with coins"."""
    ordered = sorted(kinds.items(), key=lambda item: (-item[1]["searched"], item[0]))
    return "; ".join(
        f"{creature} x{kind['searched']}: {kind['boxes']} box(es), "
        f"{kind['coins']} with coins"
        for creature, kind in ordered
    )


def kinds_total(kinds, key):
    """One count summed over every creature of the run."""
    return sum(kind[key] for kind in kinds.values())


MIND_LOCK = 34


def maneuvers(profile):
    """The profile's tactical maneuvers, lower-case, blanks dropped."""
    return [m.strip().lower() for m in profile.get("tactics") or [] if m.strip()]


def brawling(profile):
    """The profile's brawling attacks, lower-case, blanks dropped."""
    return [m.strip().lower() for m in profile.get("brawling") or [] if m.strip()]


FISTS = (
    "",
    "fists",
    "hands",
    "brawl",
    "brawling",
)  # a weapons entry for the fists turn


def parse_weapon(entry):
    """A `weapons` entry — "handaxe:Small Edged:sack", "fists:Brawling"
    — as {"weapon", "skill", "container"}; the fists turn has weapon ""."""
    parts = [part.strip() for part in str(entry).split(":")]
    weapon = parts[0].lower() if parts else ""
    return {
        "weapon": "" if weapon in FISTS else parts[0].strip(),
        "skill": parts[1] if len(parts) > 1 else "",
        "container": parts[2] if len(parts) > 2 else "",
    }


def weapon_plan(profile):
    """The turns the hunt cycles through: the profile's `weapons`, or
    the single `weapon` (and its container) with no skill to lock."""
    entries = [parse_weapon(entry) for entry in profile.get("weapons") or []]
    entries = [entry for entry in entries if entry["weapon"] or entry["skill"]]
    if entries:
        return entries
    return [
        {
            "weapon": profile["weapon"],
            "skill": "",
            "container": profile["weapon_container"],
        }
    ]


def has_turns(profile):
    """True when the profile lists `weapons` turns at all — one counts
    (a fists-only badger hunt, 2026-09-20: with a single turn the list
    was ignored, the profile's scimitar stayed the weapon, and every
    kill tried to sheathe a sword that sat in the sack)."""
    return bool(weapon_plan(profile)) and bool(
        [entry for entry in profile.get("weapons") or [] if str(entry).strip()]
    )


def fists_turn(profile):
    """True while the turn in hand is the fists (profile `weapon` is "",
    as `arm` sets it for that turn)."""
    return not profile["weapon"] and bool(brawling(profile))


def plain_swing(profile, verb):
    """True for a swing that is not a tactical maneuver: ATTACK, SMITE,
    or a brawling attack on the fists turn."""
    return verb in ("attack", "smite") or (
        fists_turn(profile) and verb in brawling(profile)
    )


DEFAULT_WEAPON_TARGET = 30


def turn_target(profile):
    """The mindstate a weapon is trained to before the next takes over:
    the profile's `weapon_target` (30, the ;train plan's target), at
    most mind lock; 0 or less trains each to lock."""
    try:
        value = int(profile.get("weapon_target", DEFAULT_WEAPON_TARGET))
    except (TypeError, ValueError):
        value = DEFAULT_WEAPON_TARGET
    return MIND_LOCK if value <= 0 else min(value, MIND_LOCK)


DEFAULT_WEAPON_MINUTES = 10


def turn_minutes(profile):
    """Minutes a weapon keeps the hands at most, its target reached or
    not — the fallback under the target rule: the profile's
    `weapon_minutes` (10); 0 leaves it to the target alone. The
    operator, 2026-10-02: a hunt whose casts did the killing left one
    sword at 4/34 and three weapons untouched in thirty minutes."""
    try:
        value = int(profile.get("weapon_minutes", DEFAULT_WEAPON_MINUTES))
    except (TypeError, ValueError):
        value = DEFAULT_WEAPON_MINUTES
    return max(0, value)


def turn_expired(profile, tally):
    """True once the turn in hand has had its `weapon_minutes` — never
    with 0, never for a tally with no stamp."""
    minutes = turn_minutes(profile)
    started = getattr(tally, "turn_clock", None)
    return bool(minutes) and started is not None and clock() - started >= minutes * 60


def mindstate_of(state, skill):
    experience = getattr(state, "experience", None) or {}
    return (experience.get(skill) or {}).get("mindstate", 0)


def rank_of(state, skill):
    experience = getattr(state, "experience", None) or {}
    return (experience.get(skill) or {}).get("rank", 0)


# A turn that goes this many swings without a kill hands the hands to
# the next: a new weapon at rank 3 cannot finish the ground's creatures
# (2026-09-26: the mace, bought that night, swung sixty times at the
# bobcats and broke the hunt off). The hunt's own KILL_LESS_SWINGS
# still ends it when no turn kills — every turn stalled in its turn.
TURN_STALL_SWINGS = 20


def stalled_turn(tally, profile):
    """True when the turn in hand has gone TURN_STALL_SWINGS swings
    without a kill and the profile has another turn to pass to."""
    if len(weapon_plan(profile)) < 2:
        return False
    since = max(tally.swings_at_kill, tally.turn_started)
    return tally.swings - since >= TURN_STALL_SWINGS


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


def farming(profile):
    """True for a hunt that ends on its haul, not on the skills: a
    `until` of boxes (#299)."""
    return str(profile.get("until") or "").lower() == "boxes"


SMITE_INTERVAL = 60  # seconds between smites: the fallback (#191)
TACTICS_EVERY = 3  # every third swing is a maneuver while Tactics is unlocked
clock = time.monotonic  # tests replace it


def note_smite(tally, state=None):
    """A smite spent (struck, refused, or the free blows gone): the
    minute starts now, and the parser's conviction count is marked so
    the game's "fully returned" line can end it sooner (#191)."""
    tally.last_smite = clock()
    tally.conviction_mark = getattr(state, "conviction_returns", None)


def conviction_back(tally, state):
    """True once the game has said "The strength of your conviction has
    fully returned." since the smite marked — 50-61 s in the logs, the
    minute's timer a few seconds late (#191). False on a session whose
    parser does not count it."""
    count = getattr(state, "conviction_returns", None)
    mark = tally.conviction_mark
    return count is not None and mark is not None and count > mark


def swing_verb(profile, tally, state=None):
    """SMITE when the profile smites, a weapon is in hand (never on the
    fists' turn, #396) and the game has said the conviction is back
    since the last one (#191), or a minute has passed (#183); else the
    next tactical maneuver when the profile lists them, Tactics is
    unlocked and TACTICS_EVERY - 1 plain swings have gone since the
    last (#190); ATTACK otherwise."""
    if profile.get("smite") and not fists_turn(profile):
        last = tally.last_smite
        if (
            last is None
            or clock() - last >= SMITE_INTERVAL
            or conviction_back(tally, state)
        ):
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
    if fists_turn(profile):
        attacks = brawling(profile)
        verb = attacks[tally.brawl % len(attacks)]
        tally.brawl += 1
        return verb
    return "attack"


DEFAULT_WOUND_FLOOR = "harmful"


def wound_floor(profile):
    """The profile's wound floor as a severity name: an empty one is
    DEFAULT_WOUND_FLOOR (#236: an unset floor guarded nothing through
    an hour of eels), "off" is "" — never ask HEALTH."""
    floor = str(profile.get("wound_floor") or "").strip().lower()
    if floor == "off":
        return ""
    return floor or DEFAULT_WOUND_FLOOR
