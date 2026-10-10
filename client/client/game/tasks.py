"""The task system (#505): a giver's offer read, judged and recorded, the
journal read, the recipient's payment read — ;task's model, Qt-free.

Captured 2026-10-09/10 on a delivery from Cormyn (the Crossing) to
Saeru (Throne City), docs/tasks.md. The offer ends with OFFER_PROMPT and
a thirty-second window; silence past it is LAPSED; an ask inside the
ten-minute cooldown is COOLDOWN. ACCEPT TASK on a delivery hands the
item over ("Here is the item, please get it to Saeru as soon as
possible."). TASK reads the journal: the task in hand as JOURNAL_DELIVERY,
or NO_TASK. The recipient thanks you by name and "hands you 314 Lirums".
An item recovery's offer names the item, the creature and the area; the
kill, boss, foraging, skinning and searching offers are uncaptured and
parse as "unknown", which ;task declines. The record of the task in
hand (the item's noun and id, taken from the hand at the accept) lives
beside the training plans, so a run after the shop's night or a stop
carries on. Elanthipedia: Task (the kinds and the givers' table).
"""

import json
import re

OFFER_PROMPT = "[You may accept by typing ACCEPT TASK"
# The giver's one line for a refusal, whether the window lapsed or
# DECLINE TASK was sent (;task's first script run, 2026-10-10 04:33).
LAPSED = "I guess you do not wish to help me"
DECLINED = LAPSED
COOLDOWN = "you must wait before I can give you a task"
# The accept's answer by kind: a delivery hands the item over; a search
# names the item and hints at kneeling (2026-10-10, ;task's second run:
# "Thank you so much.  Remember, you're looking for a glaes locket.  Oh,
# and you might find it better if you're kneeling."). The script trusts
# the journal, not the words: ACCEPT is done when TASK shows the task.
ACCEPTED = ("Here is the item", "you're looking for")
NO_TASK = "You are not currently on a task."
JOURNAL_HEAD = "You look in your task journal"
CLOSED_FOR_THE_NIGHT = "closed for the night"
# A search (captured 2026-10-10 at Gildleaf Circle, docs/tasks.md): KNEEL,
# then SEARCH answers a miss with a roundtime of 8–14 s, the find with
# the item at the feet, and the wiki's wrong-area line elsewhere.
SEARCH_MISS = ("do not find the item",)
SEARCH_FOUND = ("lying on the ground",)
SEARCH_WRONG_AREA = ("anything of interest",)
SEARCHES_PER_ROOM = 30  # thirty-one found the locket in two rooms
WINDOW_SECONDS = 30

# The recipient is a name ("Saeru") or a title and a name ("the Ranger
# Guildleader Kalika", Saeru's third offer, 2026-10-10): the words before
# " in ", the article dropped; GIVE and the givers' table take the last.
_DELIVERY = re.compile(
    r"needs to be taken to (?:the )?(?P<person>[A-Z][\w' ]*?) in (?P<place>[^.?]+)[.?]"
)
_RECOVERY = re.compile(
    r"lost a very precious (?P<item>[\w' -]+?)\.\s+(?:He|She) lost it in the area "
    r"where the (?P<creature>[\w'-]+) make their home (?P<area>[^.]+)\."
)
# A search: the same loss, no creature — "She lost it in the area near The
# Crossing, Gildleaf Circle." (Saeru, 2026-10-10); KNEEL and SEARCH there.
_SEARCHING = re.compile(
    r"lost a very precious (?P<item>[\w' -]+?)\.\s+(?:He|She) lost it in the area "
    r"(?P<area>near [^.]+)\."
)
_JOURNAL_DELIVERY = re.compile(
    r"(?P<giver>[A-Z][\w']*) wants you to deliver a package to "
    r"(?:the )?(?P<person>[A-Z][\w' ]*?) in (?P<place>[^.]+)\."
)
# "Saeru wants you to recover a glaes locket near The Crossing, Gildleaf
# Circle." — a search's journal line; a recovery's (from a creature) is
# uncaptured and would read the same way without the creature.
_JOURNAL_SEARCHING = re.compile(
    r"(?P<giver>[A-Z][\w']*) wants you to recover (?:an? )?(?P<item>[\w' -]+?) "
    r"(?P<area>near [^.]+)\."
)
_PAID = re.compile(r"hands you (?P<count>[\d,]+) (?P<currency>[A-Z]\w+)")

# The task givers Elanthipedia lists, by the room title the map knows
# them under: a delivery goes to another giver, so the recipient's room
# is looked up here. The wandering ones have no room (;seek finds them).
GIVERS = {
    "Cormyn": "Cormyn's House of Heirlooms",
    "Kalika": "Ranger Guild, Main Hall",  # the Crossing's Ranger guildleader (map 7900)
    "Amfitro": "Viper's Nest",
    "Saeru": "Seven Star Exchange and Pawn",
    "Daralaendra": "Warehouse Office",
    "Fara": "Fara's Furs",
    "Ioun": "Ioun's Pawn",
    "Anthelorm": "Riverhaven, Gem",
    "Aelik": "Aelik's Pawn",
    "Chabalu": "Chabalu's Exotics",
    "Paedraig": "Paedraig's Pawn",
}


def classify_ask(answer):
    """ "offer", "cooldown" or "unknown" for the giver's answer to an ask."""
    text = str(answer or "")
    if OFFER_PROMPT in text:
        return "offer"
    if COOLDOWN in text:
        return "cooldown"
    return "unknown"


def parse_offer(answer):
    """The offer's shape: {"kind": "delivery", "person", "place"}, {"kind":
    "recovery", "item", "creature", "area"}, or {"kind": "unknown"} for a
    wording not captured yet; every value a plain string."""
    text = " ".join(str(answer or "").split())
    match = _DELIVERY.search(text)
    if match:
        return {
            "kind": "delivery",
            "person": match.group("person"),
            "place": match.group("place").strip(),
        }
    match = _RECOVERY.search(text)
    if match:
        return {
            "kind": "recovery",
            "item": match.group("item").strip(),
            "creature": match.group("creature"),
            "area": match.group("area").strip(),
        }
    match = _SEARCHING.search(text)
    if match:
        return {
            "kind": "searching",
            "item": match.group("item").strip(),
            "area": match.group("area").strip(),
        }
    return {"kind": "unknown"}


def parse_journal(answer):
    """The task in hand from TASK's answer: a delivery as {"kind", "giver",
    "person", "place"}; None when the journal says no task, or the kind is
    uncaptured ({"kind": "unknown"} then)."""
    text = " ".join(str(answer or "").split())
    if NO_TASK in text:
        return None
    match = _JOURNAL_DELIVERY.search(text)
    if match:
        return {
            "kind": "delivery",
            "giver": match.group("giver"),
            "person": match.group("person"),
            "place": match.group("place").strip(),
        }
    match = _JOURNAL_SEARCHING.search(text)
    if match:
        return {
            "kind": "searching",
            "giver": match.group("giver"),
            "item": match.group("item").strip(),
            "area": match.group("area").strip(),
        }
    if JOURNAL_HEAD in text:
        return {"kind": "unknown"}
    return None


def paid(answer):
    """(copper count as the game counts it, currency) from the recipient's
    "hands you 314 Lirums", or None."""
    match = _PAID.search(str(answer or ""))
    if not match:
        return None
    return int(match.group("count").replace(",", "")), match.group("currency")


def accepted(answer):
    return any(word in str(answer or "") for word in ACCEPTED)


def declined(answer):
    """True when the giver answered a DECLINE TASK (or a lapse) with his
    refusal line."""
    return DECLINED in str(answer or "")


def decide(offer, declines=()):
    """True unless the offer's kind is one the profile declines: the
    script accepts every offer so each kind's wording is met live, runs
    the kinds it can and hands the rest to the operator (the operator,
    2026-10-10: a script built to learn declines nothing by default)."""
    kinds = {str(kind).strip().lower() for kind in declines or ()}
    return str(offer.get("kind") or "").lower() not in kinds


def area_rooms(db, area):
    """The map rooms a search's area names: "near The Crossing, Gildleaf
    Circle" is the title's last part, "Gildleaf Circle", every room so
    titled; empty when the map has none."""
    text = str(area or "").strip()
    if text.lower().startswith("near "):
        text = text[5:]
    part = text.split(",")[-1].strip()
    return set(db.resolve(part)) if part else set()


def search_outcome(answer):
    """ "found", "miss", "wrong area" or "unknown" for a SEARCH's answer."""
    text = str(answer or "")
    if any(word in text for word in SEARCH_FOUND):
        return "found"
    if any(word in text for word in SEARCH_MISS):
        return "miss"
    if any(word in text for word in SEARCH_WRONG_AREA):
        return "wrong area"
    return "unknown"


def giver_rooms(db, giver):
    """The giver's room by the givers' table, as recipient_rooms."""
    return recipient_rooms(db, giver)


def person_name(person):
    """The name GIVE and the givers' table take from a recipient: the last
    word of "the Ranger Guildleader Kalika", "Saeru" as is."""
    words = str(person or "").split()
    return words[-1].strip(".,") if words else ""


def recipient_rooms(db, person):
    """The map rooms a delivery's recipient stands in, by the givers'
    table; empty when the person is not in it or the map lacks the room."""
    title = GIVERS.get(person_name(person).capitalize())
    if not title:
        return set()
    return set(db.resolve(title))


# --- the record of the task in hand -----------------------------------------


def record_path(name):
    from client.game.training import training_dir

    return training_dir() / f"{str(name).lower()}.task.json"


def record(name, task):
    """The task in hand written down (its kind, giver, person, place, the
    item's noun and id), so a later ;task carries it on."""
    path = record_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(task)), encoding="utf-8")


def load(name):
    """The recorded task, or None."""
    try:
        data = json.loads(record_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def clear(name):
    try:
        record_path(name).unlink()
    except OSError:
        pass
