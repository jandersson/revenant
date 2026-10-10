"""How ;task runs — these tests are the manual (#505). It reads the
journal, asks a giver, accepts a kind the profile allows inside the
window, carries a delivery to the recipient and hands it over; a run
after a stop carries the task on from the record."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game.mapdb import MapDB
from test_tasks import (
    ACCEPTED,
    COOLDOWN,
    DELIVERY_OFFER,
    JOURNAL,
    JOURNAL_CLEAR,
    PAID,
    RECOVERY_OFFER,
)

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "task_script", REPO / "scripts/task.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

MAP = MapDB(
    [
        {
            "id": 8261,
            "uid": [1],
            "title": ["[Cormyn's House of Heirlooms]"],
            "wayto": {"10021": "north"},
        },
        {
            "id": 10021,
            "uid": [2],
            "title": ["[Seven Star Exchange and Pawn]"],
            "wayto": {},
        },
    ]
)

BASKET = {"exist": "172475803", "noun": "basket", "name": "gift basket"}
GOT_BASKET = "You get a green gift basket from inside your hunting pack.\n"
STOWED = "You put your basket in your hunting pack.\n"


class Fake:
    """A handle whose answers come from a queue per command prefix; the
    accept puts the basket in the right hand, a STOW empties it, a GET
    fills it again."""

    def __init__(self, answers, journal=JOURNAL_CLEAR):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.answers.setdefault("task", [journal])
        self.sent, self.echoed, self.walks = [], [], []
        self.pending = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            room_uid=1,
            room_title="[Cormyn's House of Heirlooms]",
            right_hand=None,
            left_hand=None,
            hostiles={},
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        if command == "accept task":
            self.state.right_hand = dict(BASKET)
        elif command.startswith("stow "):
            self.state.right_hand = None
        elif command.startswith("get "):
            self.state.right_hand = dict(BASKET)
        elif command.startswith("give "):
            self.state.right_hand = None
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                text = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else "")
                self.pending = [line + "\n" for line in text.splitlines()]
                return

    def get(self, timeout=None, streams=("",)):
        if timeout == 0 or not self.pending:
            return None
        return self.pending.pop(0)

    def command(self, timeout=None):
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    room = min(goals)
    s.state.room_uid = db.rooms[room]["uid"][0]
    s.state.room_title = db.rooms[room]["title"][0]
    return True


def no_walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    return False


@pytest.fixture(autouse=True)
def _records(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))


def echoes(fake):
    return "\n".join(fake.echoed)


def run(fake, words=(), kinds=("delivery",), walk_fn=walk):
    script.run(
        fake, script.parse_args(list(words)), {"task_kinds": list(kinds)}, MAP, walk_fn
    )
    return echoes(fake)


def test_a_delivery_is_asked_accepted_carried_and_handed_over():
    fake = Fake(
        {
            "task": [JOURNAL_CLEAR, JOURNAL_CLEAR],
            "ask cormyn": [DELIVERY_OFFER],
            "accept": [ACCEPTED],
            "stow": [STOWED],
            "get": [GOT_BASKET],
            "give": [PAID],
        }
    )
    out = run(fake, ["cormyn"])
    assert fake.sent[:3] == ["task", "ask cormyn for task", "accept task"]
    assert "stow my basket" in fake.sent
    assert fake.walks == [{10021}]
    assert "get my basket" in fake.sent
    assert "give #172475803 to Saeru" in fake.sent
    assert "task: accepted — a delivery to Saeru in Throne City" in out
    assert "task: delivered — Saeru paid 314 Lirums" in out
    assert "task: the journal is clear" in out
    assert script.load("Lanival") is None  # the record is cleared when done


def test_an_offer_of_a_kind_not_allowed_is_declined_inside_the_window():
    fake = Fake({"ask cormyn": [RECOVERY_OFFER]})
    out = run(fake, ["cormyn"])
    assert fake.sent == ["task", "ask cormyn for task", "decline task"]
    assert "a recovery task — not in task_kinds (delivery) — declined" in out
    fake = Fake({"ask cormyn": [RECOVERY_OFFER], "accept": [ACCEPTED]})
    run(fake, ["cormyn"], kinds=("delivery", "recovery"))
    assert "accept task" in fake.sent


def test_the_cooldown_is_said_and_nothing_else_sent():
    fake = Fake({"ask cormyn": [COOLDOWN]})
    out = run(fake, ["cormyn"])
    assert fake.sent == ["task", "ask cormyn for task"]
    assert "says to wait — ten minutes between asks" in out


def test_a_task_in_the_journal_is_carried_on_from_the_record():
    # A stop short of the shop (its night): the next ;task reads the
    # journal, takes the item's noun from the record, and delivers.
    script.record(
        "Lanival", {"kind": "delivery", "item": "basket", "exist": "172475803"}
    )
    fake = Fake({"task": [JOURNAL, JOURNAL_CLEAR], "get": [GOT_BASKET], "give": [PAID]})
    out = run(fake)
    assert "task: carrying on a delivery to Saeru in Throne City" in out
    assert fake.walks == [{10021}] and "give #172475803 to Saeru" in fake.sent
    assert "task: delivered — Saeru paid 314 Lirums" in out


def test_a_walk_that_ends_short_is_said_with_the_nights_hint_and_the_record_kept():
    fake = Fake(
        {
            "ask cormyn": [DELIVERY_OFFER],
            "accept": [ACCEPTED],
            "stow": [STOWED],
        }
    )
    out = run(fake, ["cormyn"], walk_fn=no_walk)
    assert "stopped short of Saeru" in out and "sunrise" in out
    assert "give" not in " ".join(fake.sent)
    assert script.load("Lanival")["item"] == "basket"


def test_no_task_and_no_giver_says_how_to_ask():
    fake = Fake({})
    out = run(fake)
    assert fake.sent == ["task"] and ";task <giver> asks one" in out


def test_parse_args():
    assert script.parse_args(["cormyn"]) == {"giver": "cormyn", "item": ""}
    assert script.parse_args(["item=basket"]) == {"giver": "", "item": "basket"}
    assert script.parse_args(["Cormyn", "item=basket"]) == {
        "giver": "cormyn",
        "item": "basket",
    }
