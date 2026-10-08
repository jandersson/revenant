"""What each opened box held, told to the creature and ground that
dropped it (#423): by the box's item id when ;hunt logged its pickup,
else by the batch of boxes found since the last ;boxes run, else
unknown; and the copper per box read back per ground."""

import sqlite3
from types import SimpleNamespace

from client.game import boxlog, lootlog

ME = SimpleNamespace(state=SimpleNamespace(name="Lanival", room_uid=1))
# Captured 2026-09-26 and 2026-10-02 (test_lootlog.py, the scouts' box).
GOBLIN_BOX = (
    "You search the scavenger goblin.\nThe goblin was carrying a poorly made iron box!"
)
SCOUT_BOX = (
    "You search the S'lai scout.\nThe scout was carrying a salt-stained copper box!"
)


def at(clock):
    return f"2026-10-02T{clock}:00+00:00"


def found(path, answer, ground, clock):
    """A search's loot row at a given time (the batch reads times)."""
    with sqlite3.connect(str(path)) as connection:
        lootlog.ensure_schema(connection)
        lootlog.record(
            connection,
            logged_at=at(clock),
            character_name="Lanival",
            ground=ground,
            **lootlog.parse(answer),
        )


def contents(path):
    with sqlite3.connect(str(path)) as connection:
        return connection.execute(
            "SELECT box_id, trap, lock, coins, currency, items, trashed,"
            " ground, creature, source FROM box_contents ORDER BY seq"
        ).fetchall()


def test_an_attempt_is_a_row_with_its_reading_outcome_and_the_rank_at_the_time(
    tmp_path,
):
    # #493: a ground's boxes judged by the attempts that failed too.
    db = tmp_path / "history.db"
    seq = boxlog.log_attempt(
        ME,
        path=db,
        run_started=at("21:00"),
        box_id="139883771",
        noun="box",
        verb="disarm",
        reading=11,
        outcome="retry",
        lockpick="ordinary",
        rank=52,
        mindstate=17,
        seconds=4.2,
    )
    assert seq == 1
    boxlog.log_attempt(ME, path=db, noun="box", verb="open", outcome=None, seconds=1.0)
    with sqlite3.connect(str(db)) as connection:
        rows = connection.execute(
            "SELECT character_name, box_id, noun, verb, reading, outcome, lockpick,"
            " rank, mindstate, seconds, run_started FROM box_attempts ORDER BY seq"
        ).fetchall()
    assert rows[0] == (
        "Lanival",
        "139883771",
        "box",
        "disarm",
        11,
        "retry",
        "ordinary",
        52,
        17,
        4.2,
        at("21:00"),
    )
    name, box_id, noun, verb, reading, outcome, lockpick, rank, mind, secs, run = rows[
        1
    ]
    assert (box_id, verb, reading, outcome, lockpick, rank) == (
        None,
        "open",
        None,
        "unknown",
        "",
        None,
    )
    assert run  # a run not named is the attempt's own time


def test_a_box_is_told_to_its_creature_by_the_id_logged_at_pickup(tmp_path):
    path = tmp_path / "history.db"
    seq = lootlog.log(ME, SCOUT_BOX, "scouts", path=path)
    boxlog.log_drop(
        ME,
        path=path,
        box_id=139883771,
        noun="box",
        description="a salt-stained copper box",
        creature="s'lai scout",
        ground="scouts",
        room=1,
        loot_seq=seq,
    )
    origin = boxlog.log_opened(
        ME,
        path=path,
        run_started=boxlog.now(),
        box_id="139883771",
        noun="box",
        trap=4,
        lock=3,
        coins=1270,
        currency="Kronars",
        items=["a small blue quartz"],
        trashed=["a tiny bronze bar"],
    )
    assert origin == {
        "ground": "scouts",
        "creature": "s'lai scout",
        "source": "id",
        "drop_seq": 1,
    }
    assert contents(path) == [
        (
            "139883771",
            4,
            3,
            1270,
            "Kronars",
            "a small blue quartz",
            "a tiny bronze bar",
            "scouts",
            "s'lai scout",
            "id",
        )
    ]


def test_a_box_without_an_id_is_told_to_the_ground_of_the_batch(tmp_path):
    # Picked up before the parser kept the id, or across a relog: the
    # boxes found since the last ;boxes run were all at the goblins.
    path = tmp_path / "history.db"
    found(path, GOBLIN_BOX, "goblins", "10:00")
    found(path, GOBLIN_BOX, "goblins", "10:05")
    origin = boxlog.log_opened(
        ME, path=path, run_started=at("11:00"), box_id=None, noun="box", coins=90
    )
    assert origin["ground"] == "goblins"
    assert origin["creature"] == "scavenger goblin"
    assert origin["source"] == "batch"


def test_a_batch_from_two_grounds_leaves_the_box_unknown(tmp_path):
    path = tmp_path / "history.db"
    found(path, GOBLIN_BOX, "goblins", "10:00")
    found(path, SCOUT_BOX, "scouts", "10:30")
    origin = boxlog.log_opened(
        ME, path=path, run_started=at("11:00"), box_id="5", noun="box"
    )
    assert origin == {"ground": "", "creature": "", "source": "", "drop_seq": None}


def test_the_batch_starts_after_the_previous_run(tmp_path):
    # The scouts' box was opened by an earlier run; the goblins' box,
    # found since, is all the next run's batch holds.
    path = tmp_path / "history.db"
    found(path, SCOUT_BOX, "scouts", "09:00")
    boxlog.log_opened(
        ME, path=path, run_started=at("09:30"), opened_at=at("09:35"), noun="box"
    )
    found(path, GOBLIN_BOX, "goblins", "10:00")
    origin = boxlog.log_opened(ME, path=path, run_started=at("11:00"), noun="box")
    assert origin["ground"] == "goblins" and origin["source"] == "batch"


def test_copper_per_box_reads_back_per_ground(tmp_path):
    path = tmp_path / "history.db"
    found(path, GOBLIN_BOX, "Goblins", "10:00")
    for coins in (100, 300):
        boxlog.log_opened(
            ME, path=path, run_started=at("11:00"), noun="box", coins=coins
        )
    assert boxlog.measured("Lanival", path=path) == {
        "goblins": {"opened": 2, "coins": 400}
    }
    assert boxlog.measured("Sable", path=path) == {}


def test_a_boxs_coins_are_kept_per_currency_and_measured_in_kronars(tmp_path):
    # The vineyard's casket, 2026-10-02 (#425): 8 copper Kronars, 6
    # bronze Dokoras and 6 silver Kronars — 608 copper Kronars and 60
    # copper Dokoras, worth 608 + 83 copper Kronars (Elanthipedia's
    # Currency table: a Dokora is 1.3858 Kronars).
    path = tmp_path / "history.db"
    found(path, GOBLIN_BOX, "vineyard", "10:00")
    boxlog.log_opened(
        ME,
        path=path,
        run_started=at("11:00"),
        noun="casket",
        kronars=608,
        lirums=0,
        dokoras=60,
    )
    with sqlite3.connect(str(path)) as connection:
        row = connection.execute(
            "SELECT kronars, lirums, dokoras, coins, currency FROM box_contents"
        ).fetchone()
    assert row == (608, 0, 60, 691, "Kronars")
    # A row from before #425 is read in its one currency's worth.
    boxlog.log_opened(
        ME,
        path=path,
        run_started=at("11:00"),
        noun="caddy",
        coins=100,
        currency="Lirums",
    )
    assert boxlog.measured("Lanival", path=path) == {
        "vineyard": {"opened": 2, "coins": 691 + 125}
    }


def test_a_table_from_before_the_currencies_grows_their_columns(tmp_path):
    path = tmp_path / "history.db"
    old = boxlog.CONTENTS_SCHEMA.replace(
        ",\n    kronars INTEGER,\n    lirums INTEGER,\n    dokoras INTEGER", ""
    )
    assert "kronars" not in old
    with sqlite3.connect(str(path)) as connection:
        connection.execute(old)
    boxlog.log_opened(ME, path=path, run_started=at("11:00"), noun="box", kronars=5)
    with sqlite3.connect(str(path)) as connection:
        assert connection.execute(
            "SELECT kronars, coins FROM box_contents"
        ).fetchall() == [(5, 5)]


def test_no_database_measures_nothing_and_a_failed_write_never_raises(tmp_path):
    path = tmp_path / "history.db"
    assert boxlog.measured("Lanival", path=path) == {}
    assert not path.exists()
    bad = tmp_path / "no-such-dir" / "history.db"
    assert boxlog.log_drop(ME, path=bad, noun="box") is None
    assert boxlog.log_opened(ME, path=bad, noun="box") is None
