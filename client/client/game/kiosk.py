"""A Trader's kiosk, read: the wordings ;kiosk sends and reads, pure.

    kiosk.listing(room_objs)     # [(target, name)]: "kiosk", "second kiosk", "plinth" ...
    kiosk.cast_name(answer)      # the kiosk a PRIA cast grew or refreshed, else None
    kiosk.read_study(answer)     # STUDY's reading: owner, markup, reserve, pouches, bundles, dispense
    kiosk.markup_of(answer)      # PULL/PUSH/STUDY's "set to N%", else None
    kiosk.markup_target(value)   # a wanted markup on the kiosk's 5% steps, -10 to 80
    kiosk.topup(reserve, floor, target)  # copper to POKE in, 0 above the floor
    kiosk.due(reading, kind, tap)        # True when that kind's stored value is worth a TAP
    kiosk.tapped(answer)         # "pouch" or "bundle" the TAP handed over, else None
    kiosk.rub_mode(answer)       # "pouch" or "bundle" RUB set it to, else None
    kiosk.offered(answer) / kiosk.paid(answer)  # an appraiser's or tanner's figure, copper

The measured mechanics are docs/kiosk.md; the wordings were captured at
Grisgonda's on 2026-10-16 (#567) unless a line says otherwise.
"""

import re

from client.game import items, money

# The Spells window's names, and the abbreviations PREPARE was seen to
# take (PREPARE PRIA 30, PREPARE FIN 72): a multi-word name can fail to
# parse ("prepare hands of justice", #320).
SPELL, SPELL_ABBREV = "Prosperity in Absentia", "pria"
MANA = 30  # lasts about an hour (docs/kiosk.md)
FINESSE, FINESSE_ABBREV = "Finesse", "fin"
TESSERA = "clear tessera"
ROOM = "4652"  # [Grisgonda's, Appraisal Room], the Crossing gem shop
MAX_KIOSKS = 6
MARKUP_MIN, MARKUP_MAX, MARKUP_STEP = -10, 80, 5
TAP_MAX = 500 * 10_000  # a TAP hands out up to 500 platinum of value
# A kiosk wears the Iridius crystal cube's look as a plinth; the nouns
# seen so far, as ;skins and sell-loot.lic read them.
NOUNS = ("kiosk", "plinth")
ORDINALS = ("", "second ", "third ", "fourth ", "fifth ", "sixth ")

OWNER = "as you examine your"
NOT_OWNER = "as you are not the owner of"
POKE_ASKS = "repeat the request to confirm"
POKED = "you drop some kronars into"
# The cast grows a kiosk; a cast while it stands refreshes it ("Malbog
# gestures at a euhedral crystalline kiosk, which responds by briefly
# undulating", a bystander's; the caster's is kiosk.lic's); POWER names it.
_GREW = re.compile(r"(?:^|, )an? ([^,.]+?) unfolds from nothingness", re.M)
_REFRESHED = re.compile(r"You gesture at an? ([^,.]+?), which responds by briefly")
_SENSED = re.compile(r"spell within an? ([^,.]+?), which will last")
_MARKUP = re.compile(r"set to (-?\d+)%")
_DISPENSE = re.compile(r"configured to dispense tied (gem pouch|bundle)")
_RUB = re.compile(r"set to pay out (pouch|bundle) sales")
_TAPPED = re.compile(r"revealing a crystalline (pouch|bundle) dusted in frost")
_AMOUNT = r"[\d,]+ (?:platinum|gold|silver|bronze|copper)"
_COINS = rf"((?:{_AMOUNT}(?:, and |, | and ))*{_AMOUNT}|[\d,]+) Kronars"
_RESERVE = re.compile(rf"holds {_COINS} in reserve")
_STORED = {
    "pouch": re.compile(rf"{_COINS} in pouches"),
    "bundle": re.compile(rf"{_COINS} in bundles"),
}
# The appraiser's quote ("I'll pay 723250 Kronars for it.", again "723250
# Kronars, take it or leave it!"), the tanner's ("I can give 245832
# Kronars for it."), and the sale ("...then hands you 723250 Kronars.").
_OFFER = re.compile(
    rf"(?:I'll pay|I can give) {_COINS}|\"{_COINS}, take it|\"{_COINS} is what"
)
_PAID = re.compile(rf"hands you {_COINS}")


def _subject(name):
    words = str(name or "").split()
    if words and words[0].lower() in ("a", "an", "some", "the"):
        words = words[1:]
    return " ".join(words).lower()


def listing(room_objs):
    """[(target, name)] for each kiosk the room lists, in its order: the
    target as a command names it ("kiosk", "second kiosk", "plinth"),
    the name without its article ("heptagonally symmetrical crystalline
    kiosk"). A listing's " and " inside a name ("spindly and acicular
    crystalline kiosk") stays in it (items.listed splits before an article)."""
    found, counts = [], {}
    text = re.sub(r"(?i)\byou also see\b", "You see", str(room_objs or ""))
    for entry in items.listed(text) or []:
        name = _subject(entry)
        noun = next((n for n in NOUNS if re.search(rf"\b{n}\b", name)), None)
        if noun is None:
            continue
        index = counts.get(noun, 0)
        counts[noun] = index + 1
        if index < len(ORDINALS):
            found.append((ORDINALS[index] + noun, name))
    return found


def cast_name(answer):
    """The kiosk's name, lowered, off a PRIA cast ("...a heptagonally
    symmetrical crystalline kiosk unfolds from nothingness."), its
    refresh, or POWER's line; None when the answer names none."""
    text = str(answer or "")
    for pattern in (_GREW, _REFRESHED, _SENSED):
        found = pattern.search(text)
        if found:
            return found.group(1).strip().lower()
    return None


def _copper(text):
    text = text.replace(",", "")
    return int(text) if text.isdigit() else money.to_copper(text)


def read_study(answer):
    """STUDY's reading, or None for an answer that is no STUDY: owner
    (bool), markup (int or None), and for the owner the copper of the
    reserve, of the pouches and of the bundles it holds now (the "current
    reserves" section, not the session's purchases) and which kind TAP
    dispenses ("pouch", "bundle" or None)."""
    text = " ".join(str(answer or "").split())
    lowered = text.lower()
    owner = OWNER in lowered
    if not owner and NOT_OWNER not in lowered:
        return None
    markup = markup_of(text)
    reading = {"owner": owner, "markup": markup}
    if not owner:
        return reading
    _, _, now = text.partition("current reserves")
    reserve = _RESERVE.search(now)
    reading["reserve"] = _copper(reserve.group(1)) if reserve else 0
    for kind, pattern in _STORED.items():
        stored = pattern.search(now)
        reading[kind] = _copper(stored.group(1)) if stored else 0
    dispense = _DISPENSE.search(text)
    reading["dispense"] = dispense.group(1).split()[-1] if dispense else None
    return reading


def markup_of(answer):
    """The markup a PULL, PUSH or STUDY answer says it is set to, else None."""
    found = _MARKUP.search(str(answer or ""))
    return int(found.group(1)) if found else None


def markup_target(value):
    """A wanted markup on the kiosk's steps: down to a multiple of 5,
    inside -10..80 (kiosk.lic's rule)."""
    value = int(value) // MARKUP_STEP * MARKUP_STEP
    return max(MARKUP_MIN, min(MARKUP_MAX, value))


def topup(reserve, floor, target):
    """The copper to POKE in: up to `target` once the reserve is under
    `floor`, else 0."""
    return max(0, target - reserve) if reserve < floor else 0


def due(reading, kind, tap):
    """True when the kiosk holds at least `tap` copper of `kind`."""
    return bool(reading) and (reading.get(kind) or 0) >= max(tap, 1)


def tapped(answer):
    """ "pouch" or "bundle", the item a TAP handed over, else None."""
    found = _TAPPED.search(" ".join(str(answer or "").split()))
    return found.group(1) if found else None


def rub_mode(answer):
    """ "pouch" or "bundle", what TAP pays out after a RUB, else None."""
    found = _RUB.search(str(answer or ""))
    return found.group(1) if found else None


def _figure(pattern, answer):
    found = pattern.search(" ".join(str(answer or "").split()))
    if not found:
        return None
    return _copper(next(g for g in found.groups() if g))


def offered(answer):
    """The copper an appraiser's or a tanner's quote names, else None."""
    return _figure(_OFFER, answer)


def paid(answer):
    """The copper a SELL's "hands you ..." paid, else None."""
    return _figure(_PAID, answer)
