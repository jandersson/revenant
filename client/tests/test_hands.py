"""client.game.hands: the hands off the parser's tags, a hand freed by
STOW with the answer judged, a weapon sheathed, the put-back a ;stop
still sends (#407)."""

from types import SimpleNamespace

from client.game import hands


class Fake:
    def __init__(self, left=None, right=None, answers=None, dead=False):
        self.state = SimpleNamespace(
            left_hand={"noun": left, "name": f"a {left}", "exist": "1"}
            if left
            else None,
            right_hand={"noun": right, "name": f"a {right}", "exist": "2"}
            if right
            else None,
        )
        self.answers = dict(answers or {})
        self.sent = []
        self.dead = dead

    def ask(self, s, command):
        self.sent.append(command)
        return self.answers.get(command, "You put it away.")

    def put(self, command, cleanup=False):
        self.sent.append((command, cleanup))


def test_held_nouns_and_holding_read_the_tags():
    s = Fake(left="pestle", right="bundling rope")
    assert hands.held(s) == {"left": "pestle", "right": "bundling rope"}
    assert hands.nouns(s) == ["pestle", "bundling rope"]
    assert hands.holding(s, "rope") and hands.holding(s, "Pestle")
    assert not hands.holding(s, "mortar")
    assert hands.side_of(s, "rope") == "right" and hands.side_of(s, "book") is None
    assert hands.full(s) and not hands.empty(s)
    assert hands.tags(s)["left"]["exist"] == "1"


def test_a_handle_without_hand_state_holds_nothing():
    bare = SimpleNamespace()
    assert hands.held(bare) == {"left": None, "right": None}
    assert hands.empty(bare) and not hands.full(bare)
    assert hands.tags(SimpleNamespace(state=None)) == {"left": None, "right": None}


def test_stow_is_judged_by_the_answer_either_not_found_wording_a_refusal():
    s = Fake(
        left="pestle",
        answers={
            "stow my pestle": "I could not find what you were referring to.",
            "stow my sack": "There isn't any more room in the backpack for that.",
            "stow my book": "You put your book in your satchel.",
        },
    )
    assert hands.stow(s, "pestle", ask=s.ask) is False
    assert hands.stow(s, "sack", ask=s.ask) is False
    assert hands.stow(s, "book", ask=s.ask) is True
    assert s.sent == ["stow my pestle", "stow my sack", "stow my book"]


def test_free_stows_what_is_not_kept_left_first():
    s = Fake(left="handaxe", right="skin")
    assert hands.free(s, keep=("handaxe",), ask=s.ask) == ["skin"]
    assert s.sent == ["stow my skin"]
    both = Fake(left="mortar", right="flowers")
    assert hands.free(both, ask=both.ask) == ["mortar", "flowers"]


def test_free_one_only_when_both_hands_are_full():
    one = Fake(left="pestle")
    assert hands.free_one(one, ask=one.ask) is True and one.sent == []
    both = Fake(left="pestle", right="mortar")
    assert hands.free_one(both, keep=("pestle",), ask=both.ask) is True
    assert both.sent == ["stow my mortar"]
    kept = Fake(left="pestle", right="mortar")
    assert hands.free_one(kept, keep=("pestle", "mortar"), ask=kept.ask) is False


def test_sheathe_into_the_container_or_a_stow_when_the_game_asks_where():
    s = Fake(
        right="scimitar",
        answers={
            "sheathe my scimitar": "Sheathe your steel scimitar where?",
            "sheathe my scimitar in my harness": "You sheathe your scimitar.",
        },
    )
    assert hands.sheathe(s, "scimitar", ask=s.ask) is True
    assert s.sent == ["sheathe my scimitar", "stow my scimitar"]
    s.sent.clear()
    assert hands.sheathe(s, "scimitar", "harness", ask=s.ask) is True
    assert s.sent == ["sheathe my scimitar in my harness"]


def test_at_end_sends_cleanup_stows_for_what_is_still_held():
    s = Fake(left="pestle", right="flowers")
    assert hands.at_end(s, ("pestle", "mortar")) == ["pestle"]
    assert s.sent == [("stow my pestle", True)]
    dead = Fake(left="pestle", dead=True)
    assert hands.at_end(dead, ("pestle",)) == [] and dead.sent == []


def test_cleanup_falls_back_to_a_plain_put_on_an_old_handle():
    sent = []
    old = SimpleNamespace(put=lambda command: sent.append(command))
    hands.cleanup(old, "stow my pestle")
    assert sent == ["stow my pestle"]
