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
so the swing's own roundtime covers the wait, and a long pattern (a
non-battle spell's 26 s) gets a swing per roundtime until it is nearly
ready, #250 — and CAST follows the last swing; a foe that went down
under a swing has the pattern RELEASEd rather than cast at nothing
(#203, after dr-scripts' combat-trainer).
`weapons` lists the weapons the hunt cycles through, one turn per
kill, each with the skill it trains — "handaxe:Small Edged:sack",
"fists:Brawling" — so every weapon skill learns in the same evening
(the operator, 2026-09-20: no argument per weapon type, #238). A
turn's weapon is WIELDed after the last one is SHEATHEd into its
container — WIELD finds it wherever it sits and remembers the place
(#259: the scimitar in the sack, the profile naming the scabbard, and
the turn swung bare-handed, before WIELD did the searching;
Elanthipedia: Wield command, Sheathe command — DRAW is an attack
maneuver, never the draw); the fists turn draws nothing and swings the profile's
`brawling` attacks in rotation — PUNCH, KICK, ELBOW (Elanthipedia:
Brawling skill, Punch command, Elbow command) — with the hands empty,
since PUNCH wants a free hand and a worn parry stick parries as it
is (Elanthipedia: Parry Ability skill), brass knuckles likewise.
Captured 2026-09-20 on a striped badger, the first live fists turn:
"you punch your brass knuckle at a striped badger" (the worn knuckles
are the fist), "you kick your foot at a striped badger", "you elbow
your plate-clad elbow at a striped badger" — each shaped like a
weapon swing in the combat stream, the kill line the same, so the
attacks need no table of their own. A
weapon whose skill sits at mind-lock is skipped until it drains; all
of them locked ends the hunt. The knife, the skins, the casts and the
maneuvers are the same whatever is in hand, SMITE keeps its minute
when the profile smites, and with `weapons` empty the hunt is the
profile's `weapon` alone, never swapped. A single turn listed is that
turn — "fists:Brawling" alone hunts bare-handed whatever `weapon`
says (2026-09-20: the list was ignored below two entries, and every
kill tried to sheathe a scimitar that sat in the sack).
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
Three things end a fight the character is losing without the health
bar saying so (#236: an hour of grass eels — no kill, nine stuns,
every limb to deep cuts, the bar never below 67): 60 swings without a
kill or three stuns in one fight break the hunt off ("the ground is
beyond you", the burst escape, then home), and an unset `wound_floor`
means harmful, where bleeding starts — said once at the start; `off`
never asks HEALTH.
A swing is aimed by ordinal when a corpse of the prey's noun stands
first in the room's listing — "attack second cougar" — so it reaches
the live one instead of the corpse ("already quite dead", a spent
swing); the parser marks the corpses in `room_creatures_dead` and
client/game/creatures.py counts them the way the game does, after
lich-5's drdefs.rb (#278). The balance word the game states ("solidly
balanced", lich-5's DRStats.balance) is tallied per swing and
reported at the end — a reading, no rule yet (#280).
"""

import re
import time

from client.game import buffs, loot, probe
from client.game.creatures import aim
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
# The ground-is-beyond-you fuses (#236): an hour of grass eels gave no
# kill and nine stuns, the health bar never crossed the floor, and the
# profile's wound floor was unset — nothing in the loop said stop while
# every limb went to deep cuts. Now a run of swings without a kill, or
# three stuns in one fight, is a break-off, and an unset wound floor is
# DEFAULT_WOUND_FLOOR (bleeding starts at harmful, docs/wounds.md) with
# "off" for never asking.
KILL_LESS_SWINGS = 60  # swings since the last kill before the hunt ends
STUN_LIMIT = 3  # stuns taken in one fight (a kill resets) before it ends
# Captured 2026-09-20 on the eels: "The teeth lands a light hit that
# lightly pierces the left forearm, lightly stunning you."
_STUNNED = ("stunning you",)
DEFAULT_WOUND_FLOOR = "harmful"

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
# end, and a pronoun is never the noun.
_KILL_PHRASE = (
    r"(?:goes still|falls to the ground(?: and lies still| lifeless)|dies|"
    r"collapses|keels over)(?=[.!]|\s*$)"
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


# Bare ATTACK with every attacker dead (captured 2026-08-22).
_ALL_DEAD = ("nothing else to face", "what are you trying to attack")
# A corpse soaking swings (captured 2026-08-22, docs/combat.md); the
# noun can be several words — "The ship's rat is already quite dead."
_DEAD_NOUN = re.compile(r"The ((?:[\w'-]+ )*?)([\w'-]+) is already quite dead")
# Swings a corpse soaked after being disposed of before the room is
# declared clear anyway — the hostile state lagged for a whole hunt
# once (2026-09-05, before the parser learned dead="1").
CORPSE_SWINGS = 2
# The game has two "no such thing" wordings, "What were you referring
# to?" and "I could not find what you were referring to." (70 and 80
# times in the logs); a SEARCH answered the second went unrecognized on
# 2026-09-20, so every table that knows the first knows both.
_NOTHING_THERE = ("what were you referring", "could not find")
# A container with no room left (captured 2026-09-21, #262): "There
# isn't any more room in the sack for that." — the bare STOW answered
# the same, its default being that sack.
_NO_ROOM = ("any more room", "no room for", "won't fit")
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
# PUNCH and KICK at range fall through the same way (captured 2026-09-20
# on a badger closing from pole range, #257): PUNCH answers "Actually,
# using a weapon would probably be a bit more effective." and KICK its
# emote, "You kick some dirt on a striped badger in disgust." — neither
# with a roundtime, so the filler loop spent three commands in a second.
_NEED_MELEE = ("must be closer", "using a weapon would probably", "kick some dirt")
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
# the first BOB. CIRCLE has a second wording (2026-09-20, #240): "You
# fake a striped badger, first moving one way and then another, leaving
# it off balance." From range they do not advance like ATTACK: "You must
# be closer to use tactical abilities on your opponent." (2026-09-20),
# so the loop ADVANCEs on the prey itself (_NEED_MELEE). A maneuver
# aimed at a corpse answers as a swing would — "The striped badger is
# already quite dead." (2026-09-20, a BOB) — and the corpse branch below
# disposes of it; that is not a miss. Anything else is reported, and
# after TACTIC_MISSES of them the maneuvers are off.
# A maneuver the foe wins is an attempt all the same (the vineyard
# cougars, 2026-09-21, #265): "You hesitate and change your mind,
# circle back awkwardly.  The cougar easily out maneuvers you." with a
# 4 s roundtime — seven in the first run at Tactics 23.
_MANEUVER_DONE = (
    "you bob",
    "you sidestep",
    "you fake",
    "you weave",
    "out maneuvers you",
    "change your mind",
)
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
    # "is dead first" (a rat, 2026-09-12), "You can't skin something
    # that's not dead!" (a badger, 2026-09-14) and "The striped badger
    # grimaces as it stands back up. / Skin what?" (2026-09-20, #240):
    # the corpse noun found a live one — the corpse is gone, the next
    # swing gets the live one.
    (
        "gone",
        (
            "what were you referring",
            "could not find",
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
            "what were you referring",
            "could not find",
            "already been searched",
            "is dead first",
        ),
    ),
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
    ("none", ("what were you referring", "could not find")),
    # The worn bundle is full (captured 2026-09-20, the fourth badger
    # skin): "Where did you intend to put that?  You don't have any
    # bundles or they're all full or too tightly packed!" — the skin
    # stays in hand and is stowed loose (bundled()).
    ("full", ("all full", "don't have any bundles")),
    ("ok", ("you bundle up", "into your bundle")),
)
_MISSING = ("what were you referring", "could not find")
# SHEATHE with no container named and nothing remembered from a WIELD
# (captured 2026-09-22): "Sheathe your steel scimitar where?"
_SHEATHE_WHERE = ("where?",)


class Tally:
    def __init__(self):
        self.kills = 0
        self.skins = 0
        self.coins = 0  # coin piles STOWed after a search that left some
        self.boxes = 0  # boxes into the loot container
        self.unlootable = set()  # nouns the game found no room for this run
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
        self.stuns = 0  # stuns taken since the last kill (#236)
        self.swings_at_kill = 0  # tally.swings at the last kill (#236)
        self.tracking_off = False  # HUNT refused this run, said once
        self.swings = 0  # swings this run, against MAX_ACTIONS
        self.check_wounds = False  # HEALTH before the next swing (a kill, a hit)
        self.fists_warned = False  # "no brawling attacks" said once
        self.armed = None  # the weapon the turn in hand drew ("" for the fists)
        self.brawl = 0  # the brawling attacks' rotation index (#238)
        self.weapon = 0  # the weapons' rotation index: the turn in hand (#238)
        self.rotated_at = 0  # the kill count the weapon last turned on
        self.balances = {}  # balance word -> swings taken at it (#280)


def hostiles(state):
    return dict(getattr(state, "hostiles", None) or {})


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


def next_turn(s, profile, tally, from_current=False):
    """The next weapons entry whose skill is not mind-locked, cyclic
    from the one after the current (from the current itself at the
    start, `from_current`); the current one when it is the only one
    open; None when every skill is locked (a turn with no skill never
    locks). The fists turn is skipped when the profile lists no
    brawling attacks, said once."""
    plan = weapon_plan(profile)
    for step in range(0 if from_current else 1, len(plan) + 1):
        index = (tally.weapon + step) % len(plan)
        entry = plan[index]
        if entry["skill"] and locked(s.state, [entry["skill"]]):
            continue
        if not entry["weapon"] and not brawling(profile):
            if not tally.fists_warned:
                tally.fists_warned = True
                s.echo(
                    "hunt: the profile lists no brawling attacks — fists turn skipped"
                )
            continue
        return index
    return None


def arm(s, profile, tally, index):
    """Take the turn at `index`: the current weapon back into its
    container, the hands cleared, the new one GOT (nothing for the
    fists), the profile's `weapon` and `weapon_container` set to it so
    the knife, the skins and the put-back read the turn in hand."""
    entry = weapon_plan(profile)[index]
    if tally.armed and tally.armed != entry["weapon"]:
        unready(s, profile)  # the last turn's weapon back where it lives
    tally.weapon = index
    tally.armed = entry["weapon"]
    profile["weapon"] = entry["weapon"]
    profile["weapon_container"] = entry["container"]
    clear_hands(s, profile)
    draw(s, profile)
    if entry["skill"]:
        s.echo(
            f"hunt: {entry['weapon'] or 'fists'} for {entry['skill']}"
            + (f" ({mindstate_of(s.state, entry['skill'])}/34)")
        )


def mindstate_of(state, skill):
    experience = getattr(state, "experience", None) or {}
    return (experience.get(skill) or {}).get("mindstate", 0)


def rotate(s, profile, tally):
    """After a kill: the next open turn takes the hands. False when
    every weapon skill is locked — the hunt's end."""
    tally.rotated_at = tally.kills
    index = next_turn(s, profile, tally)
    if index is None:
        return False
    if index != tally.weapon:
        arm(s, profile, tally, index)
    return True


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
    if fists_turn(profile):
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


def wound_floor(profile):
    """The profile's wound floor as a severity name: an empty one is
    DEFAULT_WOUND_FLOOR (#236: an unset floor guarded nothing through
    an hour of eels), "off" is "" — never ask HEALTH."""
    floor = str(profile.get("wound_floor") or "").strip().lower()
    if floor == "off":
        return ""
    return floor or DEFAULT_WOUND_FLOOR


def wound_at_floor(s, profile):
    """HEALTH, read against the profile's wound floor: the (area, kind,
    level) that meets it, or None. "" never asks."""
    floor = wound_floor(profile)
    if not floor:
        return None
    try:
        wanted = level(floor)
    except ValueError:
        s.echo(f"hunt: wound floor {floor!r} is not a severity — ignoring it")
        profile["wound_floor"] = "off"
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


BROKE_OFF = (  # a break-off's reasons: the ground is left, home or not
    "below the floor",
    "at the wound floor",
    "beyond you",
)


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
    """The weapon into a hand: WIELD searches the inventory for it and
    remembers where it came from, so SHEATHE puts it back there
    (Elanthipedia: Wield command, Sheathe command; captured 2026-09-22:
    "You draw out your steel scimitar from the leather scabbard,
    gripping it firmly in your right hand.", "You're already holding a
    watered steel scimitar!"). The scimitar that sat in the sack while
    the profile named the scabbard (#259) is found by the game itself
    now. False when the game finds no such weapon at all, said once."""
    weapon = profile["weapon"]
    if not weapon:
        return True
    answer = ask(s, f"wield my {weapon}").lower()
    if any(word in answer for word in _NOTHING_THERE):
        s.echo(f"hunt: no {weapon} to draw — the game finds none on you")
        return False
    return True


def clear_hands(s, profile):
    """STOW whatever a hand holds that is not the thing about to be
    drawn: the hunt and the brawl take turns (the handaxe, then the
    parry stick), and a tool left in hand from the last run would take
    the other hand the next one needs — PUNCH wants a free hand (the
    operator's parry stick, 2026-09-20). Never DROP."""
    keep = (profile.get("weapon") or "").lower()
    for side in ("left", "right"):
        noun = hand(s, side)
        if noun and noun.lower() != keep:
            ask(s, f"stow my {noun}")


def ready(s, profile, tally=None, index=0):
    """Hands cleared, the first turn's weapon in hand and stance set
    before the first swing."""
    if tally is not None and has_turns(profile):
        arm(s, profile, tally, index)
    else:
        clear_hands(s, profile)
        draw(s, profile)
    if profile["stance"]:
        ask(s, f"stance set {profile['stance']}")


def unready(s, profile):
    """The weapon back where it lives: SHEATHE into the profile's
    container, or — no container named — where WIELD drew it from; a
    "Sheathe your ... where?" (nothing remembered) falls back to STOW."""
    weapon = profile["weapon"]
    if not weapon:
        return
    container = profile["weapon_container"]
    command = (
        f"sheathe my {weapon} in my {container}"
        if container
        else f"sheathe my {weapon}"
    )
    answer = ask(s, command).lower()
    if any(word in answer for word in _SHEATHE_WHERE):
        ask(s, f"stow my {weapon}")


def free_hand(s, profile):
    """The weapon out of the hand for a moment: sheathed, or stowed."""
    unready(s, profile)


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
    outcome = classify(answer, BUNDLE_OUTCOMES)
    if outcome == "ok":
        ask(s, "wear my bundle")
        tally.bundle = True
        s.echo("hunt: bundle started and worn — skins go straight into it")
        draw(s, profile)
        return True
    if outcome == "full":
        # This skin will not start a bundle (a curved claw, captured
        # 2026-09-21, #260): stowed loose, the bundle left untried so
        # the next skin starts it.
        s.echo(
            "hunt: BUNDLE would not take that skin — stowed; the next one starts the bundle"
        )
        stow(s, profile, "rope")
        draw(s, profile)
        return False
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
    forms, and the roundtime is waited before the cast — and a long
    pattern (a non-battle spell's 26 s) is swung into again for as
    long as a roundtime fits, every swing counted (#250); True when a
    swing went out, so the loop does not swing again (#203)."""
    state = tally.buffs
    taken = {"alive": None}

    def report(what, answer):
        unrecognized(s, tally, what, answer)

    def fill():
        if taken["alive"] is not None:
            tally.swings += 1  # the loop counted the first
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
        held = held_skin(s, profile)
        if held is None:
            return True
        s.echo(
            f"hunt: the bundle took no more (a {held} still in hand) — skins "
            "are stowed loose from here"
        )
        tally.bundle = False
        return False
    return make_bundle(s, profile, tally)


def stow(s, profile, item):
    """An item in hand into the loot container, else the STOW default;
    False when neither has room (#262), the item still in hand."""
    container = profile["loot_container"]
    if container:
        answer = ask(s, f"put my {item} in my {container}").lower()
        if not any(word in answer for word in _NO_ROOM):
            return True
    answer = ask(s, f"stow my {item}").lower()
    return not any(word in answer for word in _NO_ROOM)


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
        piece = profile.get("cambrinth") or ""
        if held and held == piece and profile.get("cambrinth_worn"):
            # The worn cambrinth piece, off for a charge when the kill
            # came (2026-09-23: the anklet went into the sack as if it
            # were a skin, and the cast's INVOKE found nothing in hand).
            ask(s, f"wear my {piece}")
        elif held:
            stow(s, profile, held)
        else:
            ask(s, "stow left")
        answer = ask(s, f"skin {corpse}")
        outcome = classify(answer, SKIN_OUTCOMES)
    if outcome == "ok":
        tally.skins += 1
        if "into your bundle" in answer.lower() or bundled(s, profile, tally):
            # The game said so ("You carefully fit a pink grendel ear
            # into your bundle.", #272), or the hands say it landed.
            pass  # in the worn bundle, nothing in hand to stow
        elif found := items_in(answer):
            if not stow(s, profile, found[-1]):
                # Nowhere to put it (#262): it stays in hand, and no more
                # are cut this run. Never a DROP.
                s.echo(
                    f"hunt: no room for the {found[-1]} anywhere — it stays in "
                    "hand and skinning is off for this run; ;skins sells the "
                    "loose skins"
                )
                profile["skin"] = False
        else:
            ask(s, "stow left")  # the skin's hand, by convention (assumption)
    elif outcome == "no_knife":
        s.echo("hunt: nothing to skin with — skinning is off for this run")
        profile["skin"] = False
    elif outcome is None:
        unrecognized(s, tally, "skin", answer)
    if knife:
        stow(s, profile, knife)


def listing(s):
    return str(getattr(s.state, "room_objs", "") or "")


def grab(s, profile, before, tally):
    """What the search left on the ground, read off the room listing
    (client/game/loot.py, after combat-trainer's LootProcess): each
    lootable entry — coins, a gem, a box, the profile's additions —
    taken with one STOW and its answer read; a gem goes to the pouch
    the profile names instead; another hunter's loot is left; a noun
    the game finds no room for is unlootable for the rest of the run.
    The nouns taken, for the wording path to skip."""
    s.sleep(0.5)  # the listing's rewrite lands a beat after the answer
    taken = []
    creatures = getattr(s.state, "room_creatures", None) or ()
    additions = profile.get("loot_additions") or ()
    subtractions = profile.get("loot_subtractions") or ()
    limit = int(profile.get("box_limit") or 0)
    for entry in loot.new_items(before, listing(s), creatures):
        if not loot.lootable(entry, additions, subtractions):
            continue
        what = loot.kind(entry)
        noun = "coins" if what == "coins" else loot.noun_of(entry)
        if noun in tally.unlootable:
            continue
        if what == "box" and limit and tally.boxes >= limit:
            s.echo(f"hunt: {limit} box(es) carried — the {noun} stays")
            continue
        if what == "gem" and profile.get("gem_pouch"):
            pocket(s, profile, noun)
            taken.append(noun)
            continue
        answer = ask(s, f"get {noun}").lower()
        outcome = classify(answer, loot.STOW_OUTCOMES)
        if outcome == "free hand":
            free_hand(s, profile)
            answer = ask(s, f"get {noun}").lower()
            outcome = classify(answer, loot.STOW_OUTCOMES)
        if outcome == "not yours":
            s.echo(f"hunt: the {noun} is someone else's — left")
            continue
        if outcome == "no room":
            tally.unlootable.add(noun)
            s.echo(f"hunt: no room for the {noun} — it stays on the ground")
            continue
        if outcome in ("gone", "held"):
            continue
        if outcome is None:
            unrecognized(s, tally, "get", answer)
            continue
        if what == "coins":
            tally.coins += 1  # coins go to the purse on GET
            continue
        if not stow(s, profile, noun):
            tally.unlootable.add(noun)
            s.echo(f"hunt: no room for the {noun} anywhere — it stays in hand")
            continue
        if what == "box":
            tally.boxes += 1
        taken.append(noun)
    return taken


def dispose(s, profile, corpse, tally):
    """A kill: skin it when profiled, then SEARCH it away — the corpse
    keeps its noun and soaks swings until searched (docs/combat.md) —
    and what the search left on the ground grabbed off the room's
    listing, the answer's own wording second (the operator,
    2026-09-23: a hunt grabs its loot whatever the game called it)."""
    if profile["skin"]:
        skin(s, profile, corpse, tally)
    before = listing(s)
    answer = ask(s, f"search {corpse}")
    outcome = classify(answer, SEARCH_OUTCOMES)
    taken = grab(s, profile, before, tally) if outcome is not None else []
    if outcome == "found":
        for item in items_in(answer):
            if item not in taken:
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
    if word := getattr(s.state, "balance", None):
        tally.balances[word] = tally.balances.get(word, 0) + 1
    tally.stuns += sum(lowered.count(word) for word in _STUNNED)
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
        ) and not _DEAD_NOUN.search(text):
            tally.tactic_misses += 1
            unrecognized(s, tally, verb, text)
            if tally.tactic_misses >= TACTIC_MISSES:
                tally.tactics_off = True
                s.echo(
                    f"hunt: {verb} answered nothing known {TACTIC_MISSES} "
                    "times — tactics off for this run"
                )
    if is_kill(text):
        tally.kills += 1
        tally.empty_moves = 0
        tally.corpse_swings = 0
        tally.stuns = 0  # a kill resets the fight's fuses (#236)
        tally.swings_at_kill = tally.swings
        corpse = kill_noun(text) or prey or "corpse"
        s.echo(f"hunt: {corpse} down ({tally.kills})")
        if tally.coins or tally.boxes:
            s.echo(
                f"hunt: loot so far — {tally.coins} coin pile(s), {tally.boxes} box(es)"
            )
        dispose(s, profile, corpse, tally)
        tally.check_wounds = True
        if len(hostiles(s.state)) <= 1:
            # The kill line is the truth; the parser keeps the dead one
            # until a status frame it never sends (#244), and a cast at
            # it answered "already dead, so that's a bit pointless"
            # (#252). One hostile listed and it just fell: the room is
            # clear, as the game's own "nothing else to face" says.
            tally.room_clear = True
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


def aim_at(s, prey):
    """The prey phrase for the next swing: the first live one of the
    noun by ordinal when a corpse of it stands first in the room's
    listing — "second cougar" (#278; a swing at the plain noun landed
    on the corpse, "already quite dead", and was spent) — the plain
    noun otherwise, and "" when the profile names no prey."""
    if not prey:
        return prey
    return aim(
        prey,
        getattr(s.state, "room_creatures", None) or [],
        getattr(s.state, "room_creatures_dead", None) or [],
    )


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
        if tally.stuns >= STUN_LIMIT:
            escape(s)
            return (
                f"stunned {tally.stuns} times in one fight — the ground is beyond you"
            )
        if tally.swings - tally.swings_at_kill >= KILL_LESS_SWINGS:
            escape(s)
            return (
                f"{KILL_LESS_SWINGS} swings without a kill — the ground is beyond you"
            )
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
        if tally.kills > tally.rotated_at and not rotate(s, profile, tally):
            return "every weapon skill mind-locked"
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
        target = aim_at(s, prey)
        if not cast_buffs(
            s,
            profile,
            tally,
            fight=True,
            filler=lambda: swing(s, profile, tally, target),
        ):
            swing(s, profile, tally, target)
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
    first = next_turn(s, profile, tally, from_current=True) if has_turns(profile) else 0
    if first is None:
        s.echo("hunt: every weapon skill is mind-locked — nothing to train")
        return
    if not str(profile.get("wound_floor") or "").strip():
        s.echo(
            f"hunt: wound floor unset — {DEFAULT_WOUND_FLOOR} by default "
            "(profile wound_floor; off never asks HEALTH)"
        )
    ready(s, profile, tally, first)
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
        + (
            "; balance "
            + ", ".join(f"{word} x{n}" for word, n in tally.balances.items())
            if tally.balances
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
