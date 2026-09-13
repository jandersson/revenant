"""How ;attune trains — these tests are the manual. It loops a chain
of street rooms, POWERs on every arrival, waits out a room that paid
within the minute, holds at mind-lock, and stops on danger, on a
typed stop, or when perceives stop paying."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "attune_script", REPO / "scripts/attune.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01

# Captured 2026-09-12 on a circle-1 Paladin.
PERCEIVE = (
    "You reach out with your weak senses and see glowing streams of golden Holy "
    "mana radiating through the area.  Waves of black ripple through the mana streams.\n"
    "Roundtime: 8 sec.\n"
)


def street(n=5):
    rooms = []
    for i in range(1, n + 1):
        wayto = {}
        if i > 1:
            wayto[str(i - 1)] = "west"
        if i < n:
            wayto[str(i + 1)] = "east"
        rooms.append(
            {"id": i, "uid": [100 + i], "title": [f"[Street {i}]"], "wayto": wayto}
        )
    return MapDB(rooms)


MAP = street()


class Fake:
    """A handle whose Attunement mindstate follows a script of values —
    one per POWER, or one per second while held at the lock — with a
    fake clock (a POWER costs 9 s, a walk 2 s) and a typed "return" that
    arrives once the clock reaches `stop_at`."""

    def __init__(self, mindstates, stop_at=None, hostiles=None, dead=False):
        self.mindstates = list(mindstates)
        self.stop_at = stop_at
        self.stopped = False
        self.now = 1000.0
        self.sent, self.echoed, self.walks, self.slept = [], [], [], []
        self.pending = []
        self.dead = dead
        self.args = []
        self.state = SimpleNamespace(
            experience={
                "Attunement": {
                    "rank": 2,
                    "percent": 16,
                    "mindstate": self.mindstates.pop(0),
                }
            }
            if self.mindstates
            else {},
            hostiles=hostiles or {},
            room_uid=101,
        )

    def _next_mindstate(self):
        if self.mindstates:
            self.state.experience["Attunement"]["mindstate"] = self.mindstates.pop(0)

    def put(self, command):
        self.sent.append(command)
        if command == "power":
            self.pending = [line + "\n" for line in PERCEIVE.splitlines()]
            self.now += 9  # the roundtime
            self._next_mindstate()

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def command(self, timeout=None):
        if self.stop_at is not None and not self.stopped and self.now >= self.stop_at:
            self.stopped = True
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds
        if self.held:  # the pool drains while held
            self._next_mindstate()

    @property
    def held(self):
        return any("mind-locked" in line for line in self.echoed)


def walk(s, db, goals, describe="", avoid=()):
    room = min(goals)
    s.walks.append(room)
    s.state.room_uid = db.rooms[room]["uid"][0]
    s.now += 2
    return True


def echoes(fake):
    return "\n".join(fake.echoed)


def run(fake, args=(), mapdb=MAP):
    script.clock = lambda: fake.now
    script.run(fake, script.parse_args(list(args)), mapdb=mapdb, walk_fn=walk)


def test_args():
    assert script.parse_args(["rooms=3", "until=30"]) == {
        "rooms": 3,
        "until": 30,
        "here": False,
        "once": False,
        "from": "",
    }
    assert script.parse_args(["from=Hodierna"])["from"] == "hodierna"
    assert script.parse_args(["here", "once"]) == {
        "rooms": 4,
        "until": 34,
        "here": True,
        "once": True,
        "from": "",
    }


def test_it_loops_the_street_perceiving_on_every_arrival_until_mind_lock():
    # 4 → 34 in steps of 2: fifteen POWERs, then the lock, then a typed stop
    fake = Fake(mindstates=list(range(4, 35, 2)), stop_at=2000)
    run(fake)
    assert fake.sent.count("power") == 15
    assert fake.walks[:8] == [2, 3, 4, 5, 4, 3, 2, 1]  # out and back
    assert "looping 4 rooms out and back" in echoes(fake)
    assert "mind-locked (34/34)" in echoes(fake)
    assert fake.echoed[-1] == "attune: stopping"  # the typed stop, while held


def test_a_room_that_paid_within_the_minute_is_waited_out():
    # two rooms: 1 ↔ 2; the loop is [2, 1]; a visit is a 2 s walk and a
    # 9 s roundtime, so room 2 comes round 13 s after it paid: wait 47 s
    fake = Fake(mindstates=[4, 6, 8, 10], stop_at=1075)
    run(fake, ["rooms=1"], mapdb=street(2))
    assert fake.sent.count("power") == 3
    assert 47 <= sum(fake.slept) <= 55  # in one-second slices, so a stop lands at once
    assert all(slice_ <= 1 for slice_ in fake.slept)


def test_here_perceives_in_place_once_a_minute_and_never_walks():
    fake = Fake(mindstates=[4, 6, 8, 10], stop_at=1080)
    run(fake, ["here"], mapdb=None)
    assert fake.walks == []
    assert fake.sent.count("power") == 2
    assert 60 <= sum(fake.slept) <= 65


def test_a_stop_typed_during_the_hold_lands_within_a_second():
    # the mindstate never drains; ;train's stop word arrives 3 s in
    fake = Fake(mindstates=[34], stop_at=1003)
    run(fake)
    assert "mind-locked" in echoes(fake)
    assert fake.echoed[-1] == "attune: stopping"
    assert sum(fake.slept) <= 4  # not a 30-second poll


def test_once_exits_at_mind_lock_instead_of_holding():
    fake = Fake(mindstates=[32, 34])
    run(fake, ["once"])
    assert fake.sent.count("power") == 1
    assert "Attunement at 34/34 — done" in echoes(fake)
    assert "mind-locked" not in echoes(fake)


def test_hostiles_stop_it_before_a_perceive():
    fake = Fake(mindstates=[4], hostiles={"a rat": 1})
    run(fake)
    assert "hostiles in the room — stopping" in echoes(fake)
    assert "power" not in fake.sent


def test_perceives_that_stop_paying_end_the_walk():
    fake = Fake(mindstates=[10] + [10] * 20)
    run(fake)
    assert fake.sent.count("power") == script.STALE_LIMIT
    assert "perceives without gain" in echoes(fake)


def test_a_guild_without_attunement_is_told_so():
    fake = Fake(mindstates=[])
    run(fake)
    assert fake.sent == ["exp attunement"]
    assert "cannot train it" in echoes(fake)


def test_a_clear_pool_is_read_from_the_exp_answer_not_called_no_magic():
    # 2026-09-13: a Paladin's Attunement drained to "clear" left the exp
    # window, and the script said a guild without magic cannot train it.
    class Answering(Fake):
        def put(self, command):
            super().put(command)
            if command == "exp attunement":
                self.pending = [
                    "SKILL: Rank/Percent towards next rank/Amount learning/"
                    "Mindstate fraction\n",
                    "      Attunement:     18 97.08% clear          (0/34)\n",
                ]
                # The first POWER puts the skill back in the window.
                self.mindstates = [2, 4, 34]

    fake = Answering(mindstates=[])
    fake.state.experience = {}
    original = fake._next_mindstate

    def next_mindstate():
        if "Attunement" not in fake.state.experience and fake.mindstates:
            fake.state.experience["Attunement"] = {
                "rank": 18,
                "percent": 97,
                "mindstate": fake.mindstates.pop(0),
            }
        else:
            original()

    fake._next_mindstate = next_mindstate
    run(fake, ["once"])
    assert "cannot train it" not in echoes(fake)
    assert fake.sent[0] == "exp attunement"
    assert "power" in fake.sent


def test_from_walks_to_the_start_room_before_looping():
    # 2026-09-13: started at the shipyard, "no street to loop from
    # here"; the start room is where the streets are.
    fake = Fake(mindstates=[4, 6, 8, 10, 34])
    run(fake, ["from=3", "once"])
    assert fake.walks[0] == 3  # the start room first
    assert fake.sent[0] == "power"
    assert "nothing in the map" not in echoes(fake)


def test_the_profiles_attune_start_is_the_default_start_room(monkeypatch, tmp_path):
    import json

    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    (tmp_path / "lanival.json").write_text(json.dumps({"attune_start": "4"}))
    fake = Fake(mindstates=[4, 6, 8, 10, 34])
    fake.state.name = "Lanival"
    run(fake, ["once"])
    assert fake.walks[0] == 4
    # from= overrides it for the run; an unknown target is said.
    fake = Fake(mindstates=[4, 34])
    fake.state.name = "Lanival"
    run(fake, ["from=nowhere"])
    assert fake.walks == []
    assert "nothing in the map matches start room 'nowhere'" in echoes(fake)


def test_a_room_with_no_street_is_refused():
    fake = Fake(mindstates=[4])
    lone = MapDB([{"id": 1, "uid": [101], "title": ["[Shop]"], "wayto": {}}])
    run(fake, mapdb=lone)
    assert "no street to loop" in echoes(fake)
    assert "power" not in fake.sent


def test_until_holds_at_a_lower_target_and_resumes_when_drained():
    # to 30, hold (the pool drains to 20 while held), one more perceive, stop
    fake = Fake(mindstates=[28, 30, 20], stop_at=1052)
    run(fake, ["until=30"])
    assert "mind-locked (30/34)" in echoes(fake)
    assert "walking again" in echoes(fake)
    assert fake.sent.count("power") == 2
