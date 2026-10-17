"""A ranged weapon's shot and its ammunition picked up again: the
turn of a hunt whose skill is Slings, Bow or Crossbow (;hunt).

    shoot(s, prey, ask)    LOAD, AIM, the aim waited out, FIRE; FIRE's answer
    pick_up(s, ammo, ask)  STOW <ammo> until "Stow what?": the stones a search freed

The weapon is held in the right hand (WIELD, as every turn). A bare LOAD
takes the first suitable ammunition from the hands, the feet, then the
containers; AIM starts the aim and the game says when it is full; FIRE
spends it. A shot that does not lodge lands at the feet and is stowed at
once; a lodged one comes out of the corpse on the search and lies in the
room. STOW puts ammunition in the quiver. Sources: dr-scripts'
combat-trainer.lic (attack_aimed, shoot_aimed, stow_ammo) and
Elanthipedia's Load, Aim and Fire command pages (docs/bibliography.md).
"""

import re

from client.game import probe

SKILLS = frozenset({"Slings", "Bow", "Crossbow"})

# combat-trainer's firing_delay: the longest aim before the shot goes
# anyway, when the game never says the aim is full.
AIM_SECONDS = 15
PICKUP_MOST = 10  # STOWs after a search, the bound on the loop

# Captured 2026-10-17 on a hide sling, small rocks in a thigh quiver:
# "You don't have the proper ammunition readily available for your hide
# sling." (nothing that loads), "You can not load the hide sling with a
# rock!" (a foraged rock is not ammunition); the last two are
# combat-trainer's.
NO_AMMO = (
    "proper ammunition",
    "can not load",
    "what weapon are you trying to load",
    "in your right hand to load",
)
# "You begin to target a ship's rat." (captured); the others combat-trainer's.
AIMED = ("you begin to target", "you are already", "you shift your target")
BEST_SHOT = "best shot possible"  # "You think you have your best shot possible now."
# "Moving with indomitable grace, you fire a small rock at a ship's rat."
_FIRED = re.compile(r"\byou (?:fire|poach|snipe) (?:an?|some|the|your) (.+?) at ", re.I)
AT_FEET = "lands at your feet"  # "The <ammunition> lands at your feet!" (the wiki's)
PICKED = "you pick up"  # "You pick up a small rock." then "You put your rock in your thigh quiver."


def is_ranged(skill):
    """True for a skill whose weapon is fired: Slings, Bow, Crossbow."""
    return skill in SKILLS


def out_of_ammo(answer):
    """True when LOAD found nothing it could load."""
    lowered = str(answer or "").lower()
    return any(needle in lowered for needle in NO_AMMO)


def ammo_of(answer):
    """The ammunition FIRE named, as STOW reads it: the first and last
    word ("small rock"; "matte indurium sphere" is "matte sphere",
    combat-trainer's rule); "" when no shot went."""
    match = _FIRED.search(str(answer or ""))
    if not match:
        return ""
    words = match.group(1).split()
    return " ".join(dict.fromkeys([words[0], words[-1]]))


def shoot(s, prey, ask):
    """One shot at `prey` (the faced target when ""): FIRE's answer, or
    LOAD's or AIM's when no shot went — no ammunition, the prey dead or
    gone, which the hunt reads as it reads a swing's. A shot at the
    feet is stowed again."""
    loaded = ask(s, "load")
    if out_of_ammo(loaded):
        return loaded
    aimed = ask(s, f"aim {prey}" if prey else "aim")
    if not any(needle in aimed.lower() for needle in AIMED):
        return aimed
    if BEST_SHOT not in aimed.lower():
        probe.collect(s, AIM_SECONDS, until=BEST_SHOT)
    fired = ask(s, "fire")
    ammo = ammo_of(fired)
    for _ in range(fired.lower().count(AT_FEET) if ammo else 0):
        ask(s, f"stow my {ammo}")
    return fired


def pick_up(s, ammo, ask, most=PICKUP_MOST):
    """STOW `ammo` from the room again and again, as many as lie there:
    (the count picked up, the answer that ended it) — "Stow what?" when
    none is left, "You need a free hand to pick that up." when no hand
    is free."""
    picked = 0
    answer = ""
    for _ in range(most):
        answer = ask(s, f"stow {ammo}")
        if PICKED not in answer.lower():
            break
        picked += 1
    return picked, answer
