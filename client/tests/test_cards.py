"""Trading cards into the card collector's case — these tests are the
manual. At a safe point with both hands empty the worn case is
REMOVEd into the right hand and OPENed, each card — INV LIST's by id,
then those a LOOK IN of the loot and default containers lists — is got
into the left hand and ADDed, and the case is CLOSEd and worn again;
an item the case will not take goes back (client/game/cards.py, #457).
"""

from types import SimpleNamespace

import pytest

from client.game import cards, hands, interlude

# The case's answers, captured on 2026-10-04 (#457).
REMOVED = "You remove a card collector's case from your belt.\n"
OPENED = "You open your collector's case.\n"
CLOSED = "You close your collector's case.\n"
WORN = "You attach a card collector's case to your belt.\n"
NO_CARD = "You must have a card in your left hand to do that.\n"
# Assumed: the refusal of an item that is no collectible card (not seen).
NOT_COLLECTIBLE = "That isn't a card you can add to your collection.\n"
STORE_DEFAULT = "Default:  a rugged backpack\n"
TOTE = "In the straw tote you see a Guildleader Lomtaun card and a wax label.\n"
BACKPACK = "In the backpack you see a playing card and a cotton rag.\n"
PROFILE = {"loot_container": "tote", "card_case": "collector's case"}
POSSESSIONS = [
    {"exist": "800", "name": "a card collector's case", "noun": "case", "worn": True},
    {"exist": "700", "name": "a large canvas sack", "noun": "sack", "worn": True},
    {
        "exist": "501",
        "name": "a Guildleader Kalika card",
        "noun": "card",
        "worn": False,
        "container_exist": "700",
    },
    {
        "exist": "502",
        "name": "an Immortal Eu card",
        "noun": "card",
        "worn": False,
        "container_exist": "800",  # already in the case
    },
]


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(cards, "_STATE", {"dirty": True})
    monkeypatch.setattr(cards, "_TRIED", set())
    monkeypatch.setattr(hands, "_DEFAULTS", {})
    monkeypatch.setattr(interlude, "_PENDING", set())
    monkeypatch.setattr(interlude, "_DEFERRED", {})
    monkeypatch.setattr(interlude, "_PROFILE", {})


class Game:
    """The case, the containers and the hands."""

    def __init__(self, s):
        self.s = s
        self.sent = []
        self.case = []
        self.ids = iter(range(600, 700))

    def __call__(self, s, command):
        self.sent.append(command)
        state = s.state
        if command == "store default":
            return STORE_DEFAULT
        if command == "remove #800":
            state.right_hand = {
                "noun": "case",
                "exist": "800",
                "name": "collector's case",
            }
            return REMOVED
        if command == "open #800":
            return OPENED
        if command == "close #800":
            return CLOSED
        if command == "wear #800":
            state.right_hand = None
            return WORN
        if command == "look in my tote":
            return TOTE
        if command == "look in my backpack":
            return BACKPACK
        if command.startswith("get "):
            names = {
                "get #501": "a Guildleader Kalika card",
                "get lomtaun card from my tote": "a Guildleader Lomtaun card",
                "get playing card from my backpack": "a playing card",
            }
            name = names[command]
            state.left_hand = {
                "noun": "card",
                "exist": str(next(self.ids)),
                "name": name,
            }
            return f"You get {name} from inside your straw tote.\n"
        if command == "cards add":
            held = state.left_hand
            if not held:
                return NO_CARD
            if "playing" in held["name"]:
                return NOT_COLLECTIBLE
            state.left_hand = None
            self.case.append(held["name"])
            return f"You slide {held['name']} into your case.\n"
        if command.startswith("put "):
            state.left_hand = None
            return "You put your card in your backpack.\n"
        return ""


def handle(right=None, possessions=POSSESSIONS):
    echoed = []
    s = SimpleNamespace(
        name="train",
        state=SimpleNamespace(
            name="Lanival",
            left_hand=None,
            right_hand=right,
            possessions=possessions,
            room_objs="",
            hostiles={},
            stunned=False,
        ),
        dead=False,
        echo=echoed.append,
        echoed=echoed,
        waitrt=lambda: None,
    )
    return s, Game(s)


def test_each_card_goes_into_the_case_and_the_case_back_on_the_belt():
    s, game = handle()
    added = cards.run(s, PROFILE, game)
    assert added == ["a Guildleader Kalika card", "a Guildleader Lomtaun card"]
    assert game.sent == [
        "remove #800",
        "open #800",
        "get #501",  # INV LIST's card in the sack, by id
        "cards add",
        "store default",
        "look in my tote",
        "get lomtaun card from my tote",
        "cards add",
        "look in my backpack",
        "get playing card from my backpack",
        "cards add",
        "put #602 in my backpack",  # no collectible: back where it was
        "close #800",
        "wear #800",
    ]
    assert s.state.left_hand is None and s.state.right_hand is None
    assert "2 card(s) into the collector's case" in s.echoed[-1]
    assert any("would not take a playing card" in text for text in s.echoed)
    assert not cards.due(PROFILE)  # clean until the hunt pockets a card


def test_a_card_from_the_login_listing_is_not_got_again_the_same_session():
    s, game = handle()
    cards.run(s, PROFILE, game)
    cards.mark()
    s2, game2 = handle()
    cards.run(s2, PROFILE, game2)
    assert "get #501" not in game2.sent


def test_with_a_hand_full_the_cards_wait_and_nothing_is_sent():
    s, game = handle(right={"noun": "scimitar", "exist": "7", "name": "steel scimitar"})
    assert cards.run(s, PROFILE, game) == []
    assert game.sent == []
    assert "both hands must be empty" in s.echoed[-1]
    assert cards.due(PROFILE)  # still due: the next safe point with free hands


def test_without_a_card_case_in_the_profile_the_chore_is_off():
    assert not cards.due({"loot_container": "tote"})
    s, game = handle()
    assert cards.run(s, {"loot_container": "tote"}, game) == []
    assert game.sent == []


def test_without_a_listing_the_case_is_named_by_the_profile():
    s, _ = handle(possessions=[])
    assert cards.case_ref(s, PROFILE) == "my collector's case"


def test_the_interlude_never_stows_a_weapon_to_make_room_for_the_cards(monkeypatch):
    # The weapon stays in hand after a hunt by design: the left hand's
    # item is not stowed for this chore, which needs both hands.
    s, game = handle(right={"noun": "scimitar", "exist": "7", "name": "steel scimitar"})
    monkeypatch.setattr(interlude, "ask", game)
    monkeypatch.setattr(interlude, "_loot_profile", lambda s: PROFILE)
    monkeypatch.setattr(interlude, "_almanac_due", lambda s: False)
    monkeypatch.setattr(
        interlude,
        "REGISTRY",
        {"cards": (interlude._cards_due, interlude._cards, interlude._both_hands_free)},
    )
    interlude.run_due(s)
    assert game.sent == []
    assert cards.due(PROFILE)
