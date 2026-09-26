"""An Empath's healing in words: a patient's wounds read off TOUCH, taken
worst first, and the Empath's own healed with Heal Wounds and Heal Scars.

An Empath heals another by transferring the wounds to himself and then
healing his own body with spells (Elanthipedia: Empath healing, Take
command, Heal Wounds, Heal Scars). TOUCH <patient> forges the diagnostic
link and lists every wound by body part — sent to the `familiar` stream,
not the story — and TAKE <patient> <part> [INTERNAL] [SCAR] moves one;
the link holds while the TAKEs follow each other and lapses after a
while idle ("You have no empathic link with <patient>", TOUCH again).
The order is the operator's (2026-09-26): the most life-threatening
first — anything bleeding, then the severest, the head and torso before
the limbs at the same severity, a fresh wound before a scar. Heal Wounds
cast at a part heals its external wounds and then its internal ones;
Heal Scars the same for scars; CAST <part> INTERNAL only the inside.

Captured 2026-09-26, Riphik (Empathy 484) healing Cecil:
  TOUCH CECIL     You touch Cecil. / You sense a successful empathic link
                  has been forged between you and Cecil. / (familiar)
                  Cecil's injuries include... / Wounds to the LEFT ARM: /
                    Fresh External:  cuts and bruises about the left arm
                  -- minor / ... / Cecil has normal vitality.
                  — and with nothing left: "... no injuries to speak of."
                  / "You sense nothing wrong with Cecil."
  TAKE CECIL CHEST  You touch Cecil. / You feel the transfer beginning as
                  a cold stillness settles in the center of your being...
                  / You sense that Cecil's external chest wounds are
                  fully healed.  (internal: "internal chest wounds";
                  scars: "external chest scars", "internal chest scars")
  (the link lapsed)  You have no empathic link with Cecil and cannot
                  transfer his wounds.
  PREPARE HW 15   With meditative movements you prepare your body for
                  the Heal Wounds spell. / You feel fully prepared to
                  cast your spell.
  CAST LEFT ARM   You gesture. / The external wounds on your left arm
                  appear completely healed. / The internal wounds on your
                  left arm appear completely healed.
                  (Heal Scars: "The internal scars on your abdomen appear
                  greatly improved." — a second cast finished it)
Taking a patient's fresh wounds bared scars the first TOUCH had not
listed (internal scars on the limbs, the chest, the nerves), so the
patient is touched again after a round and the new ones taken too.
The patient saw "Riphik touches you.  He'll probably get warts." at
every TOUCH — one per round, not one per TAKE.
"""

import re
from dataclasses import dataclass

from client.game.wounds import level

# TOUCH's row labels -> the wound kinds client/game/wounds.py names.
_KINDS = {
    "fresh external": "external",
    "fresh internal": "internal",
    "scars external": "scar",
    "scars internal": "internal_scar",
}
_PART = re.compile(r"^Wounds to the (?P<part>[A-Z ]+):\s*$")
_ROW = re.compile(
    r"^\s*(?P<label>Fresh External|Fresh Internal|Scars External|Scars Internal):"
    r"\s*(?P<phrase>.*?)\s*--\s*(?P<severity>[a-z]+)\s*$"
)
NO_INJURIES = ("no injuries to speak of", "you sense nothing wrong with")
LINKED = ("empathic link has been forged",)
NO_LINK = ("you have no empathic link",)
AVOIDED = ("avoids your touch",)
TAKEN = ("fully healed",)
TRANSFERRING = ("you feel the transfer beginning",)
PREPARED = ("fully prepared to cast",)
HEALED = ("appear completely healed",)
IMPROVED = ("appear", "improved", "better")

# The head and torso before the limbs at one severity: a wound there is
# the one that kills (the wiki's shock and death rules follow the vital
# areas).
VITAL = ("head", "neck", "chest", "abdomen", "back", "skin", "right eye", "left eye")


@dataclass(frozen=True)
class Injury:
    part: str  # "left arm", "skin" — as TAKE and CAST want it
    kind: str  # external | internal | scar | internal_scar
    level: int  # 1 insignificant .. 8 useless (client/game/wounds.py)
    phrase: str = ""
    bleeding: bool = False


def parse_touch(text):
    """The Injury list a TOUCH listing names ([] for "no injuries to speak
    of"), or None when the text holds no listing at all."""
    injuries = []
    part = None
    seen = False
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        lowered = line.lower()
        if "injuries include" in lowered or any(n in lowered for n in NO_INJURIES):
            seen = True
        match = _PART.match(line.strip())
        if match:
            part = match.group("part").lower()
            seen = True
            continue
        match = _ROW.match(line)
        if match and part:
            try:
                severity = level(match.group("severity"))
            except ValueError:
                continue
            injuries.append(
                Injury(
                    part,
                    _KINDS[match.group("label").lower()],
                    severity,
                    match.group("phrase"),
                    "bleeding" in match.group("phrase").lower(),
                )
            )
        elif part and "bleeding" in lowered:
            # A bleeding row's wording is uncaptured: any line under a
            # part that says so puts that part first (the wiki's TOUCH
            # BLEEDING filter).
            injuries.append(Injury(part, "external", 9, line.strip(), True))
    return injuries if seen else None


def priority(injury):
    """The sort key, most urgent first: bleeding, severity, a vital part,
    a fresh wound before a scar, the outside before the inside."""
    return (
        not injury.bleeding,
        -injury.level,
        injury.part not in VITAL,
        injury.kind in ("scar", "internal_scar"),
        injury.kind in ("internal", "internal_scar"),
    )


def transfer_order(injuries):
    return sorted(injuries, key=priority)


def take_command(patient, injury):
    """TAKE <patient> <part> [INTERNAL] [SCAR]."""
    words = [f"take {patient.lower()} {injury.part}"]
    if injury.kind in ("internal", "internal_scar"):
        words.append("internal")
    if injury.kind in ("scar", "internal_scar"):
        words.append("scar")
    return " ".join(words)


def heal_casts(health):
    """The self-heal casts for a parsed HEALTH (client/game/wounds.py's
    Health), most urgent first: (spell, target) — "hw" for fresh wounds,
    "hs" for scars, the target the part alone when its outside is hurt
    (the spell heals outside then inside) or "<part> internal" when only
    the inside is."""
    casts = []
    for wound in health.wounds.values():
        area = wound.area
        for spell, outside, inside in (
            ("hw", wound.external, wound.internal),
            ("hs", wound.scar, wound.internal_scar),
        ):
            worst = max(outside, inside)
            if not worst:
                continue
            target = area if outside else f"{area} internal"
            key = (
                -worst,
                area not in VITAL,
                spell == "hs",
            )
            casts.append((key, spell, target))
    return [(spell, target) for _, spell, target in sorted(casts)]
