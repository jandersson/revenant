"""Run an NPC's task for the coin:  ;task <giver>
    ;task <giver>        ask the giver (a noun the room knows: cormyn) for a task and accept it; a kind the profile's task_declines names is declined
    ;task                carry on the task in hand (the journal's): a delivery walks to the recipient and hands the item over; a search kneels and searches the area's rooms, then brings the find back to the giver
    ;task item=<noun>    ... naming the item when the record of the accept is gone (a basket)
    ;task return         typed while it runs: finish the step in hand and stop

What it does
- TASK first: a task already in hand is carried on, no ask.
- The offer has thirty seconds: it is accepted at once (a kind in task_declines is declined). A delivery is run; any other kind is yours from here — the offer said, the task recorded.
- A delivery: the item lands in a hand and is stowed; the walk to the recipient's room (the givers' table in client/game/tasks.py); GET the item by the id the accept recorded (INV LIST's id, then the noun, when there is none; two of a noun said), GIVE it to the recipient; the payment said; the journal read again.
- A search: the area's rooms by title; in each KNEEL and SEARCH (each one's roundtime waited) until the find, SEARCHES_PER_ROOM at most; GET the find, STAND, the walk back to the giver, GIVE; the journal read again.

What stops it
- The giver's cooldown (ten minutes between asks, kept per giver: an ask inside it is not sent, the minutes left are said), an offer of a kind the profile declines, a recipient the table does not know, a walk that ends short — each said. A shop shut for the night is waited for: the door tried each game hour (fifteen real minutes), eight times at most. A walk that ends short otherwise: ;task again from there carries on.
- Delivery and searching are run by the script; recovery, kill, boss, foraging and skinning are accepted and handed over, their wordings captured on the way (#505).

Elanthipedia: Task; the wordings captured on Crannach's delivery (docs/tasks.md).
"""

import math
import re
import time

from client.game import hands, items, travel
from client.game.act import ask, said, unknown
from client.game.loop import wants_stop
from client.game.mapdb import MapDB
from client.game.tasks import (
    CLOSED_FOR_THE_NIGHT,
    LAPSED,
    SEARCHES_PER_ROOM,
    accepted,
    area_rooms,
    classify_ask,
    clear,
    decide,
    declined,
    giver_rooms,
    load,
    note_ask,
    paid,
    parse_journal,
    parse_offer,
    person_name,
    recipient_rooms,
    record,
    search_outcome,
    wait_left,
)
from client.game import walker
from client.game.walker import walk


def parse_args(words):
    options = {"giver": "", "item": ""}
    for word in words or []:
        text = str(word).strip()
        key, sep, value = text.lower().partition("=")
        if sep and key == "item":
            options["item"] = value
        elif text and not options["giver"]:
            options["giver"] = text.lower()
    return options


now = time.time  # the cooldown's clock: wall time, kept across runs (#514)


def character(s):
    return getattr(getattr(s, "state", None), "name", None) or ""


def take_offer(s, giver, declines, name=""):
    """ASK the giver, unless its cooldown runs (#514); the offer judged
    and answered inside its window. The accepted offer's dict, or None
    (said why)."""
    left = wait_left(name, giver, now())
    if left:
        s.echo(
            f"task: {giver} can be asked again in {math.ceil(left / 60)} "
            "minute(s) — ten minutes between asks"
        )
        return None
    answer = ask(s, f"ask {giver} for task")
    verdict = classify_ask(answer)
    if verdict == "cooldown":
        note_ask(name, giver, now())  # its start unknown: a whole wait from here
        s.echo(f"task: {giver} says to wait — ten minutes between asks")
        return None
    if verdict != "offer":
        unknown(s, "task", "ASK FOR TASK", answer)
        return None
    note_ask(name, giver, now())  # accepted or declined, the wait starts
    offer = parse_offer(answer)
    offer["text"] = said(answer)
    if not decide(offer, declines):
        answer = ask(s, "decline task")
        verdict = (
            "declined"
            if declined(answer)
            else "declined (the giver said nothing known)"
        )
        s.echo(f"task: {describe(offer)} — in task_declines — {verdict}")
        return None
    answer = ask(s, "accept task")
    # The journal is the judge of the accept: a kind's thank-you line
    # may be uncaptured, and the words are only said.
    journal = parse_journal(ask(s, "task"))
    if journal is None or LAPSED in answer:
        unknown(s, "task", "ACCEPT TASK", answer)
        return None
    if not accepted(answer):
        s.echo(
            f"task: the accept's answer is new — {said(answer)!r} — please report it"
        )
    offer = {
        # The offer's words win; the journal fills what it lacks (an
        # uncaptured offer's kind, the giver's name).
        **{k: v for k, v in journal.items() if k != "kind"},
        **offer,
    }
    if offer.get("kind") == "unknown":
        offer["kind"] = journal.get("kind", "unknown")
    offer["accept_text"] = said(answer)
    s.echo(f"task: accepted — {describe(offer)}")
    return offer


def describe(task):
    if task.get("kind") == "delivery":
        return f"a delivery to {task.get('person')} in {task.get('place')}"
    if task.get("kind") == "recovery":
        return (
            f"a recovery of the {task.get('item')} from the {task.get('creature')} "
            f"{task.get('area')}"
        )
    if task.get("kind") == "searching":
        return (
            f"a search for the {task.get('item')} {task.get('area')} (kneel and search)"
        )
    if task.get("kind") == "unknown":
        return "a task of a kind not captured yet"
    return f"a {task.get('kind')} task"


def stow_the_item(s, task):
    """The item the accept put in a hand: its noun and id into the task's
    record, the item stowed for the walk."""
    tags = hands.tags(s)
    for tag in tags.values():
        if tag and tag.get("noun"):
            task["item"] = tag.get("noun")
            task["exist"] = tag.get("exist")
            hands.stow(s, tag["noun"], ask)
            return
    s.echo(
        "task: nothing landed in your hands — the item's noun is unknown (item=<noun>)"
    )


def held_item(s, noun, exist):
    """The hand's ref for the task's item: the recorded id when a hand
    holds it, else the noun's."""
    for tag in hands.tags(s).values():
        if tag and exist and str(tag.get("exist")) == str(exist):
            return f"#{exist}"
    return items.ref(s, noun) if noun else None


def take_item(s, task):
    """The task's item into a hand, its ref back (None said): by the id
    the accept recorded first, then INV LIST's id for the noun, the bare
    noun last — two baskets on the character and a GET by noun can take
    the wrong one (#513)."""
    noun = str(task.get("item") or "").split()[-1] if task.get("item") else ""
    exist = task.get("exist")
    held = held_item(s, noun, exist)
    if held:
        return held
    tries = [f"#{exist}"] if exist else []
    listed = items.listed_ref(s, noun) if noun else None
    if listed and listed not in tries:
        tries.append(listed)
    if noun:
        tries.append(f"my {noun}")
    answer = ""
    for what in tries:
        answer = ask(s, f"get {what}")
        held = held_item(s, noun, exist)
        if held:
            if what != f"#{exist}" and len(named(s, noun)) > 1:
                s.echo(
                    f"task: {len(named(s, noun))} {noun}s on you and no id for the "
                    f"task's — took {held}"
                )
            return held
    if not tries:
        s.echo("task: the item's noun is unknown — ;task item=<noun>")
    else:
        unknown(s, "task", f"GET {(noun or str(exist)).upper()}", answer)
    return None


def named(s, noun):
    """INV LIST's items whose name holds `noun` as a word."""
    pattern = re.compile(rf"\b{re.escape(noun.lower())}\b")
    possessions = getattr(getattr(s, "state", None), "possessions", None) or []
    return [i for i in possessions if pattern.search(str(i.get("name") or "").lower())]


GAME_HOUR = 900  # real seconds: the walk is tried again each game hour
NIGHT_HOURS = 8  # the knocks before giving up on the morning
KNOCK_POLL = 30  # seconds between looks at a typed return while waiting


def until_morning(s, go):
    """A walk the walker ended at a shop closed for the night (#512): the
    door tried again each game hour, NIGHT_HOURS at most — the wait said
    once. True once the walk arrives; False for any other failure, a
    typed return, or a night longer than the ceiling."""
    shop = walker.night_shut(s)
    if not shop:
        return False
    s.echo(
        f"task: {shop} is closed for the night — trying the door each game hour "
        f"(fifteen minutes), {NIGHT_HOURS} times at most"
    )
    for _ in range(NIGHT_HOURS):
        waited = 0
        while waited < GAME_HOUR:
            if wants_stop(s):
                return False
            s.sleep(KNOCK_POLL)
            waited += KNOCK_POLL
        if go():
            return True
        if not walker.night_shut(s):
            return False  # stopped short for another reason
    s.echo(f"task: {shop} stayed shut for {NIGHT_HOURS} game hours")
    return False


def deliver(s, task, mapdb, walk_fn):
    """Walk to the recipient and hand the item over; the payment said,
    the journal read, the record cleared when the task is done."""
    person = str(task.get("person") or "")
    rooms = recipient_rooms(mapdb, person)
    if not rooms:
        s.echo(f"task: the givers' table has no room for {person} — stopping")
        return False
    if wants_stop(s):
        return False

    def go():
        return travel.go(s, rooms, f"{person}'s room", db=mapdb, walk=walk_fn)

    if not go() and not until_morning(s, go):
        s.echo(f"task: stopped short of {person} — ;task again from here carries on")
        return False
    held = take_item(s, task)
    if not held:
        return False
    answer = ask(s, f"give {held} to {person_name(person)}")
    payment = paid(answer)
    if payment:
        count, currency = payment
        s.echo(f"task: delivered — {person} paid {count} {currency}")
    elif CLOSED_FOR_THE_NIGHT in answer:
        s.echo(f"task: {person}'s shop is shut for the night — ;task again at sunrise")
        return False
    else:
        unknown(s, "task", "GIVE", answer)
        return False
    journal = parse_journal(ask(s, "task"))
    if journal is None:
        s.echo("task: the journal is clear")
        clear(character(s))
    else:
        s.echo(f"task: the journal still holds {describe(journal)}")
    return True


def search_for(s, task, mapdb, walk_fn):
    """KNEEL and SEARCH the area's rooms until the item lies at the feet,
    then GET it and STAND: True with the item in hand."""
    area = str(task.get("area") or "")
    rooms = area_rooms(mapdb, area)
    if not rooms:
        s.echo(f"task: the map has no room for {area!r} — stopping")
        return False
    noun = str(task.get("item") or "").split()[-1] if task.get("item") else ""
    for room in sorted(rooms):
        if wants_stop(s):
            return False
        if not travel.go(s, {room}, f"{area} ({room})", db=mapdb, walk=walk_fn):
            s.echo(f"task: could not reach room {room} of {area} — trying the next")
            continue
        ask(s, "kneel")
        for number in range(1, SEARCHES_PER_ROOM + 1):
            if wants_stop(s):
                ask(s, "stand")
                return False
            s.waitrt()
            answer = ask(s, "search")
            outcome = search_outcome(answer)
            if outcome == "found":
                s.echo(f"task: found — {said(answer)} (search {number} in room {room})")
                s.waitrt()
                got = ask(s, f"get {noun}" if noun else "get item")
                ask(s, "stand")
                if not items.ref(s, noun):
                    unknown(s, "task", "GET", got)
                    return False
                return True
            if outcome == "wrong area":
                s.echo(f"task: nothing of interest in room {room} — the next")
                break
            if outcome != "miss":
                unknown(s, "task", "SEARCH", answer)
                ask(s, "stand")
                return False
        ask(s, "stand")
    s.echo(f"task: nothing found in {len(rooms)} room(s) of {area} — stopping")
    return False


def hand_in(s, task, mapdb, walk_fn):
    """Walk the find back to the giver and GIVE it; the giver's answer
    said, the journal the judge of the end."""
    giver = str(task.get("giver") or "")
    rooms = giver_rooms(mapdb, giver)
    if not rooms:
        s.echo(
            f"task: the givers' table has no room for {giver} — the find is on you; stopping"
        )
        return False
    noun = str(task.get("item") or "").split()[-1]
    held = items.ref(s, noun)
    if held:
        hands.stow(s, noun, ask)
    if not travel.go(s, rooms, f"{giver}'s room", db=mapdb, walk=walk_fn):
        s.echo(f"task: stopped short of {giver} — ;task again from here carries on")
        return False
    held = take_item(s, task)
    if not held:
        return False
    answer = ask(s, f"give {held} to {giver}")
    payment = paid(answer)
    if payment:
        s.echo(f"task: handed in — {giver} paid {payment[0]} {payment[1]}")
    else:
        s.echo(f"task: handed in — {giver} said {said(answer)!r}")
    journal = parse_journal(ask(s, "task"))
    if journal is None:
        s.echo("task: the journal is clear")
        clear(character(s))
        return True
    s.echo(f"task: the journal still holds {describe(journal)}")
    return False


def run_search(s, task, mapdb, walk_fn):
    noun = str(task.get("item") or "").split()[-1] if task.get("item") else ""
    if noun and items.ref(s, noun) or (noun and items.listed_ref(s, noun)):
        s.echo(f"task: the {noun} is already on you — handing it in")
        return hand_in(s, task, mapdb, walk_fn)
    if not search_for(s, task, mapdb, walk_fn):
        return False
    return hand_in(s, task, mapdb, walk_fn)


def run(s, options, profile, mapdb, walk_fn=walk):
    declines = list(profile.get("task_declines") or [])
    name = character(s)
    task = parse_journal(ask(s, "task"))
    if task is not None:
        if task.get("kind") not in ("delivery", "searching"):
            s.echo(
                f"task: the journal holds {describe(task)} — beyond the script, yours from here"
            )
            return
        kept = load(name) or {}
        task = {**kept, **task}
        if options["item"]:
            task["item"] = options["item"]
        if not task.get("item"):
            # The accept's item is still in a hand (an offer read as
            # unknown, a stop before the stow): take its noun from there.
            for tag in hands.tags(s).values():
                if tag and tag.get("noun"):
                    task["item"], task["exist"] = tag["noun"], tag.get("exist")
                    break
        s.echo(f"task: carrying on {describe(task)}")
        record(name, task)
        if task["kind"] == "searching":
            run_search(s, task, mapdb, walk_fn)
        else:
            deliver(s, task, mapdb, walk_fn)
        return
    if not options["giver"]:
        s.echo("task: no task in hand — ;task <giver> asks one")
        return
    offer = take_offer(s, options["giver"], declines, name)
    if offer is None:
        return
    task = {"giver": options["giver"], **offer}
    if offer["kind"] == "searching":
        record(name, task)
        run_search(s, task, mapdb, walk_fn)
        return
    if offer["kind"] != "delivery":
        record(name, task)
        s.echo(
            f"task: {describe(task)} is beyond the script — yours from here; "
            f"the offer: {task.get('text')!r}; the accept: {task.get('accept_text')!r}"
        )
        return
    if offer["kind"] == "delivery":
        stow_the_item(s, task)
        if options["item"]:
            task["item"] = options["item"]
        record(name, task)
        deliver(s, task, mapdb, walk_fn)


def main(s):
    from client.game.profile import load_profile

    profile = load_profile(character(s))
    run(s, parse_args(s.args), profile, MapDB.load())
