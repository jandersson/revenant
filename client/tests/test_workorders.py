"""How work orders are ledgered — these tests are the manual. One row
per order handed in: the pay, the materials at catalog prices, the
coin spent while it was open; the totals and the per-item profit
;remedies ledger prints (2026-09-22)."""

from client.game import remedies, workorders


def test_a_remedy_costs_its_materials_at_the_catalog():
    # Blister cream: a stack of red flowers (343), a piece of nemoih
    # (250/25), a splash of water (62/10) and a coal nugget (31).
    cream = remedies.recipe("blister cream")
    assert workorders.material_cost(cream, "nugget") == 390
    assert workorders.material_cost(remedies.recipe("head salve"), "nugget") == 287
    # An unpriced catalyst or herb counts nothing rather than guessing.
    assert workorders.material_cost(cream, "") == 359
    assert workorders.material_cost(remedies.recipe("back salve"), "nugget") == 37


def test_rows_round_trip_with_extras_as_json(tmp_path):
    db = workorders.open_ledger(tmp_path / "h.db")
    seq = workorders.record(
        db,
        character_name="Lanival",
        discipline="remedies",
        level="easy",
        item="blister cream",
        stacks=2,
        quality="finely-crafted",
        earned=1144,
        cost=780,
        spent=748,
        crushes=26,
        rank_before=9,
        rank_after=10,
        minutes=14,
        crush_seconds=390,
        due=65,
    )
    assert seq == 1
    (row,) = workorders.rows(db, character="Lanival", discipline="remedies")
    assert row["item"] == "blister cream" and row["earned"] == 1144
    assert row["extra"] == '{"due": 65}' and row["crush_seconds"] == 390
    assert workorders.rows(db, character="Sable") == []


def test_an_older_table_grows_the_time_column_in_place(tmp_path):
    import sqlite3

    old = workorders.SCHEMA.replace("    crush_seconds INTEGER,\n", "")
    assert "crush_seconds" not in old
    connection = sqlite3.connect(str(tmp_path / "h.db"))
    connection.execute(old)
    connection.commit()
    connection.close()
    db = workorders.open_ledger(tmp_path / "h.db")
    workorders.record(
        db,
        character_name="Lanival",
        discipline="remedies",
        level="easy",
        item="blister cream",
        stacks=1,
        earned=572,
        cost=390,
        spent=0,
        crushes=7,
        crush_seconds=105,
    )
    assert workorders.rows(db)[0]["crush_seconds"] == 105


def test_the_ledger_totals_profit_and_cash_apart(tmp_path):
    db = workorders.open_ledger(tmp_path / "h.db")
    for earned, cost, spent, item in (
        (1144, 780, 748, "blister cream"),
        (1146, 780, 0, "blister cream"),
        (600, 287, 250, "head salve"),
    ):
        workorders.record(
            db,
            logged_at="2026-09-22T21:47:00+00:00",
            character_name="Lanival",
            discipline="remedies",
            level="easy",
            item=item,
            stacks=2 if item == "blister cream" else 1,
            earned=earned,
            cost=cost,
            spent=spent,
            crushes=10,
            crush_seconds=150,
            minutes=12,
            rank_before=9,
            rank_after=10,
        )
    entries = workorders.rows(db)
    assert workorders.totals(entries) == {
        "orders": 3,
        "earned": 2890,
        "cost": 1847,
        "spent": 998,
        "profit": 1043,
        "cash": 1892,
        "crushes": 30,
        "crush_seconds": 450,
        "minutes": 36,
    }
    lines = workorders.ledger_lines(entries, shown=1)
    assert lines[0] == (
        "3 order(s): 2,890 Kronars paid, 1,847 in materials, 1,043 profit; "
        "998 spent from the purse, 1,892 kept; 36 min, 15 s a crush"
    )
    assert lines[1] == (
        "blister cream (easy) x2, 4 stack(s): 1,145 pay, 780 cost, 365 profit an order, "
        "15 s a crush"
    )
    assert lines[2] == (
        "head salve (easy) x1, 1 stack(s): 600 pay, 287 cost, 313 profit an order, "
        "15 s a crush"
    )
    assert lines[3] == (
        "2026-09-22 21:47 head salve x1 (easy): paid 600, cost 287, spent 250, "
        "10 crush(es) (150 s crushing, 15 s each), rank 9->10, 12 min"
    )
    assert len(lines) == 4
    assert workorders.ledger_lines([]) == ["no work orders on record"]
