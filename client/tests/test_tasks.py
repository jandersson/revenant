"""The task model (#505): the givers' wordings as captured on
2026-10-09/10 (docs/tasks.md), read into offers, journal entries and
payments."""

from client.game import tasks
from client.game.mapdb import MapDB

DELIVERY_OFFER = (
    "Cormyn says, \"I do have a small task I'd like for you to perform.  I have a "
    "small item that needs to be taken to Saeru in Throne City.  Would you be "
    'willing to do that for me?"\n'
    "[You may accept by typing ACCEPT TASK, or decline by typing DECLINE TASK.  "
    "You have 30 seconds to decide.]\n"
)
RECOVERY_OFFER = (
    'Cormyn says, "I do have a small favor to ask.  A friend of mine recently lost '
    "a very precious tabard.  He lost it in the area where the poloh'izh make their "
    "home near Hara'jaal, Glaren Kweld.  If you could recover that for him I would "
    "greatly appreciate it.\n"
    "[You may accept by typing ACCEPT TASK, or decline by typing DECLINE TASK.  "
    "You have 30 seconds to decide.]\n"
)
SEARCHING_OFFER = (
    'Saeru says, "I do have a small favor to ask.  A friend of mine recently lost '
    "a very precious locket.  She lost it in the area near The Crossing, Gildleaf "
    "Circle.  If you could recover that for her I would greatly appreciate it.\n"
    "[You may accept by typing ACCEPT TASK, or decline by typing DECLINE TASK.  "
    "You have 30 seconds to decide.]\n"
)
SEARCHING_ACCEPTED = (
    "Saeru says, \"Thank you so much.  Remember, you're looking for a glaes locket.  "
    "Oh, and you might find it better if you're kneeling.\"\n"
)
SEARCHING_JOURNAL = (
    "You look in your task journal and see the following entry:\n"
    "Saeru wants you to recover a glaes locket near The Crossing, Gildleaf Circle.\n"
    "You have performed the following tasks:\n"
    "1 delivery tasks and 1 searching tasks\n"
)
LAPSED = 'Cormyn says, "Very well, I guess you do not wish to help me."\n'
COOLDOWN = 'Cormyn says, "I am sorry, you must wait before I can give you a task."\n'
ACCEPTED = (
    'Cormyn says, "Here is the item, please get it to Saeru as soon as possible."\n'
)
JOURNAL = (
    "You look in your task journal and see the following entry:\n"
    "Cormyn wants you to deliver a package to Saeru in Throne City.\n"
    "You have performed the following tasks:\n"
    "1 searching tasks\n"
)
JOURNAL_CLEAR = (
    "You are not currently on a task.\n"
    "You have performed the following tasks:\n"
    "1 delivery tasks and 1 searching tasks\n"
)
PAID = (
    'Saeru says, "Thank you very much, Lanival.  I have a few things here for you, '
    'thank you so much for your help."\n'
    "Saeru hands you 314 Lirums.\n"
)


def test_an_ask_is_an_offer_a_cooldown_or_unknown():
    assert tasks.classify_ask(DELIVERY_OFFER) == "offer"
    assert tasks.classify_ask(RECOVERY_OFFER) == "offer"
    assert tasks.classify_ask(COOLDOWN) == "cooldown"
    assert tasks.classify_ask(LAPSED) == "unknown"
    assert tasks.classify_ask("") == "unknown"


def test_a_delivery_offer_names_the_person_and_the_place():
    assert tasks.parse_offer(DELIVERY_OFFER) == {
        "kind": "delivery",
        "person": "Saeru",
        "place": "Throne City",
    }


def test_a_delivery_to_a_titled_recipient_keeps_the_title_and_gives_to_the_name():
    # Saeru's third offer, 2026-10-10.
    offer = tasks.parse_offer(
        "Saeru says, \"I do have a small task I'd like for you to perform.  I have a "
        "small item that needs to be taken to the Ranger Guildleader Kalika in The "
        'Crossing.  Would you be willing to do that for me?"\n'
        + DELIVERY_OFFER.splitlines()[-1]
    )
    assert offer == {
        "kind": "delivery",
        "person": "Ranger Guildleader Kalika",
        "place": "The Crossing",
    }
    assert tasks.person_name(offer["person"]) == "Kalika"
    assert tasks.person_name("Saeru") == "Saeru"
    assert tasks.parse_journal(
        "You look in your task journal and see the following entry:\n"
        "Saeru wants you to deliver a package to the Ranger Guildleader Kalika in The Crossing.\n"
    ) == {
        "kind": "delivery",
        "giver": "Saeru",
        "person": "Ranger Guildleader Kalika",
        "place": "The Crossing",
    }
    db = MapDB(
        [{"id": 7900, "uid": [1], "title": ["[Ranger Guild, Main Hall]"], "wayto": {}}]
    )
    assert tasks.recipient_rooms(db, "Ranger Guildleader Kalika") == {7900}


def test_a_recovery_offer_names_the_item_the_creature_and_the_area():
    assert tasks.parse_offer(RECOVERY_OFFER) == {
        "kind": "recovery",
        "item": "tabard",
        "creature": "poloh'izh",
        "area": "near Hara'jaal, Glaren Kweld",
    }
    hammer = RECOVERY_OFFER.replace("tabard", "hammer")
    assert tasks.parse_offer(hammer)["item"] == "hammer"


def test_a_searching_offer_names_the_item_and_the_area_and_no_creature():
    # Saeru, 2026-10-10: the same loss, "She lost it in the area near ...".
    assert tasks.parse_offer(SEARCHING_OFFER) == {
        "kind": "searching",
        "item": "locket",
        "area": "near The Crossing, Gildleaf Circle",
    }
    assert tasks.accepted(SEARCHING_ACCEPTED) is True
    assert tasks.parse_journal(SEARCHING_JOURNAL) == {
        "kind": "searching",
        "giver": "Saeru",
        "item": "glaes locket",
        "area": "near The Crossing, Gildleaf Circle",
    }


def test_an_uncaptured_offer_is_unknown_and_still_accepted():
    offer = tasks.parse_offer(
        'Cormyn says, "Go and kill ten rats for me."\n'
        + DELIVERY_OFFER.splitlines()[-1]
    )
    assert offer == {"kind": "unknown"}
    # Every kind is accepted unless the profile declines it.
    assert tasks.decide(offer) is True
    assert tasks.decide({"kind": "recovery"}, ["Recovery", "kill"]) is False
    assert tasks.decide({"kind": "delivery"}, ["recovery"]) is True


def test_the_journal_reads_the_delivery_in_hand_and_the_clear_journal():
    assert tasks.parse_journal(JOURNAL) == {
        "kind": "delivery",
        "giver": "Cormyn",
        "person": "Saeru",
        "place": "Throne City",
    }
    assert tasks.parse_journal(JOURNAL_CLEAR) is None
    assert tasks.parse_journal("") is None
    assert tasks.parse_journal(
        "You look in your task journal and see the following entry:\nSomething new.\n"
    ) == {"kind": "unknown"}


def test_a_recoverys_journal_line_names_the_creature_and_the_area():
    # Cormyn, 2026-10-10 06:06, the fourth live run.
    assert tasks.parse_journal(
        "You look in your task journal and see the following entry:\n"
        "Cormyn wants you to recover a worn gauntlet from poloh'izh near Hara'jaal, Glaren Kweld.\n"
    ) == {
        "kind": "recovery",
        "giver": "Cormyn",
        "item": "worn gauntlet",
        "creature": "poloh'izh",
        "area": "near Hara'jaal, Glaren Kweld",
    }
    # Its accept answers like a search's: the item named, no kneeling.
    assert tasks.accepted(
        'Cormyn says, "Thank you so much.  Remember, you\'re looking for a worn gauntlet."\n'
    )


def test_the_accept_and_the_payment_are_read():
    assert tasks.accepted(ACCEPTED) is True
    assert tasks.accepted(LAPSED) is False
    # The decline's answer is the lapse's line (2026-10-10, ;task's first run).
    assert tasks.declined(LAPSED) is True
    assert tasks.declined(ACCEPTED) is False
    assert tasks.paid(PAID) == (314, "Lirums")
    assert tasks.paid(ACCEPTED) is None


def test_a_searchs_area_names_its_rooms_and_the_answers_are_classed():
    db = MapDB(
        [
            {
                "id": 807,
                "uid": [1],
                "title": ["[The Crossing, Gildleaf Circle]"],
                "wayto": {},
            },
            {
                "id": 808,
                "uid": [2],
                "title": ["[The Crossing, Gildleaf Circle]"],
                "wayto": {},
            },
            {
                "id": 1,
                "uid": [3],
                "title": ["[The Crossing, Herald Street]"],
                "wayto": {},
            },
        ]
    )
    assert tasks.area_rooms(db, "near The Crossing, Gildleaf Circle") == {807, 808}
    assert tasks.area_rooms(db, "Gildleaf Circle") == {807, 808}
    assert tasks.area_rooms(db, "near Nowhere, Nothing Street") == set()
    # Captured 2026-10-10: the miss with its roundtime, the find at the feet.
    assert (
        tasks.search_outcome(
            "You search for a bit, but do not find the item you are looking for.\nRoundtime: 12 sec.\n"
        )
        == "miss"
    )
    assert (
        tasks.search_outcome(
            "You find a glaes locket lying on the ground!\nRoundtime: 10 sec.\n"
        )
        == "found"
    )
    assert (
        tasks.search_outcome("You don't find anything of interest here.\n")
        == "wrong area"
    )
    assert tasks.search_outcome("") == "unknown"


def test_the_recipients_room_comes_from_the_givers_table():
    db = MapDB(
        [
            {
                "id": 10021,
                "uid": [1],
                "title": ["[Seven Star Exchange and Pawn]"],
                "wayto": {},
            },
            {
                "id": 8261,
                "uid": [2],
                "title": ["[Cormyn's House of Heirlooms]"],
                "wayto": {},
            },
        ]
    )
    assert tasks.recipient_rooms(db, "Saeru") == {10021}
    assert tasks.recipient_rooms(db, "saeru") == {10021}
    assert tasks.recipient_rooms(db, "Nobody") == set()


def test_the_record_round_trips_and_clears(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    assert tasks.load("Lanival") is None
    tasks.record("Lanival", {"kind": "delivery", "person": "Saeru", "item": "basket"})
    assert tasks.load("Lanival")["item"] == "basket"
    tasks.clear("Lanival")
    assert tasks.load("Lanival") is None
    tasks.clear("Lanival")  # twice is harmless


def test_a_givers_cooldown_runs_ten_minutes_from_the_ask(monkeypatch, tmp_path):
    # #514: "a 10 minute waiting period before you can ask again"
    # (Elanthipedia: Task), kept per giver in wall time.
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    assert tasks.wait_left("Lanival", "cormyn", 1000.0) == 0
    tasks.note_ask("Lanival", "Cormyn", 1000.0)
    assert tasks.wait_left("Lanival", "cormyn", 1060.0) == 540.0
    assert tasks.wait_left("Lanival", "saeru", 1060.0) == 0  # another giver
    assert tasks.wait_left("Lanival", "cormyn", 1600.0) == 0
