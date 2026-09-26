"""The scripted arena ;hunt's tests fight in, shared by test_hunt*.py.

The hunt script loaded from disk with its waits shortened, the ground
(a MapDB of three shipyard rooms and home), the profile, the captured
game wordings every topic file reads, the Arena (each command prefix a
queue of answers, an answer optionally with an effect on the fight) and
the stubs that stand in for the walker. Every wording carries the date
it was captured; docs/hunting.md is the model they pin.
"""

import importlib.util
import pathlib
from types import SimpleNamespace
from client.game import buffs
from client.game.mapdb import MapDB
from client.game.profile import DEFAULTS


REPO = pathlib.Path(__file__).parents[2]


def _hunt():
    spec = importlib.util.spec_from_file_location(
        "hunt_script", REPO / "scripts/hunt.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hunt = _hunt()


hunt.COLLECT_SECONDS = 0.01


hunt.TAIL_SECONDS = 0.01


hunt.SETTLE_SECONDS = 0.0


hunt.EMPTY_ROOM_WAIT = 0


hunt.MAX_ITERATIONS = 400  # a ground the arena cannot fill ends on the fuse


hunt.ADVANCE_WAIT = 0.01


hunt.LISTING_WAIT = 0.01


buffs.PREPARE_SECONDS = 0.01


buffs.CAST_GAP_SECONDS = 0


YARD = "[Barana's Shipyard, Lumber Storage]"


GROUND = MapDB(
    [
        {
            "id": 6046,
            "uid": [21101],
            "title": [YARD],
            "tags": ["rats"],
            "wayto": {"6047": "east"},
        },
        {
            "id": 6047,
            "uid": [21102],
            "title": [YARD],
            "tags": ["rats"],
            "wayto": {"6046": "west", "6048": "north"},
        },
        {
            "id": 6048,
            "uid": [21103],
            "title": ["[Barana's Shipyard, Gate]"],
            "tags": [],
            "wayto": {"6047": "south"},
        },
        {"id": 1, "uid": [1], "title": ["[Town Green]"], "tags": ["home"], "wayto": {}},
    ]
)


PROFILE = DEFAULTS | {
    "weapon": "handaxe",
    "cast_gap": 0,  # the cadence tests count casts per swing
    "weapon_container": "sack",
    "stance": "100 80 0",
    "prey": "rat",
    "skin": True,
    "loot_container": "sack",
    "home": "home",
    "wound_floor": "off",  # the floor's own tests set one (#236: empty is harmful)
}


# The kill line as captured on a rat (2026-09-05) and a badger
# (2026-09-14). "The rat slowly tips over and falls down." stood here
# until 2026-09-14: it is a knockdown (#197), see KNOCKED_DOWN.
KILL = "The rat falls to the ground and lies still."


KNOCKED_DOWN = (
    "The rat slowly tips over and falls down.\nYou also see a rat that appears stunned."
)


# Captured 2026-09-20 on a striped badger (#240): a knockdown that
# shares "falls to the ground" with the kill line, the badger standing
# back up at the skin, and the 2026-08-22 cougars' own kill wording.
MANGLED = (
    "A striped badger screams and falls to the ground grasping its mangled "
    "left leg!\n[You're nimbly balanced and in dominating position.]\n"
    "[Roundtime 4 sec.]\nYou also see a striped badger that is lying down."
)


STOOD_UP = (
    "The striped badger grimaces as it stands back up.\n"
    "You also see a striped badger.\nSkin what?"
)


LIFELESS = "Twisting in agony, the cougar falls to the ground lifeless."


# Captured 2026-09-13 (#183): SMITE's own line, then the swing as usual.
SMITE_KILL = (
    "Drawing strength from your conviction, you execute a divinely inspired "
    "strike!\n" + KILL
)


# Captured 2026-09-05, the first live ;hunt: the kill line the script
# did not know, and the corpse answer with a two-word noun.
RAT_KILL = "The ship's rat falls to the ground and lies still."


RAT_CORPSE = "The ship's rat is already quite dead."


SKINNED = "You skin the rat, obtaining a rat pelt."


NOTHING = "You search the rat.\nYou find nothing of value."


# Captured 2026-09-20 on the first live fists turn (#238), a striped
# badger, brass knuckles and a parry stick worn: PUNCH swings the worn
# knuckles, KICK the foot, ELBOW the armored elbow — each in the
# combat stream, shaped like a weapon swing, and the kill line the same.
PUNCHED = (
    "< Moving with the precision of a mongoose, you punch your brass knuckle "
    "at a striped badger.  A striped badger attempts to dodge, avoiding only "
    "some of the blow.  The knuckle lands a hard hit to the badger's right arm."
)


PUNCH_MISSED = (
    "< You punch your brass knuckle at a striped badger.  A striped badger "
    "evades, just stepping out of harm's way.  "
)


KICKED = (
    "< Moving with indomitable grace, you kick your foot at a striped badger.  "
    "A striped badger fails to dodge, avoiding only some of the blow.  The foot "
    "lands a good strike to the badger's left arm."
)


ELBOWED = (
    "< Moving as a single sinuous force, you elbow your plate-clad elbow at a "
    "striped badger.  A striped badger fails to dodge, only slightly avoiding "
    "the blow.  The elbow lands a solid hit to the badger's left leg."
)


class Arena:
    """A scripted fight: each command prefix has a queue of answers, and
    an answer may be (text, effect) where effect(arena) changes state —
    the kill that empties the hostile list."""

    def __init__(
        self, answers, hostiles=("1",), health=100, room=6046, experience=None
    ):
        self.answers = {prefix: list(queue) for prefix, queue in answers.items()}
        self.sent = []
        self.echoed = []
        self.commands = []
        self.pending = []
        self.walks = []
        self.arrivals = {}  # room -> hostiles present on arrival
        self.room = room
        self.dead = False
        self.listing = True  # the game re-sends the room listing on a death
        self.state = SimpleNamespace(
            name="Lanival",
            hostiles={exist: True for exist in hostiles},
            vitals={"health": health},
            compass=["west"],
            room_title=YARD,
            experience=experience or {},
            room=room,  # what the stubbed locate() answers
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command.startswith(prefix) and queue:
                answer = queue.pop(0)
                before = sum(getattr(self.state, "room_creatures_dead", None) or [])
                if isinstance(answer, tuple):
                    answer, effect = answer
                    effect(self)
                marked = sum(getattr(self.state, "room_creatures_dead", None) or [])
                if self.listing and hunt.is_kill(answer) and marked == before:
                    # The game re-sends the room's listing on a death,
                    # the corpse marked "which appears dead" — what the
                    # hunt counts kills by (#315) — unless the answer's
                    # own effect marked it already.
                    mark_corpse(self, hunt.kill_noun(answer) or "rat")
                self.pending = [line + "\n" for line in answer.splitlines()]
                return

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def echo(self, text):
        self.echoed.append(text)

    def command(self, timeout=None):
        return self.commands.pop(0) if self.commands else None

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def kill(arena):
    arena.state.hostiles.clear()


def mark_corpse(arena, noun):
    """The room listing gains a corpse of `noun`, as the parser reads
    the game's re-sent listing ("a rat which appears dead")."""
    state = arena.state
    state.room_creatures = list(getattr(state, "room_creatures", None) or []) + [
        f"a {noun}"
    ]
    state.room_creatures_dead = list(
        getattr(state, "room_creatures_dead", None) or []
    ) + [True]


def _run(arena, profile=PROFILE, travel_first=True):
    # STORE was set on an earlier run: the arena's fights start where
    # they did before STOW GEM / STOW BOX (test_hunt_stores.py sets it).
    hunt.remember_stores(
        getattr(arena.state, "name", None),
        {
            "boxes": str(profile.get("loot_container") or "").lower(),
            "gems": str(profile.get("gem_pouch") or "").lower(),
        },
    )
    hunt.hunt(arena, dict(profile), GROUND, travel=travel_first)
    return arena


ROTATING = PROFILE | {
    "weapons": ["handaxe:Small Edged:sack", "fists:Brawling"],
    "brawling": ["punch", "kick", "elbow"],
    "tactics": [],
}


class Patient(Arena):
    """An arena whose operator types ;hunt return once the loop has
    paused on an empty ground the given number of times."""

    def __init__(self, *args, pauses=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.pauses = pauses

    def echo(self, text):
        super().echo(text)
        if "ground empty" in text:
            self.pauses -= 1
            if self.pauses == 0:
                self.commands.append("return")


MISSED = "< You slice an oak-hafted handaxe at a rat.  A rat dodges, barely stepping to one side.  "


# Captured 2026-09-12, the second live ;hunt: two skin successes the
# table did not know (the tail's line landed after the roundtime and
# the tail stayed in hand, so the next three skins refused), and the
# answers a corpse noun gets once the corpse is gone and a live rat
# matches it instead.
PELT_LOOSE = (
    "With preternatural poise, you work loose a sterling example of a rat "
    "pelt from the rat carcass."
)


TAIL_REMOVED = (
    "Working deftly, you skillfully remove a rat tail from the remains of a "
    "ship's rat.  The task is difficult, but the rewards are worth it."
)


BUNDLING = PROFILE | {"bundle": True, "home": ""}


def _hands(arena, left=None, right={"noun": "handaxe"}):
    arena.state.left_hand = left
    arena.state.right_hand = right


# Captured 2026-09-12: Heroic Strength prepared and cast by a circle-1
# Paladin (docs/hunting.md). The Spells window says when it has run out.
PREPARED = "You begin chanting a prayer to invoke the Heroic Strength spell."


CAST = (
    "You gesture.\nThe spell takes effect, the invisible flame of your soul "
    "intertwining with your flesh.  You feel holy strength and vigor course "
    "through your body."
)


BUFFED = PROFILE | {"buffs": ["heroic strength"], "home": ""}


TRAINING = BUFFED | {"train_casting": "Augmentation"}


def _exp(mindstate):
    return {"Augmentation": {"rank": 3, "percent": 66, "mindstate": mindstate}}


def prepares(arena):
    return [command for command in arena.sent if command.startswith("prepare")]


# Stun Foe's cast at minimum mana, captured 2026-09-14 on a striped
# badger (#192) — the wiki's "brilliant stream of pure white light" is
# the line at more mana; the resist and failure wordings are still
# uncaptured.
STUNNED = (
    "You gesture at a rat.\nA stream of dull golden light jumps from you to a "
    "rat, which warps into a spiraling force as it slams into it!\n"
    "You also see a rat that appears stunned."
)


SF_PREPARED = "You begin chanting a prayer to invoke the Stun Foe spell."


STUNNING = PROFILE | {"debilitation": "stun foe"}


# DISCERN's estimate is the wiki's until captured (#202).
DISCERNED = "You think you could weave at most 27 mana streams into this spell."


DEBIL_OPEN = {"Debilitation": {"rank": 1, "percent": 0, "mindstate": 5}}


def _stands(arena):
    """A kill line after which the room still holds a live hostile:
    another rat stands beside the fallen one in the parser's set. One
    hostile listed and it just fell is a clear room (#252)."""
    arena.state.hostiles["2"] = True


# Captured 2026-09-20 on a circle-5 Paladin with Conviction 49.
SMITE_CHECK_THREE = (
    "You contemplate the strength of your conviction.\n"
    "Your conviction is enough to deliver three blows against your enemies "
    "before you must either rest or draw upon your spiritual strength to continue.\n"
)
