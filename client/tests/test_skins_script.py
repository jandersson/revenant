"""How ;skins sells — these tests are the manual. Walk to the nearest
tannery, take the worn bundle off, SELL it from the hand, keep the
rope, walk back. Wordings captured 2026-09-12 at Falken's Tannery."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "skins_script", REPO / "scripts/skins.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01

MAP = MapDB(
    [
        {"id": 100, "uid": [1], "title": ["[Town, Square]"], "wayto": {}},
        {
            "id": 8266,
            "uid": [9003],
            "title": ["[Falken's Tannery, Workshop]"],
            "tags": ["tannery", "crossing tannery"],
            "wayto": {},
        },
    ]
)
PROFILE = {"loot_container": "sack"}

SOLD = (
    "You ask the tanner Falken to buy a lumpy bundle.\n"
    "The tanner Falken ponders over the bundle for a while, then hands you 111 Kronars.\n"
    'Tanner Falken says, "And there\'s your rope back again."\n'
)
MISSING = "What were you referring to?\n"


class Fake:
    """A handle whose answers come from a queue per command prefix."""

    def __init__(self, answers):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.walks = []
        self.pending = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(name="Lanival", room_uid=1)

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if queue else ""
                self.pending = [line + "\n" for line in text.splitlines()]
                return

    def get(self, timeout=None, streams=("",)):
        if timeout == 0 or not self.pending:
            return None
        return self.pending.pop(0)

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    s.state.room_uid = db.rooms[min(goals)]["uid"][0]
    return True


def test_sells_the_worn_bundle_keeps_the_rope_and_walks_back():
    fake = Fake({"remove": ["You remove a lumpy bundle."], "sell": [SOLD]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{8266}, {100}]
    assert fake.sent == [
        "remove my bundle",
        "sell my bundle",
        "put my rope in my sack",
    ]
    assert "skins: sold the bundle for 111 Kronars" in fake.echoed


def test_a_bundle_in_the_sack_is_fetched_when_none_is_worn():
    fake = Fake(
        {
            "remove": [MISSING],
            "get my bundle": ["You get a lumpy bundle from inside your canvas sack."],
            "sell": [SOLD],
        }
    )
    script.run(fake, ["stay"], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{8266}]  # stay: no walk back
    assert fake.sent[:3] == [
        "remove my bundle",
        "get my bundle from my sack",
        "sell my bundle",
    ]


def test_no_bundle_anywhere_stops_before_selling():
    fake = Fake({"remove": [MISSING], "get my bundle": [MISSING]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" not in fake.sent
    assert any("nothing to sell" in text for text in fake.echoed)


def test_a_tanner_who_does_not_pay_is_quoted_and_the_rope_left_alone():
    fake = Fake(
        {
            "remove": ["You remove a lumpy bundle."],
            "sell": ['The tanner Falken says, "I have no use for that."'],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert not any(command.startswith("put my rope") for command in fake.sent)
    assert any(
        "did not pay" in text and "no use for that" in text for text in fake.echoed
    )


def test_no_tannery_on_the_map_says_so():
    fake = Fake({})
    script.run(
        fake,
        [],
        MapDB([{"id": 1, "uid": [1], "title": ["[A]"], "wayto": {}}]),
        walk_fn=walk,
        profile=PROFILE,
    )
    assert fake.sent == []
    assert any("no room tagged 'tannery'" in text for text in fake.echoed)
