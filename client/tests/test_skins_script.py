"""How ;skins sells — these tests are the manual. Walk to the nearest
tannery, take the worn bundle off, SELL it from the hand, keep the
rope, walk back. Wordings captured 2026-09-12 at Falken's Tannery."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.engine.scripting import ScriptStopped

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
        {
            "id": 1200,
            "uid": [9004],
            "title": ["[Provincial Bank, Teller]"],
            "tags": ["bank"],
            "wayto": {},
        },
    ]
)
PROFILE = {"loot_container": "sack"}

# Captured 2026-09-12 on the first scripted sale: REMOVE's answer, and
# the tanner's for two pelts.
REMOVED = "You sling a lumpy bundle off from over your shoulder.\n"
SOLD = (
    "You ask the tanner Falken to buy a lumpy bundle.\n"
    "The tanner Falken ponders over the bundle for a while, then hands you 111 Kronars.\n"
    'Tanner Falken says, "And there\'s your rope back again."\n'
)
MISSING = "What were you referring to?\n"
# DEPOSIT ALL's answer, captured 2026-09-14 at the Provincial Bank.
DEPOSITED = (
    "The clerk slides a small metal box across the counter into which you drop "
    "all your Kronars.  She counts them carefully and records the deposit in "
    "her ledger.\n"
)


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
        self.started = []  # (name, args) of the scripts this one ran
        self.can_start = True
        self.polls = 0  # is_running answers True this many times first

    # --- the handle's other-script API: ;skins bank runs ;bank ---
    def run(self, name, args=()):
        if not self.can_start:
            self.echoed.append(f"{name} is already running")
            return False
        self.started.append((name, list(args)))
        return True

    def is_running(self, name):
        self.polls -= 1
        return self.polls >= 0

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if queue else ""
                self.pending = [line + "\n" for line in text.splitlines()]
                return
        if command.startswith("get my "):
            self.pending = [MISSING]  # nothing the test named

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


def commands(fake):
    """The commands sent, minus the LOOK IN that names the loose skins
    (#401) — the bundle sale's own shape."""
    return [
        c
        for c in fake.sent
        if not c.startswith("look in my ")
        and not (c.startswith("get my ") and c.split()[2] in script.SKIN_NOUNS)
    ]


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    s.state.room_uid = db.rooms[min(goals)]["uid"][0]
    return True


def test_sells_the_worn_bundle_keeps_the_rope_and_stays_at_the_tannery():
    # The start is usually the hunting ground: the first scripted run
    # walked back into the rats with the weapon stowed (2026-09-12).
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{8266}]
    assert commands(fake) == [
        "remove my bundle",
        "sell my bundle",
        "put my rope in my sack",
    ]
    assert "skins: sold the bundle for 111 Kronars" in fake.echoed


def test_a_bundle_already_in_hand_is_sold_without_a_remove():
    # 2026-09-14: a run stopped between REMOVE and SELL left the bundle
    # in the left hand, and the next run said "nothing to sell".
    fake = Fake({"sell": [SOLD]})
    fake.state.left_hand = {"noun": "bundle", "exist": "1", "name": "lumpy bundle"}
    fake.state.right_hand = {
        "noun": "handaxe",
        "exist": "2",
        "name": "oak-hafted handaxe",
    }
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert commands(fake) == ["sell my bundle", "put my rope in my sack"]


def test_a_bundle_in_the_sack_is_fetched_when_none_is_worn():
    fake = Fake(
        {
            "remove": [MISSING],
            "get my bundle": ["You get a lumpy bundle from inside your canvas sack."],
            "sell": [SOLD],
        }
    )
    script.run(fake, ["back"], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.walks == [{8266}, {100}]  # back: the walk home
    assert commands(fake)[:3] == [
        "remove my bundle",
        "get my bundle from my sack",
        "sell my bundle",
    ]


def test_a_stop_while_banking_stops_the_bank_it_started():
    # ;hunt stops its ;skins, and ;skins its ;bank (2026-09-28).
    fake = Fake({})
    fake.polls = 5
    killed = []
    fake.kill = killed.append

    def stopped(seconds):
        raise ScriptStopped()

    fake.sleep = stopped
    with pytest.raises(ScriptStopped):
        script.hand_to_bank(fake, [])
    assert killed == ["bank"]


def test_bank_runs_the_bank_script_and_waits_for_it():
    # The operator, 2026-09-20: "it should just do ;bank" — the banking
    # (the money-changer, DEPOSIT ALL, keep=N) lives in one script, and
    # ;skins carried a second copy of its last step. `back` walks home
    # once ;bank has ended; the teller is ;bank's to walk to.
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    fake.polls = 3
    script.run(fake, ["bank", "keep=500", "back"], MAP, walk_fn=walk, profile=PROFILE)
    assert commands(fake) == [
        "remove my bundle",
        "sell my bundle",
        "put my rope in my sack",
    ]
    assert fake.started == [("bank", ["keep=500"])]
    assert fake.polls == -1  # waited until ;bank was no longer running
    assert fake.walks == [{8266}, {100}]
    assert "deposit all" not in fake.sent
    # Nothing sold still banks: a hunt's search coins are in the purse.
    fake = Fake({"remove": [MISSING], "get my bundle": [MISSING]})
    script.run(fake, ["bank"], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.started == [("bank", [])]
    # A ;bank already running is the operator's: said, left alone.
    fake = Fake({"remove": [REMOVED], "sell": [SOLD]})
    fake.can_start = False
    script.run(fake, ["bank"], MAP, walk_fn=walk, profile=PROFILE)
    assert fake.started == []
    assert any("could not start ;bank" in text for text in fake.echoed)
    assert DEPOSITED  # the teller's line stays captured for ;bank's tests


def test_no_bundle_anywhere_stops_before_selling():
    fake = Fake({"remove": [MISSING], "get my bundle": [MISSING]})
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" not in fake.sent
    assert any("nothing to sell" in text for text in fake.echoed)


def test_a_tanner_who_does_not_pay_is_quoted_and_the_rope_left_alone():
    fake = Fake(
        {
            "remove": [REMOVED],
            "sell": ['The tanner Falken says, "I have no use for that."'],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert not any(command.startswith("put my rope") for command in fake.sent)
    assert any(
        "did not pay" in text and "no use for that" in text for text in fake.echoed
    )


LOOKED = (
    "In the canvas sack you see a round cambrinth flake, a badger pelt, a "
    "curved claw, a badger pelt, some bundling rope and a cotton rag.\n"
)


def test_the_look_in_answer_names_the_nouns_present():
    assert script.listed_nouns(LOOKED) == [
        "flake",
        "pelt",
        "claw",
        "pelt",
        "rope",
        "rag",
    ]
    assert script.listed_nouns("There is nothing in there.\n") == []
    assert script.listed_nouns("What were you referring to?\n") is None


def test_loose_skins_in_the_sack_are_named_and_left_there():
    # #401 (the operator, 2026-10-01): only a bundle is sold. A loose skin
    # is kept on purpose or says a hunt could not bundle it — the 22
    # loose pelts #399 left were sold unseen that morning.
    fake = Fake(
        {
            "remove": [REMOVED],
            "sell my bundle": [SOLD],
            "look in my sack": [LOOKED],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my bundle" in fake.sent
    assert not any(c.startswith(("sell my pelt", "sell my claw")) for c in fake.sent)
    assert not any(c.startswith(("get my pelt", "get my claw")) for c in fake.sent)
    assert (
        "skins: 2 pelt(s), 1 claw(s) loose in the sack — left there; "
        "only a bundle is sold"
    ) in fake.echoed
    assert fake.sent.count("look in my sack") == 1


def test_a_skin_left_in_hand_is_named_not_sold():
    # #262 left a pelt in the hand when no container had room.
    fake = Fake(
        {
            "remove": [MISSING],
            "get my bundle": [MISSING],
            "look in my sack": ["In the canvas sack you see a cotton rag.\n"],
        }
    )
    fake.state.left_hand = {"noun": "pelt", "exist": "3", "name": "badger pelt"}
    fake.state.right_hand = None
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert "sell my pelt" not in fake.sent
    assert "skins: a pelt in hand — left there; only a bundle is sold" in fake.echoed


def test_no_loose_skins_says_nothing_about_them():
    fake = Fake(
        {
            "remove": [REMOVED],
            "sell my bundle": [SOLD],
            "look in my sack": ["In the canvas sack you see some bundling rope.\n"],
        }
    )
    script.run(fake, [], MAP, walk_fn=walk, profile=PROFILE)
    assert not any("only a bundle is sold" in t for t in fake.echoed)


def test_no_tannery_on_the_map_says_so():
    fake = Fake({})
    script.run(
        fake,
        [],
        MapDB([{"id": 1, "uid": [1], "title": ["[A]"], "wayto": {}}]),
        walk_fn=walk,
        profile=PROFILE,
    )
    assert commands(fake) == []
    assert any("no room tagged 'tannery'" in text for text in fake.echoed)
