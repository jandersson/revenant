"""A compendium of anatomy charts, studied for First Aid (;compendium):
the charts it holds, the order to study them in, and the game's answers.

LOOK MY COMPENDIUM lists the charts ("... the compendium contains the
following charts:", then one per line); TURN MY COMPENDIUM TO <index>
opens a chart's page, the index being anatomy_data's word for it
("Glutinous" for the Glutinous Lipopod); STUDY MY COMPENDIUM studies the
open page, several studies "gradually absorbing" until "a sudden moment
of clarity", after which that chart is locked for twenty minutes ("Why
do you need to study this chart again?"). Captured on Cecil, 2026-10-04,
Scholarship 77: the Blood Nyad took nine studies at 14 s, the Glutinous
Lipopod seven, the Silver Leucro one at 10 s. First Aid is paid at the
first study and at clarity, Scholarship on every study (Elanthipedia:
Anatomy charts); a chart past the reader's Scholarship is "almost
impossible" (dr-scripts' first-aid.lic, not captured here).

The order is dr-scripts' first-aid's: the hardest chart the Scholarship
reads first, from its table (anatomy_data.CHARTS), where the reach is
the rank itself up to 100 and the rank over 1.6 past it.
"""

from client.game.anatomy_data import CHARTS

LOCK_SECONDS = 20 * 60  # a chart at clarity rests this long

# TURN MY COMPENDIUM TO <index>, captured 2026-10-04: "You turn to the
# section on Glutinous Lipopod physiology.", "That section does not
# exist within your compendium.", "You need to be holding your
# compendium to do that."
TURN_OUTCOMES = (
    ("turned", ("you turn to the section",)),
    ("missing", ("does not exist within your",)),
    ("unheld", ("need to be holding",)),
    ("too hard", ("almost impossible",)),
)
# STUDY MY COMPENDIUM, captured 2026-10-04: "You begin studying the
# Blood Nyad chart, gradually absorbing the knowledge contained
# within.", "You continue studying ... gradually absorbing more of the
# knowledge ...", "In a sudden moment of clarity, the information on the
# chart suddenly makes sense to you." (on a first study: "With a sudden
# moment of clarity, ..."), "Why do you need to study this chart
# again?", "You need to be holding your compendium to study it." A
# chart near the top of the reach is slow, not refused: "You begin to
# study the Boggle chart, having a difficult time comprehending the
# advanced text." (18 s), mixed with "gradually absorbing" ones, and
# the Boggle reached clarity at the 39th study, Scholarship 15/34 ->
# 25/34 on the way. The too-hard and done wordings are dr-scripts'
# first-aid.lic's.
STUDY_OUTCOMES = (
    ("clarity", ("suddenly makes sense to you",)),
    ("locked", ("why do you need to study",)),
    ("unheld", ("need to be holding",)),
    ("too hard", ("almost impossible",)),
    ("done", ("discerned all you can",)),
    ("studying", ("gradually absorbing", "difficult time comprehending")),
)
# GET MY COMPENDIUM: "You get a grey leather compendium ... from inside
# your backpack." (2026-10-04).
GOT = ("you get", "you pick up", "already holding")
_LISTED = "contains the following charts:"

# The charts at clarity this session, {name: the clock's time then}:
# the lock is the game's, kept here to skip a STUDY that only asks why.
_LOCKED = {}


def charts(answer):
    """The chart names LOOK MY COMPENDIUM lists, in its order; [] when
    the answer lists none."""
    text = str(answer or "")
    at = text.find(_LISTED)
    if at < 0:
        return []
    names = []
    for line in text[at + len(_LISTED) :].splitlines():
        if not line.strip():
            continue
        if not line[:1].isspace() and names:
            break  # the next game line
        names.append(line.strip())
    return names


def reach(scholarship):
    """The hardest chart (its table Scholarship) a reader of that rank
    studies: the rank up to 100, the rank over 1.6 past it; None when
    the rank is unknown."""
    if scholarship is None:
        return None
    return scholarship if scholarship <= 100 else scholarship / 1.6


def plan(names, scholarship):
    """The charts to study, hardest first: the table's within reach (in
    the listing's order among equals), then any the table does not know;
    a known chart past reach is left out."""
    limit = reach(scholarship)
    known = [
        name
        for name in names
        if name in CHARTS and (limit is None or CHARTS[name][1] <= limit)
    ]
    known.sort(key=lambda name: -CHARTS[name][1])
    return known + [name for name in names if name not in CHARTS]


def index(name):
    """The word TURN finds the chart's page by, lowered."""
    return CHARTS.get(name, (name, 0))[0].lower()


def lock(name, now):
    _LOCKED[name] = now


def locked(name, now):
    at = _LOCKED.get(name)
    return at is not None and now - at < LOCK_SECONDS


def next_unlock(names, now):
    """(seconds until the soonest of `names` opens again, its name), or
    None when one is open now or none was ever locked."""
    waits = [
        (LOCK_SECONDS - (now - _LOCKED[name]), name)
        for name in names
        if locked(name, now)
    ]
    if not waits or len(waits) < len(names):
        return None
    return min(waits)
