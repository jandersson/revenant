"""How ;climbexp runs an experiment — these tests are the manual.

Context first (INFO, ENC, APPRAISE), optional attempts before the
train, the walk to the stat's trainer and TRAIN twice, the walk back,
then attempts until the climb goes or the cap or a floor ends it —
every attempt a row with its context.
"""

import importlib.util
import pathlib
import sqlite3
from types import SimpleNamespace

from client.game import climblog
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _climbexp():
    spec = importlib.util.spec_from_file_location(
        "climbexp_script", REPO / "scripts/climbexp.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


climbexp = _climbexp()
climbexp.COLLECT_SECONDS = 0.01
climbexp.TAIL_SECONDS = 0.01
climbexp.ARRIVAL_TIMEOUT = 0.05
climbexp.BETWEEN = 0

INFO = "     Strength :  10              Reflex :   8\n      Agility :   8\n         TDPs : 347\n  Encumbrance : Burdened\n"
INFO_AFTER = "     Strength :  10              Reflex :   8\n      Agility :   9\n         TDPs : 330\n  Encumbrance : Burdened\n"
FOOTING = (
    "Your plate vambraces makes the climb more difficult.\n"
    "You pick your way up the tree, but reach a point where your footing is "
    "questionable.  Reluctantly, you climb back down.\n"
)
MAP = MapDB(
    [
        {
            "id": 6153,
            "uid": [224005],
            "title": ["[Wilderness, Deep Forest]"],
            "wayto": {},
        },
        {
            "id": 50986,
            "uid": [9001],
            "title": ["[The Academy of Agility]"],
            "tags": ["agility"],
            "wayto": {},
        },
    ]
)


class Fake:
    """A handle whose answers come from a script per command prefix and
    whose climbs answer from a list ("up" or a refusal text)."""

    def __init__(self, climbs, answers=None, health=100):
        self.climbs = list(climbs)
        self.answers = answers or {}
        self.sent = []
        self.echoed = []
        self.walks = []
        self.pending = []
        self.dead = False
        self.state = SimpleNamespace(
            name="Lanival",
            room_uid=224005,
            experience={"Athletics": {"rank": 7, "percent": 44, "mindstate": 3}},
            vitals={"health": health},
            indicator={},
            hostiles={},
        )

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        if command.startswith("climb"):
            answer = self.climbs.pop(0) if self.climbs else "stalled"
            if answer == "up":
                self.pending = [("compass", "n")]
            elif answer != "stalled":
                self.pending = [("", line + "\n") for line in answer.splitlines()]
            return
        for prefix, queue in self.answers.items():
            if command.startswith(prefix) and queue:
                text = queue.pop(0)
                self.pending = [("", line + "\n") for line in text.splitlines()]
                return

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if not self.pending:
            return None
        stream, text = self.pending.pop(0)
        if streams is None:
            return stream, text
        return text if stream in streams else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    return True


def run(fake, args, mapdb=MAP):
    db = sqlite3.connect(":memory:")
    climblog.ensure_schema(db)
    obstacle, options = climbexp.parse_args(args)
    climbexp.run(fake, obstacle, options, db, mapdb=mapdb, walk_fn=walk)
    return climblog.rows(db)


def test_args_split_the_obstacle_from_the_options():
    assert climbexp.parse_args(["felled", "tree", "train=agility", "cap=5"]) == (
        "felled tree",
        {"train": "agility", "cap": 5, "before": 0, "floor": 70, "tag": ""},
    )


def test_attempts_until_the_climb_goes_each_one_a_row():
    fake = Fake(
        climbs=[FOOTING, FOOTING, "up"],
        answers={
            "info": [INFO],
            "encumbrance": [INFO],
            "appraise": ["You could probably climb it."],
        },
    )
    logged = run(fake, ["felled", "tree", "tag=t1"])
    assert [r["outcome"] for r in logged] == ["footing", "footing", "up"]
    assert (
        logged[0]["hindering"] == "Your plate vambraces makes the climb more difficult."
    )
    assert logged[0]["agility"] == 8 and logged[0]["encumbrance"] == "Burdened"
    assert logged[0]["appraise"] == "You could probably climb it."
    assert logged[0]["athletics_rank"] == 7 and logged[0]["room"] == 6153
    assert (
        fake.sent[:2] == ["info", "encumbrance"]
        and fake.sent[2] == "appraise felled tree"
    )
    assert fake.sent.count("stand") == 3  # before every try
    assert any("up — experiment 't1' done" in text for text in fake.echoed)


def test_the_cap_ends_a_climb_that_never_goes():
    fake = Fake(climbs=[FOOTING] * 5, answers={"info": [INFO]})
    logged = run(fake, ["felled", "tree", "cap=3"])
    assert len(logged) == 3
    assert any("3 attempts without success" in text for text in fake.echoed)


def test_the_health_floor_and_bleeding_stop_it():
    fake = Fake(climbs=[FOOTING] * 5, answers={"info": [INFO]}, health=60)
    assert run(fake, ["felled", "tree"]) == []
    assert any("health 60% under the 70% floor" in text for text in fake.echoed)
    fake = Fake(climbs=[FOOTING] * 5, answers={"info": [INFO]})
    fake.state.indicator = {"IconBLEEDING": "y"}
    assert run(fake, ["felled", "tree"]) == []
    assert any(";tend first" in text for text in fake.echoed)


def test_training_walks_to_the_tagged_room_trains_twice_and_walks_back():
    fake = Fake(
        climbs=[FOOTING, "up"],
        answers={
            "info": [INFO, INFO_AFTER],
            "train": [
                # captured 2026-09-12, see client/game/tdp.py
                "If this is OK, you will need to STUDY once again to get your new rank.",
                "After what seems an astonishing amount of time, you find you have "
                "completed your training in agility.",
            ],
        },
    )
    logged = run(fake, ["felled", "tree", "train=agility", "before=1", "tag=t2"])
    assert fake.walks == [{50986}, {6153}]
    assert fake.sent.count("train") == 2
    phases = [(r["phase"], r["outcome"], r["agility"]) for r in logged]
    assert phases == [
        ("before", "footing", 8),
        ("train", "done", 9),
        ("after", "up", 9),
    ]
    assert logged[1]["tdps"] == 330
    assert any("trained agility" in text for text in fake.echoed)


def test_an_unrecognized_train_answer_stops_before_the_confirming_train():
    fake = Fake(
        climbs=[FOOTING],
        answers={
            "info": [INFO],
            "train": ["The trainer eyes you oddly and says nothing."],
        },
    )
    logged = run(fake, ["felled", "tree", "train=agility"])
    assert fake.sent.count("train") == 1
    assert [(r["phase"], r["outcome"]) for r in logged] == [("train", "unrecognized")]
    assert not any(command.startswith("climb") for command in fake.sent)
    assert any("no point was trained" in text for text in fake.echoed)


def test_a_success_before_the_train_ends_the_experiment():
    fake = Fake(climbs=["up"], answers={"info": [INFO]})
    logged = run(fake, ["felled", "tree", "train=agility", "before=2"])
    assert [r["phase"] for r in logged] == ["before"]
    assert "train" not in fake.sent


def test_show_prints_the_last_experiment(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_HISTORY_DB", str(tmp_path / "history.db"))
    db = climblog.open_history(climbexp.database_path())
    climblog.record(
        db,
        character_name="Lanival",
        experiment="old",
        phase="after",
        attempt=1,
        obstacle="wall",
        outcome="up",
    )
    climblog.record(
        db,
        character_name="Lanival",
        experiment="new",
        phase="after",
        attempt=1,
        obstacle="tree",
        outcome="footing",
    )
    db.close()
    fake = Fake(climbs=[])
    fake.args = ["show"]
    climbexp.main(fake)
    assert fake.echoed[0].startswith("climbexp: new — 1 row(s)")
