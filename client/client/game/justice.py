"""Warrants — whether the town's guards have a reason to stop the
character, read off RECALL WARRANT (Elanthipedia: Justice).

A wanted character is captured by the guards in time as they pass,
and SURRENDER clears the charges; RECALL WARRANT is how a character
finds out first, and it costs nothing. Captured 2026-09-22 on a Thief
with a clean sheet: "Taking a moment to think, you are certain you do
not have any outstanding warrants." The wanted wording is uncaptured:
an answer that names a warrant without the clean phrase reads as
wanted, anything else as unknown (said, never assumed clean). Scripts
that walk a character into a town — `;go2`, `;train`'s safe-room rest
— can ask before the gate; `;warrant` prints the answer.
"""

COMMAND = "recall warrant"
CLEAN = ("do not have any outstanding warrants",)
WANTED = ("warrant",)  # an answer naming one without the clean phrase


def parse_warrants(text):
    """False when the answer says the sheet is clean, True when it
    names a warrant, None when it says neither (the command unanswered,
    or a wording not yet captured)."""
    lowered = (text or "").lower()
    if any(word in lowered for word in CLEAN):
        return False
    if any(word in lowered for word in WANTED):
        return True
    return None


def describe(wanted):
    """One line for the window."""
    if wanted is False:
        return "no outstanding warrants"
    if wanted is True:
        return "WANTED — the guards will take you as you pass; SURRENDER clears it"
    return "the game did not say — RECALL WARRANT answered nothing known"
