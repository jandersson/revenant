"""Shared room location and walking for scripts (;go2, ;athletics, ...).

locate() turns parsed game state into a community-map room id; walk()
drives the character along a BFS route from the map database, verifying
arrival room by room. Extracted from ;go2 (this is ;go2's engine) so
any script can travel. A climb the game turns back for footing (#157)
gets one retry standing with the hindering items stowed, then stops
with what would help; an engagement gets the retreat burst, unless
the room's only exit is "out" — a bank or shop, where nothing engages
and a retreat has nowhere to go (#171) (docs/movement.md); a move sent
into roundtime ("...wait 7 seconds.") waits it out and goes again, and
a hidden way's SEARCH is repeated until it finds something (#367). A
ferry edge
(the map's bescort 'faldesu' crossing, #205) is ridden: GO FERRY when
the ferry is at the dock, the wait for it when not, the crossing, then
GO DOCK as the step's move — after dr-scripts' bescort take_rh_ferry,
the wordings captured on the first ride (2026-09-18): the fare is 30
lirums, put on the Therengian debt when there are none on you. A
captain who turns you away for the fare has ;bank keep=200 fetch it,
with lirums=200 when lirums are the coin named (#507), and the walk
planned again from the teller, once a walk (#455).
"""

import re
from time import monotonic

from client.client_logger import ClientLogger
from client.game import money
from client.game.mapdb import (
    normalize_title,
    ride_args,
    ride_of,
    split_move,
    translate_embedded,
    walkable,
)

module_logger = ClientLogger()

ARRIVAL_TIMEOUT = 15  # seconds for the compass frame after a move
# The moves whose off-course arrival is written to the local map (#364).
COMPASS_MOVES = frozenset(
    (
        "north",
        "south",
        "east",
        "west",
        "northeast",
        "northwest",
        "southeast",
        "southwest",
        "n",
        "s",
        "e",
        "w",
        "ne",
        "nw",
        "se",
        "sw",
    )
)

# The Faldesu ferry (#205), after bescort's take_rh_ferry, captured on
# the first ride (2026-09-18, North Road, Ferry → Riverhaven). GO FERRY
# with the ferry out: "[Assuming you mean the ferry His Daring
# Exploit.]" / "I could not find what you were referring to."; then
# "You can see the ferry "Her Opulence" approaching the dock." and "The
# ferry "Her Opulence" pulls up to the dock." GO FERRY with it in: "The
# Captain stops you and requests a transportation fee of 30 lirums as
# you board the craft." and the room is the ferry ([Her Opulence],
# "Obvious paths: none", a compass frame) — boarding is the room
# change, not a wording. With no lirums on you: "Hey," he says, "You
# haven't got enough lirums to pay for your trip.  Come back when you
# can afford the fare." / "The Captain frowns.  "But I see you're
# pretty young and don't have the sense to keep enough coins on ya fer
# emergencies, so I'll just add it to yer debt." / "[Your debt to the
# province of Therengia is being increased by 30 lirums.]" — and you
# are aboard all the same (the refusal that leaves you on the dock, for
# a character the captain does not call young, was captured at the
# Riverhaven dock on 2026-09-26 with 13 lirums on hand: "[Assuming you
# mean the ferry His Daring Exploit.]", the fee line, then the "Hey,"
# line above — and nothing more, the character still on the dock).
# Aboard: "Next departure in one minute!", "All ashore who's going
# ashore!", "Cast off!", "You feel the ferry shudder slightly as it
# shoves off.", the quarter-way lines, "You are nearing the docks.",
# then "The ferry "Her Opulence" reaches the dock and its crew ties the
# ferry off." GO DOCK lands on [Riverhaven, Ferry Dock].
FERRY_ANSWER_SECONDS = 4  # GO FERRY's answer: the room change, or the refusal
FERRY_WAIT_SECONDS = 900  # a ferry's round trip: the longest wait for one
FERRY_POLL_SECONDS = 60  # between GO FERRYs while the ferry is out
FERRY_AWAY = (
    "not here",
    "could not find what you were referring",
    "until the next one arrives",
    # Alfren's Ferry (bescort's take_xing_ferry; the first captured on
    # the first crossing, 2026-09-18, the second still bescort's)
    "no ferry here to go aboard",
    "just pulled away from the dock",
)
FERRY_NO_FARE = ("afford the fare",)
WEALTH_SECONDS = 2  # WEALTH's answer, read for the purse beside a refused fare
FERRY_FEE = re.compile(r"transportation fee of (\d+ \w+)")
# Alfren's, captured 2026-09-18: "The Captain stops you and requests a
# transportation fee of 35 kronars as you board the craft." / "You
# hand him your kronars and climb aboard." — the fee line is the
# Faldesu's shape, so FERRY_FEE reads it; the nod is bescort's.
FERRY_PAID = ("you hand him", "gives you a little nod")
FERRY_ON_DEBT = ("add it to yer debt", "debt to the province")
FERRY_ARRIVES = ("pulls into the dock", "pulls up to the dock")
FERRY_LANDS = ("ties the ferry off",)
# The Riverhaven–Throne City barges (#506): the Riverhawk and the
# Imperial Glory, bescort's haven_throne route, captured 2026-10-09/10 on
# both docks. A barge is boarded by its name's last word (GO RIVERHAWK,
# GO GLORY): the dock's object line reads "the barge Riverhawk and a
# brushy break in the undergrowth", so the name is the capitalized
# word or two after "the barge " and nothing past them (a reader that
# took the rest boarded the undergrowth). Approach: "You can see a
# barge nearing the dock.", when GO <name> answers "You can't do that
# right now.", then "A barge pulls into the dock." The fee line is the
# ferry's shape (120 Lirums); the landing "The barge pulls into dock and
# its crew quickly ties the barge off."; GO DOCK steps off. A barge
# stays a minute and crosses in six; the two alternate.
BARGE_ANSWER_SECONDS = 4
BARGE_WAIT_SECONDS = 900
BARGE_POLL_SECONDS = 30
BARGE_NOT_YET = ("can't do that right now",)
BARGE_ARRIVES = ("pulls into the dock",)
BARGE_LANDS = ("ties the barge off",)
_BARGE_NAME = re.compile(r"\bthe barge (?P<name>[A-Z][\w']*(?: [A-Z][\w']*)?)")
# The sea mammoths (#515), bescort's take_mammoth: Fang Cove's dock
# (8301) to Ratha's Shore Walk (11130) on the massive one, to
# Acenamacra's pier (2239) on the tall one, free, two minutes docked and
# about seven across (Elanthipedia: Sea Mammoths). JOIN SEA MAMMOTH (or
# TALL) with it in: 'You join the Merelew driver.  "Right this way,
# sir."' and the room is [Aboard the Mammoth, Platform] (captured
# 2026-10-10 at Fang Cove, the driver's call before it: "I'm leaving
# shortly, returning to Ratha."). With it out the answer is "What were
# you referring to?" and the dock's story brings the next one in;
# bescort's lines for that and for the landing, which sets the rider
# ashore on its own — LOOK is the step's move after it, for the compass
# frame the arrival check reads.
MAMMOTH_ANSWER_SECONDS = 4
MAMMOTH_WAIT_SECONDS = 1200  # a round trip and its two stops
MAMMOTH_POLL_SECONDS = 30
MAMMOTH_AWAY = ("What were you referring to",)
MAMMOTH_ARRIVES = (
    "waves along the waterline increase drastically",
    "watery trumpeting sound heralds",
)
MAMMOTH_LANDS = (
    "trumpets a series of watery blasts",
    "Here we are, ladies and gentlemen",
)
# The Obsidian Pass gondola (#211), after bescort's ride_gondola and
# captured on the first ride (2026-09-18): GO GONDOLA at a platform
# lands in the cab ([Gondola, Cab North], a room: a compass frame) or
# answers "There is no wooden gondola here.  You'll have to wait for
# it to come back around." — the platform's story then reads "The
# gondola arrives at the center of the chasm, and keeps heading
# north.", "The gondola swings closer to the platform." and "The
# gondola stops on the platform and the door silently swings open.";
# aboard, the direction is sent as bescort does ("You go south." into
# [Gondola, Cab South]), "The door swings shut of its own accord, and
# the gondola pushes off.", the crossing's lines, and "With a soft
# bump, the gondola comes to a stop at its destination.", then OUT
# ("You go out." onto [Obsidian Pass, Platform]). The wiki: three
# minutes across, two at each platform, LOOK GONDOLA for its progress.
GONDOLA_ANSWER_SECONDS = 4
GONDOLA_WAIT_SECONDS = 600  # a stop and a crossing
GONDOLA_ATTEMPTS = 3
GONDOLA_AWAY = ("no wooden gondola here",)
GONDOLA_DOOR = ("door silently swings open",)
GONDOLA_STOPS = ("soft bump",)

# The felled tree, captured 2026-09-11 (#157): a climb beyond the
# character's Athletics — worse armed and armored — is turned back
# with these two lines and no room change. The first names what
# hinders; "Your oak-hafted handaxe and plate vambraces make the climb
# more difficult." The second is the refusal.
# Going up: "...your footing is questionable. Reluctantly, you climb
# back down." Going down (captured 2026-09-12 on the Arthe Dale oak):
# "You attempt to climb down the tree, but you can't seem to find
# purchase." and "You start down the tree, but you find it hard going.
# Rather than risking a fall, you make your way back up." — unknown,
# they read as a stall and drew the retreat burst in a tree house.
# A third descent wording came on the next walk: "Trying to judge the
# climb, you peer over the edge.  A wave of dizziness hits you, and you
# back away from the tree."
CLIMB_REFUSALS = (
    "footing is questionable",
    "climb back down",
    "find purchase",
    "make your way back up",
    "back away from the",  # "...from the tree" / "...from the branch" (Obsidian Pass, 2026-09-18)
)
# A climb (or a stow) attempted sitting — what a turned-back climb
# leaves you — answers with these (captured on the retry, 2026-09-11);
# the same retry, which STANDs first, is the remedy.
POSTURE_REFUSALS = ("You must be standing", "You must stand first")
# A plain move sent kneeling — a prayer leaves you so — answers "You
# can't do that while kneeling!" (captured 2026-09-19 in the Tower of
# Honor's chapel, #220); the sitting and lying wordings are assumed.
# STAND and one retry, not the engaged-stall burst.
KNEELING_REFUSALS = ("while kneeling", "while sitting", "while lying down")
# STAND's answers, captured: "You stand back up.", "You are already
# standing.", and two refusals — "You are overburdened and cannot
# manage to stand." (Roundtime 9-10 s; #411, a box run that sat on
# overburdened) and "You are so unbalanced you cannot manage to
# stand." Balance comes back in seconds; a load does not.
STAND_ANSWERS = ("You stand back up", "already standing", "cannot manage to stand")
STAND_REFUSED = ("cannot manage to stand",)
STAND_SECONDS = 2.0  # the answer window
BALANCE_WAIT = 3  # seconds before the one retry an unbalanced STAND gets
# An exit the map has and the game has not: the Riverbank Mudflats'
# "go panel" answered "I could not find what you were referring to."
# (2026-09-18) — a hidden way, or a map edge that is wrong. Closed for
# the walk like a gated way, and the route planned again.
WAY_REFUSALS = ("could not find what you were referring", "You can't go there")
# A way the game closes to the character — a circle or guild gate the
# map cannot know: the Paladins' Guild's back trail from the Northeast
# Customs answered a circle-2 Paladin "You're not experienced enough to
# go there." and left him where he stood (captured 2026-09-18, #209).
# Not a stall: no retreat, no retry — the edge is closed for the run
# and the route planned again without it. The same trail answers a guild
# it keeps out "Barbarians are not allowed to go there." (captured
# 2026-09-26, a circle-1 Barbarian walked toward the Paladins' Guild: a
# stall, a RETREAT burst, the trail again, "stalled at step 148").
GATE_REFUSALS = ("not experienced enough to go there", "not allowed to go there")
# A gate's refusal outlives its walk (#394): ;train's walks to Cecil's
# rest room tried the Promenade twice an evening, each answered "not
# experienced enough" (2026-09-29). The edges are planned around by
# every walk after the refusal until a relaunch forgets them — a circle
# gained mid-session included. They live on the session's parser state,
# not in this module: one edit to any reloadable module reloads them all
# as fresh copies, and the walk home tried the Promenade again after
# every code change (2026-10-04). A climb refused for Athletics and a
# way the map has wrong stay closed for their walk alone.


def gated(s):
    """The (room, dest) edges a gate has refused this character in the
    session: the set itself, for the walk to add to — kept on the
    session's parser state (`gated_edges`), which every script shares
    and no module reload replaces."""
    state = getattr(s, "state", None)
    if state is None:
        return set()
    edges = getattr(state, "gated_edges", None)
    if edges is None:
        edges = set()
        try:
            state.gated_edges = edges
        except AttributeError:
            pass  # a state that takes no new attribute: this walk alone
    return edges


# A move sent into roundtime — a hidden path's SEARCH still running —
# answers "...wait 7 seconds." and nothing moves (captured 2026-09-28 at
# the Foothills' Stony Incline, #367): the roundtime is slept out and
# the move sent again, never the stall's retreat burst.
ROUNDTIME_WAIT = re.compile(r"\.\.\.wait (\d+) seconds?")
ROUNDTIME_RETRIES = 3
# A hidden way's SEARCH finds it only now and then: the Stony Incline's
# path showed on the ninth ("You don't find anything of interest here."
# eight times, then "There seems to be some sort of path leading to the
# east.", 2026-09-28, #367), so the SEARCH is repeated until the answer
# is not the empty one.
SEARCH_EMPTY = ("don't find anything of interest",)
SEARCH_FOUND = ("seems to be",)
SEARCH_TRIES = 15
SEARCH_ANSWER_SECONDS = 4
REROUTES = 3  # closed ways worked around on one walk before giving up
_HINDERS = re.compile(r"Your (.+?) makes? the climb more difficult")


def hindering_nouns(text):
    """The nouns of the items a "make the climb more difficult" line
    names — "oak-hafted handaxe and plate vambraces" → handaxe,
    vambraces — the words STOW takes."""
    match = _HINDERS.search(text)
    if not match:
        return []
    items = re.split(r",\s*|\s+and\s+", match.group(1))
    return [item.split()[-1] for item in items if item.strip()]


DIRECTIONS = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "ne": "northeast",
    "nw": "northwest",
    "se": "southeast",
    "sw": "southwest",
    "up": "up",
    "down": "down",
    "out": "out",
}


def locate(db, state):
    """The map id of the current room.

    The game's <nav rm> uid is the exact fix and wins whenever the map
    knows it, bar a sub-room that reports its enclosing room's uid
    (uid_room); titles collide (roads repeat the same title), so the
    title+exits guess is only the fallback. None when position is
    unknown."""
    if state is None:
        return None
    by_uid = uid_room(db, state)
    if by_uid is not None:
        return by_uid
    title = getattr(state, "room_title", None)
    if not title:
        return None
    candidates = db.rooms_titled(title)
    if not candidates:
        return None
    return _disambiguate(db, candidates, state.compass)


NEAR_STEPS = 3  # how far from the uid's room a sub-room is looked for


def uid_room(db, state):
    """The map room the game's <nav rm> uid names, the title permitting;
    None when the map does not know the uid. Inside a sub-room the game
    reports the enclosing room's uid — Fang Cove's Advanced Anatomy tent
    shows the lane's (2026-10-04, #466) — so when the uid's room is
    titled otherwise, the nearest room carrying the game's title, a few
    steps out, is where the character stands. Titles only: descriptions
    change with the time of day and with events."""
    uid = getattr(state, "room_uid", None)
    mapped = db.room_by_uid(uid) if uid else None
    title = getattr(state, "room_title", None)
    if mapped is None or not title or _titled(db, mapped, title):
        return mapped
    near = _titled_near(db, mapped, title)
    return near if near is not None else mapped


def _titled(db, room_id, title):
    titles = db.rooms.get(room_id, {}).get("title") or []
    return normalize_title(title) in {normalize_title(t) for t in titles}


def _titled_near(db, start, title):
    """The room nearest `start`, within NEAR_STEPS of its exits, titled
    `title`; None without one."""
    seen, frontier = {start}, [start]
    for _ in range(NEAR_STEPS):
        following = []
        for room_id in frontier:
            for dest in db.rooms.get(room_id, {}).get("wayto") or {}:
                try:
                    dest = int(dest)
                except ValueError:
                    continue
                if dest in seen or dest not in db.rooms:
                    continue
                if _titled(db, dest, title):
                    return dest
                seen.add(dest)
                following.append(dest)
        frontier = following
    return None


def _disambiguate(db, candidates, compass):
    """Same title, several rooms: prefer the one whose exits match ours."""
    if len(candidates) == 1 or not compass:
        return candidates[0]
    here_exits = {DIRECTIONS.get(direction, direction) for direction in compass}

    def exits_of(room_id):
        wayto = db.rooms[room_id].get("wayto") or {}
        return {
            command
            for command in wayto.values()
            if isinstance(command, str) and command in DIRECTIONS.values()
        }

    return max(candidates, key=lambda room_id: len(here_exits & exits_of(room_id)))


def avoided_rooms(db, entries):
    """The room ids an avoid list names — each entry resolved like a
    ;go2 target (tag, room id, or title substring). The standing list
    lives in settings ("avoid_rooms"); scripts resolve it once per db."""
    rooms = set()
    for entry in entries or []:
        rooms.update(db.resolve(str(entry)))
    return rooms


def read_story(s, seconds, until=()):
    """The story text that arrives within `seconds`, ending early once
    a piece holds any of `until`."""
    deadline = monotonic() + seconds
    seen = []
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        item = s.get(timeout=min(remaining, 0.5), streams=("",))
        if item is None:
            continue
        text = item[1] if isinstance(item, tuple) else item
        seen.append(text)
        if any(needle in text for needle in until):
            break
    return "".join(seen)


def ride_gondola(s, direction=""):
    """Board the gondola at this platform and cross (#211): "landed"
    when it stopped at the far platform (OUT is still the caller's to
    send, with the arrival check), "no gondola" when none came within
    GONDOLA_WAIT_SECONDS, "stuck" when the ride never stopped,
    "unknown" for an answer outside the table."""
    for _ in range(GONDOLA_ATTEMPTS):
        s.waitrt()
        s.put("go gondola")
        outcome, _, answer = await_arrival(s, timeout=GONDOLA_ANSWER_SECONDS)
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        if outcome == "arrived":
            s.echo("aboard the gondola — crossing the pass")
            if direction:
                s.put(direction)  # bescort moves the cab's way once aboard
            ride = read_story(s, GONDOLA_WAIT_SECONDS, until=GONDOLA_STOPS)
            if not any(needle in ride for needle in GONDOLA_STOPS):
                s.echo(
                    f"the gondola never stopped in {GONDOLA_WAIT_SECONDS // 60} "
                    "minutes — stopping here"
                )
                return "stuck"
            s.waitrt()
            return "landed"
        if any(needle in answer for needle in GONDOLA_AWAY):
            s.echo("no gondola at the platform — waiting for it")
            arrival = read_story(s, GONDOLA_WAIT_SECONDS, until=GONDOLA_DOOR)
            if not any(needle in arrival for needle in GONDOLA_DOOR):
                s.echo(
                    f"no gondola came in {GONDOLA_WAIT_SECONDS // 60} minutes"
                    " — stopping here"
                )
                return "no gondola"
            continue
        s.echo(f"GO GONDOLA answered {first!r} — please report it — stopping here")
        return "unknown"
    s.echo(
        f"the gondola would not take you in {GONDOLA_ATTEMPTS} tries — stopping here"
    )
    return "no gondola"


# The copper a refused fare fetches: ;bank keep=N withdraws the
# province's coin to an empty purse at the nearest teller, and the walk
# is planned again from there (#455, after #454's travel purse).
FARE_PURSE = 200
_FARE_COIN = re.compile(r"\b(kronars|lirums|dokoras)\b", re.IGNORECASE)


def fare_coin(answer):
    """The coin a captain refused the fare in ("lirums"), from the fee
    line or the refusal's "enough lirums"; "" when neither names one."""
    match = _FARE_COIN.search(str(answer or ""))
    return match.group(1).lower() if match else ""


def fetch_fare(s, coin=""):
    """;bank keep=FARE_PURSE, and <coin>=FARE_PURSE when the captain named
    one, run through the handle and waited for: the fare a ferry refused
    for coin (#455). The coin named is kept out of ;bank's foreign sweep
    and topped up at the changer — a bare keep= changed the lirums a
    Faldesu fare wants straight back to kronars (#507); where it is the
    province's own coin ;bank says so and keep= covers it. True when
    ;bank ran to its end; False, said, when the handle cannot start it
    (a ;bank already running is the operator's)."""
    run = getattr(s, "run", None)
    running = getattr(s, "is_running", None)
    if run is None or running is None:
        return False
    args = [f"keep={FARE_PURSE}"] + ([f"{coin}={FARE_PURSE}"] if coin else [])
    if not run("bank", args):
        s.echo("could not start ;bank for the fare — fetch coins by hand")
        return False
    s.echo(f"fetching the fare: ;bank {' '.join(args)}, then the way again")
    while running("bank"):
        s.sleep(1)
    return True


def ride_ferry(s, direction=""):
    """Board the ferry at this dock and cross (#205): "landed" when the
    far dock is reached (GO DOCK is still the caller's to send, with
    the arrival check), "fare" when refused for coin and left on the
    dock, "no ferry" when none came within FERRY_WAIT_SECONDS, "stuck"
    when the crossing never docked, "unknown" for an answer outside the
    table. Boarding is the room change after GO FERRY (a compass
    frame), whatever the captain says about the fare — the Faldesu's
    captain puts it on your Therengian debt when you have no lirums and
    lets you aboard. While the ferry is out, GO FERRY is tried again
    every FERRY_POLL_SECONDS; the same routine serves Alfren's Ferry
    over the Segoltha, captured on 2026-09-18 with the same arrival
    ("pulls into the dock") and fee lines, 35 kronars."""
    waiting = False  # the wait is said once, not every poll (the operator, 2026-10-10)
    for _ in range(max(1, round(FERRY_WAIT_SECONDS / FERRY_POLL_SECONDS))):
        s.waitrt()
        s.put("go ferry")
        outcome, _, answer = await_arrival(s, timeout=FERRY_ANSWER_SECONDS)
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        if outcome == "arrived":
            fee = FERRY_FEE.search(answer)
            if any(needle in answer for needle in FERRY_ON_DEBT):
                s.echo(
                    "aboard the ferry — no lirums on you, so the captain put the "
                    f"fare{' of ' + fee.group(1) if fee else ''} on your Therengian "
                    "debt (;debt pay settles it) — crossing"
                )
            else:
                s.echo(
                    "aboard the ferry"
                    + (f" — fare {fee.group(1)}" if fee else "")
                    + " — crossing"
                )
            crossing = read_story(s, FERRY_WAIT_SECONDS, until=FERRY_LANDS)
            if not any(needle in crossing for needle in FERRY_LANDS):
                s.echo(
                    f"the ferry never docked in {FERRY_WAIT_SECONDS // 60} minutes"
                    " — stopping here"
                )
                return "stuck"
            return "landed"
        if any(needle in answer for needle in FERRY_NO_FARE):
            # The game's own line, not the "[Assuming you mean the
            # ferry ...]" note ahead of it (#337), and the fare against
            # the purse.
            fee = FERRY_FEE.search(answer)
            s.echo(
                "the ferry refused the fare"
                + (f" of {fee.group(1)}" if fee else "")
                + fare_purse(s, fee.group(1) if fee else "")
                + f": {answer_line(answer, FERRY_NO_FARE)!r}"
            )
            return f"fare {fare_coin(answer)}".strip()
        if any(needle in answer for needle in FERRY_AWAY):
            if not waiting:
                s.echo(
                    "no ferry at the dock — waiting for one "
                    f"(up to {FERRY_WAIT_SECONDS // 60} minutes)"
                )
                waiting = True
            read_story(s, FERRY_POLL_SECONDS, until=FERRY_ARRIVES)
            continue
        s.echo(f"GO FERRY answered {first!r} — please report it — stopping here")
        return "unknown"
    s.echo(f"no ferry came in {FERRY_WAIT_SECONDS // 60} minutes — stopping here")
    return "no ferry"


def fare_purse(s, fee):
    """ ", you carry <coins>" for a fare's currency ("30 lirums"), from
    WEALTH (no roundtime, nothing changes); "" when the currency or the
    answer is not known."""
    currency = fee.split()[-1].capitalize() if fee else ""
    if currency not in money.CURRENCIES:
        return ""
    s.put("wealth")
    carried = money.parse_wealth(read_story(s, WEALTH_SECONDS))["carried"]
    if currency not in carried:
        return ""
    return f", you carry {money.phrase(carried[currency], currency)}"


def search_hidden(s, command):
    """SEARCH for a hidden way until the answer is not the empty one,
    SEARCH_TRIES at most (#367): True when found. The move after it
    tells the rest — a way still hidden answers "could not find"."""
    for _ in range(SEARCH_TRIES):
        s.waitrt()
        s.put(command)
        answer = read_story(s, SEARCH_ANSWER_SECONDS, until=SEARCH_EMPTY + SEARCH_FOUND)
        if not any(needle in answer for needle in SEARCH_EMPTY):
            return True
    s.echo(f"{SEARCH_TRIES} searches found no hidden way here")
    return False


def barge_name(text):
    """The barge a room's object line or a story piece names, as GO takes
    it — its name's last word, lowered: "riverhawk" from "the barge
    Riverhawk and a brushy break ...", "glory" from "the barge Imperial
    Glory"; None when none is listed."""
    match = _BARGE_NAME.search(str(text or ""))
    if not match:
        return None
    return match.group("name").split()[-1].lower()


def ride_barge(s, direction=""):
    """Board the barge at this dock by its name and cross (#506): "landed"
    at the far dock (GO DOCK is the caller's), "fare" when refused for
    coin, "no barge" when none came within BARGE_WAIT_SECONDS, "stuck"
    when the crossing never docked, "unknown" for an answer outside the
    table. The name comes from the room's objects, else from the story
    that brings the barge in; a barge still nearing answers GO with
    BARGE_NOT_YET and is tried again once it docks."""
    deadline = monotonic() + BARGE_WAIT_SECONDS
    waiting = False  # said once, not every poll (the operator, 2026-10-10)
    while monotonic() < deadline:
        name = barge_name(getattr(s.state, "room_objs", ""))
        if not name:
            if not waiting:
                s.echo(
                    "no barge at the dock — waiting for one "
                    f"(up to {BARGE_WAIT_SECONDS // 60} minutes)"
                )
                waiting = True
            story = read_story(s, BARGE_POLL_SECONDS, until=BARGE_ARRIVES)
            name = barge_name(story) or barge_name(getattr(s.state, "room_objs", ""))
            if not name:
                continue
        s.waitrt()
        s.put(f"go {name}")
        outcome, _, answer = await_arrival(s, timeout=BARGE_ANSWER_SECONDS)
        if outcome == "arrived":
            fee = FERRY_FEE.search(answer)
            s.echo(
                f"aboard the barge {name}"
                + (f" — fare {fee.group(1)}" if fee else "")
                + " — crossing"
            )
            crossing = read_story(s, BARGE_WAIT_SECONDS, until=BARGE_LANDS)
            if not any(needle in crossing for needle in BARGE_LANDS):
                s.echo(
                    f"the barge never docked in {BARGE_WAIT_SECONDS // 60} minutes"
                    " — stopping here"
                )
                return "stuck"
            return "landed"
        if any(needle in answer for needle in BARGE_NOT_YET):
            read_story(s, BARGE_POLL_SECONDS, until=BARGE_ARRIVES)
            continue
        if any(needle in answer for needle in FERRY_NO_FARE):
            fee = FERRY_FEE.search(answer)
            s.echo(
                "the barge refused the fare"
                + (f" of {fee.group(1)}" if fee else "")
                + fare_purse(s, fee.group(1) if fee else "")
                + f": {answer_line(answer, FERRY_NO_FARE)!r}"
            )
            return f"fare {fare_coin(answer)}".strip()
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(
            f"GO {name.upper()} answered {first!r} — please report it — stopping here"
        )
        return "unknown"
    s.echo(f"no barge came in {BARGE_WAIT_SECONDS // 60} minutes — stopping here")
    return "no barge"


def ride_mammoth(s, mode=""):
    """JOIN the sea mammoth at this dock and cross (#515): "landed" ashore
    at the far side (the mammoth sets you there), "no mammoth" when none
    came within MAMMOTH_WAIT_SECONDS, "stuck" when the crossing never
    landed, "unknown" for an answer outside the table. The tall one
    serves Acenamacra (bescort's 'acen', and 'fang' from its pier), the
    massive one Ratha."""
    title = str(getattr(s.state, "room_title", "") or "")
    kind = "tall" if mode == "acen" or "Acenamacra" in title else "sea"
    deadline = monotonic() + MAMMOTH_WAIT_SECONDS
    waiting = False  # said once, not every poll (the operator, 2026-10-10)
    while monotonic() < deadline:
        s.waitrt()
        s.put(f"join {kind} mammoth")
        outcome, _, answer = await_arrival(s, timeout=MAMMOTH_ANSWER_SECONDS)
        if outcome == "arrived":
            s.echo(f"aboard the {kind} mammoth — crossing")
            crossing = read_story(s, MAMMOTH_WAIT_SECONDS, until=MAMMOTH_LANDS)
            if not any(needle in crossing for needle in MAMMOTH_LANDS):
                s.echo(
                    f"the mammoth never landed in {MAMMOTH_WAIT_SECONDS // 60} "
                    "minutes — stopping here"
                )
                return "stuck"
            return "landed"
        if any(needle in answer for needle in MAMMOTH_AWAY):
            if not waiting:
                s.echo(
                    "no mammoth at the dock — waiting for one "
                    f"(up to {MAMMOTH_WAIT_SECONDS // 60} minutes)"
                )
                waiting = True
            read_story(s, MAMMOTH_POLL_SECONDS, until=MAMMOTH_ARRIVES)
            continue
        first = (answer.strip().splitlines() or ["(silence)"])[0]
        s.echo(
            f"JOIN {kind.upper()} MAMMOTH answered {first!r} — please report it "
            "— stopping here"
        )
        return "unknown"
    s.echo(f"no mammoth came in {MAMMOTH_WAIT_SECONDS // 60} minutes — stopping here")
    return "no mammoth"


# route -> (the ride, the step's own move off it)
RIDE_HANDLERS = {
    "faldesu": (ride_ferry, "go dock"),
    "ferry": (ride_ferry, "go dock"),
    "gondola": (ride_gondola, "out"),
    "haven_throne": (ride_barge, "go dock"),
    "mammoth": (ride_mammoth, "look"),
}


def await_arrival(s, timeout=ARRIVAL_TIMEOUT):
    """Wait for the compass frame that means the move landed, reading
    the story meanwhile for a climb turned back or a way closed to the
    character. ("arrived" | "refused" | "closed" | "stalled", the
    hindering item nouns a refusal named, the story text seen — the
    climb log keeps the wording, #159)."""
    deadline = monotonic() + timeout
    hindering = []
    seen = []
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return "stalled", hindering, "".join(seen)
        item = s.get(timeout=remaining, streams=None)
        if item is None:
            return "stalled", hindering, "".join(seen)
        stream, text = item
        if stream == "compass":
            return "arrived", hindering, "".join(seen)
        if stream:
            continue  # a dock's stream: not the story
        seen.append(text)
        hindering.extend(hindering_nouns(text))
        if any(needle in text for needle in CLIMB_REFUSALS + POSTURE_REFUSALS):
            return "refused", hindering, "".join(seen)
        if any(needle in text for needle in GATE_REFUSALS + WAY_REFUSALS):
            return "closed", hindering, "".join(seen)
        if any(needle in text for needle in KNEELING_REFUSALS):
            return "posture", hindering, "".join(seen)
        if ROUNDTIME_WAIT.search(text):
            return "roundtime", hindering, "".join(seen)


def answer_line(wording, needles):
    """The story line that holds one of `needles` — the game's answer —
    else the first line: a bystander's "Sekhhtha goes west." arrived
    before "You're not experienced enough to go there." and stood in
    for it in the echo (2026-09-27, #359)."""
    lines = wording.strip().splitlines() or ["?"]
    return next(
        (line for line in lines if any(needle in line for needle in needles)),
        lines[0],
    )


def note_climb(s, command, outcome, wording, room):
    """Every climb the walker sends goes into history.db's climbs table
    with what the state knows for free (#159): up, the refusal's kind,
    or a stall. Other moves are not climbs and are not logged."""
    if not command.lower().startswith("climb"):
        return
    from client.game import climblog  # climblog imports this module

    if outcome == "arrived":
        kind = "up"
    elif outcome == "refused":
        kind = climblog.refusal_kind(wording) or "other"
    else:
        kind = "stalled"
    climblog.log_walk(s, command, kind, wording, room=room)


def stand(s):
    """STAND with the answer read (#411): (True, "") once standing —
    "You stand back up.", "You are already standing.", or nothing in
    the window — else (False, the refusal's line). An unbalanced
    refusal gets one retry after BALANCE_WAIT; an overburdened one
    does not, the load has to go first."""
    line = ""
    for attempt in range(2):
        s.put("stand")
        wording = read_story(s, STAND_SECONDS, until=STAND_ANSWERS)
        s.waitrt()
        if not any(needle in wording for needle in STAND_REFUSED):
            return True, ""
        line = answer_line(wording, STAND_REFUSED)
        if "unbalanced" in wording and attempt == 0:
            s.sleep(BALANCE_WAIT)
            continue
        break
    return False, line


def stand_advice(refusal):
    """What to do about a STAND the game refused."""
    if "overburdened" in refusal:
        return "bank or stow the load first"
    if "unbalanced" in refusal:
        return "your balance has to come back first"
    return "the walk cannot start"


def retry_climb(s, command, hindering):
    """The one retry a turned-back climb gets: the refusal's roundtime
    waited out, STAND (a failed climb sits you down, and the posture
    indicator lands a beat after the refusal text — reading it at once
    said "standing" and both STOWs answered "You must stand first.",
    captured 2026-09-11; standing already, STAND is harmless), the
    hindering items stowed (a worn piece answers STOW with a refusal,
    harmless), the climb again. Returns await_arrival's answer."""
    s.waitrt()
    stood, _ = stand(s)
    steps = ["stood up" if stood else "could not stand"]
    for noun in hindering:
        s.put(f"stow my {noun}")
        s.waitrt()
    if hindering:
        steps.append("stowed " + ", ".join(hindering))
    s.echo(f"the climb was turned back — {', '.join(steps)}, trying it once more")
    while s.get(timeout=0, streams=("compass",)) is not None:
        pass
    s.put(command)
    return await_arrival(s)


def character_ranks(state):
    """The exp window's {skill: rank} from the parser's state, {} before
    the window has said anything — what the router's gates read (#214);
    a skill the window has not listed counts as rank 0 there."""
    experience = getattr(state, "experience", None) or {}
    return {
        skill: row.get("rank", 0)
        for skill, row in experience.items()
        if isinstance(row, dict)
    }


def character_premium(state):
    """True when the character's profile says the account has Premium
    (`premium`): the meeting portals into Fang Cove are open to it."""
    name = getattr(state, "name", None)
    if not name:
        return False
    from client.game.profile import load_profile

    return bool(load_profile(name).get("premium"))


def _explain_no_path(s, db, here, goals, avoid, closed, ranks, describe, premium=False):
    """Say why no route exists: the gate the character does not pass on
    the only way (#214), else the scripted-edge answer of old."""
    ungated = db.path(here, goals, avoid=avoid, closed=closed, gates=False)
    if ungated:
        shut = [
            gate
            for _, _, gate in db.route_gates(here, ungated)
            if not gate.met(ranks, premium=premium)
        ]
        if shut:
            asks = ", ".join(gate.describe() for gate in shut)
            held = ", ".join(
                f"{gate.skill} {ranks.get(gate.skill, 0)}"
                for gate in shut
                if gate.skill
            )
            s.echo(
                f"no way to {describe} within your reach — the route needs {asks}"
                + (f" (you have {held})" if held else "")
            )
            return
    s.echo(f"no walkable path to {describe} (a scripted-only edge may be needed)")


def _dead_end(db, here, closed):
    """True when the map lists no walkable way out of `here` that this
    walk has not found closed."""
    wayto = (db.rooms.get(here) or {}).get("wayto") or {}
    return not any(
        walkable(command) and (here, int(dest)) not in closed
        for dest, command in wayto.items()
    )


def leave_dead_end(s, db, here):
    """Leave a room the map lists without exits by the compass — the
    Shrine of Ushnish, entered by `go shrine` and never mapped back
    (#229): OUT first, then each direction, until a move lands in a
    room the map knows. That room's id, or None when no exit landed.
    A landing is written to the local map overlay so the next walk
    plans through it."""
    compass = list(getattr(s.state, "compass", None) or [])
    exits = sorted(compass, key=lambda direction: direction != "out")
    title = ((db.rooms.get(here) or {}).get("title") or ["?"])[0]
    for direction in exits:
        command = DIRECTIONS.get(direction, direction)
        s.echo(f"the map knows no way out of {title} — trying {command.upper()}")
        s.waitrt()
        while s.get(timeout=0, streams=("compass",)) is not None:
            pass
        s.put(command)
        outcome, _, _ = await_arrival(s)
        if outcome != "arrived":
            continue
        there = locate(db, s.state)
        if there is None or db.same_place(there, here):
            continue
        db.record_edge(here, there, command)
        s.echo(f"map: {here} {command} -> {there} recorded locally")
        return there
    return None


def walk(s, db, goals, describe="destination", avoid=(), max_steps=None):
    """Walk to the nearest goal room; True on arrival (or already there).

    Rooms in `avoid` are routed around when a clean detour exists;
    a route forced through them is announced before the first step.
    A gated edge the character's ranks cannot pass — the map's Ruby
    timeto values (#214) — is never planned, and a walk whose only way
    is gated stops before its first step saying which gate.
    Echoes progress and failure detail the way ;go2 always has: stalls
    and off-course rooms stop the walk rather than guessing onward."""
    if s.dead:
        s.echo("you are DEAD — corpses don't travel; deathwatch has it (#91)")
        return False
    here = locate(db, s.state)
    if here is None:
        title = getattr(s.state, "room_title", None) if s.state else None
        if title and not db.rooms_titled(title):
            s.echo(f"room {title!r} is not in the map database")
        else:
            s.echo("current room unknown yet — 'look' once and retry")
        return False
    # Standing first when the parser says otherwise: a ;go2 sent kneeling
    # after a prayer was answered "You can't do that while kneeling!" and
    # went nowhere (#220). The refusal path below covers a posture the
    # state has not caught up with.
    posture = getattr(getattr(s, "status", None), "posture", None)
    if posture and posture != "standing":
        stood, refusal = stand(s)
        if not stood:
            # #411: "You are overburdened and cannot manage to stand." —
            # the walk used to say "stood up first" and fail seated.
            s.echo(f"cannot stand to walk ({refusal!r}) — {stand_advice(refusal)}")
            return False
        s.echo(f"stood up first (you were {posture})")
    avoid = frozenset(avoid)
    # (room, dest) edges the game refused this walk (#209), and those a
    # gate refused the character before in the session (#394).
    closed = set(gated(s))
    ranks = character_ranks(s.state)
    premium = character_premium(s.state)  # the meeting portals into Fang Cove
    goals = set(goals)
    fetched = False  # a refused fare's coins fetched this walk (#455)
    for _ in range(REROUTES + 1):
        route = db.path(
            here, goals, avoid=avoid, closed=closed, ranks=ranks, premium=premium
        )
        if route is None:
            if _dead_end(db, here, closed):
                # A room the map lists without exits (#229): out by the
                # compass, then plan again from wherever that landed.
                left = leave_dead_end(s, db, here)
                if left is not None:
                    here = left
                    continue
            _explain_no_path(
                s, db, here, goals, avoid, closed, ranks, describe, premium
            )
            return False
        if not route:
            return True
        if max_steps and len(route) > max_steps:
            # Checked on every plan, a replan included: ;soul's altar walk
            # was 53 steps when it set out, and after two closed ways the
            # nearest altar was Shard's, 261 steps over the ferry and the
            # gondola (2026-09-28, #364).
            s.echo(
                f"the way to {describe} is {len(route)} steps — past the "
                f"{max_steps}-step limit; stopping here"
            )
            return False
        crossed = [dest for dest, _ in route if dest in avoid]
        if crossed:
            titles = db.rooms[crossed[0]].get("title") or ["?"]
            s.echo(
                f"warning: no clean detour — the route crosses "
                f"{len(crossed)} avoided room(s), first {titles[0]}"
            )
        s.echo(f"walking {len(route)} steps to {describe}")
        outcome = _follow(s, db, route, here, closed, fetched)
        if outcome == "fetched":
            fetched = True
        elif outcome != "closed":
            return outcome
        here = locate(db, s.state)
        if here is None:
            s.echo("current room unknown after the refusal — stopping here")
            return False
    s.echo(f"{REROUTES} ways closed to you on one walk — stopping here")
    return False


def _follow(s, db, route, here, closed, fetched=True):
    """Walk one planned route from `here`: True on arrival, False on a
    stop, "closed" when the game refused an edge — added to `closed`
    for the caller to plan again without it (#209) — and "fetched" when
    a ferry refused the fare and ;bank fetched it (#455), unless one
    was `fetched` already this walk."""
    for number, (dest, command) in enumerate(route, 1):
        if s.dead:
            s.echo(f"died en route at step {number} — stopping; deathwatch takes it")
            return False
        # A scripted edge translates to several game commands; the move
        # lands in the destination room and gets the arrival check, and
        # a STAND or LOOK after it goes out once there (split_move).
        commands = translate_embedded(command) or [command]
        ride = ride_of(command)
        if ride:
            # A ride edge (#205, #211): the ride first, then the move
            # off it is the step's own, with the compass sync and check.
            handler, leave = RIDE_HANDLERS[ride]
            ridden = handler(s, ride_args(command))
            fare, _, coin = ridden.partition(" ")
            if fare == "fare" and not fetched and fetch_fare(s, coin):
                return "fetched"  # planned again from where ;bank left you
            if ridden != "landed":
                return False
            commands = [leave]
        before, move, after = split_move(commands)
        s.waitrt()
        for preliminary in before:
            if preliminary.split()[0].lower() == "search":
                search_hidden(s, preliminary)
            else:
                s.put(preliminary)
            s.waitrt()
        # Discard any stale compass frames so the next one that arrives
        # pairs with this move — a spurious frame must never desync the
        # walk (the double-frame bug, structurally prevented).
        while s.get(timeout=0, streams=("compass",)) is not None:
            pass
        s.put(move)
        outcome, hindering, wording = await_arrival(s)
        for _ in range(ROUNDTIME_RETRIES):
            if outcome != "roundtime":
                break
            # Sent into roundtime (#367): sleep it out, the move again.
            match = ROUNDTIME_WAIT.search(wording)
            s.sleep(int(match.group(1)) + 0.5 if match else 1)
            s.waitrt()
            s.put(move)
            outcome, hindering, wording = await_arrival(s)
        note_climb(s, move, outcome, wording, dest)
        if outcome == "posture":
            # Kneeling (a prayer), sitting or lying: STAND and one retry
            # (#220); the engaged-stall burst below would not help.
            first = answer_line(wording, KNEELING_REFUSALS)
            s.waitrt()
            stood, refusal = stand(s)
            if not stood:
                s.echo(
                    f"step {number}: cannot stand ({refusal!r}) — "
                    f"{stand_advice(refusal)}; stopping here"
                )
                return False
            s.echo(f"step {number}: stood up first ({first!r})")
            s.put(move)
            outcome, hindering, wording = await_arrival(s)
            note_climb(s, move, outcome, wording, dest)
            if outcome == "posture":
                s.echo(f"step {number}: still cannot move ({first!r}) — stopping here")
                return False
        if outcome == "closed":
            closed.add((here, dest))
            titles = db.rooms[dest].get("title") or ["?"]
            first = answer_line(wording, GATE_REFUSALS + WAY_REFUSALS)
            kept = ""
            if any(needle in wording for needle in GATE_REFUSALS):
                gated(s).add((here, dest))
                kept = ", and on every walk this session"
            s.echo(
                f"the way to {titles[0]} is closed to you ({first!r}) — going round{kept}"
            )
            return "closed"
        if outcome == "refused":
            # A climb beyond the character's Athletics (#157): one
            # retry standing and unburdened, then the truth and a stop.
            outcome, again, wording = retry_climb(s, move, hindering)
            note_climb(s, move, outcome, wording, dest)
            if outcome == "refused":
                # Beyond the character (#157): the edge is closed for
                # this walk and the route planned again without it
                # (#211: the way under the gondola is six climbs the
                # gondola avoids); no other way, and the walk ends.
                load = ", ".join(dict.fromkeys(hindering + again))
                s.echo(
                    f"the climb at step {number} ({move!r}) is beyond "
                    "your Athletics"
                    + (f" with your {load}" if load else "")
                    + " — shed the load, train it (;athletics), or take the "
                    "long way — going round if the map has one"
                )
                closed.add((here, dest))
                return "closed"
            if outcome == "arrived" and hindering:
                s.echo(
                    f"made it with your {', '.join(hindering)} stowed — "
                    "get what you need back out"
                )
        if outcome == "stalled":
            # Engaged: moves and climbs refuse until retreated out to
            # missile range (docs/combat.md) — burst retreat/retreat/
            # step through the type-ahead and give the step one retry.
            # Unconditionally: hostile state can be empty while engaged
            # (#88 — the #85 wipe left a walker stalled at melee with a
            # clean hostiles dict, and it walked away from the fight by
            # exiting), and a retreat while unengaged is harmless —
            # except where the only exit is "out" (a bank's lobby, a
            # shop, #171): nothing engages there and a retreat answers
            # "You are already as far away as you can get!", so the
            # step gets its one retry alone.
            if list(getattr(s.state, "compass", None) or []) != ["out"]:
                s.put("retreat")
                s.put("retreat")
            s.put(move)
            outcome, _, wording = await_arrival(s)
            note_climb(s, move, outcome, wording, dest)
            if outcome in ("refused", "closed"):
                # The retry was turned back in words (a climb's refusal
                # that came late, or a way closed): the edge is closed
                # for this walk and the route planned again (#211).
                closed.add((here, dest))
                s.echo(
                    f"step {number} ({move!r}) is turned back for you — "
                    "going round if the map has a way"
                )
                return "closed"
        if outcome != "arrived":
            s.echo(f"stalled at step {number} ({move!r}) — stopping here")
            return False
        for follow_up in after:
            s.waitrt()
            s.put(follow_up)
        previous, here = here, dest  # the planned room, or its twin: the same place
        # Arrival check: the nav uid is exact when the map knows it;
        # title comparison is the fallback for unmapped-uid rooms.
        mapped = uid_room(db, s.state)  # a tent's uid is its lane's (#466)
        if mapped is not None:
            # A twin of the planned room is the planned room: the map
            # lists some places twice, only one entry carrying the
            # game's uid (#137).
            if not db.same_place(mapped, dest):
                # The map's edge led somewhere else — Varlet's Run's
                # north is Goodwhate Pike 864 in the game, 863 on the
                # map; Glaysker Lane's `go shop` is Feta's Kitchen, not
                # the Shrine of Ushnish (2026-09-20, #232): the edge is
                # closed for this walk, the room it does lead to is
                # written to the local map in its place, and the route
                # is planned again from the room the game says we are
                # in, the way a closed way is.
                closed.add((previous, dest))
                # Written to the local map only for a plain compass move
                # that changed room: the Crossing temple's staircase, its
                # clockwise/widdershins ring and its `go` doors pass rooms
                # in one move, and the arrival read there wrote "5751 down
                # -> 5752" and then "-> 5750", which sent a later walk
                # over the ferry and the gondola to Shard (2026-09-28,
                # #364). Anything else is closed for this walk only.
                if move.strip().lower() in COMPASS_MOVES and mapped != previous:
                    db.record_edge(previous, mapped, move)
                    note = f"the map now says {previous} {move} -> {mapped}"
                else:
                    note = "left off the map (a stair, a ring or a named way)"
                s.echo(
                    f"off course at step {number}: in room {mapped} "
                    f"({s.state.room_title!r}), expected {dest} — {note}; "
                    "planning again from here"
                )
                return "closed"
            continue
        expected = db.rooms[dest].get("title") or []
        actual = s.state.room_title
        if expected and actual:
            wanted = {normalize_title(title) for title in expected}
            if normalize_title(actual) not in wanted:
                s.echo(
                    f"off course at step {number}: in {actual!r}, expected "
                    f"{expected[0]!r} — stopping here"
                )
                return False
    s.waitrt()
    return True
