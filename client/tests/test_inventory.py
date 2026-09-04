"""How INV LIST's nested item list becomes flat, searchable rows.

The rules these pin down (#117): indentation gives depth, each row
names its immediate container, and identical items in the same
container collapse into one row with a quantity.

The shapes come from captured traffic (2026-09-03, five characters):
top-level items indented two spaces, every level below adding three
more and a leading "-". Item names are the game's own; no character
names appear.
"""

from client.inventory import flatten, parse_inventory

# The captured shape, trimmed: worn items, a container with contents,
# and a container inside that one holding duplicates.
CAPTURED = """You take a moment and rummage about your person, taking stock of your possessions...
You have:
  an ornate platinum brooch set with an orichalcum icosahedron
  a target shield
  an ornate scabbard
     -a short sword
     -a broadsword
     -a tapered cutlass
  a battered leather traveler's haversack
     -a curved lunch pail labeled "Victuals"
        -a goblet of rich bloodwyne
        -a goblet of rich bloodwyne
        -a wax label
  a woven shoulder sack
[Use INVENTORY HELP for more options.]
Roundtime: 5 sec.
"""


class TestStructure:
    def test_worn_items_have_no_container(self):
        rows = parse_inventory(CAPTURED)
        top = [row["item"] for row in rows if row["depth"] == 0]
        assert top == [
            "an ornate platinum brooch set with an orichalcum icosahedron",
            "a target shield",
            "an ornate scabbard",
            "a battered leather traveler's haversack",
            "a woven shoulder sack",
        ]
        assert all(row["container"] is None for row in rows if row["depth"] == 0)

    def test_contents_name_their_container(self):
        rows = parse_inventory(CAPTURED)
        swords = [row for row in rows if row["item"] == "a broadsword"]
        assert swords[0]["container"] == "an ornate scabbard"
        assert swords[0]["depth"] == 1

    def test_nesting_goes_deeper_than_one_level(self):
        # A container inside a container: the captured traffic reaches
        # depth 2, and the depth rule is not limited to it.
        rows = parse_inventory(CAPTURED)
        label = next(row for row in rows if row["item"] == "a wax label")
        assert label["depth"] == 2
        assert label["container"] == 'a curved lunch pail labeled "Victuals"'

    def test_a_deeper_tree_than_we_have_captured_still_parses(self):
        deeper = (
            "You have:\n  a bag\n     -a box\n        -a pouch\n           -a coin\n"
        )
        rows = parse_inventory(deeper)
        coin = next(row for row in rows if row["item"] == "a coin")
        assert (coin["depth"], coin["container"]) == (3, "a pouch")


class TestQuantities:
    def test_identical_items_in_one_container_collapse(self):
        # One captured character carried six identical goblets, another
        # thirty-nine identical crystal shards: rows per item, not per
        # copy.
        rows = parse_inventory(CAPTURED)
        goblets = [row for row in rows if row["item"] == "a goblet of rich bloodwyne"]
        assert len(goblets) == 1
        assert goblets[0]["quantity"] == 2

    def test_a_single_item_has_quantity_one(self):
        rows = parse_inventory(CAPTURED)
        assert next(r for r in rows if r["item"] == "a wax label")["quantity"] == 1

    def test_the_same_item_in_two_containers_stays_two_rows(self):
        text = "You have:\n  a left pouch\n     -a gem\n  a right pouch\n     -a gem\n"
        rows = [row for row in parse_inventory(text) if row["item"] == "a gem"]
        assert len(rows) == 2
        assert {row["container"] for row in rows} == {"a left pouch", "a right pouch"}


class TestNonAnswers:
    def test_output_without_the_header_yields_nothing(self):
        # An unanswered command must store nothing: an empty list would
        # read as "this character owns nothing".
        assert parse_inventory("") == []
        assert parse_inventory("You see nothing unusual.") == []

    def test_a_renaming_room_refusal_yields_nothing(self):
        refusal = (
            "Lanival, this is a reminder that you have been sent to this room "
            "so you may change your name to something which fits the medieval "
            "fantasy environment of DragonRealms."
        )
        assert parse_inventory(refusal) == []

    def test_the_footer_ends_the_list(self):
        # Roundtime and anything after it are not inventory.
        rows = parse_inventory(CAPTURED)
        assert not any("Roundtime" in row["item"] for row in rows)
        assert not any("INVENTORY HELP" in row["item"] for row in rows)


class TestFlatten:
    def test_contents_read_as_container_then_item(self):
        rows = parse_inventory(CAPTURED)
        lines = flatten(rows)
        assert "a target shield" in lines
        assert "an ornate scabbard > a broadsword" in lines
