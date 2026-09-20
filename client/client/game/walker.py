"""Shared room location and walking for scripts (;go2, ;athletics, ...).

locate() turns parsed game state into a community-map room id; walk()
drives the character along a BFS route from the map database, verifying
arrival room by room. Extracted from ;go2 (this is ;go2's engine) so
any script can travel. A climb the game turns back for footing (#157)
gets one retry standing with the hindering items stowed, then stops
with what would help; an engagement gets the retreat burst, unless
the room's only exit is "out" — a bank or shop, where nothing engages
and a retreat has nowhere to go (#171) (docs/movement.md). A ferry edge
(the map's bescort 'faldesu' crossing, #205) is ridden: GO FERRY when
the ferry is at the dock, the wait for it when not, the crossing, then
GO DOCK as the step's move — after dr-scripts' bescort take_rh_ferry,
the wordings captured on the first ride (2026-09-18): the fare is 30
lirums, put on the Therengian debt when there are none on you.
"""

import re
from time import monotonic

from client.client_logger import ClientLogger
from client.game.mapdb import (
    normalize_title,
    ride_args,
    ride_of,
    translate_embedded,
    walkable,
)

module_logger = ClientLogger()

ARRIVAL_TIMEOUT = 15  # seconds for the compass frame after a move

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
# a character the captain does not call young, is still uncaptured).
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
FERRY_FEE = re.compile(r"transportation fee of (\d+ \w+)")
# Alfren's, captured 2026-09-18: "The Captain stops you and requests a
# transportation fee of 35 kronars as you board the craft." / "You
# hand him your kronars and climb aboard." — the fee line is the
# Faldesu's shape, so FERRY_FEE reads it; the nod is bescort's.
FERRY_PAID = ("you hand him", "gives you a little nod")
FERRY_ON_DEBT = ("add it to yer debt", "debt to the province")
FERRY_ARRIVES = ("pulls into the dock", "pulls up to the dock")
FERRY_LANDS = ("ties the ferry off",)
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
# and the route planned again without it.
GATE_REFUSALS = ("not experienced enough to go there",)
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
    knows it; titles collide (roads repeat the same title), so the
    title+exits guess is only the fallback. None when position is
    unknown."""
    if state is None:
        return None
    uid = getattr(state, "room_uid", None)
    if uid:
        by_uid = db.room_by_uid(uid)
        if by_uid is not None:
            return by_uid
    title = getattr(state, "room_title", None)
    if not title:
        return None
    candidates = db.rooms_titled(title)
    if not candidates:
        return None
    return _disambiguate(db, candidates, state.compass)


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
            s.echo(f"the ferry refused the fare: {first!r} — stopping here")
            return "fare"
        if any(needle in answer for needle in FERRY_AWAY):
            s.echo("no ferry at the dock — waiting for one")
            read_story(s, FERRY_POLL_SECONDS, until=FERRY_ARRIVES)
            continue
        s.echo(f"GO FERRY answered {first!r} — please report it — stopping here")
        return "unknown"
    s.echo(f"no ferry came in {FERRY_WAIT_SECONDS // 60} minutes — stopping here")
    return "no ferry"


# route -> (the ride, the step's own move off it)
RIDE_HANDLERS = {
    "faldesu": (ride_ferry, "go dock"),
    "ferry": (ride_ferry, "go dock"),
    "gondola": (ride_gondola, "out"),
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


def retry_climb(s, command, hindering):
    """The one retry a turned-back climb gets: the refusal's roundtime
    waited out, STAND (a failed climb sits you down, and the posture
    indicator lands a beat after the refusal text — reading it at once
    said "standing" and both STOWs answered "You must stand first.",
    captured 2026-09-11; standing already, STAND is harmless), the
    hindering items stowed (a worn piece answers STOW with a refusal,
    harmless), the climb again. Returns await_arrival's answer."""
    s.waitrt()
    s.put("stand")
    s.waitrt()
    steps = ["stood up"]
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


def _explain_no_path(s, db, here, goals, avoid, closed, ranks, describe):
    """Say why no route exists: the gate the character does not pass on
    the only way (#214), else the scripted-edge answer of old."""
    ungated = db.path(here, goals, avoid=avoid, closed=closed, gates=False)
    if ungated:
        shut = [
            gate for _, _, gate in db.route_gates(here, ungated) if not gate.met(ranks)
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


def walk(s, db, goals, describe="destination", avoid=()):
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
    avoid = frozenset(avoid)
    closed = set()  # (room, dest) edges the game refused this walk (#209)
    ranks = character_ranks(s.state)
    goals = set(goals)
    for _ in range(REROUTES + 1):
        route = db.path(here, goals, avoid=avoid, closed=closed, ranks=ranks)
        if route is None:
            if _dead_end(db, here, closed):
                # A room the map lists without exits (#229): out by the
                # compass, then plan again from wherever that landed.
                left = leave_dead_end(s, db, here)
                if left is not None:
                    here = left
                    continue
            _explain_no_path(s, db, here, goals, avoid, closed, ranks, describe)
            return False
        if not route:
            return True
        crossed = [dest for dest, _ in route if dest in avoid]
        if crossed:
            titles = db.rooms[crossed[0]].get("title") or ["?"]
            s.echo(
                f"warning: no clean detour — the route crosses "
                f"{len(crossed)} avoided room(s), first {titles[0]}"
            )
        s.echo(f"walking {len(route)} steps to {describe}")
        outcome = _follow(s, db, route, here, closed)
        if outcome != "closed":
            return outcome
        here = locate(db, s.state)
        if here is None:
            s.echo("current room unknown after the refusal — stopping here")
            return False
    s.echo(f"{REROUTES} ways closed to you on one walk — stopping here")
    return False


def _follow(s, db, route, here, closed):
    """Walk one planned route from `here`: True on arrival, False on a
    stop, "closed" when the game refused an edge — added to `closed`
    for the caller to plan again without it (#209)."""
    for number, (dest, command) in enumerate(route, 1):
        if s.dead:
            s.echo(f"died en route at step {number} — stopping; deathwatch takes it")
            return False
        # A scripted edge translates to several game commands; the last
        # one lands in the destination room and gets the arrival check.
        commands = translate_embedded(command) or [command]
        ride = ride_of(command)
        if ride:
            # A ride edge (#205, #211): the ride first, then the move
            # off it is the step's own, with the compass sync and check.
            handler, leave = RIDE_HANDLERS[ride]
            if handler(s, ride_args(command)) != "landed":
                return False
            commands = [leave]
        s.waitrt()
        for preliminary in commands[:-1]:
            s.put(preliminary)
            s.waitrt()
        # Discard any stale compass frames so the next one that arrives
        # pairs with this move — a spurious frame must never desync the
        # walk (the double-frame bug, structurally prevented).
        while s.get(timeout=0, streams=("compass",)) is not None:
            pass
        s.put(commands[-1])
        outcome, hindering, wording = await_arrival(s)
        note_climb(s, commands[-1], outcome, wording, dest)
        if outcome == "closed":
            closed.add((here, dest))
            titles = db.rooms[dest].get("title") or ["?"]
            first = (wording.strip().splitlines() or ["?"])[0]
            s.echo(f"the way to {titles[0]} is closed to you ({first!r}) — going round")
            return "closed"
        if outcome == "refused":
            # A climb beyond the character's Athletics (#157): one
            # retry standing and unburdened, then the truth and a stop.
            outcome, again, wording = retry_climb(s, commands[-1], hindering)
            note_climb(s, commands[-1], outcome, wording, dest)
            if outcome == "refused":
                # Beyond the character (#157): the edge is closed for
                # this walk and the route planned again without it
                # (#211: the way under the gondola is six climbs the
                # gondola avoids); no other way, and the walk ends.
                load = ", ".join(dict.fromkeys(hindering + again))
                s.echo(
                    f"the climb at step {number} ({commands[-1]!r}) is beyond "
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
            s.put(commands[-1])
            outcome, _, wording = await_arrival(s)
            note_climb(s, commands[-1], outcome, wording, dest)
            if outcome in ("refused", "closed"):
                # The retry was turned back in words (a climb's refusal
                # that came late, or a way closed): the edge is closed
                # for this walk and the route planned again (#211).
                closed.add((here, dest))
                s.echo(
                    f"step {number} ({commands[-1]!r}) is turned back for you — "
                    "going round if the map has a way"
                )
                return "closed"
        if outcome != "arrived":
            s.echo(f"stalled at step {number} ({commands[-1]!r}) — stopping here")
            return False
        here = dest  # the planned room, or its twin: the same place
        # Arrival check: the nav uid is exact when the map knows it;
        # title comparison is the fallback for unmapped-uid rooms.
        uid = getattr(s.state, "room_uid", None)
        mapped = db.room_by_uid(uid) if uid else None
        if mapped is not None:
            # A twin of the planned room is the planned room: the map
            # lists some places twice, only one entry carrying the
            # game's uid (#137).
            if not db.same_place(mapped, dest):
                s.echo(
                    f"off course at step {number}: in room {mapped} "
                    f"({s.state.room_title!r}), expected {dest} — stopping here"
                )
                return False
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
