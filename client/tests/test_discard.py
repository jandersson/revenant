"""The drop allowlist — these tests are the rule. Only the foraged
junk a training loop discards on purpose may be dropped, plus what
settings.json's `droppable` adds; anything else is refused with an
echo and nothing is sent."""

import json

from client.game import discard


class Handle:
    def __init__(self):
        self.sent = []
        self.echoed = []

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


def test_settings_extend_the_list(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"droppable": ["rusty nail", " Broken Twig "]}))
    monkeypatch.setenv("REVENANT_SETTINGS", str(path))
    assert discard.droppable("rusty nail")
    assert discard.droppable("broken twig")
    assert discard.droppable("grass")  # the built-ins stay
    assert not discard.droppable("nail")
