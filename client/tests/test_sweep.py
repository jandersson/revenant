"""The loot sweep — these tests are the manual. Beside a bin, what the
profile's `loot_ignore` names goes out of the loot container into the
trash: GET from the container only, the item in hand checked again,
each one named; `;break sweep` names them and moves nothing
(client/game/sweep.py, #378)."""

import itertools
from types import SimpleNamespace

import pytest

from client.game import discard, interlude, sweep
from client.game.profile import save_profile

# Cecil's canvas sack, listed by ;boxes at 20:59 on 2026-09-28 (a few
# items left out), and his loot_ignore.
LISTING = (
    "In the canvas sack you see a copper-edged pine strongbox, a lead rope, "
    "some red flowers, a small covellite nugget, an ordinary lockpick, an "
    "iron mortar, an iron pestle, some iron scissors, an embroidery needle, "
    "some silver coins and a salt and pepper shaker."
)
IGNORE = [
    "copper",
    "covellite",
    "iron",
    "lead",
    "nickel",
    "oravir",
    "silver",
    "tin",
    "zinc",
    "embroidery needle",
]
PROFILE = {"loot_container": "sack", "loot_ignore": IGNORE, "loot_sweep": True}
BUCKET_ROOM = "You also see a wrought-iron bench and a bucket of viscous gloop."


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(sweep, "_STATE", {"dirty": True, "warned": False})
    monkeypatch.setattr(interlude, "_PENDING", set())
    monkeypatch.setattr(interlude, "_PROFILE", {})


class Game:
    """The sack, the hands and the bin; `swap` hands over another item
    than the one asked for (the guard's case)."""

    def __init__(self, s, listing=LISTING, swap=None, bin_refuses=False):
        self.s = s
        self.sent = []
        self.listing = listing
        self.swap = swap or {}
        self.bin_refuses = bin_refuses
        self.binned = []
        self.exists = itertools.count(100)

    def __call__(self, s, command):
        self.sent.append(command)
        state = s.state
        if command.startswith("look in my "):
            return self.listing + "\n"
        if command.startswith("get ") and " from my " in command:
            wanted = command[len("get ") : command.index(" from my ")]
            name = self.swap.get(wanted, wanted)
            state.right_hand = {
                "noun": name.split()[-1],
                "exist": str(next(self.exists)),
                "name": name,
            }
            return f"You get {name} from inside your canvas sack.\n"
        if command.startswith("put my ") and " in " in command:
            held = state.right_hand
            target = command.rsplit(" in ", 1)[1]
            state.right_hand = None
            if target == "my sack":
                return "You put your item in your canvas sack.\n"
            if self.bin_refuses:
                state.right_hand = held
                return "You can't put that there.\n"
            self.binned.append(held["name"])
            return f"You drop {held['name']} in a bucket of viscous gloop.\n"
        return ""


def handle(room_objs=BUCKET_ROOM, **game):
    echoed = []
    s = SimpleNamespace(
        name="train",
        state=SimpleNamespace(
            name="Lanival",
            left_hand=None,
            right_hand=None,
            room_objs=room_objs,
            hostiles={},
            stunned=False,
        ),
        dead=False,
        echo=echoed.append,
        echoed=echoed,
        waitrt=lambda: None,
    )
    return s, Game(s, **game)


def test_the_listing_splits_on_items_not_on_every_and():
    items = sweep.listed_items(LISTING + "\nTalokai goes northwest.")
    assert items[0] == "a copper-edged pine strongbox"
    assert items[-1] == "a salt and pepper shaker"
    assert "Talokai goes northwest" not in " ".join(items)
    assert sweep.listed_items("There is nothing in there.") == []
    assert sweep.listed_items("What were you referring to?") is None


def test_only_junk_is_sweepable_the_tools_boxes_and_coins_are_not():
    items = sweep.listed_items(LISTING)
    taken = [item for item in items if sweep.sweepable(item, IGNORE)]
    assert taken == ["a small covellite nugget", "an embroidery needle"]
    # A one-word entry is a metal lump only: "needle" would take every
    # needle, so the sweep takes none by it, and says so.
    assert not sweep.sweepable("an embroidery needle", ["needle"])
    assert sweep.broad(["needle", "copper", "embroidery needle"]) == ["needle"]


def test_the_dry_run_names_what_would_go_and_moves_nothing():
    s, game = handle()
    names = sweep.run(s, PROFILE | {"loot_ignore": IGNORE + ["ring"]}, game, dry=True)
    assert names == ["a small covellite nugget", "an embroidery needle"]
    assert game.sent == ["look in my sack"]
    assert (
        "sweep: would trash from the sack: a small covellite nugget, an embroidery needle"
        in s.echoed
    )
    assert any("ring — one word" in text for text in s.echoed)


def test_beside_a_bin_each_item_is_got_from_the_sack_checked_and_trashed():
    s, game = handle()
    trashed = sweep.run(s, PROFILE, game)
    assert trashed == ["covellite nugget", "embroidery needle"]
    assert game.sent == [
        "look in my sack",
        "get covellite nugget from my sack",
        "put my covellite nugget in bucket",
        "get embroidery needle from my sack",
        "put my embroidery needle in bucket",
    ]
    assert "sweep: trashed embroidery needle from the sack" in s.echoed
    assert not sweep.dirty()


def test_an_item_in_hand_the_list_does_not_name_goes_back():
    # The GET fetched something else: the hand's own name decides.
    s, game = handle(swap={"embroidery needle": "silver-threaded embroidery hoop"})
    trashed = sweep.run(s, PROFILE, game)
    assert trashed == ["covellite nugget"]
    assert "put my embroidery hoop in my sack" in game.sent
    assert game.binned == ["covellite nugget"]
    assert any("which loot_ignore does not name — put back" in t for t in s.echoed)


def test_a_tag_that_drops_the_listed_adjective_is_still_the_item():
    # #486 (2026-10-07 20:51): the tote listed "a grimy bar of soap",
    # loot_ignore had "grimy bar of soap", the hand tag read "bar of soap"
    # — and the soap went back in, night after night.
    s, game = handle(
        listing="In the canvas sack you see a grimy bar of soap.",
        swap={"of soap": "bar of soap"},  # the sweep asks by short_name
    )
    profile = dict(PROFILE, loot_ignore=["grimy bar of soap"])
    assert sweep.run(s, profile, game) == ["bar of soap"]
    assert game.binned == ["bar of soap"]
    assert sweep.same_item("a dark azurite runestone", "azurite runestone")
    assert not sweep.same_item("a grimy bar of soap", "bar of iron")


def test_a_bin_that_refuses_gets_the_item_put_back():
    s, game = handle(bin_refuses=True)
    assert sweep.run(s, PROFILE, game) == []
    assert game.sent.count("put my covellite nugget in my sack") == 1
    assert any("the bin would not take covellite nugget" in t for t in s.echoed)


def test_the_chore_is_due_only_when_on_dirty_and_beside_a_bin(monkeypatch):
    s, game = handle()
    monkeypatch.setattr(interlude, "ask", game)
    save_profile("Lanival", PROFILE | {"loot_sweep": False})
    assert not interlude._sweep_due(s)  # off: never on its own
    interlude._PROFILE.clear()
    save_profile("Lanival", PROFILE)
    assert interlude._sweep_due(s)
    s.state.room_objs = "You also see a wrought-iron bench."
    assert not interlude._sweep_due(s)  # no bin, no sweep
    s.state.room_objs = BUCKET_ROOM
    interlude.run_due(s)
    assert game.binned == ["covellite nugget", "embroidery needle"]
    assert not interlude._sweep_due(s)  # swept: clean until something is kept


def test_an_item_kept_for_want_of_a_bin_makes_the_next_bin_sweep():
    s, game = handle(room_objs="You also see a wrought-iron bench.")
    sweep._STATE["dirty"] = False
    assert discard.trash(s, "copper nugget", game) is None
    assert sweep.dirty()


def test_break_sweep_is_the_dry_run_even_with_the_sweep_off(monkeypatch):
    s, game = handle()
    monkeypatch.setattr(interlude, "ask", game)
    save_profile("Lanival", PROFILE | {"loot_sweep": False})
    assert interlude.post("sweep")
    interlude.run_due(s)
    assert game.sent == ["look in my sack"]
    assert game.binned == []
    assert any("would trash from the sack" in text for text in s.echoed)
