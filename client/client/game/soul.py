"""A Paladin's soul — the state, the pool, and the deeds that raise them: the model behind ;soul.

The soul state (seven levels, read by RUB on a soulstone or the guild
orb, or by walking through a soulstone arch) sizes the soul pool
(eleven levels, read by EXHALE), and the circle-5 glyph quest's orb
wants both: "a Pristine Luminescent Soul" (Elanthipedia: Glyph of
Warding walkthrough) and, by the players' reports, a full pool — its
refusal is "you feel you need to rest and contemplate a bit first"
(captured 2026-09-18 and 2026-09-19 at chalky grey with the pool
empty, then at steady white with it at the second level). The state
drifts down over time but never below chalky grey on its own, and
what raises it is on timers (Elanthipedia: Soul system): a tithe of 5
silver at an almsbox every four hours (more coins give no more), a
prayer to Chadatru at his altar (dr-scripts' crossing-training prays
hourly; the game refused a second try 74 minutes after the first,
2026-09-19, so the timer here is longer), tending a non-Paladin's
wounds or guarding one against a creature hourly, undead kills at
random. What lowers it is what ;hunt must not do: fleeing, SMITE with
an empty pool (#217).

Captured wordings (2026-09-19, Shard): the almsbox — "You drop 5
silver dokoras into the almsbox and say a soft prayer as the coins
clink in." / "A warm, soothing sensation washes over your soul."; the
orb — "You rub the orb..." / "It fades to a dull, chalky color." then
"It warms slightly and turns a steady white hue!", "You breathe
softly on the orb..." / "Nothing special seems to happen." then "You
catch the faintest flicker of light."; the tower's arch — "You step
through a gleaming soulstone archway...." / "The archway emits a warm,
steady white hue!"; the prayer — "As you kneel down to pray, you feel
your head is not cleared enough to pay proper respect to Chadatru."
(the prayer has begun: stay knelt about 75 seconds for "After
clearing your thoughts, you pray deeply toward Chadatru.  A warm,
soothing sensation washes over your soul." — captured 02:34, two
hours after the first attempt, which is the timer here) and
"You start to pay respect to Chadatru again when you decide it would
be inappropriate so soon.  You decide to wait awhile longer." The
quest scene's lines are dr-scripts' paladin-quests.lic's until the
orb accepts a FOCUS here: "You clear your mind of all thoughts" opens
the vision, "You focus your magical senses" is its own refusal, the
girl's "in a few brief moments she will be past you and beyond help"
wants GUARD GIRL ("Despite the hopelessness of the situation"), and
"and use my gift" ends it — all three held when the orb accepted the
FOCUS (2026-09-19 05:40, 65 minutes after a refusal at pristine and
full): "You clear your mind of all thoughts and focus only on the task
ahead.  Vision fades as darkness slowly overcomes you. ...", the
girl's line as the walkthrough has it, "Despite the hopelessness of
the situation, you move to guard the fleeing girl, raising your
battered old sword in defiance. ...", and "'Go now, and use my gift
to preserve those who have fallen with honor.'"; GLYPH then lists
"the Glyph of Warding". The pilgrim's badge (2026-09-20: bought by a
Cleric in Brother Durantine's storeroom, bonded with KISS, four
attuned sites PUSHed onto it) is the cheap deed: PRAY BADGE, held,
every thirty-one minutes — "As you feel your connection to them grow,
you sense the eyes of the gods upon you." / "A warm, soothing
sensation washes over your soul." / "You feel a strengthening of your
faith and bolstering of your soul."; with nothing on it "You think
really hard about your badge.  It doesn't do anything though." Model:
docs/soul.md.
"""

import json
import os
import re
import time
from pathlib import Path

# Soul states, worst to best, by the phrase the reading carries
# (Elanthipedia: Soul system). A RUB and an arch use the same words.
STATES = (
    (1, "corruption of your soul"),
    (1, "freezes your hand"),
    (2, "cold and lifeless"),
    (3, "pallid grey"),
    (4, "chalky"),
    (5, "steady white hue"),
    (6, "pure white light"),
    (7, "pristine luminescence"),
)
STATE_WORDS = {
    1: "black, corrupted",
    2: "cold and lifeless grey",
    3: "pallid grey",
    4: "chalky grey",
    5: "steady white hue",
    6: "pure white light",
    7: "pristine luminescence",
}
PRISTINE = 7
# Soul pool levels, by phrase, most specific first so a phrase that
# contains another's words is read before it (the wiki's eleven, plus
# the empty pool's "Nothing special seems to happen.", captured).
POOLS = (
    (11, "not cast shadows"),
    (10, "powerful inner light, which lingers"),
    (9, "lingers for a few moments"),
    (8, "lingers for a moment"),
    (7, "pulses rapidly"),
    (5, "pulses briefly"),
    (6, "pulses with an inner light"),
    (3, "briefly flickers"),
    (4, "flickers with an inner light"),
    (1, "might have imagined"),
    (2, "catch the faintest flicker"),
    (0, "nothing special seems to happen"),
)
POOL_FULL = 11

# The deeds' timers, in seconds. The tithe's is the wiki's four
# hours; the prayer's is unmeasured — dr-scripts assumes an hour, the
# game refused at 74 minutes (2026-09-19) — so two hours until a
# reading says otherwise, and a refusal backs off twenty minutes.
TITHE_SECONDS = 4 * 3600
PRAY_SECONDS = 2 * 3600
BADGE_SECONDS = 31 * 60  # PRAY BADGE (Elanthipedia: Pilgrim's badge)
REFUSED_BACKOFF = 20 * 60
TITHE_SILVER = 5
PRAYER_WAIT = 150  # seconds knelt for the prayer to complete (about 75)

# The tithe: the almsbox's answers.
TITHED = ("soft prayer as the coins clink", "soothing sensation")
TITHE_SHORT = ("but you do not",)  # dr-scripts' tithe.lic: not enough coins
TITHE_REFUSED = ("attend to thy own woes",)  # dr-scripts' tithe.lic
# PRAY BADGE, the pilgrim's badge held (captured 2026-09-20 with four
# attuned sites on it): the boost, an empty badge, one not bonded to
# the character, and no badge at all.
BADGE_DONE = ("strengthening of your faith", "soothing sensation")
# Within the timer the contemplation plays without the soul line
# (captured 2026-09-20, nine minutes after a boost): "You think upon
# the Immortals, and the holy places built in their honor ..." / "As
# you feel your connection to them grow, you sense the eyes of the
# gods upon you." and nothing more.
BADGE_SOON = ("eyes of the gods upon you",)
BADGE_EMPTY = ("doesn't do anything",)
BADGE_NOT_YOURS = ("not your pilgrim's badge",)
BADGE_NONE = ("what were you referring", "could not find")
# The prayer's answers.
PRAYER_BEGUN = ("head is not cleared enough",)
PRAYER_DONE = ("soothing sensation washes over your soul",)
PRAYER_SOON = ("inappropriate so soon",)
# The quest's orb (FOCUS ORB): the refusals and the vision's lines.
FOCUS_REST = ("rest and contemplate",)
FOCUS_REFUSED = ("you focus your magical senses",)  # dr-scripts' requirements line
FOCUS_BEGUN = ("you clear your mind of all thoughts",)  # captured 2026-09-19
GIRL = "in a few brief moments she will be past you and beyond help"
GUARDED = ("despite the hopelessness of the situation",)  # captured
QUEST_DONE = ("and use my gift",)  # captured
SCENE_SECONDS = 600  # the vision "will take a while"

# Where the deeds are done: map rooms with a Chadatru altar or statue
# (Elanthipedia: Chadatru; the tower's chapel captured 2026-09-19) and
# the map's own tags for the rest ("tithe" on the almsbox rooms,
# "chadatru" on a chapel). ALMSBOXES adds the rooms the map has not
# tagged (Elanthipedia: Almsbox).
ALTARS = {
    5845: "Eyes of the Thirteen, Chadatru's Shrine (the Crossing temple)",
    13430: "Tower of Honor, Chapel (Shard)",
    13380: "Ger Ilerthan, Chapel",
    17046: "Chadatru's Temple, Great Hall",
}
ALMSBOXES = {
    13143: "Temple of Light, Alcove of Smaragdaus (Shard)",
    12961: "Paladins' Guild, Foyer (Ratha)",
    # The Crossing's two, read off the rooms 2026-09-20: "the locked
    # almsbox" outside the temple gate, and "a steel tithe box" outside
    # the Paladins' Guild whose inscription reads "To donate: PUT
    # [amount] [coin type] KRONARS IN BOX" — so the PUT says `box` there.
    741: "The Crossing, Immortals' Approach (outside the temple gate)",
    815: "The Crossing, Herald Street (outside the Paladins' Guild)",
}
TITHE_BOX = "tithe box"  # the guild's box: the noun is `box`, not `almsbox`
ORB_ROOM = 8228  # Tower of Honor, Orb Room: the soulstone orb
# The coin the almsbox asks for, by the province the room's title names
# (Elanthipedia: Currency): Ilithi, Qi and the islands take Dokoras,
# Therengia Lirums, Zoluren and the rest Kronars.
_DOKORA_TOWNS = ("shard", "temple of light", "ratha", "aesry", "mer'kresh", "hara")
_LIRUM_TOWNS = ("riverhaven", "theren", "langenfirth", "hibarnhvidar", "muspar")


def parse_state(text):
    """The soul state (1-7) a RUB or an arch line carries, or None."""
    lowered = (text or "").lower()
    for level, phrase in STATES:
        if phrase in lowered:
            return level
    return None


def parse_pool(text):
    """The soul pool level (0-11) an EXHALE answer carries, or None."""
    lowered = (text or "").lower()
    for level, phrase in POOLS:
        if phrase in lowered:
            return level
    return None


def describe(state, pool):
    """One line: "soul: steady white hue (5/7), pool: faintest flicker (2/11)"."""
    parts = []
    if state is not None:
        parts.append(f"soul: {STATE_WORDS.get(state, '?')} ({state}/{PRISTINE})")
    if pool is not None:
        parts.append(f"pool: {pool}/{POOL_FULL}")
    return ", ".join(parts) or "no reading"


def ready_for_quest(state, pool):
    """Whether the orb should accept a FOCUS: pristine and full."""
    return state == PRISTINE and pool == POOL_FULL


def currency_for(title):
    """The almsbox's coin from its room title: "dokoras", "lirums" or
    "kronars"."""
    lowered = (title or "").lower()
    if any(town in lowered for town in _DOKORA_TOWNS):
        return "dokoras"
    if any(town in lowered for town in _LIRUM_TOWNS):
        return "lirums"
    return "kronars"


def box_noun(room_objs):
    """The noun the PUT names, off the room's listing: `box` where the
    listing shows a tithe box (the Crossing's Paladins' Guild, whose
    steel box reads "PUT ... KRONARS IN BOX"), `almsbox` otherwise."""
    return "box" if TITHE_BOX in (room_objs or "").lower() else "almsbox"


def tithe_command(currency, noun="almsbox"):
    return f"put {TITHE_SILVER} silver {currency} in {noun}"


def classify(text, *outcomes):
    """The first outcome name whose phrases the text holds, else None:
    classify(answer, ("done", TITHED), ("short", TITHE_SHORT))."""
    lowered = (text or "").lower()
    for name, phrases in outcomes:
        if any(phrase in lowered for phrase in phrases):
            return name
    return None


# --- the timers, kept per character across runs -----------------------------
def store_dir() -> Path:
    return Path(os.environ.get("REVENANT_SOUL_DIR", "~/.revenant/soul")).expanduser()


def store_path(character) -> Path:
    return store_dir() / f"{str(character or 'unknown').lower()}.json"


def load_timers(character) -> dict:
    """{deed: unix time of the last accepted deed, "<deed>_refused": the
    last refusal}; {} for none."""
    try:
        data = json.loads(store_path(character).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_timers(character, timers) -> None:
    path = store_path(character)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(timers, indent=1), encoding="utf-8")


def due(timers, deed, now=None):
    """Seconds until the deed's timer allows it again (0 when due now):
    the deed's own timer since the last acceptance, or the backoff
    since the last refusal, whichever ends later."""
    now = time.time() if now is None else now
    period = {"tithe": TITHE_SECONDS, "pray": PRAY_SECONDS, "badge": BADGE_SECONDS}[
        deed
    ]
    waits = []
    if deed in timers:
        waits.append(timers[deed] + period)
    if f"{deed}_refused" in timers:
        waits.append(timers[f"{deed}_refused"] + REFUSED_BACKOFF)
    return max(0, max(waits) - now) if waits else 0


def mark(timers, deed, accepted, now=None):
    """Record the deed's acceptance or refusal at `now`."""
    now = time.time() if now is None else now
    timers[deed if accepted else f"{deed}_refused"] = now
    return timers


_OPTION = re.compile(r"^(\w+)=(.*)$")


def parse_args(words):
    """;soul's words: the verb ("read" by default, "keep", "tithe",
    "pray", "badge", "quest") and the options almsbox=ID, altar=ID,
    currency=X, force."""
    options = {
        "verb": "read",
        "almsbox": None,
        "altar": None,
        "currency": "",
        "force": False,
    }
    for word in words or []:
        match = _OPTION.match(word)
        if match:
            key, value = match.group(1).lower(), match.group(2).strip()
            if key in ("almsbox", "altar"):
                options[key] = int(value) if value.isdigit() else None
            elif key == "currency":
                options[key] = value.lower()
            continue
        lowered = word.lower()
        if lowered == "force":
            options["force"] = True
        elif lowered in ("read", "keep", "tithe", "pray", "badge", "quest"):
            options["verb"] = lowered
    return options
