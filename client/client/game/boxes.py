"""A box picked open, in words: the seventeen difficulty readings, what
DISARM, PICK and OPEN answer, the caution a reading earns, and the
argument grammar ;boxes reads. Qt-free, reloadable; scripts/boxes.py is
the loop.

Locksmithing trains on the boxes a hunt brings home (Elanthipedia:
Locksmithing skill, Disarm command, Pick command): DISARM <box>
IDENTIFY reads the trap's difficulty against the character's skill in
one of seventeen phrases, DISARM <box> <caution> takes it down, PICK
<box> IDENTIFY reads the lock the same way, PICK <box> <caution> opens
it with the lockpick in hand or the worn lockpick ring's top pick, and
OPEN plus LOOK IN show the loot. The caution grades the risk and the
experience: CAREFUL is slowest and safest, plain is the middle, QUICK
is faster and riskier, BLIND riskier still — a sprung trap hurts, and a
reading of "longshot" or worse is a box for a better locksmith.
Kneeling or sitting helps (the wiki's advice; dr-scripts' pick.lic
sits by default), and armor and brawling gear on the hands hinder
("Your brass knuckles hinders your attempt."): the profile's
`hindering_gear` (knuckles, gauntlets) comes off before the first box
and goes back on after (`hindering_gear`, WORN).

The seventeen readings are the wiki's Locksmithing table, cut to the
fragment that tells them apart (TRAP_READINGS, LOCK_READINGS); the
thresholds in `caution` are pick.lic's, rounded: its 0-based indexes
0-1 quick, 2-4 plain, 5-9 careful and 10 up too hard for a trap, 2-3
quick, 4-6 plain, 7 up careful for a lock. The outcome wordings of
DISARM, PICK and OPEN (DISARM_OUTCOMES, PICK_OUTCOMES, OPEN_OUTCOMES)
are dr-scripts' data/base-picking.yaml and pick.lic's bput lists — the
trap-sprung lines, the disarm successes per trap type, the retry and
failed-identify lines, "you remove your lockpick and open and remove
the lock", "It's not even locked, why bother", "Find a more appropriate
tool" (the wrong pick for the lock), "You discover another lock
protecting". The first live run (2026-09-23, two grendel boxes at
Locksmithing 1) captured the identify failure ("Careful probing of the
oaken crate fails to reveal to you what type of trap protects it."),
the shift ("your careless examination caused something to shift inside
the trap mechanism"), the frog trap's look ("a lumpy green rune hidden
inside the box near the lock"), two readings (12/17 "Prayer would be a
good start...", 13/17 "You have an amazingly minimal chance..."), the
careful disarm's retry ("You work with the trap for a while but are
unable to make any progress.") and the hindrance lines; the rest stay
pick.lic's until the ranks reach a box, and the script echoes every
first-of-a-kind answer so they become fixtures. Every IDENTIFY taught
(0/34 to 2/34 in five attempts), so a box past the reading still
trains. Sources: docs/bibliography.md.
"""

import re

from client.game.creatures import noun_of
from client.game.loot import BOX_NOUNS

SKILL = "Locksmithing"

# The wiki's seventeen readings (1-17), the fragment that tells each one
# apart, lowercased; `reading()` returns the 1-based rank.
TRAP_READINGS = (
    "aged grandmother could defeat this trap",
    "trap is a laughable matter",
    "trivially constructed gadget",
    "simple matter for you to disarm",
    "should not take long with your skills",
    "with only minor troubles",
    "trap is precisely at your skill level",
    "trap has the edge on you",
    "odds are against you",
    "some chance of being able to disarm",
    "would be a longshot",
    "prayer would be a good start",
    "amazingly minimal chance",
    "really don't have any chance",
    "same shot as a snowball",
    "jump off a cliff",
    "pitiful snowball encased",
)
LOCK_READINGS = (
    "aged grandmother could open this",
    "lock is a laughable matter",
    "trivially constructed piece of junk",
    "simple matter for you to unlock",
    "should not take long with your skills",
    "with only minor troubles",
    "lock is precisely at your skill level",
    "lock has the edge on you",
    "odds are against you",
    "some chance of being able to pick",
    "would be a longshot",
    "prayer would be a good start",
    "amazingly minimal chance",
    "really don't have any chance",
    "same shot as a snowball",
    "jump off a cliff",
    "pitiful snowball encased",
)
TOO_HARD = 11  # "would be a longshot" and worse: left for a better locksmith

# The caution per reading, pick.lic's thresholds rounded to the wiki's
# 1-based ranks: (last rank of the band, the word after the box).
TRAP_CAUTION = ((2, "quick"), (5, ""), (TOO_HARD - 1, "careful"))
LOCK_CAUTION = ((4, "quick"), (7, ""), (TOO_HARD - 1, "careful"))


def reading(answer, readings):
    """The 1-based difficulty rank an IDENTIFY answer reads, or None."""
    lowered = (answer or "").lower()
    for rank, fragment in enumerate(readings, 1):
        if fragment in lowered:
            return rank
    return None


def caution(rank, bands):
    """The caution word for a reading: "quick", "" (plain) or "careful";
    None for a box past TOO_HARD."""
    if rank is None or rank >= TOO_HARD:
        return None
    for last, word in bands:
        if rank <= last:
            return word
    return None


# DISARM's answers. Failures first, as probe.classify wants; a trap
# sprung is read before anything else since its line comes with the
# damage. The fragments are dr-scripts' data/base-picking.yaml.
TRAP_SPRUNG = (
    "stabs you painfully in the finger",
    "acrid stream of sulfurous air",
    "stream of corrosive acid sprays",
    "deadly sharp scythe blade whips out",
    "huge electrical charge sends you flying",
    "cloud of thick green vapor",
    "begins to glow with an eerie black light",
    "your ears register the sound of a sharp snap",
    "rust colored coating on the tip",
    "blinding flash explodes around you",
    "grace of a pregnant goat",
    "attempt to undo the string tying the bladder",
    "the hammer slips from its locked",
    "nothing happened. maybe it was a dud",
    "something isn't right",
    "tormented souls being freed",
    "has gotten much bigger",
    "shred the fatty bladder",
    "liquid shadows",
    "wiggle the milky-white tube",
    "unladylike epithets",
    "prying off the body of the crusty scarab",
    "until you peer closely to examine",
    "ant-like insects emerge",
    "angry vykathi reapers",
    "spraying you completely",
    "everything goes utterly black",
    "dart flies through your fingers",
    "you just begin to move it when a slight",
    "tiny projectiles slamming into you",
)
INJURED = ("no shape to be disarming",)
# Worn armor and brawling gear on the hands hinder every DISARM and PICK
# (the wiki's warning; captured 2026-09-23 in the Chambers: "Your armor
# hinders your attempt." / "Your brass knuckles hinders your attempt."),
# said once a run when something still hinders after the profile's
# `hindering_gear` is off.
HINDERED = ("hinders your attempt",)
# WEAR's answer when a piece of that gear goes back on (captured
# 2026-09-23: "You slide some brass knuckles onto your hands and clench
# your fists to secure the fit." / "You slip some plate gauntlets onto
# your hands."); anything else leaves it in hand, and the script stows
# it and says so.
WORN = ("onto your hands", "you slip", "you slide", "you put on", "you wear")


def hindering_gear(profile):
    """The profile's `hindering_gear` as clean nouns, in order, no
    repeats: what ;boxes REMOVEs before the first box and WEARs back
    after (knuckles, gauntlets)."""
    seen = []
    for item in profile.get("hindering_gear") or []:
        noun = str(item).strip().lower()
        if noun and noun not in seen:
            seen.append(noun)
    return seen


LOST = ("need to have the item in your hands", "disarm what", "what were you referring")
IDENTIFY_FAILED = ("fails to reveal to you what type of trap", "something to shift")
# A box whose last trap is down answers IDENTIFY with the disarmed
# trap's look (base-picking.yaml's disarmed_traps) — no trap left.
NO_TRAP = (
    "rendering the trap harmless",
    "separated harmlessly from their charge",
    "pin and shaft lodged into the frame",
    "been pulled away and whatever was inside, removed",
    "no longer will function",
    "glowing rune pushed deep within",
    "too far out of position for the mechanism",
    "animal bladder and a disconnected string",
    "no longer a danger",
    "bent away from each other",
    "far enough away from the lock to be harmless",
    "you deem it quite safe",
    "small portion of the trap has been removed",
    "seal has been pried away",
    "small deflated bladder",
    "indicating a liquid was drained out",
    "as if something had been poured out",
    "bent needle sticks harmlessly",
    "unhooked the stopper",
    "picked apart and removed",
    "no longer attached to a razor-sharp",
    "it seems harmless",
    "whatever it was has been pried out",
    "remnants of some type of powder",
    "sealed with dirt, blocking whatever",
    "peeled away from the hinges",
    "no traps",  # the plain no-trap answer, uncaptured (2026-09-23)
    "not trapped",
)
DISARM_RETRY = (
    "unable to make any progress",
    "doubt you'll be this lucky every time",
    "thanks to an instinct provided by your sense of security",
)
DISARMED = (
    "stopping it up and disarming the trap",
    "contact fibers away from the cube",
    "springs upward and lodges",
    "gently slide the tiny tube out",
    "openings are sealed shut",
    "push it deep inside",
    "no longer a threat",
    "gently remove the string that holds the bladder",
    "bend it well away from the mesh bag",
    "bend it away from the tiny hammer",
    "wedge a small stick between the tiny hammer",
    "knock free the coin sized piece of metal",
    "being extremely careful not to break it",
    "spray harmlessly upon the ground",
    "allowing the deadly naphtha to drain harmlessly",
    "work first at draining it",
    "so that it can no longer spring",
    "allowing it to be opened safely",
    "faux insect falls away and crumbles",
    "unhook it from the blade rendering it harmless",
    "nudge the black crystal away",
    "pry at the studs working them away",
    "blow the powder away from the lock",
    "pack it into the pinholes, blocking them",
    "no longer touches the hinges at all",
    "you disarm",  # a plain success, uncaptured
)
MORE_TRAPS = (
    "not fully disarmed",
    "not yet fully disarmed",
    "still has more to torment",
)
DISARM_OUTCOMES = (
    ("sprung", TRAP_SPRUNG),
    ("injured", INJURED),
    ("lost", LOST),
    ("identify failed", IDENTIFY_FAILED),
    ("retry", DISARM_RETRY),
    ("no trap", NO_TRAP),
    ("disarmed", DISARMED),
)

# PICK's answers (pick.lic's bput lists).
WRONG_PICK = ("find a more appropriate tool",)
NO_PICK = ("you'll need a lockpick", "need a lockpick", "pick with what", "no lockpick")
BROKEN_PICK = (
    "lockpick breaks",
    "lockpick snaps",
    "breaks off in the lock",
)  # uncaptured
FREE_HAND = ("better have an empty hand first",)
PICK_RETRY = (
    "fails to teach you anything about the lock",
    "unable to make any progress towards opening the lock",
)
NOT_LOCKED = ("not even locked", "isn't locked", "is not locked")
UNLOCKED = ("open and remove the lock", "you unlock", "the lock opens")
MORE_LOCKS = ("discover another lock protecting",)
PICK_LOST = ("pick what", "what were you referring")
PICK_OUTCOMES = (
    ("sprung", TRAP_SPRUNG),
    ("injured", INJURED),
    ("lost", PICK_LOST),
    ("wrong pick", WRONG_PICK),
    ("broken pick", BROKEN_PICK),
    ("no pick", NO_PICK),
    ("free hand", FREE_HAND),
    ("more locks", MORE_LOCKS),
    ("retry", PICK_RETRY),
    ("not locked", NOT_LOCKED),
    ("unlocked", UNLOCKED),
)

# OPEN's answers.
OPEN_OUTCOMES = (
    ("locked", ("it is locked", "is locked")),
    ("lost", ("open what", "what were you referring")),
    ("open", ("you see", "already open", "you open", "there is nothing in")),
)

# GET <item> FROM MY <box>'s answers (pick.lic's loot_item).
TAKE_OUTCOMES = (
    ("gone", ("what were you referring", "get what")),
    (
        "no room",
        ("isn't any more room", "push you over the item limit", "you just can't"),
    ),
    ("free hand", ("need a free hand", "hands are full")),
    ("coins", ("you pick up",)),
    ("taken", ("you get", "you remove")),
)

_LISTED = re.compile(r"you see (.+?)\.\s*$", re.IGNORECASE | re.DOTALL)
_EMPTY = ("nothing in", "is empty", "there is nothing")


def listed(answer):
    """The items a LOOK IN or OPEN answer lists ("In the iron box you see
    some coins, a ruby and a dagger." -> ["some coins", "a ruby", "a
    dagger"]), repeats kept; [] for an empty container; None when the
    answer is no listing at all."""
    match = _LISTED.search(answer or "")
    if not match:
        lowered = (answer or "").lower()
        return [] if any(word in lowered for word in _EMPTY) else None
    items = re.split(r",\s*|\s+and\s+", match.group(1))
    return [item.strip() for item in items if item.strip()]


def boxes_in(answer):
    """The box nouns a container listing holds, repeats kept and in
    order: ["box", "coffer", "box"]; None when the container could not
    be read."""
    items = listed(answer)
    if items is None:
        return None
    return [noun_of(item) for item in items if noun_of(item) in BOX_NOUNS]


def parse_args(args):
    """;boxes' words: source=<container>, until=<mindstate>, once,
    careful (every step careful whatever the reading), stand (never
    sit), limit=<boxes>. (`nopractice` is gone with the practice mode,
    2026-09-23: an identify of a trap already read teaches nothing.)"""
    options = {
        "source": "",
        "until": 34,
        "once": False,
        "careful": False,
        "stand": False,
        "limit": 0,
    }
    for word in args or []:
        text = str(word).strip()
        lowered = text.lower()
        if lowered.startswith("source="):
            options["source"] = text.split("=", 1)[1].strip()
        elif lowered.startswith("until="):
            try:
                options["until"] = max(1, min(34, int(text.split("=", 1)[1])))
            except ValueError:
                pass
        elif lowered.startswith("limit="):
            try:
                options["limit"] = max(0, int(text.split("=", 1)[1]))
            except ValueError:
                pass
        elif lowered == "once":
            options["once"] = True
        elif lowered == "careful":
            options["careful"] = True
        elif lowered == "stand":
            options["stand"] = True
    return options
