"""Earn a favor — the orb run, grotto to temple altar:  ;favors [immortal]

Run it from anywhere in walking range of Crossing: the script walks to
the Stone Grotto west of town, prays a favor orb loose in the name of
a neutral Immortal (default Truffenyi; e.g. ;favors Meraud), takes the
easy exit (GO ARCH), waits while you solve the favor puzzles by hand,
then walks to the temple's Resurrection Creche, rubs the orb full of
unabsorbed experience, and lays it on the altar. Favors are what stand
between dying and a zero-favor DEPART. The orb's sacrifice is your
experience pool: with nothing learning the script refuses and tells
you to train first.

The puzzles past the arch are yours (typical tasks per Elanthipedia:
GET SPONGE / CLEAN ALTAR WITH SPONGE, or GET TINDER / LIGHT CANDLE,
then GO STAIR and GO DOOR); the script notices when you are back on
the map and resumes on its own — ;favors done forces it, ;favors abort
stops the run, and DROP MY ORB abandons the puzzles entirely (the game
destroys the orb and teleports you out). Carry at most one other orb:
beyond two, fed experience is wasted (docs/favors.md).

Wordings beyond the Elanthipedia-quoted ones are assumptions until an
attended run captures them (#82) — anything unclassified is echoed as
"favors: unrecognized ...": report those lines and they become
fixtures. Stop with:  ;stop favors
"""

import time

from client.walker import locate

GROTTO = 1420  # [Siergelde, Stone Grotto] — Zoluren's general favor altar
CRECHE = 5865  # [Resurrection Creche, Li Stil rae Kwego ia Kweld]

DEFAULT_IMMORTAL = "Truffenyi"  # patron of the common folk
# The Thirteen's neutral aspects (Elanthipedia "Immortals", aspect table
# verified 2026-08-22). Only these are named at a general altar.
NEUTRAL_IMMORTALS = (
    "Chadatru",
    "Damaris",
    "Eluned",
    "Everild",
    "Faenella",
    "Glythtide",
    "Hav'roth",
    "Hodierna",
    "Kertigen",
    "Meraud",
    "Tamsine",
    "Truffenyi",
    "Urrem'tier",
)

PAUSE = 1  # breather between ritual commands
COLLECT_SECONDS = 3  # let a command's answer arrive in one burst
RESULT_SECONDS = 2  # the tail that lands once the roundtime expires
OFFER_SECONDS = 6  # the altar's light show is long and multi-line
ARRIVAL_TIMEOUT = 10  # room change after GO ARCH
PUZZLE_POLL = 5  # seconds between are-we-back checks while puzzling
MAX_RUBS = 100  # the orb fills well before this; a fuse, not a plan
RUB_REPORT_EVERY = 10

# Keyword classification of the game's answers (assumptions until an
# attended run captures them — #82). Checked in order; first hit wins.
# "properly prepared" and the offer's light show are quoted on
# Elanthipedia (docs/favors.md); the rest are guesses.
ORB_OUTCOMES = (
    ("nothing_there", ("what were you referring",)),
    ("hands_full", ("free hand", "hands are full")),
    ("ok", ("orb",)),
)
RUB_OUTCOMES = (
    ("full", ("properly prepared",)),
    ("no_orb", ("what were you referring",)),
    ("progress", ("glow", "waver", "pale", "steady", "strong", "pulse", "swirl")),
)
OFFER_OUTCOMES = (
    ("granted", ("multicolored lights gather", "feel somehow changed")),
    ("refused", ("not full", "not ready", "not yet", "nothing happens")),
    ("no_orb", ("what were you referring",)),
)


def classify(text, outcomes):
    lowered = text.lower()
    for outcome, needles in outcomes:
        if any(needle in lowered for needle in needles):
            return outcome
    return None


def collect(s, seconds):
    pieces = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = s.get(timeout=0.5)
        if line is not None:
            pieces.append(line)
    return "\n".join(pieces)


def ask(s, command, seconds=None):
    s.put(command)
    opening = collect(s, COLLECT_SECONDS if seconds is None else seconds)
    # Results can land at the roundtime's end (the ;mechlore blind-forage
    # capture, 2026-08-22); the roundtime is only announced after the
    # command goes out, so waitrt comes after the first collect.
    s.waitrt()
    tail = collect(s, RESULT_SECONDS)
    return f"{opening}\n{tail}" if tail else opening


def echo_unrecognized(s, step, answer):
    for line in answer.splitlines():
        if line.strip():
            s.echo(f"favors: unrecognized ({step}): {line.strip()}")
            break


def resolve_immortal(args):
    """The neutral-aspect name to pray by, or None when the argument is
    not one of the Thirteen (case- and apostrophe-lenient)."""
    if not args:
        return DEFAULT_IMMORTAL
    wanted = _letters(args[0])
    for name in NEUTRAL_IMMORTALS:
        if _letters(name) == wanted:
            return name
    return None


def _letters(name):
    return "".join(ch for ch in name.lower() if ch.isalpha())


def is_dead(state):
    indicators = getattr(state, "indicator", None) or {}
    return indicators.get("IconDEAD") == "y"


def pool_active(state):
    """True while the exp window shows anything learning — the pool the
    orb's sacrifice drains."""
    experience = getattr(state, "experience", None) or {}
    return any(entry["mindstate"] > 0 for entry in experience.values())


def ritual(s, immortal):
    """Kneel, pray thrice, name the Immortal, stand, take the orb.
    Returns the get-orb outcome ("ok" means an orb is in hand)."""
    for command in ("kneel", "pray", "pray", "pray", f"say {immortal}", "stand"):
        ask(s, command)
        s.sleep(PAUSE)
    answer = ask(s, "get orb on altar")
    outcome = classify(answer, ORB_OUTCOMES)
    if outcome is None:
        echo_unrecognized(s, "get orb", answer)
    return outcome


def enter_puzzles(s):
    """GO ARCH (the easy path); True when the room actually changed."""
    s.waitrt()
    before = (getattr(s.state, "room_uid", None), getattr(s.state, "room_title", None))
    # Discard stale compass frames so the next one pairs with this move
    # (the walker's double-frame rule, docs/movement.md).
    while s.get(timeout=0, streams=("compass",)) is not None:
        pass
    s.put("go arch")
    if s.get(timeout=ARRIVAL_TIMEOUT, streams=("compass",)) is not None:
        return True
    now = (getattr(s.state, "room_uid", None), getattr(s.state, "room_title", None))
    return now != before


def wait_out_puzzles(s, db):
    """Hold while the human solves the favor puzzles. True to resume the
    run (back on the map, or ;favors done), False on ;favors abort."""
    while s.command(timeout=0) is not None:
        pass  # stale ;favors lines from earlier must not fake a done
    s.echo("favors: puzzle rooms — solve each task by hand (;help favors has spoilers)")
    s.echo(
        "favors: I resume when you're back on the map — "
        ";favors done forces it, ;favors abort stops"
    )
    while True:
        line = s.command(timeout=PUZZLE_POLL)
        if line is not None:
            word = line.strip().lower()
            if word == "done":
                return True
            if word == "abort":
                return False
            s.echo(
                "favors: mid-puzzle I only understand ;favors done and ;favors abort"
            )
            continue
        here = locate(db, s.state)
        if here is not None and db.path(here, {CRECHE}) is not None:
            s.echo("favors: back on the map — resuming the run")
            return True


def fill(s):
    """Rub the orb full at the altar: "full", "drained", or "stopped".

    The rub comes before the pool check so a full orb is recognized
    even with an empty pool, and so an empty-pool rub captures the
    game's refusal wording (#82) before we stop."""
    for rubs in range(1, MAX_RUBS + 1):
        answer = ask(s, "rub my orb")
        outcome = classify(answer, RUB_OUTCOMES)
        if outcome == "full":
            s.echo(f"favors: the orb is full after {rubs} rub(s)")
            return "full"
        if outcome == "no_orb":
            s.echo("favors: no orb in hand to rub — stopping")
            return "stopped"
        if outcome is None:
            echo_unrecognized(s, "rub", answer)
        if not pool_active(s.state):
            return "drained"
        if rubs % RUB_REPORT_EVERY == 0:
            s.echo(f"favors: {rubs} rubs — still filling")
        s.sleep(PAUSE)
    s.echo(
        f"favors: {MAX_RUBS} rubs without a full orb — stopping (report the wordings above)"
    )
    return "stopped"


def offer(s):
    """Lay the filled orb on the altar; True when the favor took."""
    answer = ask(s, "put my orb on altar", seconds=OFFER_SECONDS)
    outcome = classify(answer, OFFER_OUTCOMES)
    if outcome == "granted":
        return True
    if outcome is None:
        echo_unrecognized(s, "offer", answer)
    else:
        s.echo(f"favors: the altar refused the orb ({outcome})")
    return False


def report_favor_count(s):
    """FAVOR is the ground truth on whether the offer took — echo it."""
    answer = ask(s, "favor")
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    if not lines:
        s.echo("favors: FAVOR gave no answer — check by hand")
        return
    for line in lines[:3]:
        s.echo(f"favors: {line}")


def main(s, db=None, walk=None):
    immortal = resolve_immortal(s.args)
    if immortal is None:
        s.echo(f"favors: {s.args[0]!r} is not a neutral aspect of the Thirteen")
        s.echo("favors: pick one of " + ", ".join(NEUTRAL_IMMORTALS))
        return
    if is_dead(s.state):
        s.echo("favors: you are dead — this run needs a living body")
        return
    if not pool_active(s.state):
        s.echo(
            "favors: nothing is learning — the orb's sacrifice is your "
            "experience pool; train something first"
        )
        return
    if db is None or walk is None:
        from client.mapdb import MapDB, download, mapdb_path
        from client.walker import walk as real_walk

        if not mapdb_path().is_file():
            s.echo("downloading map database (first use, ~13MB) ...")
            download()
        db = db or MapDB.load()
        walk = walk or real_walk
    if not walk(s, db, [GROTTO], describe="the Stone Grotto"):
        s.echo("favors: could not reach the grotto — stopping")
        return
    s.echo(f"favors: praying to {immortal} for an orb")
    outcome = ritual(s, immortal)
    if outcome == "hands_full":
        s.echo(
            "favors: no free hand for the orb — stow something, then by hand: "
            "GET ORB ON ALTAR, GO ARCH, solve the puzzles, and at the creche "
            "RUB MY ORB until 'properly prepared', PUT MY ORB ON ALTAR"
        )
        return
    if outcome == "nothing_there":
        s.echo(
            "favors: no orb appeared on the altar — the lines above are the capture (#82)"
        )
        return
    if not enter_puzzles(s):
        s.echo(
            "favors: GO ARCH went nowhere — capture the lines above and take it from here by hand (#82)"
        )
        return
    if not wait_out_puzzles(s, db):
        s.echo(
            "favors: aborted — DROP MY ORB abandons the puzzles "
            "(destroys the orb, teleports you out)"
        )
        return
    if not walk(s, db, [CRECHE], describe="the temple creche"):
        s.echo(
            "favors: could not reach the creche — walk there (;go2 5865), "
            "RUB MY ORB until 'properly prepared', then PUT MY ORB ON ALTAR"
        )
        return
    result = fill(s)
    if result == "drained":
        s.echo(
            "favors: experience pool drained before the orb filled — train "
            "something, RUB MY ORB until 'properly prepared', then PUT MY ORB "
            "ON ALTAR (keep the orb on you: stored orbs shatter)"
        )
        return
    if result == "stopped":
        return
    if offer(s):
        s.echo("favors: the Immortals accepted — favor earned")
    report_favor_count(s)
