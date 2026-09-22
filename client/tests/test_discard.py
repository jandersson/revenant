"""The drop allowlist — these tests are the rule. Only the foraged
junk a training loop discards on purpose may be dropped, plus what
settings.json's `droppable` adds; anything else is refused with an
echo and nothing is sent. A listed item goes into the room's trash
receptacle when the listing shows one, else DROP (2026-09-22)."""

import json
from types import SimpleNamespace

from client.game import discard


class Handle:
    def __init__(self, room_objs=""):
        self.sent = []
        self.echoed = []
        self.state = SimpleNamespace(room_objs=room_objs)

    def echo(self, text):
        self.echoed.append(text)


def ask(handle, command):
    handle.sent.append(command)
    return "You drop it."


def test_the_built_in_list_is_the_braided_grass_and_nothing_else():
    assert discard.droppable("grass")
    assert discard.droppable("grass rope")
    assert discard.droppable("Grass Rope")
    for item in ("rope", "bundling rope", "handaxe", "bundle", "pelt", "", None):
        assert not discard.droppable(item)


def test_drop_sends_only_for_listed_items_and_refuses_the_rest():
    handle = Handle()
    assert discard.drop(handle, "grass rope", ask) == "You drop it."
    assert handle.sent == ["drop my grass rope"]
    assert discard.drop(handle, "rope", ask) is None
    assert handle.sent == ["drop my grass rope"]  # nothing more went out
    assert any("drop refused: 'rope'" in text for text in handle.echoed)


def test_the_rooms_receptacle_is_read_off_the_listing():
    # Every shape the game logs of 2026-09 showed in the Crossing.
    for listing, noun in (
        ("a wrought-iron bench and a bucket", "bucket"),
        ("a waste bin", "bin"),
        ("a large waste bucket", "bucket"),
        ("a round metal bucket and a sign", "bucket"),
        ("a wooden bin", "bin"),
        ("a waste basket", "basket"),
        ("an iron door and a garbage chute", "chute"),
    ):
        assert discard.receptacle(listing) == noun, listing
    assert discard.receptacle("a cozy hickory log cabin") is None  # no bin in a cabin
    assert discard.receptacle("a clerk, a plant grinder and a dry press") is None
    assert discard.receptacle("") is None and discard.receptacle(None) is None


GLOOP = "You drop some blister cream in a bucket of viscous gloop.\n"  # 2026-09-22


def test_a_listed_item_goes_into_the_receptacle_else_dropped():
    handle = Handle("a wrought-iron bench and a bucket")
    assert discard.drop(handle, "grass rope", ask) == "You drop it."
    assert handle.sent == ["put my grass rope in bucket"]
    # The bank lobby's bucket, as captured: the listing's noun is the
    # first word of the phrase, and the answer is no refusal.
    lobby = Handle("a bucket of viscous gloop and the tellers' windows")
    assert discard.receptacle(lobby.state.room_objs) == "bucket"
    assert discard.drop(lobby, "grass", lambda h, c: h.sent.append(c) or GLOOP) == GLOOP
    assert lobby.sent == ["put my grass in bucket"]
    assert any(word in GLOOP.lower() for word in discard.DISPOSED)
    # A refusal from the receptacle falls back to the DROP.
    refused = Handle("a waste bin")

    def refusing(h, command):
        h.sent.append(command)
        return (
            "What were you referring to?"
            if command.startswith("put")
            else "You drop it."
        )

    assert discard.drop(refused, "grass", refusing) == "You drop it."
    assert refused.sent == ["put my grass in bin", "drop my grass"]
    # The allowlist gates the receptacle too.
    assert discard.drop(Handle("a bucket"), "rope", ask) is None


def test_settings_extend_the_list(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"droppable": ["rusty nail", " Broken Twig "]}))
    monkeypatch.setenv("REVENANT_SETTINGS", str(path))
    assert discard.droppable("rusty nail")
    assert discard.droppable("broken twig")
    assert discard.droppable("grass")  # the built-ins stay
    assert not discard.droppable("nail")
