"""How ;astral crosses the Astral Plane — these tests are the manual
(#516). Moongate in through the shard here, PERCEIVE to the centre, the
ring of pillars, the destination's conduit, PERCEIVE to its end, Moongate
out. The wordings are the first trip's, Vellano to Besoge, 2026-10-10."""

import importlib.util
import pathlib
import re
from types import SimpleNamespace

from client.game import astral

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "astral_script", REPO / "scripts/astral.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

DOME_OBJS = (
    "You also see an obsidian pedestal with the silvery-white shard Vellano on it."
)
FOCUSED = (
    "You focus your magical senses on the silvery-white shard Vellano.\n"
    "Reaching past the shard, you sense that the streams of Grazhir's mana flow "
    "steadily and are completely smooth.\n"
    "You recognize this as the shard Vellano and forge a connection to it through "
    "the magical pattern.\nRoundtime: 20 sec.\n"
)
HARNESSED = (
    "You tap into the mana from one hundred of the surrounding streams and attempt "
    "to keep it channeling in a stream around you.\nRoundtime: 2 sec.\n"
    "You feel fully prepared to cast your spell.\n"
)
EFFORTLESS = (
    "You effortlessly maintain your place among the shifting streams of mana.\n"
)
CONDUIT = (
    "You reach out into the seemingly infinite strands of Lunar mana and find a "
    "conduit anchored by the presence of Besoge.\n"
    "You move into the chaotic tides of energy.\n"
)


def test_the_model_reads_the_captured_lines():
    assert astral.shard_here(DOME_OBJS) == "vellano"
    assert astral.shard_here("You also see the silvery shard Asharshpar'i.") == (
        "asharshpar'i"
    )
    assert astral.shard_here("You also see a ladder.") is None
    assert astral.pillar_of("[Astral Plane, Pillar of Unity]") == "Unity"
    assert astral.pillar_of("[Astral Plane, Vellano Conduit]") is None
    assert astral.perceived(
        "You believe the center of the microcosm is to the southwest.\n"
        "You believe the end of the conduit lies east.\n"
    ) == ("southwest", "east")
    assert astral.perceived(
        "You believe the center of the microcosm is to the east.\n"
        "You are already at the end of the conduit.\n"
    ) == ("east", "here")
    assert astral.standing(EFFORTLESS) == "effortless"
    assert astral.standing("You are struggling to maintain your place...") == (
        "struggling"
    )


def test_the_ring_goes_the_short_way():
    # Captured: from the Pillar of Unity, west is the Pillar of Secrets.
    assert astral.ring_moves("Unity", "Secrets") == ["west"]
    assert astral.ring_moves("Nightmares", "Secrets") == ["east", "east"]
    assert astral.ring_moves("Nightmares", "Fortune") == ["west"]
    assert astral.ring_moves("Secrets", "Secrets") == []


ROOMS = {
    "vellano": "[Fang Cove, Obsidian Dome]",
    "besoge": "[Caress-of-the-Moons Manor, Hall]",
}


class Plane:
    """A handle on the plane, standing at Vellano: `centre[shard]` are the
    ways PERCEIVE gives from that shard's conduit to its pillar, room by
    room; `end[shard]` the ways down that conduit to its shard. `press`
    names a verdict the first PERCEIVE carries; `between` one that comes
    between commands, which only the script's flag catches."""

    def __init__(self, centre, end, press=None, known=True, between=None):
        self.centre = {shard: list(ways) for shard, ways in centre.items()}
        self.end = {shard: list(ways) for shard, ways in end.items()}
        self.press = press
        self.known = known
        self.conduit = None  # the shard whose conduit we are in
        self.leaving = False  # toward the centre, not the shard
        self.sent, self.echoed = [], []
        self.state = SimpleNamespace(room_title=ROOMS["vellano"], room_objs=DOME_OBJS)
        self.between = between
        self.flags = ()
        self.perceive_tails = set()

    def flag(self, name, *patterns):
        self.flags = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def flagged(self, name):
        line, self.between = self.between, None
        if line and any(pattern.search(line) for pattern in self.flags):
            return line
        return None

    def at(self, shard):
        self.state.room_title = ROOMS[shard]
        self.state.room_objs = f"You also see the silvery-white shard {shard.title()}."

    def in_conduit(self, shard, leaving):
        self.conduit, self.leaving = shard, leaving
        self.state.room_title = f"[Astral Plane, {shard.title()} Conduit]"
        self.state.room_objs = ""

    def ask(self, s, command, seconds=None, tail=None):
        self.sent.append(command)
        title = self.state.room_title
        verb, _, word = command.partition(" ")
        if command == "prepare moongate":
            return "You spread your hands apart then slowly bring them together.\n"
        if verb == "focus" and "Pillar of" in title:
            self.in_conduit(word, leaving=False)
            return CONDUIT.replace("Besoge", word.title())
        if verb == "focus":
            return FOCUSED if self.known else "You do not recognize this shard.\n"
        if verb == "harness":
            return HARNESSED
        if command == "release mana":
            return "You release all the streams you were concentrating on.\n"
        if verb == "cast":
            if title.startswith("[Astral Plane"):
                self.at(word)
            else:
                self.in_conduit(word, leaving=True)
            return "You are pulled through your unstable Moongate.\n"
        if command == "perceive":
            self.perceive_tails.add(tail)
            verdict = ""
            if self.press:
                verdict = f"You are {self.press} to maintain your place.\n"
                self.press = None
            if "Pillar of" in title:
                return "You sense an immense source of Lunar mana.\n"
            if self.leaving:
                way = self.centre[self.conduit][0]
                return (
                    f"You believe the center of the microcosm is to the {way}.\n"
                    + verdict
                )
            ways = self.end[self.conduit]
            end = (
                f"You believe the end of the conduit lies {ways[0]}.\n"
                if ways
                else "You are already at the end of the conduit.\n"
            )
            return "You believe the center of the microcosm is to the east.\n" + end
        if command in ("east", "west") and astral.pillar_of(title):
            here = astral.pillar_of(title)
            step = 1 if command == "east" else -1
            pillar = astral.RING[(astral.RING.index(here) + step) % len(astral.RING)]
            self.state.room_title = f"[Astral Plane, Pillar of {pillar}]"
            return ""
        if self.leaving:
            self.centre[self.conduit].pop(0)
            if not self.centre[self.conduit]:
                pillar = astral.SHARDS[self.conduit][0]
                self.state.room_title = f"[Astral Plane, Pillar of {pillar}]"
            return EFFORTLESS
        self.end[self.conduit].pop(0)
        return EFFORTLESS

    def waitrt(self):
        pass

    def echo(self, text):
        self.echoed.append(text)


def run(plane, *words, walked=None):
    script.ask = plane.ask
    script.probe = SimpleNamespace(collect=lambda *a, **k: "")

    def go(s, target):
        if walked is not None:
            walked.append(target)
        return True

    return script.run(plane, script.parse_args(list(words) or ["besoge"]), go=go)


def first_trip():
    return Plane(
        centre={
            "vellano": ["southwest", "west", "southwest", "west"],
            "besoge": ["south"],
        },
        end={"besoge": ["north", "west"], "vellano": ["east"]},
    )


def test_vellano_to_besoge_as_the_first_trip_went():
    plane = first_trip()
    assert run(plane) == "arrived"
    assert plane.state.room_title == "[Caress-of-the-Moons Manor, Hall]"
    assert plane.sent[:4] == [
        "prepare moongate",
        "focus vellano",
        "harness 100",
        "cast vellano",
    ]
    moves = [
        c for c in plane.sent if c in ("north", "south", "east", "west", "southwest")
    ]
    assert moves == ["southwest", "west", "southwest", "west", "west", "north", "west"]
    assert plane.sent[-5:] == [
        "prepare moongate",
        "focus besoge",
        "harness 100",
        "cast besoge",
        "release mana",
    ]


def test_round_goes_there_and_back_to_the_shard_it_started_from():
    # The ;train task: Astrology and Attunement from one trip each way.
    plane = first_trip()
    assert run(plane, "besoge", "round") == "round"
    assert plane.state.room_title == "[Fang Cove, Obsidian Dome]"
    casts = [c for c in plane.sent if c.startswith("cast ")]
    assert casts == ["cast vellano", "cast besoge", "cast besoge", "cast vellano"]
    # Back from the Pillar of Secrets: east to Unity, Vellano's conduit.
    assert plane.sent.count("release mana") == 2
    assert "focus vellano" in plane.sent[plane.sent.index("cast besoge") :]


def test_from_walks_to_the_home_shard_first():
    walked = []
    plane = first_trip()
    assert run(plane, "besoge", "from=8302", walked=walked) == "arrived"
    assert walked == ["8302"]


def test_the_return_word_is_not_a_shard():
    assert script.parse_args(["besoge", "round", "return"])["shard"] == "besoge"


def test_the_plane_pressing_harnesses_more_mana():
    plane = Plane(centre={"vellano": ["west"]}, end={"besoge": []}, press="struggling")
    assert run(plane, "besoge", "harness=150") == "arrived"
    assert plane.sent.count("harness 150") == 3  # in, the press, out
    assert any("struggling" in e for e in plane.echoed)


def test_perceive_moves_on_as_its_roundtime_ends():
    # The operator, 2026-10-10: 6-9 s a room where PERCEIVE's roundtime
    # is 3 s; the ways come before it, so no tail window is waited.
    plane = first_trip()
    assert run(plane) == "arrived"
    assert plane.perceive_tails == {0}


def test_a_verdict_between_commands_is_caught_by_the_flag():
    # The plane's verdict lands on its own timer, where an ask's clear()
    # would drop it (2026-10-10: after a prompt, never inside an answer).
    plane = Plane(
        centre={"vellano": ["west"]},
        end={"besoge": []},
        between="You are struggling to maintain your place among the shifting streams of mana.",
    )
    assert run(plane, "besoge") == "arrived"
    assert plane.sent.count("harness 100") == 3  # in, the press, out
    assert any("struggling" in e for e in plane.echoed)


def test_a_shard_not_learned_stops_before_the_plane():
    plane = Plane(centre={}, end={}, known=False)
    assert run(plane) == "entry"
    assert "cast vellano" not in plane.sent
    assert any("not learned vellano" in e for e in plane.echoed)


def test_no_shard_in_the_room_or_an_unknown_destination_sends_nothing():
    plane = Plane(centre={}, end={})
    plane.state.room_objs = "You also see a ladder."
    assert run(plane) == "no start" and plane.sent == []
    assert run(Plane({}, {}), "nowhere") == "no shard"
