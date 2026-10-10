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
    LAPSED,
    PAID,
    RECOVERY_OFFER,
    SEARCHING_ACCEPTED,
    SEARCHING_JOURNAL,
    SEARCHING_OFFER,
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
            "wayto": {"10021": "north", "807": "east"},
        },
        {
            "id": 10021,
            "uid": [2],
            "title": ["[Seven Star Exchange and Pawn]"],
            "wayto": {"807": "east"},
        },
        {
            "id": 807,
            "uid": [3],
            "title": ["[The Crossing, Gildleaf Circle]"],
            "wayto": {"808": "north"},
        },
        {
            "id": 808,
            "uid": [4],
            "title": ["[The Crossing, Gildleaf Circle]"],
            "wayto": {"807": "south"},
        },
        {
            "id": 7900,
            "uid": [5],
            "title": ["[Ranger Guild, Main Hall]"],
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


def run(fake, words=(), declines=(), walk_fn=walk):
    script.run(
        fake,
        script.parse_args(list(words)),
        {"task_declines": list(declines)},
        MAP,
        walk_fn,
    )
    return echoes(fake)


def test_a_delivery_is_asked_accepted_carried_and_handed_over():
    # TASK three times: before the ask, after the accept (its judge),
    # after the give.
    fake = Fake(
        {
            "task": [JOURNAL_CLEAR, JOURNAL, JOURNAL_CLEAR],
            "ask cormyn": [DELIVERY_OFFER],
            "accept": [ACCEPTED],
            "stow": [STOWED],
            "get": [GOT_BASKET],
            "give": [PAID],
        }
    )
    out = run(fake, ["cormyn"])
    assert fake.sent[:4] == ["task", "ask cormyn for task", "accept task", "task"]
    assert "stow my basket" in fake.sent
    assert fake.walks == [{10021}]
    assert "get #172475803" in fake.sent  # by the id the accept recorded (#513)
    assert "give #172475803 to Saeru" in fake.sent
    assert "task: accepted — a delivery to Saeru in Throne City" in out
    assert "task: delivered — Saeru paid 314 Lirums" in out
    assert "task: the journal is clear" in out
    assert script.load("Lanival") is None  # the record is cleared when done


def test_a_kind_the_script_cannot_run_is_accepted_and_handed_over():
    # A script built to learn declines nothing: the recovery is accepted,
    # recorded with the offer's line, and left to the operator.
    fake = Fake(
        {
            "task": [JOURNAL_CLEAR, SEARCHING_JOURNAL],
            "ask cormyn": [RECOVERY_OFFER],
            "accept": [ACCEPTED],
        }
    )
    out = run(fake, ["cormyn"])
    assert fake.sent == ["task", "ask cormyn for task", "accept task", "task"]
    assert (
        "a recovery of the tabard from the poloh'izh near Hara'jaal, Glaren Kweld"
        in out
    )
    assert "yours from here" in out and "lost a very precious tabard" in out
    assert script.load("Lanival")["kind"] == "recovery"


def test_a_kind_in_task_declines_is_declined_inside_the_window():
    fake = Fake({"ask cormyn": [RECOVERY_OFFER], "decline": [LAPSED]})
    out = run(fake, ["cormyn"], declines=("recovery",))
    assert fake.sent == ["task", "ask cormyn for task", "decline task"]
    assert "in task_declines — declined" in out
    assert "said nothing known" not in out


def test_a_searching_task_is_accepted_by_the_journal_and_the_search_begins():
    # ;task's second live run (2026-10-10): the accept's answer is the
    # search's hint; the journal proves the accept; the search starts.
    fake = Fake(
        {
            "task": [JOURNAL_CLEAR, SEARCHING_JOURNAL],
            "ask saeru": [SEARCHING_OFFER],
            "accept": [SEARCHING_ACCEPTED],
        }
    )
    out = run(fake, ["saeru"])
    assert fake.sent[:4] == ["task", "ask saeru for task", "accept task", "task"]
    assert (
        "a search for the locket near The Crossing, Gildleaf Circle (kneel and search)"
        in out
    )
    assert "unrecognized ACCEPT" not in out
    assert fake.walks[0] == {807} and "kneel" in fake.sent
    assert script.load("Lanival")["kind"] == "searching"


def test_an_accept_the_journal_does_not_show_is_reported():
    fake = Fake(
        {
            "task": [JOURNAL_CLEAR, JOURNAL_CLEAR],
            "ask saeru": [SEARCHING_OFFER],
            "accept": [LAPSED],
        }
    )
    out = run(fake, ["saeru"])
    assert "unrecognized ACCEPT TASK answer" in out
    assert script.load("Lanival") is None


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


class TwoBaskets(Fake):
    """Two gift baskets in the pack: GET by id takes that one, GET MY
    BASKET the first the game finds — the wrong one here (#513)."""

    OTHER = {"exist": "160000001", "noun": "basket", "name": "gift basket"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state.possessions = [
            {"exist": self.OTHER["exist"], "name": "gift basket"},
            {"exist": BASKET["exist"], "name": "gift basket"},
        ]

    def put(self, command):
        super().put(command)
        if command == "get my basket":
            self.state.right_hand = dict(self.OTHER)
        elif command.startswith("get #"):
            exist = command[len("get #") :]
            self.state.right_hand = dict(BASKET, exist=exist)


def test_two_baskets_the_recorded_one_is_given():
    script.record(
        "Lanival", {"kind": "delivery", "item": "basket", "exist": "172475803"}
    )
    fake = TwoBaskets({"task": [JOURNAL, JOURNAL_CLEAR], "give": [PAID]})
    run(fake)
    assert "get #172475803" in fake.sent and "get my basket" not in fake.sent
    assert "give #172475803 to Saeru" in fake.sent


def test_two_baskets_and_no_id_the_noun_is_used_and_said():
    # A record from before the id was kept: INV LIST's first basket, and
    # the walk says the noun matched two.
    script.record("Lanival", {"kind": "delivery", "item": "basket"})
    fake = TwoBaskets({"task": [JOURNAL, JOURNAL_CLEAR], "give": [PAID]})
    out = run(fake)
    assert (
        fake.sent[fake.sent.index("give #160000001 to Saeru") - 1] == "get #160000001"
    )
    assert "task: 2 baskets on you and no id for the task's — took #160000001" in out


def test_a_shop_shut_for_the_night_is_knocked_on_each_game_hour_until_it_opens(
    monkeypatch,
):
    # 2026-10-09 23:35 (#512): Saeru's pawn "closed for the night", the
    # door open at sunrise twenty minutes on. The walker marks the shut
    # door; ;task tries it again each game hour and delivers.
    from client.game import walker

    monkeypatch.setattr(script, "GAME_HOUR", 1)
    monkeypatch.setattr(script, "KNOCK_POLL", 1)
    script.record(
        "Lanival", {"kind": "delivery", "item": "basket", "exist": "172475803"}
    )
    tries = []

    def shut_once(s, db, goals, describe="", avoid=()):
        tries.append(set(goals))
        if len(tries) == 1:
            walker.night_shut(s, "[Seven Star Exchange and Pawn]")
            return False
        walker.night_shut(s, False)
        return walk(s, db, goals, describe, avoid)

    fake = Fake({"task": [JOURNAL, JOURNAL_CLEAR], "get": [GOT_BASKET], "give": [PAID]})
    out = run(fake, walk_fn=shut_once)
    assert len(tries) == 2
    assert "is closed for the night — trying the door each game hour" in out
    assert "task: delivered — Saeru paid 314 Lirums" in out


def test_a_walk_that_ends_short_is_said_and_the_record_kept():
    fake = Fake(
        {
            "task": [JOURNAL_CLEAR, JOURNAL],
            "ask cormyn": [DELIVERY_OFFER],
            "accept": [ACCEPTED],
            "stow": [STOWED],
        }
    )
    out = run(fake, ["cormyn"], walk_fn=no_walk)
    assert "stopped short of Saeru — ;task again from here carries on" in out
    assert "closed for the night" not in out  # not the night: no wait
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


# --- a search run end to end (captured 2026-10-10 at Gildleaf Circle) --------

LOCKET = {"exist": "173989977", "noun": "locket", "name": "glaes locket"}
MISS = "You search for a bit, but do not find the item you are looking for.\nRoundtime: 12 sec.\n"
FOUND = "You find a glaes locket lying on the ground!\nRoundtime: 10 sec.\n"
GOT_LOCKET = "You pick up a glaes locket.\n"
HANDED_IN = 'Saeru says, "Thank you very much, Lanival."\nSaeru hands you 250 Lirums.\n'


class SearchFake(Fake):
    """SEARCH misses `misses` times, then finds; GET puts the locket in a
    hand; the base fake's STOW and GIVE empty it."""

    def __init__(self, answers, misses=2, journal=JOURNAL_CLEAR):
        super().__init__(answers, journal=journal)
        self.misses = misses
        self.searches = 0

    def put(self, command):
        if command == "search":
            self.sent.append(command)
            self.searches += 1
            text = MISS if self.searches <= self.misses else FOUND
            self.pending = [line + "\n" for line in text.splitlines()]
            return
        if command.startswith("get "):
            self.sent.append(command)
            self.state.right_hand = dict(LOCKET)
            self.pending = [GOT_LOCKET]
            return
        super().put(command)


def test_a_searching_task_is_searched_found_and_handed_back_to_the_giver():
    fake = SearchFake(
        {
            "task": [JOURNAL_CLEAR, SEARCHING_JOURNAL, JOURNAL_CLEAR],
            "ask saeru": [SEARCHING_OFFER],
            "accept": [SEARCHING_ACCEPTED],
            "stow": [STOWED],
            "give": [HANDED_IN],
        },
        misses=2,
    )
    out = run(fake, ["saeru"])
    # The area's first room: kneel, two misses, the find; get, stand.
    assert fake.walks[0] == {807}
    assert fake.sent.count("search") == 3 and "kneel" in fake.sent
    assert "get locket" in fake.sent and "stand" in fake.sent
    assert "task: found — You find a glaes locket lying on the ground!" in out
    # Stowed for the walk back, the giver's room, the locket given by id.
    assert "stow my locket" in fake.sent
    assert fake.walks[-1] == {10021}
    assert (
        "give #173989977 to Saeru" in fake.sent
    )  # the journal's spelling of the giver
    assert "task: handed in — Saeru paid 250 Lirums" in out
    assert "task: the journal is clear" in out and script.load("Lanival") is None


def test_a_search_moves_to_the_next_room_after_its_searches_and_gives_up_after_the_last(
    monkeypatch,
):
    monkeypatch.setattr(script, "SEARCHES_PER_ROOM", 2)
    fake = SearchFake(
        {
            "task": [JOURNAL_CLEAR, SEARCHING_JOURNAL],
            "ask saeru": [SEARCHING_OFFER],
            "accept": [SEARCHING_ACCEPTED],
        },
        misses=99,
    )
    out = run(fake, ["saeru"])
    assert fake.walks == [{807}, {808}]
    assert fake.sent.count("search") == 4 and fake.sent.count("stand") == 2
    assert "nothing found in 2 room(s)" in out
    assert script.load("Lanival")["kind"] == "searching"  # kept for a later ;task


def test_a_search_already_found_is_only_handed_in_on_a_rerun():
    script.record(
        "Lanival",
        {
            "kind": "searching",
            "giver": "Saeru",
            "item": "glaes locket",
            "area": "near The Crossing, Gildleaf Circle",
        },
    )
    fake = SearchFake({"task": [SEARCHING_JOURNAL, JOURNAL_CLEAR], "give": [HANDED_IN]})
    fake.state.right_hand = dict(LOCKET)
    out = run(fake)
    assert "already on you" in out and fake.sent.count("search") == 0
    assert "give #173989977 to Saeru" in fake.sent


def test_a_rerun_with_the_item_still_in_hand_takes_its_noun_and_gives_to_the_recipients_name():
    # 2026-10-10: an offer read as unknown left the letter in a hand and no
    # item in the record; the next ;task carries the delivery on from the
    # journal and the hand, and GIVEs to the last word of a titled name.
    journal = (
        "You look in your task journal and see the following entry:\n"
        "Saeru wants you to deliver a package to the Ranger Guildleader Kalika in The Crossing.\n"
    )
    paid = (
        'Kalika says, "Thank you very much, Lanival."\nKalika hands you 400 Lirums.\n'
    )
    fake = Fake(
        {
            "task": [journal, JOURNAL_CLEAR],
            "stow": [STOWED],
            "get": [GOT_BASKET],
            "give": [paid],
        }
    )
    fake.state.right_hand = {
        "exist": "174053253",
        "noun": "letter",
        "name": "brown letter",
    }
    out = run(fake)
    assert "carrying on a delivery to Ranger Guildleader Kalika in The Crossing" in out
    assert fake.walks == [{7900}]
    assert "give #174053253 to Kalika" in fake.sent
    assert "task: delivered — Ranger Guildleader Kalika paid 400 Lirums" in out
