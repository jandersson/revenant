"""How ;task's log keeps what the givers offer — these tests are the
manual. One `tasks` row per offer; the end fills the pay, the time, and
a search's room and count; `summary` groups them per giver and kind
for ;task history."""

from client.game import tasklog

RECOVERY = {
    "kind": "recovery",
    "item": "pearl ring",
    "creature": "poloh'izh",
    "area": "near Hara'jaal, Glaren Kweld",
}
SEARCH = {
    "kind": "searching",
    "item": "worn gauntlet",
    "area": "near Grassland Road, Meadow",
}


def test_offers_and_their_ends_read_back_per_giver_and_kind(tmp_path):
    # Cormyn, 2026-10-11: two recoveries from the same poloh'izh, a
    # search found on the 26th SEARCH in room 1454, one declined.
    path = tmp_path / "history.db"
    first = tasklog.log_offer("Lanival", "Cormyn", RECOVERY, True, path=path)
    tasklog.log_end(
        first, path=path, done_at=tasklog.now(), paid=397, currency="Kronars"
    )
    second = tasklog.log_offer("Lanival", "Cormyn", RECOVERY, True, path=path)
    tasklog.log_end(
        second, path=path, done_at=tasklog.now(), paid=316, currency="Kronars"
    )
    search = tasklog.log_offer("Lanival", "cormyn", SEARCH, True, path=path)
    tasklog.log_end(search, path=path, room=1454, searches=26)
    tasklog.log_offer("Lanival", "Cormyn", SEARCH, False, path=path)
    tasklog.log_end(None, path=path, paid=1)  # a task from before the log: nothing

    groups = {g["kind"]: g for g in tasklog.summary("Lanival", path=path)}
    recovery = groups["recovery"]
    assert (recovery["offers"], recovery["accepted"], recovery["done"]) == (2, 2, 2)
    assert tasklog.describe(recovery) == (
        "cormyn recovery: 2 offered, 2 taken, 2 done — poloh'izh near Hara'jaal,"
        " Glaren Kweld x2 — paid 316-397 Kronars — 0 min median"
    )
    search_group = groups["searching"]
    assert (search_group["offers"], search_group["accepted"], search_group["done"]) == (
        2,
        1,
        0,
    )
    assert tasklog.summary("Sable", path=path) == []


# Game-log lines as the logs of 2026-10-09 to 10-11 carry them: the
# server's prompt stamps between, the tags left in.
GAME_LOG = [
    '<prompt time="1791651000">&gt;</prompt>',
    'Cormyn says, "I do have a small favor to ask.  A friend of mine recently lost'
    " a very precious tabard.  He lost it in the area where the poloh'izh make"
    " their home near Hara'jaal, Glaren Kweld.  If you could recover that for him"
    ' I would greatly appreciate it."',
    "[You may accept by typing ACCEPT TASK, or decline by typing DECLINE TASK.  You"
    " have 30 seconds to decide.]",
    'Cormyn says, "Very well, I guess you do not wish to help me."',
    '<prompt time="1791651600">&gt;</prompt>',
    "Cormyn says, \"I do have a small task I'd like for you to perform.  I have a"
    " small item that needs to be taken to Saeru in Throne City.  Would you be"
    ' willing to do that for me?"',
    'Cormyn says, "Here is the item, please get it to Saeru as soon as possible."',
    "Cormyn wants you to deliver a package to Saeru in Throne City.",
    '<prompt time="1791655200">&gt;</prompt>',
    "The sales clerk hands you 50 Kronars.",
    '<prompt time="1791658800">&gt;</prompt>',
    "Saeru hands you 314 Lirums.",
]


def test_a_game_logs_offers_read_with_their_answers_and_pay():
    offers = tasklog.scan(GAME_LOG)
    assert [(o["giver"], o["offer"]["kind"], o["accepted"]) for o in offers] == [
        ("Cormyn", "recovery", False),
        ("Cormyn", "delivery", True),
    ]
    taken = offers[1]
    assert (taken["paid"], taken["currency"]) == (314, "Lirums")  # not the clerk's
    assert taken["offered_at"] == "2026-10-10T17:00:00+00:00"
    assert taken["done_at"] == "2026-10-10T19:00:00+00:00"
    assert "done_at" not in offers[0]


def test_the_journals_fuller_name_wins():
    # Cormyn's mirror, 2026-10-10: "a very precious mirror", the journal's
    # "small hand mirror".
    lines = [
        'Cormyn says, "I do have a small favor to ask.  A friend of mine recently'
        " lost a very precious mirror.  She lost it in the area where the poloh'izh"
        " make their home near Hara'jaal, Glaren Kweld.  If you could recover that"
        ' for her I would greatly appreciate it."',
        "Cormyn says, \"Thank you so much.  Remember, you're looking for a small"
        ' hand mirror."',
        "Cormyn wants you to recover a small hand mirror from poloh'izh near"
        " Hara'jaal, Glaren Kweld.",
    ]
    assert tasklog.scan(lines)[0]["offer"]["item"] == "small hand mirror"
