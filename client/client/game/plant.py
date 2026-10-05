"""An Empath's vela'tohr plant, kept up (#473): the cast's wordings, the
plant's life as PERCEIVE reports it, and the record `;train` reads to
know when the next cast is due.

Embrace of the Vela'Tohr (EV) is an Empath's ritual spell: PREPARE EV,
INVOKE the ritual focus (a phial of phofe attar, 40 uses), CAST. An
ethereal plant forms in the room and slowly heals a non-Empath who
TOUCHes it and stays there out of combat. It lasts 30 to 90 roisaen (a
roisaen is a real minute), ends when its Empath logs out, and despawns
at its healing limit. The Empath TOUCHes it to take its wounds, which
teaches Empathy (Elanthipedia: Embrace of the Vela'tohr; Time).

The record is ~/.revenant/training/<name>.plant.json: the room, the
cast's time, its minutes, and the session's pid, since a new session
means a logout ended the plant.
"""

import json
import re
import time

SPELL = "ev"
MANA = 500  # Riphik's cast of 2026-10-04: sixty-two roisaen
FOCUS = "phial"
MANA_FLOOR = 50  # % of mana below which the cast waits
MARGIN_MINUTES = 10  # recast this long before the recorded end
DEFAULT_MINUTES = 30  # the spell's least, for a cast PERCEIVE did not time
PLANT = "vela'tohr plant"

# Captured 2026-10-04, Riphik in the Paladins' Guild Chambers.
PREPARED = ("prepare your body for the embrace",)
INVOKED = ("draw the spell pattern's shadow",)
# The CAST waits for "fully prepared": the ritual's own lines ("Your
# ritual directs the energy...", "...burns away") come first, and a CAST
# after them but before it backfired (2026-10-05 00:11); the casts that
# formed a plant came after it (2026-10-04 01:5x and 23:01).
RITUAL = ("fully prepared to cast",)
LOST = ("your concentration slips", "your spell is lost")
FORMED = ("vela'tohr plant forms",)
CAST_FAILED = (
    "too mentally fatigued",
    "slips away",
    "don't have a spell prepared",
    "backfires",  # "Your spell badly backfires." (2026-10-05 00:12)
)
# A PREPARE refused for something still running, and what ends it.
# An empty ender: the PREPARE sent again is the confirmation the game
# asks for ("Are you sure you want to do that?  You'll interrupt your
# research!", 2026-10-05 14:12 — a research portion still running after
# ;research's return); the portion is lost, the plant kept up.
IN_THE_WAY = (
    ("stop playing before", "stop play"),
    ("stop practicing", "stop climb"),
    ("interrupt your research", ""),
)
STRAIN = ("will disrupt about half your current attunement",)
# The creator's TOUCH, the wiki's wordings, captured as such on Riphik
# (2026-10-05): "...erupt in agony and blossom with wounds!  Your
# vela'tohr plant looks healthier!"
NO_NEED = ("no need of healing",)
TOOK = ("looks healthier", "blossom with wounds", "erupt in agony")

_LASTS = re.compile(
    r"Embrace of the Vela'Tohr spell upon you, which will last for about "
    r"([\w -]+?) roisaen",
    re.IGNORECASE,
)
_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def number(words):
    """A number the game spells out ("sixty-two") as an int, or None."""
    words = str(words or "").strip().lower()
    if words.isdigit():
        return int(words)
    total = 0
    for part in re.split(r"[\s-]+", words):
        if part in _ONES:
            total += _ONES.index(part)
        elif part in _TENS:
            total += 20 + 10 * _TENS.index(part)
        elif part and part != "and":
            return None
    return total or None


def lasts(text):
    """The plant's minutes left from PERCEIVE's "...will last for about
    sixty-two roisaen.", or None."""
    match = _LASTS.search(str(text or ""))
    return number(match.group(1)) if match else None


def said(text, needles):
    lowered = str(text or "").lower()
    return any(needle in lowered for needle in needles)


def record_path(name):
    from client.game.training import training_dir

    return training_dir() / f"{str(name).lower()}.plant.json"


def record(name, room, minutes, session, now=None):
    """The cast written down: where, when, for how long, in which session."""
    path = record_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "room": str(room),
                "cast": time.time() if now is None else now,
                "minutes": int(minutes),
                "session": session,
            }
        ),
        encoding="utf-8",
    )


def load(name):
    """The last cast's record, or None."""
    try:
        return json.loads(record_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def due(name, room, session, now=None, margin=MARGIN_MINUTES):
    """True when the plant in `room` wants a cast: none recorded, one in
    another room or another session (a logout ended it), or within
    `margin` minutes of its end."""
    mark = load(name)
    if not isinstance(mark, dict):
        return True
    if str(mark.get("room")) != str(room) or mark.get("session") != session:
        return True
    try:
        ends = float(mark["cast"]) + 60 * int(mark["minutes"])
    except (KeyError, TypeError, ValueError):
        return True
    now = time.time() if now is None else now
    return now >= ends - 60 * margin
