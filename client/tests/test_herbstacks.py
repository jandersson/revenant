"""How herb stacks are merged (#402) — these tests are the manual. A
container's stacks of a dried herb become full stacks of 75 and at most
one short one, other kinds of the same noun left alone, nothing lost.
The shelf below plays the game the way the 2026-10-01 experiment on
Lanival's dried red flowers found it."""

import itertools
import re
from types import SimpleNamespace

from client.game import herbstacks as stacks

MISSING = "What were you referring to?\n"
# Captured 2026-10-01 (#402).
MERGED = "You combine the stacks of herbs together.\n"
LEFT_OVER = "You combine the stacks of herbs together, but some was left over.\n"
FULL = "That stack of herbs is too large to add more to.\n"
ORDINAL = {word: index for index, word in enumerate(stacks.ORDINALS) if word}
DRIED = "dried red flowers"


class Shelf:
    """A backpack of (name, pieces), front first, and the hands as the
    parser's tags. GET by a plain ordinal reaches every "flowers"; a
    held item answers to its id; PUT puts at the front; COMBINE caps at
    75, the merged stack in the left hand, an overflow's rest there too
    and the full one in the right."""

    def __init__(self, backpack, cap=75):
        self.ids = itertools.count(1000)
        self.backpack = [(next(self.ids), name, n) for name, n in backpack]
        # Pressed flowers tag without "dried" (2026-10-01): the tag lies,
        # the GET's answer does not.
        self.tags = {}
        self.pieces = {}
        self.cap = cap
        self.sent = []
        self.state = SimpleNamespace(left_hand=None, right_hand=None)

    def hold(self, side, item, name, n):
        self.pieces[item] = (name, n)
        shown = self.tags.get(item, name)
        tag = {"exist": str(item), "name": shown, "noun": "flowers"}
        setattr(self.state, f"{side}_hand", tag)

    def free(self, item):
        for side in ("left_hand", "right_hand"):
            hand = getattr(self.state, side)
            if hand and hand["exist"] == str(item):
                setattr(self.state, side, None)
        return self.pieces.pop(item)

    def ask(self, s, command):
        self.sent.append(command)
        got = re.fullmatch(r"get my (?:(\w+) )?flowers from my backpack", command)
        if got:
            index = ORDINAL.get(got.group(1) or "", 0)
            if index >= len(self.backpack):
                return MISSING
            side = "right" if self.state.right_hand is None else "left"
            item, name, n = self.backpack.pop(index)
            self.hold(side, item, name, n)
            return f"You get some {name} from inside your backpack.\n"
        counted = re.fullmatch(r"count #(\d+)", command)
        if counted:
            name, n = self.pieces[int(counted.group(1))]
            return f"You count out {n} pieces of material there.\n"
        put = re.fullmatch(r"put #(\d+) in my backpack", command)
        if put:
            item = int(put.group(1))
            name, n = self.free(item)
            self.backpack.insert(0, (item, name, n))
            return "You put your flowers in your backpack.\n"
        combined = re.fullmatch(r"combine #(\d+) with #(\d+)", command)
        if combined:
            first, second = (int(x) for x in combined.groups())
            if self.cap in (self.pieces[first][1], self.pieces[second][1]):
                return FULL
            total = self.pieces[first][1] + self.pieces[second][1]
            self.free(first)
            self.free(second)
            if total <= self.cap:
                self.hold("left", next(self.ids), DRIED, total)
                return MERGED
            self.hold("left", next(self.ids), DRIED, total - self.cap)
            self.hold("right", next(self.ids), DRIED, self.cap)
            return LEFT_OVER
        return ""

    def stacks_of(self, name):
        return sorted(n for _, kind, n in self.backpack if kind == name)


def run(backpack):
    shelf = Shelf(backpack)
    result = stacks.merge(shelf, shelf.ask, DRIED, "backpack")
    return shelf, result


def test_scraps_become_full_stacks_and_one_short_past_the_other_flowers():
    # The backpack of 2026-10-01: fresh red flowers between the dried
    # stacks — an ordinal on "dried flowers" stopped at the first of them.
    backpack = (
        [(DRIED, 72), (DRIED, 75), (DRIED, 75), (DRIED, 75)]
        + [("red flowers", n) for n in (10, 9, 10, 9)]
        + [(DRIED, 25)] * 4
        + [("jadice flowers", 10), ("red flowers", 7)]
    )
    shelf, result = run(backpack)
    assert shelf.stacks_of(DRIED) == [22, 75, 75, 75, 75, 75]
    assert shelf.stacks_of("red flowers") == [7, 9, 9, 10, 10]
    assert shelf.stacks_of("jadice flowers") == [10]
    assert shelf.state.left_hand is None and shelf.state.right_hand is None
    assert result == (8, 6)


def test_a_pressed_stack_tagged_without_dried_is_merged_all_the_same():
    # 2026-10-01: four pressed stacks tagged "red flowers" were put back
    # as another kind; GET answered "some dried red flowers" for them.
    shelf = Shelf([(DRIED, 50), (DRIED, 25), (DRIED, 25)])
    for item, _, _ in shelf.backpack[1:]:
        shelf.tags[item] = "red flowers"
    result = stacks.merge(shelf, shelf.ask, DRIED, "backpack")
    assert shelf.stacks_of(DRIED) == [25, 75]
    assert result == (3, 2)


def test_full_stacks_alone_are_left_as_they_are():
    shelf, result = run([(DRIED, 75), (DRIED, 75)])
    assert shelf.stacks_of(DRIED) == [75, 75]
    assert not any(c.startswith("combine") for c in shelf.sent)
    assert result == (2, 2)


def test_a_full_stack_met_mid_merge_goes_back_and_the_short_one_goes_on():
    # 2026-10-01 step 7: 70 in hand, the next stack full — refused.
    shelf, result = run([(DRIED, 70), (DRIED, 75), (DRIED, 9)])
    assert shelf.stacks_of(DRIED) == [4, 75, 75]
    assert result == (3, 3)


def test_an_answer_the_experiment_never_saw_puts_both_back_and_stops():
    shelf = Shelf([(DRIED, 10), (DRIED, 20)])
    original = shelf.ask

    def ask(s, command):
        if command.startswith("combine"):
            shelf.sent.append(command)
            return "You can't combine those.\n"
        return original(s, command)

    assert stacks.merge(shelf, ask, DRIED, "backpack") is None
    assert shelf.state.left_hand is None and shelf.state.right_hand is None
    assert shelf.stacks_of(DRIED) == [10, 20]


def test_only_the_containers_holding_the_herb_are_searched():
    # 2026-10-01: the merge LOOKed IN the gem pouch for dried herbs.
    from client.game.remedies import containers_with

    possessions = [
        {"exist": "1", "name": "a rugged backpack", "noun": "backpack"},
        {"exist": "2", "name": "some dried red flowers", "container_exist": "1"},
        {"exist": "3", "name": "a black gem pouch", "noun": "pouch"},
        {"exist": "4", "name": "a tiny ruby", "container_exist": "3"},
        {"exist": "5", "name": "a canvas sack", "noun": "sack"},
        {"exist": "6", "name": "some red flowers", "container_exist": "5"},
    ]
    assert containers_with(possessions, "dried") == ["backpack"]
    assert containers_with(possessions, "flowers") == ["backpack", "sack"]
    assert containers_with(None, "dried") == []


def test_the_dried_herbs_a_listing_holds_more_than_once():
    listing = (
        "In the backpack you see an iron mortar, some dried red flowers, some "
        "red flowers, some dried nemoih, some dried red flowers, some jadice "
        "flowers and some dried red flowers.\n"
    )
    assert stacks.dried_herbs(listing) == [DRIED]
    assert stacks.dried_herbs("In the sack you see a cotton rag.\n") == []
