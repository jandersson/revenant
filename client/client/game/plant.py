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
RITUAL = ("your ritual directs the energy", "fully prepared to cast")
LOST = ("your concentration slips", "your spell is lost")
FORMED = ("vela'tohr plant forms",)
STRAIN = ("will disrupt about half your current attunement",)
# The creator's TOUCH, the wiki's wordings until captured.
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
