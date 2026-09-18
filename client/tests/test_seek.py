"""How ;seek finds a wandering NPC — these tests are the manual. It
loops a chain of street rooms and reads every room's listing for the
noun, stops in the room that has it, laps a set number of times, and
walks back to the start on a typed return (#207)."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import seek
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "seek_script", REPO / "scripts/seek.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01

# Riverhaven's Town Square listing, captured 2026-09-18.
SQUARE = (
    "You also see a news stand with a grinning imp on it, a festive meeting "
    "portal, a simple bench, the Temple, a mud-splattered chest, a uniformed "
    "representative and a young alchemist student."
)
# The peddler's room, captured 2026-09-18 on River Road East.
PEDDLER = (
    "You also see a Riverhaven Warden, a tall Human peddler and some rickety steps."
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
    """A handle standing in room 1; `listings` maps a room id to its
    "You also see" text on the Nth arrival there (a list, the last
    entry repeating); a typed "return" arrives after `stop_after`
    walks."""

    def __init__(self, listings=None, stop_after=None, parser_objs=True):
        self.listings = {room: list(texts) for room, texts in (listings or {}).items()}
        self.stop_after = stop_after
        self.stopped = False
        self.sent, self.echoed, self.walks = [], [], []
        self.pending = []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(room_uid=101, room_players=[])
        self.parser_objs = parser_objs
        if parser_objs:
            self.state.room_objs = self._listing(1)

    def _listing(self, room):
        texts = self.listings.get(room)
        if not texts:
            return ""
        return texts.pop(0) if len(texts) > 1 else texts[0]

    def arrive(self, room):
        self.state.room_uid = 100 + room
        text = self._listing(room)
        if self.parser_objs:
            self.state.room_objs = text
        else:
            self.pending = [text + "\n"]  # LOOK's answer

    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return self.pending.pop(0) if self.pending else None

    def command(self, timeout=None):
        if (
            self.stop_after is not None
            and not self.stopped
            and len(self.walks) >= self.stop_after
        ):
            self.stopped = True
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def walk(s, db, goals, describe="", avoid=()):
    room = min(goals)
    s.walks.append(room)
    s.arrive(room)
    return True


def run(fake, args):
    script.run(fake, seek.parse_args(list(args)), MAP, walk_fn=walk)
    return "\n".join(fake.echoed)


def test_args():
    options = seek.parse_args(["tall", "peddler", "rooms=3", "laps=2", "from=389"])
    assert options == {"noun": "tall peddler", "rooms": 3, "laps": 2, "from": "389"}
    assert seek.parse_args([])["noun"] == ""


def test_present_names_the_listing_entry_that_holds_the_noun():
    assert seek.present("peddler", PEDDLER) == "a tall Human peddler"
    assert seek.present("representative", SQUARE) == "a uniformed representative"
    assert seek.present("student", SQUARE) == "a young alchemist student"
    assert seek.present("bench", SQUARE) == "a simple bench"
    assert seek.present("imp", SQUARE) == "a news stand with a grinning imp on it"
    assert seek.present("Temple", SQUARE) == "the Temple"
    assert seek.present("chest", PEDDLER) is None
    assert seek.present("ped", PEDDLER) is None  # a whole word, not a prefix
    assert seek.present("", PEDDLER) is None


def test_present_names_a_player_too():
    assert seek.present("lanival", SQUARE, ["Lanival", "Sable"]) == "Lanival"
    assert seek.present("uthmor", SQUARE, ["Lanival"]) is None


def test_the_loop_is_the_street_chain_out_and_back():
    assert seek.loop(MAP, 1, 3) == [2, 3, 4, 3, 2, 1]
    assert seek.loop(MapDB([{"id": 9, "uid": [1], "title": ["[Alone]"]}]), 9, 3) == []


def test_it_stops_in_the_room_that_lists_the_noun():
    fake = Fake(listings={1: [SQUARE], 2: [SQUARE], 3: [PEDDLER]})
    out = run(fake, ["peddler", "rooms=3"])
    assert fake.walks == [2, 3]
    assert "seek: a tall Human peddler here" in out


def test_the_noun_already_here_means_no_walk():
    fake = Fake(listings={1: [PEDDLER]})
    out = run(fake, ["peddler"])
    assert fake.walks == []
    assert "seek: a tall Human peddler here" in out


def test_it_laps_the_loop_and_gives_up_at_the_start():
    fake = Fake(listings={1: [SQUARE]})
    out = run(fake, ["peddler", "rooms=2", "laps=2"])
    assert fake.walks == [2, 3, 2, 1, 2, 3, 2, 1]
    assert "lap 1 done" in out and "lap 2 done" in out
    assert "no 'peddler' in 2 lap(s)" in out


def test_a_noun_that_appears_on_a_later_lap_is_found_then():
    fake = Fake(listings={2: [SQUARE, PEDDLER]})  # the second arrival at room 2
    out = run(fake, ["peddler", "rooms=2", "laps=3"])
    assert fake.walks == [2, 3, 2]
    assert "seek: a tall Human peddler here" in out


def test_a_typed_return_walks_back_to_the_start():
    fake = Fake(listings={}, stop_after=2)
    out = run(fake, ["peddler", "rooms=3"])
    assert fake.walks == [2, 3, 1]
    assert "returning to the start" in out


def test_a_parser_without_room_objs_looks_instead():
    fake = Fake(listings={2: [PEDDLER]}, parser_objs=False)
    out = run(fake, ["peddler", "rooms=2"])
    assert fake.sent.count("look") >= 1
    assert "seek: a tall Human peddler here" in out


def test_a_room_with_no_street_is_refused():
    lone = MapDB([{"id": 1, "uid": [101], "title": ["[Alone]"], "wayto": {}}])
    fake = Fake()
    script.run(fake, seek.parse_args(["peddler"]), lone, walk_fn=walk)
    assert "no street to loop" in "\n".join(fake.echoed)


def test_no_noun_or_a_stray_return_is_told_the_usage(monkeypatch):
    fake = Fake()
    fake.args = ["return"]
    monkeypatch.setattr(script.MapDB, "load", lambda: MAP)
    script.main(fake)
    assert "what to look for" in "\n".join(fake.echoed)
