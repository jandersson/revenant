"""The wiki's two sources for ;hunt grounds' box fallback (#422): the
Locksmithing page's "Creatures with boxes" table (tools/box_tables.py,
into boxes_data.py) and the Critter pages' Has Boxes
(tools/creature_tables.py, into creatures_data.py's BOXES). The cells
are the page's own, as read on 2026-10-02."""

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).parents[2]


def _tool(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


box_tables = _tool("box_tables")
creature_tables = _tool("creature_tables")

PAGE = """Some text before.
===Creatures with boxes===
{| class="wikitable sortable"
|-
!Creature
!Approx. Min. Ranks
!Approx. Cap
!Spawn Rate
!Drop Rate
|-
|[[Goblin]]||0||40+|| ||High
|-
|[[Wood Troll]]||30||55|| ||
|-
|[[Snow Goblin (1)|Snow Goblin]]s, 1st Tier||85(?)||135(?)|| ||
|-
|[[Snow Goblin (3)|Snow Goblin]]s, 3rd Tier||150||210|| ||High
|-
|[[Miserly Moneygrubber|Moneyrubber]], [[Pugnacious Pinchfist|Pinchfist]]||90(?)|||| ||
|}
After the table.
"""


def test_a_cell_names_its_creatures_as_the_links_show_them():
    assert box_tables.names_of("[[Goblin]]") == ["goblin"]
    assert box_tables.names_of("[[Rock Troll (1)]]") == ["rock troll"]
    assert box_tables.names_of("Super [[Rock Troll (2)|Rock Troll]]") == [
        "super rock troll"
    ]
    assert box_tables.names_of("[[Swamp Troll]] (Haven)") == ["swamp troll"]
    assert box_tables.names_of("[[Snow Goblin (1)|Snow Goblin]]s, 1st Tier") == [
        "snow goblin"
    ]
    assert box_tables.names_of(
        "[[Miserly Moneygrubber|Moneyrubber]], [[Pugnacious Pinchfist|Pinchfist]]"
    ) == ["moneyrubber", "pinchfist"]


def test_the_table_keeps_the_first_ranks_and_any_drop_rate_given():
    assert box_tables.table(PAGE) == {
        "goblin": ("0", "40+", "High"),
        "moneyrubber": ("90(?)", "", ""),
        "pinchfist": ("90(?)", "", ""),
        # The easiest tier's ranks, the third tier's drop rate.
        "snow goblin": ("85(?)", "135(?)", "High"),
        "wood troll": ("30", "55", ""),
    }
    rendered = box_tables.render({"goblin": ("0", "40+", "High")})
    assert "LOCKS = {" in rendered and "'goblin': ('0', '40+', 'High')," in rendered


def test_a_critter_page_says_whether_it_has_boxes():
    troll = "|Critter Name=wood [[:Category:troll|troll]]\n|level=7\n|Has Boxes=yes\n"
    wolf = "|level=12\n|Has Boxes=no\n"
    assert creature_tables.boxes_row("Wood Troll (1)", troll) == ("wood troll", True)
    assert creature_tables.boxes_row("Blood wolf (1)", wolf) == ("blood wolf", False)
    assert creature_tables.boxes_row("Rat", "|level=1\n") is None
    # Variants of one name: any with boxes means boxes.
    assert creature_tables.merge_boxes(
        [("blood wolf", False), ("wood troll", False), ("wood troll", True)]
    ) == {"blood wolf": False, "wood troll": True}
    rendered = creature_tables.render({}, {"blood wolf": False})
    assert "BOXES = {" in rendered and "'blood wolf': False," in rendered
