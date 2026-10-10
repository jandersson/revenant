"""How ;astral crosses the Astral Plane — these tests are the manual
(#516). Moongate in through the shard here, PERCEIVE to the centre, the
ring of pillars, the destination's conduit, PERCEIVE to its end, Moongate
out. The wordings are the first trip's, Vellano to Besoge, 2026-10-10."""

import importlib.util
import pathlib
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


class Plane:
    """A handle on the plane: `to_centre` and `to_end` are the ways
    PERCEIVE gives room by room; the last step lands on a pillar, or at
    the conduit's end. `press` names a verdict the first PERCEIVE carries."""

    def __init__(self, to_centre, to_end, press=None, known=True):
        self.to_centre = list(to_centre)
        self.to_end = list(to_end)
        self.press = press
        self.known = known
        self.sent, self.echoed = [], []
        self.state = SimpleNamespace(
            room_title="[Fang Cove, Obsidian Dome]", room_objs=DOME_OBJS
        )

    def ask(self, s, command, seconds=None, tail=None):
        self.sent.append(command)
        title = self.state.room_title
        if command == "prepare moongate":
            return "You spread your hands apart then slowly bring them together.\n"
        if command.startswith("focus ") and "Pillar of" in title:
            self.state.room_title = "[Astral Plane, Besoge Conduit]"
            return CONDUIT
        if command.startswith("focus "):
            return FOCUSED if self.known else "You do not recognize this shard.\n"
        if command.startswith("harness"):
            return HARNESSED
        if command == "release mana":
            return "You release all the streams you were concentrating on keeping localized around you.\n"
        if command.startswith("cast "):
            if title.startswith("[Astral Plane"):
                self.state.room_title = "[Caress-of-the-Moons Manor, Hall]"
            else:
                self.state.room_title = "[Astral Plane, Vellano Conduit]"
            return "You are pulled through your unstable Moongate.\n"
        if command == "perceive":
            verdict = ""
            if self.press:
                verdict, self.press = (
                    f"You are {self.press} to maintain your place among the streams.\n",
                    None,
                )
            if "Pillar of" in title:
                return "You sense an immense source of Lunar mana.\n"
            if "Besoge" in title:
                end = (
                    f"You believe the end of the conduit lies {self.to_end[0]}.\n"
                    if self.to_end
                    else "You are already at the end of the conduit.\n"
                )
                return "You believe the center of the microcosm is to the east.\n" + end
            return (
                f"You believe the center of the microcosm is to the {self.to_centre[0]}.\n"
                + verdict
            )
        if command in ("east", "west") and astral.pillar_of(title):
            here = astral.pillar_of(title)
            step = 1 if command == "east" else -1
            pillar = astral.RING[(astral.RING.index(here) + step) % len(astral.RING)]
            self.state.room_title = f"[Astral Plane, Pillar of {pillar}]"
            return ""
        if "Besoge" in title:
            self.to_end.pop(0)
            return EFFORTLESS
        self.to_centre.pop(0)
        if not self.to_centre:
            self.state.room_title = "[Astral Plane, Pillar of Unity]"
        return EFFORTLESS

    def waitrt(self):
        pass

    def echo(self, text):
        self.echoed.append(text)


def run(plane, shard="besoge", harness=100):
    script.ask = plane.ask
    script.probe = SimpleNamespace(collect=lambda *a, **k: "")
    return script.run(plane, {"shard": shard, "harness": harness})


def test_vellano_to_besoge_as_the_first_trip_went():
    plane = Plane(
        to_centre=["southwest", "west", "southwest", "west"], to_end=["north", "west"]
    )
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


def test_the_plane_pressing_harnesses_more_mana():
    plane = Plane(to_centre=["west"], to_end=[], press="struggling")
    assert run(plane, harness=150) == "arrived"
    assert plane.sent.count("harness 150") == 3  # in, the press, out
    assert any("struggling" in e for e in plane.echoed)


def test_a_shard_not_learned_stops_before_the_plane():
    plane = Plane(to_centre=[], to_end=[], known=False)
    assert run(plane) == "entry"
    assert "cast vellano" not in plane.sent
    assert any("not learned vellano" in e for e in plane.echoed)


def test_no_shard_in_the_room_or_an_unknown_destination_sends_nothing():
    plane = Plane(to_centre=[], to_end=[])
    plane.state.room_objs = "You also see a ladder."
    assert run(plane) == "no start" and plane.sent == []
    assert run(Plane([], []), shard="nowhere") == "no shard"
