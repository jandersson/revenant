"""Run an NPC's task for the coin:  ;task <giver>
    ;task <giver>        ask the giver (a noun the room knows: cormyn) for a task and accept it; a kind the profile's task_declines names is declined
    ;task                carry on the task in hand (the journal's): a delivery walks to the recipient and hands the item over
    ;task item=<noun>    ... naming the item when the record of the accept is gone (a basket)
    ;task return         typed while it runs: finish the step in hand and stop

What it does
- TASK first: a task already in hand is carried on, no ask.
- The offer has thirty seconds: it is accepted at once (a kind in task_declines is declined). A delivery is run; any other kind is yours from here — the offer said, the task recorded.
- A delivery: the item lands in a hand and is stowed; the walk to the recipient's room (the givers' table in client/game/tasks.py); GET the item, GIVE it to the recipient; the payment said; the journal read again.

What stops it
- The giver's cooldown (ten minutes between asks), an offer of a kind the profile declines, a recipient the table does not know, a walk that ends short — each said. A walk ends short at a shop shut for the night (sunrise is a game hour, fifteen real minutes) and at a ride the walker lacks (the Throne City barge, #506): ;task again from there carries on.
- Only delivery is run by the script; recovery, kill, boss, foraging, skinning and searching are accepted and handed over, their wordings captured on the way (#505).

Elanthipedia: Task; the wordings captured on Crannach's delivery (docs/tasks.md).
"""

from client.game import hands, items, travel
from client.game.act import ask, said, unknown
from client.game.loop import wants_stop
from client.game.mapdb import MapDB
from client.game.tasks import (
    CLOSED_FOR_THE_NIGHT,
    LAPSED,
    accepted,
    classify_ask,
    clear,
    decide,
    declined,
    load,
    paid,
    parse_journal,
    parse_offer,
    recipient_rooms,
    record,
)
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


def character(s):
    return getattr(getattr(s, "state", None), "name", None) or ""


def take_offer(s, giver, declines):
    """ASK the giver; the offer judged and answered inside its window.
    The accepted offer's dict, or None (said why)."""
    answer = ask(s, f"ask {giver} for task")
    verdict = classify_ask(answer)
    if verdict == "cooldown":
        s.echo(f"task: {giver} says to wait — ten minutes between asks")
        return None
    if verdict != "offer":
        unknown(s, "task", "ASK FOR TASK", answer)
        return None
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
    if not travel.go(s, rooms, f"{person}'s room", db=mapdb, walk=walk_fn):
        s.echo(
            f"task: stopped short of {person} — a shop shut for the night opens at "
            "sunrise (a game hour, fifteen real minutes), and a ride the walker lacks "
            "is #506; ;task again from here carries on"
        )
        return False
    noun = str(task.get("item") or "")
    if not noun:
        s.echo("task: the item's noun is unknown — ;task item=<noun>")
        return False
    held = items.ref(s, noun)
    if not held:
        answer = ask(s, f"get my {noun}")
        held = items.ref(s, noun)
        if not held:
            unknown(s, "task", f"GET {noun.upper()}", answer)
            return False
    answer = ask(s, f"give {held} to {person}")
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


def run(s, options, profile, mapdb, walk_fn=walk):
    declines = list(profile.get("task_declines") or [])
    name = character(s)
    task = parse_journal(ask(s, "task"))
    if task is not None:
        if task.get("kind") != "delivery":
            s.echo(
                f"task: the journal holds {describe(task)} — beyond the script, yours from here"
            )
            return
        kept = load(name) or {}
        task = {**kept, **task}
        if options["item"]:
            task["item"] = options["item"]
        s.echo(f"task: carrying on {describe(task)}")
        record(name, task)
        deliver(s, task, mapdb, walk_fn)
        return
    if not options["giver"]:
        s.echo("task: no task in hand — ;task <giver> asks one")
        return
    offer = take_offer(s, options["giver"], declines)
    if offer is None:
        return
    task = {"giver": options["giver"], **offer}
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
