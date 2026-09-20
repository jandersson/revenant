"""How ;tdp spends — these tests are the manual. It walks to the
stat's tagged room, TRAINs twice per point, re-asks the stat after
every pair, stops when the TDPs run short or the value does not rise,
and walks back."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location("tdp_script", REPO / "scripts/tdp.py")
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
            "id": 50986,
            "uid": [9001],
            "title": ["[The Academy of Agility]"],
            "tags": ["agility"],
            "wayto": {},
        },
        {
            "id": 50984,
            "uid": [9002],
            "title": ["[Tembeg's Armory, Bellows Room]"],
            "tags": ["strength"],
            "wayto": {},
        },
    ]
)


def info(agility=8, strength=10, tdps=347):
    return (
        f"     Strength :  {strength:>2}              Reflex :   8\n"
        f"      Agility :  {agility:>2}\n         TDPs : {tdps}\n"
    )


def agility(value, cost, tdps):
    return (
        f"Your base Agility is eight ({value}).\n"
        f"It will cost you {cost} TDPs to raise your Agility from {value} to {value + 1}.\n"
        f"You currently have {tdps} TDPs available.\n"
    )


# Captured 2026-09-12 at Crossing's Academy of Agility.
CONFIRM = (
    "You consult with the teachers and together decide that it will take 28 moon "
    "cycles until you successfully train your agility to 9 ranks.  There is also a "
    "fee of 56 Kronars to complete this training.\n"
    "That would leave you 319 time development points afterward.  If this is OK, "
    "you will need to STUDY once again to get your new rank.\n"
)
DONE = (
    "(You now have 319 time development points.)\n"
    "The trainer notes how young you are and that you should keep some coins to "
    "help you get equipped.  So, the cost of 56 Kronars is added to your Provincial "
    "debt.\n"
    "(Your debt has increased by 56 Kronars.)\n"
    "After what seems an astonishing amount of time, you find you have completed "
    "your training in agility.\n"
    "Your attempts to train are praiseworthy, but you must find both the proper "
    "place and the proper teacher first.\n"
)
WRONG_ROOM = (
    "Your attempts to train are praiseworthy, but you must find both the proper "
    "place and the proper teacher first.\n"
)


class Fake:
    """A handle whose answers come from a queue per command prefix."""

    def __init__(self, answers, dead=False):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.walks = []
        self.pending = []
        self.dead = dead
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
    s.state.room_uid = db.rooms[min(goals)]["uid"][0]  # we are there now
    return True


def echoes(fake):
    return "\n".join(fake.echoed)


def test_bare_tdp_shows_the_stats_and_spends_nothing():
    fake = Fake({"info": [info()]})
    script.run(fake, [])
    assert fake.sent == ["info"]
    assert ["tdp:", "Agility", "8"] in [line.split() for line in fake.echoed]
    assert "TDPs 347" in echoes(fake)


def test_bare_tdp_flags_the_stats_below_the_racial_start():
    fake = Fake({"info": ["Name: Lanival   Race: Dwarf   Guild: Paladin\n" + info()]})
    script.run(fake, [])
    assert "below the Dwarf starting stats: Reflex 8 (start 8)" not in echoes(fake)
    assert "below the Dwarf starting stats: Stamina" not in echoes(
        fake
    )  # INFO fixture has none
    fake = Fake(
        {"info": ["Name: Lanival   Race: Dwarf   Guild: Paladin\n" + info(strength=9)]}
    )
    script.run(fake, [])
    assert "below the Dwarf starting stats: Strength 9 (start 10)" in echoes(fake)
    assert "twice over" in echoes(fake)


def test_a_stat_word_quotes_the_next_point_and_a_goal_the_whole_climb():
    fake = Fake(
        {
            "agility": [agility(8, 28, 347)],
            "tdp project": [
                "It will cost you 132 TDPs to reach 12 points in Agility.\n"
            ],
        }
    )
    script.run(fake, ["agi", "12"])
    assert fake.sent == ["agility", "tdp project agility 12"]
    assert "Agility 8 → 9 costs 28 TDPs; you have 347" in echoes(fake)
    assert "Agility to 12 costs 132 TDPs in all" in echoes(fake)
    assert "train" not in fake.sent


PALADIN_INFO = (
    "Name: Lanival Redeemer   Race: Dwarf   Guild: Paladin\n"
    "     Strength :  10              Reflex :   8\n"
    "      Agility :   8            Charisma :  10\n"
    "   Discipline :  12              Wisdom :  10\n"
    " Intelligence :  10             Stamina :  12\n"
    "         TDPs : 347\n"
)


def strength(value, cost, tdps):
    return (
        f"Your base Strength is ten ({value}).\n"
        f"It will cost you {cost} TDPs to raise your Strength from {value} to {value + 1}.\n"
        f"You currently have {tdps} TDPs available.\n"
    )


def test_plan_buys_where_the_training_plan_says_and_keeps_the_reserve(
    monkeypatch, tmp_path
):
    # The ;train task (the operator, 2026-09-20): `auto` is the Paladin
    # tiers — Strength and Stamina to 15 first — so a Paladin at Strength
    # 10 buys Strength; the reserve stops the second point.
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    from client.game import training

    training.save_plan(
        "Lanival", training.load_plan("Lanival") | {"tdp": ["auto"], "tdp_reserve": 300}
    )
    fake = Fake(
        {
            # The plan's INFO, the fee check's INFO (no purse to read in
            # this fixture, #247), the plan's INFO for the second point.
            "info": [PALADIN_INFO, PALADIN_INFO, PALADIN_INFO.replace("347", "317")],
            "strength": [strength(10, 30, 347), strength(11, 33, 317)],
            "train": [CONFIRM, DONE],
        }
    )
    script.run(fake, ["plan", "2"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{50984}, {100}]  # the bellows, then back
    assert fake.sent.count("train") == 2
    assert "Strength is now 11, TDPs 317" in echoes(fake)
    assert "317 on hand keeps 300 — stopping" in echoes(fake)
    assert "tdp: 1 point(s) bought by the plan" in echoes(fake)
    # An empty tdp list spends nothing and walks nowhere.
    training.save_plan("Lanival", training.load_plan("Lanival") | {"tdp": []})
    idle = Fake({"info": [PALADIN_INFO]})
    script.run(idle, ["plan"], mapdb=MAP, walk_fn=walk)
    assert idle.sent == [] and idle.walks == []
    assert "tdp list is empty" in echoes(idle)


def test_training_walks_there_trains_twice_per_point_and_walks_back():
    fake = Fake(
        {
            "info": [info(), info(agility=10, tdps=288)],
            "agility": [agility(8, 28, 347), agility(9, 31, 319), agility(10, 35, 288)],
            "train": [CONFIRM, DONE, CONFIRM, DONE],
        }
    )
    script.run(fake, ["train", "agility", "10"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{50986}, {100}]
    assert fake.sent.count("train") == 4
    assert fake.sent.index("train") > fake.sent.index("agility")
    assert "Agility is now 9, TDPs 319" in echoes(fake)
    assert "Agility is now 10, TDPs 288" in echoes(fake)
    assert "every goal reached" in echoes(fake)
    # the fee shows even when the point took; the flavor does not
    assert "tdp: (Your debt has increased by 56 Kronars.)" in fake.echoed
    assert not any("astonishing" in line for line in fake.echoed)


BANKED_MAP = MapDB(
    list(MAP.rooms.values())
    + [
        {
            "id": 1200,
            "uid": [9100],
            "title": ["[Bank, Teller]"],
            "tags": ["bank"],
            "wayto": {},
        }
    ]
)
EMPTY_PURSE = "Wealth:\n  No Kronars.\n  No Lirums.\n  No Dokoras.\nDebt:\n  No debt.\n"
FULL_PURSE = (  # INFO's shape for a purse with coins (client/game/money.py)
    "Wealth:\n  5 bronze, 6 copper Kronars (56 copper Kronars).\n  No Lirums.\n"
    "Debt:\n  No debt.\n"
)
COUNTED = (
    "The clerk counts out {} and hands them over, making a notation in her ledger.\n"
)


def test_the_fee_is_fetched_from_the_teller_before_the_confirming_train():
    # #247: a day's trainings put 674 copper Kronars on the province's
    # debt — "Since you aren't carrying any Kronars, the cost of the
    # training, 70 Kronars, is added to your debt." — because the plan
    # banked the purse right before the tdps task. The first TRAIN's quote
    # names the fee; INFO's purse is checked against it, the difference
    # withdrawn at the teller, and the trainer asked again on return.
    fake = Fake(
        {
            "info": [
                info() + EMPTY_PURSE,  # the run's own INFO
                info() + EMPTY_PURSE,  # the purse check: nothing carried
                info(agility=9, tdps=319) + FULL_PURSE,  # after the withdrawal
                info(agility=10, tdps=288) + EMPTY_PURSE,
            ],
            "agility": [agility(8, 28, 347), agility(9, 31, 319), agility(10, 35, 288)],
            "train": [CONFIRM, CONFIRM, DONE, CONFIRM, DONE],
            "withdraw": [
                COUNTED.format("5 bronze Kronars"),
                COUNTED.format("6 copper Kronars"),
            ],
        }
    )
    script.run(fake, ["train", "agility", "10"], mapdb=BANKED_MAP, walk_fn=walk)
    # The trainer, the teller, the trainer again, then home.
    assert fake.walks == [{50986}, {1200}, {50986}, {100}]
    assert [c for c in fake.sent if c.startswith("withdraw")] == [
        "withdraw 5 bronze",
        "withdraw 6 copper",
    ]
    assert (
        fake.sent.count("train") == 5
    )  # quote, quote again after the bank, confirm; quote, confirm
    assert any(
        "the fee is 5 bronze and 6 copper Kronars and you carry 0 copper Kronars"
        in line
        for line in fake.echoed
    )
    assert "Agility is now 10, TDPs 288" in echoes(fake)
    # Only the teller's line comes back as the script's own, not the room's chatter.
    assert any("counts out 5 bronze Kronars" in line for line in fake.echoed)


def test_stay_keeps_you_at_the_trainer():
    fake = Fake(
        {
            "info": [info(), info(agility=9)],
            "agility": [agility(8, 28, 347), agility(9, 31, 319)],
            "train": [CONFIRM, DONE],
        }
    )
    script.run(fake, ["train", "agility", "stay"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{50986}]
    assert fake.sent.count("train") == 2


def test_it_stops_when_the_next_point_costs_more_than_you_have():
    fake = Fake(
        {
            "info": [info(tdps=30), info(agility=9, tdps=2)],
            "agility": [agility(8, 28, 30), agility(9, 31, 2)],
            "train": [CONFIRM, DONE],
        }
    )
    script.run(fake, ["train", "agility", "12"], mapdb=MAP, walk_fn=walk)
    assert fake.sent.count("train") == 2
    assert "the next point costs 31 and you have 2" in echoes(fake)
    assert "every goal reached" not in echoes(fake)


def test_a_value_that_did_not_rise_stops_the_run_and_echoes_the_answers():
    fake = Fake(
        {
            "info": [info(), info()],
            "agility": [agility(8, 28, 347), agility(8, 28, 347)],
            "train": [WRONG_ROOM, ""],
        }
    )
    script.run(fake, ["train", "agility", "12"], mapdb=MAP, walk_fn=walk)
    assert fake.sent.count("train") == 1  # a refusal is not followed by a confirm
    assert "you must find both the proper place" in echoes(fake)
    assert "did not rise" in echoes(fake)
    assert fake.walks == [{50986}, {100}]


def test_several_goals_run_in_order_and_a_bad_word_stops_before_walking():
    fake = Fake(
        {
            "info": [info(), info(agility=9, strength=11)],
            "agility": [agility(8, 28, 347), agility(9, 31, 319)],
            "strength": [
                "Your base Strength is ten (10).\n"
                "It will cost you 30 TDPs to raise your Strength from 10 to 11.\n"
                "You currently have 319 TDPs available.\n",
                "Your base Strength is eleven (11).\n"
                "It will cost you 33 TDPs to raise your Strength from 11 to 12.\n"
                "You currently have 289 TDPs available.\n",
            ],
            "train": [CONFIRM, DONE, CONFIRM, DONE],
        }
    )
    script.run(fake, ["train", "agility", "strength", "+1"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{50986}, {50984}, {100}]
    assert "Strength is now 11, TDPs 289" in echoes(fake)

    fake = Fake({"info": [info()]})
    script.run(fake, ["train", "luck"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == []
    assert "name a stat first" in echoes(fake)


def test_a_stat_the_map_has_no_room_for_stops_without_walking():
    fake = Fake({"info": [info()]})
    script.run(fake, ["train", "wisdom"], mapdb=MAP, walk_fn=walk)
    assert "Wisdom: INFO gave no value" in echoes(fake)
    assert fake.walks == []

    fake = Fake({"info": [info(), info()], "reflex": []})
    script.run(fake, ["train", "reflex"], mapdb=MAP, walk_fn=walk)
    assert "no room tagged 'reflex'" in echoes(fake)
    assert fake.walks == []
