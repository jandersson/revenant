"""client.game.items: an item named by its id when held, the containers
INV LIST showed, a LOOK IN listing parsed, COUNT read, a full
container's wording (#407)."""

from types import SimpleNamespace

from client.game import items

POSSESSIONS = [
    {
        "name": "a leather backpack",
        "noun": "backpack",
        "exist": "1",
        "container_exist": None,
    },
    {"name": "a gem pouch", "noun": "pouch", "exist": "2", "container_exist": None},
    {"name": "a stone mortar", "noun": "mortar", "exist": "3", "container_exist": None},
    {
        "name": "some dried red flowers",
        "noun": "flowers",
        "exist": "4",
        "container_exist": "1",
    },
    {
        "name": "a plain steel coffer (closed)",
        "noun": "coffer",
        "exist": "5",
        "container_exist": "1",
    },
    {"name": "a ruby", "noun": "ruby", "exist": "6", "container_exist": "2"},
    {
        "name": "some crushed red flowers",
        "noun": "flowers",
        "exist": "7",
        "container_exist": "3",
    },
]


def _handle(left=None, right=None):
    return SimpleNamespace(
        state=SimpleNamespace(
            left_hand={"noun": left, "exist": "11"} if left else None,
            right_hand={"noun": right, "exist": "22"} if right else None,
        )
    )


def test_a_held_item_is_named_by_its_id_anything_else_whole():
    s = _handle(left="flowers")
    assert items.ref(s, "flowers") == "#11"
    assert items.ref(s, "dried red flowers") == "#11"
    assert items.ref(s, "rope") is None
    assert items.name(s, "dried red flowers") == "#11"
    assert items.name(s, "bundling rope") == "bundling rope"
    assert items.name(SimpleNamespace(), "flowers") == "flowers"


def test_containers_are_the_holders_inv_list_showed_once_in_order():
    assert items.containers(POSSESSIONS) == ["backpack", "pouch", "mortar"]
    assert items.containers(POSSESSIONS, skip=("mortar",)) == ["backpack", "pouch"]
    assert items.containers(POSSESSIONS, holding="dried") == ["backpack"]
    assert items.containers(POSSESSIONS, holding="flowers", skip=("mortar",)) == [
        "backpack"
    ]
    assert items.containers(
        POSSESSIONS, holding=lambda item: item["noun"] == "coffer"
    ) == ["backpack"]
    assert items.containers(None) == []


def test_a_listing_is_parsed_once_for_every_reader():
    assert items.listed("In the iron box you see some coins, a ruby and a dagger.") == [
        "some coins",
        "a ruby",
        "a dagger",
    ]
    # "and" splits only before an article: a salt and pepper shaker is one item.
    assert items.listed("In the sack you see a salt and pepper shaker and a cup.") == [
        "a salt and pepper shaker",
        "a cup",
    ]
    assert items.listed("There is nothing in there.") == []
    assert items.listed("What were you referring to?") is None
    assert items.listed_nouns(
        "In the sack you see a rat tail, a plain coffer (closed)."
    ) == [
        "tail",
        "coffer",
    ]
    assert items.listed_nouns("") is None


def test_count_and_the_stow_container_are_read_off_the_answers():
    assert items.count("You count out 12 pieces of material there.") == 12
    assert items.count("You count out 1 piece of material there.") == 1
    assert items.count("Count what?") is None
    assert items.stowed_in("You put your red flowers in your leather backpack.") == (
        "leather backpack"
    )
    assert items.stowed_in("What were you referring to?") == ""


def test_a_full_container_is_known_by_every_wording():
    assert items.no_room("There isn't any more room in the sack for that.")
    assert items.no_room("That would push you over the item limit.")
    assert items.no_room("You just can't fit that in there.")
    assert not items.no_room("You put your ruby in your pouch.")
