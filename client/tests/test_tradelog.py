"""tradelog's province column: the origin's, or Interprovince for a
contract to another province; filled in on a table logged before it."""

import sqlite3

from client.game import money, trade, tradelog

CONTRACT = trade.Contract(
    origin="Crossing",
    destination="Shard",
    goods="427 jars of pickled eel",
    worth=78568,
    currency="Dokoras",
    presented=False,
    expired=False,
)


def _provinces(path):
    connection = sqlite3.connect(str(path))
    try:
        return connection.execute(
            "SELECT origin, province FROM contracts ORDER BY seq"
        ).fetchall()
    finally:
        connection.close()


def test_a_local_contract_keeps_its_province_and_a_broker_one_is_interprovince(
    tmp_path,
):
    path = tmp_path / "history.db"
    tradelog.log_issue("Lanival", "Crossing", CONTRACT, 32663, 11170, path=path)
    tradelog.log_issue("Lanival", "Fayrin's Rest", CONTRACT, path=path)
    to_arthe = CONTRACT._replace(destination="Arthe Dale")
    tradelog.log_issue("Lanival", "Crossing", to_arthe, path=path)
    assert _provinces(path) == [
        ("Crossing", "Interprovince"),
        ("Fayrin's Rest", "Ilithi"),
        ("Crossing", "Zoluren"),
    ]


def test_history_counts_an_interprovince_route_in_kronars(tmp_path):
    # #561: charged 43,833 Kronars at the Crossing, paid 78,568 Dokoras
    # at Shard; the profit was a Kronars-from-Dokoras subtraction.
    path = tmp_path / "history.db"
    tradelog.log_issue("Lanival", "Crossing", CONTRACT, 32663, 11170, path=path)
    tradelog.log_delivery("Lanival", "Shard", 78568, path=path)
    shard = CONTRACT._replace(origin="Shard", destination="Fayrin's Rest")
    tradelog.log_issue("Lanival", "Shard", shard, 1000, 200, path=path)
    tradelog.log_delivery("Lanival", "Fayrin's Rest", 3000, path=path)
    routes = {r["destination"]: r for r in tradelog.summary("Lanival", path=path)}
    broker, local = routes["Shard"], routes["Fayrin's Rest"]
    assert broker["paid"] == round(78568 * money.KRONAR_RATES["Dokoras"])
    assert broker["cost"] == 32663 + 11170
    assert local["profit"] == round(3000 * 1.385808991) - round(1200 * 1.385808991)
    assert tradelog.describe(broker).startswith(
        "Crossing → Shard: 1 contract, 1 delivered, paid 108,880, profit 65,047 Kronars"
    )


def test_a_table_from_before_the_column_gets_it_filled_in(tmp_path):
    path = tmp_path / "history.db"
    old = sqlite3.connect(str(path))
    old.execute(tradelog.SCHEMA.replace(",\n    province TEXT", ""))
    old.executemany(
        "INSERT INTO contracts (issued_at, character_name, origin, destination,"
        " goods) VALUES ('2026-10-15', 'Lanival', ?, ?, 'y')",
        [
            ("Leth Deriel", "Crossing"),
            ("Shard", "Fayrin's Rest"),
            ("Crossing", "Shard"),
            ("Riverhaven", "Crossing"),
        ],
    )
    old.commit()
    old.close()
    tradelog.summary(path=path)  # any connection adds the column
    assert _provinces(path) == [
        ("Leth Deriel", "Zoluren"),
        ("Shard", "Ilithi"),
        ("Crossing", "Interprovince"),
        ("Riverhaven", None),
    ]
