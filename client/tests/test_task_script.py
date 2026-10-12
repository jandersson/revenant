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


def test_a_recovery_with_no_weapon_in_the_profile_is_accepted_and_handed_over():
    # A script built to learn declines nothing: the recovery is accepted
    # and recorded; with no weapon ;hunt would fight bare-handed, so it
    # is left to the operator.
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
    assert "names no weapon" in out and "yours from here" in out
    assert script.load("Lanival")["kind"] == "recovery"


TABARD = {"exist": "176392386", "noun": "tabard", "name": "faded tabard"}
RECOVERY_JOURNAL = (
    "You look in your task journal and see the following entry:\n"
    "Cormyn wants you to recover a tabard from poloh'izh near Hara'jaal, "
    "Glaren Kweld.\n"
)
RECOVERED = PAID.replace("Saeru", "Cormyn").replace("314 Lirums", "777 Kronars")


class Hunting(Fake):
    """;hunt task stood in for: started, over at once, and — when it
    found the item — the item's id in the task's record, as the hunt's
    pickup writes it. A GET takes the tabard."""

    def __init__(self, answers, found=True):
        super().__init__(answers)
        self.started, self.found = [], found

    def run(self, name, args=()):
        self.started.append((name, list(args)))
        if self.found:
            script.record("Lanival", {**script.load("Lanival"), "exist": "176392386"})
        return True

    def is_running(self, name):
        return False

    def kill(self, name):
        pass

    def put(self, command):
        super().put(command)
        if command.startswith("get "):
            self.state.right_hand = dict(TABARD)


def run_armed(fake, words=()):
    script.run(fake, script.parse_args(list(words)), {"weapon": "handaxe"}, MAP, walk)
    return echoes(fake)


def test_a_recovery_is_hunted_by_hunt_task_then_handed_to_the_giver():
    fake = Hunting(
        {
            "task": [JOURNAL_CLEAR, RECOVERY_JOURNAL, JOURNAL_CLEAR],
            "ask cormyn": [RECOVERY_OFFER],
            "accept": [ACCEPTED],
            "give": [RECOVERED],
        }
    )
    out = run_armed(fake, ["cormyn"])
    assert fake.started == [("hunt", ["task"])]
    assert fake.walks == [{8261}]  # back to Cormyn
    assert "give #176392386 to Cormyn" in fake.sent  # by the id the hunt recorded
    assert "task: handed in — Cormyn paid 777 Kronars" in out
    assert script.load("Lanival") is None


def test_a_recovery_keeps_the_journals_fuller_item_name():
    # Ioun, 2026-10-11: the offer lost "a very precious ring", the journal
    # and the accept named "a pearl ring" — the name the drop line uses.
    fake = Hunting(
        {
            "task": [
                JOURNAL_CLEAR,
                RECOVERY_JOURNAL.replace("a tabard", "a pearl ring"),
            ],
            "ask cormyn": [RECOVERY_OFFER.replace("tabard", "ring")],
            "accept": [ACCEPTED],
        },
        found=False,
    )
    run_armed(fake, ["cormyn"])
    assert script.load("Lanival")["item"] == "pearl ring"


def test_a_hunt_that_ends_without_the_item_leaves_the_task_to_carry_on():
    fake = Hunting(
        {
            "task": [JOURNAL_CLEAR, RECOVERY_JOURNAL],
            "ask cormyn": [RECOVERY_OFFER],
            "accept": [ACCEPTED],
        },
        found=False,
    )
    out = run_armed(fake, ["cormyn"])
    assert "the hunt ended without the tabard — ;task again hunts on" in out
    assert not fake.walks and not any(c.startswith("give") for c in fake.sent)
    assert script.load("Lanival")["kind"] == "recovery"


STEMS = {"exist": "185113829", "noun": "stems", "name": "nuloe stems"}
# The Leth Deriel trade minister's foraging task, captured 2026-10-12.
JOURNAL_FORAGE = (
    "You look in your task journal and see the following entry:\n"
    "The Leth Deriel trade minister in Leth Deriel wants you to retrieve 3 nuloe "
    "stems.\nYou need to turn in 3 more.\n"
)
FOUND_STEMS = "You manage to find some nuloe stems.\nRoundtime: 4 sec.\n"
TAKES = (
    'The Leth Deriel trade minister takes the stems and says, "Thanks, Lanival!  '
    'I need {} more."\n'
)
FORAGE_PAID = (
    'The Leth Deriel trade minister says, "Thank you very much, Lanival.  I have a '
    'few things here for you, thank you so much for your help."\n'
    "The Leth Deriel trade minister hands you 785 Kronars.\n"
)
GROVE = MapDB(
    [
        {
            "id": 9004,
            "uid": [1],
            "title": ["[Eshar's Trading Post, Main Room]"],
            "wayto": {"2216": "out"},
        },
        {
            "id": 2216,
            "uid": [2],
            "title": ["[Acenamacra Road, Marsh]"],
            "wayto": {"9004": "west"},
        },
        {
            "id": 2217,
            "uid": [3],
            "title": ["[Acenamacra Road, Marsh]"],
            "wayto": {"2216": "west"},
        },
    ]
)


class Foraging(Fake):
    """A find puts a stack of stems in the hand, as GET does; STOW and
    GIVE empty it."""

    def put(self, command):
        super().put(command)
        if command.startswith("forage ") and "manage to find" in "".join(self.pending):
            self.state.right_hand = dict(STEMS)
        elif command.startswith("get "):
            self.state.right_hand = dict(STEMS)


def test_a_foraging_task_is_foraged_a_stack_a_find_and_given_a_stack_at_a_time():
    # 2026-10-12: "each item you give me as one item" — the finds are
    # stowed apart and given one by one until the minister pays.
    fake = Foraging(
        {
            "task": [JOURNAL_FORAGE, JOURNAL_CLEAR],
            "forage nuloe stem": [
                FOUND_STEMS,
                "You forage around but are unable to find anything.\n",
                FOUND_STEMS,
                FOUND_STEMS,
            ],
            "give": [TAKES.format(2), TAKES.format(1), FORAGE_PAID],
        }
    )
    fake.state.room_uid = 1
    script.run(fake, script.parse_args([]), {"task_declines": []}, GROVE, walk)
    out = echoes(fake)
    assert fake.walks == [{2216, 2217}, {9004}]
    assert fake.sent.count("forage nuloe stem") == 4
    assert fake.sent.count("give #185113829 to minister") == 3
    assert "done — the Leth Deriel trade minister paid 785 Kronars" in out
    assert "nuloe stem" in GROVE.rooms[2216]["tags"]  # #535: the find's room


# The Sand Spit barkeep's skinning task, captured 2026-10-12.
JOURNAL_SKINNING = (
    "You look in your task journal and see the following entry:\n"
    "A barkeep in The Crossing wants you to retrieve 2 skins from the province's "
    'storm bull population.  A barkeep will accept "a storm bull hide".  You '
    "still need to turn in 2 more.\n"
)
HIDE = {"exist": "185300001", "noun": "hide", "name": "storm bull hide"}
TAVERN = MapDB([{"id": 13275, "uid": [5], "title": ["[Sand Spit Tavern, Barroom]"]}])


class Skinning(Hunting):
    """;hunt task stood in for; a GET puts a hide in the hand."""

    def put(self, command):
        Fake.put(self, command)
        if command.startswith("get "):
            self.state.right_hand = dict(HIDE)


# The barkeep's answers to each hide and the last, captured 2026-10-12.
BARKEEP_TAKES = 'Barkeep takes the hide and says, "Thanks, Lanival!  I need {} more."\n'
BARKEEP_PAID = (
    'A barkeep says, "Thank you very much, Lanival.  I have a few coins here for '
    "you, thank you so much for your help.  Maybe the locals will rest easier "
    'knowing that you dealt with the problem."\n'
    "A barkeep hands you 7454 Kronars.\n"
)


def test_a_skinning_task_is_hunted_then_given_a_hide_at_a_time():
    # #509: the hides are cut by ;hunt task, kept loose, and each GIVE
    # counts as one, as a foraging giver's does.
    fake = Skinning(
        {"task": [JOURNAL_SKINNING], "give": [BARKEEP_TAKES.format(1), BARKEEP_PAID]}
    )
    script.run(fake, script.parse_args([]), {"weapon": "handaxe"}, TAVERN, walk)
    out = echoes(fake)
    assert fake.started == [("hunt", ["task"])]
    assert fake.walks == [{13275}]  # back to the barkeep
    assert fake.sent.count("give #185300001 to barkeep") == 2
    assert "done — the barkeep paid 7454 Kronars" in out


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
        "a search for the glaes locket near The Crossing, Gildleaf Circle "
        "(kneel and search)" in out  # the journal's fuller name
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


def test_an_ask_inside_the_givers_cooldown_is_not_sent(monkeypatch):
    # #514: the ask that got an offer starts the giver's ten minutes; a
    # ;task inside them says the minutes left and asks nothing.
    clock = [10_000.0]
    monkeypatch.setattr(script, "now", lambda: clock[0])
    declined = Fake({"ask cormyn": [RECOVERY_OFFER], "decline": [LAPSED]})
    run(declined, ["cormyn"], declines=("recovery",))
    clock[0] += 200
    again = Fake({"ask cormyn": [RECOVERY_OFFER]})
    out = run(again, ["cormyn"])
    assert again.sent == ["task"]
    assert "cormyn can be asked again in 7 minute(s)" in out
    clock[0] += 400
    later = Fake({"ask cormyn": [COOLDOWN]})
    run(later, ["cormyn"])
    assert later.sent == ["task", "ask cormyn for task"]


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
    def args(giver="", item="", history=False, any=False, loop=False, radius=None):
        return {
            "giver": giver,
            "item": item,
            "history": history,
            "any": any,
            "loop": loop,
            "radius": radius,
        }

    assert script.parse_args(["cormyn"]) == args("cormyn")
    assert script.parse_args(["item=basket"]) == args(item="basket")
    assert script.parse_args(["Cormyn", "item=basket"]) == args("cormyn", "basket")
    assert script.parse_args(["history"]) == args(history=True)
    assert script.parse_args(["any"]) == args(any=True)
    assert script.parse_args(["loop", "radius=40"]) == args(loop=True, radius=40)
    # 2026-10-12: "minister" stamped one cooldown for every trade minister.
    words = ["Tiger", "Clan", "trade", "minister"]
    assert script.parse_args(words) == args("tiger clan trade minister")


def test_a_ministers_cooldown_is_his_own_and_the_ask_takes_his_noun(monkeypatch):
    from client.game import tasks

    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    tasks.note_ask("Lanival", "leth deriel trade minister", 10_000.0 - 60)
    fake = Fake({"ask minister": [COOLDOWN]})
    run(fake, ["tiger", "clan", "trade", "minister"])
    assert "ask minister for task" in fake.sent  # not held by Leth Deriel's


def test_any_walks_to_the_nearest_giver_whose_ten_minutes_are_up(monkeypatch):
    # The operator, 2026-10-11: "We should get tasks from givers who are
    # available" — Cormyn asked at 21:12 said "9 minute(s)" at 21:14.
    from client.game import tasks

    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    tasks.note_ask("Lanival", "cormyn", 10_000.0 - 60)
    fake = Fake({"ask saeru": [COOLDOWN]})
    out = run(fake, ["any"])
    assert "task: Saeru is the nearest giver free to ask" in out
    assert fake.walks == [{10021}]  # one step north of Cormyn's
    assert "ask saeru for task" in fake.sent
    assert "ask cormyn for task" not in fake.sent


def test_any_asks_the_towns_trade_minister_by_the_word_the_game_takes(monkeypatch):
    # 2026-10-11, Eshar's Trading Post: ;task any walked 64 steps to the
    # barkeep past the Leth Deriel trade minister, whom the givers' table
    # did not hold; the ministers give foraging and skinning tasks.
    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    post = MapDB(
        [{"id": 9004, "uid": [9], "title": ["[Eshar's Trading Post, Main Room]"]}]
    )
    fake = Fake({"ask minister": [COOLDOWN]})
    fake.state.room_uid = 9
    fake.state.room_title = "[Eshar's Trading Post, Main Room]"
    script.run(fake, script.parse_args(["any"]), {}, post, walk)
    assert "task: leth deriel trade minister is the nearest giver free to ask" in (
        "\n".join(fake.echoed)
    )
    assert "ask minister for task" in fake.sent


def test_any_with_no_giver_free_within_reach_says_so(monkeypatch):
    from client.game import tasks

    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    for giver in ("cormyn", "saeru"):
        tasks.note_ask("Lanival", giver, 10_000.0 - 60)
    fake = Fake({})
    out = run(fake, ["any"])
    assert "no giver free to ask within reach" in out
    assert fake.sent == ["task"]


def test_any_past_its_radius_asks_no_one(monkeypatch):
    from client.game import tasks

    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    tasks.note_ask("Lanival", "cormyn", 10_000.0 - 60)  # here, inside his ten minutes
    fake = Fake({})
    out = run(fake, ["any", "radius=0"])  # Saeru is one step away
    assert "no giver free to ask within 0 steps" in out
    assert fake.sent == ["task"] and not fake.walks


def loop_with(monkeypatch, results, last_ask=0.0):
    """;task loop over rounds that end as `results` say; the sleeps it took."""
    from client.game import tasks

    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    if last_ask:
        tasks.note_ask("Lanival", "cormyn", last_ask)
    rounds = iter(results)
    monkeypatch.setattr(script, "run", lambda *a, **k: next(rounds))
    fake = Fake({})
    slept = []
    fake.sleep = slept.append
    done = script.loop(fake, script.parse_args(["loop"]), {}, MAP, walk)
    return done, slept, echoes(fake)


def test_loop_runs_task_after_task_until_one_ends_short(monkeypatch):
    done, slept, out = loop_with(monkeypatch, [True, True, False])
    assert done == 2 and "the loop ends — 2 task(s) done" in out


def test_loop_waits_the_characters_gap_after_an_ask(monkeypatch):
    # Fara's "you must wait" came 36 s after Mo's offer (#514).
    done, slept, _ = loop_with(monkeypatch, [False], last_ask=10_000.0 - 30)
    assert slept == [script.LOOP_GAP - 30]


def test_loop_with_no_giver_free_waits_once_then_ends(monkeypatch):
    done, slept, out = loop_with(
        monkeypatch, [True, None, None], last_ask=10_000.0 - 600 + 240
    )
    assert done == 1
    assert "waiting 4 minute(s) for a giver to be free" in out
    assert slept == [240]


def test_loop_with_a_giver_walks_back_to_that_giver_and_asks_no_other(monkeypatch):
    # The Estate Holder representative's skinning tasks, one after another.
    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    fake = Fake({"ask saeru": [COOLDOWN]})
    slept = []
    fake.sleep = slept.append
    done = script.loop(fake, script.parse_args(["loop", "saeru"]), {}, MAP, walk)
    assert done == 0
    assert fake.walks == [{10021}, {10021}]  # before each ask
    assert [c for c in fake.sent if c.startswith("ask")] == ["ask saeru for task"]
    assert "waiting 10 minute(s) for saeru to be free" in echoes(fake)
    assert "ask cormyn for task" not in fake.sent


def test_loop_with_a_giver_the_map_lacks_ends_said(monkeypatch):
    monkeypatch.setattr(script, "now", lambda: 10_000.0)
    fake = Fake({})
    done = script.loop(fake, script.parse_args(["loop", "nobody"]), {}, MAP, walk)
    assert done == 0 and not fake.walks
    assert "nothing in the map matches nobody's room" in echoes(fake)


def test_every_offer_and_its_pay_are_kept_and_history_reads_them(monkeypatch, tmp_path):
    # The operator, 2026-10-11: "Start tracking what task givers assign".
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "history.db"))
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
    run(fake, ["cormyn"])
    history = Fake({"task": [JOURNAL_CLEAR]})
    out = run(history, ["history"])
    assert (
        "task: cormyn delivery: 1 offered, 1 taken, 1 done — Saeru Throne City x1"
        " — paid 314 Lirums — 0 min median"
    ) in out
    assert history.sent == []  # read off the database, nothing asked


# --- a search run end to end (captured 2026-10-10 at Gildleaf Circle) --------

LOCKET = {"exist": "173989977", "noun": "locket", "name": "glaes locket"}
MISS = "You search for a bit, but do not find the item you are looking for.\nRoundtime: 12 sec.\n"
FOUND = "You find a glaes locket lying on the ground!\nRoundtime: 10 sec.\n"
GOT_LOCKET = "You pick up a glaes locket.\n"
HANDED_IN = 'Saeru says, "Thank you very much, Lanival."\nSaeru hands you 250 Lirums.\n'


class SearchFake(Fake):
    """SEARCH misses `misses` times, then finds; GET puts the locket in a
    hand; the base fake's STOW and GIVE empty it."""

    def __init__(self, answers, misses=2, journal=JOURNAL_CLEAR, first=None):
        super().__init__(answers, journal=journal)
        self.misses = misses
        self.searches = 0
        self.first = first  # the first SEARCH's answer, when it is another

    def put(self, command):
        if command == "search":
            self.sent.append(command)
            self.searches += 1
            text = MISS if self.searches <= self.misses else FOUND
            if self.first and self.searches == 1:
                text = self.first
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


def test_a_room_whose_search_finds_a_hidden_way_is_searched_on():
    # 2026-10-11: "You poke around near the base of the boulder and
    # discover a narrow gap." stopped the search as an unknown answer.
    fake = SearchFake(
        {
            "task": [JOURNAL_CLEAR, SEARCHING_JOURNAL, JOURNAL_CLEAR],
            "ask saeru": [SEARCHING_OFFER],
            "accept": [SEARCHING_ACCEPTED],
            "stow": [STOWED],
            "give": [HANDED_IN],
        },
        misses=1,
        first="You poke around near the base of the boulder and discover a narrow gap.",
    )
    out = run(fake, ["saeru"])
    assert fake.sent.count("search") == 2
    assert "please report it" not in out
    assert "task: found" in out


def test_a_bystanders_line_before_the_search_answer_is_read_past(monkeypatch):
    # 2026-10-11, Gildleaf Circle: another player's prayer landed in the
    # SEARCH's window ("unrecognized SEARCH answer 'Tedriel bows his head
    # and chants catechisms.'") and the search's own miss came after it.
    from client.game import act

    prayer = (
        "Tedriel bows his head and chants catechisms.\n"
        "You decipher the signs of a Holy utility spell."
    )
    tail = [MISS]
    monkeypatch.setattr(act, "rest_of_answer", lambda s, seconds=None: tail.pop(0))
    fake = SearchFake(
        {
            "task": [JOURNAL_CLEAR, SEARCHING_JOURNAL, JOURNAL_CLEAR],
            "ask saeru": [SEARCHING_OFFER],
            "accept": [SEARCHING_ACCEPTED],
            "stow": [STOWED],
            "give": [HANDED_IN],
        },
        misses=1,
        first=prayer,
    )
    fake.state.room_players = ["Tedriel"]
    out = run(fake, ["saeru"])
    assert "please report it" not in out
    assert fake.sent.count("search") == 2 and "task: found" in out


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


class Seeking(Fake):
    """;seek stood in for: over at once, the room it ends in listing the
    old blind beggar when `found`."""

    def __init__(self, answers, found=True):
        super().__init__(answers)
        self.started, self.found = [], found

    def run(self, name, args=()):
        self.started.append((name, list(args)))
        if self.found:
            self.state.room_objs = "You also see an old blind beggar."
        return True

    def is_running(self, name):
        return False

    def kill(self, name):
        pass


def test_a_wanderers_delivery_is_sought_through_the_town_then_handed_over():
    # Ioun, 2026-10-11: a gift basket for an old blind beggar in The
    # Crossing, who has no room; ;seek walks the town's streets for him.
    from test_tasks import BEGGAR_JOURNAL

    paid = PAID.replace("Saeru", "The old blind beggar").replace("314", "150")
    fake = Seeking({"task": [BEGGAR_JOURNAL, JOURNAL_CLEAR], "give": [paid]})
    fake.state.right_hand = dict(BASKET)
    out = run(fake)
    assert fake.started == [("seek", ["beggar", "town=The Crossing", "laps=2"])]
    assert "give #172475803 to beggar" in fake.sent
    assert "task: delivered" in out


def test_a_recipient_named_only_by_a_road_is_sought_along_its_rooms():
    # The barkeep, 2026-10-11: "Researcher Trelmik in Reshalia Trade
    # Road" stopped the delivery, "the givers' table has no room".
    journal = (
        "You look in your task journal and see the following entry:\n"
        "Barkeep wants you to deliver a package to Researcher Trelmik in "
        "Reshalia Trade Road.\n"
    )
    road = MapDB(
        [
            {"id": 5101, "uid": [51], "title": ["[Reshalia Trade Road]"]},
            {
                "id": 8261,
                "uid": [1],
                "title": ["[Cormyn's House of Heirlooms]"],
                "wayto": {"5101": "out"},  # a road room no way leads into is not sought
            },
        ]
    )
    paid = PAID.replace("Saeru", "Researcher Trelmik")
    fake = Seeking({"task": [journal, JOURNAL_CLEAR], "give": [paid]})
    fake.state.room_objs = ""
    fake.started = []
    fake.run = lambda name, args=(): (
        fake.started.append((name, list(args)))
        or setattr(fake.state, "room_objs", "You also see Researcher Trelmik.")
        or True
    )
    fake.state.right_hand = dict(BASKET)
    script.run(fake, script.parse_args([]), {}, road, walk)
    assert fake.started == [("seek", ["Trelmik", "area=Reshalia Trade Road", "laps=2"])]
    assert "give #172475803 to Trelmik" in fake.sent


def test_a_wanderer_not_found_stops_the_delivery_with_the_basket_kept():
    from test_tasks import BEGGAR_JOURNAL

    fake = Seeking({"task": [BEGGAR_JOURNAL]}, found=False)
    fake.state.right_hand = dict(BASKET)
    out = run(fake)
    assert not any(c.startswith("give") for c in fake.sent)
    assert "no old blind beggar found in The Crossing" in out


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
