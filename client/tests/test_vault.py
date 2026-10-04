"""The Carousel vault — these tests are the manual. ;vault walks to the
Carousel, goes in (GO ARCH, PULL LEVER, GO DOOR, OPEN VAULT), puts or
gets each item by name, and always comes back out (CLOSE VAULT, GO
DOOR, GO ARCH). The answers are Cecil's, captured 2026-10-04
(client/game/vault.py, scripts/vault.py).
"""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import vault
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]

ESCORTED = (
    "The Dwarven attendant escorts you through the platinum arch.\n"
    "[Crossing, Carousel Booth]\n"
)
LEVER = (
    "A low, grinding vibration fills the building as you pull the lever, and the "
    "door pops open as if beckoning you to step through.\n"
)
RUMMAGED = (
    "You rummage through a secure vault and see a fine scroll, a brass hook, a "
    "map, an ilmenite runestone and a grey leather compendium embossed with a "
    "snakeskin pattern.\n"
)

CAROUSEL = MapDB(
    [
        {
            "id": 8285,
            "uid": [23101],
            "title": ["[Crossing, The Carousel]"],
            "wayto": {},
        },
    ]
)


def test_the_rummage_lists_the_vault():
    assert vault.contents(RUMMAGED) == [
        "a fine scroll",
        "a brass hook",
        "a map",
        "an ilmenite runestone",
        "a grey leather compendium embossed with a snakeskin pattern",
    ]
    assert vault.contents("What were you referring to?") is None


def test_items_are_named_comma_separated():
    assert vault.items_of(["leather", "compendium,", "fine", "scroll"]) == [
        "leather compendium",
        "fine scroll",
    ]


def _script():
    spec = importlib.util.spec_from_file_location(
        "vault_script", REPO / "scripts/vault.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Carousel:
    """The Carousel, a booth and the chamber, with Cecil's bag and vault."""

    def __init__(self, s, bag, stored):
        self.s = s
        self.sent = []
        self.bag = dict(bag)  # item name -> its words, on the character
        self.stored = dict(stored)  # in the vault
        self.ids = iter(range(500, 600))
        self.where = "carousel"

    def room(self, title):
        self.s.state.room_title = title

    def __call__(self, s, command):
        self.sent.append(command)
        state = s.state
        if command == "go arch":
            if self.where == "carousel":
                self.where = "booth"
                self.room("[Crossing, Carousel Booth]")
                return ESCORTED
            self.where = "carousel"
            self.room("[Crossing, The Carousel]")
            return "The door slams closed.\n[Crossing, The Carousel]\n"
        if command == "pull lever":
            return LEVER
        if command == "go door":
            self.where = "chamber" if self.where == "booth" else "booth"
            self.room(
                "[Crossing, Carousel Chamber]"
                if self.where == "chamber"
                else "[Crossing, Carousel Booth]"
            )
            return ""
        if command == "open vault":
            return "The vault opens.\n"
        if command == "close vault":
            return "You close the vault.\n"
        if command == "rummage vault":
            return RUMMAGED
        if command.startswith("get my "):
            item = command.removeprefix("get my ")
            if item not in self.bag:
                return "What were you referring to?\n"
            state.left_hand = {
                "noun": item.split()[-1],
                "exist": str(next(self.ids)),
                "name": item,
            }
            return f"You get a {self.bag.pop(item)} from inside your backpack.\n"
        if command.startswith("put #") and command.endswith(" in vault"):
            noun = state.left_hand["noun"]
            self.stored[state.left_hand["name"]] = state.left_hand["name"]
            state.left_hand = None
            return f"You put your {noun} in the secure vault.\n"
        if command.startswith("get ") and command.endswith(" from vault"):
            item = command.removeprefix("get ").removesuffix(" from vault")
            if item not in self.stored:
                return "What were you referring to?\n"
            del self.stored[item]
            state.left_hand = {
                "noun": item.split()[-1],
                "exist": str(next(self.ids)),
                "name": item,
            }
            return f"You get a {item} from inside a secure vault.\n"
        if command.startswith("stow #"):
            state.left_hand = None
            return "You put your compendium in your backpack.\n"
        return ""


def handle():
    echoed = []
    state = SimpleNamespace(
        name="Lanival",
        room_uid=23101,
        room_title="[Crossing, The Carousel]",
        compass=["s", "out"],
        left_hand=None,
        right_hand={"noun": "compendium", "exist": "9", "name": "simple compendium"},
        hostiles={},
    )
    return SimpleNamespace(
        state=state, dead=False, echo=echoed.append, echoed=echoed, args=[]
    )


def arrive(s, db, goals, describe=None, avoid=(), **_):
    return True


def test_put_goes_in_stores_each_item_by_its_id_and_comes_back_out():
    script = _script()
    s = handle()
    game = Carousel(s, {"leather compendium": "grey leather compendium"}, {})
    script.ask = game
    options = script.parse_args(["put", "leather", "compendium,", "fine", "scroll"])
    assert script.run(s, options, {}, db=CAROUSEL, walk=arrive) == "done"
    assert game.sent == [
        "go arch",
        "pull lever",
        "go door",
        "open vault",
        "get my leather compendium",
        "put #500 in vault",
        "get my fine scroll",  # not on him: said, and the run goes on
        "close vault",
        "go door",
        "go arch",
    ]
    assert "leather compendium" in game.stored
    assert any("no fine scroll on you" in text for text in s.echoed)
    assert "1 of 2 item(s) stored" in s.echoed[-1]
    assert game.where == "carousel"


def test_get_takes_an_item_out_and_stows_it():
    script = _script()
    s = handle()
    game = Carousel(s, {}, {"leather compendium": "leather compendium"})
    script.ask = game
    options = script.parse_args(["get", "leather", "compendium"])
    script.run(s, options, {}, db=CAROUSEL, walk=arrive)
    assert "get leather compendium from vault" in game.sent
    assert "stow #500" in game.sent
    assert any("out and stowed" in text for text in s.echoed)
    assert game.sent[-3:] == ["close vault", "go door", "go arch"]


def test_list_rummages_and_says_what_is_there():
    script = _script()
    s = handle()
    game = Carousel(s, {}, {})
    script.ask = game
    script.run(s, script.parse_args(["list"]), {}, db=CAROUSEL, walk=arrive)
    assert "rummage vault" in game.sent
    assert any("5 item(s): a fine scroll" in text for text in s.echoed)


def test_with_both_hands_full_nothing_is_sent():
    script = _script()
    s = handle()
    s.state.left_hand = {"noun": "scimitar", "exist": "1", "name": "steel scimitar"}
    game = Carousel(s, {}, {})
    script.ask = game
    why = script.run(s, script.parse_args(["put", "map"]), {}, db=CAROUSEL, walk=arrive)
    assert why == "hands full" and game.sent == []


def test_back_and_the_usage():
    script = _script()
    assert script.parse_args(["put", "map", "back"]) == {
        "verb": "put",
        "items": ["map"],
        "back": True,
    }
    s = handle()
    assert script.run(s, script.parse_args([]), {}, db=CAROUSEL, walk=arrive) == "usage"
