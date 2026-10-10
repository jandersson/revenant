"""Run an NPC's task for the coin:  ;task <giver>
    ;task <giver>        ask the giver (a noun the room knows: cormyn) for a task; a kind the profile's task_kinds allows is accepted, the rest declined
    ;task                carry on the task in hand (the journal's): a delivery walks to the recipient and hands the item over
    ;task item=<noun>    ... naming the item when the record of the accept is gone (a basket)
    ;task return         typed while it runs: finish the step in hand and stop

What it does
- TASK first: a task already in hand is carried on, no ask.
- The offer has thirty seconds: it is parsed and accepted or declined at once, by kind.
- A delivery: the item lands in a hand and is stowed; the walk to the recipient's room (the givers' table in client/game/tasks.py); GET the item, GIVE it to the recipient; the payment said; the journal read again.

What stops it
- The giver's cooldown (ten minutes between asks), an offer of a kind the profile declines, a recipient the table does not know, a walk that ends short — each said. A walk ends short at a shop shut for the night (sunrise is a game hour, fifteen real minutes) and at a ride the walker lacks (the Throne City barge, #506): ;task again from there carries on.
- Only delivery is built; recovery, kill, boss, foraging, skinning and searching are declined until their wordings are captured (#505).

Elanthipedia: Task; the wordings captured on Crannach's delivery (docs/tasks.md).
"""

from client.game import hands, items, travel
from client.game.act import ask, unknown
from client.game.loop import wants_stop
from client.game.mapdb import MapDB
from client.game.tasks import (
    CLOSED_FOR_THE_NIGHT,
    LAPSED,
    accepted,
    classify_ask,
    clear,
    decide,
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


def take_offer(s, giver, kinds):
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
    if not decide(offer, kinds):
        ask(s, "decline task")
        s.echo(
            f"task: a {offer['kind']} task — not in task_kinds "
            f"({', '.join(kinds) or 'none'}) — declined"
        )
        return None
    answer = ask(s, "accept task")
    if LAPSED in answer or not accepted(answer):
        unknown(s, "task", "ACCEPT TASK", answer)
        return None
    s.echo(f"task: accepted — {describe(offer)}")
    return offer


def describe(task):
    if task.get("kind") == "delivery":
        return f"a delivery to {task.get('person')} in {task.get('place')}"
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
    kinds = list(profile.get("task_kinds") or ["delivery"])
    name = character(s)
    task = parse_journal(ask(s, "task"))
    if task is not None:
        if task.get("kind") != "delivery":
            s.echo(
                "task: the journal holds a task of a kind ;task cannot run yet — stopping"
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
    offer = take_offer(s, options["giver"], kinds)
    if offer is None:
        return
    task = {"giver": options["giver"], **offer}
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
