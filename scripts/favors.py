"""Earn a favor — the orb run, grotto to temple altar:  ;favors [immortal]
Run it from anywhere in walking range of Crossing: the script first
checks for an orb already in your possession — one in a hand, or one
GET MY ORB fetches from a container — and finishes that one (the
puzzles if you are still in them, then the creche) rather than pray
for another; otherwise it walks to
the Stone Grotto west of town, prays a favor orb loose in the name of
a neutral Immortal (default Truffenyi; e.g. ;favors Meraud), takes the
easy exit (GO ARCH), solves the puzzle rooms it knows — the choking
plant (OPEN WINDOW until it slides open, GO WINDOW), the empty vase
(GET NUTFLOWER fills it, GO PATH), the empty font (GET JUG, POUR JUG
IN FONT), the dirty altar (GET SPONGE, CLEAN ALTAR WITH SPONGE), the
unlit candles (GET TINDER, LIGHT CANDLE), the last three followed by
GO STAIR and GO DOOR; a puzzle that needs a hand
gets one, the item that is not the orb stowed — and hands a
room it does not recognise to you, then walks to the temple's
Resurrection Creche, rubs the orb full of
unabsorbed experience, and lays it on the altar. Favors are what stand
between dying and a zero-favor DEPART. The orb's sacrifice is your
experience pool: with nothing learning the script refuses and tells
you to train first.

A puzzle room the script does not know (levers, say) it describes
and leaves to you; it notices when you are back on the map and
resumes on its own — ;favors done forces it, ;favors abort stops the
run, and DROP MY ORB abandons the puzzles entirely (the game destroys
the orb and teleports you out). The choking plant's, the vase's and
the font's rooms were captured on 2026-09-13 (the window takes three
OPENs, the flowers arrange themselves on GET, the jug empties into
the font and the stair opens the door, and every exit teleports you
back to the grotto); the sponge and tinder rooms are Elanthipedia's
spoilers, uncaptured. Carry at most one other orb:
beyond two, fed experience is wasted (docs/favors.md).

Wordings beyond the Elanthipedia-quoted ones are assumptions until an
attended run captures them (#82) — anything unclassified is echoed as
"favors: unrecognized ...": report those lines and they become
fixtures. Stop with:  ;stop favors
"""

from client.game import probe
from client.game.probe import classify
from client.game.walker import locate

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
# The Labyrinth's puzzle rooms past the arch, each one task; the last
# exit teleports you back to the grotto ("You feel giddy all over and
# you grin widely as everything about you disappears and you suddenly
# find yourself transported to...", captured 2026-09-13). The cue
# words in the room's LOOK pick the puzzle; a room no cue fits is left
# to the human. Steps repeat until their done-words show.
PUZZLES = (
    {
        # "[Siergelde, Labyrinth] ... a plant upon the table looks as
        # though it is slowly choking to death in the heat." OPEN WINDOW
        # three times (captured): "you shimmy the frame ... a thin
        # crack", "loosen it even further", "hoist it upward ... slides
        # open"; once more says "That is already open." GO WINDOW: "You
        # hoist yourself off the floor and manage to swing yourself
        # through the open window." then the teleport to the grotto.
        "name": "the choking plant",
        "cues": ("choking", "window"),
        "steps": (("open window", ("slides open", "already open")),),
        "exit": ("go window",),
    },
    {
        # "A peaceful grotto ... swathed in hedges of oleander and
        # nutflower ... a simple white altar hewn of shimmering marble
        # ... You also see a vase on top of the altar." (captured
        # 2026-09-13, the second favor). GET NUTFLOWER does the whole
        # task: "You carefully pick some of the nutflower blossoms and
        # arrange them neatly in the vase."; again: "You have already
        # filled the vase to overflowing." GO PATH: "Having filled the
        # vase with flowers, you stride along the branching path toward
        # the copse of juniper trees." then the teleport. With the orb
        # and a weapon in hand: "You must clear one of your hands first."
        "name": "the empty vase",
        "cues": ("vase", "nutflower"),
        "steps": (("get nutflower", ("arrange", "already filled")),),
        "exit": ("go path",),
    },
    {
        # "Two fiery braziers stand astride a steep stone stairway which
        # leads to a massive iron door ... a granite altar with several
        # candles and a water jug on it, and a granite font." (captured
        # 2026-09-13, the third favor). The font "is empty. Something in
        # the back of your mind tells you this doesn't seem right."
        # GET JUG: "You reverently take the jug from the altar."; POUR
        # JUG IN FONT: "You carefully carry the earthen jug to the font
        # and pour the water out. The soft scent of lilac rises from the
        # filled basin ..." (the jug is gone after). GO STAIR: "You reach
        # the top of the stairway, and notice that the door has swung
        # open of its own accord!"; GO DOOR: "You step gleefully through
        # the door ..." then the teleport.
        "name": "the empty font",
        "cues": ("jug", "font"),
        "steps": (
            ("get jug", ("take the jug",)),
            ("pour jug in font", ("pour the water out",)),
        ),
        "exit": ("go stair", "go door"),
    },
    {
        # Elanthipedia (Favors/Puzzles): "granite altar with several
        # candles on it, a granite font and a small sponge".
        "name": "the dirty altar",
        "cues": ("sponge",),
        "steps": (("get sponge", ()), ("clean altar with sponge", ())),
        "exit": ("go stair", "go door"),
    },
    {
        # Elanthipedia: "some tinders, several candles, a granite font
        # and a granite altar".
        "name": "the unlit candles",
        "cues": ("tinder",),
        "steps": (("get tinder", ()), ("light candle", ())),
        "exit": ("go stair", "go door"),
    },
)
STEP_TRIES = 6  # repeats of a step waiting for its done-words
MAX_PUZZLES = 12  # rooms solved before the script hands over anyway
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


def ask(s, command, seconds=None):
    """The game's answer to a command, roundtime-delayed tail included
    (client.game.probe.ask, with this script's collection windows)."""
    return probe.ask(
        s, command, COLLECT_SECONDS if seconds is None else seconds, RESULT_SECONDS
    )


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


def held_orb(s):
    """The orb in a hand, from the parser's hand state, or None."""
    for side in ("left_hand", "right_hand"):
        held = getattr(s.state, side, None)
        if isinstance(held, dict) and "orb" in str(held.get("noun") or ""):
            return held
    return None


def fetch_orb(s):
    """GET MY ORB: True when a container gave one up (the operator's
    ask, 2026-09-13 — a run that already has an orb must not pray for
    another; beyond two, fed experience is wasted). With both hands
    full there is nothing to fetch into, so False without a send."""
    hands = [getattr(s.state, side, None) for side in ("left_hand", "right_hand")]
    if all(hands):
        return False
    answer = ask(s, "get my orb")
    return classify(answer, ORB_OUTCOMES) == "ok"


def on_the_map(s, db):
    """Back from the puzzles: a mapped room with a path to the creche."""
    here = locate(db, s.state)
    return here is not None and db.path(here, {CRECHE}) is not None


def free_hand(s):
    """A puzzle that picks something up needs a hand, and the orb has
    one: with both full, STOW the item that is not the orb (captured
    2026-09-13: "You must clear one of your hands first.")."""
    hands = [getattr(s.state, side, None) for side in ("left_hand", "right_hand")]
    if not all(hands):
        return
    other = next((h for h in hands if "orb" not in str(h.get("noun") or "")), None)
    if other and other.get("noun"):
        ask(s, f"stow my {other['noun']}")
        s.waitrt()


def match_puzzle(description):
    """The PUZZLES entry whose every cue word the room's LOOK holds."""
    text = description.lower()
    for puzzle in PUZZLES:
        if all(cue in text for cue in puzzle["cues"]):
            return puzzle
    return None


def typed_word(s):
    """A ;favors word typed since the last look: "done", "abort" or None."""
    word = None
    while (line := s.command(timeout=0)) is not None:
        candidate = line.strip().lower()
        if candidate in ("done", "abort"):
            word = candidate
        else:
            s.echo(
                "favors: mid-puzzle I only understand ;favors done and ;favors abort"
            )
    return word


def solve_puzzles(s, db):
    """Solve the Labyrinth's rooms the script knows (PUZZLES), room by
    room, until the character is back on the map; a room it does not
    know goes to the human (wait_out_puzzles). True to resume the run,
    False on ;favors abort."""
    while s.command(timeout=0) is not None:
        pass  # stale ;favors lines from earlier must not fake a done
    for _ in range(MAX_PUZZLES):
        if on_the_map(s, db):
            s.echo("favors: back on the map — resuming the run")
            return True
        word = typed_word(s)
        if word == "abort":
            return False
        if word == "done":
            return True
        room = ask(s, "look")
        puzzle = match_puzzle(room)
        if puzzle is None:
            first = next((line for line in room.splitlines() if line.strip()), "")
            s.echo(f"favors: a puzzle room I do not know — {first.strip()[:90]}")
            return wait_out_puzzles(s, db)
        steps = ", ".join(command for command, _ in puzzle["steps"])
        s.echo(f"favors: {puzzle['name']} — {steps}, then {', '.join(puzzle['exit'])}")
        free_hand(s)
        for command, done in puzzle["steps"]:
            for _ in range(STEP_TRIES):
                answer = ask(s, command).lower()
                s.waitrt()
                if not done or any(sign in answer for sign in done):
                    break
        for command in puzzle["exit"]:
            ask(s, command)
            s.waitrt()
            s.sleep(PAUSE)
    s.echo(f"favors: still in the puzzles after {MAX_PUZZLES} rooms — over to you")
    return wait_out_puzzles(s, db)


def wait_out_puzzles(s, db):
    """Hold while the human solves a puzzle room. True to resume the
    run (back on the map, or ;favors done), False on ;favors abort."""
    s.echo("favors: solve this room by hand (;help favors has the known ones)")
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
        if on_the_map(s, db):
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
    if db is None or walk is None:
        from client.game.mapdb import MapDB, download, mapdb_path
        from client.game.walker import walk as real_walk

        if not mapdb_path().is_file():
            s.echo("downloading map database (first use, ~13MB) ...")
            download()
        db = db or MapDB.load()
        walk = walk or real_walk
    # An orb already yours comes first: in a hand (the parser knows,
    # nothing sent), or — once the pool is worth a run — in a container.
    if held_orb(s) is None and not pool_active(s.state):
        s.echo(
            "favors: nothing is learning — the orb's sacrifice is your "
            "experience pool; train something first"
        )
        return
    if held_orb(s) or fetch_orb(s):
        s.echo(
            "favors: an orb is already in your possession — finishing it, no new prayer"
        )
        if not on_the_map(s, db) and not solve_puzzles(s, db):
            s.echo(
                "favors: aborted — DROP MY ORB abandons the puzzles "
                "(destroys the orb, teleports you out)"
            )
            return
        finish(s, db, walk)
        return
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
    if not solve_puzzles(s, db):
        s.echo(
            "favors: aborted — DROP MY ORB abandons the puzzles "
            "(destroys the orb, teleports you out)"
        )
        return
    finish(s, db, walk)


def finish(s, db, walk):
    """The orb in hand and the character on the map: to the creche,
    fill, offer, report."""
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
