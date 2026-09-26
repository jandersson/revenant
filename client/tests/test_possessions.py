"""Possessions by exist id (#184) — these tests are the manual: the
listing's links become items, a noun finds its ids, and the sheet's
rows carry the ids beside the names."""

from client.game import possessions

# Captured 2026-09-13: (indent, cmd, name) as the parser collects them.
LINKS = [
    ("  ", "remove #53174575", "a lumpy bundle"),
    ("     -", "get #50886622 in #53174575", "a rat tail"),
    ("     -", "get #50886623 in #53174575", "a rat tail"),
    ("  ", "remove #50886620", "a large canvas sack"),
    ("     -", "get #50886688 in #50886620", "an oak-hafted handaxe"),
    ("     -", "get #50886621 in #50886620", "a metal armet"),
    ("[Use ", "inventory help", "INVENTORY HELP"),
]


def test_links_become_items_with_ids_containers_and_depth():
    items = possessions.build(LINKS)
    assert [item["exist"] for item in items] == [
        "53174575",
        "50886622",
        "50886623",
        "50886620",
        "50886688",
        "50886621",
    ]
    bundle, tail, _, sack, handaxe, armet = items
    assert bundle["worn"] and bundle["container_exist"] is None and bundle["depth"] == 0
    assert tail == {
        "exist": "50886622",
        "name": "a rat tail",
        "noun": "tail",
        "verb": "get",
        "container_exist": "53174575",
        "worn": False,
        "depth": 1,
    }
    assert handaxe["container_exist"] == sack["exist"] and handaxe["noun"] == "handaxe"
    assert armet["name"] == "a metal armet"


def test_a_closed_containers_state_is_not_its_noun():
    # 2026-09-26: "a plain steel coffer (closed)" read as noun "(closed)",
    # so ;boxes never saw the coffer in the backpack (#323).
    items = possessions.build(
        [
            ("  ", "remove #1", "a rugged backpack"),
            ("    -", "get #2 in #1", "a plain steel coffer (closed)"),
            ("    -", "get #3 in #1", "a poorly made oaken crate (open)"),
        ]
    )
    assert [item["noun"] for item in items] == ["backpack", "coffer", "crate"]
    assert items[1]["name"] == "a plain steel coffer (closed)"


def test_a_noun_finds_its_items_in_order():
    items = possessions.build(LINKS)
    assert [item["exist"] for item in possessions.find(items, "tail")] == [
        "50886622",
        "50886623",
    ]
    assert possessions.find(items, "handaxe")[0]["exist"] == "50886688"
    assert (
        possessions.find(items, "canvas")[0]["exist"] == "50886620"
    )  # a word of the name
    assert possessions.find(items, "orb") == []
    assert possessions.find(items, "") == []
    assert possessions.find(None, "tail") == []


def test_the_sheets_rows_carry_the_ids_and_never_collapse_twins():
    rows = possessions.rows(possessions.build(LINKS))
    assert rows[1] == {
        "container": "a lumpy bundle",
        "item": "a rat tail",
        "quantity": 1,
        "depth": 1,
        "exist": "50886622",
        "container_exist": "53174575",
    }
    assert rows[2]["exist"] == "50886623"  # the second tail is its own row
    assert rows[0]["container"] is None and rows[0]["exist"] == "53174575"


def test_a_links_command_parses_or_is_none():
    assert possessions.parse_command("remove #53174575") == ("remove", "53174575", None)
    assert possessions.parse_command("get #1 in #2") == ("get", "1", "2")
    assert possessions.parse_command("inventory help") is None
    assert possessions.parse_command("") is None
