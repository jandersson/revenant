"""The sanowret crystal's lesson (#500): the wordings ;gaze reads and the
concentration rule it waits on.

A sanowret crystal teaches Arcana to any guild: GAZE gives a lecture of
about half a minute, each pulse a pulse of Arcana experience scaled by
rank; EXHALE teaches about half as much, at once. Either takes about
half the concentration and has no cooldown beyond the refill, so a
trainer gazes at full concentration and waits between (Elanthipedia:
Sanowret crystal, Template:VERBSSanowret). Never DROP it — it damages;
LOWER instead.
"""

CRYSTAL = "sanowret crystal"
SKILL = "Arcana"
FULL = 100  # % concentration a gaze waits for: each one takes about half
LECTURE_SECONDS = 45  # the half-minute lecture, with room
# The verb template's wordings, until captured.
GAZED = ("you gaze intently",)
EXHALED = ("you exhale softly",)
LECTURE_END = ("quite enlightened",)
# The refusal for too little concentration is uncaptured: the first one
# the run meets is reported, and after three such the run ends.


def ready(vitals, full=FULL):
    """True when the vitals show concentration at `full` or more, or show
    no concentration at all (a state without the bar never waits)."""
    if not isinstance(vitals, dict):
        return True
    value = vitals.get("concentration")
    return value is None or value >= full


def command(exhale=False, crystal=CRYSTAL):
    return f"{'exhale on' if exhale else 'gaze'} my {crystal}"


def said(text, needles):
    lowered = str(text or "").lower()
    return any(needle in lowered for needle in needles)
