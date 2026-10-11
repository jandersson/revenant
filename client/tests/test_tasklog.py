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
